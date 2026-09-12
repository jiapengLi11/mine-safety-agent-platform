package com.jiapeng.mineguard.rule;

public record RuleEvaluation(boolean matched, boolean triggered, int hitCount, String reason) {

    public static RuleEvaluation notMatched() {
        return new RuleEvaluation(false, false, 0, "FRAME_DID_NOT_MATCH_RULE");
    }
}
