# Housing Eligibility Agent — AgentCore-Native Architecture

*Target architecture for the Housing Choice Voucher (Section 8) / public-housing eligibility hero agent, built natively on Amazon Bedrock AgentCore. This note is the anchor design — it doubles as the opening of the leadership deck and the first section of the SA runbook. It is the second State & Local Government proof of the reusable governed-hero-agent template (alongside the public-benefits agent), and the fourth vertical overall (with pharmacovigilance in HCLS and financial aid in EDU). Draft v1.0 · 2026-07.*

---

## 1. What this agent does (the regulated workflow)

Housing-assistance intake is high-volume, waitlist-driven eligibility work: Housing Choice Vouchers (Section 8), public housing, and project-based rental assistance. When an application arrives, a regulated determination workflow must run end to end:

**intake the application → look up the authoritative HUD income limit for the household's county → de-identify PII → assess the income category and voucher eligibility → draft a determination notice → a qualified housing specialist reviews and signs off → the determination is committed to the housing authority's system of record.**

Under the U.S. Housing Act and HUD regulations (24 CFR Parts 5, 960, 966, and 982) and constitutional due-process requirements, **a qualified housing specialist must make and commit the determination** — with timely written notice and, for an adverse action, an informal hearing/review right *before* the action takes effect. The agent intakes, looks up the authoritative limit, de-identifies, screens, and drafts; it never self-adjudicates. That single rule drives the whole security design.

## 2. Design thesis

AWS now ships, in Amazon Bedrock AgentCore, the governance primitives a regulated agent needs. So we don't build a parallel governance platform — we become **the regulated-industry pattern implemented natively on AgentCore**: governed agentic AI built on AWS-native services, plus the three last-mile controls regulated customers need that AgentCore doesn't provide out of the box. This housing agent is the fourth proof of that pattern (and the second in SLG): it was produced from the same manifest-driven template as the pharmacovigilance, benefits, and financial-aid agents, by swapping the domain tools, the Cedar policies, and wiring one new authoritative data source — the governance spine, runtime, and control library were reused unchanged.

## 3. Native on AgentCore vs. built alongside

| Control (governed-agent requirement) | Native? | AgentCore component / how |
|---|---|---|
| Verified human + agent identity | Native | **AgentCore Identity** — inbound JWT authorizer (Cognito / customer IdP) |
| Deny-by-default tool authorization | Native | **AgentCore Policy (Cedar)** — default-deny + forbid-wins, enforced at the Gateway |
| Least-privilege intersection (agent ∩ housing specialist) | Native | Cedar principal with JWT group claims (`housing_specialist`) as tags + tool-parameter conditions |
| Tools as governed endpoints | Native | **AgentCore Gateway** — Lambda → MCP tools; every call passes Policy |
| Agent hosting / runtime | Native | **AgentCore Runtime** — hosts the Strands agent, serverless, session-isolated |
| Tracing / observability | Native | **AgentCore Observability** — OpenTelemetry spans per agent/tool step |
| Fail-closed PII de-identification | Build | `mask_pii` Gateway tool: Comprehend `DetectPiiEntities` (name, SSN, address, DOB…), before model + before audit |
| Human sign-off gate (separation of duties) | Build | Step Functions `waitForTaskToken` — bound, single-use approval; AgentCore has no native human gate |
| Append-only, tamper-evident WORM audit (due-process evidence) | Build | Append-only DynamoDB + S3 Object Lock; Observability traces are for ops, not tamper-proof evidence |

## 4. Target architecture (components)

**AgentCore Runtime** hosts the Strands housing agent (`housing_runtime_agent`). The Strands agent gets a `BedrockAgentCoreApp` entrypoint and is deployed with the AgentCore starter toolkit (`agentcore configure` / `agentcore launch`), which containerizes it (ARM64 via CodeBuild) and manages the endpoint. The agent is generic — its workflow prompt is rendered from the manifest, so the same runtime image serves any agent built from the template.

**AgentCore Gateway** (`hou-housing-gw`) exposes each capability as an MCP tool backed by a Lambda target: `intake_application`, `lookup_income_limit` (live HUD data), `mask_pii` (fail-closed), `assess_housing_eligibility`, `draft_notice`, `write_audit`, and `request_signoff`, plus the step-two tools `recertify` and `detect_overpayment`. Because every tool call is a Gateway call, Policy can gate all of them uniformly. The consequential `finalize_determination` and `refer_fraud` actions exist only behind governance — the human gate and a deny-by-default forbid, respectively.

