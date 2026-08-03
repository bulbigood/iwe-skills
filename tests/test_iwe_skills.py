from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from skill_manifest import load_skill, load_skills


IWE = Path(shutil.which("iwe") or "/home/linuxbrew/.linuxbrew/bin/iwe")


class IweSkillTests(unittest.TestCase):
    def test_manifest_and_frozen_contract_are_consistent(self) -> None:
        default, skills = load_skills(ROOT)
        self.assertIn(default, skills)
        for name, spec in skills.items():
            self.assertEqual(name, spec.path.name)
            self.assertEqual(spec.runtime_cli, "iwe")
            self.assertEqual(spec.supported, ">=0.18.0 <0.19.0")
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
                {"find", "retrieve", "update", "create", "extract", "delete", "schema.validate"},
            )
            self.assertNotIn("docs", contract["commands"])

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
            ('version: "0.2.0"', 'version: "0.2.1"', "skill_version"),
            (
                'metadata:\n  version: "0.2.0"',
                'version: "0.2.0"',
                "metadata",
            ),
            (
                'metadata:\n  version: "0.2.0"',
                'metadata:\n  nested:\n    version: "0.2.0"',
                "metadata.version",
            ),
            (
                "compatibility: Requires IWE CLI >=0.18.0 and <0.19.0.",
                "compatibility: Requires IWE CLI >=0.19.0 and <0.20.0.",
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
            self.assertLessEqual(len(lines), 150)
            self.assertGreaterEqual(len(words), 500)
            self.assertLessEqual(len(words), 1500)
            references = sorted(path.name for path in (spec.path / "references").glob("*.md"))
            self.assertEqual(references, ["errors.md", "query-language.md"])
            self.assertIn("references/query-language.md", skill)
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
                "unknown command or option",
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
        self.assertEqual(metrics["reference_files"], 2)
        self.assertLessEqual(metrics["skill_lines"], 150)
        self.assertGreaterEqual(metrics["estimated_tokens"], 800)
        self.assertLessEqual(metrics["estimated_tokens"], 2_000)
        self.assertEqual(metrics["contract_operations"], 7)

    def test_eval_configuration_and_scenarios_load(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scenarios = module.parse_feature()
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
            self.assertGreaterEqual(scenario.max_iwe_calls, 0)
            self.assertGreaterEqual(scenario.max_output_bytes, 1)
            self.assertLessEqual(scenario.max_output_bytes, skill.maximum_output_bytes)
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
        metrics = module.command_metrics([], [{
            "args": ["find", "--lexical", "virtue", "--limit", "2", "--format", "json"],
            "exit_code": 0,
            "stdout_bytes": 123,
            "stderr_bytes": 20,
            "result_count": 2,
        }])
        self.assertEqual(metrics["iwe_calls"], 1)
        self.assertEqual(metrics["iwe_output_bytes"], 123)
        self.assertEqual(metrics["max_result_count"], 2)
        self.assertEqual(metrics["unbounded_read_calls"], 0)
        missing = module.command_metrics(
            [{"command": "iwe find --lexical virtue --limit 1 --format json", "output": "[]"}],
            [],
        )
        self.assertEqual(missing["iwe_telemetry_missing"], 1)

    def test_eval_budget_errors_are_mechanical(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval_budget", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scenario = module.Scenario(
            "bounded", "fixture", "request", "rubric", 1, 1, 64, False, "real"
        )
        errors = module.efficiency_errors(scenario, {
            "iwe_calls": 2,
            "help_calls": 0,
            "web_calls": 0,
            "docs_calls": 0,
            "forbidden_fallback_calls": 1,
            "broad_workspace_reads": 0,
            "reference_reads": 0,
            "iwe_output_bytes": 100,
            "context_bytes": 100,
            "failed_iwe_calls": 0,
            "unbounded_read_calls": 1,
            "max_result_count": 21,
        })
        self.assertIn("IWE call budget exceeded: 2 > 1", errors)
        self.assertIn("forbidden fallback tool used", errors)
        self.assertIn("IWE output budget exceeded: 100 > 64", errors)
        self.assertIn("unbounded IWE discovery or retrieval used", errors)
        self.assertIn("IWE result-count budget exceeded: 21 > 20", errors)

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
                "unavailable", "fixture", "request", "rubric", 1, 1, 64, True, "unavailable"
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
                "incompatible", "fixture", "request", "rubric", 3, 3, 64, False, "incompatible"
            )
            module.install_command_shims(root / "incompatible", incompatible, IWE, root)
            shim = str(root / "incompatible/iwe")
            first = subprocess.run([shim, "find"], text=True, capture_output=True, env=env)
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
