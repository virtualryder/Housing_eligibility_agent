# Gate-B validation run — ALL SWITCHES ON ✅ (2026-07-24, us-east-1, account redacted `111122223333`)

*One clean-account exercise of the full Gate-B posture, per `docs/GATE-B-CHECKLIST.md`:
`-c env=valb -c network_mode=private -c kms=customer-managed -c identity_mode=pilot
-c tenant=pha-la-county -c retention_profile=sandbox-demo`. Sandbox retention was chosen
deliberately so the WORM vault is deletable after the run — the retention profile is orthogonal to
the Gate-B switches (`pilot`/`production-reference` lock evidence for 90d/7y).*

## Deployment — 7 stacks, CDK-synthesized templates via CloudFormation

| Stack | Status | Proof carried |
|---|---|---|
| hou-valb-data | ✅ CREATE_COMPLETE | CMK `alias/hou-valb-data` (rotation ON, id `6039fc6f…`) encrypting all 3 tables + WORM vault |
| hou-valb-network | ✅ CREATE_COMPLETE | VPC 2-AZ; Network Firewall; per-AZ firewall-endpoint routes (DescribeFirewall custom resource); S3/DDB gateway + 7 interface endpoints; 443-only SG |
| hou-valb-identity | ✅ CREATE_COMPLETE | pilot posture (below) |
| hou-valb-compute | ✅ CREATE_COMPLETE | 12 Lambdas in ISOLATED app subnets; GA-2 split signing keys; CMK env + CMK log groups; `TENANT_ID=pha-la-county` |
| hou-valb-workflow | ✅ CREATE_COMPLETE | deterministic controller |
| hou-valb-observability | ✅ CREATE_COMPLETE | CMK-encrypted SNS ops topic + alarms + dashboard (first attempt rolled back on an export-ordering race — deploy observability AFTER workflow; runbook updated) |
| hou-valb-gateway | ✅ CREATE_COMPLETE | AgentCore attachment: `Enforcement=ENFORCE`, GatewayUrl `…housing-gw-l2vis1b0th…/mcp`, PolicyEngineId `hou_valb_housing_authz-ovstdsudid`, 9 targets + 7 Cedar policies — IaC path reproduced first-try with the GA-4 fixes |

## B1 — locked egress, captured live

`describe-rule-group hou-valb-egress-allowlist`:
```
GeneratedRulesType: ALLOWLIST
Targets:            [".huduser.gov"]
TargetTypes:        [TLS_SNI, HTTP_HOST]
```
The governed Lambdas have NO direct internet path (isolated subnets); the live HUD lookup below
succeeded **through** this firewall — the single sanctioned external destination works, and only it
is permitted. AWS-service traffic (Comprehend, Bedrock, Secrets Manager, Step Functions, KMS, Logs,
STS, S3, DynamoDB) rode the VPC endpoints.

## B3 — pilot identity, captured live (`describe-user-pool us-east-1_Pog9Q6jpK`)

```
MfaConfiguration:         ON        (REQUIRED for every operator)
EnabledMfas:              SOFTWARE_TOKEN_MFA only (no SMS)
AdvancedSecurityMode:     ENFORCED  (Cognito threat protection)
AllowAdminCreateUserOnly: true      (no self-signup)
EstimatedNumberOfUsers:   0         (zero users shipped by IaC — P0-6 held)
```
Enterprise-OIDC federation is IaC-proven by CDK assertion (dynamic-reference client secret — never
plaintext); a real IdP round-trip requires the customer's IdP (engagement work — honesty boundary).

## Happy path through the FULL Gate-B posture — `valb-happy-1` → **SUCCEEDED**

Visited exactly: `Extract → GuardExtracted → LookupIncomeLimit → GuardAuthoritative → MaskPii →
GuardDeidentified → AssessRules → GuardRulesExecuted → DraftNotice → AuditIntent → HumanSignoff
(paused) → approve → Finalize → Committed`. Reached the human gate in **<50s** inside the private
network. Ledger after commit: hash-chained INTENT + COMMITTED, `HEAD#HOU-VALB-0001`,
**`FINAL#HOU-VALB-0001`** exactly-once marker.

**B5 tenant proof (live):** the sanitized artifact persisted by mask_pii carries
`tenant: pha-la-county` — the deployment-pinned tenant, HMAC-signed inside the ref (request-body
tenant is ignored by design); approval was bound to `content_hash dd47e5be…`.

**GA-2 (live):** provenance verified with the HUD-domain key, sanitized_ref with the deid-domain key
— two separate Secrets Manager keys (`hou-valb/provenance-signing-hud`, `…-deid`), IAM-split.

## B6 — load + replay storm, captured live

- **Load:** 10 concurrent executions → **10/10 SUCCEEDED**, zero FAILED/TIMED_OUT/throttled; every
  case paused at its own sign-off gate and finalized exactly once after approval (10 distinct
  `FINAL#` markers). Pipeline-to-pause <50s under concurrency; end-to-end ≈97s including the
  scripted approvals.
- **Replay storm:** 10 CONCURRENT direct finalize invocations with an identical approval payload for
  `HOU-VALB-STORM` → **`FIRST: 1, IDEMPOTENT: 9`** — exactly one commit, one
  `FINAL#HOU-VALB-STORM` marker; every replay returned the ORIGINAL submission (GA-5 exactly-once
  confirmed live under a race, not just in unit tests). Ledger total: 12 FINAL markers, one per case.

## B4 — PII telemetry-leak canary, captured live (`scripts/pii_canary.py`)

Marker `CANARY-64D4E7418AD4-TELEMETRYPROBE` (name + SSN-shaped + address) ran through the pipeline;
sweep verdict:
```
verdict: PASS
leaks:   {}                                     <- CloudWatch Logs 0 · X-Ray 0 · DLQs 0
known_sensitive_findings: {stepfunctions_history: 87}
```
The must-be-clean destinations are CLEAN — the P0-9 no-payload-logging discipline held on live
telemetry. Step Functions history carries the raw case (87 marker occurrences): the KNOWN,
quantified Gate-B remediation item — pass the case by reference through the controller. `--strict`
(every destination clean) is the Gate-B exit bar and intentionally does not pass yet.

## Live-run findings (found → fixed → committed, this run)

1. **Env-agnostic AZ tokens break the per-AZ firewall-endpoint `Fn::GetAtt`** — the DescribeFirewall
   response field is an attribute NAME, so the AZ must be a synth-time literal; NetworkStack now
   pins `us-east-1a/b`. (Caught by CFN validation before any resource was created.)
2. **Observability must deploy after workflow** — parallel create raced the workflow's export
   (`No export named …Controller… found` → clean rollback, redeploy succeeded). Deployment-order
   note added to the guide.

## Teardown

All 7 stacks deleted (reverse order; the VPC-attached compute stack took ~17 min — Lambda ENI
release); RETAIN'd resources removed (audit ledger, WORM vault, identity pool; secrets removed by
stack delete; CMK scheduled for deletion — KMS minimum 7-day pending window); deploy artifacts
removed from the bootstrap bucket. The sweep also caught and removed two RESURFACED orphan policy
engines from the earlier val2/val3 runs (AgentCore engine deletion is asynchronous and can revert —
always re-sweep on the NEXT session, now a standing runbook step). Final residual sweep: **0 stacks,
0 Lambdas, 0 tables, 0 state machines, 0 pools, 0 VPCs/firewalls, 0 gateways, 0 policy engines**.
Staging secret `hud-user/api-token` intentionally retained.
