package com.jiapeng.mineguard.agent;

import java.util.Arrays;

public enum ToolName {
    RECORD_ALERT("record_alert"),
    NOTIFY_SUPERVISOR("notify_supervisor"),
    REQUEST_HUMAN_APPROVAL("request_human_approval");

    private final String wireValue;

    ToolName(String wireValue) {
        this.wireValue = wireValue;
    }

    public String wireValue() {
        return wireValue;
    }

    public static ToolName fromWireValue(String value) {
        return Arrays.stream(values())
                .filter(tool -> tool.wireValue.equals(value))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unsupported tool: " + value));
    }
}
