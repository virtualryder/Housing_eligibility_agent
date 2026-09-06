import json
import re

import negation

# intake_application — extract the decision-relevant, NON-PII fields from a raw Housing Choice Voucher /
# public-housing application (free text or JSON): household size, annual household income, county
# FIPS/entityid, and elderly/disabled flags. Deterministic and fail-soft. PII (name, SSN, address, DOB)
# is NOT needed downstream for the income determination and is redacted separately by mask_pii before
# drafting/audit.


def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            return json.loads(e)
        except Exception:
            return {"application": e}
    return e


def _num(s):
    m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", str(s))
    return float(m.group(0).replace(",", "")) if m else None


def handler(event, context):
    e = _coerce(event)
    # R3-2 pass-by-reference: the controller hands an OPAQUE case_ref (raw content never travels
    # through Step Functions state); fetch server-side. Inline `application` remains for direct/dev
    # calls only.
    text = e.get("application", "")
    if not text and e.get("case_ref"):
        import case_store
        text = case_store.get_case(e["case_ref"]) or ""
        if not text:
            return {"structured": False, "fields": {}, "missing_required": ["application"],
                    "error": "case_ref unresolved (unknown ref or wrong tenant) - fail-closed"}
    if not isinstance(text, str):
        text = json.dumps(text)
    low = text.lower()

    hh = e.get("household_size")
    if hh is None:
        m = re.search(r"household(?:\s+size)?[^0-9]{0,12}(\d+)", low)
        hh = int(m.group(1)) if m else None
    income = e.get("annual_income")
    if income is None:
        m = re.search(r"(?:annual(?:\s+household)?\s+income|yearly\s+income|income[^.\n]{0,20}year)[^0-9$]{0,12}\$?([\d,]+(?:\.\d+)?)", low)
        income = _num(m.group(1)) if m else None
    entityid = e.get("entityid") or e.get("county_fips")
    if entityid is None:
        m = re.search(r"(?:entityid|county\s*fips|fips)[^0-9]{0,8}(\d{5,10})", low)
        entityid = m.group(1) if m else None
    # L20 (live-found on benefits, 2026-09-06; same class here): these flags were NEGATION-BLIND.
    # "Applicant is not disabled" matched `disabled` and granted the disabled preference, and
    # "no longer elderly-designated" would have granted the elderly one. Both flags change the
    # preference category a household is placed in, so a negation-blind match assigns a household
    # to a preference the application explicitly denies. Shared implementation in
    # lib/controls/negation.py; fail-closed, so an ambiguous mention never grants a preference.
    elderly = e.get("elderly")
    if elderly is None:
        elderly = negation.asserted(low, r"\b(elderly|senior|age\s*6[2-9]|age\s*[7-9]\d)\b")
    disabled = e.get("disabled")
    if disabled is None:
        disabled = negation.asserted(low, r"\b(disabled|disability|ssdi|ssi\s+disab)\b")

    fields = {"household_size": hh, "annual_income": income, "entityid": entityid,
              "elderly": bool(elderly), "disabled": bool(disabled)}
    missing = [k for k in ("household_size", "annual_income") if fields.get(k) is None]
    return {"structured": True, "fields": fields, "missing_required": missing,
            "note": "non-PII decision fields; PII is redacted separately by mask_pii"}
