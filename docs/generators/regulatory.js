const G = require("./guides.js");
const { H1, H2, H3, P, bold, code, bullet, num, codeBlock, callout, table, spacer, coverAndToc, makeDoc, Packer } = G;

const cover = coverAndToc(
  ["Regulatory-Adherence Guide"],
  "Housing Eligibility Agent on Amazon Bedrock AgentCore",
  "How the governed Housing Choice Voucher (Section 8) / public-housing eligibility accelerator maps to the U.S. Housing Act and HUD regulations (24 CFR Parts 5, 960/966, 982), the informal-hearing/due-process requirements, the Privacy Act, and StateRAMP / NIST SP 800-53 — the controls it provides, the evidence it produces, and the validation that remains the housing authority's responsibility. Accelerator reference; not a compliance certification or legal advice. Version 1.0 · 2026.",
  ["1. Purpose & scope", "2. The regulated workflow", "3. Frameworks in scope", "4. Housing program-integrity mapping", "5. Privacy Act & PII-safeguarding mapping", "6. Due process, StateRAMP & NIST SP 800-53 mapping", "7. Separation of duties & the human gate", "8. Shared responsibility", "9. Disclaimer"]
);

const body = [
  H1("1. Purpose & scope"),
  P("This guide maps the controls implemented in the Housing Choice Voucher (Section 8) / public-housing eligibility accelerator to the requirements a Public Housing Agency (PHA) or housing authority must satisfy. It is written for the compliance, privacy, information-security, and housing-program leadership who decide whether an AI-assisted eligibility workflow can be adopted."),
  P([bold("What this guide is: "), "a control-to-requirement mapping showing how the accelerator supports adherence, what evidence it produces, and where the housing authority's own validation is required."]),
  P([bold("What this guide is not: "), "a certification, an attestation, or legal/regulatory advice. Adopting this accelerator does not by itself make a system compliant or an eligibility determination correct. Program participation, the accuracy of admission rules and local preferences, and the lawfulness of the process remain the housing authority's responsibility (§8)."]),
  callout("Design principle", [["Every control below follows one rule from the regulated workflow: a qualified housing specialist makes the eligibility determination and commits it — the agent intakes, looks up the authoritative HUD limit, de-identifies, screens, and drafts, but never self-adjudicates. The security design exists to enforce that rule and to produce the due-process evidence trail."]], G.colors.TEAL),

  H1("2. The regulated workflow"),
  P("Housing-assistance intake decides whether a household qualifies for a Housing Choice Voucher or public housing, which HUD income category it falls in against Area Median Income (AMI), and whether an extremely-low-income targeting priority applies. When an application arrives, a regulated workflow runs: intake the application, look up the authoritative HUD income limit for the household's county, de-identify PII, assess the income category and voucher eligibility, draft a determination notice, obtain a qualified housing specialist's review and sign-off, and commit the determination to the system of record."),
  P("The accelerator automates the intake, authoritative-lookup, de-identification, screening, and drafting steps under governance, and pauses at a human sign-off gate before any determination is committed. Four regulatory areas bear on this workflow, mapped in §§4–6."),

  H1("3. Frameworks in scope"),
  table(["Framework", "Relevance to the workflow"], [
    [[bold("U.S. Housing Act / HUD regulations")], "Federal housing-assistance program rules — income limits and definitions (24 CFR Part 5, §5.603 income categories), the Housing Choice Voucher program (24 CFR Part 982), and public housing (24 CFR Parts 960/966); the extremely-low-income targeting requirement (42 USC 1437n) and the qualified-specialist determination."],
    [[bold("Due process / informal hearing")], "Timely written notice and an informal hearing/review right before an adverse action takes effect — 24 CFR 982.555 (HCV informal hearing) and 24 CFR Part 966 (public-housing grievance)."],
    [[bold("Privacy Act")], "Safeguarding of applicant personally identifiable information — Social Security numbers, income records, and other identifiers — and controlled access to it."],
    [[bold("StateRAMP / NIST SP 800-53")], "The authorization framework for state and local government systems — access control, audit, and reproducible control evidence supporting an authorization to operate (ATO)."],
  ], [2900, 7540]),

  H1("4. Housing program-integrity mapping"),
  P("The U.S. Housing Act and HUD regulations require an accurate income-category determination against the authoritative area limits, extremely-low-income targeting, re-certification, and an auditable determination trail, with a qualified specialist making the determination. The accelerator produces the determination and the tamper-evident record a program review or audit depends on; the authoritative admission rules, local preferences, and their correctness remain the housing authority's responsibility."),
  table(["Housing requirement", "How the accelerator addresses it", "Evidence / authority responsibility"], [
    ["Income-category determination (24 CFR 5.603)", "assess_housing_eligibility classifies the household deterministically against Area Median Income — EXTREMELY_LOW (≤ 30% AMI), VERY_LOW (≤ 50% AMI), LOW (≤ 80% AMI), or OVER_INCOME. The 30/50/80% AMI limits are fetched LIVE from the HUD USER Income Limits API (lookup_income_limit) on the household's county FIPS, and their provenance is stamped into the determination — a real, cited, reproducible basis.", [{ text: "Authority: ", bold: true }, "admission policy; a free HUD USER Bearer token (register at huduser.gov)."]],
    ["Voucher/public-housing admission threshold", "assess_housing_eligibility returns ELIGIBLE / INELIGIBLE / NEEDS_REVIEW: HCV/public-housing admission generally requires very-low income (≤ 50% AMI); households between 50% and 80% (low income) route to NEEDS_REVIEW; above 80% is over-income.", "The eligibility output; authority owns its published admission policy and local preferences."],
    ["Extremely-low-income targeting (42 USC 1437n)", "assess_housing_eligibility raises the extremely-low-income targeting flag for a ≤ 30% AMI household — by statute at least 75% of new HCV admissions must go to extremely-low-income families.", "The targeting-priority flag; authority owns its targeting monitoring and waitlist administration."],
    ["Annual/interim re-certification", "recertify re-runs the income rules on new facts and classifies the change; an ADVERSE change (subsidy reduction or termination) flags that advance written notice and an informal hearing/review right are required BEFORE it takes effect (24 CFR 982.555 / 966). It never commits.", "The re-certification schedule and hearing procedures; authority owns the notice language and hearing process."],
    ["A defensible, reproducible determination", "assess_housing_eligibility is a deterministic rules engine (no model) with the stated AMI basis and HUD provenance, so a housing specialist can defend it at an informal hearing.", "The auditable determination basis; authority owns the authoritative rules."],
    ["An auditable determination trail", "Append-only DynamoDB ledger plus an S3 Object Lock (WORM) copy of each decision (including the HUD income-limit source and any recertification record); the writing principal is denied delete, update, and retention bypass.", "Object Lock configuration; IAM deny policy. Authority sets the retention period."],
    ["The determination is made by a qualified specialist", "The commit is performed by a housing specialist at the human sign-off gate; the agent cannot finalize (Cedar no-self-commit).", "Enforced by the Step Functions gate + the forbid (see §7)."],
  ], [2650, 4090, 3700]),

  H1("5. Privacy Act & PII-safeguarding mapping"),
  P("The Privacy Act and HUD's own safeguarding requirements protect applicant PII — Social Security numbers, income records, addresses — and limit its disclosure. The accelerator de-identifies PII before the model or the audit sees it, and constrains access by least privilege. The housing authority's privacy program and its determination of who has a need to know remain prerequisites."),
  table(["Privacy Act area", "How the accelerator addresses it", "Evidence / authority responsibility"], [
    ["Protect applicant PII", "The mask_pii tool runs Amazon Comprehend DetectPiiEntities to remove PII (name, SSN, address, date of birth, and more) before drafting and before the audit — fail-closed: if masking cannot run, no draft is produced. The non-PII county FIPS used for the HUD lookup is deliberately handled before masking.", "Comprehend detection; demo proves name/SSN redaction and the fail-closed path."],
    ["Control access (need to know)", "Amazon Cognito authentication with AgentCore Policy (Cedar) deny-by-default; every tool call is authorized against the housing specialist's identity and group.", "Cognito pool + Cedar policies; authority maps housing-specialist roles."],
    ["Audit access to records", "Every governed action writes a tamper-evident record capturing INTENT → COMMITTED with a content hash and timestamp; duplicates are rejected.", "The hou-audit ledger + WORM bucket; demo proves write-once + duplicate rejection."],
    ["Least privilege / minimum necessary", "The agent acts only within the intersection of its own and the housing specialist's permissions; the finalize action is forbidden to the agent entirely.", "Cedar least-privilege permit/forbid policies."],
    ["Protect records in transit and at rest", "Runs inside the authority's AWS account; PII is masked before any model call; records are Object-Lock protected.", [{ text: "Authority: ", bold: true }, "KMS/encryption, network controls, the Privacy Act system-of-records notice & routine-use review."]],
  ], [2500, 4240, 3700]),

  H1("6. Due process, StateRAMP & NIST SP 800-53 mapping"),
  P("Due process requires timely written notice and an informal hearing/review right before an adverse action takes effect; StateRAMP / NIST SP 800-53 add the access-control, audit, and control-evidence discipline a state/local authorization to operate depends on. The accelerator implements the notice-generation, access-control, audit, and de-identification safeguards; the authoritative notice language, the hearing process, and the ATO package are the authority's."),
  table(["Due process / 800-53 area", "How the accelerator addresses it", "Status / authority responsibility"], [
    ["Timely written notice + informal hearing", "draft_notice produces a de-identified determination notice on masked data only; recertify flags that advance notice and an informal hearing/review right (24 CFR 982.555 / 966) are required before an adverse action takes effect. The WORM record preserves the notice and its basis.", "The authoritative notice language and hearing procedures; authority owns the informal-hearing process."],
    ["Access controls (AC family)", "Deny-by-default Cedar authorization at the Gateway; authenticated identity via Cognito/IdP; least-privilege permits scoped to the housing-specialist group.", "Live in ENFORCE; authority federates its IdP and maps roles."],
    ["Encryption & data protection (SC family)", "PII is masked before any model call; the audit copy is Object-Lock protected; runs inside the authority's account.", [{ text: "Authority: ", bold: true }, "KMS keys, TLS, and network segmentation."]],
    ["Audit & accountability (AU family)", "Immutable WORM audit of every decision and state change, with identity-tagged, OTel-correlated logs.", "Live; authority sets retention and log aggregation."],
    ["Reproducible control evidence (CA/SA)", "Reproducible AWS CDK infrastructure-as-code, a 117-test automated suite gating every change in CI, and captured clean-account validation runs (the full governed workflow live end-to-end; the Cedar authorization gateway deployed as code in enforcement mode) committed in the repo's evidence/ folder.", [{ text: "Authority: ", bold: true }, "the StateRAMP / NIST 800-53 control set, the SSP, and the authorization to operate."]],
  ], [2500, 4240, 3700]),

  H1("7. Separation of duties & the human sign-off gate"),
  P("The single most important control for housing program integrity and due process is that a qualified housing specialist — not the agent — makes and commits the determination. The accelerator enforces this structurally:"),
  bullet([bold("The agent cannot commit. "), "The finalize_determination action is forbidden by a Cedar policy and is hidden from the agent entirely; it is not reachable as a tool."]),
  bullet([bold("Commitment runs only through the gate. "), "The sanctioned path is a request for sign-off that starts a Step Functions workflow, which pauses until a housing specialist approves."]),
  bullet([bold("The approver must differ from the requester. "), "A separation-of-duties check rejects self-approval."]),
  bullet([bold("Approvals are single-use. "), "The approval token is consumed against a durable ledger; it cannot be replayed."]),
  bullet([bold("Both ends are audited. "), "An INTENT record is written when sign-off is requested and a COMMITTED record when the determination is finalized."]),
  bullet([bold("A fraud referral is never the agent's. "), "refer_fraud is a consequential, human-only action, forbidden outright by no_self_fraud_referral — the same deny-by-default pattern as no-self-commit."]),
  callout("Proven live", [["In enforcement mode: a housing specialist's request to self-approve is blocked as a separation-of-duties violation; a different qualified housing specialist's approval succeeds; the determination finalizes only after approval; and re-using the token is rejected. The generic agent also runs on AgentCore Runtime with these controls intact."]], G.colors.MINT, "E9F5EF"),

  H1("8. Shared responsibility"),
  P("The accelerator provides the pattern, the controls, and the evidence. Program participation and the connection to the housing authority's real systems and rules remain the authority's."),
  table(["The accelerator provides", "The housing authority is responsible for"], [
    ["The governed agent, Cedar policies, and tools", "Program participation and authorization to operate (StateRAMP / ATO)"],
    ["Fail-closed PII de-identification", "IdP federation and housing-specialist role mapping"],
    ["The human sign-off workflow (separation of duties)", "Validated connectors to the PHA system of record (EIV / PIC / HMIS)"],
    ["The deterministic eligibility rules engine (illustrative defaults)", "The authoritative admission rules, local preferences, and their legal review"],
    ["The live HUD income-limit integration + the immutable WORM audit design", "Record-retention policy and program-review / hearing readiness"],
    ["Reproducible CDK IaC + the automated test suite + captured validation evidence", "Computer-system validation and the StateRAMP / NIST 800-53 control package"],
    ["Documentation (this guide, the runbook, maintenance)", "Notice language, informal-hearing rights, and the applicant appeal process"],
  ], [5220, 5220]),

  H1("9. Disclaimer"),
  P([{ text: "This document describes how an accelerator's technical controls map to selected regulatory requirements. It is provided for evaluation and architecture purposes only. It is not legal, regulatory, or compliance advice, and it is not a certification or attestation of compliance with the U.S. Housing Act, 24 CFR Parts 5, 960, 966, or 982, 42 USC 1437n, the informal-hearing/due-process requirements, the Privacy Act, StateRAMP / NIST SP 800-53, or any other authority. Eligibility determinations have direct consequences for households; the correctness of admission rules, income limits, local preferences, and notices, and the lawfulness of the process, depend on the housing authority's validated implementation, policies, legal review, and use. The income limits are fetched live from HUD, but the program-admission rules, thresholds, and preferences shipped with the accelerator are illustrative configuration, not authoritative program rules. Consult your compliance, privacy, and housing-program leadership before processing real applicant data.", italics: true, color: G.colors.MUTED, size: 19 }]),
];

const doc = makeDoc(cover, body, "Housing Eligibility AgentCore · Regulatory-Adherence Guide");
Packer.toBuffer(doc).then((b) => { require("fs").writeFileSync("Housing-AgentCore-Regulatory-Adherence.docx", b); console.log("wrote regulatory"); });
