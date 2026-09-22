package com.jiapeng.mineguard.agent;

import java.util.List;
import java.util.Objects;

public record AuthoritativeRuleDecision(
        RiskLevel riskLevel,
        DecisionAction decision,
        boolean requiresHumanApproval,
        List<String> reasonCodes) {

    public AuthoritativeRuleDecision {
        Objects.requireNonNull(riskLevel, "riskLevel is required");
        Objects.requireNonNull(decision, "decision is required");
        reasonCodes = List.copyOf(Objects.requireNonNull(reasonCodes, "reasonCodes are required"));
        if (reasonCodes.isEmpty() || reasonCodes.stream().anyMatch(code -> code == null || code.isBlank())) {
            throw new IllegalArgumentException("At least one non-blank reason code is required");
        }
    }
}
