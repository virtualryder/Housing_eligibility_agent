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

---

# ADDENDUM (2026-07-24, retry session): GATEWAY LEG ✅ CAPTURED — GA-4 COMPLETE

## The full AgentCore/Gateway/Cedar attachment deployed as pure IaC — CREATE_COMPLETE

Stack `hou-val4-gw3` (the CDK GatewayStack, no shell steps) reached **CREATE_COMPLETE** with outputs:

| Output | Value |
|---|---|
| **Enforcement** | **`ENFORCE`** |
| GatewayUrl | `https://hou-val4-housing-gw-h3nmeyqc7p.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp` |
| GatewayArn | `arn:aws:bedrock-agentcore:us-east-1:<redacted>:gateway/hou-val4-housing-gw-h3nmeyqc7p` |
| PolicyEngineId | `hou_val4_housing_authz-g32ayjkggz` |
| SsmDiscoveryParam | `/hou-val4-housing/gateway-url` |

The provider executed the complete sequence live: policy engine → MCP gateway (CUSTOM_JWT via the
identity pool) → SSM discovery → **9 gateway targets** (manifest-synthesized schemas, exact Lambda
ARNs) → **7 Cedar policies** (gateway ARN injected into forbids) → **flip to ENFORCE**. Stack delete
reversed everything (verified: 0 gateways, 0 policy engines after teardown).

## Three more live-run findings (fixed + tested via the run itself)

5. `CreateGateway` validates a PERMISSION FAMILY on the gateway role against BOTH the policy engine
   and the gateway resource: `bedrock-agentcore:GetPolicyEngine` + the `*Authorize*` family
   (`AuthorizeAction`, `PartiallyAuthorizeActions`, …). Undocumented; discovered error-by-error;
   role now grants the family, resource-scoped to this account's policy engines + gateways.
6. A FAILED CreateGateway orphans the already-created policy engine → ConflictException forever.
   Provider now reuses an existing engine by name on create and cleans orphans by name on delete.
7. The CloudFormation async-invoke "stall" root cause: a FIXED provider function name re-created
   immediately after deletion. Unique (CDK-generated) names invoke instantly. This also explains the
   val2/val3 stalls.

## Teardown
All `hou-val4` stacks deleted; provider reverse-teardown verified (0 gateways / 0 policy engines);
retained sandbox resources (audit table, bucket, pool, secrets, SSM param, S3 artifacts) removed.
Residual sweep: **0 stacks, 0 tables, 0 Lambdas, 0 gateways.**

**GA-4 is now fully captured: the governed pipeline happy path AND the IaC gateway attachment in
ENFORCE — every Review-2 "mandatory before a synthetic-data pilot" deployment item is live-proven.**
