"""P0-2 — deterministic workflow controller. Two layers, both offline:

1. GUARDS: every transition guard (workflow_guards.py) passes on genuine evidence and FAILS CLOSED on
   missing/forged/tampered evidence — the machine-verifiable transitions of the state machine.
2. STATE MACHINE SHAPE (see tests/test_cdk_stacks.py): the synthesized ASL contains the pipeline in
   order with a fail-closed Choice after every guard routing to ManualReview.
"""
import json
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")

from toolkit import CONTROLS, make_sanitized_ref  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(CONTROLS))
import provenance  # noqa: E402
import workflow_guards as wg  # noqa: E402

SOURCE = "US Dept of Housing and Urban Development (HUD USER) — Income Limits"


def _signed_source(hh=4, il30=50000, il50=83300, il80=133250):
    fields = {"entityid": "0603799999", "year": "2026", "household_size": hh,
              "il30": il30, "il50": il50, "il80": il80}
    tok = provenance.sign(SOURCE, fields)
    return {"source": SOURCE, "entityid": "0603799999", "year": "2026",
            "authoritative": tok["authoritative"], "sig": tok["sig"], "alg": tok["alg"]}


def _g(guard, **payload):
    return wg.handler({"guard": guard, **payload}, None)


# ── extracted ────────────────────────────────────────────────────────────────

def test_guard_extracted_pass_and_fail():
    ok = _g("extracted", fields={"entityid": "0603799999", "annual_income": 40000, "household_size": 4})
    assert ok["ok"] is True
    for missing in ({"annual_income": 40000, "household_size": 4},           # no entityid
                    {"entityid": "x", "household_size": 4},                  # no income
                    {}):
        assert _g("extracted", fields=missing)["ok"] is False


# ── authoritative (HUD provenance) ───────────────────────────────────────────

def test_guard_authoritative_verifies_genuine_signature():
    r = _g("authoritative", il_source=_signed_source(), household_size=4,
           il30=50000, il50=83300, il80=133250)
    assert r["ok"] is True


def test_guard_authoritative_fails_closed_on_tamper_or_absence():
    src = _signed_source(il50=83300)
    # tampered limit
    assert _g("authoritative", il_source=src, household_size=4,
              il30=50000, il50=70000, il80=133250)["ok"] is False
    # hand-typed label, no signature
    assert _g("authoritative", il_source="HUD USER (authoritative)", household_size=4,
              il30=50000, il50=83300, il80=133250)["ok"] is False
    assert _g("authoritative", household_size=4, il50=83300)["ok"] is False


# ── deidentified (sanitized_ref) ─────────────────────────────────────────────

def test_guard_deidentified_requires_verified_ref():
    assert _g("deidentified", sanitized_ref=json.loads(make_sanitized_ref()))["ok"] is True
    assert _g("deidentified", sanitized_ref={"deidentified": True})["ok"] is False
    assert _g("deidentified")["ok"] is False


# ── rules executed ───────────────────────────────────────────────────────────

def test_guard_rules_executed():
    assert _g("rules_executed", assessment={"assessed": True, "determination": "ELIGIBLE"})["ok"] is True
    assert _g("rules_executed", assessment={"assessed": True, "determination": "APPROVED?!"})["ok"] is False
    assert _g("rules_executed", assessment={"assessed": False})["ok"] is False
    assert _g("rules_executed")["ok"] is False


# ── unknown guard / errors fail closed ───────────────────────────────────────

def test_unknown_guard_fails_closed():
    assert _g("no_such_guard")["ok"] is False
    assert wg.handler("not-even-json{{", None)["ok"] is False


def test_guard_authoritative_handles_source_down_lookup_output():
    """Regression (found in the live P0-11 run): a source-down lookup returns found:false with NO
    limit keys; the guard must judge it fail-closed — never let a missing key become a state-machine
    runtime error. The controller passes the WHOLE lookup output under `lookup`."""
    r = _g("authoritative", lookup={"found": False, "error": "HUD_API_TOKEN not configured",
                                    "entityid": "0603799999"}, household_size=4)
    assert r["ok"] is False and "unavailable" in r["reason"]
    # happy path through the same wrapped shape
    src = _signed_source()
    r = _g("authoritative", lookup={"found": True, "il_source": src,
                                    "il30": 50000, "il50": 83300, "il80": 133250}, household_size=4)
    assert r["ok"] is True
