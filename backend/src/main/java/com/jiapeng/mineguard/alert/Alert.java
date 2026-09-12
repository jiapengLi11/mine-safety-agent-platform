package com.jiapeng.mineguard.alert;

import java.util.Objects;

public final class Alert {

    private final String alertId;
    private AlertState state;

    public Alert(String alertId) {
        if (alertId == null || alertId.isBlank()) {
            throw new IllegalArgumentException("Alert id is required");
        }
        this.alertId = alertId;
        this.state = AlertState.CANDIDATE;
    }

    public String alertId() {
        return alertId;
    }

    public AlertState state() {
        return state;
    }

    public void confirm() {
        transition(AlertState.CANDIDATE, AlertState.CONFIRMED);
    }

    public void beginHandling() {
        transition(AlertState.CONFIRMED, AlertState.HANDLING);
    }

    public void close() {
        transition(AlertState.HANDLING, AlertState.CLOSED);
    }

    public void markFalsePositive() {
        if (state != AlertState.CANDIDATE && state != AlertState.CONFIRMED && state != AlertState.HANDLING) {
            throw new IllegalStateException("Cannot mark alert as false positive from " + state);
        }
        state = AlertState.FALSE_POSITIVE;
    }

    public void suppress() {
        transition(AlertState.CANDIDATE, AlertState.SUPPRESSED);
    }

    private void transition(AlertState expected, AlertState target) {
        if (!Objects.equals(state, expected)) {
            throw new IllegalStateException("Expected alert state " + expected + " but was " + state);
        }
        state = target;
    }
}
