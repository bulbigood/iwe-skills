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


DEFAULT_SKILL, SKILLS = load_skills(ROOT)
SELECTED_SKILL = load_skill(os.environ.get("IWE_SKILL"), ROOT)
IWE = Path(shutil.which("iwe") or "/home/linuxbrew/.linuxbrew/bin/iwe")


class IweSkillTests(unittest.TestCase):
    def test_manifest_matches_every_skill_metadata(self) -> None:
        self.assertIn(DEFAULT_SKILL, SKILLS)
        for name, spec in SKILLS.items():
            self.assertEqual(name, spec.path.name)
            self.assertTrue((spec.path / "SKILL.md").is_file())

    def test_generated_references_match_selected_iwe(self) -> None:
        self.assertTrue(IWE.is_file(), f"missing local IWE binary: {IWE}")
        env = os.environ.copy()
        env["PATH"] = f"{IWE.parent}:{env.get('PATH', '')}"
        version = subprocess.run(
            [str(IWE), "--version"], text=True, capture_output=True, check=True
        ).stdout.strip()
        self.assertEqual(version, f"iwe {SELECTED_SKILL.iwe_cli_version}")
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts/generate_skill_references.py"),
                "--skill",
                SELECTED_SKILL.name,
                "--check",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_complete_offline_references_are_linked(self) -> None:
        for spec in SKILLS.values():
            skill = (spec.path / "SKILL.md").read_text(encoding="utf-8")
            builtin = (spec.path / "references/builtin-reference.md").read_text(encoding="utf-8")
            cli = (spec.path / "references/cli-reference.md").read_text(encoding="utf-8")
            self.assertIn("references/builtin-reference.md", skill)
            self.assertIn("references/cli-reference.md", skill)
            for topic in ("query", "config", "schema"):
                self.assertIn(f"## `{topic}`", builtin)
                self.assertIn(f"[`{topic}`](#{topic})", builtin)
            for command in (
                "init", "create", "new", "retrieve", "find", "count",
                "normalize", "tree", "squash", "export", "schema", "stats",
                "rename", "delete", "extract", "inline", "update", "attach",
                "completions", "docs",
            ):
                self.assertIn(f"## `iwe {command}`", cli)
            self.assertIn("## Contents", cli)

    def test_cli_version_is_stored_only_in_manifest_and_skill_metadata(self) -> None:
        allowed = {ROOT / "config.toml"}
        allowed.update(spec.path / "SKILL.md" for spec in SKILLS.values())
        for spec in SKILLS.values():
            for path in ROOT.rglob("*"):
                if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if spec.iwe_cli_version in text:
                    self.assertIn(path, allowed, f"CLI version leaked into {path}")

    def test_agent_facing_text_omits_help_guidance(self) -> None:
        for spec in SKILLS.values():
            for path in spec.path.rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn("--help", text, f"help guidance remains in {path}")

    def test_guidance_matches_safety_policy(self) -> None:
        for spec in SKILLS.values():
            skill = (spec.path / "SKILL.md").read_text(encoding="utf-8")
            setup = (spec.path / "references/project-setup.md").read_text(encoding="utf-8")
            reads = (spec.path / "references/read-and-navigate.md").read_text(encoding="utf-8")
            writes = (spec.path / "references/write-and-refactor.md").read_text(encoding="utf-8")

            self.assertIn("`.iwe/` marker directory", skill)
            self.assertIn("marker directory alone is sufficient", setup)
            self.assertNotIn("`--roots` alias is deprecated", reads)
            self.assertIn("supported `--roots` flag", reads)
            self.assertIn("Default to `--keep-target`", writes)
            self.assertGreaterEqual(writes.count("fresh, focused confirmation"), 3)

    def test_marker_only_workspace_and_roots_flag_work(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            (Path(workspace) / ".iwe").mkdir()
            result = subprocess.run(
                [str(IWE), "find", "--roots"],
                cwd=workspace,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("deprecated", result.stderr.lower())

    def test_recommended_agent_metadata_exists(self) -> None:
        for spec in SKILLS.values():
            metadata = (spec.path / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${spec.name}", metadata)

    def test_eval_suite_uses_generic_skill_selection(self) -> None:
        feature = (ROOT / "tests/eval/features/iwe.feature").read_text(encoding="utf-8")
        self.assertGreaterEqual(feature.count("Scenario:"), 6)
        self.assertNotIn("--help", feature)
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
        config = json.loads(
            (ROOT / "tests/eval/configs/codex.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["name"], "codex")
        self.assertIn("codex exec", config["agent_command"])
        self.assertIn("--output-schema {judge_schema}", config["judge_command"])


if __name__ == "__main__":
    unittest.main()
