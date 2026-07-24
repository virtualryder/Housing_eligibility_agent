# Housing Eligibility Agent — Production-Grade Build Plan

*Living plan. Chosen as the portfolio's lead agent to take from **Demonstrated** → **Pilot-ready** → **Operational-pilot**. This file is updated at the end of **every** work cycle (status column + changelog at the bottom). It is written to be read by four audiences at once: a customer **CIO** (ROI, deployability), a **CISO** (security, evidence), an **AWS Solution Architect** (IaC, operability), and the **customer program owner** (scope honesty). It builds directly from the external ChatGPT deep-review and its P0/P1/P2 remediation list.*

> **Readiness labels used throughout** (do not blur them): **Demonstrated** = control works in a sandbox · **Pilot-ready** = safe for a scoped, human-supervised customer workflow · **Operational-pilot** = integrated, observed, recoverable, IdP-federated, run under a defined operating model. **Production** (validated SoR integration, ATO, CSV, pen-test) is explicitly **out of scope** for this build and is tracked as Phase 2.

## 0. Where we are, honestly

The agent is a **Demonstrated** governed Housing Choice Voucher (Section 8) eligibility **screening** accelerator on Amazon Bedrock AgentCore + Cedar + a Strands agent. It is deliberately **not** an automated adjudicator: it intakes, looks up the authoritative HUD income limit, de-identifies, screens against Area Median Income, and drafts a notice; a **housing specialist** makes and commits the determination at a human sign-off gate.

**Genuine strengths (keep and harden, do not remove the honesty boundary):**

- Deny-by-default Cedar with forbid-wins policies; the agent provably cannot self-commit or self-refer fraud.
- Human separation-of-duties enforced by a Step Functions sign-off gate (approver ≠ requester, single-use token).
- A fork-proof, append-only, hash-chained **WORM** audit ledger written by server-authoritative atomic compare-and-swap.
- **Authoritative-source integrity already solved**: HUD income limits are HMAC-signed by the only component that reached the real API; unverified numbers route to `NEEDS_REVIEW`, never fabricated (`lib/controls/provenance.py`). This is the pattern we extend to close the biggest remaining gap.

**Load-bearing gaps that block a credible pilot (this plan closes them):** the de-identification gate is a spoofable model-supplied `deidentified: true` boolean; the workflow is model-orchestrated rather than a deterministic controller; the user's bearer token is surfaced as a model-visible tool argument; deployment is imperative shell (no reviewable IaC); Object Lock is GOVERNANCE/1-day; default `ChangeMe-*` credentials ship; and there is no tagged release with captured validation evidence.

## 1. Operating rules for every cycle (non-negotiable)

1. **Green before done.** Every change ships with a test (unit / policy / eval / integration) and the offline suite must pass. No task is marked complete on a red or partial suite. CI gates below.
2. **Docs move with code.** The README, the SA runbook, and the relevant runbook are updated in the **same** cycle as the change that affects them. Drift is a defect.
3. **Evidence is a deliverable.** Consequential changes (a deployed run, a control proof) are captured in `evidence/` and referenced from `VALIDATED_RELEASE.md` — commit SHA, region, date, teardown, trace IDs. Never fabricate; stage deploy-dependent proofs in the runbook until captured.
4. **Four-lens check.** Each item states what it answers for the CIO, CISO, AWS SA, and customer program owner.
5. **Honesty boundary is load-bearing.** We strengthen disclaimers, never delete them. Scope stays "screening + lookup + draft," not "automated eligibility adjudication."

## 2. Phase P0 — to Pilot-ready (blocks putting it in front of a customer)

Traceability: each maps to a ChatGPT P0 item.

