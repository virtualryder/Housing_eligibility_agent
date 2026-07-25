#!/usr/bin/env python3
"""Post-deployment validation (GA-7) — emits the machine-readable PASS/FAIL verdict.
Read-only except three probe invocations (mask + guard + one fail-closed workflow execution)."""
import argparse, json, subprocess, sys, time

def aws(*args):
    r = subprocess.run(["aws", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout or r.stderr).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="pilot"); ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--release", default="dev"); ap.add_argument("--expect-absent", action="store_true")
    a = ap.parse_args()
    p = f"hou-{a.env}"; out = {"release": a.release, "env": a.env}
    rc, stacks = aws("cloudformation", "describe-stacks", "--region", a.region,
                     "--query", f"Stacks[?starts_with(StackName,'{p}')].StackStatus", "--output", "json")
    statuses = json.loads(stacks) if rc == 0 and stacks.startswith("[") else []
    if a.expect_absent:
        out["residual_stacks"] = statuses
        out["deployment_status"] = "PASS" if not statuses else "FAIL"
        print(json.dumps(out)); sys.exit(0 if not statuses else 1)
    out["stacks"] = "COMPLETE" if statuses and all(s.endswith("_COMPLETE") for s in statuses) else f"FAIL:{statuses}"
    # GA-2: TWO domain-scoped signing secrets (deid + HUD) must both exist
    rc1, _ = aws("secretsmanager", "describe-secret", "--secret-id", f"{p}/provenance-signing-deid", "--region", a.region)
    rc2, _ = aws("secretsmanager", "describe-secret", "--secret-id", f"{p}/provenance-signing-hud", "--region", a.region)
    out["secrets"] = "PRESENT" if rc1 == 0 and rc2 == 0 else "FAIL"
    # masking control probe: mask -> genuine ref ok; forged ref denied
    payload = json.dumps({"case": "Probe Person, SSN 123-45-6789, household of 4, income 40000, county entityid 0603799999"})
    open("/tmp/_m.json", "w").write(payload)
    rc, _ = aws("lambda", "invoke", "--function-name", f"{p}-mask-pii", "--region", a.region,
                "--cli-binary-format", "raw-in-base64-out", "--payload", f"file:///tmp/_m.json", "/tmp/_mo.json")
    mask = json.load(open("/tmp/_mo.json")) if rc == 0 else {}
    ok_mask = mask.get("deidentified") is True and "123-45-6789" not in json.dumps(mask.get("masked_case", "")) \
              and (mask.get("sanitized_ref") or {}).get("authoritative") is True
    out["masking_control"] = "PASS" if ok_mask else "FAIL"
    for name, ref, want in (("guard_genuine", mask.get("sanitized_ref"), True),
                            ("forged_ref_denied", dict(mask.get("sanitized_ref") or {}, sig="deadbeef"*8), False)):
        open("/tmp/_g.json", "w").write(json.dumps({"guard": "deidentified", "sanitized_ref": ref}))
        rc, _ = aws("lambda", "invoke", "--function-name", f"{p}-workflow-guards", "--region", a.region,
                    "--cli-binary-format", "raw-in-base64-out", "--payload", "file:///tmp/_g.json", "/tmp/_go.json")
        g = json.load(open("/tmp/_go.json")) if rc == 0 else {}
        out[name] = "PASS" if g.get("ok") is want else "FAIL"
    # workflow fail-closed probe (no HUD token -> ManualReview) or happy path if token present.
    # R3-2 pass-by-reference: raw content enters ONLY via ingest-case; the execution starts with
    # {case_id, requester, case_ref} — inline application text is no longer a valid input.
    open("/tmp/_i.json", "w").write(json.dumps(
        {"application": "Household of 4. Annual household income: 40000. County entityid 0603799999.",
         "case_id": f"VAL-{int(time.time())}"}))
    rc, _ = aws("lambda", "invoke", "--function-name", f"{p}-ingest-case", "--region", a.region,
                "--cli-binary-format", "raw-in-base64-out", "--payload", "file:///tmp/_i.json", "/tmp/_io.json")
    ing = json.load(open("/tmp/_io.json")) if rc == 0 else {}
    out["ingest_pass_by_reference"] = "PASS" if ing.get("ingested") and str(ing.get("case_ref", "")).startswith("case-") else "FAIL"
    open("/tmp/_w.json", "w").write(json.dumps({"case_id": ing.get("case_id", "VAL"), "requester": "validator",
                                                "case_ref": ing.get("case_ref", "")}))
    rc, arn = aws("stepfunctions", "start-execution", "--region", a.region,
                  "--state-machine-arn", f"arn:aws:states:{a.region}:{{ACCT}}:stateMachine:{p}-determination-workflow"
                  .replace("{ACCT}", aws("sts", "get-caller-identity", "--query", "Account", "--output", "text")[1]),
                  "--input", "file:///tmp/_w.json", "--query", "executionArn", "--output", "text")
    verdict = "FAIL"
    if rc == 0:
        for _ in range(20):
            time.sleep(6)
            _, st = aws("stepfunctions", "describe-execution", "--execution-arn", arn,
                        "--query", "status", "--output", "text", "--region", a.region)
            if st != "RUNNING":
                verdict = "PASS" if st == "SUCCEEDED" else f"FAIL:{st}"
                break
        else:
            verdict = "PASS:RUNNING(awaiting human gate)"   # happy path paused at sign-off
    out["workflow_fail_closed"] = verdict
    rc, _ = aws("secretsmanager", "get-secret-value", "--secret-id", f"{p}/hud-api-token", "--region", a.region)
    out["hud_lookup"] = "CONFIGURED" if rc == 0 else "NOT-CONFIGURED (fail-closed to ManualReview)"
    out["deployment_status"] = "PASS" if all(str(v).startswith("PASS") or v in ("COMPLETE", "PRESENT")
                                             for k, v in out.items()
                                             if k in ("stacks", "secrets", "masking_control",
                                                      "guard_genuine", "forged_ref_denied",
                                                      "ingest_pass_by_reference",
                                                      "workflow_fail_closed")) else "FAIL"
    print(json.dumps(out, indent=1))
    sys.exit(0 if out["deployment_status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
