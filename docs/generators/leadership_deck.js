/* Leadership deck — Governed Agentic AI for Regulated Industries (Housing Eligibility accelerator on AgentCore) */
const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Housing Eligibility AgentCore Accelerator";
p.title = "Governed Agentic AI for Housing Choice Voucher Eligibility";

const NAVY = "0E2A47", NAVY2 = "143A5E", TEAL = "1C7293", MINT = "02C39A", AMBER = "E8A13A";
const INK = "1A2733", CLOUD = "F4F7FA", CARD = "FFFFFF", MUTED = "6B7A8A", LINE = "D9E1E8", WHITE = "FFFFFF", ICE = "CADCFC";
const TF = "Cambria", BF = "Calibri";
const sh = (o = {}) => Object.assign({ type: "outer", color: "0A1F33", blur: 9, offset: 3, angle: 90, opacity: 0.22 }, o);
function bg(s, c) { s.background = { color: c }; }
function footer(s, n) {
  s.addText([{ text: "Governed Agentic AI · Amazon Bedrock AgentCore", options: { color: MUTED, fontSize: 8, fontFace: BF } }], { x: 0.6, y: 7.06, w: 8, h: 0.3, align: "left", margin: 0 });
  s.addText(String(n).padStart(2, "0"), { x: 12.4, y: 7.02, w: 0.4, h: 0.3, align: "right", color: MUTED, fontSize: 9, fontFace: BF, margin: 0 });
}
function title(s, t, color = INK) { s.addText(t, { x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontFace: TF, fontSize: 27, bold: true, color, align: "left", valign: "top", margin: 0 }); }
function eyebrow(s, t, color = TEAL) { s.addText(t.toUpperCase(), { x: 0.62, y: 0.28, w: 12, h: 0.3, fontFace: BF, fontSize: 11, bold: true, color, charSpacing: 2, margin: 0 }); }
function card(s, x, y, w, h, fill = CARD, radius = 0.09) { s.addShape(p.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: LINE, width: 1 }, rectRadius: radius, shadow: sh() }); }
function circle(s, x, y, d, fill, txt, txtColor = WHITE, fs = 16) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" }, shadow: sh({ blur: 6, offset: 2, opacity: 0.18 }) });
  if (txt !== undefined) s.addText(txt, { x, y, w: d, h: d, align: "center", valign: "middle", color: txtColor, fontFace: BF, fontSize: fs, bold: true, margin: 0 });
}

/* 1. TITLE */
(() => {
  const s = p.addSlide(); bg(s, NAVY);
  s.addShape(p.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: NAVY } });
  s.addShape(p.ShapeType.ellipse, { x: 9.4, y: -1.9, w: 6.2, h: 6.2, fill: { color: NAVY2 }, line: { type: "none" } });
  s.addShape(p.ShapeType.ellipse, { x: 10.4, y: -0.9, w: 4.2, h: 4.2, fill: { color: "18466F" }, line: { type: "none" } });
  s.addShape(p.ShapeType.ellipse, { x: 11.25, y: -0.05, w: 2.5, h: 2.5, fill: { color: TEAL }, line: { type: "none" } });
  s.addText("AMAZON BEDROCK AGENTCORE  ·  STATE & LOCAL GOVERNMENT", { x: 0.7, y: 1.35, w: 11, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: MINT, charSpacing: 2, margin: 0 });
  s.addText("Governed Agentic AI,\nProven in Housing Choice Voucher Eligibility", { x: 0.66, y: 1.95, w: 11.6, h: 2.1, fontFace: TF, fontSize: 38, bold: true, color: WHITE, lineSpacingMultiple: 1.02, margin: 0 });
  s.addText("A Housing Choice Voucher (Section 8) / public-housing eligibility accelerator running natively on Amazon Bedrock AgentCore — identity-bound, deny-by-default with Cedar, live HUD income limits, and proven end-to-end on AWS. The fourth vertical built from one reusable template.",
    { x: 0.7, y: 4.15, w: 9.7, h: 1.0, fontFace: BF, fontSize: 16, color: ICE, lineSpacingMultiple: 1.15, margin: 0 });
  const chips = ["30 / 30 live governance checks", "Agent native on Runtime", "Fourth vertical from one template"];
  let cx = 0.7;
  chips.forEach((c) => {
    const w = 0.42 + c.length * 0.098;
    s.addShape(p.ShapeType.roundRect, { x: cx, y: 5.5, w, h: 0.5, fill: { color: NAVY2 }, line: { color: TEAL, width: 1 }, rectRadius: 0.25 });
    s.addText(c, { x: cx, y: 5.5, w, h: 0.5, align: "center", valign: "middle", color: WHITE, fontFace: BF, fontSize: 12, bold: true, margin: 0 });
    cx += w + 0.25;
  });
  s.addText("Draft v1 · 2026", { x: 0.7, y: 6.7, w: 4, h: 0.3, color: MUTED, fontSize: 10, fontFace: BF, margin: 0 });
  s.addNotes("Fourth proof of the pattern, and the second in State & Local Government: the same governed chassis that runs pharmacovigilance, benefits eligibility, and financial-aid awarding now runs Housing Choice Voucher eligibility, from one reusable template. AWS shipped the governance primitives; we implement the regulated pattern natively — plus a live HUD income-limit integration — and prove it end-to-end.");
})();

