package com.jiapeng.mineguard.rule;

import java.time.Duration;

public record WindowHitCountRule(
        String ruleId,
        String className,
        double minimumConfidence,
        Duration window,
        int minimumHits,
        Duration cooldown) {

    public WindowHitCountRule {
        if (ruleId == null || ruleId.isBlank() || className == null || className.isBlank()) {
            throw new IllegalArgumentException("Rule id and class name are required");
        }
        if (minimumConfidence < 0 || minimumConfidence > 1) {
            throw new IllegalArgumentException("Minimum confidence must be between 0 and 1");
        }
        if (window == null || window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("Window must be positive");
        }
        if (minimumHits < 1) {
            throw new IllegalArgumentException("Minimum hits must be at least one");
        }
        if (cooldown == null || cooldown.isNegative()) {
            throw new IllegalArgumentException("Cooldown cannot be negative");
        }
    }
}
