import json

import sanitized  # server-issued sanitized-artifact verification (P0-1)

# detect_overpayment — deterministic housing-assistance overpayment calculation. Given the monthly
# Housing Assistance Payment (HAP subsidy) actually paid and the subsidy that SHOULD have been paid
# under corrected income/facts, over a number of months, compute the overpayment. NO model. Governance
# note: identifying an overpayment is a calculation; RECOVERING it (repayment agreement / termination)
# or referring it as suspected fraud is a consequential action that must follow notice and a qualified
# human's decision — the agent recommends, it does not recover or refer.
#
# Fail-closed: refuses non-de-identified input.


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
        return {"computed": False,
                "error": ("refused: de-identification not proven — a valid sanitized_ref signed by "
                          "mask_pii is required; a deidentified boolean is not accepted as proof (P0-1)"),
                "deidentified_input": e.get("deidentified"), "sanitized_ref_verified": False}

    prior = _num(e.get("prior_monthly_subsidy"))
    corrected = _num(e.get("corrected_monthly_subsidy"), 0.0)
    months = e.get("months")
    try:
        months = int(months)
    except Exception:
        months = None

    if prior is None or months is None or months < 1:
        return {"computed": True, "classification": "NEEDS_REVIEW",
                "reason": "insufficient data (need prior_monthly_subsidy, corrected_monthly_subsidy, months)",
                "deidentified_input": True}

    monthly_diff = round(prior - corrected, 2)
    overpayment = round(max(0.0, monthly_diff) * months, 2)
    classification = "OVERPAYMENT" if overpayment > 0 else "NONE"

    note = (
        "overpaid subsidy identified; recovery must follow adequate notice and the household's "
        "informal-hearing rights, and any suspected-fraud referral is a HUMAN-only decision (the agent "
        "cannot refer)."
        if classification == "OVERPAYMENT" else
        "no overpayment (corrected subsidy >= subsidy paid)."
    )

    # Short proof fields FIRST (MCP client truncates ~200 chars).
    return {
        "computed": True,
        "classification": classification,           # OVERPAYMENT | NONE | NEEDS_REVIEW
        "overpayment_amount": overpayment,
        "monthly_difference": monthly_diff,
        "months": months,
        "deidentified_input": True,
        "computed_by": "rules:overpayment(prior-corrected)*months",
        "note": note,
    }
