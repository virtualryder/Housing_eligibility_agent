"""Review-2 — production secrets path. Signing secret + HUD token resolve from AWS Secrets
Manager by ARN (cached, fail-closed), never plaintext in templates; env remains the dev/test path."""
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "controls"))


def _fresh_provenance(monkeypatch, **env):
    for k in ("PROVENANCE_SECRET", "PROVENANCE_SECRET_ARN"):
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
