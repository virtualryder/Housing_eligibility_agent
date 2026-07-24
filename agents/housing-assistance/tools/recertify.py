import json

import sanitized  # server-issued sanitized-artifact verification (P0-1)

# recertify — annual/interim RE-CERTIFICATION. Housing Choice Voucher and public-housing tenants are
# re-examined periodically (and on interim income changes). Re-runs the deterministic income-eligibility
# rules on NEW facts and compares to the prior determination to classify the change. The governance
# point: an ADVERSE change (a reduction of the housing subsidy, an increase in the tenant rent share, or
# a termination of assistance) triggers due process — HUD requires TIMELY WRITTEN NOTICE and an INFORMAL
# HEARING/REVIEW right (24 CFR 982.555 for HCV; 24 CFR 966 grievance for public housing) BEFORE the
# adverse action takes effect. This tool flags that requirement; it never commits the change (the human
# sign-off gate owns the commit, and an adverse commit must carry the advance notice).
#
# Fail-closed: refuses non-de-identified input (mirrors mask_before_assess). Uses the same authoritative
# HUD very-low (il50) / low (il80) income limits supplied by lookup_income_limit.


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


def handler(event, context):
    e = _coerce(event)
    # P0-1: proof of masking is a mask_pii-signed sanitized_ref; a bare boolean is never accepted.
    if not sanitized.verify_ref(e.get("sanitized_ref")):
        return {"recertified": False,
                "error": ("refused: de-identification not proven — a valid sanitized_ref signed by "
                          "mask_pii is required; a deidentified boolean is not accepted as proof (P0-1)"),
                "deidentified_input": e.get("deidentified"), "sanitized_ref_verified": False}

    income = _num(e.get("annual_income"))
    il50 = _num(e.get("il50"))
    il80 = _num(e.get("il80"))
    # prior state: accept explicit prior_eligible, or infer from a prior_determination string
    prior_eligible = e.get("prior_eligible")
    if prior_eligible is None:
        pd = str(e.get("prior_determination", "")).upper()
        if "INELIGIBLE" in pd:
            prior_eligible = False
        elif "ELIGIBLE" in pd:
            prior_eligible = True

    if income is None or il50 is None or prior_eligible is None:
        return {"recertified": True, "change_type": "NEEDS_REVIEW", "advance_notice_required": None,
                "reason": "insufficient data (need annual_income, the HUD il50 limit, and the prior determination)",
                "deidentified_input": True}

    # New eligibility: continued assistance is generally retained through low-income (<= il80); admission
    # requires very-low (<= il50). For recertification we treat OVER-il80 as loss of assistance.
    hi = il80 if il80 is not None else il50
    new_eligible = income <= hi

    if prior_eligible and not new_eligible:
        change_type = "ADVERSE"          # termination / loss of assistance
    elif (not prior_eligible) and new_eligible:
        change_type = "FAVORABLE"        # newly eligible
    else:
        change_type = "NO_CHANGE"

    advance_notice_required = (change_type == "ADVERSE")
    due_process_note = (
        "ADVERSE action: HUD due process (24 CFR 982.555 HCV informal hearing / 24 CFR 966 public-housing "
        "grievance) requires timely written advance notice and a hearing/review right BEFORE the "
        "reduction/termination takes effect; the commit must go through the human sign-off gate carrying "
        "that notice." if advance_notice_required else
        "no adverse action; standard recertification processing"
    )

    # Short proof fields FIRST (MCP client truncates ~200 chars).
    return {
        "recertified": True,
        "change_type": change_type,                 # ADVERSE | FAVORABLE | NO_CHANGE
        "advance_notice_required": advance_notice_required,
        "prior_eligible": bool(prior_eligible),
        "new_eligible": bool(new_eligible),
        "deidentified_input": True,
        "recertified_by": "rules:HUD/AMI(authoritative limits)",
        "reason": ("income %.0f vs applicable limit %.0f" % (income, hi)),
        "due_process_note": due_process_note,
    }