**AgentCore Identity** provides inbound auth — a JWT authorizer (Amazon Cognito or the customer's IdP) authenticates the housing specialist on whose behalf the agent acts — and outbound auth for the credentials the Gateway uses to reach connectors (the PHA system of record — EIV / PIC / HMIS — delivered as a labeled stub).

**AgentCore Policy (Cedar)** is the deny-by-default authorization engine (`hou_housing_authz`). Default-deny and forbid-wins are automatic. Principal = the OAuth user (JWT `cognito:groups` surfaced as a tag); Action = the specific tool invocation (auto-mapped from the Gateway's tool definitions); Resource = the Gateway; conditions can test both user claims and tool input parameters. This is simultaneously the deny-by-default gateway and the least-privilege intersection — natively.

**AgentCore Observability** emits OpenTelemetry spans for every agent and tool step.

**Built alongside — the regulated last mile:**
- **Fail-closed PII de-identification:** the `mask_pii` tool de-identifies the application (Amazon Comprehend `DetectPiiEntities` — name, SSN, address, date of birth, and more) before the model drafts and before anything is written to the audit. Fail-closed — if masking can't run, the call stops rather than exposing PII.
- **Human sign-off gate (separation of duties):** `request_signoff` starts a Step Functions execution that pauses on `waitForTaskToken`; a *different* qualified housing specialist approves with a bound, single-use token. The agent cannot finalize a determination itself.
- **Append-only, tamper-evident WORM audit:** an append-only, tamper-evident record (append-only DynamoDB + S3 Object Lock) capturing `INTENT → COMMITTED` for the due-process evidence trail.

## 4a. Authoritative data — live HUD income limits

`lookup_income_limit` is a governed Gateway tool that calls the **HUD USER Income Limits API** (`https://www.huduser.gov/hudapi/public/il/data/{entityid}`) with the household's county FIPS `entityid` and returns the **30% / 50% / 80% of Area Median Income** limits for the household size, plus `median_income`, `county_name`, and a provenance object. The county identifier is a **non-PII** decision field, so this tool runs *before* `mask_pii`; the returned limits and their provenance flow into the determination and are stamped into the WORM audit, so the basis of every decision is traceable to a named, authoritative federal source. HUD requires a free Bearer token (register at huduser.gov); it is supplied at runtime via the `HUD_API_TOKEN` environment variable / Secrets Manager and is **never committed to the repo**. The call is Cedar-authorized and audited like every other tool, and it fails soft (`found: false`) so the workflow degrades gracefully if the token is absent or the county is unknown. This is the SLG counterpart to the financial-aid agent's live College Scorecard cost-of-attendance lookup: real federal data reached through a *governed* tool, not an ungoverned side-channel.

## 5. How one governed action flows

1. The housing specialist authenticates (Cognito/IdP) and receives a JWT.
2. The agent (on AgentCore Runtime) decides to call a tool.
3. The call goes through AgentCore Gateway; **Inbound Auth** validates the JWT.
4. The **Policy Engine** evaluates Cedar: principal (user claims) + action (the tool) + resource (the gateway) + conditions (group, tool parameters), default-deny. A deny means the tool never runs — and the denial is auditable.
5. The allowed tool runs. `lookup_income_limit` fetches the authoritative HUD limit on the non-PII county id; then `mask_pii` runs (fail-closed), so the model and the eligibility rules only ever see de-identified text.
6. The consequential step never executes inline: `request_signoff` opens the Step Functions human gate; a second qualified housing specialist approves; only then does `finalize_determination` run.
7. Every decision and state change is written to the WORM audit, and every step is traced in Observability.

## 6. The eligibility rules engine (deterministic)

`assess_housing_eligibility` is a **deterministic rules engine**, not a model. It applies the **HUD income-category framework** (24 CFR 5.603) to the de-identified decision fields using the authoritative per-county limits from `lookup_income_limit`: it classifies the household as **EXTREMELY_LOW** (≤ 30% AMI), **VERY_LOW** (≤ 50% AMI), **LOW** (≤ 80% AMI), or **OVER_INCOME**, and returns a determination (ELIGIBLE / INELIGIBLE / NEEDS_REVIEW). Voucher/public-housing admission generally requires very-low income (≤ 50% AMI); households between 50% and 80% (low income) route to NEEDS_REVIEW for eligible categories; above 80% is over-income. It also raises the **extremely-low-income targeting** flag: by statute (42 USC 1437n) at least 75% of new HCV admissions must go to extremely-low-income families, so a ≤ 30% AMI household is flagged as targeting priority. Every determination stamps the HUD income-limit provenance into its output. It fails closed if the case is not marked de-identified. This is the eligibility counterpart to the PV agent's seriousness/reporting-clock step: a transparent, auditable, non-model determination a housing specialist can defend at an informal hearing.

## 6a. Deeper caseload workflows (step two)

Beyond intake and screening, the agent adds the workflows a real caseload needs — each a **new governed tool with its own Cedar control**, following one rule: the higher-risk the action, the stronger the governance.

- **`recertify`** — annual/interim re-certification. It re-runs the income rules on new facts, classifies the change, and on an **ADVERSE** result (a subsidy reduction or a termination of assistance) flags that **timely written advance notice** and an **informal hearing/review** right are required *before* the action takes effect (24 CFR 982.555 for HCV; 24 CFR 966 grievance for public housing). Fail-closed (`mask_before_recertify`).
- **`detect_overpayment`** — deterministic housing-assistance overpayment math (subsidy paid vs. subsidy owed under corrected income, over a recovery period). Recovery and any referral remain human decisions. Fail-closed (`mask_before_overpayment`).
- **`refer_fraud`** — a **consequential, human-only** action. The agent can **never** refer a case as suspected fraud; `refer_fraud` is forbidden outright by `no_self_fraud_referral`, exactly mirroring `no_self_commit`.

The point for an adopter: the governance model scales to new workflows with no new plumbing — a tool body plus a deny-by-default forbid — and each new forbid fires *by name* in ENFORCE.

## 7. Cedar policy model for housing (illustrative)

Default-deny is automatic; we author explicit permits plus a few targeted forbids. Illustrative — final syntax is pinned against the account during deploy:

```cedar
// A housing specialist may intake, look up limits, mask, assess, and draft — gated on the group claim.
permit(principal, action, resource is AgentCore::Gateway)
when { principal.hasTag("cognito:groups") &&
       principal.getTag("cognito:groups") like "*housing_specialist*" };

// No eligibility assessment on un-masked data: assess requires the de-identified flag.
forbid(principal, action == AgentCore::Action::"assess-eligibility___assess_housing_eligibility",
       resource == AgentCore::Gateway::"<gateway-arn>")
unless { context.input.deidentified == true };

// No drafting on un-masked data.
forbid(principal, action == AgentCore::Action::"hou-core___draft_notice",
       resource == AgentCore::Gateway::"<gateway-arn>")
unless { context.input.deidentified == true };

// The determination is never a direct tool call — only the approval workflow can finalize.
forbid(principal, action == AgentCore::Action::"hou-core___finalize_determination",
       resource == AgentCore::Gateway::"<gateway-arn>");

// A fraud referral is a human-only decision — the agent can never call it.
forbid(principal, action == AgentCore::Action::"hou-core___refer_fraud",
       resource == AgentCore::Gateway::"<gateway-arn>");
```

The shape is the point: a group-scoped permit, forbids that enforce masking-before-processing and masking-before-model, and no path for the agent to self-commit a determination or refer a case.

## 8. Build order

1. **Governance spine first** — Cedar policies + Policy Engine + Gateway, with deny-by-default proven before anything else.
2. **Tools as Gateway Lambda targets** — `intake_application`, `lookup_income_limit`, `mask_pii`, `assess_housing_eligibility`, `recertify`, `detect_overpayment`, `draft_notice`, `write_audit`, `request_signoff`.
3. **Runtime + Identity** — the generic Strands agent onto AgentCore Runtime; Cognito inbound JWT wired to the Cedar principal.
4. **Human sign-off gate** — Step Functions `waitForTaskToken` wired to `request_signoff` and `finalize_determination`.
5. **WORM audit + Observability.**
6. **Authoritative data** — inject the HUD API token into the `lookup_income_limit` Lambda (env / Secrets), kept out of the repo.
7. **Manifest + validate** — the whole agent is one manifest; deploy; end-to-end run (Cedar allow/deny, live HUD lookup, masking, eligibility, real Bedrock notice, tamper-evident audit) + negative tests; teardown.

## 9. What's ours vs. the customer's (honesty boundary)

The accelerator owns: the agent, the Cedar policies, the tools, the fail-closed masking, the human-gate workflow, the WORM audit design, the eligibility rules engine, the live HUD income-limit integration, the IaC/manifest, and the docs. The customer owns: IdP federation and housing-specialist role mapping; validated connectors to the PHA system of record (EIV / PIC / HMIS); the authoritative program-admission rules and local preferences and their legal review; computer-system validation; and production authorization to operate (StateRAMP / ATO). Program-admission rules and local preferences here are configuration, and `verify_income_source` / system-of-record connectors ship as labeled stubs. Nothing here is production-certified on day one — and saying so is part of the credibility.

## 10. Regulatory anchors (full mapping is a separate guide)

- **U.S. Housing Act / HUD regulations** (24 CFR 5 income limits & definitions, 982 HCV, 960/966 public housing) → `lookup_income_limit` + `assess_housing_eligibility` rules engine; the **qualified-specialist determination** → the human gate.
- **Extremely-low-income targeting** (42 USC 1437n) → the targeting-priority flag in the determination.
- **Due process** (24 CFR 982.555 HCV informal hearing / 24 CFR 966 public-housing grievance) → the drafted determination notice + the WORM record + the advance-notice flag on adverse recertification.
- **Privacy Act / PII safeguarding** (applicant SSNs, income records) → fail-closed masking + least-privilege Cedar + tamper-evident audit + encryption.
- **StateRAMP / NIST SP 800-53** (the authorization framework for state/local systems) → deny-by-default access control, audit, and the reproducible control evidence.

Each of these becomes a control-to-requirement line in the regulatory-adherence guide.
