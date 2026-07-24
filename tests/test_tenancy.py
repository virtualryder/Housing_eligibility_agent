"""Gate-B B5 — tenant isolation: tenant identity is DERIVED (deployment-pinned), never REQUESTED.

Proves: (1) request-body tenant values are ignored by mask_pii's minting path; (2) a validly-SIGNED
sanitized_ref from another tenant/deployment is refused fail-closed; (3) the pinned tenant is what
gets HMAC-signed into refs, so it cannot be altered post-mint."""
import importlib
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")

from toolkit import CONTROLS  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(CONTROLS))
import sanitized  # noqa: E402
import tenancy  # noqa: E402


def test_tenant_is_deployment_pinned_and_ignores_request_input(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "pha-la-county")
    # a hostile/confused caller supplies its own tenant in the event — it is ignored by design
    assert tenancy.resolve_tenant({"tenant": "some-other-pha"}) == "pha-la-county"
    monkeypatch.delenv("TENANT_ID")
    assert tenancy.resolve_tenant({"tenant": "attacker"}) == tenancy.DEFAULT_TENANT


def test_ref_minted_under_pinned_tenant_verifies_and_signs_the_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "pha-la-county")
    ref = sanitized.mint_ref("[REDACTED:NAME] applies", engine="comprehend")
    assert ref["tenant"] == "pha-la-county"
    assert sanitized.verify_ref(ref) is True
    # the tenant is inside the signed field set: altering it post-mint breaks the signature
    hijacked = dict(ref)
    hijacked["tenant"] = "some-other-pha"
    assert sanitized.verify_ref(hijacked) is False


def test_cross_tenant_ref_refused_even_with_valid_signature(monkeypatch):
    """An artifact minted by tenant A (validly signed — e.g. a mis-shared signing key) is refused by
    tenant B's deployment: signature proof alone is not enough, the tenant must also match."""
    monkeypatch.setenv("TENANT_ID", "pha-tenant-a")
    ref_a = sanitized.mint_ref("[REDACTED:NAME] case", engine="comprehend")
    assert sanitized.verify_ref(ref_a) is True
    monkeypatch.setenv("TENANT_ID", "pha-tenant-b")   # same key, different deployment tenant
    assert sanitized.verify_ref(ref_a) is False        # fail-closed cross-tenant rejection


def test_default_tenant_backward_compatible(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    ref = sanitized.mint_ref("[REDACTED:NAME]", engine="comprehend")
    assert ref["tenant"] == "default" and sanitized.verify_ref(ref) is True


def test_mask_pii_stamps_pinned_tenant_not_body_tenant(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "pha-la-county")
    import mask_pii
    importlib.reload(mask_pii)

    class _CM:
        def detect_pii_entities(self, Text, LanguageCode):
            return {"Entities": [{"BeginOffset": 0, "EndOffset": 5, "Type": "NAME"}]}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _CM())
    out = mask_pii.handler({"case": "Alice applies for HCV", "tenant": "attacker-chosen"}, None)
    assert out["deidentified"] is True
    assert out["sanitized_ref"]["tenant"] == "pha-la-county"   # body tenant ignored
    assert sanitized.verify_ref(out["sanitized_ref"]) is True
