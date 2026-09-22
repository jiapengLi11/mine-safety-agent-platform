from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoldenCase:
    id: str
    module: str
    tags: tuple[str, ...]
    input: dict[str, Any]
    expected: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GoldenCase":
        return cls(
            id=value["id"],
            module=value.get("module", "unknown"),
            tags=tuple(value.get("tags", [])),
            input=value["input"],
            expected=value["expected"],
        )


@dataclass
class TargetResponse:
    output: dict[str, Any] | None
    raw_output: str
    latency_ms: float
    ttft_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    peak_vram_mb: float | None = None
    error: str | None = None


@dataclass
class CaseEvaluation:
    case_id: str
    tags: list[str]
    output: dict[str, Any] | None
    raw_output: str
    latency_ms: float
    ttft_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    peak_vram_mb: float | None
    error: str | None
    schema_errors: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    harness_scores: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_goldens(path: Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                cases.append(GoldenCase.from_dict(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"Invalid golden at {path}:{line_number}: {exc}") from exc
    if not cases:
        raise ValueError(f"No golden cases found in {path}")
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Golden case IDs must be unique")
    return cases

