package com.jiapeng.mineguard.agent;

import org.springframework.stereotype.Component;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

import static com.jiapeng.mineguard.agent.PolicyViolationCode.CITATION_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.FORBIDDEN_TOOL;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.INVALID_FIELD_TYPE;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.INVALID_FIELD_VALUE;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.INVALID_JSON;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.MISSING_FIELD;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.RULE_APPROVAL_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.RULE_DECISION_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.RULE_REASON_CODES_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.RULE_RISK_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.TOOL_ARGUMENT_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.TOOL_PLAN_MISMATCH;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.UNEXPECTED_FIELD;
import static com.jiapeng.mineguard.agent.PolicyViolationCode.UNKNOWN_CITATION;

@Component
public final class AgentOutputPolicyGateway {

    private static final int MAX_OUTPUT_CHARACTERS = 16_384;
    private static final Set<String> TOP_LEVEL_FIELDS = Set.of(
            "schemaVersion",
            "riskLevel",
            "decision",
            "summary",
            "reasonCodes",
            "citations",
            "requiresHumanApproval",
            "toolCalls");
    private static final Set<String> TOOL_FIELDS = Set.of("name", "arguments");
    private static final Set<String> TOOL_ARGUMENT_FIELDS = Set.of("eventId", "cameraId");
    private static final Pattern REASON_CODE = Pattern.compile("^[A-Z][A-Z0-9_]{2,63}$");

    private final ObjectMapper objectMapper;

    public AgentOutputPolicyGateway(ObjectMapper objectMapper) {
        this.objectMapper = Objects.requireNonNull(objectMapper)
                .rebuild()
                .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
                .build();
    }

    public PolicyGatewayResult evaluate(String rawOutput, AgentSafetyContext context) {
        Objects.requireNonNull(context, "context is required");
        List<PolicyViolation> violations = new ArrayList<>();
        if (rawOutput == null || rawOutput.isBlank()) {
            violations.add(new PolicyViolation(INVALID_JSON, "$", "Model output is empty"));
            return blocked(context, violations);
        }
        if (rawOutput.length() > MAX_OUTPUT_CHARACTERS) {
            violations.add(new PolicyViolation(
                    PolicyViolationCode.OUTPUT_TOO_LARGE,
                    "$",
                    "Model output exceeds " + MAX_OUTPUT_CHARACTERS + " characters"));
            return blocked(context, violations);
        }
        JsonNode root;
        try {
            root = objectMapper.readTree(rawOutput);
        } catch (JacksonException | IllegalArgumentException exception) {
            violations.add(new PolicyViolation(INVALID_JSON, "$", "Model output is not valid JSON"));
            return blocked(context, violations);
        }
        if (root == null || !root.isObject()) {
            violations.add(new PolicyViolation(INVALID_JSON, "$", "Model output must be one JSON object"));
            return blocked(context, violations);
        }

        validateExactFields(root, TOP_LEVEL_FIELDS, "$", violations);
        String schemaVersion = text(root, "schemaVersion", 1, 20, null, violations);
        String riskValue = text(root, "riskLevel", 1, 20, null, violations);
        String decisionValue = text(root, "decision", 1, 30, null, violations);
        String summary = text(root, "summary", 1, 500, null, violations);
        List<String> reasonCodes = stringArray(root, "reasonCodes", REASON_CODE, 64, violations);
        List<String> citations = stringArray(root, "citations", null, 100, violations);
        Boolean approval = bool(root, "requiresHumanApproval", violations);
        List<AgentToolCall> tools = toolCalls(root, violations);

        if (!"1.0".equals(schemaVersion)) {
            violations.add(new PolicyViolation(
                    INVALID_FIELD_VALUE, "$.schemaVersion", "schemaVersion must be 1.0"));
        }
        RiskLevel risk = enumValue(RiskLevel.class, riskValue, "$.riskLevel", violations);
        DecisionAction decision = enumValue(DecisionAction.class, decisionValue, "$.decision", violations);
        if (!violations.isEmpty()) {
            return blocked(context, violations);
        }

        AuthoritativeRuleDecision rule = context.ruleDecision();
        if (risk != rule.riskLevel()) {
            violations.add(new PolicyViolation(
                    RULE_RISK_MISMATCH, "$.riskLevel", "Model risk must match the rule engine"));
        }
        if (decision != rule.decision()) {
            violations.add(new PolicyViolation(
                    RULE_DECISION_MISMATCH, "$.decision", "Model decision must match the rule engine"));
        }
        if (approval != rule.requiresHumanApproval()) {
            violations.add(new PolicyViolation(
                    RULE_APPROVAL_MISMATCH,
                    "$.requiresHumanApproval",
                    "Model approval requirement must match the rule engine"));
        }
        if (!new HashSet<>(reasonCodes).equals(new HashSet<>(rule.reasonCodes()))) {
            violations.add(new PolicyViolation(
                    RULE_REASON_CODES_MISMATCH,
                    "$.reasonCodes",
                    "Model reason codes must match the rule engine"));
        }

        List<String> unknownCitations = citations.stream()
                .filter(citation -> !context.availableEvidenceIds().contains(citation))
                .toList();
        if (!unknownCitations.isEmpty()) {
            violations.add(new PolicyViolation(
                    UNKNOWN_CITATION,
                    "$.citations",
                    "Unknown citations: " + String.join(",", unknownCitations)));
        }
        if (!new LinkedHashSet<>(citations).equals(new LinkedHashSet<>(context.expectedCitations()))) {
            violations.add(new PolicyViolation(
                    CITATION_MISMATCH,
                    "$.citations",
                    "Citations must equal the available required evidence ids"));
        }

        List<AgentToolCall> expectedTools = expectedTools(context, rule.decision());
        validateToolPlan(tools, expectedTools, violations);
        if (!violations.isEmpty()) {
            return blocked(context, violations);
        }

        SafeAgentPlan accepted = new SafeAgentPlan(
                risk,
                decision,
                summary,
                reasonCodes,
                citations,
                approval,
                tools,
                SafeAgentPlan.PlanSource.MODEL_ACCEPTED);
        return new PolicyGatewayResult(PolicyGatewayResult.Status.ACCEPTED, accepted, List.of());
    }

