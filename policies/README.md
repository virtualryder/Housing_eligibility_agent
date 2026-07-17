# Cedar policies (the governance core)

These seven Cedar statements are the authorization model for the agent. They are the
**single most important artifact in the repo** — everything else exists to enforce them.

They are **declared in `agents/housing-assistance/manifest.yaml`** (under `policies:`) and
rendered to Cedar by `lib/engine/render.py` at deploy time, then attached to the AgentCore
Policy engine. The `.cedar` files here are the rendered, human-readable form, checked in so the
model is reviewable without running a deploy. The account id (`111122223333`) and gateway ARN
are placeholders — the deploy substitutes the real account and the gateway ARN that only exists
after the gateway is created.

| Policy | Kind | What it enforces |
|---|---|---|
| `housing_specialist_permit` | permit | Only a member of the `housing_specialist` Cognito group may use any tool. Everything else is denied by default. |
| `mask_before_assess` | forbid | `assess_housing_eligibility` cannot run on data that hasn't been de-identified (`deidentified == true`). |
| `mask_before_recertify` | forbid | `recertify` (annual/interim re-certification) cannot run on un-masked data. |
| `mask_before_overpayment` | forbid | `detect_overpayment` cannot run on un-masked data. |
| `mask_before_draft` | forbid | `draft_notice` cannot run on un-masked data — the model only sees de-identified text. |
| `no_self_commit` | forbid | The agent can never call `finalize_determination`; committing a determination is reachable **only** through the human sign-off gate. |
| `no_self_fraud_referral` | forbid | The agent can never call `refer_fraud`; a suspected-fraud referral is a human-only decision. |

Two rules of the engine make this airtight:

1. **Deny-by-default.** No statement, no access. `housing_specialist_permit` is the only broad grant.
2. **Forbid wins.** A `forbid` overrides any `permit`, so the forbids cannot be circumvented by the
   permit — masking-before-processing and no-self-commit always hold.

The demo (`bash lib/engine/demo.sh agents/housing-assistance`) proves each of these live in
ENFORCE mode, and each denial names the exact policy that fired.