### P0-1 · Replace the `deidentified` boolean with a server-issued sanitized-artifact reference  *(the single most important fix)*
- **Problem.** Cedar and every downstream tool authorize on `context.input.deidentified == true`, a flag the model/caller supplies. `{"case":"unmasked…","deidentified":true}` bypasses masking.
- **Fix.** `mask_pii` writes the sanitized payload to a server-controlled store and returns a **signed `sanitized_ref`** `{artifact_id, sanitized_sha256, engine, version, ts, tenant, entity_count, sig}` (HMAC via the existing `PROVENANCE_SECRET`, extending `lib/controls/provenance.py`). Downstream tools accept **only** `sanitized_ref` (never raw `case` + boolean), verify the signature fail-closed, load sanitized content by `artifact_id`, and confirm the hash. Raw content never re-enters the model. Cedar keeps a coarse defense-in-depth forbid; the authoritative gate is the server-side signature verification.
- **Test gate.** Unit tests: valid ref passes; forged/absent/tampered ref → deny; hash-mismatch → deny; raw-case-without-ref → deny. Red-team case: spoofed `deidentified:true` no longer works.
- **IaC.** New DynamoDB `sanitized-artifacts` table (short TTL) provisioned by CDK (P0-5) with `PutItem`-only + `GetItem` least-privilege.
- **Docs.** README security section + SA runbook "de-identification" subsection rewritten to describe artifact provenance.
- **Lenses.** CISO: closes the top technical objection. SA: clean trust boundary. CIO/owner: masking is provable, not asserted.

### P0-2 · Put the regulated workflow under a deterministic controller
- **Problem.** Ordering (intake→lookup→mask→assess→draft→audit→sign-off) is a model prompt ("sensible order"), not machine-verified.
- **Fix.** A Step Functions **STANDARD** state machine drives the pipeline: `RECEIVED → EXTRACTED → AUTHORITATIVE_DATA_VERIFIED → DEIDENTIFIED → RULES_EXECUTED → DRAFT_CREATED → REVIEW_PENDING → HUMAN_APPROVED → COMMITTED`. Each transition requires machine-verifiable evidence (e.g. a valid `sanitized_ref`, a verified provenance token). The LLM operates **inside** bounded steps (extraction, drafting) but does not choose the compliance sequence.
- **Test gate.** ASL validated; a state-machine local test (Step Functions Local in CI) proving a skipped/out-of-order step fails closed; each guard has a unit test.
- **IaC.** CDK-defined state machine + IAM.
- **Lenses.** CISO/SA: "is the workflow deterministic or model-directed?" answered correctly. CIO: predictable, auditable process.

### P0-3 · Remove the access token from model-visible tool arguments
- **Problem.** `request_signoff` takes `access_token` as a declared tool input the model constructs.
- **Fix.** Derive the principal at the trusted gateway/runtime boundary; pass only trusted principal context to the approval service. The model never handles a bearer token. Add a redaction assertion that no tool schema contains a token field.
- **Test gate.** Schema test: no `access_token`/token fields in any `mcp_tools` input; identity-derivation unit test; trace-redaction test (P0-9).
- **Lenses.** CISO: eliminates a token-in-trace/audit surface.

### P0-4 · Authoritative-source failure returns MANUAL REVIEW, never fallback adjudication
- **Problem.** "Degrades gracefully" language could read as availability over correctness.
- **Status.** Already largely implemented (unsigned/absent HUD limits → `NEEDS_REVIEW`). **Action:** formalize a written **data-source policy** (required/optional, max staleness, cache rules, provenance, failure behavior, discrepancy handling, override, evidence shown) and add a test that a source-down path can never emit an authoritative determination.
- **Lenses.** CISO/owner: correctness precedence is documented and tested.

### P0-5 · Move primary deployment to CDK (in-repo), retire shell as the customer path
- **Problem.** Deployment is `deploy.sh` + broad admin CLI in `us-east-1`.
- **Fix.** AWS **CDK** (in this repo) provisioning: explicit IAM roles + resource policies, parameterized region, dev/test/prod context, customer-managed KMS option, VPC/endpoint option, tags/cost allocation, retention config, removal policies. Shell stays as an internal reference only, clearly labeled. Synthesize + `cdk diff` in CI.
- **Test gate.** `cdk synth` clean in CI; cfn-nag/cdk-nag scan; a deployable dev stack.
- **Lenses.** SA: reviewable plans, Control Tower-compatible. CISO: explicit IAM. CIO: repeatable.