/* 2. TENSION */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "The problem");
  title(s, "Housing authorities want agentic AI for eligibility. They can't deploy an ungoverned one.");
  s.addText([
    { text: "An agent that touches applicant PII and income records and issues eligibility determinations must be identity-bound, deny-by-default, auditable, and ", options: { color: INK, fontSize: 15, fontFace: BF } },
    { text: "incapable of adjudicating on its own.", options: { color: TEAL, fontSize: 15, fontFace: BF, bold: true } },
    { text: "  “Impressive demo” is not the bar — “will survive a program review and an informal hearing” is.", options: { color: INK, fontSize: 15, fontFace: BF } },
  ], { x: 0.62, y: 1.5, w: 12.0, h: 0.9, valign: "top", lineSpacingMultiple: 1.15, margin: 0 });
  const items = [
    ["Touches income records", "Names, SSNs, and household income flow through the housing application.", "Privacy Act · de-identification", TEAL],
    ["Creates records with consequences", "The determination notice affects a household's assistance and its right to an informal hearing.", "U.S. Housing Act · hearing rights", AMBER],
    ["Takes consequential actions", "Committing a determination grants or denies housing assistance — accountably.", "Program integrity · separation of duties", MINT],
  ];
  const w = 3.86, gap = 0.24, x0 = 0.62, y = 2.75, h = 3.6;
  items.forEach((it, i) => {
    const x = x0 + i * (w + gap);
    card(s, x, y, w, h);
    circle(s, x + 0.32, y + 0.34, 0.62, it[3], String(i + 1));
    s.addText(it[0], { x: x + 1.12, y: y + 0.36, w: w - 1.3, h: 0.6, fontFace: TF, fontSize: 16, bold: true, color: INK, valign: "middle", margin: 0 });
    s.addText(it[1], { x: x + 0.34, y: y + 1.25, w: w - 0.66, h: 1.4, fontFace: BF, fontSize: 13.5, color: "34434F", valign: "top", lineSpacingMultiple: 1.12, margin: 0 });
    s.addShape(p.ShapeType.roundRect, { x: x + 0.34, y: y + h - 0.78, w: w - 0.68, h: 0.5, fill: { color: CLOUD }, line: { type: "none" }, rectRadius: 0.08 });
    s.addText(it[2], { x: x + 0.34, y: y + h - 0.78, w: w - 0.68, h: 0.5, align: "center", valign: "middle", fontFace: BF, fontSize: 11, bold: true, color: it[3], margin: 0 });
  });
  footer(s, 2);
  s.addNotes("Three non-negotiables that block ungoverned agents in housing eligibility. The rest of the deck shows how AgentCore + three last-mile controls satisfy all three.");
})();

/* 3. WHY NOW */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Why now");
  title(s, "AWS just shipped the governance primitives");
  s.addText("Amazon Bedrock AgentCore now provides — as native, managed services — the exact controls a governable agent needs. The gap between a “cool agent” and a “governable agent” just closed, on AWS.",
    { x: 0.62, y: 1.45, w: 11.7, h: 0.9, fontFace: BF, fontSize: 15, color: INK, lineSpacingMultiple: 1.15, margin: 0 });
  const prims = [
    ["Identity", "Inbound JWT — Cognito or the authority's IdP"],
    ["Policy (Cedar)", "Deny-by-default, forbid-wins authorization"],
    ["Gateway", "APIs / Lambda exposed as governed MCP tools"],
    ["Runtime", "Serverless, session-isolated agent hosting"],
    ["Observability", "OpenTelemetry spans per agent & tool step"],
  ];
  const w = 2.28, gap = 0.2, x0 = 0.62, y = 2.9, h = 3.15;
  prims.forEach((pr, i) => {
    const x = x0 + i * (w + gap);
    card(s, x, y, w, h);
    circle(s, x + w / 2 - 0.34, y + 0.35, 0.68, TEAL, String.fromCharCode(9679), MINT, 20);
    s.addText(pr[0], { x: x + 0.12, y: y + 1.2, w: w - 0.24, h: 0.5, align: "center", fontFace: TF, fontSize: 15.5, bold: true, color: NAVY, margin: 0 });
    s.addText(pr[1], { x: x + 0.16, y: y + 1.72, w: w - 0.32, h: 1.3, align: "center", fontFace: BF, fontSize: 12, color: "44535F", lineSpacingMultiple: 1.1, valign: "top", margin: 0 });
  });
  s.addText("Five native governance primitives — no platform to hand-build.", { x: 0.62, y: 6.25, w: 12, h: 0.4, fontFace: BF, fontSize: 13, italic: true, color: TEAL, margin: 0 });
  footer(s, 3);
  s.addNotes("The 'why now.' Previously teams hand-rolled identity, policy engines, audit. AgentCore makes those native.");
})();

