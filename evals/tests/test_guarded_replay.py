from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from mineguard_eval.models import load_goldens
from mineguard_eval.targets import RuleContractTarget
from run_guarded_replay import compare_run_payload, summarize_model


class GuardedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (EVAL_ROOT / "schemas" / "agent-decision-v1.schema.json").read_text(encoding="utf-8")
        )
        gates = json.loads((EVAL_ROOT / "config" / "release-gates.json").read_text(encoding="utf-8"))
        cls.profile = gates["profiles"]["candidate-model"]
        cls.cases = load_goldens(EVAL_ROOT / "datasets" / "mineguard-goldens-v1.jsonl")

    def payload(self) -> dict:
        target = RuleContractTarget()
        rows = []
        for case in self.cases:
            response = target.invoke(case)
            rows.append({
                "case_id": case.id,
                "output": response.output,
                "raw_output": response.raw_output,
                "latency_ms": response.latency_ms,
                "ttft_ms": None,
                "input_tokens": None,
                "output_tokens": None,
                "peak_vram_mb": None,
                "error": None,
            })
        return {"target": target.name, "profile": "candidate-model", "cases": rows}

    def test_valid_run_passes_raw_and_guarded_without_blocks(self) -> None:
        result = compare_run_payload(
            self.payload(), {case.id: case for case in self.cases}, self.schema, self.profile
        )
        self.assertTrue(result["raw_gate"]["passed"])
        self.assertTrue(result["guarded_gate"]["passed"])
        self.assertEqual(0, result["policy"]["blocked_cases"])

    def test_unknown_citation_is_fixed_by_safe_fallback(self) -> None:
        payload = self.payload()
        row = next(item for item in payload["cases"] if item["case_id"] == "missing-evidence-review")
        row["output"]["citations"] = ["SOP-FUEL-SMOKE-001"]
        row["raw_output"] = json.dumps(row["output"])
        result = compare_run_payload(
            payload, {case.id: case for case in self.cases}, self.schema, self.profile
        )
        self.assertFalse(result["raw_gate"]["passed"])
        self.assertTrue(result["guarded_gate"]["passed"])
        self.assertEqual(1, result["policy"]["blocked_cases"])
        summary = summarize_model("small-model", [result])
        self.assertEqual(1, summary["guarded_passed_runs"])
        self.assertEqual(0, summary["review_escalations"])


if __name__ == "__main__":
    unittest.main()