### P0-6 · Remove default users/passwords from production paths
- **Fix.** No `ChangeMe-*` in any prod deploy path; Cognito users created only in a clearly-labeled sandbox module; production expects federated IdP (P1). Secrets via Secrets Manager.
- **Test gate.** Grep/CI check fails if a default password appears outside the sandbox fixture.

### P0-7 · Exact IAM resource references; eliminate role lookup by name prefix
- **Fix.** `_obs_setup.sh`'s `starts_with(RoleName,'AmazonBedrockAgentCoreSDKRuntime')` replaced by resolving exact role ARNs from deployment (CDK) outputs.
- **Test gate.** No `list-roles … starts_with` in deploy paths; obs wiring reads a stack output.

### P0-8 · Threat model
- **Fix.** `docs/THREAT-MODEL.md` covering prompt injection, token misuse, PII leakage, approval bypass, external-API poisoning, replay — with the control that mitigates each and its test.
- **Lenses.** CISO: the artifact they will ask for first.

### P0-9 · Log/trace redaction tests
- **Fix.** Tests proving raw PII and bearer tokens never enter CloudWatch/X-Ray spans or the audit payload; telemetry redaction before export.
- **Test gate.** Redaction unit tests in CI.

### P0-10 · Narrow the pilot to one program + jurisdiction; mark unimplemented connectors as stubs
- **Fix.** A `PILOT-SCOPE.md`: one PHA / one program (HCV income screening) / one income-limit year; EIV/PIC/HMIS explicitly stubbed; "screening + draft," not adjudication.
- **Lenses.** GTM/owner: a real, bounded pilot outcome.

### P0-11 · Publish an immutable tagged release with validation evidence
- **Fix.** `VALIDATED_RELEASE.md` + a git tag; captured clean-account run (SHA, region, date, duration, test results, trace IDs, teardown, residual-resource scan).

### P0-12 · Object Lock: configurable retention + COMPLIANCE option (also a P1 theme)
- **Fix.** Replace GOVERNANCE/1-day with a configurable retention profile; provide a COMPLIANCE-mode reference and a documented break-glass procedure. (Full retention-profile work continues in P1.)

## 3. Phase P1 — to Operational-pilot

- **P1-1 Enterprise IdP federation + MFA** (Okta/Entra/Ping): Cognito federation, short sessions, group→Cedar-role sync, token revocation; retire sandbox users.
- **P1-2 Customer-managed KMS** across DynamoDB, S3 WORM, logs; key policy separates admin from usage.
- **P1-3 Multi-account reference architecture**: dev/test/prod, Control Tower landing-zone compatibility, dedicated logging/archive account for the audit vault.
- **P1-4 Private networking + controlled egress**: private subnets, VPC endpoints/PrivateLink, egress allow-list (HUD USER + Bedrock only) via Network Firewall, TLS policy; the external HUD dependency becomes a *governed* dependency (allow-list, TLS verify, timeouts, retries, circuit breaker, response-size + schema + content-type validation, rate limits, provenance, poisoned-response controls, freshness).
- **P1-5 Production observability**: CloudWatch dashboards (deployment health, security, model quality, business KPI) + alarms (PII-masking failure, authz denial, authoritative-source failure, approval backlog, workflow-stuck, audit-write failure, token/inference cost) + SLOs/error budgets + on-call + runbooks linked to alarms + correlation IDs end-to-end.
- **P1-6 Exactly-once commit + replay protection**: approval-token expiry, approval-after-case-modification rejection, idempotent commit, partial-failure recovery (S3-ok/DDB-fail and inverse).
- **P1-7 Configurable records-retention profiles** (finish P0-12): state housing records-management schedules, legal hold, disposition, cross-account archive, periodic chain verification, signed verification reports.
- **P1-8 Load / chaos / concurrency / recovery tests**: concurrency + race on approval, duplicate requests, external-API rate-limit + timeout, Step Functions/model timeout, RPO/RTO, tenant isolation.
- **P1-9 Model evaluation corpus** with domain-expert labels (AMI categorization + notice quality) + reviewer-agreement study; disparate-impact check for the screening step.
- **P1-10 Rules-version management + effective dates**; human-override capture + reason codes.
- **P1-11 Release promotion + rollback pipeline**; **P1-12 supply-chain hardening**: CodeQL/SAST, secret scanning + push protection, container + IaC scanning, signed commits/images, build provenance/SBOM signing, protected branches + CODEOWNERS.

