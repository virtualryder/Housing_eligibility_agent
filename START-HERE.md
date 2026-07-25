# START HERE — Governed HCV Intake & Preliminary Income-Screening Accelerator

*One page. What this is, what's proven, how to evaluate it, and what a pilot engagement looks like.
Current validated release: **[`v0.9.4`](https://github.com/virtualryder/Housing_eligibility_agent/releases/tag/v0.9.4)**
(deploy tags, never `main`). Supported deployment path: **AWS CDK** (`cdk/`); the shell engine is
legacy/internal.*

## What this is (and is not)

A **governed AI accelerator** for Housing Choice Voucher (Section 8) intake and **preliminary
income screening**: it extracts decision fields, fetches the authoritative HUD income limit with a
cryptographically verified provenance chain, de-identifies PII with *proof* of masking, computes the
AMI category deterministically, drafts a determination notice with a guarded model, and **stops at a
human sign-off gate** — a housing specialist makes and commits every determination, exactly once.

It is **not** an eligibility adjudication system. Household composition, citizenship, criminal
history, assets/deductions, preferences, waiting lists, VAWA, hearings, EIV — the full 24 CFR
admission rulebook — remain PHA-owned and are out of scope ([`PILOT-SCOPE.md`](PILOT-SCOPE.md)).

## Evidence provenance — read this honestly

All validation evidence in this repository (three live clean-account runs, the strict PII canary,
concurrency/replay proofs) was **produced by the project itself**, captured and committed with dates,
commit SHAs, and teardown verification. It has **not yet been independently certified** — no
third-party penetration test, and no deployment reproduced by someone other than the author. The
reproducibility gap has a shipped answer awaiting its first run: the **GitHub-OIDC release-validation
workflow** ([`.github/workflows/release-validation.yml`](.github/workflows/release-validation.yml))
deploys a tag into a clean account and publishes the verdict under a run ID no one can fabricate.

## Reading order by role

| You are | Read, in order |
|---|---|
| **Solution Architect / deployer** | [`DEPLOYMENT-GUIDE.md`](DEPLOYMENT-GUIDE.md) → [`cdk/README.md`](cdk/README.md) → [`CONFIG-WORKSHEET.md`](CONFIG-WORKSHEET.md) → `docs/Housing-AgentCore-SA-Runbook.docx` §0 |
| **CISO / security reviewer** | [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md) → [`evidence/GATE-B-VALIDATION.md`](evidence/GATE-B-VALIDATION.md) → [`docs/KEY-MANAGEMENT.md`](docs/KEY-MANAGEMENT.md) → [`docs/GATE-B-CHECKLIST.md`](docs/GATE-B-CHECKLIST.md) → [`SECURITY.md`](SECURITY.md) |
| **CIO / program owner** | [`README.md`](README.md) §Validated-evidence + §Known-open-issues → [`PILOT-SCOPE.md`](PILOT-SCOPE.md) → [`docs/Cost-and-Latency-One-Pager.md`](docs/Cost-and-Latency-One-Pager.md) → the pilot offer below |
| **Auditor / regulator** | [`VALIDATED_RELEASE.md`](VALIDATED_RELEASE.md) → [`evidence/`](evidence/) → `docs/Housing-AgentCore-Regulatory-Adherence.docx` → [`docs/RETENTION-PROFILES.md`](docs/RETENTION-PROFILES.md) |
| **AWS leadership / GTM** | `docs/Housing-AgentCore-Leadership.pptx` → `docs/Housing-AgentCore-Customer.pptx` → [`PRODUCTION-PLAN.md`](PRODUCTION-PLAN.md) §7b |

What's proven vs. not, in one table: **README → "What is actually validated vs. what is not."**
Open items, honestly stated: **README → "Known open issues."**

## The pilot offer (repeatable engagement)

**Scope:** one PHA · one program · one HUD income-limit year · synthetic or retrospective
de-identified cases first, then shadow mode · every determination human-approved · no autonomous
denial, termination, or fraud referral — ever (Cedar-forbidden, not just policy).

| Phase | Duration | What happens |
|---|---|---|
| 1. Workshop | ~1 week | Architecture + captured-evidence walkthrough with program, privacy, and security teams; scope + metrics agreed |
| 2. Deploy + validate | ~1 week | CDK deploy of the tagged release into the PHA's account (full Gate-B switches); machine validation verdict + strict PII canary + allow/deny tests, captured |
| 3. Scoped pilot | 4–6 weeks | Synthetic → retrospective → shadow-mode cases through the governed workflow; weekly metric reviews (handling time, draft edit rate, AMI agreement, manual-review rate, overrides + reasons) |
| 4. Production scoping | joint | What real integration (EIV/PIC/HMIS), identity, rules configuration, and authorization-to-operate would require |

**Customer provides:** an AWS account (Control Tower-compatible), a huduser.gov API token, an IdP
admin for federation, a named program owner + 2–3 housing specialists for review sessions, privacy/
security review participation, and (shadow phase) retrospective de-identified cases.

**Estimated professional-services effort:** deploy + validate ≈ 3–5 SA-days; pilot operation ≈ 1–2
SA-days/week; IdP federation ≈ 2–4 days with the customer's identity team. System-of-record
integration is deliberately EXCLUDED from the pilot (shadow mode reads nothing and writes nothing
into the official case record) and is the dominant cost of any production phase.

**Success gates:** zero consequential security bypasses · zero PII in telemetry (strict canary) ·
~100% AMI-calculation agreement on approved test cases · zero duplicate finalizations · measured
(not assumed) staff-time and draft-quality deltas · a written go/no-go production business case.

## Current status in one line

Gate A (synthetic-data pilot prerequisites): **complete, live-validated.** Gate B engineering
(private networking, CMK, MFA identity, tenant pinning, zero-PII orchestration, key management,
security metrics): **complete, live-validated.** Remaining before real applicant PII: **customer-side
items** — IdP round-trip, governance signatures (PIA/retention/IR/access review/backup exercise),
independent security testing, and the first independent deployment run. Production additionally
requires system-of-record integration, multi-account evidence isolation, scale/failure testing, and
authorization to operate ([`PRODUCTION-PLAN.md`](PRODUCTION-PLAN.md)).
