# Gate B — before real applicant PII (checklist + evidence map)

*Gate A proved the governed pipeline and its deployment path on synthetic data (see
[`VALIDATED_RELEASE.md`](../VALIDATED_RELEASE.md)). Gate B is the set of prerequisites that must hold
before the FIRST real applicant record enters the system. Each row names the control, where it lives,
how it is proven, and who owns it. Nothing on this page is asserted without a proof path.*

## Built into the repo (deploy-time switches + harnesses)

| # | Control | Where | Proof | Status |
|---|---|---|---|---|
| B1 | **Private networking + locked egress** — governed Lambdas in isolated subnets; ALL egress through AWS Network Firewall with a deny-by-default allowlist naming ONLY `.huduser.gov`; S3/DDB gateway + 7 interface endpoints keep AWS traffic on the AWS network; 443-only security group | `cdk/housing_stacks/network_stack.py` (`-c network_mode=private`) | CDK assertions (all functions in VPC, allowlist content, endpoint count); live leg = Gate-B validation run | ✅ built + assertion-proven |
| B2 | **Customer-managed KMS** — one CMK (rotation on) over DDB tables, WORM vault, both signing secrets + HUD token, Lambda env vars, per-function log groups, SNS ops topic | `-c kms=customer-managed` (data/compute/observability stacks) | CDK assertions (full coverage in CMK mode; zero KMS resources in default mode) | ✅ built + assertion-proven |
| B3 | **Enterprise IdP + MFA** — `identity_mode=pilot`: MFA REQUIRED (software token only, SMS disabled), Cognito threat protection ENFORCED, admin-create-only, zero IaC users; OIDC IdP attachable as IaC (client secret via Secrets Manager dynamic reference — never plaintext) | `cdk/housing_stacks/identity_stack.py` + `docs/IdP-Federation-Reference.md` | CDK assertions; federated login exercised in the Gate-B validation run | ✅ built + assertion-proven |
| B4 | **PII telemetry-leak canary** — unique fake-PII marker run through the live pipeline, then swept across CloudWatch Logs, X-Ray, Step Functions history, DLQs; `--strict` = every destination clean | `scripts/pii_canary.py` | offline verdict tests + live canary run; **known finding to remediate: SFN history carries the raw case (pass-by-reference)** | ✅ built; strict-pass pending remediation |
| B5 | **Tenant isolation** — tenant is deployment-pinned (`-c tenant=<pha-id>` → `TENANT_ID`), NEVER read from a request body; the pinned tenant is HMAC-signed into every `sanitized_ref`; verifiers refuse cross-tenant refs even with a valid signature. One PHA per isolated deployment — no SaaS multi-tenancy claims | `lib/controls/tenancy.py`, `sanitized.py`, `mask_pii.py` | unit tests (body-tenant ignored; post-mint tamper breaks the signature; cross-tenant refusal) + CDK `TENANT_ID` assertion | ✅ built + proven |
| B6 | **Load / concurrency / replay** — N concurrent executions must all reach legal terminal states; a concurrent replay storm against one approval must commit EXACTLY once (live confirmation of the GA-5 design) | `scripts/load_replay_test.py` | offline verdict tests; live run at pilot concurrency target | ✅ built; live capture pending |

## Gate-B validation run (to capture, one clean-account exercise)

Deploy with every switch on — `-c network_mode=private -c kms=customer-managed -c identity_mode=pilot
-c tenant=<pha-id> -c retention_profile=pilot` — then capture: happy path through the private/CMK
deployment; a federated + MFA login through the gateway (Cedar allow/deny on the real principal);
`pii_canary.py` (record the SFN-history finding or its remediation); `load_replay_test.py --load 25`
and a `--storm 10` replay; teardown + sweep. Evidence lands in `evidence/GATE-B-VALIDATION.md`.

## Customer-owned governance (the accelerator provides the template; the PHA signs)

These are DECISIONS AND PROCESSES, not code. The pilot cannot accept real PII until each has a named
owner and a signed date.

**Privacy impact assessment (PIA).** Data inventory for a case (applicant identity, income,
household composition — Privacy Act / state-law categories); processing purposes (screening,
drafting, audit); the de-identification boundary (what the model sees is the masked artifact — cite
the sanitized_ref control); retention per the selected profile; access (housing specialists via the
IdP, MFA-required); disclosure paths (none outside the account); applicant rights + the
informal-hearing process. Owner: PHA privacy officer. The threat model (`docs/THREAT-MODEL.md`) and
data-source policy feed sections 2–4.

**Retention approval.** The PHA formally selects and signs the Object Lock retention profile
(`docs/RETENTION-PROFILES.md`) against its records schedule — never assert 7y as universal. Owner:
PHA records officer.

**Incident response.** Trigger definitions (mask failure alarms, forged-ref attempts, canary FAIL,
unusual deny spikes on the gateway); first hour (disable the gateway client id — one Cognito call —
which stops ALL tool access; snapshot logs; preserve the WORM ledger which cannot be altered);
notification obligations per the PHA's breach policy; post-incident chain verification
(`lib/controls/verify_chain.py`). Owner: joint — PHA security + operating SA.

**Access review.** Quarterly: every member of the `housing_specialist` group re-attested by the PHA
program manager; IdP group mapping reviewed; Cognito sign-in audit (threat-protection logs) sampled.
Owner: PHA program manager.

**Backup / recovery validation.** The audit ledger has PITR + the WORM vault is versioned-immutable;
the recovery EXERCISE (restore a table to a point in time in a scratch account, replay chain
verification to INTACT) must be performed once before the pilot and captured in evidence. Owner:
operating SA.

**Remaining Gate-B engineering (tracked, not blocking the checklist's publication):**
pass-by-reference for the controller payload (the B4 canary's known finding), custom security
metrics (forged-ref count → alarm), and the PHA administrative-plan / notice-language accessibility
reviews which are customer work items.
