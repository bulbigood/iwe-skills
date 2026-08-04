from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_eval_module(name: str):
    path = ROOT / f"tests/eval/{name}.py"
    return load_module(path, f"iwe_eval_{name}")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    def test_tool_procedure_errors_do_not_invalidate_content_metrics(self) -> None:
        critique = {
            "dimensions": {name: {"score": 5} for name in self.runner.DIMENSIONS}
        }
        for name in ("skill_compliance", "tool_efficiency", "resource_efficiency"):
            critique["dimensions"][name]["score"] = 2
        procedure = [
            "unbounded IWE discovery or retrieval used",
            "IWE telemetry measurements do not match observed command evidence",
            "possible deprecated positional iwe find query",
        ]
        sample_verdict = self.runner.verdict(
            self.scenario, critique, [], True, procedure_errors=procedure
        )
        self.assertTrue(sample_verdict["valid"])
        self.assertEqual(sample_verdict["validation_errors"], [])
        self.assertEqual(sample_verdict["procedure_errors"], procedure)

        outcome = self.runner.aggregate_results([{
            "scenario": self.scenario.name,
            "sample": 1,
            "verdict": sample_verdict,
        }], self.config)[0]
        for name in ("task_correctness", "scenario_compliance", "safety", "evidence_quality"):
            self.assertEqual(outcome["metrics"][name]["successful_samples"], 1)
        for name in ("skill_compliance", "tool_efficiency", "resource_efficiency"):
            self.assertEqual(outcome["metrics"][name]["successful_samples"], 0)
        self.assertEqual(outcome["invalid_samples"], 0)
        self.assertTrue(outcome["result_pass"])
        self.assertFalse(outcome["procedure_pass"])
        self.assertFalse(outcome["pass"])
        self.assertEqual(outcome["procedure_failure_samples"], 1)
        self.assertEqual(
            outcome["procedure_error_counts"]["unbounded IWE discovery or retrieval used"], 1
        )

    def test_procedure_errors_are_reported_but_not_mechanical_validity_errors(self) -> None:
        commands = [{
            "command": "iwe find virtue --format json",
            "exit_code": 0,
            "output": "[]",
        }]
        metrics = self.runner.command_metrics(commands)
        procedure = self.runner.procedure_errors(self.scenario, commands, metrics)
        self.assertIn("unbounded IWE discovery or retrieval used", procedure)
        self.assertIn("possible deprecated positional iwe find query", procedure)
        with tempfile.TemporaryDirectory() as directory:
            integrity = self.runner.mechanical_errors(
                self.scenario, {}, {}, commands, Path(directory), metrics
            )
        self.assertEqual(integrity, [])

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


