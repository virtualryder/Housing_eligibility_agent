# CDK — the primary customer deployment path (P0-5)

*Reviewable, parameterized IaC replacing the imperative shell engine for customer deployments. The
shell engine (`lib/engine/`) remains an internal reference only and is not the release-validated path.*

## Stacks

| Stack | Provisions | P0 controls carried |
|---|---|---|
| `hou-<env>-data` | append-only audit ledger (PITR, RETAIN), **sanitized-artifacts store** (TTL), **WORM vault** (Object Lock, retention **profile**), optional customer-managed KMS | P0-1 store · P0-12 retention (`-c retention_profile=sandbox-demo\|pilot\|production-reference`, COMPLIANCE for production-reference) |
| `hou-<env>-compute` | one Lambda per governed tool, **explicit least-privilege IAM** per function, tamper **Deny** on the audit writer, **exact-ARN outputs** | P0-5 · P0-7 (consumers use outputs, never name discovery) |
| `hou-<env>-workflow` | the **deterministic controller** state machine (guarded transitions → ManualReview on any unverified evidence) + the human sign-off gate (`waitForTaskToken`, SoD) | P0-2 |
| `hou-<env>-identity` | federation-ready Cognito pool + client + reviewer group — **zero users, zero passwords** | P0-6 (production identity = enterprise IdP; see `docs/IdP-Federation-Reference.md`) |

## Use

```bash
cd cdk && python -m pip install -r requirements.txt
cdk synth  -c env=dev  -c retention_profile=sandbox-demo            # review the plan
cdk deploy --all -c env=prod -c retention_profile=production-reference -c kms=customer-managed
cdk destroy --all -c env=dev                                        # teardown (audit table/vault RETAIN)
```

Offline verification (no AWS): `python -m pytest tests/test_cdk_stacks.py -q` synthesizes the stacks
and asserts retention modes, IAM denies, the controller's exact state sequence + fail-closed choices,
and the no-users/no-passwords identity posture. Runs in CI.

**AgentCore attachment:** the gateway targets + Cedar policy load consume these stacks' CfnOutputs
(function ARNs, table/bucket names). Until that attachment is itself IaC, run the engine's
gateway/policy steps pointing at the outputs — never at discovered names.