## 4. Phase P2 — to Production (tracked, out of scope this build)

Validated SoR integrations (EIV/PIC/HMIS); formal customer domain-rule approval; legal/regulatory review; ATO / customer risk acceptance; independent pen-test; operational ownership + IR exercises; privacy impact assessment; bias/fairness assessment; rules change-control board; BC/DR + regional-failure design.

## 5. Test strategy & CI gates (enforced every cycle)

- **Offline unit/policy/eval** (`pytest tests/ -q`) — must be green; add **Cedar policy property tests** and **Step Functions Local** workflow tests (new).
- **Security scans blocking**: bandit + detect-secrets against committed baselines; `pip-audit`; **cdk-nag / cfn-nag** on synth; CodeQL (P1).
- **Redaction tests** (P0-9), **schema tests** (no token fields, P0-3), **default-cred guard** (P0-6), **IaC synth** (P0-5).
- **E2E**: opt-in live deploy→prove→destroy, capturing evidence to `evidence/`.

## 6. IaC plan (CDK, in-repo)

`cdk/` (Python CDK to match the Lambda stack): stacks for **Identity** (Cognito/federation), **Data** (DynamoDB audit + sanitized-artifacts + S3 WORM w/ configurable Object Lock + KMS), **Compute** (tool Lambdas + runtime), **Workflow** (Step Functions controller + sign-off), **Gateway/Policy** (AgentCore engine/gateway/targets + Cedar), **Observability** (dashboards/alarms), **Network** (VPC/endpoints/egress firewall — P1). Context-parameterized dev/test/prod; `cdk synth`+`cdk diff`+`cdk-nag` in CI. Shell engine retained as labeled internal reference.

## 7. Traceability to the ChatGPT review

P0-1↔"deidentified artifact", P0-2↔"deterministic controller", P0-3↔"token as arg", P0-4↔"fallback→manual review", P0-5↔"CDK", P0-6↔"default creds", P0-7↔"role by prefix", P0-8↔"threat model", P0-9↔"redaction tests", P0-10↔"narrow pilot", P0-11↔"tagged release + evidence", P0-12/P1-7↔"Object Lock retention". P1 items map to the review's P1 list; P2 to its P2 list.

## 7b. Review-2 gap closure — the road to a real pilot (2026-07-24)

*The second external review approved a controlled, non-production pilot "after several final
deployment and operational items" and scored pilot-readiness 7.5/10. Every claim was verified against
the repo (all accurate). Items are organized as three GATES; nothing advances past a gate until its
items are green. Wording rule from the review, adopted permanently: this is an **"HCV preliminary
income-screening and determination-drafting assistant"** — never an "eligibility adjudication
platform."*

### Gate A — before a synthetic-data / retrospective customer pilot (current work)

