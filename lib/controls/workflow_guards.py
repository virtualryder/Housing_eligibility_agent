import json

import provenance
import sanitized

# workflow_guards — the machine-verifiable transition evidence for the DETERMINISTIC workflow
# controller (P0-2). The Step Functions controller (cdk/ WorkflowStack) invokes this single Lambda
# between pipeline stages; each guard returns {"guard", "ok", "reason"} and the state machine BRANCHES
# on `ok` — a stage cannot be skipped, reordered, or passed on asserted (unverified) state, because the
# transition itself demands cryptographic or structural proof:
#
#   extracted      -> the intake actually produced the decision fields
#   authoritative  -> the HUD limits carry a VERIFIED lookup-minted provenance signature (P0-3 pattern)
#   deidentified   -> a VERIFIED mask_pii-signed sanitized_ref exists (P0-1; boolean never accepted)
#   rules_executed -> the deterministic rules engine ran and yielded a legal determination
#
# Fail-closed: any missing/forged/tampered evidence -> ok:false; the controller routes to ManualReview
# (NEEDS_REVIEW) — never onward. Pure logic + the shared verifiers, fully unit-testable offline.

_LEGAL_DETERMINATIONS = {"ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"}


def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except Exception:
            e = {}
    return e


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def guard_extracted(e):
    f = e.get("fields") or {}
    ok = bool(f.get("entityid")) and _num(f.get("annual_income")) is not None and f.get("household_size")
    return ok, ("decision fields present" if ok else
                "intake did not yield entityid + annual_income + household_size")


def guard_authoritative(e):
    """Same verification the assessor performs: rebuild the signed field set from the limits the
    workflow will actually use and verify the lookup-minted signature.

    Accepts the WHOLE lookup output under `lookup` (how the controller passes it — a source-down
    lookup returns found:false with NO limit keys, and judging that is THIS guard's job, never a
    JSONPath error in the state machine), or flat il_source/il30/il50/il80 keys for direct calls."""
    if isinstance(e.get("lookup"), dict):
        lk = e["lookup"]
        e = {**lk, "household_size": e.get("household_size", lk.get("household_size"))}
    if e.get("found") is False:
        return False, "authoritative source unavailable (lookup found:false) — manual review"
    src = e.get("il_source")
    if isinstance(src, str):
        try:
            src = json.loads(src)
        except Exception:
            src = None
    if not isinstance(src, dict):
        return False, "no provenance token (il_source) from lookup_income_limit"
    hh = e.get("household_size")
    try:
        hh = int(hh)
    except Exception:
        return False, "household_size missing/invalid"
    fields = {"entityid": str(src.get("entityid") or ""), "year": str(src.get("year") or ""),
              "household_size": hh,
              "il30": _num(e.get("il30")), "il50": _num(e.get("il50")), "il80": _num(e.get("il80"))}
    ok = provenance.verify(src.get("source", ""), fields, src, domain="hud")   # GA-2: HUD trust domain key
    return ok, ("HUD limits carry a verified lookup signature" if ok else
                "income limits are NOT verified authoritative (missing/forged/tampered signature)")


def guard_deidentified(e):
    ok = sanitized.verify_ref(e.get("sanitized_ref"))
    return ok, ("masking proven by a verified mask_pii-signed sanitized_ref" if ok else
                "de-identification not proven (no valid sanitized_ref; a boolean is not proof)")


def guard_rules_executed(e):
    r = e.get("assessment") or {}
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except Exception:
            r = {}
    ok = r.get("assessed") is True and r.get("determination") in _LEGAL_DETERMINATIONS
    return ok, ("deterministic rules engine produced a legal determination" if ok else
                "rules engine did not run or returned no legal determination")


_GUARDS = {
    "extracted": guard_extracted,
    "authoritative": guard_authoritative,
    "deidentified": guard_deidentified,
    "rules_executed": guard_rules_executed,
}


def _emit_metric(guard, ok):
    """R3-3 security telemetry: every guard evaluation emits a CloudWatch EMF metric
    (Housing/Governance :: GuardFailed{Guard}). A failed guard is a SECURITY SIGNAL — forged
    sanitized_ref, tampered provenance, spoofed boolean — not just an ops event; the
    ObservabilityStack alarms on any nonzero sum. Metric only (no payload content), so this adds
    nothing to the telemetry PII surface."""
    import json as _json
    import time as _time
    try:
        print(_json.dumps({
            "_aws": {"Timestamp": int(_time.time() * 1000),
                     "CloudWatchMetrics": [{"Namespace": "Housing/Governance",
                                            "Dimensions": [["Guard"]],
                                            "Metrics": [{"Name": "GuardFailed", "Unit": "Count"}]}]},
            "Guard": guard, "GuardFailed": 0 if ok else 1}))
    except Exception:
        pass   # metrics must never affect the control decision


def handler(event, context):
    e = _coerce(event)
    name = str(e.get("guard", ""))
    fn = _GUARDS.get(name)
    if fn is None:
        _emit_metric(name or "unknown", False)
        return {"guard": name, "ok": False, "reason": "unknown guard (fail-closed)"}
    try:
        ok, reason = fn(e)
    except Exception as exc:  # any guard error is a fail-closed deny, never a pass
        ok, reason = False, "guard error (fail-closed): %s" % type(exc).__name__
    _emit_metric(name, ok)
    return {"guard": name, "ok": bool(ok), "reason": reason}
