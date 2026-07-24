import hashlib
import hmac
import json
import os

# provenance.py — the SHARED authoritative-source provenance signer/verifier (P0-3).
#
# THE DEFECT THIS FIXES: a determination tool (assess_housing_eligibility, and the analogous
# EDU / benefits / PV assessors) used to trust income limits + an `il_source` label that arrived in
# the tool CALL BODY. Any caller could hand it fabricated numbers plus a string that says
# "US Dept of Housing and Urban Development — authoritative" and the determination would be issued —
# and written to the WORM audit — as if it came from the real federal source. Provenance you can type
# is not provenance.
#
# THE FIX: the ONLY component that actually reached the authoritative source (lookup_income_limit,
# which alone made the HUD USER API call) SIGNS the exact values it fetched with a per-deploy secret
# (env PROVENANCE_SECRET, injected into the lookup + assess Lambdas at deploy time, never in the repo).
# The downstream assessor VERIFIES that signature against the values it was handed before it will treat
# them as authoritative. A caller without the secret cannot forge the signature, and cannot alter a
# single limit number without breaking it. No valid signature -> the values are UNVERIFIED -> the
# determination is NEEDS_REVIEW with authoritative:false. Fail-closed: secret absent, token missing,
# or any mismatch all resolve to "not authoritative", never to a fabricated authoritative determination.
#
# HMAC (symmetric) is deliberate: signer and verifier are two Lambdas in the SAME deployment/account
# that already share a trust boundary; a per-deploy shared secret is the least machinery that binds the
# values to the genuine lookup. (The connector system-of-record, a cross-trust-boundary case, uses
# asymmetric RS256/JWKS instead — see lib/connector/sor_api.py.)

_SECRET_ENV = "PROVENANCE_SECRET"
_SECRET_ARN_ENV = "PROVENANCE_SECRET_ARN"   # production path: AWS Secrets Manager (Review-2)
_ALG = "HMAC-SHA256"
_sm_cache = {}

# GA-2 — SEPARATE SIGNING KEYS PER TRUST DOMAIN. The de-identification proof (sanitized_ref, minted
# by mask_pii) and the authoritative-source proof (HUD limits, minted by lookup_income_limit) are
# DIFFERENT trust statements made by DIFFERENT components. Under a single shared key, any holder of
# that key can mint EITHER proof — a compromised lookup could forge "this was masked" and a
# compromised masker could forge "these limits came from HUD". Domain-scoped keys make each proof
# forgeable only by its own minter. Verifiers resolve the key for THEIR domain, so a cross-domain
# token simply fails verification (fail-closed), it is never "close enough".
_DOMAINS = {
    "deid": ("PROVENANCE_SECRET_DEID", "PROVENANCE_SECRET_ARN_DEID"),
    "hud": ("PROVENANCE_SECRET_HUD", "PROVENANCE_SECRET_ARN_HUD"),
}


def _sm(arn):
    """Secrets Manager fetch, cached for the Lambda lifetime; unreadable -> b'' (fail-closed)."""
    if arn not in _sm_cache:
        try:
            import boto3
            r = boto3.client("secretsmanager").get_secret_value(SecretId=arn)
            _sm_cache[arn] = (r.get("SecretString") or "").encode("utf-8")
        except Exception:
            return b""   # fail-closed: unreadable secret -> nothing is authoritative (NOT cached; retried next call)
    return _sm_cache[arn]


def _secret(domain=None):
    """Resolve the signing secret for a trust domain (GA-2). Resolution order:
      1. domain-scoped env / Secrets Manager ARN (PROVENANCE_SECRET[_ARN]_{DEID|HUD}) — production;
         if EITHER is configured for the domain, ONLY the domain-scoped material is used: a
         misconfigured/unreadable domain key fails closed and never silently degrades to a shared key.
      2. legacy shared PROVENANCE_SECRET / PROVENANCE_SECRET_ARN — dev/tests/sandbox compatibility.
    Reads are CloudTrail-visible; rotation = new version picked up on cold start. No secret -> b''
    -> nothing signs or verifies as authoritative (fail-closed)."""
    if domain in _DOMAINS:
        env_k, arn_k = _DOMAINS[domain]
        v = os.environ.get(env_k) or ""
        arn = os.environ.get(arn_k) or ""
        if v:
            return v.encode("utf-8")
        if arn:
            return _sm(arn)
    v = os.environ.get(_SECRET_ENV) or ""
    if v:
        return v.encode("utf-8")
    arn = os.environ.get(_SECRET_ARN_ENV) or ""
    if arn:
        return _sm(arn)
    return b""


def _norm(o):
    # Numbers cross the gateway as JSON and come back as int OR float (the assessor coerces limits with
    # float()). Normalize integral floats/Decimals to int so a value SIGNED as 50000 still VERIFIES when
    # it arrives as 50000.0 — otherwise a faithfully-passed limit would read as tampered.
    from decimal import Decimal
    if isinstance(o, bool):
        return o
    if isinstance(o, Decimal):
        i = int(o)
        return i if o == i else float(o)
    if isinstance(o, float):
        return int(o) if o.is_integer() else o
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_norm(v) for v in o]
    return o


def _canon(source, fields):
    return json.dumps({"source": source, "fields": _norm(fields)},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sign(source, fields, domain=None):
    """Mint a provenance token for `fields` (the authoritative values fetched from `source`), with the
    key of the caller's trust `domain` (GA-2: 'hud' for the authoritative-source lookup, 'deid' for the
    sanitized-artifact minter; None = legacy shared key). authoritative is True ONLY when a secret is
    configured AND a signature was produced — so a signer running without its key self-reports
    non-authoritative rather than pretending."""
    s = _secret(domain)
    if not s:
        return {"source": source, "authoritative": False, "sig": None, "alg": _ALG,
                "reason": "signing secret not configured for this trust domain; source values cannot be signed as authoritative"}
    sig = hmac.new(s, _canon(source, fields).encode("utf-8"), hashlib.sha256).hexdigest()
    return {"source": source, "authoritative": True, "sig": sig, "alg": _ALG}


def verify(source, fields, token, domain=None):
    """True ONLY if `token` carries a signature that matches HMAC over (token source, `fields`) with the
    key of the VERIFIER'S trust `domain` (GA-2) — so a token minted in another domain (or with no key)
    fails, exactly like a forgery. Missing secret, missing/short token, authoritative!=True, or ANY
    value mismatch -> False (fail-closed). `fields` MUST be rebuilt by the verifier from the values IT
    will actually use, so tampering with any limit after the lookup breaks verification."""
    s = _secret(domain)
    if not s or not isinstance(token, dict):
        return False
    sig = token.get("sig")
    if not sig or token.get("authoritative") is not True:
        return False
    tok_source = token.get("source", source)
    expected = hmac.new(s, _canon(tok_source, fields).encode("utf-8"), hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(str(sig), expected)
    except Exception:
        return False
