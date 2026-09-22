from __future__ import annotations

import argparse
import html
import json
import math
import statistics
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mineguard_eval.metrics import aggregate_results, evaluate_case, evaluate_gates
from mineguard_eval.models import GoldenCase, TargetResponse, load_goldens
from mineguard_eval.policy_gateway import apply_policy_gateway, guarded_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay saved model outputs through the MineGuard deterministic safety gateway"
    )
    parser.add_argument("--matrix-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "datasets" / "mineguard-goldens-v1.jsonl"
    )
    parser.add_argument(
        "--schema", type=Path, default=ROOT / "schemas" / "agent-decision-v1.schema.json"
    )
    parser.add_argument(
        "--gates", type=Path, default=ROOT / "config" / "release-gates.json"
    )
    parser.add_argument("--profile", default="candidate-model")
    parser.add_argument("--include", nargs="*", help="Optional model directory names")
    return parser.parse_args()


def _response(row: dict[str, Any]) -> TargetResponse:
    return TargetResponse(
        output=row.get("output"),
        raw_output=row.get("raw_output", ""),
        latency_ms=float(row.get("latency_ms", 0.0)),
        ttft_ms=row.get("ttft_ms"),
        input_tokens=row.get("input_tokens"),
        output_tokens=row.get("output_tokens"),
        peak_vram_mb=row.get("peak_vram_mb"),
        error=row.get("error"),
    )


def _finite(value: float) -> float | None:
    return None if math.isnan(value) or math.isinf(value) else value


def compare_run_payload(
    payload: dict[str, Any],
    case_by_id: dict[str, GoldenCase],
    schema: dict[str, Any],
    gate_profile: dict[str, Any],
) -> dict[str, Any]:
    raw_results = []
    guarded_results = []
    policy_cases = []
    for row in payload["cases"]:
        case = case_by_id[row["case_id"]]
        response = _response(row)
        raw_evaluation = evaluate_case(case, response, schema)
        policy = apply_policy_gateway(case, response, schema)
        guarded_evaluation = evaluate_case(case, guarded_response(response, policy), schema)
        raw_results.append(raw_evaluation)
        guarded_results.append(guarded_evaluation)
        policy_cases.append({
            "case_id": case.id,
            "accepted": policy.accepted,
            "policy_latency_ms": policy.latency_ms,
            "violations": [asdict(item) for item in policy.violations],
            "raw_output": response.output,
            "safe_output": policy.output,
        })

    raw_aggregate = aggregate_results(raw_results)
    guarded_aggregate = aggregate_results(guarded_results)
    raw_gate = evaluate_gates(raw_aggregate, gate_profile)
    guarded_gate = evaluate_gates(guarded_aggregate, gate_profile)
    violation_counts = Counter(
        violation["code"] for item in policy_cases for violation in item["violations"]
    )
    blocked = [item for item in policy_cases if not item["accepted"]]
    review_escalations = sum(
        1
        for item in blocked
        if case_by_id[item["case_id"]].expected["decision"] != "HUMAN_REVIEW"
    )
    return {
        "target": payload.get("target"),
        "profile": payload.get("profile"),
        "raw_gate": raw_gate,
        "guarded_gate": guarded_gate,
        "raw_aggregate": {key: _finite(value) for key, value in raw_aggregate.items()},
        "guarded_aggregate": {key: _finite(value) for key, value in guarded_aggregate.items()},
        "policy": {
            "total_cases": len(policy_cases),
            "accepted_cases": len(policy_cases) - len(blocked),
            "blocked_cases": len(blocked),
            "block_rate": len(blocked) / len(policy_cases),
            "review_escalations": review_escalations,
            "review_escalation_rate": review_escalations / len(policy_cases),
            "mean_latency_ms": statistics.fmean(item["policy_latency_ms"] for item in policy_cases),
            "violation_counts": dict(sorted(violation_counts.items())),
        },
        "cases": policy_cases,
    }


def _mean(runs: list[dict[str, Any]], section: str, metric: str) -> float | None:
    values = [item[section].get(metric) for item in runs]
    numeric = [float(item) for item in values if isinstance(item, (int, float))]
    return statistics.fmean(numeric) if numeric else None


