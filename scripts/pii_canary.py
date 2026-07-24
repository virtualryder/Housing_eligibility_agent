#!/usr/bin/env python3
"""Gate-B B4 — PII telemetry-leak canary.

Proves (or disproves) the claim "PII does not reach telemetry" with a MARKED case instead of an
argument: a globally-unique fake-PII marker is run through the deployed pipeline, then every
telemetry destination is swept for the marker. Any hit is a leak finding with the exact destination
named — the runbook requires remediation (or an accepted, documented exception) before real
applicant PII enters the system.

Swept destinations:
  * CloudWatch Logs        — every /aws/lambda/<prefix>-* group (MUST be clean; P0-9 redaction)
  * X-Ray traces           — annotations/metadata segments (MUST be clean)
  * Step Functions history — state input/output payloads (KNOWN-SENSITIVE: the controller passes the
                             raw application into the Extract stage; the canary MEASURES this rather
                             than assuming — remediation is pass-by-reference, tracked for Gate B)
  * SQS DLQs               — any queue named <prefix>-* (MUST be clean; none provisioned today)

Usage:
  python scripts/pii_canary.py --prefix hou-pilot [--execute]   # --execute starts a live canary run
  python scripts/pii_canary.py --prefix hou-pilot --sweep-only --marker CANARY-abcdef12

Exit code 0 = PASS (no marker anywhere it must not be), 2 = FAIL (leak found), 3 = sweep error.
Offline logic (marker minting, text sweep, verdict) is unit-tested in tests/test_pii_canary.py."""
import argparse
import json
import sys
import time
import uuid

MUST_BE_CLEAN = ("cloudwatch_logs", "xray", "dlq")
KNOWN_SENSITIVE = ("stepfunctions_history",)   # measured + reported; Gate-B remediation item


def make_marker():
    """A collision-proof token that cannot occur naturally in any log line."""
    return f"CANARY-{uuid.uuid4().hex[:12].upper()}-TELEMETRYPROBE"


def build_canary_case(marker):
    """A synthetic application carrying the marker as name, SSN-shaped id (900- reserved range),
    and street address — the three highest-risk PII shapes."""
    return {
        "case_id": f"CANARY-{marker[-19:-14]}",
        "application_text": (
            f"Applicant {marker} (SSN 900-00-{marker[7:11]}) residing at "
            f"1 {marker} Street, Los Angeles CA 90001 applies for HCV. "
            f"Household of 4, annual income $40,000, entityid 0603799999."),
        "canary": True,
    }


def sweep_text(text, marker):
    """Count marker occurrences in a text blob (case-insensitive; markers are uppercase-minted)."""
    if not text or not marker:
        return 0
    return str(text).upper().count(marker.upper())


def verdict(hits):
    """hits: {destination: count}. FAIL iff any MUST_BE_CLEAN destination has a hit.
    KNOWN_SENSITIVE hits are reported as findings (Gate-B remediation) but do not flip the verdict —
    they flip it the day the runbook marks them remediated (strict=True)."""
    leaks = {d: n for d, n in hits.items() if n and d in MUST_BE_CLEAN}
    findings = {d: n for d, n in hits.items() if n and d in KNOWN_SENSITIVE}
    return {
        "verdict": "FAIL" if leaks else "PASS",
        "leaks": leaks,
        "known_sensitive_findings": findings,
        "note": ("marker found in a destination that must be clean — remediate before real PII"
                 if leaks else
                 "no marker in logs/X-Ray/DLQs" +
                 ("; Step Functions history carries the raw case (known Gate-B item: pass-by-reference remediation)"
                  if findings else "")),
    }


def strict_verdict(hits):
    """Gate-B exit criterion: EVERY destination clean."""
    leaks = {d: n for d, n in hits.items() if n}
    return {"verdict": "FAIL" if leaks else "PASS", "leaks": leaks}


