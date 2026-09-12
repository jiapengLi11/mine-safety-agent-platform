package com.jiapeng.mineguard.rule;

import java.time.Instant;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class InMemoryWindowHitTracker implements WindowHitTracker {

    private final Map<WindowKey, WindowState> windows = new ConcurrentHashMap<>();

    @Override
    public RuleEvaluation record(
            String ruleId,
            String cameraId,
            String eventId,
            Instant occurredAt,
            WindowHitCountRule rule) {
        WindowKey key = new WindowKey(ruleId, cameraId);
        WindowState state = windows.computeIfAbsent(key, ignored -> new WindowState());
        synchronized (state) {
            Instant cutoff = occurredAt.minus(rule.window());
            Iterator<Map.Entry<String, Instant>> iterator = state.hits.entrySet().iterator();
            while (iterator.hasNext()) {
                if (iterator.next().getValue().isBefore(cutoff)) {
                    iterator.remove();
                }
            }
            state.hits.putIfAbsent(eventId, occurredAt);

            int count = state.hits.size();
            boolean coolingDown = state.lastTriggeredAt != null
                    && occurredAt.isBefore(state.lastTriggeredAt.plus(rule.cooldown()));
            if (count >= rule.minimumHits() && !coolingDown) {
                state.lastTriggeredAt = occurredAt;
                return new RuleEvaluation(true, true, count, "MINIMUM_HITS_REACHED");
            }
            return new RuleEvaluation(
                    true,
                    false,
                    count,
                    coolingDown ? "RULE_IN_COOLDOWN" : "WAITING_FOR_MORE_HITS");
        }
    }

    private record WindowKey(String ruleId, String cameraId) {
    }

    private static final class WindowState {
        private final Map<String, Instant> hits = new HashMap<>();
        private Instant lastTriggeredAt;
    }
}
