# Data-source policy (P0-4) — correctness precedes availability

*The written policy for every external/authoritative data dependency of the Housing agent. Rule zero:
**if authoritative source data is unavailable or unverifiable, the outcome is `NEEDS_REVIEW` (manual
review) — never a determination on fallback, cached, sample, or caller-supplied values.***

## HUD USER Income Limits API (the authoritative source)

| Attribute | Policy |
|---|---|
| Required? | **Required** for any authoritative determination. Optional only for non-binding demo output, which is always labeled `authoritative:false`. |
| Provenance | Values are HMAC-signed by `lookup_income_limit` (the only component that reaches HUD) — `lib/controls/provenance.py`. `assess_housing_eligibility` verifies the signature against the exact figures it uses. |
| Failure behavior | Token absent / API down / county unknown → `found:false`, **no signed token** → assess returns `NEEDS_REVIEW, authoritative:false`. Proven by `tests/test_provenance_gate.py::test_lookup_source_down_yields_no_token_then_review`. |
| Staleness | Limits are per HUD income-limit year. The `year` is signed inside the provenance token; a determination cites the year it used. Max staleness: the current published HUD year (customer may pin an earlier program year deliberately). |
| Caching | No silent caching in the reference path. If a customer adds a cache, cached values MUST retain their original signed provenance token and the year; a cache miss follows Failure behavior. |
| Discrepancy handling | If supplied figures do not verify against the token (tampering/mismatch) → `NEEDS_REVIEW` (proven: `test_assess_needs_review_when_limits_tampered_after_signing`). |
| Manual override | A housing specialist may decide a `NEEDS_REVIEW` case at the human sign-off gate; the override and the reviewer's verified identity are written to the append-only audit. The agent has no override path. |
| Evidence shown to reviewer | The determination carries `il_provenance` (source, entityid, county, year, verified flag) so the reviewer sees exactly which limits, from where, decided the screen. |

## De-identification (Amazon Comprehend DetectPiiEntities)

Required before any assess/recertify/overpayment/draft. Fail-closed: detection failure → no masked
text, no `sanitized_ref`, nothing downstream proceeds. Proof of masking is the mask_pii-signed
`sanitized_ref` (P0-1, `lib/controls/sanitized.py`) — never a boolean claim.

## The system-of-record connectors (EIV / PIC / HMIS)

**Stubbed** (`honesty_boundary.stubbed` in the manifest). Until a customer engagement wires and
validates them, no determination may claim verification against those systems.

*The "degrades gracefully" language in older docs refers to demo resilience routing to `NEEDS_REVIEW`;
it never means adjudicating on fallback values. This file governs on any conflict.*