/* 4. THESIS */
(() => {
  const s = p.addSlide(); bg(s, NAVY);
  eyebrow(s, "The thesis", MINT);
  s.addText("Implement the regulated pattern natively — don't rebuild the platform", { x: 0.6, y: 0.45, w: 12.1, h: 0.9, fontFace: TF, fontSize: 26, bold: true, color: WHITE, margin: 0 });
  card(s, 0.62, 1.7, 5.9, 4.35, NAVY2, 0.1);
  s.addText("NATIVE ON AGENTCORE", { x: 0.95, y: 2.0, w: 5.2, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: MINT, charSpacing: 1.5, margin: 0 });
  const nativeList = ["Verified human + agent identity", "Deny-by-default authorization (Cedar)", "Least-privilege intersection (agent ∩ housing specialist)", "Tools as governed endpoints (Gateway)", "Serverless agent runtime", "Tracing & observability"];
  nativeList.forEach((t, i) => {
    const y = 2.55 + i * 0.56;
    circle(s, 0.95, y, 0.34, MINT, "✓", NAVY, 13);
    s.addText(t, { x: 1.42, y: y - 0.04, w: 4.9, h: 0.42, fontFace: BF, fontSize: 13, color: WHITE, valign: "middle", margin: 0 });
  });
  card(s, 6.8, 1.7, 5.9, 4.35, "1E2E1A", 0.1);
  s.addShape(p.ShapeType.rect, { x: 6.8, y: 1.7, w: 5.9, h: 4.35, fill: { type: "none" }, line: { color: AMBER, width: 1.25 } });
  s.addText("THE REGULATED LAST MILE — BUILT ALONGSIDE", { x: 7.13, y: 2.0, w: 5.4, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: AMBER, charSpacing: 1, margin: 0 });
  const buildList = [["Fail-closed PII de-identification", "No masking → no assessment, no draft. Ever."], ["Human sign-off gate (separation of duties)", "A different qualified housing specialist, single-use token."], ["Immutable WORM audit", "Append-only + Object Lock; writer can't tamper."]];
  buildList.forEach((t, i) => {
    const y = 2.62 + i * 1.02;
    circle(s, 7.13, y, 0.4, AMBER, "⚙", NAVY, 15);
    s.addText(t[0], { x: 7.68, y: y - 0.06, w: 4.85, h: 0.5, fontFace: BF, fontSize: 14, bold: true, color: WHITE, valign: "middle", margin: 0 });
    s.addText(t[1], { x: 7.68, y: y + 0.4, w: 4.85, h: 0.5, fontFace: BF, fontSize: 12, color: "C9D6C2", valign: "top", margin: 0 });
  });
  s.addText("Governed agentic AI on AWS-native services, plus the three controls regulated customers need that AgentCore doesn't ship. A stronger — and more honest — story than “we built our own platform.”",
    { x: 0.62, y: 6.2, w: 12.1, h: 0.7, fontFace: BF, fontSize: 13.5, italic: true, color: ICE, align: "center", margin: 0 });
  footer(s, 4);
  s.addNotes("Six of nine controls are native; three are the regulated 'last mile' we add. Positions the work as extending AgentCore, not competing with it.");
})();

/* 5. HERO USE CASE */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "The hero use case");
  title(s, "Housing eligibility: determining voucher eligibility from an application");
  const steps = ["Intake the\napplication", "Look up the\nHUD limit", "De-identify\n& assess vs AMI", "Draft the\nnotice", "Specialist\nsign-off", "Commit the\ndetermination"];
  const n = steps.length, w = 1.86, gap = 0.15, x0 = 0.62, y = 1.85, h = 1.35;
  steps.forEach((t, i) => {
    const x = x0 + i * (w + gap);
    const isHuman = i === 4, isCommit = i === 5;
    const fill = isHuman ? AMBER : isCommit ? NAVY : TEAL;
    s.addShape(p.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { type: "none" }, rectRadius: 0.08, shadow: sh({ blur: 6, offset: 2, opacity: 0.16 }) });
    s.addText(t, { x, y, w, h, align: "center", valign: "middle", color: WHITE, fontFace: BF, fontSize: 11.5, bold: true, lineSpacingMultiple: 1.0, margin: 0.03 });
    if (i < n - 1) s.addText("›", { x: x + w - 0.02, y, w: gap + 0.05, h, align: "center", valign: "middle", color: MUTED, fontSize: 16, bold: true, margin: 0 });
  });
  card(s, 0.62, 3.7, 12.1, 2.35, CARD, 0.1);
  circle(s, 1.05, 4.15, 0.9, NAVY, "§", MINT, 30);
  s.addText("The one rule that drives the entire security design", { x: 2.25, y: 4.02, w: 10.2, h: 0.5, fontFace: TF, fontSize: 18, bold: true, color: NAVY, margin: 0 });
  s.addText([
    { text: "Under the U.S. Housing Act and HUD regulations, a qualified housing specialist makes and commits the eligibility determination — with timely written notice and, for an adverse action, an informal hearing right before it takes effect. ", options: { bold: true, color: INK } },
    { text: "The agent intakes, looks up the authoritative HUD limit, de-identifies, screens, and drafts — it never self-adjudicates. Everything else in this architecture exists to enforce that one sentence.", options: { color: "34434F" } },
  ], { x: 2.25, y: 4.55, w: 10.25, h: 1.35, fontFace: BF, fontSize: 14, valign: "top", lineSpacingMultiple: 1.16, margin: 0 });
  footer(s, 5);
  s.addNotes("Amber = the human step; navy = the consequential commit. The callout is the crux: a housing specialist commits, the agent never self-adjudicates. The HUD income-limit lookup runs on the non-PII county before masking.");
})();