| # | Item | Status |
|---|---|---|
| A1 | **Full AgentCore/Gateway/Cedar path in CDK** (runtime, gateway, targets, policy store, ENFORCE, guardrail, observability wiring) + assertions (all tools attached, policies loaded, ENFORCE on, no public endpoint, exact ARNs) | ☐ the big one — next build |
| A2 | **Secrets Manager** for signing secret + HUD token (no plaintext in context/CFN/env; least-privilege grants; CloudTrail-visible reads; rotation via version) | ✅ **DONE** — `SigningSecret` + `HudTokenSecret` in CDK, ARN-based resolution cached + fail-closed (`provenance._secret`, `lookup_income_limit._resolve_token`), tests `test_secrets_path.py` + template assertion (no plaintext). Follow-on: separate keys per trust domain (deid vs HUD) |
| A3 | **Adversarial audit-transaction proof** (TransactWriteItems cannot overwrite; every Put conditioned) | ✅ **DONE** — `test_audit_chain.py` +2 adversarial tests (was already enforced in code; now proven) |
| A4 | **Live end-to-end happy path** with a real HUD token: authn → runtime → gateway → Cedar allow + outsider deny → forged-masking deny → live HUD + provenance → assess → draft → WORM → SoD approve → single finalize → chain verify → teardown | ☐ requires A1 + a HUD USER token (owner registers at huduser.gov; store in `hou-<env>/hud-api-token` secret) |
| A5 | **Idempotent finalization + duplicate/replay protections** (duplicate submission, double approval, approval-after-change, expired approval, retried Lambda, audit-ok/finalize-fail recovery) | ☐ design exists (single-use sign-off token); needs implementation + tests |
| A6 | **Minimum CloudWatch dashboards + alarms** as a CDK ObservabilityStack (security denies, forged refs, workflow stuck/failed, approval age, manual-review rate, audit-write failure, HUD availability, DLQ) | ☐ port the portfolio security-alarms pattern into CDK |
| A7 | **DEPLOYMENT-GUIDE.md (CDK-only)** — prerequisites, quotas, deployment-role IAM, bootstrap, config matrix, secrets setup, IdP procedure, post-deploy validation script emitting the PASS/FAIL JSON, rollback/upgrade/uninstall, troubleshooting, time + cost | ☐ |
| A8 | **Formal GitHub Release** for the validated tag (source archive, SBOM, checksums, validation evidence, known limitations, changelog) — a tag alone is not a release package | ☐ |
| A9 | **Cedar policy property tests** (deny-by-default for every tool, role×tool matrix, agent-cannot-finalize, requester-cannot-approve, forbid-overrides-permit, new-tool-fails-CI-until-authorized) | ☐ |
| A10 | **cdk-nag + CodeQL/Bandit + secret scanning + push protection + branch protection + CODEOWNERS** in CI | ☐ |
| A11 | **Customer configuration worksheet + synthetic test dataset with expected results** | ☐ |
| A12 | **Pilot support/ownership statement** (who operates, who escalates, exact pilot architecture) | ☐ |

### Gate B — before real applicant PII (unchanged from P1, now ordered)

Enterprise IdP federation + MFA (phishing-resistant) · private networking + egress control (VPC,
endpoints, Network Firewall, HUD allowlist, WAF, throttling) · customer-managed KMS · **telemetry
PII-leak canary** (unique fake-PII marker traced through every telemetry destination incl. Step
Functions history, X-Ray, Bedrock logs, DLQs) · privacy impact assessment · customer security review ·
customer-approved retention schedule (never assert 7y as universal) · access review + IR procedure +
backup/recovery validation · load/concurrency/replay testing · PHA administrative-plan review ·
accessibility review of notices · written data-processing responsibilities · **tenant isolation**:
tenant derived from authenticated identity (never request body), tenant-keyed storage/audit, Cedar
tenant conditions — until then, one PHA per isolated AWS environment, no SaaS multi-tenancy claims.

### Gate C — before production

Validated EIV/PIC/HMIS integration · PHA-approved full rules configuration · legal/policy review ·
independent pen-test · ATO/StateRAMP · production ops model + SLOs · multi-account + DR ·
exactly-once processing · model-risk + fairness/adverse-impact review · change control ·
evidence-of-record completeness (every finalized case records: release tag, commit, model id,
prompt/guardrail/rules/policy/masking versions, HUD year + provenance, input + artifact hashes,
requester/approver, correlation id) · release-promotion/rollback pipeline · vulnerability management ·
training + SOPs.

### Adopted framing (use verbatim in every deck)

> "This is a governed regulated-workflow accelerator demonstrating how Amazon Bedrock AgentCore,
> deterministic rules, Cedar authorization, authoritative data, tamper-evident evidence and human
> approval can be combined for high-consequence public-sector workflows."

And for the CIO's "why is an LLM needed" question: *"It is not, for the deterministic portions. The
LLM is used only where language generation or interpretation adds value; the eligibility calculation
remains deterministic."*

## 8. Changelog

