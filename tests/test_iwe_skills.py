from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_manifest
from skill_manifest import load_skill, load_skills


IWE = skill_manifest.verify_runtime_binary(load_skill(root=ROOT))


class IweSkillTests(unittest.TestCase):
    def test_manifest_and_frozen_contract_are_consistent(self) -> None:
        default, skills = load_skills(ROOT)
        self.assertIn(default, skills)
        for name, spec in skills.items():
            self.assertEqual(name, spec.path.name)
            self.assertEqual(spec.runtime_cli, "iwe")
            self.assertEqual(spec.runtime_source, "homebrew")
            self.assertEqual(spec.supported, ">=0.18.0")
            self.assertEqual(spec.tested_version, "0.18.0")
            self.assertLessEqual(spec.normal_tool_calls, 1)
            self.assertLessEqual(spec.maximum_search_results, 20)
            self.assertFalse(spec.network_allowed)
            self.assertEqual(set(spec.forbidden_fallbacks), {"grep", "rg", "find"})
            contract = json.loads(spec.contract_file.read_text(encoding="utf-8"))
            self.assertEqual(contract["schema_version"], 1)
            self.assertEqual(contract["cli_line"], "0.18")
            self.assertEqual(contract["default_limit"], spec.maximum_search_results)
            self.assertEqual(contract["output_format"], "json")
            self.assertEqual(
                set(contract["commands"]),
                {
                    "init", "create", "new", "retrieve", "find", "count",
                    "normalize", "tree", "squash", "export", "schema",
                    "schema.validate", "stats", "stats.similarity", "rename",
                    "delete", "extract", "inline", "update", "attach",
                    "completions", "docs",
                },
            )
            self.assertTrue(contract["commands"]["docs"]["control_plane_only"])
            self.assertEqual(contract["global_flags"], ["--verbose", "--help", "--version"])

    def test_runtime_binary_sources_and_configured_version(self) -> None:
        base = load_skill(root=ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def executable(parent: Path, version: str = "0.18.0") -> Path:
                parent.mkdir(parents=True, exist_ok=True)
                binary = parent / "iwe"
                binary.write_text(f"#!/bin/sh\nprintf 'iwe {version}\\n'\n", encoding="utf-8")
                binary.chmod(0o755)
                return binary.resolve()

            brew_binary = executable(root / "brew/bin")
            brew_spec = replace(base, runtime_source="homebrew", runtime_directory=None)
            self.assertEqual(
                skill_manifest.resolve_runtime_binary(
                    brew_spec, env={"HOMEBREW_PREFIX": str(root / "brew")}
                ),
                brew_binary,
            )

            cargo_binary = executable(root / "cargo/bin")
            cargo_spec = replace(base, runtime_source="cargo", runtime_directory=None)
            self.assertEqual(
                skill_manifest.resolve_runtime_binary(
                    cargo_spec, env={"CARGO_HOME": str(root / "cargo")}
                ),
                cargo_binary,
            )

            relative_root = root / "relative-project"
            shutil.copytree(ROOT / "skills", relative_root / "skills")
            shutil.copytree(ROOT / "contracts", relative_root / "contracts")
            relative_binary = executable(relative_root / "tools")
            relative_config = (ROOT / "config.toml").read_text(encoding="utf-8").replace(
                'source = "homebrew"', 'source = "directory"\ndirectory = "tools"'
            )
            (relative_root / "config.toml").write_text(relative_config, encoding="utf-8")
            relative_spec = load_skill(root=relative_root)
            self.assertEqual(relative_spec.runtime_directory, (relative_root / "tools").resolve())
            self.assertEqual(skill_manifest.verify_runtime_binary(relative_spec), relative_binary)

            absolute_binary = executable(root / "absolute-tools")
            absolute_spec = replace(
                base,
                runtime_source="directory",
                runtime_directory=absolute_binary.parent,
            )
            self.assertEqual(skill_manifest.verify_runtime_binary(absolute_spec), absolute_binary)
            wrong_binary = executable(root / "wrong", "0.18.1")
            with self.assertRaisesRegex(RuntimeError, "expected 'iwe 0.18.0'"):
                skill_manifest.verify_runtime_binary(
                    replace(absolute_spec, runtime_directory=wrong_binary.parent)
                )

    def test_manifest_rejects_invalid_or_incomplete_runtime_source(self) -> None:
        for replacement, message in (
            ('source = "unknown"', "source must be homebrew"),
            ('source = "directory"', "requires directory"),
        ):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "skills", root / "skills")
                shutil.copytree(ROOT / "contracts", root / "contracts")
                config = (ROOT / "config.toml").read_text(encoding="utf-8").replace(
                    'source = "homebrew"', replacement
                )
                (root / "config.toml").write_text(config, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_skills(root)

        for cli in ("../iwe", "nested/iwe", "/tmp/iwe", "nested\\iwe"):
            with self.subTest(cli=cli), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "skills", root / "skills")
                shutil.copytree(ROOT / "contracts", root / "contracts")
                escaped_cli = cli.replace("\\", "\\\\")
                config = (ROOT / "config.toml").read_text(encoding="utf-8").replace(
                    'cli = "iwe"', f'cli = "{escaped_cli}"'
                )
                (root / "config.toml").write_text(config, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "runtime cli must be a filename"):
                    load_skills(root)

    def test_manifest_rejects_escaping_contract_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "skills", root / "skills")
            (root / "config.toml").write_text(
                (ROOT / "config.toml").read_text(encoding="utf-8").replace(
                    'file = "contracts/iwe-v18.json"', 'file = "../iwe-v18.json"'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "contract path escapes"):
                load_skills(root)

    def test_manifest_rejects_contract_limit_above_execution_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "skills", root / "skills")
            shutil.copytree(ROOT / "contracts", root / "contracts")
            (root / "config.toml").write_text(
                (ROOT / "config.toml").read_text(encoding="utf-8").replace(
                    "maximum_search_results = 20", "maximum_search_results = 10"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "default_limit"):
                load_skills(root)

    def test_manifest_rejects_model_facing_version_or_compatibility_drift(self) -> None:
        for old, new, message in (
            ('version: "0.4.0"', 'version: "0.4.1"', "skill_version"),
            (
                'metadata:\n  version: "0.4.0"',
                'version: "0.4.0"',
                "metadata",
            ),
            (
                'metadata:\n  version: "0.4.0"',
                'metadata:\n  nested:\n    version: "0.4.0"',
                "metadata.version",
            ),
            (
                "compatibility: Requires IWE CLI >=0.18.0.",
                "compatibility: Requires IWE CLI >=0.17.0.",
                "compatibility",
            ),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / "skills", root / "skills")
                shutil.copytree(ROOT / "contracts", root / "contracts")
                shutil.copy2(ROOT / "config.toml", root / "config.toml")
                skill_file = root / "skills/iwe-v18/SKILL.md"
                skill_file.write_text(
                    skill_file.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, message):
                    load_skills(root)

    def test_model_facing_payload_has_no_external_documentation(self) -> None:
        _, skills = load_skills(ROOT)
        for spec in skills.values():
            for path in spec.path.rglob("*"):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8")
                lowered = text.lower()
                self.assertNotIn("http://", lowered, path)
                self.assertNotIn("https://", lowered, path)
                self.assertNotIn("iwe docs", lowered, path)

    def test_runtime_payload_is_small_and_only_has_triggered_references(self) -> None:
        _, skills = load_skills(ROOT)
        for spec in skills.values():
            skill_file = spec.path / "SKILL.md"
            skill = skill_file.read_text(encoding="utf-8")
            lines = skill.splitlines()
            words = skill.split()
            self.assertGreaterEqual(len(lines), 60)
            self.assertLessEqual(len(lines), 270)
            self.assertGreaterEqual(len(words), 500)
            self.assertLessEqual(len(words), 2_700)
            references = sorted(path.name for path in (spec.path / "references").glob("*.md"))
            self.assertEqual(references, ["errors.md"])
            self.assertIn("## Complex IWE queries", skill)
            self.assertIn("references/errors.md", skill)
            self.assertLessEqual(
                sum(path.stat().st_size for path in (spec.path / "references").glob("*.md")),
                16_000,
            )

    def test_skill_encodes_optimistic_bounded_execution_policy(self) -> None:
        _, skills = load_skills(ROOT)
        for spec in skills.values():
            skill = (spec.path / "SKILL.md").read_text(encoding="utf-8")
            for required in (
                "IWE is authoritative",
                "Do not use web search",
                "Do not run routine preflight",
                "Default result limit: 20",
                "Do not run a second query",
                "Exact command help",
                "Refine the IWE query once",
                "fresh, focused confirmation",
            ):
                self.assertIn(required, skill)
            self.assertEqual(skill.count("--help"), 1)
            self.assertNotIn("iwe --version", skill)
            self.assertNotIn("iwe status", skill)
            self.assertNotIn("iwe schema\n", skill)
            self.assertNotIn("allowed-tools:", skill)

    def test_skill_examples_are_bounded_and_use_contract_commands(self) -> None:
        spec = load_skill(root=ROOT)
        skill = (spec.path / "SKILL.md").read_text(encoding="utf-8")
        contract = json.loads(spec.contract_file.read_text(encoding="utf-8"))
        command_lines = [line.strip() for line in skill.splitlines() if line.strip().startswith("iwe ")]
        self.assertGreaterEqual(len(command_lines), 2)
        self.assertLessEqual(len(command_lines), 4)
        for line in command_lines:
            command = line.split()[1]
            self.assertIn(command, contract["commands"])
        for line in command_lines:
            if line.startswith(("iwe find ", "iwe retrieve ")):
                self.assertRegex(line, r"--limit\s+[1-9]")
                self.assertIn("--format json", line)
        find_example = next(line for line in command_lines if line.startswith("iwe find "))
        self.assertIn("key=$key,title=$title", find_example)
        update_example = next(line for line in command_lines if line.startswith("iwe update "))
        self.assertIn("--append", update_example)
        self.assertIn("content:", update_example)
        self.assertTrue(any(line.startswith("iwe extract ") for line in command_lines))
        self.assertIn('"body":"<text>"', skill)
        self.assertIn("Create has no `--format` flag", skill)

    def test_local_iwe_matches_tested_version(self) -> None:
        spec = load_skill(root=ROOT)
        self.assertTrue(IWE.is_file(), f"missing local IWE binary: {IWE}")
        version = subprocess.run(
            [str(IWE), "--version"], text=True, capture_output=True, check=True
        ).stdout.strip()
        self.assertEqual(version, f"iwe {spec.tested_version}")

    def test_contract_sync_check_passes(self) -> None:
        spec = load_skill(root=ROOT)
        env = os.environ.copy()
        env["PATH"] = f"{IWE.parent}:{env.get('PATH', '')}"
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/sync_iwe_contract.py"), "--skill", spec.name, "--check"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_recommended_agent_metadata_exists(self) -> None:
        _, skills = load_skills(ROOT)
        for spec in skills.values():
            metadata = (spec.path / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${spec.name}", metadata)

    def test_skill_metrics_report_compact_offline_payload(self) -> None:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/skill_metrics.py"), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        metrics = payload["skills"][0]
        self.assertEqual(metrics["external_urls"], 0)
        self.assertEqual(metrics["reference_files"], 1)
        self.assertLessEqual(metrics["skill_lines"], 270)
        self.assertGreaterEqual(metrics["estimated_tokens"], 800)
        self.assertLessEqual(metrics["estimated_tokens"], 4_000)
        self.assertEqual(metrics["contract_operations"], 22)

    def test_skill_contains_every_cataloged_case_and_command_glossary_entry(self) -> None:
        spec = load_skill(root=ROOT)
        skill = (spec.path / "SKILL.md").read_text(encoding="utf-8")
        contract = json.loads(spec.contract_file.read_text(encoding="utf-8"))
        expected_cases = {
            *(f"**A{i} " for i in range(1, 11)),
            *(f"**B{i} " for i in range(1, 11)),
            *(f"**C{i} " for i in range(1, 9)),
            *(f"**D{i} " for i in range(1, 7)),
            *(f"**E{i} " for i in range(1, 6)),
            *(f"**F{i} " for i in range(1, 9)),
            *(f"**G{i} " for i in range(1, 8)),
            *(f"**H{i} " for i in range(1, 4)),
            *(f"**I{i} " for i in range(1, 6)),
        }
        self.assertEqual(len(expected_cases), 62)
        for case in expected_cases:
            self.assertIn(case, skill)
        glossary = skill.split("## Command glossary", 1)[1].split("## Complex IWE queries", 1)[0]
        for operation in contract["commands"]:
            command = operation.replace(".", " ")
            self.assertIn(f"`{command}`", glossary)
        for rare_case in (
            "missing executable",
            "still-unknown command/option",
            "invalid YAML",
            "empty result after refinement",
            "unsupported operation",
            "source outside index",
            "unexplained truncation",
            "permission/I/O failure",
            "schema/expectation failure",
        ):
            self.assertIn(rare_case, skill)

    def test_eval_configuration_and_scenarios_load(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertEqual(module.SCENARIOS_FILE.name, "iwe.eval.yaml")
        self.assertTrue(module.SCENARIO_SCHEMA.is_file())
        self.assertFalse((ROOT / "tests/eval/features/iwe.feature").exists())
        scenarios = module.load_scenarios()
        source = module.yaml.safe_load(module.SCENARIOS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(source["schema_version"], 2)
        for item in source["scenarios"]:
            self.assertNotIn("execution", item)
            self.assertNotIn("scoring", item)
            self.assertNotIn("iwe_calls", item.get("efficiency", {}))
            self.assertNotIn("result_limit", item.get("runtime", {}))
            self.assertEqual(
                set(item["procedure"]),
                {"ideal", "acceptable_variations", "stop_when", "avoid"},
            )
            self.assertTrue(all(item["procedure"].values()))
        names = {scenario.name for scenario in scenarios}
        self.assertEqual(len(scenarios), 10)
        for expected in (
            "One-call bounded discovery",
            "Ambiguous discovery with one follow-up",
            "Recover from CLI option incompatibility",
            "Fallback when IWE is unavailable",
        ):
            self.assertIn(expected, names)
        skill = load_skill(root=ROOT)
        for scenario in scenarios:
            self.assertGreaterEqual(scenario.max_output_bytes, 1)
            self.assertLessEqual(scenario.max_output_bytes, skill.maximum_output_bytes)
            self.assertEqual(set(scenario.scoring), set(module.DIMENSIONS))
            for dimension, scoring in scenario.scoring.items():
                self.assertEqual(set(scoring), {"minimum_score", "excellent"}, dimension)
                self.assertIn(scoring["minimum_score"], range(6), dimension)
                self.assertTrue(scoring["excellent"].strip())
        config = json.loads((ROOT / "tests/eval/configs/codex.json").read_text(encoding="utf-8"))
        for command in (config["agent_command"], config["judge_command"]):
            self.assertIn("--strict-config", command)
            self.assertIn('shell_environment_policy.inherit=\"none\"', command)
        self.assertIn("-s workspace-write", config["agent_command"])
        self.assertIn("sandbox_workspace_write.network_access=false", config["agent_command"])
        self.assertIn("-s read-only", config["judge_command"])
        secret = "IWE_EVAL_TEST_SECRET"
        os.environ[secret] = "must-not-leak"
        try:
            environment = module.eval_environment(
                Path("/tmp/home"), Path("/tmp/codex"), Path("/tmp/shims"), IWE, Path("/tmp/eval")
            )
        finally:
            os.environ.pop(secret, None)
        self.assertNotIn(secret, environment)

    def test_eval_scenario_loader_rejects_malformed_scoring_fail_closed(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_invalid_yaml", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        source = module.yaml.safe_load(module.SCENARIOS_FILE.read_text(encoding="utf-8"))

        def reject(mutator) -> None:
            document = json.loads(json.dumps(source))
            mutator(document)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.yaml"
                path.write_text(module.yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
                with self.assertRaises(ValueError):
                    module.load_scenarios(path)

        reject(lambda document: document["scenarios"][0]["excellent"].update(task_correctness="   "))
        reject(lambda document: document["scenarios"][0]["excellent"].update(weight="unsupported"))
        reject(lambda document: document["scenarios"][0]["efficiency"].update(task_tool_calls=[3, 2]))
        reject(lambda document: document["scenarios"][0]["excellent"].pop("evidence_quality"))
        reject(lambda document: document["scenarios"][0].pop("procedure"))
        reject(lambda document: document["scenarios"][0]["procedure"].update(ideal=[]))

        duplicate_key = module.SCENARIOS_FILE.read_text(encoding="utf-8").replace(
            "    task_correctness:",
            "    task_correctness: duplicate\n    task_correctness:",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate-key.yaml"
            path.write_text(duplicate_key, encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_scenarios(path)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-syntax.yaml"
            path.write_text("schema_version: [\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_scenarios(path)

    def test_eval_uses_declared_zero_to_five_scores_and_metric_thresholds(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_thresholds", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scenario = next(
            item for item in module.load_scenarios()
            if item.id == "one-call-bounded-discovery"
        )
        self.assertEqual(set(scenario.scoring), set(module.DIMENSIONS))
        self.assertEqual(scenario.scoring["tool_efficiency"]["minimum_score"], 5)
        self.assertEqual(scenario.scoring["resource_efficiency"]["minimum_score"], 5)

        judge_schema = json.loads(
            (ROOT / "tests/eval/judge.schema.json").read_text(encoding="utf-8")
        )
        score_schema = judge_schema["$defs"]["dimension"]["properties"]["score"]
        self.assertEqual(
            score_schema, {"type": "integer", "minimum": 0, "maximum": 5}
        )

        critique = {
            "dimensions": {name: {"score": 5} for name in module.DIMENSIONS}
        }
        critique["dimensions"]["tool_efficiency"]["score"] = 2
        result = module.verdict(scenario, critique, [], True)
        self.assertTrue(result["valid"])
        self.assertEqual(result["metric_scores"]["tool_efficiency"], 2)
        self.assertIn("tool_efficiency", result["metric_failures"])

        for malformed_score in ("not-a-number", True, 6, -1):
            malformed: dict = {
                "dimensions": {name: {"score": 5} for name in module.DIMENSIONS}
            }
            malformed["dimensions"]["tool_efficiency"]["score"] = malformed_score
            malformed_verdict = module.verdict(scenario, malformed, [], True)
            self.assertFalse(malformed_verdict["valid"])
            self.assertEqual(malformed_verdict["metric_scores"]["tool_efficiency"], 0)

    def test_scenarios_declare_manual_excellence_targets(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_targets", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        targets = {
            scenario.name: (
                scenario.min_tool_calls,
                scenario.max_tool_calls,
                scenario.min_task_tool_output_bytes,
                scenario.max_task_tool_output_bytes,
            )
            for scenario in module.load_scenarios()
        }
        self.assertEqual(targets, {
            "Discover and retrieve bounded multi-hop context": (1, 1, 4000, 26800),
            "Query structured metadata without scanning files": (1, 1, 1000, 20000),
            "Apply a guarded structured-block update": (3, 5, 1000, 12000),
            "Refactor an inclusion link without breaking the graph": (3, 6, 1000, 16000),
            "Refuse an unbounded destructive request": (0, 1, 0, 4000),
            "Create and validate a schema-bound document": (1, 2, 0, 4000),
            "One-call bounded discovery": (1, 1, 100, 5000),
            "Ambiguous discovery with one follow-up": (1, 2, 100, 12000),
            "Recover from CLI option incompatibility": (2, 3, 100, 12000),
            "Fallback when IWE is unavailable": (2, 3, 100, 6000),
        })

        update = next(
            scenario
            for scenario in module.load_scenarios()
            if scenario.id == "apply-a-guarded-structured-block-update"
        )
        renamed = replace(update, name="Renamed display label")
        self.assertEqual(renamed.slug, update.id)
        errors = module.mechanical_errors(
            renamed,
            {},
            {},
            [],
            Path("/tmp/unused-workspace"),
            module.command_metrics([]),
        )
        self.assertIn("roadmap does not equal the exact requested transformation", errors)

    def test_judge_workspace_excludes_tested_skill(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_judge", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "agent-workspace"
            skill_file = workspace / ".agents/skills/iwe-v18/SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text("secret tested policy", encoding="utf-8")
            (workspace / "result.md").write_text("result", encoding="utf-8")
            (workspace / "copied-policy.md").write_text("secret tested policy", encoding="utf-8")
            module.remove_tested_skill_for_judge(workspace)
            self.assertFalse((workspace / ".agents").exists())
            self.assertFalse(any(workspace.rglob("SKILL.md")))
            self.assertEqual((workspace / "result.md").read_text(encoding="utf-8"), "result")
            judge_workspace = module.create_judge_workspace(root)
            self.assertEqual(list(judge_workspace.iterdir()), [])

        prompt = module.judge_prompt(
            load_skill(root=ROOT),
            module.load_scenarios()[0],
            {
                "metrics": {},
                "iwe_telemetry": [],
                "commands": [{
                    "command": "sed -n '1,200p' .agents/skills/iwe-v18/SKILL.md",
                    "output": "secret tested policy",
                }],
                "final": "answer",
            },
            {},
            {},
            [],
        )
        self.assertNotIn("secret tested policy", prompt)
        self.assertIn("[TESTED_SKILL_OUTPUT_REDACTED]", prompt)

        skill = load_skill(root=ROOT)
        sensitive_line = next(
            line for line in (skill.path / "SKILL.md").read_text(encoding="utf-8").splitlines()
            if len(line) >= 48
        )
        copied_prompt = module.judge_prompt(
            skill,
            module.load_scenarios()[0],
            {
                "metrics": {},
                "iwe_telemetry": [],
                "commands": [{"command": "cat copied-policy.md", "output": sensitive_line}],
                "final": sensitive_line,
            },
            {},
            {},
            [],
        )
        self.assertNotIn(sensitive_line, copied_prompt)
        self.assertIn("[TESTED_SKILL_TEXT_REDACTED]", copied_prompt)
        wrapped = "\n".join(
            sensitive_line[index:index + 40]
            for index in range(0, len(sensitive_line), 40)
        )
        wrapped_prompt = module.judge_prompt(
            skill,
            module.load_scenarios()[0],
            {
                "metrics": {},
                "iwe_telemetry": [{"stdout": wrapped}],
                "commands": [{"command": "cat copied-policy.md", "output": wrapped}],
                "final": wrapped,
            },
            {},
            {},
            [],
        )
        self.assertNotIn(wrapped, wrapped_prompt)
        self.assertIn("[TESTED_SKILL_TEXT_REDACTED]", wrapped_prompt)

    def test_install_skill_uses_one_neutral_guidance_tree(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_install", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            module.install_skill(workspace, load_skill(root=ROOT))
            self.assertTrue((workspace / ".agents/guidance/SKILL.md").is_file())
            self.assertTrue((workspace / ".agents/guidance/references/errors.md").is_file())
            self.assertFalse((workspace / ".agents/skills").exists())
            self.assertEqual(len(list((workspace / ".agents").rglob("SKILL.md"))), 1)

    def test_task_tool_calls_exclude_only_exact_successful_standalone_activation(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_activation", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        commands = [
            {
                "command": "sed -n '1,200p' .agents/skills/iwe-v18/SKILL.md",
                "exit_code": 0,
                "output": "skill body",
            },
            {
                "command": "sed -n '1,200p' .agents/skills/other/SKILL.md",
                "exit_code": 0,
                "output": "other skill",
            },
            {
                "command": "sed -n '1,200p' .agents/skills/iwe-v18/SKILL.md",
                "exit_code": 1,
                "output": "",
            },
            {
                "command": "printf '%s' .agents/skills/iwe-v18/SKILL.md",
                "exit_code": 0,
                "output": ".agents/skills/iwe-v18/SKILL.md",
            },
            {
                "command": "sed -n '1,200p' .agents/skills/iwe-v18/SKILL.md && iwe find --lexical x --limit 1",
                "exit_code": 0,
                "output": "skill body\n[]",
            },
            {
                "command": "cat .agents/skills/iwe-v18/SKILL.md graph/task.md",
                "exit_code": 0,
                "output": "skill body\ntask body",
            },
            {
                "command": "cat .agents/skills/iwe-v18/SKILL.md",
                "output": "skill body",
            },
        ]
        metrics = module.command_metrics(commands, tested_skill="iwe-v18")
        self.assertEqual(metrics["raw_tool_calls"], 7)
        self.assertEqual(metrics["task_tool_calls"], 6)
        combined_only = module.command_metrics([commands[-2]], tested_skill="iwe-v18")
        self.assertEqual(combined_only["task_tool_calls"], 1)
        non_range_sed = module.command_metrics(
            [{
                "command": "sed -n p .agents/skills/iwe-v18/SKILL.md",
                "exit_code": 0,
                "output": "skill body",
            }],
            tested_skill="iwe-v18",
        )
        self.assertEqual(non_range_sed["task_tool_calls"], 1)
        single_address_sed = module.command_metrics(
            [{
                "command": "sed -n 1p .agents/skills/iwe-v18/SKILL.md",
                "exit_code": 0,
                "output": "skill body",
            }],
            tested_skill="iwe-v18",
        )
        self.assertEqual(single_address_sed["task_tool_calls"], 0)
        wrapped_activation = module.command_metrics(
            [{
                "command": "/bin/bash -lc \"sed -n '1,240p' .agents/skills/iwe-v18/SKILL.md\"",
                "exit_code": 0,
                "output": "skill body",
            }],
            tested_skill="iwe-v18",
        )
        self.assertEqual(wrapped_activation["task_tool_calls"], 0)
        wrapped_chain = module.command_metrics(
            [{
                "command": "/bin/bash -lc \"sed -n '1,240p' .agents/skills/iwe-v18/SKILL.md && iwe find --lexical x --limit 1\"",
                "exit_code": 0,
                "output": "skill body\n[]",
            }],
            tested_skill="iwe-v18",
        )
        self.assertEqual(wrapped_chain["task_tool_calls"], 1)
        for noncanonical_path in (
            "/tmp/other/.agents/skills/iwe-v18/SKILL.md",
            "../other/.agents/skills/iwe-v18/SKILL.md",
            "./.agents/skills/iwe-v18/SKILL.md",
        ):
            noncanonical = module.command_metrics(
                [{
                    "command": f"cat {noncanonical_path}",
                    "exit_code": 0,
                    "output": "skill body",
                }],
                tested_skill="iwe-v18",
            )
            self.assertEqual(noncanonical["task_tool_calls"], 1)

    def test_eval_metrics_count_chained_iwe_and_forbidden_fallbacks(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_metrics", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        metrics = module.command_metrics([
            {
                "command": "/bin/bash -lc \"iwe find --lexical x --limit 5 -f json && iwe retrieve -k x --limit 1 -f json\"",
                "exit_code": 0,
                "output": "[]",
            },
            {
                "command": "/bin/bash -lc \"rg needle graph\"",
                "exit_code": 97,
                "output": "blocked",
            },
        ])
        self.assertEqual(metrics["iwe_calls"], 2)
        self.assertEqual(metrics["forbidden_fallback_calls"], 1)
        self.assertEqual(metrics["iwe_output_bytes"], 2)
        self.assertEqual(metrics["unbounded_read_calls"], 0)

    def test_eval_metrics_detect_unbounded_discovery(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_unbounded", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        metrics = module.command_metrics([{
            "command": "/bin/bash -lc \"iwe find --lexical virtue --format json\"",
            "exit_code": 0,
            "output": "[]",
        }])
        self.assertEqual(metrics["unbounded_read_calls"], 1)
        for args in (
            ["find", "--lexical", "virtue", "--limit", "0", "--format", "json"],
            ["retrieve", "--key", "virtue", "--max-documents", "0", "--format", "json"],
            ["retrieve", "--key", "virtue", "--max-tokens", "0", "--format", "json"],
            ["retrieve", "--key", "virtue", "--max-document-tokens", "0", "--format", "json"],
            ["retrieve", "--fuzzy=virtue", "--format", "json"],
            ["retrieve", "--lexical=virtue", "--format", "json"],
            ["retrieve", "--filter=type=note", "--format", "json"],
            [
                "retrieve", "--key", "virtue", "--expand-includes", "0",
                "--max-documents", "5", "--max-tokens", "100", "--max-document-tokens", "50",
            ],
        ):
            with self.subTest(args=args):
                self.assertTrue(module._unbounded_iwe_args(args))
                command = "iwe " + " ".join(args)
                parsed = module.command_metrics([{"command": command, "output": "[]"}])
                self.assertEqual(parsed["unbounded_read_calls"], 1)
        self.assertFalse(module._unbounded_iwe_args([
            "retrieve", "--key", "virtue", "--expand-includes=1",
            "--max-documents=5", "--max-tokens=100", "--max-document-tokens=50",
        ]))

    def test_eval_metrics_use_shim_telemetry_for_exact_output_and_results(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_telemetry", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        metrics = module.command_metrics(
            [
                {
                    "command": "sed -n '1,200p' .agents/skills/iwe-v18/SKILL.md",
                    "exit_code": 0,
                    "output": "skill",
                },
                {"command": "iwe find --lexical virtue --limit 2 --format json", "output": "[]"},
            ],
            [{
                "args": ["find", "--lexical", "virtue", "--limit", "2", "--format", "json"],
                "exit_code": 0,
                "stdout_bytes": 2,
                "emitted_stdout_bytes": 2,
                "stderr_bytes": 0,
                "result_count": 0,
                "stdout": "[]",
                "stderr": "",
            }],
            tested_skill="iwe-v18",
        )
        self.assertEqual(metrics["iwe_calls"], 1)
        self.assertEqual(metrics["iwe_output_bytes"], 2)
        self.assertEqual(metrics["max_result_count"], 0)
        self.assertEqual(metrics["result_records"], 0)
        self.assertEqual(metrics["task_tool_output_bytes"], 2)
        self.assertEqual(metrics["raw_tool_calls"], 2)
        self.assertEqual(metrics["task_tool_calls"], 1)
        self.assertEqual(metrics["unbounded_read_calls"], 0)
        self.assertEqual(metrics["iwe_telemetry_extra"], 0)
        self.assertEqual(metrics["iwe_telemetry_mismatch"], 0)
        missing = module.command_metrics(
            [{"command": "iwe find --lexical virtue --limit 1 --format json", "output": "[]"}],
            [],
        )
        self.assertEqual(missing["iwe_telemetry_missing"], 1)
        forged_record = {
            "args": ["find", "--lexical", "virtue", "--limit", "1", "--format", "json"],
            "exit_code": 0,
            "stdout_bytes": 2,
            "emitted_stdout_bytes": 2,
            "stderr_bytes": 0,
            "result_count": 0,
            "stdout": "[]",
            "stderr": "",
        }
        forged = module.command_metrics(
            [{"command": "printf 'no iwe invocation'", "exit_code": 0, "output": ""}],
            [forged_record],
        )
        self.assertEqual(forged["iwe_calls"], 0)
        self.assertEqual(forged["iwe_telemetry_extra"], 1)
        self.assertEqual(forged["iwe_telemetry_mismatch"], 1)
        self.assertEqual(forged["iwe_telemetry_invalid"], 1)
        forged_errors = module.efficiency_errors(module.load_scenarios()[0], forged)
        self.assertIn("IWE telemetry contains records without observed command invocations", forged_errors)
        self.assertIn("IWE telemetry arguments do not match observed command invocations", forged_errors)
        mismatched = module.command_metrics(
            [{"command": "iwe find --lexical virtue --limit 1 --format json", "exit_code": 0, "output": "[]"}],
            [{**forged_record, "args": ["find", "--lexical", "other", "--limit", "1", "--format", "json"]}],
        )
        self.assertEqual(mismatched["iwe_telemetry_mismatch"], 1)
        same_argv_forgery = module.command_metrics(
            [{"command": "iwe find --lexical virtue --limit 1 --format json", "exit_code": 0, "output": "[]"}],
            [{**forged_record, "result_count": 1}],
        )
        self.assertEqual(same_argv_forgery["iwe_telemetry_mismatch"], 0)
        self.assertEqual(same_argv_forgery["iwe_telemetry_invalid"], 1)
        empty_measurement_forgery = module.command_metrics(
            [{"command": "iwe find --lexical virtue --limit 1 --format json", "exit_code": 0, "output": "[]"}],
            [{
                **forged_record,
                "stdout_bytes": 0,
                "emitted_stdout_bytes": 0,
                "result_count": None,
                "stdout": "",
            }],
        )
        self.assertEqual(empty_measurement_forgery["iwe_telemetry_invalid"], 1)
        self.assertIn(
            "IWE telemetry measurements do not match observed command evidence",
            module.efficiency_errors(module.load_scenarios()[0], same_argv_forgery),
        )

    def test_eval_mechanical_errors_only_gate_integrity_and_prohibited_actions(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_budget", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scenario = module.Scenario(
            "bounded", "fixture", "request", "rubric",
            max_output_bytes=64, allow_fallback=False, iwe_mode="real"
        )
        errors = module.efficiency_errors(scenario, {
            "iwe_calls": 2,
            "help_calls": 0,
            "web_calls": 0,
            "docs_calls": 0,
            "forbidden_fallback_calls": 1,
            "broad_workspace_reads": 0,
            "reference_reads": 1,
            "iwe_output_bytes": 100,
            "context_bytes": 100,
            "failed_iwe_calls": 1,
            "unbounded_read_calls": 1,
            "max_result_count": 21,
        })
        self.assertEqual(
            errors,
            [
                "unbounded IWE discovery or retrieval used",
                "forbidden fallback tool used",
            ],
        )

    def test_eval_fixture_cache_enforces_pinned_commit_and_clean_tree(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_fixture", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.name", "Eval Test"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.email", "eval@example.invalid"], cwd=source, check=True)
            marker = source / "marker.txt"
            marker.write_text("pinned\n", encoding="utf-8")
            subprocess.run(["git", "add", "marker.txt"], cwd=source, check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "pinned"], cwd=source, check=True)
            pinned = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True, capture_output=True, check=True
            ).stdout.strip()
            marker.write_text("newer\n", encoding="utf-8")
            subprocess.run(["git", "commit", "--quiet", "-am", "newer"], cwd=source, check=True)
            config = {"fixtures": {"pkm-demo": {"repository": str(source), "commit": pinned}}}
            cache = root / "cache"
            cache.mkdir()
            target = module.ensure_fixture(config, "pkm-demo", cache)
            self.assertEqual((target / "marker.txt").read_text(encoding="utf-8"), "pinned\n")
            (target / "marker.txt").write_text("dirty\n", encoding="utf-8")
            (target / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            target = module.ensure_fixture(config, "pkm-demo", cache)
            self.assertEqual((target / "marker.txt").read_text(encoding="utf-8"), "pinned\n")
            self.assertFalse((target / "untracked.txt").exists())

    def test_eval_failure_and_tool_shims_behave_deterministically(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_shims", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            telemetry = root / "iwe.jsonl"
            env = os.environ.copy()
            env["IWE_EVAL_IWE_LOG"] = str(telemetry)
            unavailable = module.Scenario(
                "unavailable", "fixture", "request", "rubric",
                max_output_bytes=64, allow_fallback=True, iwe_mode="unavailable"
            )
            module.install_command_shims(root / "unavailable", unavailable, IWE, root)
            result = subprocess.run(
                [str(root / "unavailable/iwe"), "find"], text=True, capture_output=True, env=env
            )
            self.assertEqual(result.returncode, 127)
            blocked = subprocess.run(
                [str(root / "unavailable/rg"), "needle"], text=True, capture_output=True
            )
            self.assertEqual(blocked.returncode, 97)

            incompatible = module.Scenario(
                "incompatible", "fixture", "request", "rubric",
                max_output_bytes=64, allow_fallback=False, iwe_mode="incompatible"
            )
            module.install_command_shims(root / "incompatible", incompatible, IWE, root)
            shim = str(root / "incompatible/iwe")
            first = subprocess.run(
                [shim, "find", "--project", "key=$key"],
                text=True,
                capture_output=True,
                env=env,
            )
            help_run = subprocess.run([shim, "find", "--help"], text=True, capture_output=True, env=env)
            retry = subprocess.run([shim, "--version"], text=True, capture_output=True, env=env)
            self.assertEqual(first.returncode, 2)
            self.assertEqual(help_run.returncode, 0)
            self.assertEqual(retry.stdout.strip(), "iwe 0.18.0")
            records = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 4)
            self.assertEqual([record["exit_code"] for record in records], [127, 2, 0, 0])
            self.assertTrue(all("stdout_bytes" in record for record in records))
            self.assertGreater(records[2]["stdout_bytes"], 64)
            self.assertEqual(records[2]["emitted_stdout_bytes"], 64)
            self.assertEqual(records[-1]["stdout"].strip(), "iwe 0.18.0")


if __name__ == "__main__":
    unittest.main()
