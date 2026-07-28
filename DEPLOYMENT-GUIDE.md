# Deployment Guide — CDK (the only supported customer path)

> **Re-validated live 2026-07-28 (`hou-val2`, us-east-1, all Gate-B switches).** 7/7 stacks in 530s;
> `validate_deployment.py` → **PASS** (masking control, genuine guard, forged-ref denied, ingest
> pass-by-reference, workflow fail-closed, HUD lookup CONFIGURED); strict PII canary **PASS, 0 leaks**;
> MFA ON / 0 users / admin-create-only; Network Firewall egress allowlist = `.huduser.gov`.
> See [`evidence/`](evidence/). This guide was walked end to end as an SA would; the fixes below came
> out of that walk.


*GA-7 (Review-2). Deploys the governed HCV preliminary income-screening assistant. Estimated time:
30–45 min. Estimated pilot cost: < $5/day idle + ~$0.09 per governed transaction (see
`docs/Cost-and-Latency-One-Pager.md`).*

> ## ⛔ Reusing an environment name? Delete its leftover log groups FIRST
>
> `cdk destroy` does **not** delete the `/aws/lambda/hou-<env>-*` log groups. When you later redeploy
> the **same `-c env=` value**, the compute stack (with `kms=customer-managed`) creates those log
> groups *explicitly*, CloudFormation's existence check sees the collision, and the deploy dies at the
> compute stack with a message that **never names the log groups**:
>
> ```
> Early validation failed for change set cdk-deploy-change-set:
>   hou-<env>-compute (AWS::CloudFormation::Stack)
>   The following hook(s)/validation failed: [AWS::EarlyValidation::ResourceExistenceCheck]
> ```
>
> ```bash
> E=val2   # your -c env= value
> aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/hou-$E" \
>   --query 'logGroups[].logGroupName' --output text | tr '\t' '\n' \
>   | xargs -r -n1 -I{} aws logs delete-log-group --log-group-name {}
> ```
>
> Also clear a stack left in `REVIEW_IN_PROGRESS` by the failed attempt:
> `aws cloudformation delete-stack --stack-name hou-$E-compute`.
>
> **A first-time deploy into a clean account is unaffected.** This bites on re-deploys — which is
> exactly what an evaluating SA does. Diagnosed on a live redeploy 2026-07-28 (`hou-val2`); 11
> leftover log groups blocked it, and deleting them let all 7 stacks deploy in 530s.
> The teardown section below now removes them so the next deploy is clean.

## 1. Prerequisites
- **Account/org:** a dedicated sandbox or pilot account (one PHA per account — no multi-tenancy);
  Control Tower/SCPs must allow: CloudFormation, Lambda, DynamoDB, S3 (+Object Lock), Step Functions,
  Cognito, Secrets Manager, SNS, CloudWatch, Comprehend, Bedrock (model access enabled for the
  configured Claude model), Bedrock AgentCore (for the gateway attachment).
- **Region:** any Region with Bedrock AgentCore + the chosen model (validated in us-east-1).
- **Quotas:** default quotas suffice for a pilot (≤ 13 Lambdas, 1 state machine, 4 DynamoDB tables
  — audit ledger, sanitized artifacts, case store, pending approvals — 1 bucket).
