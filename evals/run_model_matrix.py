from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from download_qwen_models import load_matrix, validate_model_dir


ROOT = Path(__file__).resolve().parent
QUALITY_METRICS = (
    "schema_valid_rate",
    "risk_accuracy",
    "decision_accuracy",
    "high_risk_recall",
    "human_approval_recall",
    "citation_precision",
    "citation_recall",
    "tool_precision",
    "tool_recall",
    "forbidden_tool_violation_rate",
    "prompt_injection_pass_rate",
)
PERFORMANCE_METRICS = (
    "p50_latency_ms",
    "p95_latency_ms",
    "p50_ttft_ms",
    "p95_ttft_ms",
    "p50_tpot_ms",
    "p95_tpot_ms",
    "mean_output_tokens_per_second",
    "peak_vram_mb",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MineGuard Qwen model matrix sequentially")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "qwen-matrix-5090.json")
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--include", nargs="*", help="Optional model names")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-new-tokens", type=int, default=384)
    parser.add_argument("--dry-run", action="store_true", help="Validate files and CUDA without loading models")
    parser.add_argument("--enforce-one-pass", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_case_signature(case: dict[str, Any]) -> str:
    output = case.get("output") or {}
    tools = [
        {"name": item.get("name"), "arguments": item.get("arguments", {})}
        for item in output.get("toolCalls", [])
        if isinstance(item, dict)
    ]
    value = {
        "riskLevel": output.get("riskLevel"),
        "decision": output.get("decision"),
        "reasonCodes": output.get("reasonCodes"),
        "citations": output.get("citations"),
        "requiresHumanApproval": output.get("requiresHumanApproval"),
        "toolCalls": tools,
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def calculate_consistency(runs: list[dict[str, Any]]) -> float | None:
    if len(runs) < 2:
        return None
    per_case: dict[str, list[str]] = {}
    for run in runs:
        for case in run.get("cases", []):
            per_case.setdefault(case["case_id"], []).append(stable_case_signature(case))
    stable = sum(1 for values in per_case.values() if len(values) == len(runs) and len(set(values)) == 1)
    return stable / len(per_case) if per_case else None


def mean_metric(runs: list[dict[str, Any]], metric: str) -> float | None:
    values = [run.get("aggregate", {}).get(metric) for run in runs]
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return statistics.fmean(numeric) if numeric else None


def summarize_model(model: dict[str, Any], runs: list[dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {
        metric: mean_metric(runs, metric) for metric in (*QUALITY_METRICS, *PERFORMANCE_METRICS)
    }
    return {
        "name": model["name"],
        "model_id": model["model_id"],
        "parameters_b": model["parameters_b"],
        "dtype": model["dtype"],
        "completed_runs": len(runs),
        "all_runs_passed": bool(runs) and not errors and all(run["gate"]["passed"] for run in runs),
        "structured_output_consistency": calculate_consistency(runs),
        "metrics_mean": metrics,
        "errors": errors,
    }


def select_smallest_passing(summaries: list[dict[str, Any]], expected_runs: int) -> str | None:
    eligible = [
        item
        for item in summaries
        if item["all_runs_passed"] and item["completed_runs"] == expected_runs
    ]
    return min(eligible, key=lambda item: item["parameters_b"])["name"] if eligible else None


def display(value: Any, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def write_matrix_reports(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "matrix-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# MineGuard Qwen Model Matrix",
        "",
        f"- Completed: `{payload['generated_at']}`",
        f"- Repeats per model: `{payload['repeats']}`",
        f"- Smallest model passing every run: **{payload['smallest_passing_model'] or 'NONE'}**",
        "",
        "| Model | Runs | All pass | Consistency | Risk | Decision | Tools P/R | P95 latency | P95 TTFT | P95 TPOT | Peak VRAM |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in payload["models"]:
        m = item["metrics_mean"]
        lines.append(
            f"| {item['name']} | {item['completed_runs']} | {'PASS' if item['all_runs_passed'] else 'FAIL'} | "
            f"{display(item['structured_output_consistency'])} | {display(m['risk_accuracy'])} | "
            f"{display(m['decision_accuracy'])} | {display(m['tool_precision'])}/{display(m['tool_recall'])} | "
            f"{display(m['p95_latency_ms'], 1)} ms | {display(m['p95_ttft_ms'], 1)} ms | "
            f"{display(m['p95_tpot_ms'], 2)} ms | {display(m['peak_vram_mb'], 1)} MB |"
        )
    lines.extend(
        [
            "",
            "> Selection rule: choose the smallest model only when every configured repeat passes the candidate-model gate.",
            "> This benchmark is an engineering acceptance suite, not a publication-scale capability claim.",
        ]
    )
    (output_dir / "matrix-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['name'])}</td><td>{item['completed_runs']}</td>"
        f"<td class=\"{'pass' if item['all_runs_passed'] else 'fail'}\">{'PASS' if item['all_runs_passed'] else 'FAIL'}</td>"
        f"<td>{display(item['structured_output_consistency'])}</td>"
        f"<td>{display(item['metrics_mean']['risk_accuracy'])}</td>"
        f"<td>{display(item['metrics_mean']['decision_accuracy'])}</td>"
        f"<td>{display(item['metrics_mean']['tool_precision'])}/{display(item['metrics_mean']['tool_recall'])}</td>"
        f"<td>{display(item['metrics_mean']['p95_latency_ms'], 1)} ms</td>"
        f"<td>{display(item['metrics_mean']['peak_vram_mb'], 1)} MB</td></tr>"
        for item in payload["models"]
    )
    document = f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>MineGuard Qwen Matrix</title>
<style>body{{margin:0;background:#edf1e8;color:#17231f;font-family:Georgia,serif}}main{{max-width:1200px;margin:auto;padding:48px 28px}}h1{{font-size:48px;margin-bottom:8px}}.pick{{padding:18px;border-left:8px solid #0d6b57;background:#fff;margin:26px 0}}table{{width:100%;border-collapse:collapse;background:#fff;font:14px Consolas,monospace}}th,td{{padding:13px;border-bottom:1px solid #d5dacd;text-align:left}}th{{background:#17352d;color:white}}.pass{{color:#08735a;font-weight:bold}}.fail{{color:#b33b2e;font-weight:bold}}small{{color:#65736d}}</style></head>
<body><main><h1>MineGuard Qwen Matrix</h1><small>{html.escape(payload['generated_at'])}</small><div class=\"pick\">Smallest all-pass model: <strong>{html.escape(payload['smallest_passing_model'] or 'NONE')}</strong></div>
<table><thead><tr><th>Model</th><th>Runs</th><th>Gate</th><th>Consistency</th><th>Risk</th><th>Decision</th><th>Tools P/R</th><th>P95 latency</th><th>Peak VRAM</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>"""
    (output_dir / "matrix-report.html").write_text(document, encoding="utf-8")


def check_cuda(device: str) -> dict[str, Any]:
    if not device.startswith("cuda"):
        return {"available": False, "device": device}
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is missing from the active environment") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available to PyTorch")
    return {
        "available": True,
        "device": device,
        "visible_devices": os.getenv("CUDA_VISIBLE_DEVICES"),
        "name": torch.cuda.get_device_name(0),
        "bf16_supported": torch.cuda.is_bf16_supported(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
    }


def main() -> int:
    args = parse_args()
    matrix = load_matrix(args.config)
    repeats = args.repeats or int(matrix.get("repeats", 3))
    if repeats < 1:
        raise ValueError("--repeats must be at least 1")
    model_root = (args.model_root or Path(matrix["model_root"])).resolve()
    selected = set(args.include or [])
    models = [
        item
        for item in matrix["models"]
        if item.get("enabled", True) and (not selected or item["name"] in selected)
    ]
    if not models:
        raise ValueError("No enabled models matched --include")

    required = [
        ROOT / "datasets" / "mineguard-goldens-v1.jsonl",
        ROOT / "schemas" / "agent-decision-v1.schema.json",
        ROOT / "prompts" / "system-v1.txt",
        ROOT / "config" / "release-gates.json",
    ]
    missing_files = [str(path) for path in required if not path.is_file()]
    missing_models = {
        item["name"]: validate_model_dir(model_root / item["relative_path"])
        for item in models
        if validate_model_dir(model_root / item["relative_path"])
    }
    if missing_files or missing_models:
        raise FileNotFoundError(
            f"Preflight failed. Missing files={missing_files}; incomplete models={missing_models}"
        )
    cuda = check_cuda(args.device)
    print(f"PREFLIGHT PASS: {len(models)} models; repeats={repeats}; CUDA={cuda}")
    if args.dry_run:
        print("DRY RUN ONLY: no model was loaded and no inference was started.")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = (args.output_dir or ROOT / "reports" / f"{timestamp}-qwen-matrix").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hashes = {path.name: sha256_file(path) for path in required}
    summaries: list[dict[str, Any]] = []
    progress: dict[str, Any] = {
        "schema_version": "1.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats,
        "model_root": str(model_root),
        "cuda": cuda,
        "source_hashes": source_hashes,
        "models": [],
    }

    for model_index, model in enumerate(models, start=1):
        model_path = model_root / model["relative_path"]
        run_payloads: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        print(f"\n=== [{model_index}/{len(models)}] {model['name']} ===")
        for repeat in range(1, repeats + 1):
            run_dir = output_dir / model["name"] / f"run-{repeat:02d}"
            command = [
                sys.executable,
                str(ROOT / "run_eval.py"),
                "--target", "qwen",
                "--profile", "candidate-model",
                "--model-path", str(model_path),
                "--device", args.device,
                "--dtype", model["dtype"],
                "--max-new-tokens", str(args.max_new_tokens),
                "--output-dir", str(run_dir),
            ]
            print(f"Run {repeat}/{repeats}: {' '.join(command)}")
            completed = subprocess.run(command, cwd=ROOT.parent, check=False)
            results_path = run_dir / "results.json"
            if completed.returncode != 0 or not results_path.is_file():
                error = {"repeat": repeat, "returncode": completed.returncode, "results": str(results_path)}
                errors.append(error)
                print(f"RUN FAILED: {error}")
                break
            run_payloads.append(json.loads(results_path.read_text(encoding="utf-8")))
            progress["models"] = summaries + [summarize_model(model, run_payloads, errors)]
            (output_dir / "matrix-progress.json").write_text(
                json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        summary = summarize_model(model, run_payloads, errors)
        summaries.append(summary)
        progress["models"] = summaries
        (output_dir / "matrix-progress.json").write_text(
            json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    smallest = select_smallest_passing(summaries, repeats)
    payload = {
        **progress,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "smallest_passing_model": smallest,
        "models": summaries,
    }
    write_matrix_reports(output_dir, payload)
    print(f"\nMatrix complete. Smallest all-pass model: {smallest or 'NONE'}")
    print(f"Reports: {output_dir}")
    return 1 if args.enforce_one_pass and smallest is None else 0


if __name__ == "__main__":
    raise SystemExit(main())
