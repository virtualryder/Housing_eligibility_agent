# Pilot scope (P0-10) — one program, one jurisdiction, one year

**What this pilot IS:** governed **intake assistance, data-completeness checking, authoritative HUD
income-limit lookup, preliminary income screening (AMI categorization), and draft determination
notices** for **one Public Housing Authority (PHA)**, for the **Housing Choice Voucher (HCV / Section
8) program only**, against **one HUD income-limit year**, with **every determination committed by a
housing specialist** at the human sign-off gate.

**What this pilot is NOT (do not present it as):** automated eligibility adjudication. Full HCV
eligibility (citizenship/eligible-immigration status, student rules, SSN documentation, criminal
history, lifetime sex-offender and methamphetamine restrictions, assets/deductions/adjusted income,
local preferences, waiting-list rules, reasonable accommodations, VAWA protections, informal
review/hearing workflow, portability, EIV discrepancy resolution, the PHA administrative plan) is the
PHA's process, out of scope, and remains with the housing specialist.

**Stubs, explicitly:** `verify_income_source` and `connect_system_of_record` (EIV / PIC / HMIS) are
STUBS (`manifest.yaml honesty_boundary`). No claim of system-of-record verification is made until a
customer engagement wires and validates them.

**Pilot success metrics** (measure against the PHA's own baseline; no savings promised in advance):
median intake handling time; reviewer active time per case; draft-notice acceptance without material
edits; missing-field detection recall; rules-engine agreement with specialist decisions on the income
screen (target ~100% for the codified rule); on-time processing; human override rate with reason
codes; security-control failure rate (target: zero consequential bypasses).

*Configuration for the pilot PHA (county entityids, income-limit year, retention profile, IdP) is an
engagement-time worksheet; nothing in this repo hardcodes a jurisdiction.*
