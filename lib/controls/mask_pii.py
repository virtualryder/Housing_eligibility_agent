import json
import boto3
from botocore.exceptions import BotoCoreError, ClientError

import sanitized  # server-issued sanitized-artifact references (P0-1; bundled beside this handler)

# mask_pii — fail-closed general PII de-identification via Amazon Comprehend DetectPiiEntities
# (name, SSN, address, DOB, phone, email, bank/routing, etc.). Reusable control for non-health
# verticals (the mask_phi analog without Comprehend Medical). FAIL-CLOSED: if detection cannot run,
# NO masked text is returned and deidentified=false — nothing downstream may proceed.
#
# P0-1: on success this control MINTS a SIGNED `sanitized_ref` over the exact masked content
# (see lib/controls/sanitized.py) and, when SANITIZED_TABLE is configured, persists the masked payload
# server-side. Downstream tools authorize on the VERIFIED reference — the `deidentified` boolean is
# retained only as the coarse Cedar gateway gate and is never accepted as proof by any tool.

def _coerce(e):
    e = e or {}
    if isinstance(e, str):
        try:
            return json.loads(e)
        except Exception:
            return {"case": e}
    return e

def handler(event, context):
    e = _coerce(event)
    case = e.get("case", e.get("application", ""))
    if not isinstance(case, str):
        case = json.dumps(case, ensure_ascii=False)
    if not case.strip():
        return {"deidentified": False, "masked_case": None, "error": "empty input"}
    try:
        cm = boto3.client("comprehend")
        ents = cm.detect_pii_entities(Text=case[:99000], LanguageCode="en").get("Entities", [])
    except (BotoCoreError, ClientError) as exc:
        # Fail-closed: never emit unmasked text if detection fails.
        return {"deidentified": False, "masked_case": None,
                "error": "pii detection failed: %s" % type(exc).__name__}
    # redact spans back-to-front so offsets stay valid
    spans = sorted(ents, key=lambda x: x.get("BeginOffset", 0), reverse=True)
    masked = case
    for ent in spans:
        b, end = ent.get("BeginOffset"), ent.get("EndOffset")
        t = ent.get("Type", "PII")
        if b is None or end is None:
            continue
        masked = masked[:b] + ("[REDACTED:%s]" % t) + masked[end:]
    ref = sanitized.mint_ref(masked, engine="comprehend:DetectPiiEntities",
                             entities_masked=len(ents), tenant=e.get("tenant", "default"))
    return {"deidentified": True, "masked_case": masked, "entities_masked": len(ents),
            "masked_by": "comprehend:DetectPiiEntities",
            "sanitized_ref": ref,
            "note": ("pass sanitized_ref (JSON) to assess/recertify/overpayment/draft — it is the "
                     "server-signed proof of masking; the deidentified boolean alone is not accepted")}
