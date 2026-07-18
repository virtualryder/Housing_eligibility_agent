import json

import provenance  # shared verifier (bundled beside this handler at deploy; on sys.path in tests)

# assess_housing_eligibility — deterministic Housing Choice Voucher (Section 8) income-eligibility
# determination. NO licensed data and NO model call: a rules engine over the PUBLIC HUD income-limit
# framework. Runs AFTER mask_pii (fail-closed: refuses un-masked input, mirroring the mask-before-model
# control). The income limits themselves are the AUTHORITATIVE per-county HUD figures supplied by
# lookup_income_limit (HUD USER Income Limits API); this tool classifies the household against them.
#
# P0-3 — NEVER fabricate authority. The limits AND their provenance arrive in the call body, so this tool
# cannot take a caller's word that they are HUD's. It requires a SIGNED provenance token minted by
# lookup_income_limit (which alone reached HUD and holds the per-deploy secret) and VERIFIES that
# signature against the exact figures it is about to use. If the token is missing, unsigned, forged, or
# does not match the figures, the limits are UNVERIFIED: the determination is NEEDS_REVIEW with
# authoritative:false and NO eligibility call is made on unverified numbers. A hand-typed "HUD" source
# string no longer buys authority.
#
# Income categories (24 CFR 5.603 / HUD): extremely low = <= 30% AMI (il30), very low = <= 50% AMI
# (il50), low = <= 80% AMI (il80). HCV/public-housing admission generally requires VERY-LOW income
# (<= il50). By statute (42 USC 1437n) at least 75% of new HCV admissions must go to EXTREMELY-LOW-income
# families — the extremely-low-income targeting requirement — so <= il30 is flagged as targeting priority.
# Households between 50% and 80% AMI (low income) are eligible only for specific categories and are
# routed to NEEDS_REVIEW; above 80% AMI is over-income.

SOURCE_NOTE = "HUD income categories per 24 CFR 5.603; extremely-low-income targeting per 42 USC 1437n (75% of HCV admissions)"


def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except Exception:
            e = {"_raw": e}
    return e


def _num(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _parse_il_source(raw):
    # il_source is declared string-typed at the gateway and travels as a JSON token; also accept a dict
    # (direct/unit-test calls). Anything that is not a JSON object is not a token.
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else None
        except Exception:
            return None
    return None


def handler(event, context):
    e = _coerce(event)
    # Fail-closed: refuse to operate on non-de-identified input. Cedar's mask_before_assess forbid blocks
    # this at the gateway; the body refuses too (defense in depth).
    if e.get("deidentified") is not True:
        return {"assessed": False, "error": "refused: case is not de-identified (deidentified must be true)",
                "deidentified_input": e.get("deidentified")}

    income = _num(e.get("annual_income"))
    hh = e.get("household_size")
    try:
        hh = int(hh)
    except Exception:
        hh = None
    il30 = _num(e.get("il30"))
    il50 = _num(e.get("il50"))
    il80 = _num(e.get("il80"))
    il_source = _parse_il_source(e.get("il_source"))  # signed provenance token from lookup_income_limit

    # ---- P0-3: verify provenance. Rebuild the signed field set from the figures WE will use (not from
    # the token), so tampering with any limit after the lookup breaks verification. ----
    prov_verified = False
    if il_source is not None and hh is not None and il50 is not None:
        fields = {
            "entityid": str(il_source.get("entityid") or ""),
            "year": str(il_source.get("year") or ""),
            "household_size": hh,
            "il30": il30, "il50": il50, "il80": il80,
        }
        prov_verified = provenance.verify(il_source.get("source", ""), fields, il_source)

    prov_source = il_source.get("source") if isinstance(il_source, dict) else None

    if income is None or il50 is None:
        return {"assessed": True, "determination": "NEEDS_REVIEW", "authoritative": False,
                "provenance_verified": False, "eligible": None,
                "reason": "insufficient data (need annual_income and the HUD very-low (il50) limit)",
                "income_category": None, "deidentified_input": True,
                "il_provenance": {"authoritative": False, "verified": False, "source": prov_source},
                "assessed_by": "rules:HUD/AMI(needs limits)"}

    if not prov_verified:
        # Unverified limits: caller-supplied or a fabricated/forged source. NEVER issue an authoritative
        # determination on them — route to a human. (This is the P0-3 anti-fabrication path.)
        return {
            "assessed": True,
            "determination": "NEEDS_REVIEW",
            "authoritative": False,
            "provenance_verified": False,
            "eligible": None,
            "income_category": None,
            "household_size": hh,
            "annual_income": int(income),
            "deidentified_input": True,
            "assessed_by": "rules:HUD/AMI(unverified-limits->review)",
            "reason": ("income limits are not from a verified authoritative source (no valid HUD "
                       "provenance signature) — no eligibility determination made on unverified limits; "
                       "run lookup_income_limit and pass its signed il_source"),
            "il_provenance": {"authoritative": False, "verified": False, "source": prov_source},
            "notes": [SOURCE_NOTE,
                      "P0-3: assess requires a lookup-signed provenance token; a caller-supplied source label is not trusted"],
        }

    # ---- provenance VERIFIED -> authoritative determination ----
    # income category vs Area Median Income
    if il30 is not None and income <= il30:
        income_category = "EXTREMELY_LOW"
    elif income <= il50:
        income_category = "VERY_LOW"
    elif il80 is not None and income <= il80:
        income_category = "LOW"
    else:
        income_category = "OVER_INCOME"

    extremely_low_priority = (il30 is not None and income <= il30)

    if income <= il50:
        determination, eligible = "ELIGIBLE", True
        reason = ("annual income %.0f is within the very-low-income (50%% AMI) limit %.0f%s"
                  % (income, il50, "; extremely-low-income (30% AMI) targeting priority" if extremely_low_priority else ""))
    elif il80 is not None and income <= il80:
        determination, eligible = "NEEDS_REVIEW", None
        reason = ("annual income %.0f is low-income (>50%% and <=80%% AMI, limit %.0f); HCV admission generally "
                  "requires very-low income — housing-specialist review for eligible categories" % (income, il80))
    else:
        determination, eligible = "INELIGIBLE", False
        hi = il80 if il80 is not None else il50
        reason = ("annual income %.0f exceeds the applicable income limit (%.0f); over-income for assistance" % (income, hi))

    notes = [SOURCE_NOTE]
    if determination == "ELIGIBLE":
        notes.append("income screen only; full HCV eligibility (citizenship, criminal-history, unit inspection, HAP) remains for housing-specialist review")

    # Short proof fields FIRST (the MCP client truncates long results ~220 chars); detail LAST.
    return {
        "assessed": True,
        "determination": determination,             # ELIGIBLE | INELIGIBLE | NEEDS_REVIEW
        "authoritative": True,
        "provenance_verified": True,
        "eligible": eligible,
        "income_category": income_category,          # EXTREMELY_LOW | VERY_LOW | LOW | OVER_INCOME
        "extremely_low_priority": extremely_low_priority,
        "household_size": hh,
        "annual_income": int(income),
        "limit_50_ami": int(il50),
        "il_provenance": {"authoritative": True, "verified": True, "source": prov_source,
                          "entityid": il_source.get("entityid"), "county_name": il_source.get("county_name"),
                          "year": il_source.get("year")},
        "deidentified_input": True,
        "assessed_by": "rules:HUD/AMI(verified authoritative limits)",
        "reason": reason,
        "notes": notes,
    }
