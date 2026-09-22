package com.jiapeng.mineguard.agent;

import java.util.Objects;

public record AgentToolCall(ToolName name, String eventId, String cameraId) {

    public AgentToolCall {
        Objects.requireNonNull(name, "name is required");
        if (eventId == null || eventId.isBlank() || cameraId == null || cameraId.isBlank()) {
            throw new IllegalArgumentException("Tool eventId and cameraId are required");
        }
    }
}
