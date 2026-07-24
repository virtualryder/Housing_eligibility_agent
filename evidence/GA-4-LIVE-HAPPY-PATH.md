# GA-4 live validation — FULL HAPPY PATH CAPTURED (2026-07-24, us-east-1, account redacted)

## ✅ The core objective: the complete governed pipeline ran END-TO-END on live services

Execution `ga4-happy-1` on `hou-val2-determination-workflow` → **SUCCEEDED**, visiting exactly:
`Extract → GuardExtracted → LookupIncomeLimit → GuardAuthoritative → MaskPii → GuardDeidentified →
AssessRules → GuardRulesExecuted → DraftNotice → AuditIntent → HumanSignoff → Finalize → Committed`

Every guard passed on **genuine, live evidence**:
- **LIVE HUD USER API** lookup (real token from Secrets Manager) → limits HMAC-signed → GuardAuthoritative verified the signature (LA County, 2026, il50_p4=83300).
- **Real Comprehend** masking → signed `sanitized_ref` minted with the **Secrets Manager** signing secret (SM path live-proven) → GuardDeidentified verified.
- Deterministic AMI assessment → GuardRulesExecuted; **real Bedrock** notice draft; **WORM/hash-chain audit INTENT** written.
- **Paused at HumanSignoff** (`waitForTaskToken`): pending approval stored with duplicate protection + `content_hash d8a764c4…` binding the approval to the exact assessment.
- Approval released → **Finalize exactly once**. Final ledger: `INTENT(determination)` → `COMMITTED(finalize)` → `HEAD#HOU-GA4-0001` chain tip → **`FINAL#HOU-GA4-0001` exactly-once marker**.

## Live-run defects found → fixed → committed (why validation exists)
1. IAM role description rejected the em-dash (Latin-1 constraint) → fixed.
2. AgentCore policy-engine name rejected hyphens (`^[A-Za-z][A-Za-z0-9_]*$`) → prefix sanitized.
3. Provider delete path raised on a never-created gateway → idempotent-delete guard added.
4. Windows↔VM mount sync lag shipped a stale template to S3 once → verify-before-upload noted in runbook.

## ⚠ Partially validated: the GatewayStack attachment
Data/compute/workflow/identity/observability stacks all reached CREATE_COMPLETE via CDK templates.
The gateway attachment provider progressed past both fixed defects but its third attempt rolled back
with the failure outside the captured log window; diagnosis deferred to keep teardown discipline.
**The AgentCore gateway/Cedar path therefore remains proven by the earlier shell-engine deployment,
not yet by the CDK provider — GA-4 gateway leg re-runs after that diagnosis (task #95 stays open).**

## Teardown
All `hou-val2-*` stacks DELETE_COMPLETE; retained sandbox resources (audit ledger incl. the evidence
above — sandbox-demo profile, bucket, pool, both env secrets) deleted; deploy artifacts removed from
the bootstrap bucket. Residual sweep: **0 stacks, 0 Lambdas, 0 tables, 0 state machines, 0 pools, 0 buckets.**
The staging secret `hud-user/api-token` is intentionally retained for the next run.
