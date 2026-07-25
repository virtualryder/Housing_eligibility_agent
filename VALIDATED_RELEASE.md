# VALIDATED_RELEASE — evidence of the release actually working (P0-11)

*Every release of this repo ships with this file filled in. A customer deploys an immutable tagged
release with captured evidence — never "whatever is on main." Fields marked ☐ are captured during the
release's clean-account validation run and MUST NOT be asserted before capture.*

## Release

| Field | Value |
|---|---|
| Tag | `v0.9.4` (immutable; 2026-07-24) — supersedes `v0.9.3`/`v0.9.2` |
| Commit SHA | the commit carrying tag `v0.9.4` (`git rev-list -n1 v0.9.4`) |
| Date | 2026-07-24 |
| Deployment path validated | CDK (`cdk/`) — the customer path, including the AgentCore Gateway/Cedar attachment as IaC AND the **full Gate-B hardening posture** (`network_mode=private`, `kms=customer-managed`, `identity_mode=pilot`, pinned `tenant`). (The legacy shell engine is an internal reference and is NOT the release-validated path.) |

## Offline verification (captured now, re-run at tag time)

| Check | Result |
|---|---|
| Offline test suite (`python -m pytest tests/ -q`) | **145 passed** (2026-07-24, incl. all live-run regression tests) — P0-1 sanitized-artifact matrix, P0-3 token-boundary + redaction, P0-2 workflow-controller guards, P0-3(prov) HUD provenance gate, audit-chain (+ adversarial transaction proofs), sign-off identity/SoD, exactly-once finalize, **GA-2 cross-domain key-forgery matrix**, **B5 tenant-isolation matrix**, **B4 canary + B6 load/replay verdict logic**, Cedar property tests + new-tool CI gate, CDK stack assertions incl. gateway-attachment, **network/KMS/identity Gate-B coverage**, golden evals |
| CDK synth + assertions (`tests/test_cdk_stacks.py`) | **passing** — templates synthesize; retention/IAM/state-machine assertions hold |
| Security scans (ruff bug-classes, pip-audit, SBOM) | via `.github/workflows/ci.yml` on every push |

## P0-11 clean-account validation run (deploy -> prove -> destroy) — ✅ CAPTURED 2026-07-24
*(Historical capture — test counts quoted below are as-of that run; the current suite count is in the
table above. Counts inside dated capture sections are never retro-edited.)*

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

## Gate-B clean-account validation run (ALL hardening switches on) — ✅ CAPTURED 2026-07-24

Full narrative + raw values: [`evidence/GATE-B-VALIDATION.md`](evidence/GATE-B-VALIDATION.md).

| Field | Value |
|---|---|
| Posture | 7 stacks `CREATE_COMPLETE`: private networking (isolated subnets + Network Firewall **ALLOWLIST = [.huduser.gov] only**, 9 VPC endpoints), customer-managed KMS (rotating CMK over tables/WORM/secrets/env/logs/SNS), pilot identity (**MFA ON, software-token only, threat protection ENFORCED, 0 users**), pinned tenant `pha-la-county`, AgentCore gateway in **ENFORCE** |
| Happy path | `valb-happy-1` → **SUCCEEDED** end-to-end INSIDE the private network (<50s to the human gate); live HUD lookup THROUGH the firewall; tenant HMAC-signed in the live artifact; `FINAL#` exactly-once marker |
| Load | **10/10 concurrent executions SUCCEEDED**, one `FINAL#` marker per case, zero throttles/failures |
| Replay storm | 10 concurrent identical finalize replays → **`FIRST: 1, IDEMPOTENT: 9`** — exactly-once confirmed live under race |
| PII canary | **PASS** — 0 marker hits in CloudWatch Logs / X-Ray / DLQs; SFN history finding quantified (87 hits) with pass-by-reference remediation tracked (`--strict` = Gate-B exit bar) |
| Defects found + fixed by the run | 2 (env-agnostic AZ token in firewall routing; observability-before-workflow export race) — total across all validation runs: **10, all fixed + regression-tested** |
| Teardown | all stacks deleted; RETAIN'd resources removed; CMK scheduled for deletion (7-day KMS minimum); residual sweep clean |

## Known boundaries at this release

Reference accelerator, not a certified system (`manifest.yaml honesty_boundary`, `PILOT-SCOPE.md`).
EIV/PIC/HMIS connectors stubbed. Retention profile must be selected per `docs/RETENTION-PROFILES.md`.
Enterprise IdP federation is P1-1.
