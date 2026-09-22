from __future__ import annotations

from typing import Any

from .models import CaseEvaluation, GoldenCase


def run_harness_metrics(
    case: GoldenCase,
    result: CaseEvaluation,
    schema: dict[str, Any],
    latency_limit_ms: float = 15000,
) -> dict[str, dict[str, Any]]:
    """Evaluate framework-native contract metrics while domain metrics remain authoritative."""
    try:
        from harness_evals import EvalCase, ToolCall, evaluate
        from harness_evals.metrics import (
            LatencyMetric,
            SchemaValidationMetric,
            ToolArgumentMatchMetric,
            ToolCorrectnessMetric,
        )
    except ImportError:
        return {"harness_unavailable": {"value": 0.0, "passed": False}}

    output = result.output if result.output is not None else result.raw_output
    actual_tools = [
        ToolCall(
            name=item["name"],
            input=item.get("arguments", {}) if isinstance(item.get("arguments", {}), dict) else {},
        )
        for item in (result.output or {}).get("toolCalls", [])
        if isinstance(item, dict) and "name" in item
    ]
    expected_tools = [
        ToolCall(
            name=item["name"],
            input=item.get("arguments", {}) if isinstance(item.get("arguments", {}), dict) else {},
        )
        for item in case.expected.get("toolCalls", [])
    ]
    eval_case = EvalCase(
        input=case.input,
        output=output,
        expected=case.expected,
        latency_ms=result.latency_ms,
        tool_calls=actual_tools,
        expected_tools=[item.name for item in expected_tools],
        expected_tool_calls=expected_tools,
        tags={"case_id": case.id, "module": case.module},
    )
    metrics = [SchemaValidationMetric(schema=schema), LatencyMetric(max_ms=latency_limit_ms)]
    if actual_tools or expected_tools:
        metrics.extend(
            [
                ToolCorrectnessMetric(mode="exact"),
                ToolArgumentMatchMetric(pair="exact", arg_match="exact"),
            ]
        )
    scores = evaluate(eval_case, metrics=metrics)
    return {
        score.name: {
            "value": score.value,
            "threshold": score.threshold,
            "passed": score.passed,
            "reason": getattr(score, "reason", None),
        }
        for score in scores
    }
