from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from mineguard_eval.metrics import aggregate_results, evaluate_case, evaluate_gates
from mineguard_eval.models import TargetResponse, load_goldens
from mineguard_eval.targets import RuleContractTarget, extract_json_object


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (EVAL_ROOT / "schemas" / "agent-decision-v1.schema.json").read_text(encoding="utf-8")
        )
        cls.cases = load_goldens(EVAL_ROOT / "datasets" / "mineguard-goldens-v1.jsonl")

    def test_rule_contract_baseline_passes_ci_gate(self) -> None:
        target = RuleContractTarget()
        results = [evaluate_case(case, target.invoke(case), self.schema) for case in self.cases]
        aggregate = aggregate_results(results)
        gates = json.loads((EVAL_ROOT / "config" / "release-gates.json").read_text(encoding="utf-8"))
        self.assertTrue(evaluate_gates(aggregate, gates["profiles"]["ci"])["passed"])

    def test_forbidden_tool_and_unknown_citation_are_detected(self) -> None:
        case = self.cases[0]
        output = RuleContractTarget().invoke(case).output
        assert output is not None
        output["toolCalls"].append({"name": "execute_sql", "arguments": {"sql": "DROP TABLE alerts"}})
        output["citations"].append("MADE-UP-SOP")
        result = evaluate_case(
            case,
            TargetResponse(output=output, raw_output=json.dumps(output), latency_ms=1),
            self.schema,
        )
        self.assertEqual(0.0, result.metrics["no_forbidden_tools"])
        self.assertEqual(0.0, result.metrics["no_unknown_citations"])

    def test_json_extraction_ignores_leading_text(self) -> None:
        self.assertEqual({"riskLevel": "LOW"}, extract_json_object('note\n{"riskLevel":"LOW"}\nend'))

    def test_unexpected_tools_reduce_precision(self) -> None:
        case = next(item for item in self.cases if item.id == "smoking-single-observe")
        output = RuleContractTarget().invoke(case).output
        assert output is not None
        output["toolCalls"] = [
            {
                "name": "record_alert",
                "arguments": {"eventId": "EVT-SMOKE-002", "cameraId": "CAM-01"},
            }
        ]
        result = evaluate_case(
            case,
            TargetResponse(output=output, raw_output=json.dumps(output), latency_ms=1),
            self.schema,
        )
        self.assertEqual(0.0, result.metrics["tool_precision"])
        self.assertEqual(0.0, result.metrics["tool_recall"])

    def test_malformed_collection_types_fail_without_crashing(self) -> None:
        case = self.cases[0]
        output = RuleContractTarget().invoke(case).output
        assert output is not None
        output["citations"] = [{"invented": True}]
        output["reasonCodes"] = "SMOKING_REPEATED"
        result = evaluate_case(
            case,
            TargetResponse(output=output, raw_output=json.dumps(output), latency_ms=1),
            self.schema,
        )
        self.assertEqual(0.0, result.metrics["schema_valid"])
        self.assertEqual(0.0, result.metrics["reason_codes_exact"])
        self.assertEqual(0.0, result.metrics["citation_recall"])

    def test_duplicate_golden_ids_are_rejected(self) -> None:
        temporary = EVAL_ROOT / "tests" / ".duplicate.jsonl"
        try:
            row = {"id": "same", "input": {}, "expected": {}}
            temporary.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_goldens(temporary)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
