# VALIDATED_RELEASE — evidence of the release actually working (P0-11)

*Every release of this repo ships with this file filled in. A customer deploys an immutable tagged
release with captured evidence — never "whatever is on main." Fields marked ☐ are captured during the
release's clean-account validation run and MUST NOT be asserted before capture.*

## Release

| Field | Value |
|---|---|
| Tag | `v0.9.0-pilot-rc1` (immutable; pushed 2026-07-24) |
| Commit SHA | the commit carrying tag `v0.9.0-pilot-rc1` (`git rev-list -n1 v0.9.0-pilot-rc1`) |
| Date | 2026-07-24 |
| Deployment path validated | CDK (`cdk/`) — the customer path. (The legacy shell engine is an internal reference and is NOT the release-validated path.) |

## Offline verification (captured now, re-run at tag time)

| Check | Result |
|---|---|
| Offline test suite (`python -m pytest tests/ -q`) | **98 passed** (2026-07-24, incl. the live-run regression test) — includes P0-1 sanitized-artifact matrix, P0-3 token-boundary + redaction, P0-2 workflow-controller guards, P0-3(prov) HUD provenance gate, audit-chain, sign-off identity/SoD, golden evals |
| CDK synth + assertions (`tests/test_cdk_stacks.py`) | **passing** — templates synthesize; retention/IAM/state-machine assertions hold |
| Security scans (ruff bug-classes, pip-audit, SBOM) | via `.github/workflows/ci.yml` on every push |

## Clean-account validation run (deploy -> prove -> destroy) — ✅ CAPTURED 2026-07-24

Full narrative + raw values: [`evidence/P0-11-VALIDATION-RUN.md`](evidence/P0-11-VALIDATION-RUN.md).

| Field | Value |
|---|---|
| AWS account class / region | sandbox account (id redacted: `111122223333`) / us-east-1 |
| Deployment path | **CDK-synthesized templates** (data, compute, workflow, identity) via CloudFormation — all `CREATE_COMPLETE`; compute+workflow cleanly `UPDATE_COMPLETE`d mid-run |
| P0-1 cloud proof | real Comprehend masking (`[REDACTED:NAME]/[SSN]/[ADDRESS]`); signed `sanitized_ref` minted + stored (`artifact_id e7fbca53…`, `authoritative:true, stored:true`); guard: genuine ref **ok:true**; forged sig / spoofed `deidentified:true` boolean / mutated content all **ok:false** |
| P0-2 cloud proof | controller execution `p011-validation-2` → **SUCCEEDED**: Extract → GuardExtracted(ok) → Lookup(source down) → GuardAuthoritative(**ok:false**) → **ManualReview** — no determination on unverifiable data, enforced by the state machine |
| Defect found + fixed by the run | `p011-validation-1` FAILED `States.Runtime` (brittle guard JSONPath on a source-down lookup) → guard now judges the whole lookup output; regression test added; suite **98/98** |
| Teardown | all 4 stacks `DELETE_COMPLETE`; RETAIN'd sandbox resources removed (audit table, WORM bucket, Cognito pool); deploy artifacts removed from the bootstrap bucket |
| Residual-resource scan | **clean** — 0 `hou-val` stacks, 0 Lambdas, 0 DynamoDB tables, 0 state machines, 0 Cognito pools |

**Tagging (owner action):** the working tree carrying this evidence is ready to become the immutable
release — `git add -A && git commit -m "v0.9.0-pilot-rc1: P0 hardening + captured validation" && git tag v0.9.0-pilot-rc1`.

## Known boundaries at this release

Reference accelerator, not a certified system (`manifest.yaml honesty_boundary`, `PILOT-SCOPE.md`).
EIV/PIC/HMIS connectors stubbed. Retention profile must be selected per `docs/RETENTION-PROFILES.md`.
Enterprise IdP federation is P1-1.
