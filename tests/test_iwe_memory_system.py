from __future__ import annotations

import os
import shutil
import subprocess
import unittest
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/iwe-memory-system"
IWE = Path(shutil.which("iwe") or "/home/linuxbrew/.linuxbrew/bin/iwe")


class IweMemorySystemTests(unittest.TestCase):
    def test_generated_references_match_installed_iwe_0180(self) -> None:
        self.assertTrue(IWE.is_file(), f"missing local IWE binary: {IWE}")
        env = os.environ.copy()
        env["PATH"] = f"{IWE.parent}:{env.get('PATH', '')}"
        version = subprocess.run(
            [str(IWE), "--version"], text=True, capture_output=True, check=True
        ).stdout.strip()
        self.assertEqual(version, "iwe 0.18.0")
        result = subprocess.run(
            ["python3", str(SKILL / "scripts/generate-cli-reference.py"), "--check"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_complete_offline_reference_is_linked(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        builtin = (SKILL / "references/builtin-reference.md").read_text(encoding="utf-8")
        cli = (SKILL / "references/cli-reference.md").read_text(encoding="utf-8")
        self.assertIn("references/builtin-reference.md", skill)
        self.assertIn("references/cli-reference.md", skill)
        for topic in ("query", "config", "schema"):
            self.assertIn(f"## `{topic}`", builtin)
        for command in (
            "init", "create", "new", "retrieve", "find", "count", "normalize",
            "tree", "squash", "export", "schema", "stats", "rename", "delete",
            "extract", "inline", "update", "attach", "completions", "docs",
        ):
            self.assertIn(f"## `iwe {command}`", cli)

    def test_eval_suite_forbids_runtime_documentation_lookup(self) -> None:
        feature = (ROOT / "tests/eval/features/iwe-memory-system.feature").read_text()
        self.assertGreaterEqual(feature.count("Scenario:"), 6)
        self.assertIn("does not invoke internet access, iwe help, or iwe docs", feature)
        self.assertIn("Refuse an unbounded destructive request", feature)

    def test_codex_eval_configuration_and_scenarios_load(self) -> None:
        runner_path = ROOT / "tests/eval/run.py"
        spec = importlib.util.spec_from_file_location("iwe_skill_eval", runner_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        scenarios = module.parse_feature()
        self.assertEqual(len(scenarios), 6)
        self.assertEqual({item.fixture for item in scenarios}, {
            "seventeen-centuries", "pkm-demo", "pkm-demo-update",
            "pkm-demo-extract-inline", "pkm-demo-schema",
        })
        config = __import__("json").loads(
            (ROOT / "tests/eval/configs/codex.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["name"], "codex")
        self.assertIn("codex exec", config["agent_command"])
        self.assertIn("--output-schema {judge_schema}", config["judge_command"])


if __name__ == "__main__":
    unittest.main()
