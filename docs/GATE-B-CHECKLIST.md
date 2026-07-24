# Gate B — before real applicant PII (checklist + evidence map)

*Gate A proved the governed pipeline and its deployment path on synthetic data (see
[`VALIDATED_RELEASE.md`](../VALIDATED_RELEASE.md)). Gate B is the set of prerequisites that must hold
before the FIRST real applicant record enters the system. Each row names the control, where it lives,
how it is proven, and who owns it. Nothing on this page is asserted without a proof path.*

## Built into the repo (deploy-time switches + harnesses)

| # | Control | Where | Proof | Status |
|---|---|---|---|---|
| B1 | **Private networking + locked egress** — governed Lambdas in isolated subnets; ALL egress through AWS Network Firewall with a deny-by-default allowlist naming ONLY `.huduser.gov`; S3/DDB gateway + 7 interface endpoints keep AWS traffic on the AWS network; 443-only security group | `cdk/housing_stacks/network_stack.py` (`-c network_mode=private`) | CDK assertions + **LIVE: rule group captured (`ALLOWLIST [.huduser.gov]`), full pipeline succeeded inside the private network with the HUD call through the firewall** | ✅ **live-proven** |
| B2 | **Customer-managed KMS** — one CMK (rotation on) over DDB tables, WORM vault, both signing secrets + HUD token, Lambda env vars, per-function log groups, SNS ops topic | `-c kms=customer-managed` (data/compute/observability stacks) | CDK assertions + **LIVE: `alias/hou-valb-data` CMK deployed across all consumers; pipeline ran fully CMK-encrypted** | ✅ **live-proven** |
| B3 | **Enterprise IdP + MFA** — `identity_mode=pilot`: MFA REQUIRED (software token only, SMS disabled), Cognito threat protection ENFORCED, admin-create-only, zero IaC users; OIDC IdP attachable as IaC (client secret via Secrets Manager dynamic reference — never plaintext) | `cdk/housing_stacks/identity_stack.py` + `docs/IdP-Federation-Reference.md` | CDK assertions + **LIVE: `MfaConfiguration ON`, `SOFTWARE_TOKEN_MFA` only, `ENFORCED`, 0 users captured** (real-IdP round-trip = customer engagement work) | ✅ **live-proven** |
| B4 | **PII telemetry-leak canary** — unique fake-PII marker run through the live pipeline, then swept across CloudWatch Logs, X-Ray, Step Functions history, DLQs; `--strict` = every destination clean | `scripts/pii_canary.py` + pass-by-reference orchestration (`ingest-case` → encrypted case store → opaque refs only through the controller) | offline verdict tests + **LIVE STRICT PASS (2026-07-24): 0 hits in EVERY destination incl. SFN history** — the 87-hit finding remediated; CDK assertion pins zero-content state | ✅ **STRICT live-proven** |
| B5 | **Tenant isolation** — tenant is deployment-pinned (`-c tenant=<pha-id>` → `TENANT_ID`), NEVER read from a request body; the pinned tenant is HMAC-signed into every `sanitized_ref`; verifiers refuse cross-tenant refs even with a valid signature. One PHA per isolated deployment — no SaaS multi-tenancy claims | `lib/controls/tenancy.py`, `sanitized.py`, `mask_pii.py` | unit tests + CDK assertion + **LIVE: `tenant: pha-la-county` captured inside the signed artifact of the live run** | ✅ **live-proven** |
| B6 | **Load / concurrency / replay** — N concurrent executions must all reach legal terminal states; a concurrent replay storm against one approval must commit EXACTLY once (live confirmation of the GA-5 design) | `scripts/load_replay_test.py` | offline verdict tests + **LIVE: 10/10 concurrent SUCCEEDED; replay storm `FIRST:1, IDEMPOTENT:9`; 12 FINAL markers, one per case** | ✅ **live-proven** |

## Gate-B validation run — ✅ CAPTURED 2026-07-24

Executed with every switch on; full narrative + raw values in
[`../evidence/GATE-B-VALIDATION.md`](../evidence/GATE-B-VALIDATION.md). Deployment-order note from
the run: **deploy observability AFTER workflow** (it imports the controller's export). VPC-attached
Lambda stacks take noticeably longer to delete (ENI release) — plan teardown windows accordingly.

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

**Gate-B engineering — all closed (Review-3 cycle, 2026-07-24):** pass-by-reference orchestration
(strict canary PASS), guard-failure security metrics + alarm, key-management runbook + key-version
stamping ([`KEY-MANAGEMENT.md`](KEY-MANAGEMENT.md)), and a reproducible **GitHub-OIDC
release-validation workflow** (`.github/workflows/release-validation.yml` + one-time role setup in
`.github/setup/`) so a reviewer can independently confirm a tagged release deploys, validates, and
tears down clean — first independent run pending the validation account. Remaining items are
customer-owned: governance signatures above, PHA administrative-plan / notice-accessibility reviews,
enterprise-IdP exercise, independent security testing.
