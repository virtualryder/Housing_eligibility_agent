# CDK — THE supported customer deployment path

*Reviewable, parameterized IaC. Deploy the validated release tag (`v0.9.4`), never `main`, per
[`../DEPLOYMENT-GUIDE.md`](../DEPLOYMENT-GUIDE.md). The shell engine (`lib/engine/`) is
**legacy/internal reference only** and must not be used for customer deployments.*

## Stacks

| Stack | Provisions | Controls carried |
|---|---|---|
| `hou-<env>-data` | append-only audit ledger (PITR, RETAIN), **sanitized-artifacts store** (TTL), pending-approvals table, **WORM vault** (Object Lock, retention **profile**), optional customer-managed KMS (key policy pre-authorizes logs/cloudwatch service principals) | P0-1 store · P0-12 retention (`-c retention_profile=sandbox-demo\|pilot\|production-reference`, COMPLIANCE for production-reference) · Gate-B B2 |
| `hou-<env>-network` *(optional, `-c network_mode=private`)* | 2-AZ VPC, governed Lambdas in ISOLATED subnets, **AWS Network Firewall deny-by-default egress allowlist = `.huduser.gov` ONLY**, S3/DDB gateway + 7 interface endpoints, 443-only SG | Gate-B B1 (live-validated) |
| `hou-<env>-compute` | one Lambda per governed tool, **explicit least-privilege IAM** per function, tamper **Deny** on the audit writer, **exact-ARN outputs**, **GA-2 domain-split signing secrets** (deid vs HUD — IAM prevents cross-domain reads), CMK env+logs under `kms=customer-managed`, `TENANT_ID` pinning | P0-5 · P0-7 · GA-2 · Gate-B B5 |
| `hou-<env>-workflow` | the **deterministic controller** state machine (guarded transitions → ManualReview on any unverified evidence) + the human sign-off gate (`waitForTaskToken`, SoD, content-hash binding) | P0-2 · GA-5 |
| `hou-<env>-identity` | federation-ready Cognito pool + client + reviewer group — **zero users, zero passwords**; `-c identity_mode=pilot` = MFA REQUIRED (software token only) + threat protection ENFORCED; optional enterprise-OIDC IdP as IaC (client secret via Secrets Manager dynamic reference) | P0-6 · Gate-B B3 |
| `hou-<env>-observability` | CloudWatch alarms → SNS ops topic (CMK-encrypted under `kms=customer-managed`) + operations dashboard. **Deploy AFTER workflow** (imports its export) | GA-6 |
| `hou-<env>-gateway` | **the full AgentCore attachment AS IaC** (GA-1, live-validated twice): custom-resource provider creates the Cedar policy engine → MCP gateway (CUSTOM_JWT via the identity pool) → SSM discovery param → one target per governed tool (exact ARNs, schemas synthesized from the manifest) → all Cedar policies → **ENFORCE**; stack delete reverses everything | GA-1 · GA-4 |

## Use

```bash
git checkout v0.9.4            # deploy the validated release, never main
cd cdk && python -m pip install -r requirements.txt
cdk synth  -c env=dev  -c retention_profile=sandbox-demo            # review the plan
# full Gate-B posture (validated live 2026-07-24 — evidence/GATE-B-VALIDATION.md):
cdk deploy --all -c env=pilot -c retention_profile=pilot -c kms=customer-managed \
  -c network_mode=private -c identity_mode=pilot -c tenant=<pha-id>
cdk destroy --all -c env=dev                                        # teardown (audit table/vault RETAIN)
```

Offline verification (no AWS): `python -m pytest tests/test_cdk_stacks.py -q` synthesizes the stacks
and asserts retention modes, IAM denies, the controller's exact state sequence + fail-closed choices,
the no-users identity posture, gateway-attachment tool/policy coverage, GA-2 split secret grants, and
the Gate-B network/KMS/identity coverage. Runs in CI.
