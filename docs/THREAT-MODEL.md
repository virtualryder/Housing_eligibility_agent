# Threat model (P0-8) — Housing eligibility agent

*Scope: the governed agent spine (AgentCore Runtime + Gateway + Cedar + tool Lambdas + Step Functions
sign-off + evidence ledger) and its external dependencies (HUD USER API, Cognito). Assets: applicant
PII, determinations, the audit ledger, reviewer credentials, HUD data integrity. Format: threat →
control(s) → proof.*

| # | Threat | Control(s) | Proof |
|---|---|---|---|
| T1 | **Prompt injection** — instructions in the application text steer the model to skip masking, exfiltrate data, or call forbidden tools | Deterministic masking (not promptable); Cedar deny-by-default + forbid-wins; consequential tools hidden + forbidden; output Guardrail (PII anonymize + prompt-attack HIGH); P0-1 sanitized-ref gate refuses unproven-masked input regardless of what the model was told | `redteam.sh` checks B/C/D (live); `test_sanitized_artifact.py` (offline) |
| T2 | **Masking bypass** — caller/model asserts data is de-identified when it is not | Server-issued signed `sanitized_ref` (proof-of-masking) + `sanitized_sha256` content binding; boolean never accepted | `test_sanitized_artifact.py::test_spoofed_deidentified_boolean_is_refused`, `::test_draft_refuses_substituted_content` |
| T3 | **Token misuse** — bearer token exposed to the model / telemetry, stolen, or replayed | P0-3 trusted runtime boundary: no token field in any tool schema; credential-shaped args scrubbed on every call; runtime injects the token out-of-band into sign-off only; Lambda re-verifies RS256/JWKS; logs record `token_present` boolean only | `test_token_boundary.py` (schema scan, scrub/inject, audit-payload redaction) |
| T4 | **Approval bypass / self-approval** — agent commits, or requester approves own case | Cedar `no_self_commit` forbid + tool hidden from agent + Lambda refusal; Step Functions `waitForTaskToken` human gate; approver ≠ requester enforced on a VERIFIED identity; single-use approval token | `test_signoff_identity.py`; `demo.sh` sign-off leg (live) |
| T5 | **Authoritative-data poisoning** — fabricated/tampered HUD limits force a wrong determination | HMAC-signed provenance minted only by the real lookup; verifier rebuilds fields from the values it will use; unverified → `NEEDS_REVIEW` | `test_provenance_gate.py` (13 cases) |
| T6 | **Audit tampering / fork** — rewrite or fork history after the fact | Server-read hash-chain head + atomic `TransactWriteItems` CAS; `attribute_not_exists` immutability; IAM Deny on update/delete/governance-bypass; WORM S3 copy; `verify_chain` replay | `test_audit_chain.py` |
| T7 | **PII in telemetry** — traces/logs become a second copy of sensitive data | Masking before model + audit; `token_present` boolean logging; P0-3 scrub keeps credentials out of tool-call telemetry; Guardrail anonymizes model output | `test_token_boundary.py` redaction tests (extend under P1-5 with span-capture tests) |
| T8 | **Fraud-referral abuse** — agent (or injected prompt) refers a household as suspected fraud | Cedar `no_self_fraud_referral` + Lambda refusal (human-only) | `test_tools.py::test_core_refer_fraud_refused` |
| T9 | **Replay / duplicate commit** — same approval or audit event applied twice | Single-use sign-off token; idempotent evidence writes (exact-replay returns stored:false-noop) | `test_audit_chain.py`; P1-6 extends with exactly-once commit tests |
| T10 | **Deployment-path compromise** — wrong role modified (prefix lookup), default creds abused | P0-7 exact-ARN role resolution (refuses discovery); P0-6 sandbox-only default-cred guard (`SANDBOX_IDENTITY=1` acknowledgment); CDK explicit IAM (P0-5) | `test_token_boundary.py::test_no_role_lookup_by_name_prefix_in_deploy_paths`; `test_p0_compliance.py` |

Residual risks (tracked, not closed): telemetry span-content capture proof on a live deploy (P1-5);
exactly-once commit under partial failure (P1-6); enterprise IdP/MFA (P1-1); pen-test (P2).