    private static void validateToolPlan(
            List<AgentToolCall> actual,
            List<AgentToolCall> expected,
            List<PolicyViolation> violations) {
        List<ToolName> actualNames = actual.stream().map(AgentToolCall::name).toList();
        List<ToolName> expectedNames = expected.stream().map(AgentToolCall::name).toList();
        if (!actualNames.equals(expectedNames)) {
            violations.add(new PolicyViolation(
                    TOOL_PLAN_MISMATCH, "$.toolCalls", "Tool names and order must match policy"));
            return;
        }
        if (!actual.equals(expected)) {
            violations.add(new PolicyViolation(
                    TOOL_ARGUMENT_MISMATCH,
                    "$.toolCalls",
                    "Tool arguments must use the authoritative eventId and cameraId"));
        }
    }

    private static List<AgentToolCall> expectedTools(
            AgentSafetyContext context, DecisionAction decision) {
        AgentToolCall record = new AgentToolCall(
                ToolName.RECORD_ALERT, context.eventId(), context.cameraId());
        AgentToolCall notify = new AgentToolCall(
                ToolName.NOTIFY_SUPERVISOR, context.eventId(), context.cameraId());
        AgentToolCall approval = new AgentToolCall(
                ToolName.REQUEST_HUMAN_APPROVAL, context.eventId(), context.cameraId());
        return switch (decision) {
            case IGNORE, OBSERVE -> List.of();
            case NOTIFY -> List.of(record, notify);
            case HUMAN_REVIEW -> List.of(approval);
            case ESCALATE -> List.of(record, approval);
        };
    }

    private static PolicyGatewayResult blocked(
            AgentSafetyContext context, List<PolicyViolation> violations) {
        SafeAgentPlan fallback = new SafeAgentPlan(
                context.ruleDecision().riskLevel(),
                DecisionAction.HUMAN_REVIEW,
                "Model output was blocked by deterministic safety policy.",
                context.ruleDecision().reasonCodes(),
                context.expectedCitations(),
                true,
                List.of(new AgentToolCall(
                        ToolName.REQUEST_HUMAN_APPROVAL,
                        context.eventId(),
                        context.cameraId())),
                SafeAgentPlan.PlanSource.POLICY_FALLBACK);
        return new PolicyGatewayResult(
                PolicyGatewayResult.Status.BLOCKED_TO_HUMAN_REVIEW, fallback, violations);
    }

    private static void validateExactFields(
            JsonNode node,
            Set<String> expected,
            String path,
            List<PolicyViolation> violations) {
        for (String field : expected) {
            if (!node.has(field)) {
                violations.add(new PolicyViolation(MISSING_FIELD, path + "." + field, "Required field is missing"));
            }
        }
        for (String field : node.propertyNames()) {
            if (!expected.contains(field)) {
                violations.add(new PolicyViolation(UNEXPECTED_FIELD, path + "." + field, "Unexpected field"));
            }
        }
    }

    private static String text(
            JsonNode object,
            String field,
            int minLength,
            int maxLength,
            Pattern pattern,
            List<PolicyViolation> violations) {
        JsonNode node = object.get(field);
        if (node == null) {
            return null;
        }
        if (!node.isString()) {
            violations.add(new PolicyViolation(INVALID_FIELD_TYPE, "$." + field, "Expected a string"));
            return null;
        }
        String value = node.stringValue();
        if (value.length() < minLength || value.length() > maxLength
                || (pattern != null && !pattern.matcher(value).matches())) {
            violations.add(new PolicyViolation(INVALID_FIELD_VALUE, "$." + field, "Invalid string value"));
        }
        return value;
    }

