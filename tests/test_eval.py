"""Eval / regression harness for the Housing Choice Voucher income-eligibility rules engine.

Golden cases pin the income-category + DETERMINATION against the HUD AMI framework so a rules change
fails CI. Categories: EXTREMELY_LOW <= 30% AMI (il30), VERY_LOW <= 50% (il50), LOW <= 80% (il80),
else OVER_INCOME; admission requires very-low; extremely-low-income targeting per 42 USC 1437n.

P0-3: assess only issues an authoritative determination on limits that carry a signature minted by
lookup_income_limit, so every golden case supplies a genuine signed il_source token (same secret the
deployed lookup + assess Lambdas share). The unsigned/fabricated path is covered in test_provenance_gate.
"""
import json
import os

os.environ.setdefault("PROVENANCE_SECRET", "p0-unit-provenance-secret")  # aligns with conftest; before tool import

import pytest  # noqa: E402
from toolkit import call, CONTROLS, make_sanitized_ref  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, str(CONTROLS))
import provenance  # noqa: E402

SOURCE = "US Dept of Housing and Urban Development (HUD USER) — Income Limits"
LIMITS = {"il30": 50000, "il50": 83300, "il80": 133250}  # illustrative LA-County-scale limits


def _il_source(hh=4, il30=50000, il50=83300, il80=133250, entityid="0603799999", year="2026"):
    fields = {"entityid": entityid, "year": str(year), "household_size": hh,
              "il30": il30, "il50": il50, "il80": il80}
    tok = provenance.sign(SOURCE, fields)
    return json.dumps({"source": SOURCE, "entityid": entityid, "county_name": "Los Angeles County",
                       "household_size": hh, "year": str(year),
                       "authoritative": tok["authoritative"], "sig": tok["sig"], "alg": tok["alg"]})


SIGNED = _il_source(**{"hh": 4, **LIMITS})
REF = make_sanitized_ref()  # P0-1: signed proof of masking for the positive paths

GOLDEN = [
    ("extremely_low",
     {"annual_income": 40000, "household_size": 4, **LIMITS, "il_source": SIGNED, "deidentified": True, "sanitized_ref": REF},
     {"determination": "ELIGIBLE", "income_category": "EXTREMELY_LOW", "extremely_low_priority": True}),
    ("very_low",
     {"annual_income": 70000, "household_size": 4, **LIMITS, "il_source": SIGNED, "deidentified": True, "sanitized_ref": REF},
     {"determination": "ELIGIBLE", "income_category": "VERY_LOW", "extremely_low_priority": False}),
    ("low_needs_review",
     {"annual_income": 100000, "household_size": 4, **LIMITS, "il_source": SIGNED, "deidentified": True, "sanitized_ref": REF},
     {"determination": "NEEDS_REVIEW", "income_category": "LOW"}),
    ("over_income",
     {"annual_income": 150000, "household_size": 4, **LIMITS, "il_source": SIGNED, "deidentified": True, "sanitized_ref": REF},
     {"determination": "INELIGIBLE", "income_category": "OVER_INCOME", "eligible": False}),
]

NEGATIVE = [
    ("assess_unmasked", "assess_housing_eligibility",
     {"annual_income": 40000, "il50": 83300, "deidentified": False},
     lambda r: r["assessed"] is False),
    ("assess_unsigned_limits", "assess_housing_eligibility",
     {"annual_income": 40000, "household_size": 4, **LIMITS, "deidentified": True, "sanitized_ref": REF},
     lambda r: r["determination"] == "NEEDS_REVIEW" and r["authoritative"] is False),
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
