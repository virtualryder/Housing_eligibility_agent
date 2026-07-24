# P0-11 clean-account validation run — CAPTURED EVIDENCE

*Live deploy → prove → destroy of the CDK path, 2026-07-24, us-east-1, sandbox account (id redacted:
`111122223333`). Every value below was captured from the real run; nothing is asserted.*

## 1. Deploy (CDK-synthesized templates via CloudFormation)

Synthesized offline (`python app.py`, context `env=val, retention_profile=sandbox-demo`), asset bundle
uploaded to the CDK bootstrap bucket, stacks created via `create-stack`:

| Stack | Result |
|---|---|
| `hou-val-data` | `CREATE_COMPLETE` (audit ledger PITR, sanitized-artifacts TTL table, WORM bucket Object Lock GOVERNANCE/1d sandbox profile) |
| `hou-val-compute` | `CREATE_COMPLETE` → `UPDATE_COMPLETE` (12 tool/control Lambdas, explicit IAM, tamper Deny, exact-ARN outputs) |
| `hou-val-workflow` | `CREATE_COMPLETE` → `UPDATE_COMPLETE` (deterministic controller `hou-val-determination-workflow` + sign-off gate) |
| `hou-val-identity` | `CREATE_COMPLETE` (federation-ready pool, **zero users/passwords**) |

## 2. Cloud proof — P0-1 sanitized-artifact control (real Comprehend, real DynamoDB)

`hou-val-mask-pii` invoked with live PII → **redacted in the cloud** and a **signed ref minted +
stored server-side**:

```
masked_case   : "Applicant [REDACTED:NAME], SSN [REDACTED:SSN], [REDACTED:ADDRESS], household of 4, …"
sanitized_ref : artifact_id e7fbca5338f24d70b17b8257428f24e3 · sha256 0328ab0c…2b9bca
                authoritative: true · stored: true (DynamoDB sanitized-artifacts table) · HMAC-SHA256
```

`hou-val-workflow-guards` (guard `deidentified`) then judged, in the cloud:

| Attempt | Result |
|---|---|
| **Genuine** mask_pii-signed ref | `ok: true — masking proven by a verified mask_pii-signed sanitized_ref` |
| **Forged** signature (`deadbeef…`) | `ok: false` (fail-closed) |
| **Spoofed boolean** `{"deidentified": true}` — the exact attack from the external review | `ok: false` (fail-closed) |
| **Mutated content** (an encoding-corrupted copy of the genuine ref) | `ok: false` — the hash/signature binding caught a real-world in-transit mutation |

## 3. Cloud proof — P0-2 deterministic controller (fail-closed end-to-end)

Execution `p011-validation-2` on `hou-val-determination-workflow` → **`SUCCEEDED`** with the
machine-enforced sequence: `Extract → GuardExtracted (ok:true) → LookupIncomeLimit (HUD source down,
found:false) → GuardAuthoritative (ok:false — "authoritative source unavailable — manual review") →
ManualReview` terminal. **No assessment, draft, or determination was produced on unverifiable
authoritative data** — correctness preceded availability, decided by the state machine, not the model.

**Regression found by the run (and fixed + tested):** execution `p011-validation-1` FAILED with
`States.Runtime` — the guard payload's JSONPath referenced limit keys a source-down lookup doesn't
return. Fix: the controller passes the **whole** lookup output and the guard judges it
(`workflow_guards.guard_authoritative`; regression test
`test_guard_authoritative_handles_source_down_lookup_output`). Exactly the class of defect this
validation step exists to catch.

## 4. Teardown

All four stacks deleted (`DELETE_COMPLETE`), followed by manual deletion of the deliberately-RETAIN'd
sandbox resources (audit ledger table, WORM bucket, Cognito pool) and the uploaded deploy artifacts,
then a residual-resource sweep (CloudFormation / Lambda / DynamoDB / Step Functions / Cognito) —
recorded in `VALIDATED_RELEASE.md`.

## 5. Boundaries of this run

Sandbox-demo retention profile; no HUD token configured (the happy-path authoritative branch is proven
offline by the signed-provenance suite and remains staged for a run with a HUD USER key); AgentCore
gateway/Cedar attachment not exercised (tool-level + controller-level controls were); identity pool
had zero users by design (P0-6).
