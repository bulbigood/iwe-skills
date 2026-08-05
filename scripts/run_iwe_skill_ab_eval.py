#!/usr/bin/env python3
"""Run the production all-scenario iwe-v18 versus both control conditions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from skill_manifest import load_skills, verify_runtime_binary


ROOT = Path(__file__).resolve().parents[1]
DEPRECATED_SKILL = "iwe-memory-system"
CURRENT_SKILL = "iwe-v18"
NO_SKILL_TARGET = "iwe-no-skill"
DEFAULT_SAMPLES = 5
DEFAULT_JOBS = 10
SCENARIOS_FILE = Path("tests/eval/scenarios/iwe.eval.yaml")
CACHE = Path("tests/eval/.cache/iwe-v18-vs-controls-all-scenarios")
DEFAULT_RESULTS_FILE = Path("tests/eval/results/2026-08-05-iwe-v18-vs-controls.md")


@dataclass(frozen=True)
class Target:
    skill_id: str
    skill_path: Path | None
    skill_version: str | None
    iwe_version: str
    contract_file: Path
    runtime_skill_id: str


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run iwe-v18 against deprecated-skill and no-skill controls."
    )
    parser.add_argument(
        "--samples",
        type=positive_int,
        default=DEFAULT_SAMPLES,
        help=f"paired samples per target (default: {DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--jobs",
        type=positive_int,
        default=DEFAULT_JOBS,
        help=f"concurrent production evaluation cells (default: {DEFAULT_JOBS})",
    )
    parser.add_argument(
        "--results-file",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help=f"generated Markdown report (default: {DEFAULT_RESULTS_FILE})",
    )
    parser.add_argument(
        "--agent",
        choices=("codex",),
        default="codex",
        help="shared agent implementation for tested runs and judges (default: codex)",
    )
    return parser.parse_args(argv)


def _deprecated_version(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"invalid frontmatter in {skill_file}")
    frontmatter = yaml.safe_load(text.split("\n---\n", 1)[0][4:])
    metadata = frontmatter.get("metadata") if isinstance(frontmatter, dict) else None
    version = metadata.get("version") if isinstance(metadata, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError(f"missing metadata.version in {skill_file}")
    return version


def load_scenario_ids(root: Path = ROOT) -> tuple[str, ...]:
    source = yaml.safe_load((root / SCENARIOS_FILE).read_text(encoding="utf-8"))
    scenarios = source.get("scenarios") if isinstance(source, dict) else None
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError(f"no scenarios declared in {SCENARIOS_FILE}")
    ids: list[str] = []
    for item in scenarios:
        identifier = item.get("id") if isinstance(item, dict) else None
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"every scenario in {SCENARIOS_FILE} must have a non-empty id")
        ids.append(identifier)
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate scenario id in {SCENARIOS_FILE}")
    return tuple(ids)


def load_targets(root: Path = ROOT) -> tuple[Target, ...]:
    default_id, skills = load_skills(root)
    if CURRENT_SKILL not in skills:
        raise ValueError(f"{CURRENT_SKILL} is not configured in config.toml")
    current = skills[CURRENT_SKILL]
    default = skills[default_id]
    deprecated_path = (root / "skills" / DEPRECATED_SKILL).resolve()
    if not deprecated_path.is_relative_to(root.resolve()) or not deprecated_path.is_dir():
        raise ValueError(f"missing deprecated skill directory: {deprecated_path}")
    deprecated_version = _deprecated_version(deprecated_path / "SKILL.md")
    return (
        Target(
            current.name,
            current.path,
            current.skill_version,
            current.tested_version,
            current.contract_file,
            current.name,
        ),
        Target(
            DEPRECATED_SKILL,
            deprecated_path,
            deprecated_version,
            default.tested_version,
            default.contract_file,
            default.name,
        ),
        Target(
            NO_SKILL_TARGET,
            None,
            None,
            default.tested_version,
            default.contract_file,
            default.name,
        ),
    )


def write_experiment(
    samples: int, root: Path = ROOT, jobs: int = DEFAULT_JOBS
) -> Path:
    _, skills = load_skills(root)
    targets = load_targets(root)
    scenario_ids = load_scenario_ids(root)
    cache = (root / CACHE).resolve()
    lines = [
        "schema_version = 1",
        'name = "iwe-v18-vs-controls-all-scenarios"',
        'agent_judge_config = "codex"',
        f"scenarios = {json.dumps(scenario_ids)}",
        f"samples = {samples}",
        f"jobs = {jobs}",
    ]
    for target in targets:
        runtime_spec = skills[target.runtime_skill_id]
        binary = verify_runtime_binary(runtime_spec)
        runtime = cache / "runtimes" / target.skill_id
        runtime.mkdir(parents=True, exist_ok=True)
        link = runtime / runtime_spec.runtime_cli
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(binary)
        lines.extend([
            "",
            "[[targets]]",
            f"id = {json.dumps(target.skill_id)}",
        ])
        if target.skill_path is None:
            lines.append('skill_mode = "none"')
        else:
            lines.extend([
                f"skill_path = {json.dumps(str(target.skill_path.relative_to(root)))}",
                f"skill_version = {json.dumps(target.skill_version)}",
            ])
        lines.extend([
            f"contract_file = {json.dumps(str(target.contract_file.relative_to(root)))}",
            "[targets.runtime]",
            f"cli = {json.dumps(runtime_spec.runtime_cli)}",
            'source = "directory"',
            f"version = {json.dumps(target.iwe_version)}",
            f"directory = {json.dumps(str(runtime.relative_to(root)))}",
        ])
    path = cache / "experiment.toml"
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def build_command(manifest: Path, results_file: Path, agent: str = "codex") -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tests/eval/run.py"),
        "--experiment",
        str(manifest),
        "--model-profile",
        "weak",
        "--markdown-report",
        str(results_file),
        "--agent",
        agent,
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = write_experiment(args.samples, jobs=args.jobs)
    return subprocess.call(build_command(manifest, args.results_file, args.agent), cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
