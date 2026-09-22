from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from download_qwen_models import load_matrix, validate_model_dir
from run_model_matrix import calculate_consistency, select_smallest_passing, summarize_model


def fake_run(*, gate_passed: bool = True, decision: str = "ESCALATE") -> dict:
    return {
        "gate": {"passed": gate_passed},
        "aggregate": {
            "schema_valid_rate": 1.0,
            "risk_accuracy": 1.0,
            "decision_accuracy": 1.0,
            "high_risk_recall": 1.0,
            "human_approval_recall": 1.0,
            "citation_precision": 1.0,
            "citation_recall": 1.0,
            "tool_precision": 1.0,
            "tool_recall": 1.0,
            "forbidden_tool_violation_rate": 0.0,
            "prompt_injection_pass_rate": 1.0,
            "p95_latency_ms": 1000.0,
            "peak_vram_mb": 2048.0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "output": {
                    "riskLevel": "HIGH",
                    "decision": decision,
                    "reasonCodes": ["SMOKING_REPEATED"],
                    "citations": ["SOP-1"],
                    "requiresHumanApproval": True,
                    "toolCalls": [{"name": "request_human_approval", "arguments": {"eventId": "1"}}],
                },
            }
        ],
    }


class ModelMatrixTests(unittest.TestCase):
    def test_matrix_config_contains_three_ordered_qwen_models(self) -> None:
        matrix = load_matrix(EVAL_ROOT / "config" / "qwen-matrix-5090.json")
        self.assertEqual(["Qwen3-1.7B", "Qwen3-4B", "Qwen3-8B"], [m["name"] for m in matrix["models"]])
        self.assertTrue(all(model["dtype"] == "bfloat16" for model in matrix["models"]))

    def test_consistency_requires_identical_control_fields(self) -> None:
        self.assertEqual(1.0, calculate_consistency([fake_run(), fake_run()]))
        self.assertEqual(0.0, calculate_consistency([fake_run(), fake_run(decision="NOTIFY")]))

    def test_smallest_model_is_selected_only_after_all_repeats_pass(self) -> None:
        models = [
            {"name": "small", "parameters_b": 1.7, "all_runs_passed": False, "completed_runs": 3},
            {"name": "medium", "parameters_b": 4.0, "all_runs_passed": True, "completed_runs": 3},
            {"name": "large", "parameters_b": 8.0, "all_runs_passed": True, "completed_runs": 3},
        ]
        self.assertEqual("medium", select_smallest_passing(models, expected_runs=3))
        models[1]["completed_runs"] = 2
        self.assertEqual("large", select_smallest_passing(models, expected_runs=3))

    def test_summary_keeps_errors_and_mean_metrics(self) -> None:
        model = {
            "name": "Qwen3-test",
            "model_id": "Qwen/Qwen3-test",
            "parameters_b": 1.0,
            "dtype": "bfloat16",
        }
        summary = summarize_model(model, [fake_run(), fake_run()], [])
        self.assertTrue(summary["all_runs_passed"])
        self.assertEqual(1.0, summary["structured_output_consistency"])
        self.assertEqual(1000.0, summary["metrics_mean"]["p95_latency_ms"])

    def test_model_directory_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIn("config.json", validate_model_dir(root))
            (root / "config.json").write_text("{}", encoding="utf-8")
            (root / "tokenizer_config.json").write_text("{}", encoding="utf-8")
            (root / "model-00001-of-00001.safetensors").write_bytes(b"test")
            self.assertEqual([], validate_model_dir(root))


if __name__ == "__main__":
    unittest.main()
