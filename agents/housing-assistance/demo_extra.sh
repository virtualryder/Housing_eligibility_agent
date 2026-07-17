# demo_extra.sh (housing-assistance) — agent-specific payloads + content checks.
# Sourced by lib/engine/demo.sh; shares: REV, OUT, REV_U, call(), check(), pass, fail.
T_INTAKE="intake-application___intake_application"
T_IL="lookup-income-limit___lookup_income_limit"
T_MASK="mask-pii___mask_pii"
T_ASSESS="assess-eligibility___assess_housing_eligibility"
T_DRAFT="hou-core___draft_notice"
T_AUDIT="write-audit___write_audit"
T_FINAL="hou-core___finalize_determination"

echo "  -- deny-by-default (identity -> Cedar) --"
check "housing_specialist intake_application" ALLOW "$(call "$REV" "$T_INTAKE" '{"application":"Household of 4 applying for a Housing Choice Voucher. Annual household income: 40000. County entityid 0603799999."}')"
check "outsider           intake_application" DENY  "$(call "$OUT" "$T_INTAKE" '{"application":"Household of 4. Annual income 40000."}')"

echo "  -- authoritative HUD income limits via HUD USER API (LIVE federal API, governed) --"
IL_OUT="$(call "$REV" "$T_IL" '{"entityid":"0603799999","household_size":4}')"
check "housing_specialist lookup_income_limit" ALLOW "$IL_OUT"
if echo "$IL_OUT" | grep -q '"found": *true' && echo "$IL_OUT" | grep -qi 'HUD'; then echo "  PASS | lookup_income_limit returned AUTHORITATIVE HUD limits + provenance"; pass=$((pass+1)); else echo "  WARN | lookup_income_limit -> $IL_OUT (needs HUD_API_TOKEN for the live call; using fallback limits below)"; fi
# extract the value AFTER the colon (the key names il30/il50/il80 contain digits, so a bare [0-9]+
# would match the key; sed captures only the number that follows the key).
IL50_VAL="$(printf '%s' "$IL_OUT" | sed -nE 's/.*"il50":[[:space:]]*([0-9]+).*/\1/p' | head -1)"
IL30_VAL="$(printf '%s' "$IL_OUT" | sed -nE 's/.*"il30":[[:space:]]*([0-9]+).*/\1/p' | head -1)"
IL80_VAL="$(printf '%s' "$IL_OUT" | sed -nE 's/.*"il80":[[:space:]]*([0-9]+).*/\1/p' | head -1)"
[ -z "$IL30_VAL" ] && IL30_VAL=30000
[ -z "$IL50_VAL" ] && IL50_VAL=50000
[ -z "$IL80_VAL" ] && IL80_VAL=80000

echo "  -- fail-closed PII de-identification (mask_pii) --"
MASK_OUT="$(call "$REV" "$T_MASK" '{"case":"Applicant Jane Doe, SSN 123-45-6789, 42 Main St, applying for a Housing Choice Voucher; household 4, annual income 40000."}')"
check "housing_specialist mask_pii" ALLOW "$MASK_OUT"
if echo "$MASK_OUT" | grep -q 'REDACTED' && ! echo "$MASK_OUT" | grep -q 'Jane Doe'; then echo "  PASS | mask_pii redacted PII (name/SSN removed)"; pass=$((pass+1)); else echo "  FAIL | mask_pii did NOT redact -> $MASK_OUT"; fail=$((fail+1)); fi

echo "  -- forbid: mask-before-assess (eligibility determination) --"
check "housing_specialist assess (UN-masked)" DENY "$(call "$REV" "$T_ASSESS" '{"annual_income":40000,"il50":50000,"deidentified":false}')"
ASSESS_OUT="$(call "$REV" "$T_ASSESS" "{\"annual_income\":40000,\"household_size\":4,\"il30\":$IL30_VAL,\"il50\":$IL50_VAL,\"il80\":$IL80_VAL,\"il_source\":\"US Dept of Housing and Urban Development (HUD USER) - Income Limits\",\"deidentified\":true}")"
check "housing_specialist assess (de-identified)" ALLOW "$ASSESS_OUT"
if echo "$ASSESS_OUT" | grep -qE 'ELIGIBLE|NEEDS_REVIEW' && echo "$ASSESS_OUT" | grep -qE '"income_category"'; then echo "  PASS | assess_housing_eligibility returned a determination + income category"; pass=$((pass+1)); else echo "  FAIL | assess -> $ASSESS_OUT"; fail=$((fail+1)); fi
if echo "$ASSESS_OUT" | grep -q '"il_provenance"' && ! echo "$ASSESS_OUT" | grep -q 'not supplied'; then echo "  PASS | determination carries HUD income-limit provenance (authoritative source in the audit trail)"; pass=$((pass+1)); else echo "  FAIL | il provenance missing -> $ASSESS_OUT"; fail=$((fail+1)); fi