class ExperimentManifestTests(unittest.TestCase):
    def test_loads_two_target_manifest_with_target_local_runtimes(self) -> None:
        experiment_module = load_eval_module("experiment")
        experiment = experiment_module.load_experiment(
            ROOT / "tests/eval/experiments/example.toml", ROOT
        )
        self.assertEqual(len(experiment.targets), 2)
        self.assertEqual(experiment.samples, 2)
        self.assertEqual(experiment.targets[0].runtime.version, "0.18.0")
        self.assertEqual(experiment.targets[1].runtime.version, "0.18.1")
        self.assertEqual(experiment.targets[0].skill_path, experiment.targets[1].skill_path)
        self.assertNotEqual(experiment.targets[0].id, experiment.targets[1].id)

    def test_matrix_is_complete_paired_and_deterministic(self) -> None:
        runner = load_runner()
        experiment = load_eval_module("experiment").load_experiment(
            ROOT / "tests/eval/experiments/example.toml", ROOT
        )
        scenarios = [s for s in runner.load_scenarios() if s.id in experiment.scenario_ids]
        cells = runner.build_matrix(experiment, scenarios)
        self.assertEqual(len(cells), 8)
        self.assertEqual(len({(c.target_id, c.scenario_id, c.sample_index) for c in cells}), 8)
        self.assertEqual(len({c.pair_id for c in cells}), 4)
        for pair_id in {c.pair_id for c in cells}:
            self.assertEqual(sum(c.pair_id == pair_id for c in cells), 2)

    def test_pairwise_comparison_is_threshold_based_and_keeps_invalid_cells(self) -> None:
        compare = load_eval_module("compare")
        def result(target, sample, score, valid=True):
            scores = {name: 5 for name in load_runner().DIMENSIONS}
            scores["tool_efficiency"] = score
            return {"target_id": target, "scenario_id": "s", "sample": sample,
                    "pair_id": f"pair-{sample}",
                    "verdict": {"valid": valid, "metric_scores": scores,
                                "metric_failures": {} if score >= 4 else {"tool_efficiency": {}},
                                "validation_errors": [] if valid else ["bad"]},
                    "agent": {"metrics": {"tool_calls": sample}}}
        comparison = compare.compare_results([
            result("a", 1, 5), result("b", 1, 3),
            result("a", 2, 3, False), result("b", 2, 5),
        ], ("a", "b"), ("tool_efficiency",))[0]
        metric = comparison["metrics"]["tool_efficiency"]
        self.assertEqual((metric["left_wins"], metric["ties"], metric["left_losses"]), (1, 0, 1))
        self.assertEqual(comparison["invalid_cells"], {"a": 1, "b": 0})
        self.assertNotIn("mean", json.dumps(comparison).lower())
        self.assertNotIn("weighted", json.dumps(comparison).lower())

    def test_experiment_list_mode_shows_pairs_without_resolving_binaries(self) -> None:
        completed = subprocess.run([
            str(ROOT / ".venv/bin/python"), str(ROOT / "tests/eval/run.py"),
            "--experiment", "tests/eval/experiments/example.toml", "--list",
        ], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("v18-on-0180", completed.stdout)
        self.assertIn("IWE 0.18.1", completed.stdout)
        self.assertIn("one-call-bounded-discovery", completed.stdout)

    def test_target_aggregation_is_independent_complete_and_histogrammed(self) -> None:
        runner = load_runner()
        scores = {name: 5 for name in runner.DIMENSIONS}
        rows = []
        for target in ("a", "b"):
            for sample in (1, 2):
                target_scores = dict(scores)
                if target == "b":
                    target_scores["task_correctness"] = 0
                rows.append({"target_id": target, "scenario": "S", "scenario_id": "s",
                             "sample": sample, "verdict": {"valid": True,
                             "metric_scores": target_scores,
                             "metric_failures": {} if target == "a" else {"task_correctness": {}},
                             "validation_errors": []}})
        outcomes = runner.aggregate_results(rows, runner.load_eval_config(), expected_samples=2)
        self.assertTrue(next(o for o in outcomes if o["target_id"] == "a")["pass"])
        failed = next(o for o in outcomes if o["target_id"] == "b")
        self.assertFalse(failed["pass"])
        self.assertEqual(failed["metrics"]["task_correctness"]["score_histogram"]["0"], 2)

    def test_experiment_rejects_skill_name_mismatch_in_strict_frontmatter(self) -> None:
        experiment_module = load_eval_module("experiment")
        source = (ROOT / "tests/eval/experiments/example.toml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            (root / "skill").mkdir()
            (root / "skill/SKILL.md").write_text(
                "---\nname: wrong-name\nmetadata:\n  version: 0.2.0\n---\nbody\n",
                encoding="utf-8",
            )
            (root / "contract.json").write_text(
                json.dumps({"schema_version": 1, "cli_line": "0.18", "commands": {"find": {}}}),
                encoding="utf-8",
            )
            manifest = source.replace("skills/iwe-v18", str((root / "skill").relative_to(ROOT))).replace(
                "contracts/iwe-v18.json", str((root / "contract.json").relative_to(ROOT))
            )
            path = root / "experiment.toml"
            path.write_text(manifest, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "skill name"):
                experiment_module.load_experiment(path, ROOT)

    def test_comparison_rejects_conflicting_pair_ids_and_missing_expected_cells(self) -> None:
        compare = load_eval_module("compare")
        rows = [
            {"target_id": target, "scenario_id": "s", "sample": 1, "pair_id": pair_id,
             "verdict": {"valid": True, "metric_scores": {"safety": 5}, "metric_failures": {}},
             "agent": {"metrics": {}}}
            for target, pair_id in (("a", "pair-a"), ("b", "pair-b"))
        ]
        with self.assertRaisesRegex(ValueError, "pair_id"):
            compare.compare_results(rows, ("a", "b"), ("safety",), {("s", 1): "expected"})
        with self.assertRaisesRegex(ValueError, "missing expected"):
            compare.compare_results([], ("a", "b"), ("safety",), {("s", 1): "expected"})

    def test_single_skill_list_output_remains_legacy_compatible(self) -> None:
        completed = subprocess.run([
            str(ROOT / ".venv/bin/python"), str(ROOT / "tests/eval/run.py"), "--list",
        ], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        first = completed.stdout.splitlines()[0]
        self.assertFalse(first.startswith("discover-and-retrieve-"), first)
        self.assertRegex(first, r"^.+ \[[^]]+\]$")


class ProductionEvalCommandTests(unittest.TestCase):
    def test_production_command_runs_all_default_skill_scenarios_with_five_samples(self) -> None:
        module = load_module(ROOT / "scripts/run_production_eval.py", "run_production_eval")
        self.assertEqual(
            module.build_command(5),
            [sys.executable, str(ROOT / "tests/eval/run.py"), "--config", "codex", "--samples", "5"],
        )

    def test_production_command_allows_positive_sample_override(self) -> None:
        module = load_module(ROOT / "scripts/run_production_eval.py", "run_production_eval_override")
        self.assertEqual(module.parse_args(["--samples", "3"]).samples, 3)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.parse_args(["--samples", "0"])


class PairedSkillEvalCommandTests(unittest.TestCase):
    def test_ab_command_maps_default_and_deprecated_skills_to_default_cli(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_skill_ab_eval")
        targets = module.load_targets(ROOT)
        self.assertEqual(targets[0].skill_id, "iwe-v18")
        self.assertEqual(targets[0].skill_version, "0.2.0")
        self.assertEqual(targets[0].iwe_version, "0.18.0")
        self.assertEqual(targets[0].runtime_skill_id, "iwe-v18")
        self.assertEqual(targets[1].skill_id, "iwe-memory-system")
        self.assertEqual(targets[1].skill_version, "0.0.67")
        self.assertEqual(targets[1].iwe_version, targets[0].iwe_version)
        self.assertEqual(targets[1].contract_file, targets[0].contract_file)
        self.assertEqual(targets[1].runtime_skill_id, "iwe-v18")

    def test_ab_command_generates_the_linked_markdown_results(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_skill_ab_eval_report")
        args = module.parse_args([])
        command = module.build_command(Path("manifest.toml"), args.results_file)
        self.assertEqual(
            args.results_file,
            Path("tests/eval/results/2026-08-04-iwe-v18-vs-memory-system.md"),
        )
        self.assertEqual(command[-2:], ["--markdown-report", str(args.results_file)])

        renderer = load_eval_module("report_markdown")
        experiment = {
            "name": "ab",
            "scenarios": ["scenario"],
            "samples": 1,
            "estimated_agent_calls": 2,
            "estimated_judge_calls": 2,
            "agent_judge_config": "codex",
            "targets": [{
                "id": "a", "skill_version": "1.0.0", "runtime": {"version": "0.18.0"}
            }],
        }
        metrics = {
            name: {
                "successful_samples": 0 if name == "tool_efficiency" else 1,
                "total_samples": 1,
                "required_successes": 1,
                "pass": name != "tool_efficiency",
                "score_histogram": {"0": 1} if name == "tool_efficiency" else {"5": 1},
            }
            for name in load_runner().DIMENSIONS
        }
        markdown = renderer.render_markdown(experiment, {"scenarios": [{
            "target_id": "a", "scenario": "Scenario", "samples": 1,
            "invalid_samples": 0, "procedure_failure_samples": 1,
            "procedure_error_counts": {"unbounded": 1}, "metrics": metrics, "pass": False,
        }]}, Path("reports/run"))
        self.assertIn("Generated by tests/eval/report_markdown.py", markdown)
        self.assertIn("Scenarios tested: `scenario`", markdown)
        self.assertIn("Paired samples per target: `1`", markdown)
        self.assertIn("0/1 **(FAIL)**", markdown)
        self.assertIn("Machine-readable reports: `reports/run`", markdown)

    def test_ab_command_defaults_to_five_samples_and_allows_override(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_skill_ab_eval_args")
        self.assertEqual(module.parse_args([]).samples, 5)
        self.assertEqual(module.parse_args(["--samples", "2"]).samples, 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.parse_args(["--samples", "0"])


if __name__ == "__main__":
    unittest.main()
