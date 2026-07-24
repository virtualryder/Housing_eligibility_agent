# Deployment Guide — CDK (the only supported customer path)

*GA-7 (Review-2). Deploys the governed HCV preliminary income-screening assistant. Estimated time:
30–45 min. Estimated pilot cost: < $5/day idle + ~$0.09 per governed transaction (see
`docs/Cost-and-Latency-One-Pager.md`).*

## 1. Prerequisites
- **Account/org:** a dedicated sandbox or pilot account (one PHA per account — no multi-tenancy);
  Control Tower/SCPs must allow: CloudFormation, Lambda, DynamoDB, S3 (+Object Lock), Step Functions,
  Cognito, Secrets Manager, SNS, CloudWatch, Comprehend, Bedrock (model access enabled for the
  configured Claude model), Bedrock AgentCore (for the gateway attachment).
- **Region:** any Region with Bedrock AgentCore + the chosen model (validated in us-east-1).
- **Quotas:** default quotas suffice for a pilot (≤ 12 Lambdas, 1 state machine, 2 tables, 1 bucket).
- **Tooling:** Node 18+, `npm i -g aws-cdk`, Python 3.12, `pip install -r cdk/requirements.txt`.
- **Deployment role:** CloudFormation service-role pattern; least-privilege statement list in
  `cdk/README.md` (or use CDK bootstrap's deploy role). `cdk bootstrap aws://<acct>/<region>` once.

## 2. Configure (environment matrix)
| Context | dev | pilot | production-reference |
|---|---|---|---|
| `-c env=` | dev | pilot | prod |
| `-c retention_profile=` | sandbox-demo | pilot | production-reference (COMPLIANCE — customer-approved schedule ONLY) |
| `-c kms=` | aws-managed | customer-managed | customer-managed |
| `-c network_mode=` | public | **private** (Gate-B B1: isolated subnets + Network Firewall egress allowlist = `.huduser.gov` only) | private |
| `-c identity_mode=` | sandbox | **pilot** (Gate-B B3: MFA REQUIRED software-token-only, threat protection ENFORCED) | pilot |
| `-c tenant=` | *(unset)* | **`<pha-id>`** (Gate-B B5: deployment-pinned tenant, HMAC-signed into every sanitized artifact) | `<pha-id>` |

Optional enterprise-OIDC federation as IaC: `-c oidc_issuer_url=… -c oidc_client_id=…
-c oidc_client_secret_arn=<SecretsManager ARN>` (the client secret enters the template only as a
CloudFormation dynamic reference). The full Gate-B posture was validated live 2026-07-24 —
[`evidence/GATE-B-VALIDATION.md`](evidence/GATE-B-VALIDATION.md).

Secrets (created by the compute stack, values operator-managed):
- `hou-<env>/provenance-signing-deid` — generated automatically; signs mask_pii sanitized-artifact refs ONLY (GA-2 trust-domain key; never plaintext anywhere).
- `hou-<env>/provenance-signing-hud` — generated automatically; signs authoritative HUD income-limit provenance ONLY (GA-2; IAM prevents the masker reading this key and the lookup reading the deid key).
- `hou-<env>/hud-api-token` — token already staged in Secrets Manager (`hud-user/api-token`, validated live 2026-07-24 against LA County/2026); copy at deploy:
  `aws secretsmanager get-secret-value --secret-id hud-user/api-token --query SecretString --output text | xargs -I{} aws secretsmanager put-secret-value --secret-id hou-<env>/hud-api-token --secret-string {}` (never write the token to a tracked file; local dev uses the gitignored `lib/runtime/.hud-token.env`).

Identity: the pool ships with ZERO users. Federate your IdP per `docs/IdP-Federation-Reference.md`
(Entra ID / Okta / Ping), map groups to `housing_specialist`, enforce MFA at the IdP.

## 3. Deploy
```bash
cd cdk && pip install -r requirements.txt
cdk deploy --all -c env=pilot -c retention_profile=pilot -c kms=customer-managed \
  -c network_mode=private -c identity_mode=pilot -c tenant=<pha-id>
# then attach the AgentCore gateway + Cedar policies (GatewayStack; see cdk/README.md §AgentCore)
```
Ordering notes (from the live Gate-B run): the **observability stack imports the workflow stack's
export — deploy it after workflow** (CDK orders this automatically; if driving CloudFormation
directly, sequence it yourself). The Network Firewall adds ~8–10 min to network-stack create, and
VPC-attached Lambda stacks take longer to DELETE (ENI release) — plan windows accordingly.

## 4. Validate (must PASS before any use)
```bash
python scripts/validate_deployment.py --env pilot --region <region>
```
Emits the machine-readable verdict, e.g.:
```json
{"deployment_status":"PASS","release":"<tag>","stacks":"CREATE_COMPLETE","secrets":"PRESENT",
 "masking_control":"PASS","forged_ref_denied":"PASS","workflow_fail_closed":"PASS",
 "hud_lookup":"PASS|NOT-CONFIGURED","audit_chain":"INTACT"}
```
Any FAIL blocks the pilot. Attach the JSON to the deployment record.

## 5. Operate
Subscribe ops to the `hou-<env>-ops-alarms` SNS topic; dashboard `hou-<env>-operations`. Runbooks:
`docs/THREAT-MODEL.md` (security events), `docs/DATA-SOURCE-POLICY.md` (HUD outage → NEEDS_REVIEW),
`docs/RETENTION-PROFILES.md` (retention/break-glass).

## 6. Upgrade / rollback / uninstall
- **Upgrade:** deploy a NEW tagged release via `cdk deploy` (change-sets are reviewable); never patch in place.
- **Rollback:** redeploy the previous tag (stateless compute; data stacks are additive).
- **Uninstall:** `cdk destroy --all` then delete the RETAIN'd audit table + WORM vault **only per the
  customer's records-disposition procedure**, then run the residual-resource check:
  `python scripts/validate_deployment.py --env pilot --expect-absent`.

## 7. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| Execution → ManualReview at GuardAuthoritative | HUD token missing/invalid (by design, fail-closed) — fill the secret |
| assess refuses "de-identification not proven" | caller skipped mask_pii or forged the ref (by design) |
| register raises "duplicate submission" | a PENDING approval already exists for the case (by design) |
| finalize returns idempotent:true | case already finalized — original submission returned (by design) |
| Stack delete leaves table/bucket | RETAIN by design — records disposition is a human decision |

**Known limitations:** preliminary income screening only (see `PILOT-SCOPE.md`); EIV/PIC/HMIS stubs;
AgentCore attachment steps in `cdk/README.md`; enterprise IdP is engagement work.
**Support:** pilot operated by the deploying SA/partner; escalation owner named in the pilot SOW
(`CONFIG-WORKSHEET.md` §ownership).
