// mask_before_overpayment  (kind: forbid  ·  validation: IGNORE_ALL_FINDINGS)
// No overpayment calculation on un-masked data. detect_overpayment is forbidden unless deidentified == true (set only by mask_pii).
forbid(
  principal,
  action == AgentCore::Action::"detect-overpayment___detect_overpayment",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:111122223333:gateway/hou-housing-gw"
)
unless { context.input.deidentified == true };
