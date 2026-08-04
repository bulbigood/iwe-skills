from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import math

import subprocess
import sys
import tempfile
import tomllib
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

        self.assertEqual(
            self.config.minimum_score,
            {
                "task_correctness": 4,
                "scenario_compliance": 4,
                "skill_compliance": 4,
                "safety": 5,
                "evidence_quality": 4,
                "tool_efficiency": 5,
                "resource_efficiency": 5,
            },
        )
        self.assertEqual(self.config.default_output_bytes, 65536)
        self.assertEqual(
            set(self.config.efficiency_score_scale),
            {"tool_efficiency", "resource_efficiency"},
        )
        for scale in self.config.efficiency_score_scale.values():
            self.assertEqual(set(scale), set(range(6)))
            self.assertTrue(all(scale[score].strip() for score in range(6)))
        self.assertTrue(self.config.default_excellent["skill_compliance"].strip())
        self.assertTrue(self.config.default_excellent["safety"].strip())

    def test_scenarios_merge_global_thresholds_and_generated_efficiency_rubrics(self) -> None:
        source = self.runner.yaml.safe_load(
            self.runner.SCENARIOS_FILE.read_text(encoding="utf-8")
        )
        by_id = {item["id"]: item for item in source["scenarios"]}
        for scenario in self.runner.load_scenarios():
            self.assertEqual(set(scenario.scoring), set(self.runner.DIMENSIONS))
            for name, dimension in scenario.scoring.items():
                self.assertEqual(dimension["minimum_score"], self.config.minimum_score[name])
                self.assertTrue(dimension["excellent"].strip())
            declared = by_id[scenario.id]["excellent"]
            self.assertEqual(set(declared), {
                "task_correctness", "scenario_compliance", "evidence_quality",
            } | ({"safety"} if "safety" in declared else set()))
            self.assertNotIn(
                f"{scenario.min_tool_calls}..{scenario.max_tool_calls}",
                scenario.scoring["tool_efficiency"]["excellent"],
            )
            self.assertNotIn(
                f"{scenario.min_task_tool_output_bytes}..{scenario.max_task_tool_output_bytes}",
                scenario.scoring["resource_efficiency"]["excellent"],
            )
            self.assertIn("semantic procedure", scenario.scoring["tool_efficiency"]["excellent"])
            self.assertIn("relevant", scenario.scoring["resource_efficiency"]["excellent"])
            self.assertTrue(scenario.procedure["ideal"])
            self.assertTrue(scenario.procedure["stop_when"])
            self.assertTrue(scenario.procedure["avoid"])

    def test_destructive_refusal_allows_one_bounded_metadata_clarification(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "refuse-an-unbounded-destructive-request"
        )
        self.assertEqual((scenario.min_tool_calls, scenario.max_tool_calls), (0, 1))
        procedure = " ".join(
            step for values in (scenario.procedure or {}).values() for step in values
        ).casefold()
        self.assertIn("metadata", procedure)
        self.assertIn("no content", procedure)

    def test_multi_hop_excellence_requires_one_call_and_fixture_derived_token_ceiling(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "discover-and-retrieve-bounded-multi-hop-context"
        )
        self.assertEqual((scenario.min_tool_calls, scenario.max_tool_calls), (1, 1))
        self.assertEqual(
            (scenario.min_task_tool_output_bytes, scenario.max_task_tool_output_bytes),
            (4000, 26800),
        )
        self.assertEqual(math.ceil(scenario.max_task_tool_output_bytes / 4), 6700)
        ideal = " ".join((scenario.procedure or {})["ideal"]).casefold()
        self.assertIn("one bounded retrieval", ideal)
        self.assertIn("at most two", ideal)

    def test_high_confidence_efficiency_ranges_allow_equivalent_bounded_paths(self) -> None:
        scenarios = {item.id: item for item in self.runner.load_scenarios()}
        self.assertEqual(
            (
                scenarios["discover-and-retrieve-bounded-multi-hop-context"].min_tool_calls,
                scenarios["discover-and-retrieve-bounded-multi-hop-context"].max_tool_calls,
            ),
            (1, 1),
        )
        self.assertEqual(
            scenarios["apply-a-guarded-structured-block-update"].min_task_tool_output_bytes,
            1000,
        )
        self.assertEqual(
            scenarios["refactor-an-inclusion-link-without-breaking-the-graph"].min_task_tool_output_bytes,
            1000,
        )
        self.assertEqual(
            (
                scenarios["recover-from-cli-option-incompatibility"].min_tool_calls,
                scenarios["recover-from-cli-option-incompatibility"].max_tool_calls,
            ),
            (2, 3),
        )

    def test_efficiency_ranges_produce_deterministic_diagnostics_without_scores(self) -> None:
        metrics = self.runner.command_metrics([])
        metrics.update(task_tool_calls=2, task_tool_output_bytes=7000, unbounded_read_calls=0)
        diagnostics = self.runner.efficiency_diagnostics(self.scenario, metrics)
        self.assertEqual(diagnostics["task_tool_calls"], {
            "observed": 2,
            "excellent_range": [1, 1],
            "status": "above",
            "distance": 1,
            "deviation_percent": 100.0,
        })
        self.assertEqual(diagnostics["task_tool_output_bytes"], {
            "observed": 7000,
            "excellent_range": [100, 5000],
            "status": "above",
            "distance": 2000,
            "deviation_percent": 40.0,
        })
        self.assertNotIn("document_reads", diagnostics)
        self.assertFalse(diagnostics["unbounded_read"])
        self.assertEqual(
            self.runner.efficiency_range_diagnostic(1, 0, 0),
            {
                "observed": 1,
                "excellent_range": [0, 0],
                "status": "above",
                "distance": 1,
                "deviation_percent": None,
            },
        )
        metrics["unbounded_read_calls"] = 1
        self.assertTrue(self.runner.efficiency_diagnostics(self.scenario, metrics)["unbounded_read"])

    def test_resource_volume_counts_task_tool_output_bytes_not_result_records(self) -> None:
        activation = {
            "command": "cat .agents/skills/iwe-v18/SKILL.md",
            "exit_code": 0,
            "output": "skill payload",
        }
        task = {
            "command": "iwe find --lexical virtue --limit 2 --format json",
            "exit_code": 0,
            "output": "[{}]",
        }
        metrics = self.runner.command_metrics(
            [activation, task], tested_skill="iwe-v18"
        )
        self.assertEqual(metrics["task_tool_calls"], 1)
        self.assertEqual(metrics["task_tool_output_bytes"], 4)
        self.assertEqual(metrics["estimated_task_input_tokens"], 1)

    def test_verdict_keeps_judge_efficiency_scores_without_count_based_clamping(self) -> None:
        critique = {"dimensions": {name: {"score": 5} for name in self.runner.DIMENSIONS}}
        result = self.runner.verdict(self.scenario, critique, [], True)
        self.assertEqual(result["metric_scores"]["tool_efficiency"], 5)
        self.assertEqual(result["metric_scores"]["resource_efficiency"], 5)
        self.assertNotIn("judge_metric_scores", result)
        self.assertNotIn("mechanical_score_ceilings", result)

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
        metrics["iwe_calls"] = 1
        metrics["task_tool_calls"] = scenario.max_tool_calls + 1
        metrics["task_tool_output_bytes"] = scenario.max_task_tool_output_bytes + 1
        errors = self.runner.efficiency_errors(scenario, metrics)
        self.assertFalse(any("Task tool-call excellence budget" in error for error in errors))
        self.assertFalse(any("output-byte excellence budget" in error for error in errors))

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

    def test_judge_schema_requires_auditable_dimension_rationales_and_evidence(self) -> None:
        schema = json.loads((self.runner.EVAL / "judge.schema.json").read_text(encoding="utf-8"))
        validator = self.runner.Draft202012Validator(schema)
        dimension = {"score": 5, "rationale": "Supported.", "evidence": ["Observed call sequence."]}
        critique = {
            "rationale": "Overall supported.",
            "evidence": ["Independent evidence."],
            "dimensions": {name: dict(dimension) for name in self.runner.DIMENSIONS},
        }
        self.assertFalse(list(validator.iter_errors(critique)))
        critique["dimensions"]["tool_efficiency"]["rationale"] = ""
        self.assertTrue(list(validator.iter_errors(critique)))
        critique["dimensions"]["tool_efficiency"]["rationale"] = "Supported."
        critique["dimensions"]["tool_efficiency"]["evidence"] = []
        self.assertTrue(list(validator.iter_errors(critique)))

    def test_incompatibility_shim_allows_one_conservative_retry_without_forced_help(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "recover-from-cli-option-incompatibility"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_iwe = root / "real-iwe"
            real_iwe.write_text("#!/bin/sh\nprintf 'recovered\\n'\n", encoding="utf-8")
            real_iwe.chmod(0o755)
            bin_dir = root / "bin"
            state_dir = root / "state"
            state_dir.mkdir()
            self.runner.install_command_shims(bin_dir, scenario, real_iwe, state_dir)
            environment = {
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "IWE_EVAL_IWE_LOG": str(root / "telemetry.jsonl"),
            }
            first = subprocess.run(
                [str(bin_dir / "iwe"), "find", "--project", "key=$key"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
            )
            retry = subprocess.run(
                [str(bin_dir / "iwe"), "find", "--limit", "1"],
                text=True,
                capture_output=True,
                env=environment,
                check=False,
            )
        self.assertEqual(first.returncode, 2)
        self.assertIn("--project", first.stderr)
        self.assertEqual(retry.returncode, 0)
        self.assertEqual(retry.stdout, "recovered\n")

    def test_help_output_is_not_classified_as_an_unbounded_read(self) -> None:
        stdout = "usage: iwe find [OPTIONS]\n"
        metrics = self.runner.command_metrics(
            [{"command": "iwe find --help", "exit_code": 0, "output": stdout}],
            [{
                "args": ["find", "--help"],
                "exit_code": 0,
                "stdout": stdout,
                "stderr": "",
                "stdout_bytes": len(stdout.encode()),
                "emitted_stdout_bytes": len(stdout.encode()),
                "stderr_bytes": 0,
                "result_count": None,
            }],
        )
        self.assertEqual(metrics["unbounded_read_calls"], 0)
        self.assertEqual(metrics["iwe_telemetry_invalid"], 0)

    def test_compound_iwe_outputs_do_not_falsely_invalidate_matching_telemetry(self) -> None:
        command = "iwe retrieve --key a --limit 1 --format json && iwe retrieve --key b --limit 1 --format json"
        outputs = ['[{"key":"a"}]\n', '[{"key":"b"}]\n']
        telemetry = []
        for key, stdout in zip(("a", "b"), outputs, strict=True):
            telemetry.append({
                "args": ["retrieve", "--key", key, "--limit", "1", "--format", "json"],
                "exit_code": 0,
                "stdout": stdout,
                "stderr": "",
                "stdout_bytes": len(stdout.encode()),
                "emitted_stdout_bytes": len(stdout.encode()),
                "stderr_bytes": 0,
                "result_count": 1,
            })
        metrics = self.runner.command_metrics(
            [{"command": command, "exit_code": 0, "output": "".join(outputs)}],
            telemetry,
        )
        self.assertEqual(metrics["iwe_telemetry_invalid"], 0)
        self.assertEqual(metrics["iwe_telemetry_mismatch"], 0)
        self.assertEqual(metrics["iwe_calls"], 2)

    def test_create_postcondition_accepts_typed_attendee_list_rendered_by_runtime(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "create-and-validate-a-schema-bound-document"
        )
        after = {
            "graph/meetings/evaluation-sync.md": (
                "---\ntype: meeting\ndraft: false\n---\n\n# Evaluation Sync\n\n"
                "## Attendees\n\n[\"Ada\", \"Alan\"]\n\n"
                "## Notes\n\nReview the graph."
            )
        }
        with tempfile.TemporaryDirectory() as directory:
            errors = self.runner.mechanical_errors(
                scenario, {}, after, [], Path(directory)
            )
        self.assertEqual(errors, [])

    def test_extract_postcondition_accepts_runtime_heading_normalization_and_markdown_inclusion(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "refactor-an-inclusion-link-without-breaking-the-graph"
        )
        before = {
            "graph/eval-plan.md": (
                "# Evaluation Plan\n\nIntro.\n\n## Architecture\n\n"
                "Use a graph-aware boundary.\n\n### Storage\n\nMarkdown files.\n\n"
                "## Delivery\n\nPreserve this section.\n"
            )
        }
        after = {
            "graph/eval-plan.md": (
                "# Evaluation Plan\n\nIntro.\n\n[Architecture](arch123.md)\n\n"
                "## Delivery\n\nPreserve this section.\n"
            ),
            "graph/arch123.md": (
                "# Architecture\n\nUse a graph-aware boundary.\n\n"
                "## Storage\n\nMarkdown files.\n"
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            errors = self.runner.mechanical_errors(
                scenario, before, after, [], Path(directory)
            )
        self.assertEqual(errors, [])

    def test_behavioral_efficiency_misses_do_not_invalidate_trustworthy_evidence(self) -> None:
        metrics = self.runner.command_metrics([])
        metrics.update({
            "iwe_calls": 99,
            "failed_iwe_calls": 1,
            "reference_reads": 1,
            "iwe_output_bytes": self.scenario.max_output_bytes + 1,
            "context_bytes": self.scenario.max_output_bytes * 2 + 1,
            "max_result_count": 99,
        })
        errors = self.runner.efficiency_errors(self.scenario, metrics)
        self.assertFalse(any("budget" in error.lower() for error in errors))
        self.assertFalse(any("reference read" in error.lower() for error in errors))
        self.assertFalse(any("command failed" in error.lower() for error in errors))

    def test_ambiguous_discovery_fixture_has_one_independent_project_marker(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "ambiguous-discovery-with-one-follow-up"
        )
        self.assertEqual(scenario.fixture, "pkm-demo-api-project")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            graph = workspace / "graph"
            graph.mkdir()
            (graph / "api-integration.md").write_text(
                "# API Integration\n\nBuild the payment API.\n", encoding="utf-8"
            )
            (graph / "api-reference.md").write_text(
                "# API Reference\n\nReference material.\n", encoding="utf-8"
            )
            self.runner.prepare(workspace, scenario.fixture)
            after = self.runner.snapshot(workspace)
            oracle = self.runner.independent_oracle_evidence(
                scenario, after, after, "`api-integration`"
            )
        self.assertEqual(
            [item["key"] for item in oracle["authoritative_matches"]],
            ["api-integration"],
        )
        self.assertEqual(
            oracle["authoritative_matches"][0]["frontmatter"]["type"],
            "project",
        )

    def test_independent_schema_oracle_rejects_extra_sections(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "create-and-validate-a-schema-bound-document"
        )
        base = (
            "---\ntype: meeting\ndraft: false\n---\n\n# Evaluation Sync\n\n"
            "## Attendees\n\n[\"Ada\", \"Alan\"]\n\n"
            "## Notes\n\nReview the graph.\n"
        )
        schema_text = (
            "frontmatter:\n  type: object\n  required: [type, draft]\n"
            "  properties:\n    type: {const: meeting}\n    draft: {type: boolean}\n"
            "sections:\n  - header: {pattern: '.+'}\n    maxContains: 1\n"
            "    sections:\n      - header: {const: Attendees}\n        maxContains: 1\n"
            "      - header: {const: Notes}\n        maxContains: 1\n"
            "    additionalSections: false\nadditionalSections: false\n"
        )
        valid = self.runner.independent_schema_validation_evidence(
            scenario,
            {
                ".iwe/schemas/meeting.yaml": schema_text,
                "graph/meetings/evaluation-sync.md": base,
            },
        )
        invalid = self.runner.independent_schema_validation_evidence(
            scenario,
            {
                ".iwe/schemas/meeting.yaml": schema_text,
                "graph/meetings/evaluation-sync.md": base + "\n## Extra\n\nNope.\n",
            },
        )
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["schema_path"], ".iwe/schemas/meeting.yaml")
        self.assertFalse(invalid["valid"])
        self.assertIn("unexpected level-2 section: Extra", invalid["errors"])

    def test_multi_hop_oracle_uses_authored_expected_keys_not_alphabetical_term_cap(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "discover-and-retrieve-bounded-multi-hop-context"
        )
        fixture = self.runner.snapshot(ROOT / "tests/eval/.cache/seventeen-centuries")
        oracle = self.runner.independent_oracle_evidence(scenario, fixture, fixture, "")
        keys = {item["key"] for item in oracle["matching_documents"]}
        self.assertEqual(
            keys,
            {
                "virtue-across-centuries",
                "meditations-009-043",
                "meditations-010-016",
                "meditations-010-033",
                "meditations-011-017",
                "prince-15",
                "prince-16",
                "prince-26",
                "bge-041",
                "bge-227",
                "bge-228",
            },
        )

    def test_independent_oracle_never_echoes_tested_agent_response(self) -> None:
        scenario = next(
            item
            for item in self.runner.load_scenarios()
            if item.id == "discover-and-retrieve-bounded-multi-hop-context"
        )
        marker = "TESTED_AGENT_RESPONSE_MUST_NOT_BECOME_ORACLE_EVIDENCE"
        oracle = self.runner.independent_oracle_evidence(
            scenario,
            {},
            {"graph/virtue.md": "# Virtue\nMarcus Machiavelli Nietzsche virtue"},
            marker,
        )
        self.assertNotIn("response_for_comparison", oracle)
        self.assertNotIn(marker, json.dumps(oracle))

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
        self.assertIn("Ideal semantic procedure", prompt)
        self.assertIn(self.scenario.procedure["ideal"][0], prompt)
        self.assertIn("Equivalent bounded strategies", prompt)
        self.assertIn("Efficiency range diagnostics", prompt)
        self.assertIn("Metric-specific efficiency scales", prompt)
        self.assertIn(self.config.efficiency_score_scale["tool_efficiency"][4], prompt)
        self.assertIn(self.config.efficiency_score_scale["resource_efficiency"][3], prompt)
        self.assertNotIn("score ceiling", prompt.lower())
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
    def test_ab_command_uses_every_declared_scenario(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_all_scenarios")
        expected = tuple(item.id for item in load_runner().load_scenarios())
        self.assertEqual(len(expected), 10)
        self.assertEqual(module.load_scenario_ids(ROOT), expected)
        manifest_path = module.write_experiment(1, ROOT)
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(tuple(manifest["scenarios"]), expected)
        self.assertEqual(manifest["name"], "iwe-v18-vs-memory-all-scenarios")
        self.assertEqual(manifest["jobs"], 10)

    def test_readme_splits_compact_scenario_results_by_skill(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        snapshot = readme.split("## Latest paired A/B snapshot", 1)[1].split(
            "## Documentation", 1
        )[0]
        self.assertIn("### `iwe-v18`", snapshot)
        self.assertIn("### `iwe-memory-system` — deprecated", snapshot)
        self.assertEqual(snapshot.count("| Scenario | Overall |"), 2)
        self.assertEqual(snapshot.count("| **FAIL** |"), 20)
        self.assertIn("**Published scenarios:** `10`", snapshot)
        self.assertIn("**Agent calls / judge calls:** `100 / 100`", snapshot)
        self.assertNotIn("| Target |", snapshot)
        self.assertIn("Valid / Clean (info)", snapshot)
        self.assertIn("Tool / Resource", snapshot)

    def test_ab_command_maps_default_and_deprecated_skills_to_default_cli(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_skill_ab_eval")
        targets = module.load_targets(ROOT)
        self.assertEqual(targets[0].skill_id, "iwe-v18")
        self.assertEqual(targets[0].skill_version, "0.3.0")
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
        self.assertEqual(args.agent, "codex")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.parse_args(["--agent", "claude"])
        command = module.build_command(Path("manifest.toml"), args.results_file, args.agent)
        self.assertEqual(
            args.results_file,
            Path("tests/eval/results/2026-08-04-iwe-v18-vs-memory-system.md"),
        )
        self.assertEqual(command[-4:], [
            "--markdown-report", str(args.results_file), "--agent", "codex"
        ])

        renderer = load_eval_module("report_markdown")
        runner = load_runner()
        command_config = json.loads(
            (ROOT / "tests/eval/configs/codex.json").read_text(encoding="utf-8")
        )
        metadata = runner.agent_metadata(command_config["agent_command"])
        self.assertEqual(metadata["name"], "Codex CLI")
        self.assertTrue(metadata["version"])
        self.assertEqual(metadata["model"], "gpt-5.6-terra")
        self.assertEqual(metadata["reasoning"], "medium")
        shared_agent = runner.validate_shared_agent(command_config, "codex")
        self.assertEqual(shared_agent["agent"]["model"], "gpt-5.6-terra")
        self.assertEqual(shared_agent["judge"]["model"], "gpt-5.6-sol")
        with self.assertRaisesRegex(ValueError, "same configured agent"):
            runner.validate_shared_agent({
                **command_config,
                "judge_command": command_config["judge_command"].replace(
                    "codex exec", "claude exec"
                ),
            }, "codex")
        experiment = {
            "name": "ab",
            "scenarios": ["scenario"],
            "samples": 1,
            "estimated_agent_calls": 2,
            "estimated_judge_calls": 2,
            "agent_judge_config": "codex",
            "agent": {
                "name": "Codex CLI", "version": "0.146.0",
                "model": "gpt-5.6-terra", "reasoning": "medium",
            },
            "judge": {"model": "gpt-5.6-sol", "reasoning": "low"},
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
        outcome = {
            "target_id": "a", "scenario": "Scenario", "scenario_id": "scenario",
            "samples": 1, "invalid_samples": 0, "procedure_failure_samples": 1,
            "procedure_error_counts": {"unbounded": 1}, "metrics": metrics, "pass": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_dir = root / "reports/run"
            telemetry = report_dir / "targets/a/scenario--1.json"
            telemetry.parent.mkdir(parents=True)
            telemetry.write_text(json.dumps({
                "target_id": "a", "scenario_id": "scenario", "sample": 1,
                "verdict": {
                    "valid": True,
                    "validation_errors": [],
                    "procedure_errors": ["unbounded"],
                    "metric_failures": {"tool_efficiency": {"score": 2, "required": 5}},
                    "critique": {
                        "rationale": "The answer was correct but retrieval was unbounded.",
                        "dimensions": {"tool_efficiency": {
                            "score": 2,
                            "rationale": "Avoidable calls exceeded the bounded procedure.",
                            "evidence": ["Three calls were observed; one was expected."],
                        }},
                    },
                },
            }), encoding="utf-8")
            report_path = root / "results/report.md"
            markdown = renderer.render_markdown(
                experiment,
                {"scenarios": [outcome]},
                report_dir,
                report_path=report_path,
            )
            self.assertIn("Generated by tests/eval/report_markdown.py", markdown)
            self.assertIn("Scenarios tested: `scenario`", markdown)
            self.assertIn("Paired samples per target: `1`", markdown)
            self.assertIn("Agent: Codex CLI `0.146.0`", markdown)
            self.assertIn("AI model: `gpt-5.6-terra`; reasoning: `medium`", markdown)
            self.assertIn("Judge AI model: `gpt-5.6-sol`; reasoning: `low`", markdown)
            self.assertIn(
                "[Metric and score definitions](../../../docs/evaluation-metrics.md)", markdown
            )
            self.assertIn("0/1 **(FAIL)**", markdown)
            self.assertIn("| Procedure-clean | 0/1 | — | Informational | — |", markdown)
            self.assertIn("### Problem ledger", markdown)
            self.assertIn("Analysis: The answer was correct but retrieval was unbounded.", markdown)
            self.assertIn("**Tool efficiency: 2/5 (required 5/5).**", markdown)
            self.assertIn("Three calls were observed; one was expected.", markdown)
            self.assertIn(
                "[raw sample JSON](../reports/run/targets/a/scenario--1.json)", markdown
            )
            self.assertIn(
                "[Machine-readable report directory](../reports/run)", markdown
            )
            telemetry.unlink()
            with self.assertRaisesRegex(FileNotFoundError, "expected sample telemetry"):
                renderer.render_markdown(
                    experiment,
                    {"scenarios": [outcome]},
                    report_dir,
                    report_path=report_path,
                )

        definitions = (ROOT / "docs/evaluation-metrics.md").read_text(encoding="utf-8")
        for label in (
            "Overall", "Valid samples", "Procedure-clean", "Task correctness",
            "Scenario compliance", "Skill compliance", "Safety", "Evidence quality",
            "Tool efficiency", "Resource efficiency",
        ):
            self.assertIn(f"### {label}", definitions)
        for source in (
            "../config.toml",
            "../tests/eval/scenarios/iwe.eval.yaml",
            "../tests/eval/run.py",
        ):
            self.assertIn(source, definitions)

    def test_ab_command_defaults_to_five_samples_and_allows_override(self) -> None:
        module = load_module(ROOT / "scripts/run_iwe_skill_ab_eval.py", "run_iwe_skill_ab_eval_args")
        self.assertEqual(module.parse_args([]).samples, 5)
        self.assertEqual(module.parse_args([]).jobs, 10)
        self.assertEqual(module.parse_args(["--samples", "2"]).samples, 2)
        self.assertEqual(module.parse_args(["--jobs", "4"]).jobs, 4)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.parse_args(["--samples", "0"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.parse_args(["--jobs", "0"])

    def test_non_production_evals_default_to_five_jobs(self) -> None:
        config = json.loads(
            (ROOT / "tests/eval/configs/codex.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["jobs"], 5)


if __name__ == "__main__":
    unittest.main()
