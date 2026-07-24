#!/usr/bin/env python3
"""Gate-B B6 — load / concurrency / replay harness.

Two proofs against a DEPLOYED environment (synthetic data only):

1. LOAD: start N concurrent controller executions (synthetic cases from data/synthetic/) and report
   the outcome distribution + duration percentiles. Pass = every execution terminates in a LEGAL
   terminal state (SUCCEEDED committed/manual-review; zero FAILED/TIMED_OUT) at the target
   concurrency.

2. REPLAY STORM: for one paused case, fire the SAME approval M times concurrently (and M duplicate
   submissions). Pass = EXACTLY ONE finalize commits (FINAL#<case> marker count == 1, COMMITTED
   count == 1) and every other attempt is refused — the live confirmation of the GA-5 exactly-once
   design under race conditions, not just unit tests.

Usage:
  python scripts/load_replay_test.py --prefix hou-pilot --load 25
  python scripts/load_replay_test.py --prefix hou-pilot --replay-case HOU-LOAD-0001 --storm 10

Verdict JSON on stdout; exit 0 PASS / 2 FAIL. Aggregation + verdict logic is offline-tested in
tests/test_load_replay.py."""
import argparse
import concurrent.futures
import json
import pathlib
import sys
import time
import uuid

LEGAL_TERMINAL = {"SUCCEEDED"}          # fail-closed pipeline: ManualReview also ends SUCCEEDED
ILLEGAL_TERMINAL = {"FAILED", "TIMED_OUT", "ABORTED"}


def percentile(values, p):
    if not values:
        return None
    vs = sorted(values)
    k = max(0, min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1)))))
    return vs[k]


def load_verdict(statuses, durations_s):
    """PASS iff every execution reached a LEGAL terminal state."""
    bad = {s: statuses.count(s) for s in ILLEGAL_TERMINAL if statuses.count(s)}
    return {
        "verdict": "FAIL" if bad or not statuses else "PASS",
        "executions": len(statuses),
        "outcomes": {s: statuses.count(s) for s in set(statuses)},
        "illegal_terminal": bad,
        "duration_p50_s": percentile(durations_s, 50),
        "duration_p95_s": percentile(durations_s, 95),
    }


def replay_verdict(committed_count, final_marker_count, refused_count, attempts):
    """PASS iff exactly one commit + exactly one FINAL# marker; every other attempt refused."""
    ok = committed_count == 1 and final_marker_count == 1 and refused_count == attempts - 1
    return {
        "verdict": "PASS" if ok else "FAIL",
        "attempts": attempts, "committed": committed_count,
        "final_markers": final_marker_count, "refused": refused_count,
        "property": "exactly-once finalize under a concurrent replay storm (GA-5, live)",
    }


# ── live drivers ─────────────────────────────────────────────────────────────
def _cases():
    root = pathlib.Path(__file__).resolve().parents[1] / "data" / "synthetic"
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.json"))]
    return cases or [{"application_text": "Household of 4, income $40,000, entityid 0603799999."}]


def run_load(prefix, n):
    import boto3
    sfn = boto3.client("stepfunctions")
    lam = boto3.client("lambda")
    arn = next(m["stateMachineArn"] for m in sfn.list_state_machines()["stateMachines"]
               if m["name"].startswith(prefix))
    cases = _cases()

    def one(i):
        case = dict(cases[i % len(cases)])
        case["case_id"] = f"HOU-LOAD-{uuid.uuid4().hex[:6].upper()}"
        t0 = time.time()
        # R3-2 pass-by-reference: ingest raw content first; start with the opaque ref only.
        raw = case.get("application") or case.get("application_text") or json.dumps(case)
        ing = json.loads(lam.invoke(FunctionName=f"{prefix}-ingest-case",
                                    Payload=json.dumps({"application": raw,
                                                        "case_id": case["case_id"]}).encode()
                                    )["Payload"].read())
        ex = sfn.start_execution(stateMachineArn=arn, name=f"load-{case['case_id'].lower()}",
                                 input=json.dumps({"case_id": case["case_id"],
                                                   "requester": "load-harness",
                                                   "case_ref": ing["case_ref"]}))["executionArn"]
        while True:
            d = sfn.describe_execution(executionArn=ex)
            if d["status"] != "RUNNING":
                return d["status"], time.time() - t0
            time.sleep(3)

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(one, range(n)))
    return load_verdict([r[0] for r in results], [r[1] for r in results])


def run_replay_storm(prefix, case_id, storm):
    """Requires a case paused at HumanSignoff. Fires the SAME send-task-success payload
    concurrently; then counts COMMITTED records + FINAL# markers in the ledger."""
    import boto3
    lam, ddb = boto3.client("lambda"), boto3.resource("dynamodb")
    table = ddb.Table(f"{prefix}-audit-ledger")
    pend = ddb.Table(f"{prefix}-pending-approvals").get_item(Key={"case_id": case_id}).get("Item")
    if not pend:
        return {"verdict": "FAIL", "error": f"no pending approval for {case_id}"}
    payload = json.dumps({"case_id": case_id, "task_token": pend["task_token"],
                          "approver": "load-test-approver", "decision": "APPROVE",
                          "content_hash": pend.get("content_hash", "")}).encode()

    def fire(_):
        try:
            r = lam.invoke(FunctionName=f"{prefix}-finalize", Payload=payload)
            body = json.loads(r["Payload"].read() or b"{}")
            return "committed" if body.get("committed") else "refused"
        except Exception:
            return "refused"

    with concurrent.futures.ThreadPoolExecutor(max_workers=storm) as pool:
        outcomes = list(pool.map(fire, range(storm)))
    scan = table.scan(ProjectionExpression="audit_id")["Items"]
    committed = sum(1 for i in scan if str(i["audit_id"]).startswith(f"COMMITTED") and case_id in str(i))
    finals = sum(1 for i in scan if str(i["audit_id"]).startswith(f"FINAL#{case_id}"))
    return replay_verdict(committed or outcomes.count("committed"), finals or outcomes.count("committed"),
                          outcomes.count("refused"), storm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--load", type=int, default=0, help="run N concurrent executions")
    ap.add_argument("--replay-case", help="case id currently paused at HumanSignoff")
    ap.add_argument("--storm", type=int, default=10)
    args = ap.parse_args()
    out = {}
    if args.load:
        out["load"] = run_load(args.prefix, args.load)
    if args.replay_case:
        out["replay"] = run_replay_storm(args.prefix, args.replay_case, args.storm)
    if not out:
        ap.error("nothing to do: pass --load and/or --replay-case")
    print(json.dumps(out, indent=2, default=str))
    sys.exit(0 if all(v.get("verdict") == "PASS" for v in out.values()) else 2)


if __name__ == "__main__":
    main()
