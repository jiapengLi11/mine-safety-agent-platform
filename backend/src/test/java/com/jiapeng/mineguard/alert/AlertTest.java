package com.jiapeng.mineguard.alert;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AlertTest {

    @Test
    void followsTheValidHandlingLifecycle() {
        Alert alert = new Alert("ALT-001");

        alert.confirm();
        alert.beginHandling();
        alert.close();

        assertThat(alert.state()).isEqualTo(AlertState.CLOSED);
    }

    @Test
    void rejectsIllegalStateTransitions() {
        Alert alert = new Alert("ALT-002");

        assertThatThrownBy(alert::close)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Expected alert state HANDLING");
    }
}
