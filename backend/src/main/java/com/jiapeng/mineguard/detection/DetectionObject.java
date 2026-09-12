package com.jiapeng.mineguard.detection;

import java.util.Objects;

public record DetectionObject(String className, double confidence, BoundingBox box) {

    public DetectionObject {
        if (className == null || className.isBlank()) {
            throw new IllegalArgumentException("Detection class name is required");
        }
        if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1) {
            throw new IllegalArgumentException("Detection confidence must be between 0 and 1");
        }
        Objects.requireNonNull(box, "Detection bounding box is required");
    }
}