/* 6. ARCHITECTURE MAP */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Architecture");
  title(s, "Six controls native, three built alongside");
  const rows = [
    ["Verified human + agent identity", "AgentCore Identity — inbound JWT (Cognito / authority IdP)", true],
    ["Deny-by-default authorization", "AgentCore Policy (Cedar) — default-deny + forbid-wins", true],
    ["Least-privilege intersection", "Cedar principal = OAuthUser; group claim + tool-parameter conditions", true],
    ["Tools as governed endpoints", "AgentCore Gateway — Lambda → MCP tools; every call passes Policy", true],
    ["Agent hosting / runtime", "AgentCore Runtime — serverless, session-isolated", true],
    ["Tracing / observability", "AgentCore Observability — OpenTelemetry spans", true],
    ["Fail-closed PII de-identification", "mask_pii tool — Comprehend DetectPiiEntities, before model & audit", false],
    ["Human sign-off gate", "Step Functions waitForTaskToken — bound, single-use approval", false],
    ["Immutable WORM audit", "Append-only DynamoDB + S3 Object Lock — due-process evidence", false],
  ];
  const x = 0.62, w = 12.1, y0 = 1.55, rh = 0.565;
  rows.forEach((r, i) => {
    const y = y0 + i * rh;
    const fill = i % 2 === 0 ? CARD : "ECF1F5";
    s.addShape(p.ShapeType.rect, { x, y, w, h: rh - 0.06, fill: { color: fill }, line: { type: "none" } });
    const c = r[2] ? MINT : AMBER;
    s.addShape(p.ShapeType.roundRect, { x: x + 0.14, y: y + 0.11, w: 1.35, h: 0.32, fill: { color: c }, line: { type: "none" }, rectRadius: 0.16 });
    s.addText(r[2] ? "NATIVE" : "BUILD", { x: x + 0.14, y: y + 0.11, w: 1.35, h: 0.32, align: "center", valign: "middle", color: r[2] ? NAVY : WHITE, fontFace: BF, fontSize: 10.5, bold: true, margin: 0 });
    s.addText(r[0], { x: x + 1.65, y, w: 3.9, h: rh - 0.06, valign: "middle", fontFace: BF, fontSize: 13, bold: true, color: INK, margin: 0 });
    s.addText(r[1], { x: x + 5.65, y, w: w - 5.85, h: rh - 0.06, valign: "middle", fontFace: BF, fontSize: 12, color: "44535F", margin: 0 });
  });
  footer(s, 6);
  s.addNotes("The full nine-control map — identical structure to the PV, benefits, and financial-aid agents. That's the reusable pattern; only the domain tools and one authoritative data source (HUD) change.");
})();