def summarize_model(name: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    violations = Counter()
    for run in runs:
        violations.update(run["policy"]["violation_counts"])
    total_cases = sum(run["policy"]["total_cases"] for run in runs)
    blocked = sum(run["policy"]["blocked_cases"] for run in runs)
    escalations = sum(run["policy"]["review_escalations"] for run in runs)
    metrics = (
        "schema_valid_rate",
        "risk_accuracy",
        "decision_accuracy",
        "citation_precision",
        "citation_recall",
        "tool_precision",
        "tool_recall",
        "p95_latency_ms",
    )
    return {
        "name": name,
        "runs": len(runs),
        "raw_passed_runs": sum(run["raw_gate"]["passed"] for run in runs),
        "guarded_passed_runs": sum(run["guarded_gate"]["passed"] for run in runs),
        "total_cases": total_cases,
        "accepted_cases": total_cases - blocked,
        "blocked_cases": blocked,
        "block_rate": blocked / total_cases,
        "review_escalations": escalations,
        "review_escalation_rate": escalations / total_cases,
        "mean_policy_latency_ms": statistics.fmean(run["policy"]["mean_latency_ms"] for run in runs),
        "violation_counts": dict(sorted(violations.items())),
        "raw_metrics": {metric: _mean(runs, "raw_aggregate", metric) for metric in metrics},
        "guarded_metrics": {metric: _mean(runs, "guarded_aggregate", metric) for metric in metrics},
    }


def _display(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_reports(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "guarded-comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# MineGuard Raw vs Guarded System Comparison",
        "",
        f"- Source matrix: `{result['source_matrix']}`",
        f"- Generated at: `{result['generated_at']}`",
        "- The model is not rerun; saved raw outputs are replayed through the deterministic policy gateway.",
        "",
        "| Model | Runs | Raw pass | Guarded pass | Accepted | Block rate | Review escalation | Policy latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result["models"]:
        lines.append(
            f"| {item['name']} | {item['runs']} | {item['raw_passed_runs']}/{item['runs']} | "
            f"{item['guarded_passed_runs']}/{item['runs']} | {item['accepted_cases']}/{item['total_cases']} | "
            f"{item['block_rate']:.2%} | {item['review_escalation_rate']:.2%} | "
            f"{item['mean_policy_latency_ms']:.3f} ms |"
        )
    lines.extend(["", "## Quality impact", ""])
    for item in result["models"]:
        raw = item["raw_metrics"]
        guarded = item["guarded_metrics"]
        lines.extend([
            f"### {item['name']}",
            "",
            "| Metric | Raw | Guarded |",
            "|---|---:|---:|",
            f"| Schema valid rate | {_display(raw['schema_valid_rate'])} | {_display(guarded['schema_valid_rate'])} |",
            f"| Decision accuracy | {_display(raw['decision_accuracy'])} | {_display(guarded['decision_accuracy'])} |",
            f"| Citation precision | {_display(raw['citation_precision'])} | {_display(guarded['citation_precision'])} |",
            f"| Tool precision | {_display(raw['tool_precision'])} | {_display(guarded['tool_precision'])} |",
            f"| Tool recall | {_display(raw['tool_recall'])} | {_display(guarded['tool_recall'])} |",
            f"| Violations | `{json.dumps(item['violation_counts'], ensure_ascii=False)}` | blocked before execution |",
            "",
        ])
    lines.extend([
        "> A guarded gate failure can mean the gateway safely escalated an invalid model plan to human review,",
        "> but no longer matched the ideal automated decision. Safety containment and task fidelity are reported separately.",
    ])
    (output_dir / "guarded-comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['name'])}</td><td>{item['runs']}</td>"
        f"<td>{item['raw_passed_runs']}/{item['runs']}</td>"
        f"<td>{item['guarded_passed_runs']}/{item['runs']}</td>"
        f"<td>{item['accepted_cases']}/{item['total_cases']}</td>"
        f"<td>{item['block_rate']:.2%}</td><td>{item['review_escalation_rate']:.2%}</td>"
        f"<td>{item['mean_policy_latency_ms']:.3f} ms</td></tr>"
        for item in result["models"]
    )
    document = f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>MineGuard Guarded Comparison</title>
<style>:root{{--ink:#14251f;--green:#08735a;--cream:#f4efe2;--line:#d6d0c1}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#dcece4,var(--cream) 52%);color:var(--ink);font-family:Georgia,serif}}main{{max-width:1180px;margin:auto;padding:56px 28px}}h1{{font-size:clamp(2.5rem,6vw,5rem);line-height:.92;margin:0 0 18px}}p{{max-width:760px;color:#53665e}}table{{width:100%;margin-top:36px;border-collapse:collapse;background:#fff9;font:14px Consolas,monospace}}th,td{{padding:14px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#173d32;color:white}}.note{{margin-top:28px;border-left:7px solid var(--green);padding:15px 20px;background:#fff9}}</style></head>
<body><main><h1>Raw Model<br>vs Safety Gateway</h1><p>Saved RTX 5090 outputs replayed through the deterministic policy boundary. No model inference was repeated.</p><table><thead><tr><th>Model</th><th>Runs</th><th>Raw pass</th><th>Guarded pass</th><th>Accepted</th><th>Block rate</th><th>Review escalation</th><th>Policy latency</th></tr></thead><tbody>{rows}</tbody></table><div class=\"note\">Safety containment and ideal-task fidelity are separate: a blocked plan can be safe while intentionally requiring human review.</div></main></body></html>"""
    (output_dir / "guarded-comparison.html").write_text(document, encoding="utf-8")


def main() -> int:
    args = parse_args()
    matrix_dir = args.matrix_dir.resolve()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    gates = json.loads(args.gates.read_text(encoding="utf-8"))
    gate_profile = gates["profiles"][args.profile]
    cases = load_goldens(args.dataset)
    case_by_id = {case.id: case for case in cases}
    selected = set(args.include or [])
    model_runs: dict[str, list[dict[str, Any]]] = {}
    run_files = sorted(matrix_dir.glob("*/run-*/results.json"))
    if not run_files:
        raise FileNotFoundError(f"No model run results found under {matrix_dir}")
    for path in run_files:
        model_name = path.parent.parent.name
        if selected and model_name not in selected:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        comparison = compare_run_payload(payload, case_by_id, schema, gate_profile)
        comparison["source"] = str(path)
        comparison["run"] = path.parent.name
        model_runs.setdefault(model_name, []).append(comparison)
        print(
            f"{model_name}/{path.parent.name}: raw={'PASS' if comparison['raw_gate']['passed'] else 'FAIL'} "
            f"guarded={'PASS' if comparison['guarded_gate']['passed'] else 'FAIL'} "
            f"blocked={comparison['policy']['blocked_cases']}/{comparison['policy']['total_cases']}"
        )
    if not model_runs:
        raise ValueError("No model results matched --include")

    result = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_matrix": str(matrix_dir),
        "profile": args.profile,
        "models": [summarize_model(name, runs) for name, runs in model_runs.items()],
        "runs": model_runs,
    }
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = (args.output_dir or ROOT / "reports" / f"{timestamp}-guarded-replay").resolve()
    write_reports(output_dir, result)
    print(f"Reports: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
