"""Review-3 R3-2 — ZERO-PII pass-by-reference orchestration.

The finding this closes: the PII canary measured 87 marker hits in Step Functions execution history
because the raw application traveled as state input. Now raw content is written ONCE to the
encrypted, TTL'd, tenant-scoped case store and only opaque refs cross the controller."""
import importlib
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")

from toolkit import CONTROLS  # noqa: E402
import sys  # noqa: E402
import pathlib  # noqa: E402
sys.path.insert(0, str(CONTROLS))
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "housing-assistance" / "tools"))

import case_store  # noqa: E402
import ingest_case  # noqa: E402

RAW = "Applicant Maria Gonzalez (SSN 523-11-9876) at 1420 W 12th St applies for HCV. Household of 4, annual income $40,000, entityid 0603799999."


def _fresh():
    case_store.MemoryCaseStore.items.clear()


def test_ingest_returns_ref_never_content(monkeypatch):
    _fresh()
    out = ingest_case.handler({"application": RAW, "case_id": "HOU-1"}, None)
    assert out["ingested"] is True and out["case_ref"].startswith("case-")
    assert RAW not in str(out) and "Gonzalez" not in str(out)   # the response is content-free
    assert case_store.get_case(out["case_ref"]) == RAW
    assert ingest_case.handler({"application": "  "}, None)["ingested"] is False


def test_case_store_tenant_scoped(monkeypatch):
    _fresh()
    monkeypatch.setenv("TENANT_ID", "pha-a")
    ref = case_store.put_case(RAW)
    assert case_store.get_case(ref) == RAW
    monkeypatch.setenv("TENANT_ID", "pha-b")
    assert case_store.get_case(ref) is None      # cross-tenant fetch refused (B5)
    monkeypatch.delenv("TENANT_ID")
    assert case_store.get_case("case-nope") is None
    assert case_store.get_case(None) is None


def test_intake_extracts_from_ref_and_fails_closed_on_bad_ref():
    _fresh()
    import intake_application as intake
    ref = case_store.put_case(RAW)
    out = intake.handler({"case_ref": ref}, None)
    assert out["structured"] is True
    assert out["fields"]["household_size"] == 4 and out["fields"]["entityid"] == "0603799999"
    bad = intake.handler({"case_ref": "case-unknown"}, None)
    assert bad.get("structured") is False and "fail-closed" in bad["error"]


def test_mask_by_ref_returns_no_content(monkeypatch):
    _fresh()
    import mask_pii
    importlib.reload(mask_pii)

    class _CM:
        def detect_pii_entities(self, Text, LanguageCode):
            return {"Entities": [{"BeginOffset": 10, "EndOffset": 24, "Type": "NAME"}]}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _CM())
    ref = case_store.put_case(RAW)
    out = mask_pii.handler({"case_ref": ref}, None)
    assert out["deidentified"] is True and "sanitized_ref" in out
    assert "masked_case" not in out                      # R3-2: no content into state output
    assert "Gonzalez" not in str(out) and "523-11" not in str(out)
    # unknown ref fails closed
    bad = mask_pii.handler({"case_ref": "case-unknown"}, None)
    assert bad["deidentified"] is False and "fail-closed" in bad["error"]
    # inline mode (dev/direct) still returns the masked text
    inline = mask_pii.handler({"case": RAW}, None)
    assert "masked_case" in inline


def test_drafter_stores_notice_by_ref_when_case_store_configured(monkeypatch):
    _fresh()
    import sanitized
    import housing_core
    importlib.reload(housing_core)
    masked = "[REDACTED:NAME] applies for HCV. Household of 4, income $40,000."
    sref = sanitized.mint_ref(masked, engine="comprehend", store=sanitized.MemoryStore())
    # store carries the text via candidate binding instead (no store configured for sanitized)
    class _BR:
        def converse(self, **kw):
            return {"output": {"message": {"content": [{"text": "Dear applicant, determination drafted."}]}},
                    "stopReason": "end_turn"}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _BR())
    monkeypatch.setenv("CASE_TABLE", "unit-inmemory")   # flips notice->ref path; table calls fall back? no:
    # CASE_TABLE set means case_store would call boto3 Table — monkeypatch _table to memory
    monkeypatch.setattr(case_store, "_table", lambda: None)
    out = housing_core.handler({"deidentified": True, "sanitized_ref": sref, "case": masked}, None)
    assert out.get("notice_ref", "").startswith("case-")
    assert "notice" not in out                           # content stored, not echoed
    assert case_store.get_case(out["notice_ref"]).startswith("Dear applicant")
    monkeypatch.delenv("CASE_TABLE")
    out2 = housing_core.handler({"deidentified": True, "sanitized_ref": sref, "case": masked}, None)
    assert "notice" in out2                              # dev/inline mode unchanged
