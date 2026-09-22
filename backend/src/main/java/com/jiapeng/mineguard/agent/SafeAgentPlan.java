package com.jiapeng.mineguard.agent;

import java.util.List;
import java.util.Objects;

public record SafeAgentPlan(
        RiskLevel riskLevel,
        DecisionAction decision,
        String summary,
        List<String> reasonCodes,
        List<String> citations,
        boolean requiresHumanApproval,
        List<AgentToolCall> toolCalls,
        PlanSource source) {

    public SafeAgentPlan {
        Objects.requireNonNull(riskLevel, "riskLevel is required");
        Objects.requireNonNull(decision, "decision is required");
        Objects.requireNonNull(source, "source is required");
        if (summary == null || summary.isBlank()) {
            throw new IllegalArgumentException("summary is required");
        }
        reasonCodes = List.copyOf(Objects.requireNonNull(reasonCodes));
        citations = List.copyOf(Objects.requireNonNull(citations));
        toolCalls = List.copyOf(Objects.requireNonNull(toolCalls));
    }

    public enum PlanSource {
        MODEL_ACCEPTED,
        POLICY_FALLBACK
    }
}