    private static Boolean bool(
            JsonNode object, String field, List<PolicyViolation> violations) {
        JsonNode node = object.get(field);
        if (node == null) {
            return null;
        }
        if (!node.isBoolean()) {
            violations.add(new PolicyViolation(INVALID_FIELD_TYPE, "$." + field, "Expected a boolean"));
            return null;
        }
        return node.booleanValue();
    }

    private static List<String> stringArray(
            JsonNode object,
            String field,
            Pattern pattern,
            int maxItemLength,
            List<PolicyViolation> violations) {
        JsonNode node = object.get(field);
        if (node == null) {
            return List.of();
        }
        if (!node.isArray()) {
            violations.add(new PolicyViolation(INVALID_FIELD_TYPE, "$." + field, "Expected an array"));
            return List.of();
        }
        List<String> values = new ArrayList<>();
        Set<String> unique = new HashSet<>();
        for (int index = 0; index < node.size(); index++) {
            JsonNode item = node.get(index);
            if (!item.isString()) {
                violations.add(new PolicyViolation(
                        INVALID_FIELD_TYPE, "$." + field + "[" + index + "]", "Expected a string"));
                continue;
            }
            String value = item.stringValue();
            if (value.isEmpty() || value.length() > maxItemLength
                    || (pattern != null && !pattern.matcher(value).matches())) {
                violations.add(new PolicyViolation(
                        INVALID_FIELD_VALUE, "$." + field + "[" + index + "]", "Invalid string value"));
            }
            if (!unique.add(value)) {
                violations.add(new PolicyViolation(
                        INVALID_FIELD_VALUE, "$." + field, "Array items must be unique"));
            }
            values.add(value);
        }
        return values;
    }

    private static List<AgentToolCall> toolCalls(
            JsonNode root, List<PolicyViolation> violations) {
        JsonNode node = root.get("toolCalls");
        if (node == null) {
            return List.of();
        }
        if (!node.isArray()) {
            violations.add(new PolicyViolation(INVALID_FIELD_TYPE, "$.toolCalls", "Expected an array"));
            return List.of();
        }
        List<AgentToolCall> calls = new ArrayList<>();
        for (int index = 0; index < node.size(); index++) {
            JsonNode tool = node.get(index);
            String path = "$.toolCalls[" + index + "]";
            if (!tool.isObject()) {
                violations.add(new PolicyViolation(INVALID_FIELD_TYPE, path, "Expected an object"));
                continue;
            }
            validateExactFields(tool, TOOL_FIELDS, path, violations);
            JsonNode nameNode = tool.get("name");
            JsonNode arguments = tool.get("arguments");
            if (nameNode == null || !nameNode.isString()) {
                violations.add(new PolicyViolation(INVALID_FIELD_TYPE, path + ".name", "Expected a string"));
                continue;
            }
            ToolName name;
            try {
                name = ToolName.fromWireValue(nameNode.stringValue());
            } catch (IllegalArgumentException exception) {
                violations.add(new PolicyViolation(FORBIDDEN_TOOL, path + ".name", exception.getMessage()));
                continue;
            }
            if (arguments == null || !arguments.isObject()) {
                violations.add(new PolicyViolation(
                        INVALID_FIELD_TYPE, path + ".arguments", "Expected an object"));
                continue;
            }
            validateExactFields(arguments, TOOL_ARGUMENT_FIELDS, path + ".arguments", violations);
            String eventId = nestedText(arguments, "eventId", path + ".arguments", violations);
            String cameraId = nestedText(arguments, "cameraId", path + ".arguments", violations);
            if (eventId != null && cameraId != null) {
                calls.add(new AgentToolCall(name, eventId, cameraId));
            }
        }
        return calls;
    }

    private static String nestedText(
            JsonNode object,
            String field,
            String parentPath,
            List<PolicyViolation> violations) {
        JsonNode node = object.get(field);
        if (node == null || !node.isString() || node.stringValue().isBlank()) {
            violations.add(new PolicyViolation(
                    INVALID_FIELD_TYPE, parentPath + "." + field, "Expected a non-blank string"));
            return null;
        }
        return node.stringValue();
    }

    private static <T extends Enum<T>> T enumValue(
            Class<T> enumType,
            String value,
            String path,
            List<PolicyViolation> violations) {
        if (value == null) {
            return null;
        }
        try {
            return Enum.valueOf(enumType, value);
        } catch (IllegalArgumentException exception) {
            violations.add(new PolicyViolation(INVALID_FIELD_VALUE, path, "Unsupported enum value: " + value));
            return null;
        }
    }
}
