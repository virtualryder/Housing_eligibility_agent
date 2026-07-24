"""WorkflowStack — the DETERMINISTIC workflow controller (P0-2) + the human sign-off gate.

The regulated pipeline is a Step Functions STANDARD state machine — the model no longer decides the
compliance sequence. Every transition is gated on machine-verifiable evidence via the workflow_guards
Lambda (provenance signature, sanitized_ref signature, rules output); a failed guard routes to
ManualReview (NEEDS_REVIEW), never onward:

  RECEIVED → Extract → [extracted?] → Lookup → [authoritative?] → Mask → [deidentified?]
    → Assess → [rules_executed?] → Draft → AuditIntent → HumanSignoff (waitForTaskToken, SoD)
    → COMMITTED

The LLM operates INSIDE bounded steps only (the drafter Lambda invokes Bedrock; extraction is
deterministic). The sign-off gate keeps the existing separation-of-duties semantics: signoff_register
stores the task token for a DIFFERENT verified approver; finalize runs only after approval."""
import aws_cdk as cdk
from aws_cdk import aws_stepfunctions as sfn, aws_stepfunctions_tasks as tasks
from constructs import Construct


class WorkflowStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, prefix: str, compute, data, **kw):
        super().__init__(scope, cid, **kw)

        def invoke(name, fn, payload, result_path):
            return tasks.LambdaInvoke(self, name, lambda_function=fn,
                                      payload=sfn.TaskInput.from_object(payload),
                                      result_selector={"out.$": "$.Payload"},
                                      result_path=result_path)

        def guard(name, guard_name, payload):
            return tasks.LambdaInvoke(self, name, lambda_function=compute.guards,
                                      payload=sfn.TaskInput.from_object(
                                          {"guard": guard_name, **payload}),
                                      result_selector={"ok.$": "$.Payload.ok",
                                                       "reason.$": "$.Payload.reason"},
                                      result_path=f"$.guards.{guard_name}")

        manual_review = sfn.Succeed(self, "ManualReview",
                                    comment="Fail-closed: evidence missing/unverified -> NEEDS_REVIEW "
                                            "for a housing specialist; no automated outcome.")

        extract = invoke("Extract", compute.intake,
                         {"application.$": "$.application"}, "$.extract")
        g_extracted = guard("GuardExtracted", "extracted", {"fields.$": "$.extract.out.fields"})

        lookup = invoke("LookupIncomeLimit", compute.lookup,
                        {"entityid.$": "$.extract.out.fields.entityid",
                         "household_size.$": "$.extract.out.fields.household_size"}, "$.lookup")
        # Pass the WHOLE lookup output: a source-down lookup has no limit keys, and judging that is
        # the guard's job — a brittle JSONPath here would turn fail-closed into a runtime error.
        g_auth = guard("GuardAuthoritative", "authoritative",
                       {"lookup.$": "$.lookup.out",
                        "household_size.$": "$.extract.out.fields.household_size"})

        mask = invoke("MaskPii", compute.mask, {"case.$": "$.application"}, "$.mask")
        g_deid = guard("GuardDeidentified", "deidentified",
                       {"sanitized_ref.$": "$.mask.out.sanitized_ref"})

        assess = invoke("AssessRules", compute.assess,
                        {"annual_income.$": "$.extract.out.fields.annual_income",
                         "household_size.$": "$.extract.out.fields.household_size",
                         "il30.$": "$.lookup.out.il30", "il50.$": "$.lookup.out.il50",
                         "il80.$": "$.lookup.out.il80", "il_source.$": "$.lookup.out.il_source",
                         "deidentified": True, "sanitized_ref.$": "$.mask.out.sanitized_ref"},
                        "$.assessment")
        g_rules = guard("GuardRulesExecuted", "rules_executed", {"assessment.$": "$.assessment.out"})

        draft = invoke("DraftNotice", compute.core,
                       {"case.$": "$.mask.out.masked_case",
                        "determination.$": "States.JsonToString($.assessment.out)",
                        "deidentified": True, "sanitized_ref.$": "$.mask.out.sanitized_ref"},
                       "$.draft")
        audit_intent = invoke("AuditIntent", compute.write_audit,
                              {"icsr_id.$": "$.case_id", "action": "determination",
                               "phase": "INTENT", "actor": "workflow-controller",
                               "payload.$": "States.JsonToString($.assessment.out)"},
                              "$.audit")

        signoff = tasks.LambdaInvoke(
            self, "HumanSignoff", lambda_function=compute.signoff_register,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object(
                {"icsr_id.$": "$.case_id", "requester.$": "$.requester",
                 # GA-5: bind the approval to the EXACT assessment content the approver saw
                 "content_hash.$": "States.Hash(States.JsonToString($.assessment.out), 'SHA-256')",
                 "taskToken": sfn.JsonPath.task_token}),
            timeout=cdk.Duration.hours(24), result_path="$.approval")
        finalize = invoke("Finalize", compute.finalize,
                          {"icsr_id.$": "$.case_id", "requester.$": "$.requester",
                           "approver.$": "$.approval.approver"}, "$.commit")
        committed = sfn.Succeed(self, "Committed")

        # explicit chain with fail-closed choices
        c1 = sfn.Choice(self, "ExtractedOk").when(
            sfn.Condition.boolean_equals("$.guards.extracted.ok", True), lookup).otherwise(manual_review)
        c2 = sfn.Choice(self, "AuthoritativeOk").when(
            sfn.Condition.boolean_equals("$.guards.authoritative.ok", True), mask).otherwise(manual_review)
        c3 = sfn.Choice(self, "DeidentifiedOk").when(
            sfn.Condition.boolean_equals("$.guards.deidentified.ok", True), assess).otherwise(manual_review)
        c4 = sfn.Choice(self, "RulesOk").when(
            sfn.Condition.boolean_equals("$.guards.rules_executed.ok", True), draft).otherwise(manual_review)

        definition = (extract.next(g_extracted).next(c1))
        lookup.next(g_auth).next(c2)
        mask.next(g_deid).next(c3)
        assess.next(g_rules).next(c4)
        draft.next(audit_intent).next(signoff).next(finalize).next(committed)

        self.controller = sfn.StateMachine(
            self, "Controller", state_machine_name=f"{prefix}-determination-workflow",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=cdk.Duration.hours(25),
        )
        cdk.CfnOutput(self, "ControllerArn", value=self.controller.state_machine_arn)
