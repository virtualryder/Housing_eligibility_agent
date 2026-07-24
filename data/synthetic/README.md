# Synthetic test dataset (GA-7 / A11)

Five synthetic HCV applications + expected outcomes for `assess_housing_eligibility` given the
ILLUSTRATIVE limits (hh=4: il30=50000, il50=83300, il80=133250 — LA-County-scale; live runs use the
signed HUD lookup instead). All PII below is fabricated.

| case | application | expected category | expected determination |
|---|---|---|---|
| SYN-001 | household 4, income 40000, entityid 0603799999 | EXTREMELY_LOW | ELIGIBLE (targeting priority) |
| SYN-002 | household 4, income 70000, entityid 0603799999 | VERY_LOW | ELIGIBLE |
| SYN-003 | household 4, income 100000, entityid 0603799999 | LOW | NEEDS_REVIEW |
| SYN-004 | household 4, income 150000, entityid 0603799999 | OVER_INCOME | INELIGIBLE |
| SYN-005 | household 4, income 40000, NO entityid | — | ManualReview at GuardExtracted (fail-closed) |

Raw inputs: `cases.jsonl`. These mirror the CI golden evals (`tests/test_eval.py`), so a deployed
environment and the offline suite must agree.