/* 7. GOVERNED FLOW */
(() => {
  const s = p.addSlide(); bg(s, NAVY);
  eyebrow(s, "Runtime behavior", MINT);
  s.addText("How one governed action flows", { x: 0.6, y: 0.45, w: 12, h: 0.8, fontFace: TF, fontSize: 26, bold: true, color: WHITE, margin: 0 });
  const flow = [
    ["1", "Housing specialist authenticates", "Cognito / IdP issues a JWT for the person on whose behalf the agent acts."],
    ["2", "Agent decides to call a tool", "The Strands agent runs on AgentCore Runtime and reaches for a Gateway tool."],
    ["3", "Gateway validates identity", "Inbound auth checks the JWT before anything runs."],
    ["4", "Cedar evaluates — default-deny", "Principal + action + resource + conditions. A deny means the tool never runs — and is auditable."],
    ["5", "Authoritative lookup, then masking", "lookup_income_limit fetches the HUD limit on the non-PII county; mask_pii then de-identifies. Assessment and drafting only ever see masked text."],
    ["6", "Human gate for the commit", "request_signoff opens a Step Functions gate; a second housing specialist approves. Only then does finalize_determination run."],
    ["7", "WORM audit + trace", "Every decision and state change (with the HUD provenance) is written to an immutable record and traced in Observability."],
  ];
  const colW = 5.95, x0 = 0.62, y0 = 1.55, rh = 0.75;
  flow.forEach((f, i) => {
    const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
    const x = x0 + col * (colW + 0.55), y = y0 + row * (rh + 0.12);
    circle(s, x, y, 0.56, i === 5 ? AMBER : i === 6 ? MINT : TEAL, f[0], i === 5 ? NAVY : i === 6 ? NAVY : WHITE, 17);
    s.addText(f[1], { x: x + 0.72, y: y - 0.04, w: colW - 0.75, h: 0.32, fontFace: BF, fontSize: 14, bold: true, color: WHITE, margin: 0 });
    s.addText(f[2], { x: x + 0.72, y: y + 0.28, w: colW - 0.75, h: 0.5, fontFace: BF, fontSize: 11.5, color: ICE, valign: "top", lineSpacingMultiple: 1.05, margin: 0 });
  });
  footer(s, 7);
  s.addNotes("Step 5 (authoritative HUD lookup on the non-PII county, then fail-closed masking) and step 6 (human gate) are the regulated controls; step 4 (Cedar deny-by-default) is the native spine.");
})();

/* 8. PROOF */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Evidence");
  title(s, "Proof, not slideware: validated live on AWS, evidence captured");
  const stats = [["117/117", "automated tests green", MINT], ["2", "clean-account live validation runs captured", TEAL], ["8", "real defects found & fixed by validation", AMBER], ["0", "residual on teardown", NAVY]];
  const sw = 2.9, gap = 0.23, x0 = 0.62, y = 1.5;
  stats.forEach((st, i) => {
    const x = x0 + i * (sw + gap);
    card(s, x, y, sw, 1.35);
    s.addText(st[0], { x, y: y + 0.12, w: sw, h: 0.7, align: "center", fontFace: TF, fontSize: 34, bold: true, color: st[2], margin: 0 });
    s.addText(st[1], { x: x + 0.1, y: y + 0.85, w: sw - 0.2, h: 0.42, align: "center", fontFace: BF, fontSize: 11.5, color: "44535F", margin: 0 });
  });
  card(s, 0.62, 3.15, 12.1, 3.05, CARD, 0.1);
  s.addText("Captured in the repo (evidence/), run on the customer deployment path (AWS CDK) and torn down clean:", { x: 0.95, y: 3.35, w: 11.4, h: 0.4, fontFace: BF, fontSize: 13, bold: true, color: NAVY, margin: 0 });
  const proofs = [
    "Full governed pipeline SUCCEEDED live — intake to committed determination",
    "Live HUD income-limit lookup; provenance signature verified by the workflow",
    "Real PII masking (Comprehend), cryptographically proven fail-closed downstream",
    "Deterministic AMI engine; real Bedrock notice through a Guardrail",
    "Cedar authorization gateway deployed as pure IaC — CREATE_COMPLETE in ENFORCE",
    "No-self-commit — the agent can't finalize; deny-by-default holds",
    "Human sign-off: approver ≠ requester, approval hash-bound to the exact case",
    "Hash-chained WORM audit + exactly-once finalization (replay-safe)",
  ];
  const cw = 5.55, cx = [0.98, 6.9];
  proofs.forEach((t, i) => {
    const col = i < 4 ? 0 : 1, row = i % 4;
    const x = cx[col], yy = 3.85 + row * 0.56;
    circle(s, x, yy, 0.32, MINT, "✓", NAVY, 12);
    s.addText(t, { x: x + 0.44, y: yy - 0.05, w: cw, h: 0.44, valign: "middle", fontFace: BF, fontSize: 12, color: INK, margin: 0 });
  });
  footer(s, 8);
  s.addNotes("Two clean-account validation runs are captured in evidence/ and referenced from VALIDATED_RELEASE.md: the full governed pipeline SUCCEEDED end-to-end on live services (HUD, Comprehend, Secrets Manager, Bedrock, WORM, sign-off, exactly-once finalize), and the AgentCore/Cedar gateway attachment reached CREATE_COMPLETE in ENFORCE as pure CDK IaC. Validation surfaced 8 real defects — every one fixed and regression-tested, which is the point of validating. Zero residual on teardown.");
})();

