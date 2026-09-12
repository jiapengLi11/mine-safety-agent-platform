package com.jiapeng.mineguard.rule;

import com.jiapeng.mineguard.detection.DetectionFrameEvent;

import java.util.Objects;

public final class TemporalRuleEvaluator {

    private final WindowHitTracker tracker;

    public TemporalRuleEvaluator(WindowHitTracker tracker) {
        this.tracker = Objects.requireNonNull(tracker);
    }

    public RuleEvaluation evaluate(DetectionFrameEvent event, WindowHitCountRule rule) {
        boolean matched = event.objects().stream().anyMatch(object ->
                object.className().equals(rule.className())
                        && object.confidence() >= rule.minimumConfidence());
        if (!matched) {
            return RuleEvaluation.notMatched();
        }
        return tracker.record(
                rule.ruleId(),
                event.cameraId(),
                event.eventId(),
                event.capturedAt(),
                rule);
    }
}
