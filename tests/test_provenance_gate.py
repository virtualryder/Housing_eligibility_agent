"""P0-3 — authoritative-source provenance gate. Proves that the determination tool trusts income limits
ONLY when they carry a signature minted by the lookup tool (which alone reached HUD and holds the shared
secret), and returns NEEDS_REVIEW (never a fabricated authoritative answer) otherwise. Pure logic, no AWS:
the HUD API call in lookup_income_limit is monkeypatched with a fixture response."""
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "lib" / "controls"
TOOLS = ROOT / "agents" / "housing-assistance" / "tools"
for _p in (str(CONTROLS), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SECRET = os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")  # aligns with conftest

import provenance  # noqa: E402

SOURCE = "US Dept of Housing and Urban Development (HUD USER) — Income Limits"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _assess():
    return _load("assess_under_test", TOOLS / "assess_housing_eligibility.py")


def _lookup():
    return _load("lookup_under_test", TOOLS / "lookup_income_limit.py")


# ---------- provenance primitive ----------

def test_sign_then_verify_roundtrips():
    fields = {"entityid": "0603799999", "year": "2026", "household_size": 4, "il30": 30000, "il50": 50000, "il80": 80000}
    tok = provenance.sign(SOURCE, fields)
    assert tok["authoritative"] is True and tok["sig"]
    assert provenance.verify(SOURCE, fields, tok) is True


def test_verify_rejects_tampered_value():
    fields = {"entityid": "0603799999", "year": "2026", "household_size": 4, "il30": 30000, "il50": 50000, "il80": 80000}
    tok = provenance.sign(SOURCE, fields)
    tampered = dict(fields, il50=40000)  # attacker lowers the ceiling to force eligibility
    assert provenance.verify(SOURCE, tampered, tok) is False


def test_verify_rejects_wrong_secret(monkeypatch):
    fields = {"entityid": "x", "year": "2026", "household_size": 1, "il30": 1, "il50": 2, "il80": 3}
    tok = provenance.sign(SOURCE, fields)
    monkeypatch.setenv("PROVENANCE_SECRET", "a-different-secret")
    assert provenance.verify(SOURCE, fields, tok) is False


def test_verify_rejects_missing_secret(monkeypatch):
    fields = {"entityid": "x", "year": "2026", "household_size": 1, "il30": 1, "il50": 2, "il80": 3}
    tok = provenance.sign(SOURCE, fields)
    monkeypatch.delenv("PROVENANCE_SECRET", raising=False)
    assert provenance.verify(SOURCE, fields, tok) is False
    monkeypatch.setenv("PROVENANCE_SECRET", SECRET)


def test_verify_rejects_unsigned_and_forged_tokens():
    fields = {"entityid": "x", "year": "2026", "household_size": 1, "il30": 1, "il50": 2, "il80": 3}
    assert provenance.verify(SOURCE, fields, {"source": SOURCE, "authoritative": True}) is False   # no sig
    assert provenance.verify(SOURCE, fields, {"source": SOURCE, "authoritative": True, "sig": "deadbeef"}) is False
    assert provenance.verify(SOURCE, fields, "US Dept of Housing and Urban Development") is False   # a plain label
    assert provenance.verify(SOURCE, fields, None) is False


def test_sign_without_secret_is_not_authoritative(monkeypatch):
    monkeypatch.delenv("PROVENANCE_SECRET", raising=False)
    tok = provenance.sign(SOURCE, {"il50": 50000})
    assert tok["authoritative"] is False and tok["sig"] is None
    monkeypatch.setenv("PROVENANCE_SECRET", SECRET)


# ---------- assess gate ----------

def _signed_il_source(entityid="0603799999", year="2026", hh=4, il30=30000, il50=50000, il80=80000):
    fields = {"entityid": entityid, "year": str(year), "household_size": hh, "il30": il30, "il50": il50, "il80": il80}
    tok = provenance.sign(SOURCE, fields)
    return json.dumps({"source": SOURCE, "entityid": entityid, "county_name": "Test County",
                       "household_size": hh, "year": str(year),
                       "authoritative": tok["authoritative"], "sig": tok["sig"], "alg": tok["alg"]})


def test_assess_needs_review_without_provenance():
    m = _assess()
    r = m.handler({"annual_income": 40000, "household_size": 4, "il30": 30000, "il50": 50000, "il80": 80000,
                   "deidentified": True}, None)
    assert r["determination"] == "NEEDS_REVIEW"
    assert r["authoritative"] is False and r["eligible"] is None


def test_assess_needs_review_with_fabricated_source_string():
    m = _assess()
    r = m.handler({"annual_income": 40000, "household_size": 4, "il30": 30000, "il50": 50000, "il80": 80000,
                   "il_source": "US Dept of Housing and Urban Development (HUD USER) — Income Limits",
                   "deidentified": True}, None)
    assert r["determination"] == "NEEDS_REVIEW"
    assert r["authoritative"] is False


def test_assess_needs_review_when_limits_tampered_after_signing():
    m = _assess()
    # genuine token for il50=50000, but the caller passes a LOWER il50 to force eligibility
    src = _signed_il_source(il50=50000)
    r = m.handler({"annual_income": 45000, "household_size": 4, "il30": 30000, "il50": 40000, "il80": 80000,
                   "il_source": src, "deidentified": True}, None)
    assert r["determination"] == "NEEDS_REVIEW"
    assert r["authoritative"] is False


def test_assess_authoritative_with_signed_source():
    m = _assess()
    src = _signed_il_source(il30=30000, il50=50000, il80=80000)
    r = m.handler({"annual_income": 45000, "household_size": 4, "il30": 30000, "il50": 50000, "il80": 80000,
                   "il_source": src, "deidentified": True}, None)
    assert r["determination"] == "ELIGIBLE"
    assert r["authoritative"] is True and r["provenance_verified"] is True
    assert r["income_category"] == "VERY_LOW"


def test_assess_still_fail_closed_on_unmasked():
    m = _assess()
    r = m.handler({"annual_income": 40000, "il50": 50000, "il_source": _signed_il_source(), "deidentified": False}, None)
    assert r["assessed"] is False


# ---------- lookup -> assess integration (a real lookup token verifies downstream) ----------

def test_lookup_signs_and_assess_verifies(monkeypatch):
    lk = _lookup()
    monkeypatch.setattr(lk, "API_TOKEN", "fake-hud-token")
    fixture = {"data": {"county_name": "Los Angeles County", "year": 2026, "median_income": 98200,
                        "extremely_low": {"il30_p4": 44150}, "very_low": {"il50_p4": 73550},
                        "low": {"il80_p4": 105050}}}
    monkeypatch.setattr(lk, "_query", lambda entityid, year: fixture)
    out = lk.handler({"entityid": "0603799999", "household_size": 4}, None)
    assert out["found"] is True and out["authoritative"] is True
    assert isinstance(out["il_source"], str)

    m = _assess()
    r = m.handler({"annual_income": 60000, "household_size": 4,
                   "il30": out["il30"], "il50": out["il50"], "il80": out["il80"],
                   "il_source": out["il_source"], "deidentified": True}, None)
    assert r["provenance_verified"] is True and r["authoritative"] is True
    assert r["determination"] == "ELIGIBLE"      # 60000 <= il50 73550


def test_lookup_source_down_yields_no_token_then_review(monkeypatch):
    lk = _lookup()
    monkeypatch.setattr(lk, "API_TOKEN", "")   # HUD token absent -> source unavailable
    out = lk.handler({"entityid": "0603799999", "household_size": 4}, None)
    assert out["found"] is False
    # with no lookup output, the agent has no signed il_source; assess must route to review
    m = _assess()
    r = m.handler({"annual_income": 60000, "household_size": 4, "il50": 73550, "deidentified": True}, None)
    assert r["determination"] == "NEEDS_REVIEW" and r["authoritative"] is False
