import json
import os
import urllib.request
import urllib.parse
import urllib.error

import provenance  # shared signer (bundled beside this handler at deploy; on sys.path in tests)

# lookup_income_limit — fetch the AUTHORITATIVE HUD income limits (30% / 50% / 80% of Area Median
# Income) for a household's county from the HUD USER Income Limits API
# (https://www.huduser.gov/hudapi/public/il/data/{entityid}). The county identifier (entityid = county
# FIPS code) is a NON-PII decision field, so this runs before mask_pii. It supplies the authoritative
# limits used by assess_housing_eligibility and returns SIGNED PROVENANCE so the determination and the
# WORM audit are traceable to the source (parallel to lookup_coa/College Scorecard in the EDU agent).
#
# P0-3: this is the ONLY component that actually calls HUD, so it is the only one that can vouch for the
# limits. It SIGNS the exact figures it fetched (entityid, year, household size, il30/il50/il80) with the
# per-deploy PROVENANCE_SECRET and returns that token as `il_source`. assess_housing_eligibility verifies
# the signature before treating the limits as authoritative. A caller cannot forge a HUD-labeled source
# string anymore — only a real lookup produces a token that verifies.
#
# entityid: HUD county entityid is a 10-char code 'SSCCC99999' (state FIPS + county FIPS + 99999),
# e.g. Los Angeles County CA = 0603799999. Response shape: data.median_income / data.county_name /
# data.year at the top level, with the per-family-size limits NESTED under three sub-objects:
#   data.extremely_low.il30_p1..p8 (30% AMI), data.very_low.il50_p1..p8 (50% AMI),
#   data.low.il80_p1..p8 (80% AMI).
#
# Auth: HUD requires a free Bearer token (register at huduser.gov). Env HUD_API_TOKEN, injected
# post-deploy via Lambda env / Secrets Manager — kept OUT of the repo. The call is a GOVERNED Gateway
# tool — Cedar-authorized and auditable like every other tool; reaching real federal data is not an
# ungoverned side-channel. Fail-soft: found=false (never throws), so the workflow degrades gracefully
# when the token is absent or the county is unknown — and because a source-down lookup returns NO signed
# token, the downstream determination correctly becomes NEEDS_REVIEW instead of a fabricated answer.

API_BASE = "https://www.huduser.gov/hudapi/public/il/data"
def _resolve_token():
    """HUD bearer token: env (dev) or AWS Secrets Manager via HUD_API_TOKEN_ARN (production path,
    Review-2 — never a plaintext Lambda env value). Fail-closed: no token -> found:false -> review."""
    v = os.environ.get("HUD_API_TOKEN", "")
    if v:
        return v
    arn = os.environ.get("HUD_API_TOKEN_ARN", "")
    if arn:
        try:
            import boto3
            return (boto3.client("secretsmanager").get_secret_value(SecretId=arn).get("SecretString") or "")
        except Exception:
            return ""   # unreadable secret == source unavailable (never a fabricated lookup)
    return ""


API_TOKEN = _resolve_token()
SOURCE = "US Dept of Housing and Urban Development (HUD USER) — Income Limits"


def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except Exception:
            e = {"entityid": e}
    return e


def _clamp_hh(v):
    try:
        n = int(v)
    except Exception:
        n = 1
    return min(8, max(1, n))


def _query(entityid, year):
    url = "%s/%s" % (API_BASE, urllib.parse.quote(str(entityid)))
    if year:
        url += "?" + urllib.parse.urlencode({"year": str(year)})
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + API_TOKEN,
        "User-Agent": "governed-housing-agent/1.0",
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def handler(event, context):
    e = _coerce(event)
    entityid = (str(e.get("entityid") or e.get("county_fips") or "")).strip()
    hh = _clamp_hh(e.get("household_size", 1))
    year = e.get("year")

    if not entityid:
        return {"found": False, "error": "provide a county entityid (FIPS code)"}
    if not API_TOKEN:
        return {"found": False, "error": "HUD_API_TOKEN not configured (register at huduser.gov; inject via env/Secrets)",
                "source": SOURCE, "entityid": entityid}

    try:
        raw = _query(entityid, year)
    except urllib.error.HTTPError as ex:
        return {"found": False, "error": "HUD Income Limits HTTP %s: %s" % (ex.code, ex.reason),
                "source": SOURCE, "entityid": entityid}
    except (urllib.error.URLError, TimeoutError, ValueError) as ex:
        return {"found": False, "error": "HUD Income Limits call failed: %s" % type(ex).__name__,
                "source": SOURCE, "entityid": entityid}

    data = (raw or {}).get("data") or raw or {}

    def _lim(bucket, prefix):
        # limits are nested: data.extremely_low.il30_pN / data.very_low.il50_pN / data.low.il80_pN.
        # Fall back to a flat data.<prefix>_pN in case the API ever returns them un-nested.
        sub = data.get(bucket) or {}
        v = sub.get("%s_p%d" % (prefix, hh))
        if v is None:
            v = data.get("%s_p%d" % (prefix, hh))
        try:
            return int(v)
        except Exception:
            return None

    il30 = _lim("extremely_low", "il30")
    il50 = _lim("very_low", "il50")
    il80 = _lim("low", "il80")
    if il50 is None:
        return {"found": False, "error": "no income-limit data for entityid '%s' (household size %d)" % (entityid, hh),
                "source": SOURCE, "entityid": entityid}

    county_name = data.get("county_name") or data.get("area_name") or ""
    median = data.get("median_income")
    try:
        median = int(median)
    except Exception:
        median = None

    # ---- SIGN the fetched figures. The signed field set is EXACTLY what assess re-derives and verifies:
    # entityid, year, household size, and the three limits. (P0-3 authoritative provenance.) ----
    year_str = str((data.get("year") or year) or "")
    sig_fields = {"entityid": entityid, "year": year_str, "household_size": hh,
                  "il30": il30, "il50": il50, "il80": il80}
    tok = provenance.sign(SOURCE, sig_fields, domain="hud")   # GA-2: HUD trust domain key
    il_source_obj = {
        "source": SOURCE,
        "api": "huduser.gov/hudapi/public/il/data",
        "entityid": entityid,
        "county_name": county_name,
        "household_size": hh,
        "year": year_str,
        "authoritative": tok.get("authoritative", False),
        "sig": tok.get("sig"),
        "alg": tok.get("alg"),
    }
    # il_source travels as a JSON STRING (assess declares it string-typed at the gateway); assess parses
    # it and verifies the signature. This is a machine provenance token, not a human label.
    il_source = json.dumps(il_source_obj, separators=(",", ":"), ensure_ascii=False)

    # Short proof fields FIRST (MCP client truncates ~220 chars); provenance token LAST.
    return {
        "found": True,
        "household_size": hh,
        "il30": il30,          # extremely-low income limit (30% AMI)
        "il50": il50,          # very-low income limit (50% AMI) — HCV eligibility ceiling
        "il80": il80,          # low income limit (80% AMI)
        "county_name": county_name,
        "median_income": median,
        "authoritative": tok.get("authoritative", False),
        "il_source": il_source,
        "note": "authoritative HUD income limits; pass il30/il50/il80 AND il_source (signed) to assess_housing_eligibility",
    }
