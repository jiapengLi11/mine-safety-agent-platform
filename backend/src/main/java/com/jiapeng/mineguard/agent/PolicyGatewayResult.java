package com.jiapeng.mineguard.agent;

import java.util.List;
import java.util.Objects;

public record PolicyGatewayResult(
        Status status,
        SafeAgentPlan safePlan,
        List<PolicyViolation> violations) {

    public PolicyGatewayResult {
        Objects.requireNonNull(status, "status is required");
        Objects.requireNonNull(safePlan, "safePlan is required");
        violations = List.copyOf(Objects.requireNonNull(violations, "violations are required"));
    }

    public boolean accepted() {
        return status == Status.ACCEPTED;
    }

    public enum Status {
        ACCEPTED,
        BLOCKED_TO_HUMAN_REVIEW
    }
}