- **Tooling:** Node 18+, `npx --yes aws-cdk@2` (or `npm i -g aws-cdk`; without `--yes` npx stops at an interactive install prompt and hangs silently), Python 3.12, `pip install -r cdk/requirements.txt`.
- **Deployment role:** CloudFormation service-role pattern; least-privilege statement list in
  `cdk/README.md` (or use CDK bootstrap's deploy role). `npx --yes aws-cdk@2 bootstrap aws://<acct>/<region>` once.

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
git checkout v0.9.5        # always deploy a validated release tag, never main
cd cdk && pip install -r requirements.txt
npx --yes aws-cdk@2 deploy --all --require-approval never -c env=pilot -c retention_profile=pilot -c kms=customer-managed \
  -c network_mode=private -c identity_mode=pilot -c tenant=<pha-id>
```
`--all` includes EVERYTHING — the AgentCore Gateway/Cedar attachment (`hou-<env>-gateway`) deploys
as IaC with the rest; there are no post-deployment shell steps (see the stack table in
`cdk/README.md`).
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
{"deployment_status":"PASS","release":"<tag>","stacks":"COMPLETE","secrets":"PRESENT",
 "masking_control":"PASS","guard_genuine":"PASS","forged_ref_denied":"PASS",
 "ingest_pass_by_reference":"PASS","workflow_fail_closed":"PASS",
 "hud_lookup":"CONFIGURED|NOT-CONFIGURED (fail-closed to ManualReview)"}
```
Any FAIL blocks the pilot. Attach the JSON to the deployment record. For INDEPENDENT verification,
run the GitHub-OIDC release-validation workflow (`.github/workflows/release-validation.yml`) instead
of trusting a local run.

## 5. Run a case (operator flow — pass-by-reference)

Raw applicant content never enters Step Functions state: it goes in ONCE through the ingest Lambda,
and only an opaque `case_ref` starts the workflow.

```bash
P=hou-pilot; R=us-east-1
# 1. INGEST the application (the only door for raw content; response is content-free)
aws lambda invoke --function-name $P-ingest-case --region $R \
  --cli-binary-format raw-in-base64-out \
  --payload '{"case_id":"HOU-2026-0001","application":"<raw application text>"}' /tmp/ing.json
CASE_REF=$(python -c "import json;print(json.load(open('/tmp/ing.json'))['case_ref'])")

# 2. START the governed workflow with the REF (never the text)
aws stepfunctions start-execution --region $R \
  --state-machine-arn arn:aws:states:$R:<acct>:stateMachine:$P-determination-workflow \
  --name hou-2026-0001 \
  --input "{\"case_id\":\"HOU-2026-0001\",\"requester\":\"<intake-operator>\",\"case_ref\":\"$CASE_REF\"}"

# 3. The pipeline pauses at HumanSignoff (~1 min). The housing specialist reviews:
aws dynamodb get-item --table-name $P-pending-approvals --region $R \
  --key '{"case_id":{"S":"HOU-2026-0001"}}'          # -> task_token + content_hash
#    - the DRAFT NOTICE is in the case store under the draft step's notice_ref (execution history
#      shows the ref; fetch: aws dynamodb get-item --table-name $P-case-store --key '{"case_ref":{"S":"<notice_ref>"}}')
#    - the assessment (non-PII) is in the execution history AssessRules output

# 4. A DIFFERENT person than the requester APPROVES (content_hash binds the approval to what they saw)
aws stepfunctions send-task-success --region $R --task-token "<task_token>" \
  --task-output '{"approved":true,"decision":"APPROVE","approver":"<specialist>","content_hash":"<content_hash>","case_id":"HOU-2026-0001"}'

# 5. Finalize runs EXACTLY ONCE; verify the committed record + marker:
aws dynamodb get-item --table-name $P-audit-ledger --region $R \
  --key '{"audit_id":{"S":"FINAL#HOU-2026-0001"}}'
```

A rejected case: send `"approved":false,"decision":"REJECT"` — nothing commits. A case the guards
refuse (unverifiable HUD data, unproven masking) never reaches the gate: it ends in `ManualReview`
for ordinary human processing. Synthetic test cases with expected results: `data/synthetic/`.

## 6. Operate
Subscribe ops to the `hou-<env>-ops-alarms` SNS topic; dashboard `hou-<env>-operations`. Runbooks:
`docs/THREAT-MODEL.md` (security events), `docs/DATA-SOURCE-POLICY.md` (HUD outage → NEEDS_REVIEW),
`docs/RETENTION-PROFILES.md` (retention/break-glass).

## 7. Upgrade / rollback / uninstall
- **Upgrade:** deploy a NEW tagged release via `cdk deploy` (change-sets are reviewable); never patch in place.
- **Rollback:** redeploy the previous tag (stateless compute; data stacks are additive).
- **Uninstall:** stop any executions parked at the human sign-off gate first (a RUNNING execution
  blocks state-machine deletion and the destroy stalls), then
  `npx --yes aws-cdk@2 destroy --all --force`, then delete the RETAIN'd audit table + WORM vault
  **only per the customer's records-disposition procedure**, then run the residual-resource check:
  `python scripts/validate_deployment.py --env pilot --expect-absent`.

  **Also delete the log groups** — `destroy` leaves them, and they will block the *next* deploy that
  reuses the same `-c env=` value (see the warning at the top of this guide):

  ```bash
  E=pilot
  aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/hou-$E" \
    --query 'logGroups[].logGroupName' --output text | tr '\t' '\n' \
    | xargs -r -n1 -I{} aws logs delete-log-group --log-group-name {}
  ```

  Then sweep every resource type, not just stacks — an empty `describe-stacks` is **not** proof of
  zero residual (verified `hou-val2`, 2026-07-28).

## 8. Troubleshooting
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
