package com.jiapeng.mineguard.detection;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public record DetectionFrameEvent(
        String eventId,
        int schemaVersion,
        String traceId,
        String cameraId,
        long frameId,
        Instant capturedAt,
        Instant inferredAt,
        String modelVersion,
        int imageWidth,
        int imageHeight,
        String sourceObjectKey,
        List<DetectionObject> objects) {

    public DetectionFrameEvent {
        requireText(eventId, "eventId");
        requireText(traceId, "traceId");
        requireText(cameraId, "cameraId");
        requireText(modelVersion, "modelVersion");
        if (schemaVersion != 1) {
            throw new IllegalArgumentException("Unsupported detection-event schema version: " + schemaVersion);
        }
        if (frameId < 0 || imageWidth <= 0 || imageHeight <= 0) {
            throw new IllegalArgumentException("Frame id and image dimensions must be valid");
        }
        Objects.requireNonNull(capturedAt, "capturedAt is required");
        Objects.requireNonNull(inferredAt, "inferredAt is required");
        if (inferredAt.isBefore(capturedAt)) {
            throw new IllegalArgumentException("inferredAt cannot be before capturedAt");
        }
        objects = List.copyOf(Objects.requireNonNull(objects, "objects are required"));
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " is required");
        }
    }
}