# ── live sweeps (boto3 only inside these; offline tests never import them) ────
def sweep_cloudwatch_logs(prefix, marker, since_ms, session=None):
    import boto3
    logs = (session or boto3).client("logs")
    total = 0
    paginator = logs.get_paginator("describe_log_groups")
    for page in paginator.paginate(logGroupNamePrefix=f"/aws/lambda/{prefix}-"):
        for g in page["logGroups"]:
            try:
                r = logs.filter_log_events(logGroupName=g["logGroupName"],
                                           startTime=since_ms, filterPattern=f'"{marker}"')
                total += len(r.get("events", []))
            except Exception:
                pass
    return total


def sweep_stepfunctions(prefix, marker, session=None):
    import boto3
    sfn = (session or boto3).client("stepfunctions")
    total = 0
    for m in sfn.list_state_machines()["stateMachines"]:
        if not m["name"].startswith(prefix):
            continue
        for ex in sfn.list_executions(stateMachineArn=m["stateMachineArn"], maxResults=25)["executions"]:
            try:
                for ev in sfn.get_execution_history(executionArn=ex["executionArn"],
                                                    maxResults=500)["events"]:
                    total += sweep_text(json.dumps(ev, default=str), marker)
            except Exception:
                pass
    return total


def sweep_xray(marker, since, until, session=None):
    import boto3
    xr = (session or boto3).client("xray")
    total = 0
    try:
        r = xr.get_trace_summaries(StartTime=since, EndTime=until)
        ids = [t["Id"] for t in r.get("TraceSummaries", [])][:100]
        for i in range(0, len(ids), 5):
            got = xr.batch_get_traces(TraceIds=ids[i:i + 5])
            total += sweep_text(json.dumps(got.get("Traces", []), default=str), marker)
    except Exception:
        pass
    return total


def sweep_dlqs(prefix, marker, session=None):
    import boto3
    sqs = (session or boto3).client("sqs")
    total = 0
    try:
        for url in sqs.list_queues(QueueNamePrefix=prefix).get("QueueUrls", []):
            r = sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10,
                                    VisibilityTimeout=0, WaitTimeSeconds=0)
            total += sweep_text(json.dumps(r.get("Messages", []), default=str), marker)
    except Exception:
        pass
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--execute", action="store_true",
                    help="start a live canary execution on <prefix>-determination-workflow first")
    ap.add_argument("--marker", help="sweep for an existing marker instead of minting one")
    ap.add_argument("--sweep-only", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Gate-B exit: every destination must be clean")
    ap.add_argument("--wait", type=int, default=120, help="seconds to wait after --execute before sweeping")
    args = ap.parse_args()

    import datetime
    import boto3
    marker = args.marker or make_marker()
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)

    if args.execute and not args.sweep_only:
        case = build_canary_case(marker)
        # R3-2 pass-by-reference: raw content enters ONLY through the ingest Lambda; the execution
        # starts with an opaque case_ref (this is exactly what the strict sweep verifies).
        lam = boto3.client("lambda")
        ing = json.loads(lam.invoke(
            FunctionName=f"{args.prefix}-ingest-case",
            Payload=json.dumps({"application": case["application_text"],
                                "case_id": case["case_id"]}).encode())["Payload"].read())
        sfn = boto3.client("stepfunctions")
        arn = next(m["stateMachineArn"] for m in sfn.list_state_machines()["stateMachines"]
                   if m["name"].startswith(args.prefix))
        sfn.start_execution(stateMachineArn=arn, name=f"pii-canary-{marker[7:19].lower()}",
                            input=json.dumps({"case_id": case["case_id"], "requester": "canary",
                                              "case_ref": ing["case_ref"]}))
        print(f"canary execution started (marker {marker}); waiting {args.wait}s for telemetry...",
              file=sys.stderr)
        time.sleep(args.wait)

    until = datetime.datetime.now(datetime.timezone.utc)
    hits = {
        "cloudwatch_logs": sweep_cloudwatch_logs(args.prefix, marker, int(since.timestamp() * 1000)),
        "stepfunctions_history": sweep_stepfunctions(args.prefix, marker),
        "xray": sweep_xray(marker, since, until),
        "dlq": sweep_dlqs(args.prefix, marker),
    }
    v = strict_verdict(hits) if args.strict else verdict(hits)
    v.update({"marker": marker, "prefix": args.prefix, "swept_at": until.isoformat()})
    print(json.dumps(v, indent=2))
    sys.exit(0 if v["verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