/* 9. RUNTIME + IDENTITY */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Native on Runtime");
  title(s, "The agent runs on AgentCore Runtime — driven by the housing specialist's identity");
  s.addText("The housing specialist authenticates with Cognito; that same identity flows to the Gateway, so Cedar evaluates the real person. The agent inherits the housing specialist's least-privilege — it can do nothing they aren't allowed to do.",
    { x: 0.62, y: 1.45, w: 12.1, h: 0.75, fontFace: BF, fontSize: 14, color: INK, lineSpacingMultiple: 1.14, margin: 0 });
  card(s, 0.62, 2.5, 5.95, 2.35, CARD, 0.1);
  circle(s, 1.0, 2.85, 0.62, MINT, "✓", NAVY, 20);
  s.addText("Housing-specialist identity", { x: 1.8, y: 2.85, w: 4.6, h: 0.5, fontFace: TF, fontSize: 17, bold: true, color: NAVY, valign: "middle", margin: 0 });
  s.addText("Runs the full governed workflow: intake → look up HUD limit → mask PII → assess vs AMI → draft notice → write audit → request sign-off. The forbidden finalize tool is hidden from the agent entirely by Cedar.",
    { x: 1.0, y: 3.6, w: 5.35, h: 1.15, fontFace: BF, fontSize: 12.5, color: "34434F", valign: "top", lineSpacingMultiple: 1.12, margin: 0 });
  card(s, 6.78, 2.5, 5.95, 2.35, CARD, 0.1);
  circle(s, 7.16, 2.85, 0.62, "C0392B", "✕", WHITE, 20);
  s.addText("Outsider identity", { x: 7.96, y: 2.85, w: 4.6, h: 0.5, fontFace: TF, fontSize: 17, bold: true, color: NAVY, valign: "middle", margin: 0 });
  s.addText("Access denied — zero authorized tools. The agent honestly reports it did nothing: nothing looked up, masked, assessed, drafted, audited, or committed. Deny-by-default holds even when the agent is driving.",
    { x: 7.16, y: 3.6, w: 5.35, h: 1.15, fontFace: BF, fontSize: 12.5, color: "34434F", valign: "top", lineSpacingMultiple: 1.12, margin: 0 });
  const extras = [["Observable", "OpenTelemetry spans + structured logs per step, correlated to the identity, in CloudWatch."], ["Decoupled", "Stable identity + dynamic gateway discovery: the runtime survives redeploys untouched."]];
  extras.forEach((e, i) => {
    const x = 0.62 + i * 6.16;
    s.addShape(p.ShapeType.roundRect, { x, y: 5.1, w: 5.95, h: 1.0, fill: { color: NAVY }, line: { type: "none" }, rectRadius: 0.09, shadow: sh() });
    s.addText(e[0].toUpperCase(), { x: x + 0.3, y: 5.24, w: 5.4, h: 0.34, fontFace: BF, fontSize: 12, bold: true, color: MINT, charSpacing: 1.5, margin: 0 });
    s.addText(e[1], { x: x + 0.3, y: 5.56, w: 5.4, h: 0.5, fontFace: BF, fontSize: 12, color: ICE, valign: "top", lineSpacingMultiple: 1.05, margin: 0 });
  });
  footer(s, 9);
  s.addNotes("Proven live: the agent runs on Runtime under a real Cognito identity, and governance holds on the real principal. Outsider proves deny-by-default even when the agent drives.");
})();

/* 10. LAST-MILE CONTROLS */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "The regulated last mile", AMBER);
  title(s, "Three controls we build on top — the review-passing difference");
  const cards = [
    ["Fail-closed PII de-identification", "Comprehend de-identifies the application before the model or the audit sees it. If masking can't run, assessment and drafting are blocked — no un-masked PII is ever emitted.", "Privacy Act", TEAL],
    ["Human sign-off gate", "Committing a determination is never an inline tool call. A Step Functions gate pauses for a different qualified housing specialist, who approves with a bound, single-use token.", "U.S. Housing Act · separation of duties", AMBER],
    ["Immutable WORM audit", "Append-only DynamoDB + S3 Object Lock capture INTENT → COMMITTED with the HUD provenance. The principal that writes evidence is denied delete, update, and bypass.", "Program-review & hearing evidence", MINT],
  ];
  const w = 3.86, gap = 0.24, x0 = 0.62, y = 1.75, h = 4.2;
  cards.forEach((c, i) => {
    const x = x0 + i * (w + gap);
    card(s, x, y, w, h, CARD, 0.1);
    circle(s, x + 0.34, y + 0.36, 0.72, c[3], String(i + 1));
    s.addText(c[0], { x: x + 1.2, y: y + 0.42, w: w - 1.35, h: 0.62, fontFace: TF, fontSize: 15, bold: true, color: NAVY, valign: "middle", lineSpacingMultiple: 0.98, margin: 0 });
    s.addText(c[2], { x: x + 0.34, y: y + 1.35, w: w - 0.68, h: 0.36, fontFace: BF, fontSize: 11, bold: true, color: c[3], margin: 0 });
    s.addText(c[1], { x: x + 0.34, y: y + 1.85, w: w - 0.68, h: 2.1, fontFace: BF, fontSize: 12.6, color: "34434F", valign: "top", lineSpacingMultiple: 1.15, margin: 0 });
  });
  s.addText("AgentCore's Observability traces are for operations — not tamper-proof evidence. That gap is exactly why the WORM audit is a control, not a log.",
    { x: 0.62, y: 6.2, w: 12.1, h: 0.4, fontFace: BF, fontSize: 12.5, italic: true, color: TEAL, margin: 0 });
  footer(s, 10);
  s.addNotes("These three are where a governed agent earns a program reviewer's — and a hearing officer's — trust. Each maps to a named requirement.");
})();

