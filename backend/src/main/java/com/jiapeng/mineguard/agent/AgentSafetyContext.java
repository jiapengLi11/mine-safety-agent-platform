package com.jiapeng.mineguard.agent;

import java.util.List;
import java.util.Objects;
import java.util.Set;

public record AgentSafetyContext(
        String eventId,
        String cameraId,
        AuthoritativeRuleDecision ruleDecision,
        Set<String> availableEvidenceIds,
        List<String> requiredEvidenceIds) {

    public AgentSafetyContext {
        requireText(eventId, "eventId");
        requireText(cameraId, "cameraId");
        Objects.requireNonNull(ruleDecision, "ruleDecision is required");
        availableEvidenceIds = Set.copyOf(
                Objects.requireNonNull(availableEvidenceIds, "availableEvidenceIds are required"));
        requiredEvidenceIds = List.copyOf(
                Objects.requireNonNull(requiredEvidenceIds, "requiredEvidenceIds are required"));
        if (availableEvidenceIds.stream().anyMatch(id -> id == null || id.isBlank())
                || requiredEvidenceIds.stream().anyMatch(id -> id == null || id.isBlank())) {
            throw new IllegalArgumentException("Evidence ids must be non-blank");
        }
    }

    public List<String> expectedCitations() {
        return requiredEvidenceIds.stream().filter(availableEvidenceIds::contains).distinct().toList();
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " is required");
        }
    }
}
