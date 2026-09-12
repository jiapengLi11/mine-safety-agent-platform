package com.jiapeng.mineguard.rule;

import com.jiapeng.mineguard.detection.BoundingBox;
import com.jiapeng.mineguard.detection.DetectionFrameEvent;
import com.jiapeng.mineguard.detection.DetectionObject;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class TemporalRuleEvaluatorTest {

    private final WindowHitCountRule rule = new WindowHitCountRule(
            "SMOKING-3-IN-20S",
            "smoking",
            0.65,
            Duration.ofSeconds(20),
            3,
            Duration.ofSeconds(60));

    private final TemporalRuleEvaluator evaluator = new TemporalRuleEvaluator(new InMemoryWindowHitTracker());

    @Test
    void triggersOnlyAfterThreeDistinctMatchingFrames() {
        Instant start = Instant.parse("2026-09-12T10:00:00Z");

        assertThat(evaluator.evaluate(event("event-1", start, 0.80), rule).triggered()).isFalse();
        assertThat(evaluator.evaluate(event("event-2", start.plusSeconds(8), 0.75), rule).triggered()).isFalse();
        RuleEvaluation third = evaluator.evaluate(event("event-3", start.plusSeconds(18), 0.90), rule);

        assertThat(third.triggered()).isTrue();
        assertThat(third.hitCount()).isEqualTo(3);
    }

    @Test
    void duplicateEventDoesNotIncreaseTheHitCount() {
        Instant start = Instant.parse("2026-09-12T10:00:00Z");

        evaluator.evaluate(event("same-event", start, 0.80), rule);
        RuleEvaluation duplicate = evaluator.evaluate(event("same-event", start.plusSeconds(1), 0.80), rule);

        assertThat(duplicate.hitCount()).isEqualTo(1);
        assertThat(duplicate.triggered()).isFalse();
    }

    @Test
    void ignoresFramesBelowTheConfiguredConfidence() {
        RuleEvaluation result = evaluator.evaluate(
                event("event-low", Instant.parse("2026-09-12T10:00:00Z"), 0.64),
                rule);

        assertThat(result.matched()).isFalse();
        assertThat(result.reason()).isEqualTo("FRAME_DID_NOT_MATCH_RULE");
    }

    @Test
    void suppressesAnotherTriggerDuringCooldown() {
        Instant start = Instant.parse("2026-09-12T10:00:00Z");
        evaluator.evaluate(event("event-1", start, 0.80), rule);
        evaluator.evaluate(event("event-2", start.plusSeconds(4), 0.80), rule);
        evaluator.evaluate(event("event-3", start.plusSeconds(8), 0.80), rule);

        RuleEvaluation result = evaluator.evaluate(event("event-4", start.plusSeconds(12), 0.80), rule);

        assertThat(result.triggered()).isFalse();
        assertThat(result.reason()).isEqualTo("RULE_IN_COOLDOWN");
    }

    @Test
    void removesHitsThatFallOutsideTheSlidingWindow() {
        Instant start = Instant.parse("2026-09-12T10:00:00Z");
        evaluator.evaluate(event("event-1", start, 0.80), rule);
        evaluator.evaluate(event("event-2", start.plusSeconds(10), 0.80), rule);

        RuleEvaluation result = evaluator.evaluate(event("event-3", start.plusSeconds(21), 0.80), rule);

        assertThat(result.hitCount()).isEqualTo(2);
        assertThat(result.triggered()).isFalse();
    }

    @Test
    void isolatesHitWindowsByCamera() {
        Instant start = Instant.parse("2026-09-12T10:00:00Z");
        evaluator.evaluate(event("event-1", "CAM-001", start, 0.80), rule);
        evaluator.evaluate(event("event-2", "CAM-001", start.plusSeconds(5), 0.80), rule);

        RuleEvaluation otherCamera = evaluator.evaluate(
                event("event-3", "CAM-002", start.plusSeconds(10), 0.80),
                rule);

        assertThat(otherCamera.hitCount()).isEqualTo(1);
        assertThat(otherCamera.triggered()).isFalse();
    }

    private static DetectionFrameEvent event(String eventId, Instant capturedAt, double confidence) {
        return event(eventId, "CAM-001", capturedAt, confidence);
    }

    private static DetectionFrameEvent event(
            String eventId,
            String cameraId,
            Instant capturedAt,
            double confidence) {
        return new DetectionFrameEvent(
                eventId,
                1,
                "trace-" + eventId,
                cameraId,
                Math.abs(eventId.hashCode()),
                capturedAt,
                capturedAt.plusMillis(80),
                "company-reviewed-v3",
                1920,
                1080,
                "frames/CAM-001/" + eventId + ".jpg",
                List.of(new DetectionObject(
                        "smoking",
                        confidence,
                        new BoundingBox(100, 100, 180, 220))));
    }
}