/* 11. WHY IT MATTERS FOR AWS */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Strategic value");
  title(s, "Why this matters for AWS");
  const items = [
    ["Wins the state/local government bar", "Housing authorities carry strict Privacy Act, due-process, and HUD program-integrity requirements, plus StateRAMP — native governance is the deciding factor, and AWS already holds the compliance footprint.", TEAL],
    ["A repeatable pattern, proven four times", "The same governed chassis produced the pharmacovigilance, benefits, financial-aid, and housing agents from one template — swap domain logic, Cedar policies, and one authoritative data source.", MINT],
    ["Low blast radius, high credibility", "One deep, proven hero per vertical beats a claim of forty shallow agents. Reference-grade, not vaporware.", AMBER],
    ["Honest by construction", "It's clear about what's proven vs. engagement work — exactly what authorities and their auditors trust.", NAVY],
  ];
  const w = 5.95, gap = 0.24, x0 = 0.62, y0 = 1.65, h = 2.05;
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = x0 + col * (w + gap), y = y0 + row * (h + 0.24);
    card(s, x, y, w, h, CARD, 0.1);
    circle(s, x + 0.34, y + 0.36, 0.6, it[2], String(i + 1));
    s.addText(it[0], { x: x + 1.12, y: y + 0.32, w: w - 1.3, h: 0.72, fontFace: TF, fontSize: 15, bold: true, color: NAVY, valign: "middle", lineSpacingMultiple: 0.98, margin: 0 });
    s.addText(it[1], { x: x + 0.34, y: y + 1.18, w: w - 0.66, h: 0.82, fontFace: BF, fontSize: 12.4, color: "34434F", valign: "top", lineSpacingMultiple: 1.12, margin: 0 });
  });
  footer(s, 11);
  s.addNotes("Ties the technical work to AWS strategy: wins regulated state/local deals, reusable (now proven four times), low-risk, credible because honest.");
})();

/* 12. HONESTY BOUNDARY */
(() => {
  const s = p.addSlide(); bg(s, CLOUD);
  eyebrow(s, "Credibility");
  title(s, "What's proven vs. what's engagement work");
  card(s, 0.62, 1.6, 5.95, 4.15, CARD, 0.1);
  s.addText("THE ACCELERATOR OWNS  ·  PROVEN", { x: 0.95, y: 1.85, w: 5.3, h: 0.4, fontFace: BF, fontSize: 12.5, bold: true, color: MINT, charSpacing: 1, margin: 0 });
  ["The agent + the Cedar policies", "The tools + fail-closed masking", "The deterministic AMI engine + live HUD lookup", "The human-gate workflow + WORM audit", "Reproducible IaC + one-command demo", "The documentation set"].forEach((t, i) => {
    const y = 2.45 + i * 0.53;
    circle(s, 0.98, y, 0.32, MINT, "✓", NAVY, 12);
    s.addText(t, { x: 1.42, y: y - 0.05, w: 4.95, h: 0.44, valign: "middle", fontFace: BF, fontSize: 12.5, color: INK, margin: 0 });
  });
  card(s, 6.78, 1.6, 5.95, 4.15, CARD, 0.1);
  s.addText("THE AUTHORITY OWNS  ·  ENGAGEMENT WORK", { x: 7.11, y: 1.85, w: 5.4, h: 0.4, fontFace: BF, fontSize: 12.5, bold: true, color: AMBER, charSpacing: 1, margin: 0 });
  ["IdP federation + housing-specialist role mapping", "Connectors to the PHA system of record (EIV / PIC / HMIS)", "Authoritative admission rules & preferences (legal review)", "Notice language, informal-hearing rights, appeal process", "Computer-system validation + authorization to operate (StateRAMP)"].forEach((t, i) => {
    const y = 2.45 + i * 0.62;
    circle(s, 7.14, y, 0.32, AMBER, "⚙", NAVY, 12);
    s.addText(t, { x: 7.58, y: y - 0.06, w: 5.0, h: 0.56, valign: "middle", fontFace: BF, fontSize: 12.5, color: INK, lineSpacingMultiple: 1.0, margin: 0 });
  });
  s.addShape(p.ShapeType.roundRect, { x: 0.62, y: 5.95, w: 12.1, h: 0.7, fill: { color: NAVY }, line: { type: "none" }, rectRadius: 0.09 });
  s.addText("The income limits are live from HUD; the admission rules and local preferences shipped here are illustrative configuration — not authoritative rules. Nothing is production-certified on day one, and saying so is the credibility.", { x: 0.62, y: 5.95, w: 12.1, h: 0.7, align: "center", valign: "middle", fontFace: BF, fontSize: 13, bold: true, italic: true, color: WHITE, margin: 0 });
  footer(s, 12);
  s.addNotes("We own the pattern and the proof; the housing authority owns certification, connectors, and the authoritative admission rules. HUD income limits are live and authoritative; the admission thresholds are illustrative configuration.");
})();

