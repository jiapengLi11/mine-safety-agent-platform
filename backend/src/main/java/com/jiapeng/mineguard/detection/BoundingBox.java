package com.jiapeng.mineguard.detection;

public record BoundingBox(double x1, double y1, double x2, double y2) {

    public BoundingBox {
        if (!Double.isFinite(x1) || !Double.isFinite(y1) || !Double.isFinite(x2) || !Double.isFinite(y2)) {
            throw new IllegalArgumentException("Bounding-box coordinates must be finite");
        }
        if (x1 < 0 || y1 < 0 || x2 <= x1 || y2 <= y1) {
            throw new IllegalArgumentException("Bounding box must have a positive area in pixel coordinates");
        }
    }
}
