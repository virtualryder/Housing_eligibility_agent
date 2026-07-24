import json
import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError

import sanitized  # server-issued sanitized-artifact verification + content binding (P0-1)

# Housing core tools behind the `hou-core` Gateway target:
#   - draft_notice            -> REAL Bedrock (Converse) eligibility determination notice from a de-identified case
#   - finalize_determination  -> deny-only stub (the human sign-off gate owns the real commit)
#   - refer_fraud             -> deny-only stub (a human-only decision)
# Branch on the input shape (finalize carries case_id; refer carries fraud_case_id; draft carries case/deidentified).

DRAFT_MODEL_ID = os.environ.get("DRAFT_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")

_SYSTEM = (
    "You draft a HOUSING ASSISTANCE ELIGIBILITY DETERMINATION NOTICE (Housing Choice Voucher / public "
    "housing) for a housing specialist to review. You are given an ALREADY DE-IDENTIFIED case plus an "
    "eligibility determination. Write a clear, plain-language notice (roughly 120-250 words). Rules: "
    "(1) Preserve every [REDACTED:...] placeholder verbatim; never guess redacted values. (2) State the "
    "determination (eligible/ineligible/needs review), the income category (extremely low / very low / "
    "low / over income), and the plain reason. (3) Note any waitlist/next-step or verification step. "
    "(4) Include a short, neutral statement of the applicant's right to an informal review/hearing. "
    "(5) This is a DRAFT for human review, not a final decision. Output the notice text only."
)


def _coerce(event):
    e = event or {}
    if isinstance(e, str):
        try:
            e = json.loads(e)
        except Exception:
            e = {"_raw": e}
    return e


def _draft(e):
    # P0-1: drafting consumes the sanitized TEXT, so it enforces BOTH controls:
    #   (1) proof-of-masking — a mask_pii-signed sanitized_ref must verify (boolean never accepted);
    #   (2) content binding — the case text used must hash to the signed digest. Preferred channel is
    #       the server-side artifact store (content never re-enters the model); a model-passed `case`
    #       is accepted ONLY if it is byte-identical to the signed masked artifact.
    ref = sanitized.parse_ref(e.get("sanitized_ref"))
    if not sanitized.verify_ref(ref):
        return {"error": ("refused: de-identification not proven — a valid sanitized_ref signed by "
                          "mask_pii is required; a deidentified boolean is not accepted as proof (P0-1)"),
                "drafted_by": None, "deidentified_input": e.get("deidentified"),
                "sanitized_ref_verified": False}
    raw_case = e.get("case", "")
    if not isinstance(raw_case, str):
        raw_case = json.dumps(raw_case, ensure_ascii=False)
    masked_text = sanitized.load_text(ref, candidate_text=raw_case)
    if masked_text is None:
        return {"error": ("refused: case content does not match the signed sanitized artifact "
                          "(hash mismatch — possible substitution of unmasked or altered content)"),
                "drafted_by": None, "sanitized_ref_verified": True, "content_bound": False}
    # Non-PII determination context may accompany the masked case (it carries no applicant identifiers).
    determination = e.get("determination", "")
    if not isinstance(determination, str):
        determination = json.dumps(determination, ensure_ascii=False)
    case = masked_text if not determination else (masked_text + "\n\nDetermination:\n" + determination)
    kwargs = dict(
        modelId=DRAFT_MODEL_ID,
        system=[{"text": _SYSTEM}],
        messages=[{"role": "user", "content": [{"text": "De-identified case + determination:\n" + case}]}],
        inferenceConfig={"maxTokens": 700, "temperature": 0.2},
    )
    if GUARDRAIL_ID:
        kwargs["guardrailConfig"] = {"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION}
    try:
        br = boto3.client("bedrock-runtime")
        resp = br.converse(**kwargs)
        notice = resp["output"]["message"]["content"][0]["text"].strip()
        if resp.get("stopReason") == "guardrail_intervened" and not notice:
            return {"error": "output guardrail blocked the draft (fail-closed)", "drafted_by": None, "guardrail": "BLOCKED"}
        out = {"drafted_by": DRAFT_MODEL_ID, "chars": len(notice),
               "guardrail_applied": bool(GUARDRAIL_ID), "deidentified_input": True}
        # R3-2 pass-by-reference: with a case store configured, the notice (content, even though
        # de-identified) is stored server-side and only an opaque notice_ref returns into Step
        # Functions state; the approver fetches it by ref. Without a store (dev/direct calls) the
        # text returns inline as before.
        import os
        if os.environ.get("CASE_TABLE"):
            import case_store
            out["notice_ref"] = case_store.put_case(notice, kind="notice")
        else:
            out["notice"] = notice
        return out
    except (BotoCoreError, ClientError, KeyError, IndexError) as exc:
        return {"error": "draft failed: " + type(exc).__name__ + ": " + str(exc), "drafted_by": None}


def handler(event, context):
    e = _coerce(event)
    if "fraud_case_id" in e:
        # refer_fraud is a consequential, HUMAN-ONLY action. The agent can never refer a case as suspected
        # fraud; a qualified investigator/official does. Forbidden to the agent by Cedar (no_self_fraud_referral)
        # and refused here too (defense in depth).
        return {"error": "refused: a fraud referral is a human-only decision; the agent cannot refer",
                "fraud_case_id": e.get("fraud_case_id"), "referred": False}
    if "case_id" in e and "case" not in e:
        # finalize_determination is never a real inline call — the human sign-off gate owns it.
        return {"error": "refused: finalize_determination must go through the human sign-off gate",
                "case_id": e.get("case_id"), "committed": False}
    if "case" in e or "deidentified" in e or "sanitized_ref" in e:
        return _draft(e)
    return {"ok": True, "received": e, "note": "housing core tool"}