- *(cycle 1)* Plan created; agent selected (Housing) after four-repo audit; decisions locked: CDK in-repo, P0+P1 → operational-pilot. Next: execute P0-1 (sanitized-artifact) with tests.
- *(cycle 2)* **P0-1 COMPLETE (offline-proven).** New `lib/controls/sanitized.py`: mask_pii now mints a signed `sanitized_ref` (HMAC over {artifact_id, sanitized_sha256, engine, entities_masked, tenant, ts} via PROVENANCE_SECRET) with an optional server-side artifact store (SANITIZED_TABLE; CDK will provision). assess / recertify / detect_overpayment / draft_notice now authorize ONLY on the verified ref — the `deidentified` boolean is retained solely as the coarse Cedar gate and is never accepted as proof. draft_notice additionally hash-binds the case text to the signed artifact (substituted/unmasked content refused) and prefers the server-side content channel. Manifest schemas + workflow steps updated. Tests: full suite **74/74 green**, including the review's exact attack (`deidentified:true` + unmasked case -> refused), forged/tampered refs, content-substitution at draft, and mask_pii ref-mint. redteam.sh check D annotated (now blocks at the P0-1 gate). Cost-hygiene sweep of the AWS account run (zero billable compute; 7 orphaned Cognito pools deleted). Live clean-account validation deploy is staged for the CDK cycle (P0-5 -> P0-11) so evidence is captured against the customer deployment path, not the legacy shell path. Next: P0-3 (remove token-as-tool-arg) then P0-2 (deterministic controller).
- *(cycle 3)* **P0-2 through P0-10 + P0-12 COMPLETE (offline-proven; suite 97/97).**
  **P0-3:** `lib/runtime/token_boundary.py` — no tool schema declares a credential; credential-shaped
  args scrubbed from every MCP call; runtime-held token injected out-of-band into sign-off only;
  audit-payload + state-machine-input redaction proven. **P0-2:** deterministic Step Functions
  controller (CDK WorkflowStack) with `lib/controls/workflow_guards.py` machine-verifiable transitions
  (extracted / authoritative-signature / sanitized_ref / rules) — unverified evidence routes to
  ManualReview; happy-path state sequence + fail-closed choices asserted by walking the synthesized
  ASL. **P0-5/P0-7:** in-repo Python CDK (data / compute / workflow / identity stacks): explicit
  least-privilege IAM + tamper Deny, exact-ARN CfnOutputs, `_obs_setup.sh` now REFUSES prefix
  discovery and requires the exact role ARN. **P0-6:** identity stack ships zero users/passwords;
  `deploy_identity.sh` refuses `ChangeMe-*` without an explicit `SANDBOX_IDENTITY=1` acknowledgment.
  **P0-4:** `docs/DATA-SOURCE-POLICY.md` (+ existing source-down tests). **P0-8:**
  `docs/THREAT-MODEL.md` (10 threats → controls → proofs). **P0-9:** redaction tests in
  `tests/test_token_boundary.py`. **P0-10:** `PILOT-SCOPE.md`. **P0-12:** retention PROFILES
  (sandbox/pilot/production-reference COMPLIANCE 7y) in CDK + deploy-env overrides +
  `docs/RETENTION-PROFILES.md`. CI now installs aws-cdk-lib and runs the CDK assertion tests.
  **P0-11 remaining:** `VALIDATED_RELEASE.md` template landed; the git tag + captured clean-account
  deploy→prove→destroy run (with teardown + residual scan, per the account rules) is the next cycle —
  the only P0 item that requires touching AWS. After that: ChatGPT re-review, then P1.
- *(cycle 4)* **P0-11 COMPLETE — live clean-account validation captured (evidence/P0-11-VALIDATION-RUN.md).**
  CDK-synthesized stacks deployed to the sandbox account (all CREATE_COMPLETE), the P0-1 control proven
  IN THE CLOUD (real Comprehend masking; signed ref verifies; forged/spoofed/mutated refs refused), the
  P0-2 controller proven IN THE CLOUD (fail-closed ManualReview on unverifiable HUD data). The run
  surfaced a real defect (brittle guard JSONPath on source-down lookup → States.Runtime) which was
  fixed + regression-tested (suite 98/98). Full teardown verified: stacks deleted, RETAIN'd sandbox
  resources removed, residual sweep clean. Owner action remaining: commit + `git tag v0.9.0-pilot-rc1`.
  **ALL 12 P0 ITEMS CLOSED. The repo is ready for the ChatGPT re-review, then Phase P1.**
