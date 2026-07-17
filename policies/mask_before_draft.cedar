// mask_before_draft  (kind: forbid  ·  validation: IGNORE_ALL_FINDINGS)
// The model only ever sees de-identified text. draft_notice is forbidden unless deidentified == true (set only by mask_pii).
forbid(
  principal,
  action == AgentCore::Action::"hou-core___draft_notice",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/hou-housing-gw"
)
unless { context.input.deidentified == true };
