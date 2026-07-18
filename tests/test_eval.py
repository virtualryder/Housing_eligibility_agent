"""Eval / regression harness for the Housing Choice Voucher income-eligibility rules engine.

Golden cases pin the income-category + DETERMINATION against the HUD AMI framework so a rules change
fails CI. Categories: EXTREMELY_LOW <= 30% AMI (il30), VERY_LOW <= 50% (il50), LOW <= 80% (il80),
else OVER_INCOME; admission requires very-low; extremely-low-income targeting per 42 USC 1437n.
"""
import pytest
from toolkit import call

LIMITS = {"il30": 50000, "il50": 83300, "il80": 133250}  # illustrative LA-County-scale limits

GOLDEN = [
    ("extremely_low",
     {"annual_income": 40000, "household_size": 4, **LIMITS, "deidentified": True},
     {"determination": "ELIGIBLE", "income_category": "EXTREMELY_LOW", "extremely_low_priority": True}),
    ("very_low",
     {"annual_income": 70000, "household_size": 4, **LIMITS, "deidentified": True},
     {"determination": "ELIGIBLE", "income_category": "VERY_LOW", "extremely_low_priority": False}),
    ("low_needs_review",
     {"annual_income": 100000, "household_size": 4, **LIMITS, "deidentified": True},
     {"determination": "NEEDS_REVIEW", "income_category": "LOW"}),
    ("over_income",
     {"annual_income": 150000, "household_size": 4, **LIMITS, "deidentified": True},
     {"determination": "INELIGIBLE", "income_category": "OVER_INCOME", "eligible": False}),
]

NEGATIVE = [
    ("assess_unmasked", "assess_housing_eligibility",
     {"annual_income": 40000, "il50": 83300, "deidentified": False},
     lambda r: r["assessed"] is False),
    ("recertify_unmasked", "recertify",
     {"annual_income": 40000, "il50": 83300, "il80": 133250, "prior_eligible": True, "deidentified": False},
     lambda r: r["recertified"] is False),
]


@pytest.mark.parametrize("label,inp,expected", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_golden_determination(label, inp, expected):
    r = call("assess_housing_eligibility", inp)
    for k, v in expected.items():
        assert r.get(k) == v, f"{label}: {k} expected {v!r}, got {r.get(k)!r}"


@pytest.mark.parametrize("label,tool,inp,check", NEGATIVE, ids=[n[0] for n in NEGATIVE])
def test_negative_fail_closed(label, tool, inp, check):
    assert check(call(tool, inp)), f"{label}: fail-closed guard did not hold"