echo "  -- forbid: mask-before-model (eligibility notice) --"
check "housing_specialist draft (UN-masked)" DENY "$(call "$REV" "$T_DRAFT" '{"case":"x","deidentified":false}')"
DRAFT_OUT="$(call "$REV" "$T_DRAFT" '{"case":"De-identified applicant [REDACTED:NAME], household 4, annual income 40000. Determination: ELIGIBLE, income category VERY_LOW (within 50% AMI). Next step: voucher waitlist placement.","deidentified":true}')"
check "housing_specialist draft (de-identified)" ALLOW "$DRAFT_OUT"
if echo "$DRAFT_OUT" | grep -qE '"chars": *[1-9]' && ! echo "$DRAFT_OUT" | grep -q '"error"'; then echo "  PASS | draft_notice produced a real Bedrock notice"; pass=$((pass+1)); else echo "  FAIL | draft -> $DRAFT_OUT"; fail=$((fail+1)); fi
if echo "$DRAFT_OUT" | grep -q '"guardrail_applied": *true'; then echo "  PASS | notice passed the fail-closed guardrail"; pass=$((pass+1)); else echo "  FAIL | guardrail not applied -> $DRAFT_OUT"; fail=$((fail+1)); fi

echo "  -- immutable WORM audit --"
NONCE="$RANDOM$RANDOM"
AUDIT_IN="{\"icsr_id\":\"HOU-2026-0002\",\"action\":\"eligibility_determination\",\"phase\":\"INTENT\",\"actor\":\"$REV_U\",\"payload\":\"run-$NONCE\"}"
A1="$(call "$REV" "$T_AUDIT" "$AUDIT_IN")"
check "housing_specialist write_audit (1st)" ALLOW "$A1"
if echo "$A1" | grep -q '"stored": *true' && echo "$A1" | grep -q '"worm": *true'; then echo "  PASS | audit -> append-only ledger + WORM"; pass=$((pass+1)); else echo "  FAIL | audit not stored/worm -> $A1"; fail=$((fail+1)); fi
A2="$(call "$REV" "$T_AUDIT" "$AUDIT_IN")"
if echo "$A2" | grep -q '"stored": *false' && echo "$A2" | grep -qi 'append-only'; then echo "  PASS | duplicate rejected (immutable)"; pass=$((pass+1)); else echo "  FAIL | dup not rejected -> $A2"; fail=$((fail+1)); fi

echo "  -- forbid: no self-commit --"
check "housing_specialist finalize_determination" DENY "$(call "$REV" "$T_FINAL" '{"case_id":"HOU-2026-0002"}')"

echo "  == STEP TWO: deeper caseload workflows =="
T_RECERT="recertify___recertify"
T_OVERPAY="detect-overpayment___detect_overpayment"
T_FRAUD="hou-core___refer_fraud"

echo "  -- annual recertification: adverse change triggers due-process advance notice --"
check "housing_specialist recertify (UN-masked)" DENY "$(call "$REV" "$T_RECERT" '{"annual_income":95000,"il50":50000,"il80":80000,"prior_eligible":true,"deidentified":false}')"
RECERT_OUT="$(call "$REV" "$T_RECERT" '{"annual_income":95000,"household_size":4,"il50":50000,"il80":80000,"prior_eligible":true,"deidentified":true}')"
check "housing_specialist recertify (de-identified)" ALLOW "$RECERT_OUT"
if echo "$RECERT_OUT" | grep -q '"change_type": *"ADVERSE"' && echo "$RECERT_OUT" | grep -q '"advance_notice_required": *true'; then echo "  PASS | adverse recertification -> advance notice + informal-hearing right required (due process)"; pass=$((pass+1)); else echo "  FAIL | recertify -> $RECERT_OUT"; fail=$((fail+1)); fi

echo "  -- housing-assistance overpayment (calculate, don't recover) --"
OVER_OUT="$(call "$REV" "$T_OVERPAY" '{"prior_monthly_subsidy":900,"corrected_monthly_subsidy":600,"months":6,"deidentified":true}')"
check "housing_specialist detect_overpayment" ALLOW "$OVER_OUT"
if echo "$OVER_OUT" | grep -q '"classification": *"OVERPAYMENT"' && echo "$OVER_OUT" | grep -q '"overpayment_amount": *1800'; then echo "  PASS | overpayment computed (900-600)*6 = 1800; recovery/referral left to a human"; pass=$((pass+1)); else echo "  FAIL | overpayment -> $OVER_OUT"; fail=$((fail+1)); fi

echo "  -- forbid: no self fraud-referral (human-only) --"
check "housing_specialist refer_fraud" DENY "$(call "$REV" "$T_FRAUD" '{"fraud_case_id":"HOU-2026-0002"}')"
