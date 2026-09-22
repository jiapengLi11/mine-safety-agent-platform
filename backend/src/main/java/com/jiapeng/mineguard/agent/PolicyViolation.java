package com.jiapeng.mineguard.agent;

public record PolicyViolation(PolicyViolationCode code, String path, String message) {
}
