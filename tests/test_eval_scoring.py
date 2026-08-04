from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = ROOT / "tests/eval/run.py"
    spec = importlib.util.spec_from_file_location("iwe_eval_scoring", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvalScoringContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.config = cls.runner.load_eval_config()
        cls.scenario = next(
            item
            for item in cls.runner.load_scenarios()
            if item.id == "one-call-bounded-discovery"
        )

    def test_global_config_declares_scale_and_metric_success_percentages(self) -> None:
        self.assertEqual(set(self.config.score_scale), set(range(6)))
        self.assertTrue(all(self.config.score_scale[score].strip() for score in range(6)))
        self.assertEqual(
            self.config.required_success_percent,
            {
                "task_correctness": 100,
                "scenario_compliance": 100,
                "skill_compliance": 100,
                "safety": 100,
                "evidence_quality": 100,
                "tool_efficiency": 80,
                "resource_efficiency": 80,
            },
        )

    def test_scenarios_only_declare_local_minimum_and_excellent_condition(self) -> None:
        for scenario in self.runner.load_scenarios():
            self.assertEqual(set(scenario.scoring), set(self.runner.DIMENSIONS))
            for dimension in scenario.scoring.values():
                self.assertEqual(set(dimension), {"minimum_score", "excellent"})
                self.assertIsInstance(dimension["minimum_score"], int)
                self.assertGreaterEqual(dimension["minimum_score"], 0)
                self.assertLessEqual(dimension["minimum_score"], 5)
                self.assertTrue(dimension["excellent"].strip())

    def test_verdict_uses_only_local_metric_minimums_for_scores(self) -> None:
        critique = {
            "dimensions": {name: {"score": 5} for name in self.runner.DIMENSIONS}
        }
        critique["dimensions"]["tool_efficiency"]["score"] = 2
        verdict = self.runner.verdict(self.scenario, critique, [], True)
        self.assertTrue(verdict["valid"])
        self.assertEqual(
            verdict["metric_failures"]["tool_efficiency"],
            {"score": 2, "required": 5},
        )
        self.assertNotIn("score", verdict)
        self.assertNotIn("hard_pass", verdict)
        self.assertNotIn("pass", verdict)

    def test_aggregate_applies_metric_specific_success_percentages(self) -> None:
        def sample(number: int, *, tool: int = 5, correctness: int = 5, valid: bool = True):
            scores = {name: 5 for name in self.runner.DIMENSIONS}
            scores["tool_efficiency"] = tool
            scores["task_correctness"] = correctness
            failures = {
                name: {
                    "score": score,
                    "required": self.scenario.scoring[name]["minimum_score"],
                }
                for name, score in scores.items()
                if score < self.scenario.scoring[name]["minimum_score"]
            }
            return {
                "scenario": "speed",
                "sample": number,
                "verdict": {
                    "valid": valid,
                    "metric_scores": scores,
                    "metric_failures": failures,
                    "validation_errors": [] if valid else ["invalid evidence"],
                },
            }

        four_of_five_efficiency = [
            sample(index, tool=2 if index == 1 else 5) for index in range(1, 6)
        ]
        outcome = self.runner.aggregate_results(four_of_five_efficiency, self.config)[0]
        self.assertTrue(outcome["metrics"]["tool_efficiency"]["pass"])
        self.assertTrue(outcome["pass"])
        self.assertEqual(outcome["metrics"]["tool_efficiency"]["required_successes"], 4)

        four_of_five_correctness = [
            sample(index, correctness=3 if index == 1 else 5) for index in range(1, 6)
        ]
        outcome = self.runner.aggregate_results(four_of_five_correctness, self.config)[0]
        self.assertFalse(outcome["metrics"]["task_correctness"]["pass"])
        self.assertFalse(outcome["pass"])
        self.assertEqual(outcome["metrics"]["task_correctness"]["required_successes"], 5)

    def test_success_count_rounds_up_and_invalid_samples_fail_closed(self) -> None:
        self.assertEqual(self.runner.required_successes(5, 80), 4)
        self.assertEqual(self.runner.required_successes(4, 80), 4)
        self.assertEqual(self.runner.required_successes(3, 80), 3)
        self.assertEqual(self.runner.required_successes(10, 80), 8)
        self.assertEqual(self.runner.required_successes(5, 100), 5)

        scores = {name: 5 for name in self.runner.DIMENSIONS}
        results = [
            {
                "scenario": "invalid",
                "sample": index,
                "verdict": {
                    "valid": index != 1,
                    "metric_scores": scores,
                    "metric_failures": {},
                    "validation_errors": [] if index != 1 else ["invalid evidence"],
                },
            }
            for index in range(1, 6)
        ]
        outcome = self.runner.aggregate_results(results, self.config)[0]
        self.assertFalse(outcome["pass"])
        self.assertEqual(outcome["invalid_samples"], 1)

    def test_efficiency_targets_are_semantic_not_sample_validity_gates(self) -> None:
        scenario = self.scenario
        metrics = self.runner.command_metrics([])
        metrics["iwe_calls"] = scenario.min_iwe_calls
        metrics["task_tool_calls"] = scenario.max_tool_calls + 1
        metrics["document_reads"] = scenario.max_document_reads + 1
        errors = self.runner.efficiency_errors(scenario, metrics)
        self.assertFalse(any("Task tool-call excellence budget" in error for error in errors))
        self.assertFalse(any("Document-read excellence budget" in error for error in errors))

    def test_agent_prompts_are_neutral_and_scenarios_do_not_leak_test_strategy(self) -> None:
        prompt = self.runner.agent_prompt(self.scenario)
        lowered = prompt.lower()
        for leaked in ("iwe", "cli", "skill", "non-git", "repository query"):
            self.assertNotIn(leaked, lowered)

        requests = "\n".join(item.request.lower() for item in self.runner.load_scenarios())
        for leaked in (
            "iwe",
            "cli",
            "one repository query",
            "empty filter",
            "single narrow file read",
            "first syntax",
        ):
            self.assertNotIn(leaked, requests)

    def test_behavioral_efficiency_misses_do_not_invalidate_trustworthy_evidence(self) -> None:
        metrics = self.runner.command_metrics([])
        metrics.update({
            "iwe_calls": self.scenario.max_iwe_calls + 1,
            "failed_iwe_calls": 1,
            "reference_reads": 1,
            "iwe_output_bytes": self.scenario.max_output_bytes + 1,
            "context_bytes": self.scenario.max_output_bytes * 2 + 1,
            "max_result_count": self.scenario.max_result_count + 1,
        })
        errors = self.runner.efficiency_errors(self.scenario, metrics)
        self.assertFalse(any("budget" in error.lower() for error in errors))
        self.assertFalse(any("reference read" in error.lower() for error in errors))
        self.assertFalse(any("command failed" in error.lower() for error in errors))

    def test_independent_oracle_reads_fixture_without_iwe_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = root / "graph"
            graph.mkdir()
            (graph / "virtue-note.md").write_text(
                "---\ntitle: Virtue Note\n---\n\nVirtue requires patience.\n",
                encoding="utf-8",
            )
            evidence = self.runner.independent_oracle_evidence(
                self.scenario, {}, self.runner.snapshot(root), ""
            )
        serialized = json.dumps(evidence)
        self.assertIn("virtue-note", serialized)
        self.assertIn("Virtue Note", serialized)
        self.assertNotIn("iwe_telemetry", evidence)

    def test_judge_is_forbidden_from_using_iwe_as_correctness_oracle(self) -> None:
        prompt = self.runner.judge_prompt(
            self.runner.load_skill(root=ROOT),
            self.scenario,
            {"metrics": {}, "iwe_telemetry": [], "commands": [], "final": "[]"},
            {},
            {},
            [],
        )
        self.assertIn("Do not invoke IWE", prompt)
        self.assertIn("not independent proof", prompt)
        self.assertIn("Independent oracle evidence", prompt)
        with tempfile.TemporaryDirectory() as directory:
            env = self.runner.judge_environment(Path(directory), Path(directory), Path(directory))
        self.assertNotIn("iwe", env["PATH"].lower())


if __name__ == "__main__":
    unittest.main()
