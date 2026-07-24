"""Review-2 — production secrets path. Signing secret + HUD token resolve from AWS Secrets
Manager by ARN (cached, fail-closed), never plaintext in templates; env remains the dev/test path."""
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "controls"))


def _fresh_provenance(monkeypatch, **env):
    for k in ("PROVENANCE_SECRET", "PROVENANCE_SECRET_ARN",
              "PROVENANCE_SECRET_DEID", "PROVENANCE_SECRET_ARN_DEID",
              "PROVENANCE_SECRET_HUD", "PROVENANCE_SECRET_ARN_HUD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import provenance
    importlib.reload(provenance)
    provenance._sm_cache.clear()
    return provenance


def test_env_secret_still_works_for_dev(monkeypatch):
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET="dev-secret")
    tok = p.sign("s", {"a": 1})
    assert tok["authoritative"] is True and p.verify("s", {"a": 1}, tok)


def test_secrets_manager_arn_resolution_cached(monkeypatch):
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET_ARN="arn:aws:secretsmanager:us-east-1:111122223333:secret:x")
    calls = []

    class _SM:
        def get_secret_value(self, SecretId):
            calls.append(SecretId)
            return {"SecretString": "sm-secret"}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _SM())
    tok = p.sign("s", {"a": 1})
    assert tok["authoritative"] is True
    assert p.verify("s", {"a": 1}, tok) is True
    assert len(calls) == 1, "secret must be cached, not re-fetched per call"


def test_unreadable_secret_fails_closed(monkeypatch):
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET_ARN="arn:aws:secretsmanager:us-east-1:111122223333:secret:x")

    class _SM:
        def get_secret_value(self, SecretId):
            raise RuntimeError("denied")

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _SM())
    tok = p.sign("s", {"a": 1})
    assert tok["authoritative"] is False and tok["sig"] is None   # nothing signs without the secret


# ── GA-2: separate signing keys per trust domain (deid vs HUD) ────────────────

def test_cross_domain_token_is_a_forgery(monkeypatch):
    """THE GA-2 PROPERTY: with distinct domain keys, a token minted in one trust domain does NOT
    verify in the other — the HUD lookup cannot forge 'this was masked' and the masker cannot forge
    'these limits came from HUD'."""
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET_DEID="deid-key-1",
                          PROVENANCE_SECRET_HUD="hud-key-1")
    hud_tok = p.sign("hud-source", {"il50": 83300}, domain="hud")
    deid_tok = p.sign("mask-source", {"sanitized_sha256": "abc"}, domain="deid")
    assert hud_tok["authoritative"] and deid_tok["authoritative"]
    # each verifies ONLY in its own domain
    assert p.verify("hud-source", {"il50": 83300}, hud_tok, domain="hud") is True
    assert p.verify("mask-source", {"sanitized_sha256": "abc"}, deid_tok, domain="deid") is True
    # cross-domain = forgery
    assert p.verify("hud-source", {"il50": 83300}, hud_tok, domain="deid") is False
    assert p.verify("mask-source", {"sanitized_sha256": "abc"}, deid_tok, domain="hud") is False


def test_domain_falls_back_to_shared_secret_for_dev(monkeypatch):
    """Compat: with only the legacy shared PROVENANCE_SECRET set (dev/tests/sandbox), both domains
    resolve to it — the 100+ existing offline tests keep meaning what they meant."""
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET="shared-dev")
    tok = p.sign("s", {"a": 1}, domain="hud")
    assert tok["authoritative"] is True
    assert p.verify("s", {"a": 1}, tok, domain="hud") is True
    assert p.verify("s", {"a": 1}, tok, domain="deid") is True   # same shared key in dev


def test_configured_domain_key_never_degrades_to_shared(monkeypatch):
    """If a domain key IS configured but unreadable, the domain fails closed — it must never silently
    fall back to the shared key (that would quietly reunify the trust domains)."""
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET="shared-dev",
                          PROVENANCE_SECRET_ARN_HUD="arn:aws:secretsmanager:us-east-1:111122223333:secret:hud-key")

    class _SMDenied:
        def get_secret_value(self, SecretId):
            raise RuntimeError("denied")

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _SMDenied())
    tok = p.sign("s", {"a": 1}, domain="hud")
    assert tok["authoritative"] is False and tok["sig"] is None
    # the deid domain (no domain key configured) still works off the shared dev secret
    assert p.sign("s", {"a": 1}, domain="deid")["authoritative"] is True


def test_sanitized_ref_rejected_when_minted_with_hud_key(monkeypatch):
    """End-to-end at the control layer: a sanitized_ref whose signature was minted with the HUD key is
    refused by the deid verifier — proof-of-masking cannot be forged from the lookup's key."""
    p = _fresh_provenance(monkeypatch, PROVENANCE_SECRET_DEID="deid-key-1",
                          PROVENANCE_SECRET_HUD="hud-key-1")
    import sanitized
    importlib.reload(sanitized)
    ref = sanitized.mint_ref("[REDACTED:NAME] applied for HCV", engine="comprehend")
    assert sanitized.verify_ref(ref) is True
    # forge the same field set with the HUD key (what a compromised lookup could do)
    fields = {k: ref[k] for k in ("artifact_id", "sanitized_sha256", "engine", "entities_masked", "tenant", "ts")}
    forged_tok = p.sign(sanitized.SOURCE, fields, domain="hud")
    forged = dict(ref)
    forged["sig"] = forged_tok["sig"]
    assert sanitized.verify_ref(forged) is False


def test_hud_token_resolves_from_arn_and_fails_closed(monkeypatch):
    sys.path.insert(0, str(ROOT / "agents" / "housing-assistance" / "tools"))
    monkeypatch.delenv("HUD_API_TOKEN", raising=False)
    monkeypatch.setenv("HUD_API_TOKEN_ARN", "arn:aws:secretsmanager:us-east-1:111122223333:secret:hud")

    class _SM:
        def get_secret_value(self, SecretId):
            return {"SecretString": "hud-live-token"}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _SM())
    import lookup_income_limit as lk
    importlib.reload(lk)
    assert lk.API_TOKEN == "hud-live-token"

    class _SMDenied:
        def get_secret_value(self, SecretId):
            raise RuntimeError("denied")

    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: _SMDenied())
    importlib.reload(lk)
    assert lk.API_TOKEN == ""   # unreadable == source unavailable (found:false path)
