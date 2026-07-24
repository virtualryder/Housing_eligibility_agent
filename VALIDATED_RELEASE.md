# VALIDATED_RELEASE — evidence of the release actually working (P0-11)

*Every release of this repo ships with this file filled in. A customer deploys an immutable tagged
release with captured evidence — never "whatever is on main." Fields marked ☐ are captured during the
release's clean-account validation run and MUST NOT be asserted before capture.*

## Release

| Field | Value |
|---|---|
| Tag | `v0.9.1-pilot-rc2` (immutable; 2026-07-24) — supersedes `v0.9.0-pilot-rc1` |
| Commit SHA | the commit carrying tag `v0.9.1-pilot-rc2` (`git rev-list -n1 v0.9.1-pilot-rc2`) |
| Date | 2026-07-24 |
| Deployment path validated | CDK (`cdk/`) — the customer path, **including the AgentCore Gateway/Cedar attachment as IaC** (`GatewayStack`). (The legacy shell engine is an internal reference and is NOT the release-validated path.) |

## Offline verification (captured now, re-run at tag time)

| Check | Result |
|---|---|
| Offline test suite (`python -m pytest tests/ -q`) | **117 passed** (2026-07-24, incl. all live-run regression tests) — P0-1 sanitized-artifact matrix, P0-3 token-boundary + redaction, P0-2 workflow-controller guards, P0-3(prov) HUD provenance gate, audit-chain (+ adversarial transaction proofs), sign-off identity/SoD, exactly-once finalize, Secrets Manager path, Cedar property tests + `authz_expectations.yaml` new-tool CI gate, CDK stack assertions incl. full gateway-attachment coverage, golden evals |
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

## GA-4 clean-account validation run (full governed pipeline + IaC gateway) — ✅ CAPTURED 2026-07-24

Full narrative + raw values: [`evidence/GA-4-LIVE-HAPPY-PATH.md`](evidence/GA-4-LIVE-HAPPY-PATH.md)
(happy path + gateway addendum).

| Field | Value |
|---|---|
| AWS account class / region | sandbox account (id redacted: `111122223333`) / us-east-1 |
| Happy-path proof | execution `ga4-happy-1` → **SUCCEEDED** end-to-end on live services: live HUD USER lookup (signed provenance verified) → real Comprehend masking (Secrets Manager–signed `sanitized_ref`) → deterministic AMI assessment → real guarded Bedrock notice → WORM/hash-chain `INTENT` → `HumanSignoff` pause (`content_hash` bound, duplicate-protected) → approval → **exactly-once Finalize** → `COMMITTED` + `FINAL#HOU-GA4-0001` marker |
| Gateway/Cedar IaC proof | `GatewayStack` → **CREATE_COMPLETE in `ENFORCE`**: policy engine + MCP gateway (CUSTOM_JWT via Cognito) + **9 manifest-synthesized targets** on exact Lambda ARNs + **7 deny-by-default Cedar policies** (gateway ARN injected), captured outputs incl. `Enforcement=ENFORCE`, GatewayUrl, PolicyEngineId, SSM discovery param |
| Secrets path proof | no plaintext secrets in templates (asserted); signing secret + HUD token resolved from Secrets Manager at runtime, fail-closed |
| Defects found + fixed by the runs | 7 live findings (IAM Latin-1 description; AgentCore engine-name charset; idempotent provider delete; stale-template upload race; `CreateGateway` gateway-role permission family `GetPolicyEngine`/`*Authorize*` on BOTH policy-engine and gateway resources; orphaned-engine reuse/cleanup; fixed provider function name causing CFN async-invoke stalls) — all fixed, tested, committed |
| Teardown | provider reverse-teardown verified (**0 gateways, 0 policy engines**); all stacks `DELETE_COMPLETE`; retained sandbox resources removed |
| Residual-resource scan | **clean** — 0 stacks, 0 Lambdas, 0 tables, 0 state machines, 0 pools, 0 buckets (staging secret `hud-user/api-token` intentionally retained) |

## Known boundaries at this release

Reference accelerator, not a certified system (`manifest.yaml honesty_boundary`, `PILOT-SCOPE.md`).
EIV/PIC/HMIS connectors stubbed. Retention profile must be selected per `docs/RETENTION-PROFILES.md`.
Enterprise IdP federation is P1-1.
