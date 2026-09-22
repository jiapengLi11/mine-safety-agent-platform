from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from .models import GoldenCase, TargetResponse


MAX_OUTPUT_CHARACTERS = 16_384


@dataclass(frozen=True)
class PolicyViolation:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class PolicyResult:
    accepted: bool
    output: dict[str, Any]
    violations: tuple[PolicyViolation, ...]
    latency_ms: float


class DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKey(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _schema_violation(error: Any) -> PolicyViolation:
    code_by_validator = {
        "additionalProperties": "UNEXPECTED_FIELD",
        "required": "MISSING_FIELD",
        "type": "INVALID_FIELD_TYPE",
    }
    path_items = list(error.absolute_path)
    path = "$" + "".join(f"[{item}]" if isinstance(item, int) else f".{item}" for item in path_items)
    code = code_by_validator.get(error.validator, "INVALID_FIELD_VALUE")
    if error.validator == "enum" and path_items and path_items[-1] == "name":
        code = "FORBIDDEN_TOOL"
    return PolicyViolation(code, path, error.message)


def _expected_citations(case: GoldenCase) -> list[str]:
    available = {item["id"] for item in case.input.get("retrievedEvidence", [])}
    return list(dict.fromkeys(
        item for item in case.input.get("requiredEvidenceIds", []) if item in available
    ))


def _expected_tools(case: GoldenCase, decision: str) -> list[dict[str, Any]]:
    event = case.input["event"]
    arguments = {"eventId": event["eventId"], "cameraId": event["cameraId"]}
    record = {"name": "record_alert", "arguments": arguments}
    notify = {"name": "notify_supervisor", "arguments": arguments}
    approval = {"name": "request_human_approval", "arguments": arguments}
    return {
        "IGNORE": [],
        "OBSERVE": [],
        "NOTIFY": [record, notify],
        "HUMAN_REVIEW": [approval],
        "ESCALATE": [record, approval],
    }[decision]


def _fallback(case: GoldenCase) -> dict[str, Any]:
    event = case.input["event"]
    rule = case.input["ruleDecision"]
    return {
        "schemaVersion": "1.0",
        "riskLevel": rule["riskLevel"],
        "decision": "HUMAN_REVIEW",
        "summary": "Model output was blocked by deterministic safety policy.",
        "reasonCodes": rule["reasonCodes"],
        "citations": _expected_citations(case),
        "requiresHumanApproval": True,
        "toolCalls": [{
            "name": "request_human_approval",
            "arguments": {"eventId": event["eventId"], "cameraId": event["cameraId"]},
        }],
    }


def apply_policy_gateway(
    case: GoldenCase,
    response: TargetResponse,
    schema: dict[str, Any],
) -> PolicyResult:
    started = time.perf_counter()
    violations: list[PolicyViolation] = []
    raw = response.raw_output
    if not raw or not raw.strip():
        violations.append(PolicyViolation("INVALID_JSON", "$", "Model output is empty"))
        return _blocked(case, violations, started)
    if len(raw) > MAX_OUTPUT_CHARACTERS:
        violations.append(PolicyViolation(
            "OUTPUT_TOO_LARGE", "$", f"Model output exceeds {MAX_OUTPUT_CHARACTERS} characters"
        ))
        return _blocked(case, violations, started)
    try:
        output = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, DuplicateJsonKey, TypeError) as exc:
        violations.append(PolicyViolation("INVALID_JSON", "$", str(exc)))
        return _blocked(case, violations, started)
    if not isinstance(output, dict):
        violations.append(PolicyViolation("INVALID_JSON", "$", "Model output must be one JSON object"))
        return _blocked(case, violations, started)

    validator = Draft202012Validator(schema)
    violations.extend(
        _schema_violation(error)
        for error in sorted(validator.iter_errors(output), key=lambda item: list(item.absolute_path))
    )
    if violations:
        return _blocked(case, violations, started)

    rule = case.input["ruleDecision"]
    for field, code in (
        ("riskLevel", "RULE_RISK_MISMATCH"),
        ("decision", "RULE_DECISION_MISMATCH"),
        ("requiresHumanApproval", "RULE_APPROVAL_MISMATCH"),
    ):
        if output[field] != rule[field]:
            violations.append(PolicyViolation(code, f"$.{field}", "Model value must match rule engine"))
    if Counter(output["reasonCodes"]) != Counter(rule["reasonCodes"]):
        violations.append(PolicyViolation(
            "RULE_REASON_CODES_MISMATCH", "$.reasonCodes", "Reason codes must match rule engine"
        ))

    available = {item["id"] for item in case.input.get("retrievedEvidence", [])}
    unknown = [item for item in output["citations"] if item not in available]
    if unknown:
        violations.append(PolicyViolation(
            "UNKNOWN_CITATION", "$.citations", "Unknown citations: " + ",".join(unknown)
        ))
    if set(output["citations"]) != set(_expected_citations(case)):
        violations.append(PolicyViolation(
            "CITATION_MISMATCH", "$.citations", "Citations must equal available required evidence"
        ))

    expected_tools = _expected_tools(case, rule["decision"])
    actual_tools = output["toolCalls"]
    if [item["name"] for item in actual_tools] != [item["name"] for item in expected_tools]:
        violations.append(PolicyViolation(
            "TOOL_PLAN_MISMATCH", "$.toolCalls", "Tool names and order must match policy"
        ))
    elif actual_tools != expected_tools:
        violations.append(PolicyViolation(
            "TOOL_ARGUMENT_MISMATCH", "$.toolCalls", "Tool arguments must match event context"
        ))

    if violations:
        return _blocked(case, violations, started)
    return PolicyResult(
        accepted=True,
        output=output,
        violations=(),
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def _blocked(
    case: GoldenCase,
    violations: list[PolicyViolation],
    started: float,
) -> PolicyResult:
    return PolicyResult(
        accepted=False,
        output=_fallback(case),
        violations=tuple(violations),
        latency_ms=(time.perf_counter() - started) * 1000,
    )


def guarded_response(response: TargetResponse, policy: PolicyResult) -> TargetResponse:
    return TargetResponse(
        output=policy.output,
        raw_output=json.dumps(policy.output, ensure_ascii=False),
        latency_ms=response.latency_ms + policy.latency_ms,
        ttft_ms=response.ttft_ms,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        peak_vram_mb=response.peak_vram_mb,
        error=None,
    )
