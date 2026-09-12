package com.jiapeng.mineguard.rule;

import java.time.Instant;

public interface WindowHitTracker {

    RuleEvaluation record(
            String ruleId,
            String cameraId,
            String eventId,
            Instant occurredAt,
            WindowHitCountRule rule);
}
