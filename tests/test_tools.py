"""Unit tests for the housing-assistance governed tools — contract + fail-closed behavior. No AWS."""
import json
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")  # aligns with conftest; before tool import

from toolkit import call, CONTROLS  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(CONTROLS))
import provenance  # noqa: E402

SOURCE = "US Dept of Housing and Urban Development (HUD USER) — Income Limits"


def _signed_il_source(entityid="0603799999", year="2026", hh=4, il30=50000, il50=83300, il80=133250):
    """Mint the signed il_source token exactly as lookup_income_limit would, for the assess tests."""
    fields = {"entityid": entityid, "year": str(year), "household_size": hh,
              "il30": il30, "il50": il50, "il80": il80}
    tok = provenance.sign(SOURCE, fields)
    return json.dumps({"source": SOURCE, "entityid": entityid, "county_name": "Los Angeles County",
                       "household_size": hh, "year": str(year),
                       "authoritative": tok["authoritative"], "sig": tok["sig"], "alg": tok["alg"]})


def test_intake_extracts_fields():
    r = call("intake_application", {"application": "Household of 4. Annual household income: 40000. County entityid 0603799999."})
    assert r["fields"]["household_size"] == 4
    assert r["fields"]["annual_income"] == 40000


def test_assess_fail_closed_on_unmasked():
    r = call("assess_housing_eligibility", {"annual_income": 40000, "il50": 83300, "deidentified": False})
    assert r["assessed"] is False


def test_assess_unsigned_limits_go_to_review():
    # P0-3: limits with NO signed provenance (or a hand-typed source string) must NOT be trusted.
    r = call("assess_housing_eligibility", {"annual_income": 40000, "household_size": 4,
                                            "il30": 50000, "il50": 83300, "il80": 133250,
                                            "il_source": "US Dept of Housing and Urban Development (HUD USER)",
                                            "deidentified": True})
    assert r["determination"] == "NEEDS_REVIEW"
    assert r["authoritative"] is False
    assert r["provenance_verified"] is False
    assert r["eligible"] is None


def test_assess_verified_extremely_low_priority():
    # With a genuine lookup-signed token the determination is authoritative.
    r = call("assess_housing_eligibility", {"annual_income": 40000, "household_size": 4,
                                            "il30": 50000, "il50": 83300, "il80": 133250,
                                            "il_source": _signed_il_source(il30=50000, il50=83300, il80=133250),
                                            "deidentified": True})
    assert r["determination"] == "ELIGIBLE"
    assert r["authoritative"] is True
    assert r["income_category"] == "EXTREMELY_LOW"
    assert r["extremely_low_priority"] is True


def test_recertify_adverse_advance_notice():
    r = call("recertify", {"annual_income": 150000, "household_size": 4, "il50": 83300, "il80": 133250,
                           "prior_eligible": True, "deidentified": True})
    assert r["change_type"] == "ADVERSE"
    assert r["advance_notice_required"] is True


def test_overpayment_math():
    r = call("overpayment", {"prior_monthly_subsidy": 900, "corrected_monthly_subsidy": 600,
                             "months": 6, "deidentified": True})
    assert r["classification"] == "OVERPAYMENT"
    assert r["overpayment_amount"] == 1800.0


def test_core_finalize_refused():
    assert call("housing_core", {"case_id": "HOU-1"})["committed"] is False


def test_core_refer_fraud_refused():
    assert call("housing_core", {"fraud_case_id": "HOU-1"})["referred"] is False
