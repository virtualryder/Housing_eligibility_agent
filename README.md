# Housing Eligibility Agent — Governed Agentic AI on Amazon Bedrock AgentCore

[![CI](https://github.com/virtualryder/Housing_eligibility_agent/actions/workflows/ci.yml/badge.svg)](https://github.com/virtualryder/Housing_eligibility_agent/actions/workflows/ci.yml)

> **SUPPORTED DEPLOYMENT PATH — read this first.** The ONE supported path is **AWS CDK at the
> validated release tag [`v0.9.2`](https://github.com/virtualryder/Housing_eligibility_agent/releases/tag/v0.9.2)**
> (`cdk/` — includes the AgentCore Gateway/Cedar attachment as IaC), per
> [`DEPLOYMENT-GUIDE.md`](DEPLOYMENT-GUIDE.md) and [`VALIDATED_RELEASE.md`](VALIDATED_RELEASE.md).
> The shell engine (`lib/engine/`) is **legacy/internal reference only** — do not deploy it for a
> customer. Product framing: this is a **governed HCV intake and preliminary income-screening
> accelerator** — it is not, and does not claim to be, a complete eligibility adjudication system.
>
> *Part of the Governed Agent Platform: also being consolidated into the [governed-agent-platform](https://github.com/virtualryder/governed-agent-platform) monorepo, where all four verticals share one versioned governance core.*

> **Continuous validation.** On every push CI runs the **governance-core integrity gate** (`lib/verify_core.py`, so the shared core must match its pinned `core.lock` and drift cannot merge unnoticed), manifest render, the unit + eval suite, and a bug-class lint, plus a **supply-chain job** that audits the pinned runtime dependencies (`pip-audit`) and emits a CycloneDX SBOM. An **opt-in** end-to-end job (`.github/workflows/e2e.yml`, manual `workflow_dispatch`) deploys the spine to a sandbox AWS account, proves it live with the demo in ENFORCE, and tears it down — see the workflow header for one-time setup.


A **governed** Housing Choice Voucher (Section 8) / public-housing eligibility agent for State & Local
Government. It intakes an application, looks up the **authoritative HUD income limit** for the
household's county, de-identifies PII, determines the income category and voucher eligibility, drafts a
determination notice, and **pauses at a human sign-off gate** — a housing specialist makes and commits
the determination; the agent never self-adjudicates. Built on the same governed-hero-agent pattern as
the pharmacovigilance, benefits, and financial-aid agents, from a reusable, manifest-driven template.

> **Accelerator, not a certification.** Reference implementation of the *pattern*. Not a
> production-certified system. Computer-system validation, IdP federation, connectors to the housing
> authority's system of record (EIV / PIC / HMIS), authoritative program rules, and the authorization
> to operate (StateRAMP / ATO) remain the adopter's responsibility. The income limits are fetched live
> from HUD; program-specific admission rules and preferences are **configuration** — set per PHA and
> program.

## Production-grade build (P0 hardening — 2026-07)

This repo is the portfolio's **lead agent** being taken to pilot-readiness under
[`PRODUCTION-PLAN.md`](PRODUCTION-PLAN.md). The following are **built and offline-proven (145 tests
green)** — and the highest-stakes claims are also **live-proven with captured evidence**, including
a full **Gate-B run with every hardening switch on** (see *Validated evidence* below) — closing the
external deep-review's P0 findings:

- **De-identification is proven, not asserted (P0-1).** `mask_pii` mints a server-signed
  `sanitized_ref` over the exact masked content; every downstream tool verifies it fail-closed and
  `draft_notice` hash-binds its input to the signed artifact. A model-supplied `deidentified: true`
  boolean is never accepted (`lib/controls/sanitized.py`, `tests/test_sanitized_artifact.py`).
- **The model never handles a bearer token (P0-3).** No tool schema declares a credential; the runtime
  scrubs credential-shaped args from every call and injects the token out-of-band into the sign-off
  call only (`lib/runtime/token_boundary.py`, `tests/test_token_boundary.py`).
- **The regulated workflow is deterministic (P0-2).** A Step Functions controller drives
  intake → verified-HUD-limits → proven-masking → rules → draft → audit → human sign-off, with a
  machine-verifiable guard between every stage; unverified evidence routes to `ManualReview`
  (`cdk/housing_stacks/workflow_stack.py`, `lib/controls/workflow_guards.py`).
- **CDK is the customer deployment path (P0-5/P0-7).** Explicit least-privilege IAM, exact-ARN
  outputs (no name discovery), parameterized envs — [`cdk/README.md`](cdk/README.md). The shell engine
  is an internal reference only.
- **No default credentials in production paths (P0-6);** configurable **audit retention profiles**
  incl. COMPLIANCE mode (P0-12, [`docs/RETENTION-PROFILES.md`](docs/RETENTION-PROFILES.md));
  **data-source policy** (correctness over availability, [`docs/DATA-SOURCE-POLICY.md`](docs/DATA-SOURCE-POLICY.md));
  **threat model** ([`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md)); **pilot scope**
  ([`PILOT-SCOPE.md`](PILOT-SCOPE.md)); captured release evidence
  ([`VALIDATED_RELEASE.md`](VALIDATED_RELEASE.md)).

### Validated evidence (live runs, captured — 2026-07)

Two clean-account validation runs, both fully torn down afterward, with the raw captures committed
under [`evidence/`](evidence/):

- **The full governed pipeline SUCCEEDED end-to-end on live services**
  ([`evidence/GA-4-LIVE-HAPPY-PATH.md`](evidence/GA-4-LIVE-HAPPY-PATH.md)): live HUD USER income-limit
  lookup with HMAC-signed provenance verified by the guard; real Comprehend masking with a Secrets
  Manager–signed `sanitized_ref`; deterministic AMI assessment; a real guarded Bedrock notice; the
  hash-chained WORM `INTENT` record; the `waitForTaskToken` human sign-off pause with a `content_hash`
  binding the approval to the exact assessment; and an **exactly-once** finalize
  (`FINAL#<case>` conditional marker). The agent never self-adjudicated.
- **The AgentCore Gateway/Cedar authorization plane deploys as pure IaC and reached
  `CREATE_COMPLETE` in `ENFORCE`** (same evidence file, addendum): the CDK `GatewayStack` custom
  resource created the Cedar policy engine, the MCP gateway (CUSTOM_JWT via the Cognito identity
  pool), all 9 manifest-synthesized tool targets on exact Lambda ARNs, and all 7 deny-by-default
  Cedar policies — then flipped to ENFORCE; stack delete reversed everything (verified zero residue).
- **Fail-closed behavior proven in the cloud**
  ([`evidence/P0-11-VALIDATION-RUN.md`](evidence/P0-11-VALIDATION-RUN.md)): forged signature / spoofed
  `deidentified:true` / mutated content all refused; a source-down HUD lookup routed to
  `ManualReview` — no determination on unverifiable data.
- **The full Gate-B hardening posture ran live, end-to-end**
  ([`evidence/GATE-B-VALIDATION.md`](evidence/GATE-B-VALIDATION.md)): governed Lambdas in **isolated
  subnets** behind an AWS Network Firewall **deny-by-default allowlist naming only `.huduser.gov`**;
  a **customer-managed KMS key** over tables, WORM vault, secrets, Lambda env, log groups, and SNS;
  **MFA-required** identity with threat protection ENFORCED; the **deployment-pinned tenant**
  HMAC-signed into the live sanitized artifact; **10/10 concurrent executions SUCCEEDED**; a 10-way
  **replay storm committed exactly once** (`FIRST:1, IDEMPOTENT:9`); and the **PII telemetry canary
  passed** — zero marker hits in CloudWatch Logs, X-Ray, and DLQs (the one known finding, Step
  Functions history, is quantified with its pass-by-reference remediation tracked).
- **Validation found real defects** — ten live findings across the runs (IAM/AgentCore API
  constraints, an orphaned-engine conflict, a CloudFormation async-invoke stall, an env-agnostic AZ
  token in the firewall routing, a stack-ordering race) — every one fixed, regression-tested, and
  documented in the evidence. That is what the validation step is for.

### What is actually validated vs. what is not

| Claim | Status |
|---|---|
| CDK deployment path incl. AgentCore Gateway/Cedar as IaC | ✅ live-validated (2×), captured evidence |
| Full governed pipeline end-to-end on live services | ✅ live-validated, incl. inside the private-network posture |
| Fail-closed controls (forged ref / spoofed boolean / source-down) | ✅ live-validated |
| Exactly-once finalize under a concurrent replay storm | ✅ live-validated (`FIRST:1, IDEMPOTENT:9`) |
| Gate-B switches (private egress, CMK, MFA identity, tenant pinning) | ✅ live-validated (one clean-account run, all on) |
| PII kept out of CloudWatch Logs / X-Ray / DLQs | ✅ live-validated (canary, 0 hits) |
| Enterprise IdP round-trip with a customer IdP | ❌ engagement work (IaC hook is assertion-proven only) |
| EIV / PIC / HMIS system-of-record integration | ❌ stubbed — adopter work |
| Independent penetration test / third-party security review | ❌ not performed |
| Multi-account governance/evidence isolation | ❌ reference architecture only |
| Business ROI (staff-time savings) | ❌ hypothesis — measured in the customer pilot |

### Known open issues (tracked, honestly)

1. ~~Step Functions execution history carries the raw case~~ — **CLOSED (2026-07-24)**:
   pass-by-reference orchestration shipped (raw content enters only via `ingest-case` into the
   encrypted case store; only opaque refs cross the controller) and the **strict PII canary passed
   live: zero marker hits in every destination including SFN history**
   ([`evidence/GATE-B-VALIDATION.md`](evidence/GATE-B-VALIDATION.md) addendum). A CDK assertion pins
   the property.
2. Provenance key lifecycle: rotation runbook + key-version stamping beyond the GA-2 domain split.
3. Load validated at 10-way concurrency; production-scale (50–100+) and partial-failure/recovery
   testing remain.
4. Customer-owned governance signatures (PIA, retention, IR, access review, backup/recovery
   exercise) pending per [`docs/GATE-B-CHECKLIST.md`](docs/GATE-B-CHECKLIST.md).

---

## Why this agent

Housing-assistance intake (Housing Choice Vouchers, public housing, project-based rental assistance) is
high-volume, waitlist-driven, and under heavy regulation (the U.S. Housing Act, 24 CFR Parts 5/960/966/982,
due-process/informal-hearing requirements, StateRAMP / NIST 800-53). It's an obvious place for an AI
agent — but a regulated housing authority cannot adopt an ungoverned one: PII must never leak, every
decision needs a tamper-evident audit, tool access must be least-privilege, and a **qualified housing
specialist must make and commit the determination**. This agent keeps the human in charge and makes the
platform enforce it.

## The governed workflow

```
intake_application -> lookup_income_limit -> mask_pii -> assess_housing_eligibility -> draft_notice -> write_audit -> request_signoff
   (HUD USER API, non-PII, before masking)                                                                              |
                                                            housing specialist (a DIFFERENT person) approves -> finalize
```

- **intake_application** — extract the non-PII decision fields (household size, annual income, county
  FIPS/entityid, elderly/disabled flags) from the raw application.
- **lookup_income_limit** — fetch the **authoritative HUD income limits** (30% / 50% / 80% of Area
  Median Income) for the household's county from the **HUD USER Income Limits API**. The county
  identifier is non-PII, so this runs *before* masking; the limits and their provenance flow into the
  determination and the audit. (Parallel to College Scorecard in the financial-aid agent.)
- **mask_pii** — fail-closed PII de-identification (Amazon Comprehend `DetectPiiEntities`: name, SSN,
  address, DOB…). If masking can't run, nothing downstream proceeds.
- **assess_housing_eligibility** — a deterministic rules engine (income vs Area Median Income) returning
  the income category (EXTREMELY_LOW ≤30% / VERY_LOW ≤50% / LOW ≤80% / OVER_INCOME), ELIGIBLE /
  INELIGIBLE / NEEDS_REVIEW, and the **extremely-low-income targeting** flag (42 USC 1437n). No model,
  no licensed data.
- **draft_notice** — a real Bedrock (Claude) determination notice, through a fail-closed output
  guardrail, on de-identified data only.
- **write_audit** — append-only DynamoDB ledger + S3 Object Lock (WORM) copy of every decision. Each record is **hash-chained** to the prior one (`chain_hash = SHA-256(prev_hash + entry_hash)`), so the ledger is tamper-evident by construction — not just un-deletable but provably un-editable — and `lib/controls/verify_chain.py` replays the links to prove INTACT (or name the first broken record).
- **request_signoff** — starts a Step Functions separation-of-duties gate; a *different* housing
  specialist approves with a single-use token before `finalize_determination` ever runs.

Authorization is **Cedar deny-by-default** at the AgentCore Gateway: `housing_specialist_permit`
(role-gated), the `mask_before_*` forbids (no processing/drafting on un-masked data), and
`no_self_commit` (the agent can never finalize a determination). The Runtime discovers the gateway via
SSM and validates the housing specialist's Cognito JWT.

## Authoritative data — live HUD income limits

`lookup_income_limit` calls the **HUD USER Income Limits API**
(`https://www.huduser.gov/hudapi/public/il/data/{entityid}`) with the county FIPS `entityid` and returns
the 30% / 50% / 80% AMI limits for the household size, plus `median_income`, `county_name`, and a
provenance object stamped into the WORM audit. HUD requires a free Bearer token (register at
huduser.gov); it is supplied at runtime via the `HUD_API_TOKEN` environment variable / Secrets Manager
and is **never committed to this repo**. The call is a governed Gateway tool — Cedar-authorized and
audited like every other tool — and it fails soft (`found: false`) so the workflow degrades gracefully
if the token is absent or the county is unknown.

```bash
# after deploy, inject the token into the lookup Lambda (kept out of the repo):
aws lambda update-function-configuration --function-name hou-lookup-income-limit \
  --environment "Variables={HUD_API_TOKEN=<your-token>}" --region us-east-1
```

## Tests — proven live in ENFORCE

`bash lib/engine/demo.sh agents/housing-assistance` exercises the full governed workflow against the
deployed system with Cedar in **ENFORCE**: deny-by-default (housing specialist ALLOW / outsider DENY),
the authoritative HUD income-limit lookup with provenance, fail-closed PII masking, the mask-before
forbids firing *by name*, the eligibility determination + income category, a real guarded Bedrock
notice, the append-only, tamper-evident WORM audit (write-once + duplicate rejection), `no_self_commit`, and the human
sign-off gate (separation of duties + single-use token).

### Deeper caseload workflows (each a governed tool + its own Cedar control)

The higher-risk the action, the stronger the governance. Beyond intake/screening, the agent adds:

- **`recertify`** — annual/interim re-certification that classifies the change and, on an **ADVERSE**
  result (a subsidy reduction or termination), flags that **timely advance notice and an informal
  hearing/review** are required (24 CFR 982.555 / 24 CFR 966) before the action takes effect.
  Fail-closed (`mask_before_recertify`).
- **`detect_overpayment`** — deterministic housing-assistance overpayment calculation over a recovery
  period; recovery and any referral remain human decisions. Fail-closed (`mask_before_overpayment`).
- **`refer_fraud`** — a **consequential, human-only** action: the agent can **never** refer a case as
  suspected fraud. Forbidden by Cedar `no_self_fraud_referral` — the same deny-by-default pattern as
  `no_self_commit`, showing the model scales to every new high-risk action.

## Deploy / prove / run / tear down

Requirements: AWS CLI v2 (admin, us-east-1), Python 3.12 + `pyyaml`, Bedrock model access, Bash
(Git-Bash on Windows), and a free HUD USER API token. One agent = one manifest
(`agents/housing-assistance/manifest.yaml`) + domain tool bodies + Cedar policies; the engine, control
library, and runtime are reused.

```bash
bash lib/engine/deploy.sh  agents/housing-assistance    # spine: engine -> gateway -> targets -> policies -> ENFORCE
# inject the HUD token (kept out of the repo) so the live income-limit lookup works:
aws lambda update-function-configuration --function-name hou-lookup-income-limit \
  --environment "Variables={HUD_API_TOKEN=<your-token>}" --region us-east-1
bash lib/engine/demo.sh    agents/housing-assistance    # governance proof (Cedar ENFORCE)
bash lib/engine/redteam.sh agents/housing-assistance   # adversarial proof: governance holds under attack
# Runtime (from a fresh venv):
bash lib/runtime/setup_venv.sh
bash lib/runtime/_obs_setup.sh  agents/housing-assistance
bash lib/runtime/_configure.sh  agents/housing-assistance
bash lib/runtime/_launch.sh     agents/housing-assistance
bash lib/runtime/_invoke.sh     agents/housing-assistance housing_specialist   # or: bash invoke_demo.sh (with sample data)
# Optional depth add-on — the governed OAuth connector (real outbound auth via AgentCore Identity, no stored secret):
bash lib/connector/deploy_connector.sh agents/housing-assistance   # mock OAuth SoR (MOCK-EIV-PIC) + Identity provider + verify_source
bash lib/connector/prove_connector.sh  agents/housing-assistance   # proves OAuth + RS256/JWKS signature check + no secret + deny-by-default
bash lib/engine/destroy.sh agents/housing-assistance    # zero-residual teardown (identity preserved)
```

> **Windows / Git-Bash note.** Deploy from a **path without spaces** (Git-Bash quoting breaks otherwise),
> and if you launch the runtime detached use the `cmd.exe /c '"…bash.exe" -l runner.sh > log 2>&1'`
> pattern. Before tearing down, **stop any orphaned sign-off Step Functions executions** still `RUNNING`
> (`aws stepfunctions list-executions --status-filter RUNNING` → `stop-execution`) so the state machine
> can delete cleanly. See `docs/` for the full SA runbook.

Test-user passwords are env-driven (`PV_REVIEWER_PW` / `PV_APPROVER_PW` / `PV_OUTSIDER_PW`) with
placeholder defaults (`ChangeMe-*1!`) — rotate before shared use. Region/account resolve dynamically.

## Layout

```
lib/engine/     manifest-driven engine: render.py + deploy/demo/destroy + deploy_identity + signoff.asl.tmpl
lib/controls/   shared control tools: mask_pii, write_audit, request/approve/finalize sign-off, mcp_client
lib/runtime/    generic Strands agent on AgentCore Runtime (agent.py + Dockerfile + toolkit helpers)
lib/connector/  reusable governed OAuth connector: verify_source (token via AgentCore Identity, no stored secret) + deploy/prove scripts + RS256/JWKS-verified mock SoR
agents/housing-assistance/
                manifest.yaml (single source of truth) + tools/ (intake_application, lookup_income_limit,
                assess_housing_eligibility, recertify, overpayment, housing_core) + demo_extra.sh
policies/       the seven Cedar policies (rendered from the manifest), human-readable + a README
docs/           architecture note + Word/PowerPoint guides (regulatory-adherence, SA runbook, maintenance, depth-evidence, cost/latency one-pager, IdP-federation reference; generators/ regenerates the guides & decks, decks)
```

The Cedar policies in `policies/` are the governance core — see `policies/README.md`. They are
generated from the manifest at deploy time; the checked-in `.cedar` files are the reviewable rendered
form (account id and gateway ARN are placeholders).

## Honesty boundary

The accelerator owns the governed agent, the Cedar policies, the tools, the fail-closed masking, the
human-gate workflow, the WORM audit design, the live HUD income-limit integration, the IaC, the tests.
The adopter owns: IdP federation to their own provider (a working OIDC/SAML → Cognito → Cedar reference ships as `lib/engine/deploy_federation.sh` + `docs/IdP-Federation-Reference.md`, so federated users hit the same deny-by-default policies as the built-in users) and housing-specialist role mapping; validated connectors to the PHA
system of record (EIV / PIC / HMIS); the authoritative program-admission rules/preferences and their
legal review; computer-system validation; and production authorization to operate (StateRAMP / ATO).
The repo also ships a **real** governed OAuth connector — `verify_source` authenticates to a mock system of record via AgentCore Identity (no stored secret) and the SoR verifies the token's RS256 signature against the Cognito JWKS — as the reference pattern; connectors to the **production** system of record remain adopter work.

## License

Apache-2.0 — see [LICENSE](LICENSE).
