"""P0-1 — server-issued sanitized-artifact references. Proves the de-identification gate now rests on a
mask_pii-SIGNED reference (proof-of-masking) with a CONTENT-BINDING hash — and that the previously
spoofable `deidentified: true` boolean is no longer accepted as proof by any tool. Pure logic, no AWS
(Comprehend in mask_pii is monkeypatched; the artifact store is in-memory)."""
import json
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")  # before tool import

import pytest  # noqa: E402
from toolkit import call, load, CONTROLS  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(CONTROLS))
import sanitized  # noqa: E402

MASKED = "[REDACTED:NAME] household of 4, annual income 40000, county entityid 0603799999"


def _ref(text=MASKED, store=None):
    return sanitized.mint_ref(text, engine="comprehend:DetectPiiEntities",
                              entities_masked=3, store=store)


# ── the primitive ─────────────────────────────────────────────────────────────

def test_mint_then_verify_roundtrips():
    ref = _ref()
    assert ref["authoritative"] is True and ref["sig"]
    assert sanitized.verify_ref(ref) is True
    assert sanitized.verify_ref(json.dumps(ref)) is True   # JSON form (as it crosses the gateway)


def test_verify_rejects_forged_and_tampered_refs():
    ref = _ref()
    forged = dict(ref, sig="deadbeef" * 8)
    assert sanitized.verify_ref(forged) is False
    tampered = dict(ref, sanitized_sha256=sanitized.sha256_text("different content"))
    assert sanitized.verify_ref(tampered) is False          # digest swap breaks the signature
    assert sanitized.verify_ref({"deidentified": True}) is False
    assert sanitized.verify_ref(True) is False
    assert sanitized.verify_ref(None) is False


def test_mint_without_secret_is_not_authoritative(monkeypatch):
    monkeypatch.delenv("PROVENANCE_SECRET", raising=False)
    ref = _ref()
    assert ref["authoritative"] is False
    assert sanitized.verify_ref(ref) is False               # fail-closed both ends


def test_store_roundtrip_and_content_binding():
    st = sanitized.MemoryStore()
    ref = _ref(store=st)
    assert ref["stored"] is True
    assert sanitized.load_text(ref, store=st) == MASKED                       # server-side channel
    assert sanitized.load_text(ref, candidate_text=MASKED, store=None) == MASKED  # hash-bound candidate
    assert sanitized.load_text(ref, candidate_text="UNMASKED SSN 123-45-6789", store=None) is None


# ── the tools refuse the spoofed boolean (the ChatGPT P0 attack) ─────────────

@pytest.mark.parametrize("tool,extra,flag", [
    ("assess_housing_eligibility", {"annual_income": 40000, "household_size": 4,
                                    "il30": 50000, "il50": 83300, "il80": 133250}, "assessed"),
    ("recertify", {"annual_income": 40000, "il50": 83300, "il80": 133250, "prior_eligible": True}, "recertified"),
    ("overpayment", {"prior_monthly_subsidy": 900, "corrected_monthly_subsidy": 600, "months": 6}, "computed"),
])
def test_spoofed_deidentified_boolean_is_refused(tool, extra, flag):
    # The exact attack from the review: unmasked data + a hand-typed deidentified:true. Must refuse.
    r = call(tool, {**extra, "case": "unmasked SSN 123-45-6789", "deidentified": True})
    assert r[flag] is False
    assert r.get("sanitized_ref_verified") is False


def test_forged_ref_is_refused():
    ref = dict(_ref(), sig="deadbeef" * 8)
    r = call("assess_housing_eligibility",
             {"annual_income": 40000, "household_size": 4, "il50": 83300,
              "deidentified": True, "sanitized_ref": json.dumps(ref)})
    assert r["assessed"] is False


def test_valid_ref_is_accepted():
    r = call("assess_housing_eligibility",
             {"annual_income": 40000, "household_size": 4, "il50": 83300,
              "deidentified": True, "sanitized_ref": json.dumps(_ref())})
    assert r["assessed"] is True            # proceeds (then P0-3 provenance governs authority)


# ── draft_notice: content binding end-to-end ─────────────────────────────────

def test_draft_refuses_substituted_content(monkeypatch):
    core = load("housing_core")
    ref = _ref(MASKED)
    # model tries to hand DIFFERENT (e.g. unmasked) content under a genuine ref -> hash mismatch
    r = core.handler({"case": "raw SSN 123-45-6789 name Jane Doe",
                      "deidentified": True, "sanitized_ref": json.dumps(ref)}, None)
    assert r.get("drafted_by") is None
    assert r.get("content_bound") is False


def test_draft_accepts_exact_masked_content(monkeypatch):
    core = load("housing_core")

    class _FakeBedrock:
        def converse(self, **kw):
            return {"output": {"message": {"content": [{"text": "DRAFT NOTICE"}]}}, "stopReason": "end_turn"}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _FakeBedrock())
    r = core.handler({"case": MASKED, "determination": json.dumps({"determination": "ELIGIBLE"}),
                      "deidentified": True, "sanitized_ref": json.dumps(_ref(MASKED))}, None)
    assert r.get("notice") == "DRAFT NOTICE"


# ── mask_pii mints the ref ───────────────────────────────────────────────────

def test_mask_pii_returns_signed_ref(monkeypatch):
    mp = load("mask_pii")

    class _FakeComprehend:
        def detect_pii_entities(self, Text, LanguageCode):
            return {"Entities": [{"BeginOffset": 0, "EndOffset": 8, "Type": "NAME"}]}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _FakeComprehend())
    out = mp.handler({"case": "Jane Doe household of 4, income 40000"}, None)
    assert out["deidentified"] is True
    ref = out["sanitized_ref"]
    assert sanitized.verify_ref(ref) is True
    assert ref["sanitized_sha256"] == sanitized.sha256_text(out["masked_case"])  # bound to the exact output
