// mask_before_recertify  (kind: forbid  ·  validation: IGNORE_ALL_FINDINGS)
// No annual/interim re-certification on un-masked data. recertify is forbidden unless deidentified == true (set only by mask_pii).
forbid(
  principal,
  action == AgentCore::Action::"recertify___recertify",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/hou-housing-gw"
)
unless { context.input.deidentified == true };