/* 13. ROADMAP + ASK */
(() => {
  const s = p.addSlide(); bg(s, NAVY);
  s.addShape(p.ShapeType.ellipse, { x: 10.2, y: 4.6, w: 5.5, h: 5.5, fill: { color: NAVY2 }, line: { type: "none" } });
  eyebrow(s, "Roadmap", MINT);
  s.addText("One governed pattern, four verticals proven", { x: 0.6, y: 0.45, w: 12, h: 0.85, fontFace: TF, fontSize: 26, bold: true, color: WHITE, margin: 0 });
  s.addText("Four heroes now run on the same governed chassis — identity, Cedar, Gateway, Runtime, and the three last-mile controls — produced from one reusable template. Housing is the second State & Local Government proof; each new vertical is a domain-logic swap away.",
    { x: 0.62, y: 1.4, w: 11.6, h: 0.8, fontFace: BF, fontSize: 14, color: ICE, lineSpacingMultiple: 1.14, margin: 0 });
  const verts = [["HCLS", "Pharmacovigilance", "PROVEN", MINT], ["SLG", "Benefits Eligibility", "PROVEN", MINT], ["EDU", "Financial Aid", "PROVEN", MINT], ["SLG", "Housing Eligibility", "PROVEN", MINT]];
  const w = 2.9, gap = 0.23, x0 = 0.62, y = 2.5;
  verts.forEach((v, i) => {
    const x = x0 + i * (w + gap);
    const highlight = i === 3;
    s.addShape(p.ShapeType.roundRect, { x, y, w, h: 1.75, fill: { color: NAVY2 }, line: { color: highlight ? AMBER : v[3], width: highlight ? 2 : 1.25 }, rectRadius: 0.1, shadow: sh() });
    s.addText(v[0], { x, y: y + 0.22, w, h: 0.5, align: "center", fontFace: TF, fontSize: 22, bold: true, color: WHITE, margin: 0 });
    s.addText(v[1], { x: x + 0.1, y: y + 0.78, w: w - 0.2, h: 0.55, align: "center", fontFace: BF, fontSize: 12.5, color: ICE, valign: "top", lineSpacingMultiple: 1.0, margin: 0 });
    s.addShape(p.ShapeType.roundRect, { x: x + w / 2 - 0.6, y: y + 1.36, w: 1.2, h: 0.3, fill: { color: v[3] }, line: { type: "none" }, rectRadius: 0.15 });
    s.addText(v[2], { x: x + w / 2 - 0.6, y: y + 1.36, w: 1.2, h: 0.3, align: "center", valign: "middle", color: NAVY, fontFace: BF, fontSize: 10, bold: true, margin: 0 });
  });
  s.addText("THE ASK", { x: 0.62, y: 4.65, w: 4, h: 0.35, fontFace: BF, fontSize: 12.5, bold: true, color: MINT, charSpacing: 2, margin: 0 });
  const asks = [["1", "Internal demo", "Stand up the stack live and walk leadership through the captured validation evidence."], ["2", "Government workshops", "Take the pattern to housing-authority and SLG accounts as a reference architecture."], ["3", "Scoped pilot", "A pilot on synthetic applications with a named housing authority, boundary made explicit."]];
  asks.forEach((a, i) => {
    const x = 0.62 + i * 4.06;
    circle(s, x, 5.15, 0.5, MINT, a[0], NAVY, 16);
    s.addText(a[1], { x: x + 0.66, y: 5.13, w: 3.3, h: 0.34, fontFace: BF, fontSize: 14, bold: true, color: WHITE, margin: 0 });
    s.addText(a[2], { x: x + 0.66, y: 5.47, w: 3.3, h: 0.9, fontFace: BF, fontSize: 11.5, color: ICE, valign: "top", lineSpacingMultiple: 1.08, margin: 0 });
  });
  s.addText("Governed agentic AI, native on AWS — proven where the bar is highest.", { x: 0.62, y: 6.65, w: 12, h: 0.4, fontFace: TF, fontSize: 15, italic: true, bold: true, color: MINT, margin: 0 });
  s.addNotes("Close on the multiplier: one pattern, four verticals proven, two in SLG. The ask is a three-step path from internal demo to a scoped, synthetic-data pilot with a housing authority.");
})();

p.writeFile({ fileName: "Housing-AgentCore-Leadership.pptx" }).then((f) => console.log("wrote", f));
