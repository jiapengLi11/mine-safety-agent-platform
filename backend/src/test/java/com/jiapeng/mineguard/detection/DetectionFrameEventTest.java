package com.jiapeng.mineguard.detection;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DetectionFrameEventTest {

    @Test
    void rejectsInferenceTimestampBeforeCaptureTimestamp() {
        Instant capturedAt = Instant.parse("2026-09-12T12:00:00Z");

        assertThatThrownBy(() -> event(capturedAt, capturedAt.minusMillis(1), List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("inferredAt");
    }

    @Test
    void defensivelyCopiesDetectedObjects() {
        Instant now = Instant.parse("2026-09-12T12:00:00Z");
        List<DetectionObject> mutableObjects = new ArrayList<>();
        DetectionFrameEvent event = event(now, now.plusMillis(80), mutableObjects);

        mutableObjects.add(new DetectionObject("person", 0.9, new BoundingBox(1, 1, 10, 10)));

        assertThat(event.objects()).isEmpty();
        assertThatThrownBy(() -> event.objects().clear())
                .isInstanceOf(UnsupportedOperationException.class);
    }

    private static DetectionFrameEvent event(
            Instant capturedAt,
            Instant inferredAt,
            List<DetectionObject> objects) {
        return new DetectionFrameEvent(
                "event-1",
                1,
                "trace-1",
                "CAM-001",
                1,
                capturedAt,
                inferredAt,
                "company-reviewed-v3",
                1920,
                1080,
                null,
                objects);
    }
}
