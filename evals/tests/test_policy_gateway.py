from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from mineguard_eval.models import TargetResponse, load_goldens
from mineguard_eval.policy_gateway import MAX_OUTPUT_CHARACTERS, apply_policy_gateway
from mineguard_eval.targets import RuleContractTarget


class PolicyGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (EVAL_ROOT / "schemas" / "agent-decision-v1.schema.json").read_text(encoding="utf-8")
        )
        cls.cases = load_goldens(EVAL_ROOT / "datasets" / "mineguard-goldens-v1.jsonl")

    def response(self, case_id: str) -> tuple[object, TargetResponse]:
        case = next(item for item in self.cases if item.id == case_id)
        response = RuleContractTarget().invoke(case)
        return case, response

    def test_accepts_exact_rule_plan(self) -> None:
        case, response = self.response("smoking-repeat-high")
        result = apply_policy_gateway(case, response, self.schema)
        self.assertTrue(result.accepted)
        self.assertEqual((), result.violations)

    def test_blocks_unknown_citation_and_preserves_rule_reason(self) -> None:
        case, response = self.response("missing-evidence-review")
        assert response.output is not None
        response.output["citations"] = ["SOP-FUEL-SMOKE-001"]
        response.raw_output = json.dumps(response.output)
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertIn("UNKNOWN_CITATION", {item.code for item in result.violations})
        self.assertEqual(["REQUIRED_EVIDENCE_MISSING"], result.output["reasonCodes"])
        self.assertEqual([], result.output["citations"])

    def test_blocks_schema_metadata(self) -> None:
        case, response = self.response("smoking-repeat-high")
        assert response.output is not None
        response.output["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        response.raw_output = json.dumps(response.output)
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertIn("UNEXPECTED_FIELD", {item.code for item in result.violations})

    def test_blocks_risk_downgrade(self) -> None:
        case, response = self.response("smoking-repeat-high")
        assert response.output is not None
        response.output["riskLevel"] = "LOW"
        response.raw_output = json.dumps(response.output)
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertEqual("HIGH", result.output["riskLevel"])

    def test_blocks_forbidden_tool(self) -> None:
        case, response = self.response("smoking-repeat-high")
        assert response.output is not None
        response.output["toolCalls"][0]["name"] = "execute_sql"
        response.raw_output = json.dumps(response.output)
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertIn("FORBIDDEN_TOOL", {item.code for item in result.violations})

    def test_blocks_duplicate_keys(self) -> None:
        case, response = self.response("smoking-repeat-high")
        response.raw_output = response.raw_output.replace(
            '"riskLevel": "HIGH"', '"riskLevel": "LOW", "riskLevel": "HIGH"'
        )
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertIn("INVALID_JSON", {item.code for item in result.violations})

    def test_blocks_oversized_output(self) -> None:
        case, response = self.response("smoking-repeat-high")
        response.raw_output = "x" * (MAX_OUTPUT_CHARACTERS + 1)
        result = apply_policy_gateway(case, response, self.schema)
        self.assertFalse(result.accepted)
        self.assertIn("OUTPUT_TOO_LARGE", {item.code for item in result.violations})


if __name__ == "__main__":
    unittest.main()
