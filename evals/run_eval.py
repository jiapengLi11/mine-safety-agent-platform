from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mineguard_eval.harness_adapter import run_harness_metrics
from mineguard_eval.metrics import aggregate_results, evaluate_case, evaluate_gates
from mineguard_eval.models import load_goldens
from mineguard_eval.report import write_reports
from mineguard_eval.targets import OpenAICompatibleTarget, RuleContractTarget, TransformersQwenTarget


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MineGuard structured safety decisions")
    parser.add_argument("--target", choices=["rule", "qwen", "openai"], default="rule")
    parser.add_argument("--profile", choices=["ci", "candidate-model"], default="ci")
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets" / "mineguard-goldens-v1.jsonl")
    parser.add_argument("--schema", type=Path, default=ROOT / "schemas" / "agent-decision-v1.schema.json")
    parser.add_argument("--gates", type=Path, default=ROOT / "config" / "release-gates.json")
    parser.add_argument("--system-prompt", type=Path, default=ROOT / "prompts" / "system-v1.txt")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--enforce-gate", action="store_true")
    parser.add_argument("--model-path", type=Path, default=Path(r"E:\project11\model_cache\Qwen3-0.6B-c1899de"))
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--dtype", choices=["auto", "float16", "bfloat16", "float32"], default="float16"
    )
    parser.add_argument("--max-new-tokens", type=int, default=384)
    parser.add_argument("--base-url", default=os.getenv("MINEGUARD_LLM_BASE_URL", "http://127.0.0.1:8000/v1"))
    parser.add_argument("--model", default=os.getenv("MINEGUARD_LLM_MODEL", "Qwen3-1.7B"))
    parser.add_argument("--api-key", default=os.getenv("MINEGUARD_LLM_API_KEY", "local-dev"))
    return parser.parse_args()


def build_target(args: argparse.Namespace, schema: dict, system_prompt: str):
    if args.target == "rule":
        return RuleContractTarget()
    if args.target == "qwen":
        return TransformersQwenTarget(
            model_path=args.model_path,
            system_prompt=system_prompt,
            schema=schema,
            device=args.device,
            dtype_name=args.dtype,
            max_new_tokens=args.max_new_tokens,
        )
    return OpenAICompatibleTarget(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        system_prompt=system_prompt,
        schema=schema,
    )


def safe_json_number(value: float) -> float | None:
    return None if math.isnan(value) or math.isinf(value) else value


def main() -> int:
    args = parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    gate_config = json.loads(args.gates.read_text(encoding="utf-8"))
    system_prompt = args.system_prompt.read_text(encoding="utf-8")
    cases = load_goldens(args.dataset)
    if args.limit:
        cases = cases[: args.limit]
    target = build_target(args, schema, system_prompt)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = args.output_dir or ROOT / "reports" / f"{timestamp}-{args.target}"
    print(f"Target: {target.name}; cases: {len(cases)}; profile: {args.profile}")
    results = []
    for index, case in enumerate(cases, start=1):
        try:
            response = target.invoke(case)
        except Exception as exc:
            from mineguard_eval.models import TargetResponse

            response = TargetResponse(
                output=None, raw_output="", latency_ms=0.0, error=f"{type(exc).__name__}: {exc}"
            )
        result = evaluate_case(case, response, schema)
        result.harness_scores = run_harness_metrics(case, result, schema)
        results.append(result)
        status_keys = (
            "schema_valid",
            "risk_correct",
            "decision_correct",
            "approval_correct",
            "reason_codes_exact",
            "citation_precision",
            "citation_recall",
            "tool_precision",
            "tool_recall",
            "no_forbidden_tools",
            "no_unknown_citations",
            "prompt_injection_pass",
        )
        status = "PASS" if all(result.metrics[key] == 1.0 for key in status_keys) else "FAIL"
        print(f"[{index:02d}/{len(cases):02d}] {status} {case.id} {result.latency_ms:.1f} ms")

    aggregate = aggregate_results(results)
    profile = gate_config["profiles"][args.profile]
    gate = evaluate_gates(aggregate, profile)
    environment = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "target": target.name,
        "model_path": str(args.model_path) if args.target == "qwen" else None,
        "dtype": getattr(target, "dtype_name", None),
    }
    aggregate = {key: safe_json_number(value) for key, value in aggregate.items()}
    # Gate calculations are complete before non-finite display values become JSON null.
    for check in gate["checks"].values():
        check["actual"] = safe_json_number(check["actual"])
    write_reports(output_dir, target.name, args.profile, aggregate, gate, results, environment)
    print(f"Gate: {'PASS' if gate['passed'] else 'FAIL'}")
    print(f"Reports: {output_dir}")
    return 1 if args.enforce_gate and not gate["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
