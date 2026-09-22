package com.jiapeng.mineguard.agent;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class AgentOutputPolicyGatewayTest {

    private final AgentOutputPolicyGateway gateway = new AgentOutputPolicyGateway(new ObjectMapper());

    @Test
    void acceptsAnExactEvidenceGroundedEscalationPlan() {
        PolicyGatewayResult result = gateway.evaluate(validEscalationJson(), escalationContext());

        assertThat(result.accepted()).isTrue();
        assertThat(result.violations()).isEmpty();
        assertThat(result.safePlan().source()).isEqualTo(SafeAgentPlan.PlanSource.MODEL_ACCEPTED);
        assertThat(result.safePlan().toolCalls()).containsExactly(
                new AgentToolCall(ToolName.RECORD_ALERT, "EVT-1", "CAM-1"),
                new AgentToolCall(ToolName.REQUEST_HUMAN_APPROVAL, "EVT-1", "CAM-1"));
    }

    @Test
    void blocksAnInventedCitationWhenRetrievalReturnedNoEvidence() {
        AgentSafetyContext context = new AgentSafetyContext(
                "EVT-RAG-1",
                "CAM-7",
                new AuthoritativeRuleDecision(
                        RiskLevel.HIGH,
                        DecisionAction.HUMAN_REVIEW,
                        true,
                        List.of("REQUIRED_EVIDENCE_MISSING")),
                Set.of(),
                List.of("SOP-FUEL-SMOKE-001"));
        String output = """
                {
                  "schemaVersion":"1.0",
                  "riskLevel":"HIGH",
                  "decision":"HUMAN_REVIEW",
                  "summary":"Human review is required.",
                  "reasonCodes":["REQUIRED_EVIDENCE_MISSING"],
                  "citations":["SOP-FUEL-SMOKE-001"],
                  "requiresHumanApproval":true,
                  "toolCalls":[{"name":"request_human_approval","arguments":{"eventId":"EVT-RAG-1","cameraId":"CAM-7"}}]
                }
                """;

        PolicyGatewayResult result = gateway.evaluate(output, context);

        assertBlockedWith(result, PolicyViolationCode.UNKNOWN_CITATION);
        assertThat(result.safePlan().citations()).isEmpty();
    }

    @Test
    void blocksSchemaMetadataCopiedIntoTheBusinessOutput() {
        String validOutput = validEscalationJson();
        String output = "{\"$schema\":\"https://json-schema.org/draft/2020-12/schema\","
                + "\"$id\":\"https://mineguard.local/decision.json\","
                + validOutput.substring(validOutput.indexOf('{') + 1);

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.UNEXPECTED_FIELD);
    }

    @Test
    void blocksHumanReviewWhenTheApprovalToolIsMissing() {
        AgentSafetyContext context = new AgentSafetyContext(
                "EVT-RAG-1",
                "CAM-7",
                new AuthoritativeRuleDecision(
                        RiskLevel.HIGH,
                        DecisionAction.HUMAN_REVIEW,
                        true,
                        List.of("REQUIRED_EVIDENCE_MISSING")),
                Set.of(),
                List.of("SOP-FUEL-SMOKE-001"));
        String output = """
                {
                  "schemaVersion":"1.0",
                  "riskLevel":"HIGH",
                  "decision":"HUMAN_REVIEW",
                  "summary":"Human review is required.",
                  "reasonCodes":["REQUIRED_EVIDENCE_MISSING"],
                  "citations":[],
                  "requiresHumanApproval":true,
                  "toolCalls":[]
                }
                """;

        PolicyGatewayResult result = gateway.evaluate(output, context);

        assertBlockedWith(result, PolicyViolationCode.TOOL_PLAN_MISMATCH);
    }

    @Test
    void blocksARiskDowngradeEvenWhenTheJsonSchemaIsValid() {
        String output = validEscalationJson().replace("\"riskLevel\":\"HIGH\"", "\"riskLevel\":\"LOW\"");

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.RULE_RISK_MISMATCH);
        assertThat(result.safePlan().riskLevel()).isEqualTo(RiskLevel.HIGH);
    }

    @Test
    void blocksToolArgumentsThatDoNotMatchTheAuthoritativeEvent() {
        String output = validEscalationJson().replace("\"cameraId\":\"CAM-1\"", "\"cameraId\":\"CAM-OTHER\"");

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.TOOL_ARGUMENT_MISMATCH);
    }

    @Test
    void blocksForbiddenToolsBeforeExecution() {
        String output = validEscalationJson().replace("record_alert", "execute_sql");

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.FORBIDDEN_TOOL);
        assertThat(result.safePlan().toolCalls()).containsExactly(
                new AgentToolCall(ToolName.REQUEST_HUMAN_APPROVAL, "EVT-1", "CAM-1"));
    }

    @Test
    void invalidJsonFallsBackToOneHumanApprovalRequest() {
        PolicyGatewayResult result = gateway.evaluate("not-json", escalationContext());

        assertBlockedWith(result, PolicyViolationCode.INVALID_JSON);
        assertThat(result.safePlan().source()).isEqualTo(SafeAgentPlan.PlanSource.POLICY_FALLBACK);
        assertThat(result.safePlan().decision()).isEqualTo(DecisionAction.HUMAN_REVIEW);
        assertThat(result.safePlan().reasonCodes()).containsExactly("SMOKING_REPEATED");
        assertThat(result.safePlan().requiresHumanApproval()).isTrue();
        assertThat(result.safePlan().toolCalls()).containsExactly(
                new AgentToolCall(ToolName.REQUEST_HUMAN_APPROVAL, "EVT-1", "CAM-1"));
    }

    @Test
    void blocksDuplicateJsonFieldsInsteadOfAcceptingTheLastValue() {
        String output = validEscalationJson().replace(
                "\"riskLevel\":\"HIGH\"",
                "\"riskLevel\":\"LOW\",\"riskLevel\":\"HIGH\"");

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.INVALID_JSON);
    }

    @Test
    void blocksOversizedModelOutputBeforeParsing() {
        PolicyGatewayResult result = gateway.evaluate("x".repeat(16_385), escalationContext());

        assertBlockedWith(result, PolicyViolationCode.OUTPUT_TOO_LARGE);
    }

    @Test
    void blocksAnOmittedRequiredCitation() {
        String output = validEscalationJson().replace(
                "\"citations\":[\"SOP-SMOKE-001\"]",
                "\"citations\":[]");

        PolicyGatewayResult result = gateway.evaluate(output, escalationContext());

        assertBlockedWith(result, PolicyViolationCode.CITATION_MISMATCH);
    }

    private static AgentSafetyContext escalationContext() {
        return new AgentSafetyContext(
                "EVT-1",
                "CAM-1",
                new AuthoritativeRuleDecision(
                        RiskLevel.HIGH,
                        DecisionAction.ESCALATE,
                        true,
                        List.of("SMOKING_REPEATED")),
                Set.of("SOP-SMOKE-001"),
                List.of("SOP-SMOKE-001"));
    }

    private static String validEscalationJson() {
        return """
                {
                  "schemaVersion":"1.0",
                  "riskLevel":"HIGH",
                  "decision":"ESCALATE",
                  "summary":"Repeated smoking requires controlled escalation.",
                  "reasonCodes":["SMOKING_REPEATED"],
                  "citations":["SOP-SMOKE-001"],
                  "requiresHumanApproval":true,
                  "toolCalls":[
                    {"name":"record_alert","arguments":{"eventId":"EVT-1","cameraId":"CAM-1"}},
                    {"name":"request_human_approval","arguments":{"eventId":"EVT-1","cameraId":"CAM-1"}}
                  ]
                }
                """;
    }

    private static void assertBlockedWith(
            PolicyGatewayResult result, PolicyViolationCode expectedCode) {
        assertThat(result.accepted()).isFalse();
        assertThat(result.status()).isEqualTo(PolicyGatewayResult.Status.BLOCKED_TO_HUMAN_REVIEW);
        assertThat(result.violations()).extracting(PolicyViolation::code).contains(expectedCode);
        assertThat(result.safePlan().source()).isEqualTo(SafeAgentPlan.PlanSource.POLICY_FALLBACK);
    }
}
