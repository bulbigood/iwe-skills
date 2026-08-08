"""Strict experiment manifest loading for paired IWE evaluations."""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


EVAL = Path(__file__).resolve().parent
EXACT_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


@dataclass(frozen=True)
class RuntimeTarget:
    cli: str
    source: str
    directory: Path | None
    version: str

    @property
    def runtime_cli(self) -> str:
        return self.cli

    @property
    def runtime_source(self) -> str:
        return self.source

    @property
    def runtime_directory(self) -> Path | None:
        return self.directory

    @property
    def tested_version(self) -> str:
        return self.version


@dataclass(frozen=True)
class EvalTarget:
    id: str
    skill_path: Path | None
    skill_version: str | None
    contract_file: Path
    runtime: RuntimeTarget
    agents_file: Path | None = None

    @property
    def has_skill(self) -> bool:
        return self.skill_path is not None

    @property
    def name(self) -> str:
        return self.skill_path.name if self.skill_path is not None else self.id

    @property
    def path(self) -> Path | None:
        return self.skill_path


@dataclass(frozen=True)
class Experiment:
    name: str
    scenario_ids: tuple[str, ...]
    samples: int
    jobs: int
    agent_judge_config: str
    comparison_metrics: tuple[str, ...] | None
    guidance_accounting: str
    worker_scheduling: str
    targets: tuple[EvalTarget, ...]


def _repo_path(root: Path, value: str, field: str, *, kind: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{field} escapes repository root: {value}")
    valid = path.is_dir() if kind == "directory" else path.is_file()
    if not valid:
        raise ValueError(f"{field} does not exist: {value}")
    return path


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid YAML frontmatter in {path}")
    value = yaml.safe_load(match.group(1))
    if not isinstance(value, dict):
        raise ValueError(f"invalid YAML frontmatter mapping in {path}")
    return value


def load_experiment(path: Path, root: Path) -> Experiment:
    root = root.resolve()
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid experiment TOML: {exc}") from exc
    schema = json.loads((EVAL / "experiment.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda e: list(e.path))
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.absolute_path)) or "<root>"
        raise ValueError(f"invalid experiment at {location}: {error.message}")
    ids = [item["id"] for item in document["targets"]]
    if len(ids) != len(set(ids)):
        raise ValueError("target ids must be unique")

    available_scenarios = {
        item["id"]
        for item in __import__("yaml").safe_load((EVAL / "scenarios/iwe.eval.yaml").read_text(encoding="utf-8"))["scenarios"]
    }
    unknown = set(document["scenarios"]) - available_scenarios
    if unknown:
        raise ValueError(f"unknown scenarios: {sorted(unknown)}")

    targets = []
    for raw in document["targets"]:
        has_skill = raw.get("skill_mode", "installed") == "installed"
        skill_path = (
            _repo_path(root, raw["skill_path"], "skill_path", kind="directory")
            if has_skill else None
        )
        contract_file = _repo_path(root, raw["contract_file"], "contract_file", kind="file")
        agents_file = (
            _repo_path(root, raw["agents_file"], "agents_file", kind="file")
            if raw.get("agents_file") is not None else None
        )
        declared = raw.get("skill_version")
        if skill_path is not None:
            frontmatter = _frontmatter(skill_path / "SKILL.md")
            if frontmatter.get("name") != skill_path.name:
                raise ValueError(
                    f"skill name {frontmatter.get('name')!r} does not match directory {skill_path.name!r}"
                )
            metadata = frontmatter.get("metadata")
            if not isinstance(metadata, dict):
                raise ValueError(f"missing skill metadata in {skill_path / 'SKILL.md'}")
            actual = metadata.get("version")
            if actual != declared:
                raise ValueError(f"skill_version {declared} does not match {actual}")
        runtime_raw = raw["runtime"]
        version = runtime_raw["version"]
        if not EXACT_VERSION.fullmatch(version):
            raise ValueError("runtime version must be exact x.y.z")
        contract = json.loads(contract_file.read_text(encoding="utf-8"))
        if contract.get("schema_version") != 1 or contract.get("cli_line") != ".".join(version.split(".")[:2]):
            raise ValueError(f"contract cli_line does not match runtime version {version}")
        if not isinstance(contract.get("commands"), dict) or not contract["commands"]:
            raise ValueError(f"contract commands must be a non-empty object: {contract_file}")
        directory = runtime_raw.get("directory")
        runtime_directory = None if directory is None else (root / directory).resolve()
        if runtime_directory is not None and not runtime_directory.is_relative_to(root):
            raise ValueError(f"runtime directory escapes repository root: {directory}")
        if runtime_raw["source"] != "directory":
            raise ValueError(
                f"target {raw['id']} must use directory runtime source for unambiguous multi-version evaluation"
            )
        targets.append(EvalTarget(
            raw["id"], skill_path, declared, contract_file,
            RuntimeTarget(runtime_raw["cli"], runtime_raw["source"], runtime_directory, version),
            agents_file,
        ))
    comparison_metrics = document.get("comparison_metrics")
    return Experiment(document["name"], tuple(document["scenarios"]), document["samples"],
                      document["jobs"], document["agent_judge_config"],
                      tuple(comparison_metrics) if comparison_metrics is not None else None,
                      document.get("guidance_accounting", "exclude_activation"),
                      document.get("worker_scheduling", "streaming"),
                      tuple(targets))
