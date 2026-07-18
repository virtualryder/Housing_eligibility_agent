"""Unit tests for the housing-assistance governed tools — contract + fail-closed behavior. No AWS."""
from toolkit import call


def test_intake_extracts_fields():
    r = call("intake_application", {"application": "Household of 4. Annual household income: 40000. County entityid 0603799999."})
    assert r["fields"]["household_size"] == 4
    assert r["fields"]["annual_income"] == 40000


def test_assess_fail_closed_on_unmasked():
    r = call("assess_housing_eligibility", {"annual_income": 40000, "il50": 83300, "deidentified": False})
    assert r["assessed"] is False


def test_assess_extremely_low_priority():
    r = call("assess_housing_eligibility", {"annual_income": 40000, "household_size": 4,
                                            "il30": 50000, "il50": 83300, "il80": 133250, "deidentified": True})
    assert r["determination"] == "ELIGIBLE"
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
