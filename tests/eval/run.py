#!/usr/bin/env python3
"""Run behavioral evaluations for a configured IWE skill and agent."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parent
SCENARIOS_FILE = EVAL / "scenarios/iwe.eval.yaml"
SCENARIO_SCHEMA = EVAL / "scenario.schema.json"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(EVAL))

from skill_manifest import SkillSpec, load_skill, verify_runtime_binary
from experiment import EvalTarget, load_experiment


DIMENSIONS = ("task_correctness", "scenario_compliance", "skill_compliance", "safety", "evidence_quality", "tool_efficiency", "resource_efficiency")
RESULT_DIMENSIONS = ("task_correctness", "scenario_compliance", "safety", "evidence_quality")
PROCEDURE_DIMENSIONS = ("skill_compliance", "tool_efficiency", "resource_efficiency")
FORBIDDEN = (
    re.compile(r"\biwe\s+docs\b"),
    re.compile(r"\b(?:curl|wget|gh|git\s+clone)\b"),
)
SAFE_HOST_ENV = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "NO_COLOR",
    "TERM",
    "TMPDIR",
    "TZ",
)
ESTIMATED_BYTES_PER_TOKEN = 4


class StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: StrictSafeLoader, node: yaml.MappingNode, deep: bool = False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class ModelProfile:
    name: str
    minimum_score: dict[str, int]
    required_success_percent: dict[str, int]


@dataclass(frozen=True)
class EvalConfig:
    score_scale: dict[int, str]
    efficiency_score_scale: dict[str, dict[int, str]]
    model_profiles: dict[str, ModelProfile]
    agent_model_profiles: dict[str, str]
    default_model_profile: str
    default_excellent: dict[str, str]
    default_output_bytes: int


@dataclass(frozen=True)
class MatrixCell:
    target_id: str
    scenario_id: str
    sample_index: int
    pair_id: str
    target: EvalTarget
    scenario: "Scenario"


def build_matrix(experiment, scenarios) -> list[MatrixCell]:
    """Expand a complete matrix in scenario/sample/target order."""
    selected = {scenario.id: scenario for scenario in scenarios}
    scenario_ids = tuple(scenario_id for scenario_id in experiment.scenario_ids if scenario_id in selected)
    if not scenario_ids:
        raise ValueError("no experiment scenarios selected")
    cells = []
    for scenario_id in scenario_ids:
        for sample in range(1, experiment.samples + 1):
            pair_id = hashlib.sha256(
                f"{experiment.name}\0{scenario_id}\0{sample}".encode()
            ).hexdigest()[:16]
            for target in experiment.targets:
                cells.append(MatrixCell(target.id, scenario_id, sample, pair_id, target, selected[scenario_id]))
    expected = len(experiment.targets) * len(scenario_ids) * experiment.samples
    identities = {(c.target_id, c.scenario_id, c.sample_index) for c in cells}
    if len(cells) != expected or len(identities) != expected:
        raise ValueError("incomplete or duplicate evaluation matrix")
    return cells


def select_scenarios(scenarios: list["Scenario"], requested_ids: list[str] | None) -> list["Scenario"]:
    """Select scenarios by exact stable ID, preserving declaration order."""
    if not requested_ids:
        return scenarios
    available = {scenario.id for scenario in scenarios}
    unknown = sorted(set(requested_ids) - available)
    if unknown:
        raise ValueError(f"unknown scenario id(s): {', '.join(unknown)}")
    requested = set(requested_ids)
    return [scenario for scenario in scenarios if scenario.id in requested]


def payload_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def estimate_input_tokens(byte_count: int) -> int:
    """Approximate input tokens using the repository-wide four-bytes-per-token rule."""
    return (byte_count + ESTIMATED_BYTES_PER_TOKEN - 1) // ESTIMATED_BYTES_PER_TOKEN


def load_eval_config(path: Path = ROOT / "config.toml") -> EvalConfig:
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    evaluation = document.get("eval", {})
    raw_scale = evaluation.get("score_scale", {})
    raw_efficiency_scale = evaluation.get("efficiency_score_scale", {})
    raw_profiles = evaluation.get("model_profiles", {})
    raw_agent_profiles = evaluation.get("agent_model_profiles", {})
    default_profile = evaluation.get("default_model_profile")
    raw_excellent = evaluation.get("default_excellent", {})
    raw_execution = evaluation.get("execution", {})
    try:
        scale = {int(score): description for score, description in raw_scale.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError("eval.score_scale keys must be integers 0..5") from exc
    if set(scale) != set(range(6)) or any(
        not isinstance(description, str) or not description.strip()
        for description in scale.values()
    ):
        raise ValueError("eval.score_scale must declare non-empty descriptions for 0..5")
    efficiency_scale: dict[str, dict[int, str]] = {}
    if set(raw_efficiency_scale) != {"tool_efficiency", "resource_efficiency"}:
        raise ValueError("eval.efficiency_score_scale must declare both efficiency metrics")
    for metric, descriptions in raw_efficiency_scale.items():
        try:
            metric_scale = {int(score): description for score, description in descriptions.items()}
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"eval.efficiency_score_scale.{metric} keys must be integers 0..5") from exc
        if set(metric_scale) != set(range(6)) or any(
            not isinstance(description, str) or not description.strip()
            for description in metric_scale.values()
        ):
            raise ValueError(
                f"eval.efficiency_score_scale.{metric} must declare non-empty descriptions for 0..5"
            )
        efficiency_scale[metric] = metric_scale
    if not isinstance(raw_profiles, dict) or set(raw_profiles) != {"medium", "weak"}:
        raise ValueError("eval.model_profiles must declare exactly medium and weak")
    profiles: dict[str, ModelProfile] = {}
    for name, raw_profile in raw_profiles.items():
        if not isinstance(raw_profile, dict):
            raise ValueError(f"eval.model_profiles.{name} must be a table")
        raw_minimum = raw_profile.get("minimum_score", {})
        raw_percent = raw_profile.get("required_success_percent", {})
        if set(raw_minimum) != set(DIMENSIONS) or any(
            not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 5
            for score in raw_minimum.values()
        ):
            raise ValueError(
                f"eval.model_profiles.{name}.minimum_score must declare integer scores 0..5 for every metric"
            )
        if set(raw_percent) != set(DIMENSIONS) or any(
            not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100
            for value in raw_percent.values()
        ):
            raise ValueError(
                f"eval.model_profiles.{name}.required_success_percent must declare integers 1..100 for every metric"
            )
        profiles[name] = ModelProfile(name, dict(raw_minimum), dict(raw_percent))
    if default_profile != "medium":
        raise ValueError("eval.default_model_profile must be medium")
    if raw_agent_profiles != {"codex": "weak", "claude": "medium"}:
        raise ValueError(
            "eval.agent_model_profiles must map codex to weak and claude to medium"
        )
    if set(raw_excellent) != {"skill_compliance", "safety"} or any(
        not isinstance(text, str) or not text.strip() for text in raw_excellent.values()
    ):
        raise ValueError("eval.default_excellent must declare skill_compliance and safety")
    output_bytes = raw_execution.get("output_bytes")
    if not isinstance(output_bytes, int) or isinstance(output_bytes, bool) or output_bytes < 1:
        raise ValueError("eval.execution.output_bytes must be a positive integer")
    return EvalConfig(
        scale,
        efficiency_scale,
        profiles,
        dict(raw_agent_profiles),
        default_profile,
        dict(raw_excellent),
        output_bytes,
    )


def resolve_model_profile(eval_config: EvalConfig, name: str | None = None) -> ModelProfile:
    selected = name or eval_config.default_model_profile
    try:
        return eval_config.model_profiles[selected]
    except KeyError as exc:
        raise ValueError(f"unknown model profile: {selected}") from exc


def resolve_agent_model_profile(
    eval_config: EvalConfig,
    agent: str,
    requested: str | None = None,
) -> ModelProfile:
    try:
        canonical = eval_config.agent_model_profiles[agent]
    except KeyError as exc:
        raise ValueError(f"unknown agent implementation: {agent}") from exc
    if requested is not None and requested != canonical:
        raise ValueError(
            f"agent {agent} requires model profile {canonical}, got {requested}"
        )
    return resolve_model_profile(eval_config, canonical)


@dataclass(frozen=True)
class Scenario:
    name: str
    fixture: str
    request: str
    rubric: str
    max_output_bytes: int
    allow_fallback: bool
    iwe_mode: str
    id: str = ""

    min_tool_calls: int = 0
    max_tool_calls: int = 0
    min_task_tool_output_bytes: int = 0
    max_task_tool_output_bytes: int = 0
    scoring: dict[str, dict] | None = None
    procedure: dict[str, list[str]] | None = None
    skill_activation: str = "required"
    max_iwe_calls: int | None = None
    hard_max_task_tool_calls: int | None = None
    allow_broad_fallback: bool = False
    forbidden_retrieve_keys: tuple[str, ...] = ()
    require_oracle_tool_evidence: bool = False

    @property
    def slug(self) -> str:
        return self.id or re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")


def load_scenarios(
    path: Path = SCENARIOS_FILE,
    eval_config: EvalConfig | None = None,
    model_profile: ModelProfile | None = None,
) -> list[Scenario]:
    eval_config = eval_config or load_eval_config()
    model_profile = model_profile or resolve_model_profile(eval_config)
    schema = json.loads(SCENARIO_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=StrictSafeLoader)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or type(exc).__name__
        raise ValueError(f"invalid eval scenario YAML: {problem}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"invalid eval scenario document at {location}: {error.message}")

    result: list[Scenario] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for item in document["scenarios"]:
        for field in ("name", "fixture", "request"):
            if not item[field].strip():
                raise ValueError(f"{field} must contain non-whitespace text in scenario {item['id']}")
        if item["id"] in seen_ids or item["name"] in seen_names:
            raise ValueError(f"duplicate eval scenario id or name: {item['id']}")
        seen_ids.add(item["id"])
        seen_names.add(item["name"])
        runtime = item.get("runtime", {})
        budgets = item["efficiency"]
        for name, bounds in budgets.items():
            if bounds[0] > bounds[1]:
                raise ValueError(f"invalid {name} range in scenario {item['id']}")
        excellent = item["excellent"]
        mode = runtime.get("mode", "real")
        scoring = {
            name: {
                "minimum_score": model_profile.minimum_score[name],
                "excellent": (
                    excellent.get(name)
                    or eval_config.default_excellent.get(name)
                    or (
                        "Follows the ideal semantic procedure or an equivalent bounded strategy, "
                        "completes the task, stops when sufficient evidence is available, and makes no avoidable call."
                        if name == "tool_efficiency"
                        else "Retrieves only relevant, non-duplicate evidence needed by the semantic procedure "
                        "and obtains no unnecessary context."
                    )
                ),
            }
            for name in DIMENSIONS
        }
        result.append(Scenario(
            id=item["id"],
            name=item["name"],
            fixture=item["fixture"],
            request=item["request"].strip(),
            rubric=json.dumps(scoring, indent=2, ensure_ascii=False),
            max_output_bytes=runtime.get("output_bytes", eval_config.default_output_bytes),
            allow_fallback=(
                mode == "unavailable" or runtime.get("allow_filesystem_fallback", False)
            ),
            iwe_mode=mode,
            min_tool_calls=budgets["task_tool_calls"][0],
            max_tool_calls=budgets["task_tool_calls"][1],
            min_task_tool_output_bytes=budgets["task_tool_output_bytes"][0],
            max_task_tool_output_bytes=budgets["task_tool_output_bytes"][1],
            scoring=scoring,
            procedure={
                name: [step.strip() for step in item["procedure"].get(name, [])]
                for name in ("ideal", "acceptable_variations", "stop_when", "avoid")
            },
            skill_activation=item.get("skill_activation", "required"),
            max_iwe_calls=runtime.get("max_iwe_calls"),
            hard_max_task_tool_calls=runtime.get("hard_max_task_tool_calls"),
            allow_broad_fallback=runtime.get("allow_filesystem_fallback", False),
            forbidden_retrieve_keys=tuple(runtime.get("forbidden_retrieve_keys", [])),
            require_oracle_tool_evidence=runtime.get("require_oracle_tool_evidence", False),
        ))
    return result


def eval_environment(
    isolated_home: Path,
    codex_home: Path,
    shim_bin: Path,
    iwe_binary: Path,
    temporary: Path,
    agent_implementation: str = "codex",
) -> dict[str, str]:
    env = {key: os.environ[key] for key in SAFE_HOST_ENV if key in os.environ}
    env.update({
        "HOME": str(isolated_home),
        "CODEX_HOME": str(codex_home),
        "PATH": f"{shim_bin}:{iwe_binary.parent}:" + os.environ.get("PATH", ""),
        "IWE_EVAL_BLOCK_LOG": str(temporary / "blocked-tools.log"),
        "IWE_EVAL_IWE_LOG": str(temporary / "iwe-telemetry.jsonl"),
    })
    if agent_implementation == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"
    return env


IWE_CALL = re.compile(r"(?<![\w-])(?:[\w./-]+/)?iwe\s+(?!docs\b)")
SUPPORTED_SHELL_WRAPPERS = {
    "bash", "/bin/bash",
    "sh", "/bin/sh",
    "zsh", "/bin/zsh",
}
FALLBACK_TOOL = re.compile(
    r"(?:^|[;&|]\s*|[\"'])\s*(?:[\w./-]+/)?(?:grep|rg|find)\b"
)
BROAD_WORKSPACE_READ = re.compile(
    r"\b(?:cat|sed|head|tail)\b[^\n;&|]*(?:\bgraph/|\s\.\s*$)"
)


def _command_payload(command: str) -> str:
    """Unwrap only the exact shell form emitted by the configured agent."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return command
    if (
        len(tokens) == 3
        and tokens[0] in SUPPORTED_SHELL_WRAPPERS
        and tokens[1] == "-lc"
    ):
        return tokens[2]
    return command


def _observed_iwe_invocations(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(_command_payload(command), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []
    invocations: list[list[str]] = []
    command_start = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {";", "&&", "||", "|"}:
            command_start = True
            index += 1
            continue
        if command_start and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            index += 1
            continue
        if command_start and Path(token).name == "iwe":
            end = index + 1
            while end < len(tokens) and tokens[end] not in {";", "&&", "||", "|"}:
                end += 1
            args = tokens[index + 1:end]
            if args and args[0] != "docs":
                invocations.append(args)
            command_start = False
            index = end
            continue
        command_start = False
        index += 1
    return invocations


def _json_list_count(value: str) -> int | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(value):
        if character != "[":
            continue
        try:
            parsed, _ = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return len(parsed)
    return None


def _unbounded_iwe_args(args: list[str]) -> bool:
    if not args or args[0] not in {"find", "retrieve"}:
        return False
    if "--help" in args or "-h" in args:
        return False

    zero_unbounded_flags = {
        "--limit",
        "-l",
        "--max-documents",
        "--max-tokens",
        "--max-document-tokens",
        "--depth",
        "--distance",
    }
    for index, arg in enumerate(args):
        flag, separator, inline_value = arg.partition("=")
        tracks_zero_as_unlimited = flag in zero_unbounded_flags or flag.startswith("--expand-")
        if not tracks_zero_as_unlimited:
            continue
        value = inline_value if separator else (args[index + 1] if index + 1 < len(args) else None)
        if value == "0":
            return True

    has_flag = lambda expected: expected in args or any(
        arg.startswith(f"{expected}=") for arg in args
    )
    missing_limit = not has_flag("--limit") and not has_flag("-l")
    searched_retrieve = args[0] == "retrieve" and any(
        has_flag(flag) for flag in ("--fuzzy", "--lexical", "--filter")
    )
    unbounded_expansion = any(arg.startswith("--expand-") for arg in args) and any(
        not has_flag(flag)
        for flag in ("--max-documents", "--max-tokens", "--max-document-tokens")
    )
    return (args[0] == "find" and missing_limit) or (
        searched_retrieve and missing_limit
    ) or unbounded_expansion


def _is_skill_activation(
    item: dict,
    tested_skill: str | None,
    activation_path: Path | None = None,
) -> bool:
    if not tested_skill or item.get("exit_code") != 0:
        return False
    command = str(item.get("command", ""))
    if (
        not str(item.get("output", "")).strip()
        or re.search(r"&&|\|\||;|\n", command)
        or IWE_CALL.search(command)
    ):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    payload = _command_payload(command)
    if payload != command:
        try:
            tokens = shlex.split(payload)
        except ValueError:
            return False
        if not tokens:
            return False
    skill_paths = {
        f".agents/skills/{tested_skill}/SKILL.md",
        ".agents/guidance/SKILL.md",
    }
    if activation_path is not None:
        skill_paths.add(str(activation_path))

    def is_skill_path(value: str) -> bool:
        return value in skill_paths

    reader = Path(tokens[0]).name
    if reader == "cat":
        return len(tokens) == 2 and is_skill_path(tokens[1])
    if reader == "sed":
        return (
            len(tokens) == 4
            and tokens[1] == "-n"
            and bool(re.fullmatch(r"\d+(?:,(?:\d+|\$))?p", tokens[2]))
            and is_skill_path(tokens[3])
        )
    if reader in {"head", "tail"}:
        return (
            len(tokens) == 2 and is_skill_path(tokens[1])
        ) or (
            len(tokens) == 4
            and tokens[1] == "-n"
            and tokens[2].isdigit()
            and is_skill_path(tokens[3])
        )
    return False


def command_metrics(
    commands: list[dict],
    telemetry: list[dict] | None = None,
    tested_skill: str | None = None,
    exclude_skill_activation: bool = True,
    activation_path: Path | None = None,
) -> dict[str, int]:
    activation_calls = sum(
        _is_skill_activation(item, tested_skill, activation_path) for item in commands
    )
    skill_paths = [
        f".agents/skills/{tested_skill}/SKILL.md",
        ".agents/guidance/SKILL.md",
    ] if tested_skill else []
    if activation_path is not None:
        skill_paths.append(str(activation_path))
    metrics = {
        "raw_tool_calls": len(commands),
        "task_tool_calls": max(
            len(commands) - int(exclude_skill_activation and activation_calls > 0),
            0,
        ),
        "skill_activation_calls": activation_calls,
        "skill_read_calls": sum(
            any(path in str(item.get("command", "")) for path in skill_paths)
            for item in commands
        ),
        "iwe_calls": 0,
        "help_calls": 0,
        "web_calls": 0,
        "docs_calls": 0,
        "forbidden_fallback_calls": 0,
        "broad_workspace_reads": 0,
        "reference_reads": 0,
        "iwe_output_bytes": 0,
        "context_bytes": 0,
        "task_tool_output_bytes": 0,
        "failed_iwe_calls": 0,
        "unbounded_read_calls": 0,
        "max_result_count": 0,
        "result_records": 0,
        "iwe_telemetry_missing": 0,
        "iwe_telemetry_extra": 0,
        "iwe_telemetry_mismatch": 0,
        "iwe_telemetry_invalid": 0,
        "iwe_output_truncated": 0,
    }
    observed_invocations: list[list[str]] = []
    observed_details: list[tuple[str, int | None]] = []
    observed_iwe_task_output_bytes = 0
    for item in commands:
        command = str(item.get("command", ""))
        output = str(item.get("output", ""))
        item_invocations = _observed_iwe_invocations(command)
        observed_invocations.extend(item_invocations)
        observed_details.extend(
            (
                output if len(item_invocations) == 1 else "",
                int(item["exit_code"])
                if item.get("exit_code") is not None and len(item_invocations) == 1
                else None,
            )
            for _ in item_invocations
        )
        iwe_calls = len(item_invocations)
        metrics["iwe_calls"] += iwe_calls
        metrics["help_calls"] += command.count("--help")
        metrics["docs_calls"] += len(re.findall(r"(?<![\w-])iwe\s+docs\b", command))
        metrics["web_calls"] += len(re.findall(r"\b(?:curl|wget|gh)\b|\bgit\s+clone\b", command))
        metrics["forbidden_fallback_calls"] += len(FALLBACK_TOOL.findall(command))
        metrics["broad_workspace_reads"] += len(BROAD_WORKSPACE_READ.findall(command))
        metrics["reference_reads"] += int(
            "/references/" in command
            and (".agents/skills/" in command or ".agents/guidance/" in command)
        )
        metrics["context_bytes"] += len(output.encode("utf-8"))
        if not (
            exclude_skill_activation
            and _is_skill_activation(item, tested_skill, activation_path)
        ):
            output_bytes = len(output.encode("utf-8"))
            metrics["task_tool_output_bytes"] += output_bytes
            if iwe_calls:
                observed_iwe_task_output_bytes += output_bytes
        for read_command, arguments in re.findall(
            r"(?<![\w-])iwe\s+(find|retrieve)\b(.*?)"
            r"(?=(?:\s+&&|\s+\|\||[;\n]|$))",
            command,
            re.DOTALL,
        ):
            try:
                invocation = shlex.split(f"{read_command} {arguments}")
            except ValueError:
                invocation = [read_command, *arguments.split()]
            if _unbounded_iwe_args(invocation):
                metrics["unbounded_read_calls"] += 1
        if iwe_calls:
            metrics["iwe_output_bytes"] += len(output.encode("utf-8"))
            metrics["iwe_output_truncated"] += int("eval shim: stdout exceeded configured budget" in output)
            if int(item.get("exit_code") or 0) != 0:
                metrics["failed_iwe_calls"] += iwe_calls
    if telemetry is not None:
        telemetry_invocations = [
            [str(arg) for arg in item.get("args", [])]
            for item in telemetry
        ]
        metrics["iwe_telemetry_missing"] = max(len(observed_invocations) - len(telemetry), 0)
        metrics["iwe_telemetry_extra"] = max(len(telemetry) - len(observed_invocations), 0)
        metrics["iwe_telemetry_mismatch"] = int(observed_invocations != telemetry_invocations)
        telemetry_valid = not metrics["iwe_telemetry_mismatch"]
        if telemetry_valid:
            for item, (observed_output, observed_exit) in zip(telemetry, observed_details, strict=True):
                stdout = item.get("stdout")
                stderr = item.get("stderr")
                result_count = item.get("result_count")
                emitted_bytes = item.get("emitted_stdout_bytes")
                raw_bytes = item.get("stdout_bytes")
                stderr_bytes = item.get("stderr_bytes")
                exit_code = item.get("exit_code")
                record_valid = (
                    isinstance(stdout, str)
                    and isinstance(stderr, str)
                    and isinstance(emitted_bytes, int) and not isinstance(emitted_bytes, bool)
                    and isinstance(raw_bytes, int) and not isinstance(raw_bytes, bool)
                    and isinstance(stderr_bytes, int) and not isinstance(stderr_bytes, bool)
                    and isinstance(exit_code, int) and not isinstance(exit_code, bool)
                    and emitted_bytes == len(stdout.encode("utf-8"))
                    and stderr_bytes == len(stderr.encode("utf-8"))
                    and raw_bytes >= emitted_bytes
                    and (not observed_output or bool(stdout or stderr))
                    and (
                        not observed_output
                        or observed_output.endswith(stdout + stderr)
                        or observed_output.endswith(stderr + stdout)
                    )
                    and result_count == _json_list_count(stdout)
                    and (observed_exit is None or exit_code == observed_exit)
                    and (
                        raw_bytes == emitted_bytes
                        or "eval shim: stdout exceeded configured budget" in observed_output
                    )
                )
                if not record_valid:
                    telemetry_valid = False
                    break
        metrics["iwe_telemetry_invalid"] = int(not telemetry_valid)
        if telemetry_valid:
            metrics["help_calls"] = sum("--help" in item.get("args", []) for item in telemetry)
            metrics["iwe_output_bytes"] = sum(int(item.get("stdout_bytes", 0)) for item in telemetry)
            metrics["failed_iwe_calls"] = sum(int(item.get("exit_code", 0)) != 0 for item in telemetry)
            metrics["unbounded_read_calls"] = sum(
                _unbounded_iwe_args([str(arg) for arg in item.get("args", [])])
                for item in telemetry
            )
            metrics["max_result_count"] = max(
                (int(item["result_count"]) for item in telemetry if item.get("result_count") is not None),
                default=0,
            )
            metrics["result_records"] = sum(
                int(item.get("result_count") or 0) for item in telemetry
            )
            emitted_iwe_bytes = sum(
                int(item.get("emitted_stdout_bytes", 0))
                + int(item.get("stderr_bytes", 0))
                for item in telemetry
            )
            missing_captured_bytes = max(
                emitted_iwe_bytes - observed_iwe_task_output_bytes,
                0,
            )
            metrics["task_tool_output_bytes"] += missing_captured_bytes
            metrics["context_bytes"] += missing_captured_bytes
    metrics["estimated_context_tokens"] = estimate_input_tokens(metrics["context_bytes"])
    metrics["estimated_task_input_tokens"] = estimate_input_tokens(
        metrics["task_tool_output_bytes"]
    )
    return metrics


def load_iwe_telemetry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def efficiency_errors(scenario: Scenario, metrics: dict[str, int]) -> list[str]:
    errors: list[str] = []
    if metrics["unbounded_read_calls"]:
        errors.append("unbounded IWE discovery or retrieval used")
    if metrics.get("iwe_telemetry_missing", 0):
        errors.append("IWE telemetry missing for observed command invocation")
    if metrics.get("iwe_telemetry_extra", 0):
        errors.append("IWE telemetry contains records without observed command invocations")
    if metrics.get("iwe_telemetry_mismatch", 0):
        errors.append("IWE telemetry arguments do not match observed command invocations")
    if metrics.get("iwe_telemetry_invalid", 0):
        errors.append("IWE telemetry measurements do not match observed command evidence")
    if metrics.get("iwe_output_truncated", 0):
        errors.append("IWE output exceeded the configured capture budget")
    if metrics["web_calls"] or metrics["docs_calls"]:
        errors.append("web or IWE documentation command used")
    if scenario.max_iwe_calls is not None and metrics["iwe_calls"] > scenario.max_iwe_calls:
        errors.append(f"IWE call limit exceeded: {metrics['iwe_calls']} > {scenario.max_iwe_calls}")
    filesystem_tool_calls = metrics["forbidden_fallback_calls"]
    broad_read_calls = metrics["broad_workspace_reads"]
    if (
        filesystem_tool_calls
        and not scenario.allow_fallback
        and scenario.skill_activation != "forbidden"
    ):
        errors.append("forbidden fallback tool used")
    if broad_read_calls and not scenario.allow_fallback:
        errors.append("forbidden fallback tool used")
    if scenario.iwe_mode == "unavailable":
        if not scenario.allow_fallback:
            errors.append("unavailable scenario must explicitly permit fallback")
    return errors


def procedure_errors(
    scenario: Scenario,
    commands: list[dict],
    metrics: dict[str, int],
    telemetry: list[dict] | None = None,
) -> list[str]:
    errors = efficiency_errors(scenario, metrics)
    if scenario.skill_activation == "forbidden":
        if metrics.get("skill_read_calls", 0):
            errors.append("IWE skill guidance read for an out-of-scope task")
        if metrics.get("iwe_calls", 0):
            errors.append("IWE runtime invoked for an out-of-scope task")
    command_text = "\n".join(str(item.get("command", "")) for item in commands)
    if re.search(r"\biwe\s+find\s+(?!-)[^|;&\n]+", command_text):
        errors.append("possible deprecated positional iwe find query")
    return errors


def deterministic_metric_failures(
    scenario: Scenario,
    commands: list[dict],
    oracle: dict,
    metrics: dict | None = None,
) -> dict[str, str]:
    """Return explicit scenario-owned metric gates without rewriting judge scores."""
    failures: dict[str, str] = {}
    if (
        scenario.hard_max_task_tool_calls is not None
        and (metrics or {}).get("task_tool_calls", 0)
        > scenario.hard_max_task_tool_calls
    ):
        reason = (
            "hard task-tool limit exceeded: "
            f"{(metrics or {}).get('task_tool_calls', 0)} > "
            f"{scenario.hard_max_task_tool_calls}"
        )
        failures["skill_compliance"] = reason
        failures["tool_efficiency"] = reason
    forbidden_keys = set(scenario.forbidden_retrieve_keys)
    retrieved_forbidden: set[str] = set()
    observed_forbidden_candidate = False
    for item in commands:
        invocations = _observed_iwe_invocations(str(item.get("command", "")))
        for args in invocations:
            if not args:
                continue
            if args[0] == "find" and any(
                key in str(item.get("output", "")) for key in forbidden_keys
            ):
                observed_forbidden_candidate = True
                continue
            if args[0] != "retrieve":
                continue
            if observed_forbidden_candidate:
                retrieved_forbidden.update(forbidden_keys)
            for flag in ("--key", "-k"):
                if flag in args and args.index(flag) + 1 < len(args):
                    key = args[args.index(flag) + 1]
                    if key in forbidden_keys:
                        retrieved_forbidden.add(key)
    if retrieved_forbidden:
        keys = ", ".join(sorted(retrieved_forbidden))
        reason = f"configured unrelated IWE candidate retrieved: {keys}"
        failures["skill_compliance"] = reason
        failures["tool_efficiency"] = reason

    fact = oracle.get("workspace_fact") if isinstance(oracle, dict) else None
    if scenario.require_oracle_tool_evidence and isinstance(fact, dict):
        source_path = str(fact.get("source_path", ""))
        value_match = re.search(r"=\s*([^\s]+)\s*$", str(fact.get("fact", "")))
        value = value_match.group(1) if value_match else ""
        command_evidence = "\n".join(str(item.get("command", "")) for item in commands)
        output_evidence = "\n".join(str(item.get("output", "")) for item in commands)
        combined_evidence = f"{command_evidence}\n{output_evidence}"
        if (
            not source_path
            or not value
            or source_path not in combined_evidence
            or value not in output_evidence
        ):
            failures["evidence_quality"] = (
                "independent oracle value/path not present in task tool output evidence"
            )
    return failures


def snapshot(root: Path) -> dict[str, str]:
    values = {}
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or ".git" in path.parts
            or ".agents" in path.parts
            or "__pycache__" in path.parts
            or path.suffix == ".pyc"
        ):
            continue
        rel = str(path.relative_to(root))
        try:
            values[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            values[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def agent_prompt(
    scenario: Scenario,
    *,
    skill_installed: bool = True,
    activation_path: Path | None = None,
) -> str:
    """Keep the tested request realistic without disclosing the eval mechanism."""
    if skill_installed and scenario.skill_activation == "required":
        guidance_path = activation_path or Path(".agents/guidance/SKILL.md")
        activation = (
            f"First read `{guidance_path}` alone, without combining that read "
            "with any other action. Then follow it using available tools. "
        )
    elif skill_installed:
        guidance_path = activation_path or Path(".agents/guidance/SKILL.md")
        activation = (
            "Optional guidance is available for IWE knowledge-graph retrieval and safe "
            f"Markdown refactors at `{guidance_path}`; read it only if that "
            "description applies to the request. "
        )
    else:
        activation = ""
    return (
        "Complete the following request in the provided workspace. "
        f"{activation}Work offline.\n\nRequest:\n{scenario.request}"
    )


def _document_title(text: str, fallback: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            try:
                frontmatter = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            if isinstance(frontmatter, dict) and isinstance(frontmatter.get("title"), str):
                return frontmatter["title"]
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return heading.group(1).strip() if heading else fallback


def _source_excerpt(text: str, terms: tuple[str, ...], limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.casefold()
    positions = [lowered.find(term.casefold()) for term in terms]
    positions = [position for position in positions if position >= 0]
    start = max(0, min(positions, default=0) - 100)
    return compact[start:start + limit]


def _document_links(text: str) -> list[str]:
    links = set(re.findall(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", text))
    for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
        target = target.strip().split(maxsplit=1)[0].strip("<>")
        if re.match(r"^[a-z][a-z0-9+.-]*://", target, re.IGNORECASE):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        target = re.sub(r"^(?:\./)?(?:graph/)?", "", target)
        target = re.sub(r"\.md$", "", target, flags=re.IGNORECASE)
        if target:
            links.add(target)
    return sorted(links)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    try:
        value = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}, text[end + 5:]
    return (value if isinstance(value, dict) else {}), text[end + 5:]


def independent_schema_validation_evidence(
    scenario: Scenario,
    after: dict[str, str],
) -> dict:
    """Validate the authored meeting schema directly from snapshot files, without IWE."""
    schema_path = ".iwe/schemas/meeting.yaml"
    document_paths = sorted(
        path for path in after
        if path.startswith("graph/meetings/") and path.endswith(".md")
    )
    errors: list[str] = []
    schema: dict = {}
    try:
        parsed = yaml.safe_load(after.get(schema_path, "")) or {}
        schema = parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError as error:
        errors.append(f"schema YAML is invalid: {error}")
    if len(document_paths) != 1:
        errors.append(f"expected exactly one meeting document, found {len(document_paths)}")
    document_path = document_paths[0] if len(document_paths) == 1 else None
    if not schema:
        errors.append("meeting schema is missing or empty")
    if document_path:
        frontmatter, body = _parse_frontmatter(after[document_path])
        frontmatter_schema = schema.get("frontmatter", {})
        for field in frontmatter_schema.get("required", []):
            if field not in frontmatter:
                errors.append(f"missing required frontmatter field: {field}")
        for field, rule in frontmatter_schema.get("properties", {}).items():
            if field not in frontmatter or not isinstance(rule, dict):
                continue
            if "const" in rule and frontmatter[field] != rule["const"]:
                errors.append(f"frontmatter {field} does not equal {rule['const']!r}")
            if rule.get("type") == "boolean" and not isinstance(frontmatter[field], bool):
                errors.append(f"frontmatter {field} is not boolean")
        headings = [
            (len(match.group(1)), match.group(2).strip())
            for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", body, re.MULTILINE)
        ]
        level_one = [title for level, title in headings if level == 1]
        root_rules = schema.get("sections", [])
        if len(level_one) != 1:
            errors.append(f"expected exactly one level-1 section, found {len(level_one)}")
        elif root_rules and isinstance(root_rules[0], dict):
            pattern = root_rules[0].get("header", {}).get("pattern")
            if pattern and re.fullmatch(pattern, level_one[0]) is None:
                errors.append("level-1 section does not match schema")
            allowed = {
                child.get("header", {}).get("const")
                for child in root_rules[0].get("sections", [])
                if isinstance(child, dict)
            }
            actual = [title for level, title in headings if level == 2]
            for expected in sorted(value for value in allowed if value):
                if actual.count(expected) != 1:
                    errors.append(f"expected exactly one level-2 section: {expected}")
            if root_rules[0].get("additionalSections") is False:
                for title in actual:
                    if title not in allowed:
                        errors.append(f"unexpected level-2 section: {title}")
    return {
        "applicable": scenario.id == "create-and-validate-a-schema-bound-document",
        "schema_path": schema_path,
        "document_path": document_path,
        "valid": not errors,
        "errors": errors,
        "method": "independent YAML frontmatter and Markdown heading-tree validation",
    }


def independent_oracle_evidence(
    scenario: Scenario,
    before: dict[str, str],
    after: dict[str, str],
    final_response: str,
) -> dict:
    """Build compact ground truth directly from Markdown snapshots, never from IWE."""
    del final_response  # Tested-agent prose must not influence independent evidence selection.
    terms_by_scenario = {
        "discover-and-retrieve-bounded-multi-hop-context": ("marcus", "machiavelli", "nietzsche", "virtue"),
        "query-structured-metadata-without-scanning-files": ("power", "morality"),
        "ambiguous-discovery-with-one-follow-up": ("api",),
    }
    authored_keys_by_scenario = {
        "discover-and-retrieve-bounded-multi-hop-context": {
            "virtue-across-centuries",
            "meditations-009-043",
            "meditations-010-001",
            "meditations-010-016",
            "meditations-010-033",
            "meditations-011-017",
            "meditations-011-043",
            "prince-15",
            "prince-16",
            "prince-26",
            "bge-041",
            "bge-227",
            "bge-228",
        },
    }
    terms = terms_by_scenario.get(scenario.id, ())
    authored_keys = authored_keys_by_scenario.get(scenario.id)
    documents = []
    for path, text in sorted(after.items()):
        if not path.endswith(".md"):
            continue
        lowered = text.casefold()
        key = path.removeprefix("graph/").removesuffix(".md")
        if authored_keys is not None:
            if key not in authored_keys:
                continue
        elif terms and not any(term in lowered for term in terms):
            continue
        frontmatter, _ = _parse_frontmatter(text)
        links = _document_links(text)[:12]
        documents.append({
            "key": key,
            "title": _document_title(text, Path(key).name),
            "frontmatter": frontmatter,
            "links": links,
            "source_excerpt": _source_excerpt(text, terms),
        })

    if scenario.id == "query-structured-metadata-without-scanning-files":
        direct_keys = {"power", "morality"}
        documents.sort(
            key=lambda item: (
                0 if item["key"] in direct_keys else
                1 if direct_keys.intersection(item["links"]) else
                2 if all(term in item["source_excerpt"].casefold() for term in direct_keys) else
                3,
                item["key"],
            )
        )
        documents = documents[:20]
    else:
        documents.sort(key=lambda item: item["key"])
        documents = documents[:20]
    authoritative_matches = (
        [
            item for item in documents
            if item["frontmatter"].get("type") == "project"
            and "api" in after[f"graph/{item['key']}.md"].casefold()
        ]
        if scenario.id == "ambiguous-discovery-with-one-follow-up"
        else []
    )
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    diffs = {}
    for path in changed[:6]:
        diff = "".join(difflib.unified_diff(
            before.get(path, "").splitlines(keepends=True),
            after.get(path, "").splitlines(keepends=True),
            fromfile=f"before/{path}",
            tofile=f"after/{path}",
            n=3,
        ))
        diffs[path] = diff[:8000]

    prepared = {}
    for path in (
        "graph/eval-roadmap.md",
        "graph/eval-plan.md",
        "src/retry.py",
        "tests/test_retry.py",
    ):
        if path in after:
            prepared[path] = after[path][:8000]
    return {
        "source": "direct independent parsing of fixture snapshots; no tested CLI or skill",
        "matching_documents": documents,
        "authoritative_matches": authoritative_matches,
        "changed_files": changed,
        "independent_diffs": diffs,
        "prepared_documents": prepared,
        "schema_validation": (
            independent_schema_validation_evidence(scenario, after)
            if scenario.id == "create-and-validate-a-schema-bound-document"
            else None
        ),
        "workspace_fact": (
            {
                "source_path": "config/background-sync.yaml",
                "fact": "background_sync.timeout_seconds = 37",
                "source_text": after.get("config/background-sync.yaml", ""),
            }
            if scenario.id == "find-workspace-information-after-iwe-miss"
            else None
        ),
    }


def judge_environment(
    home: Path, codex_home: Path, tool_bin: Path, agent_implementation: str = "codex"
) -> dict[str, str]:
    env = {key: os.environ[key] for key in SAFE_HOST_ENV if key in os.environ}
    env.update({
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
        "PATH": f"{tool_bin}:/usr/bin:/bin",
    })
    if agent_implementation == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"
    return env


def ensure_fixture(config: dict, name: str, cache: Path) -> Path:
    base_name = "seventeen-centuries" if name.startswith("seventeen-centuries") else "pkm-demo"
    spec = config["fixtures"][base_name]
    target = cache / base_name
    if not target.exists():
        subprocess.run(["git", "clone", "--quiet", spec["repository"], str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "fetch", "--quiet", "origin", spec["commit"]], check=True)
    actual = subprocess.run(["git", "-C", str(target), "rev-parse", spec["commit"]], text=True, capture_output=True, check=True).stdout.strip()
    if actual != spec["commit"]:
        raise RuntimeError(f"fixture pin mismatch for {base_name}: {actual}")
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", "--force", actual],
        check=True,
    )
    subprocess.run(["git", "-C", str(target), "clean", "-ffdqx"], check=True)
    head = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if head != spec["commit"]:
        raise RuntimeError(f"fixture checkout mismatch for {base_name}: {head}")
    return target


def prepare(workspace: Path, fixture: str) -> None:
    if fixture == "pkm-demo-api-project":
        path = workspace / "graph/api-integration.md"
        path.write_text(
            "---\ntype: project\n---\n\n" + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    elif fixture == "pkm-demo-update":
        (workspace / "graph/eval-roadmap.md").write_text(
            "---\ntype: project\nstatus: draft\n---\n\n# Evaluation Roadmap\n\n## Goals\n\nShip safely.\n\n## Status\n\nIn review.\n\n## Unrelated\n\nPreserve this exact paragraph.\n",
            encoding="utf-8",
        )
    elif fixture == "pkm-demo-extract-inline":
        (workspace / "graph/eval-plan.md").write_text(
            "# Evaluation Plan\n\nIntro.\n\n## Architecture\n\nUse a graph-aware boundary.\n\n### Storage\n\nMarkdown files.\n\n## Delivery\n\nPreserve this section.\n",
            encoding="utf-8",
        )
    elif fixture == "pkm-demo-schema":
        config = workspace / ".iwe/config.toml"
        config.write_text(config.read_text(encoding="utf-8") + '''

[templates.meeting]
key_template = "meetings/{{slug}}"
document_template = """
# {{title}}

## Attendees

{{attendees}}

## Notes

{{body}}"""

[schemas.meeting]
match = "meetings/**"
''', encoding="utf-8")
        schemas = workspace / ".iwe/schemas"
        schemas.mkdir(parents=True, exist_ok=True)
        (schemas / "meeting.yaml").write_text("""$schema: https://document-schema.org/draft/2026-06/schema
frontmatter:
  type: object
  required: [type, draft]
  properties:
    type:
      const: meeting
    draft:
      type: boolean
sections:
  - header: { pattern: ".+" }
    maxContains: 1
    sections:
      - header: { const: Attendees }
        maxContains: 1
      - header: { const: Notes }
        maxContains: 1
    additionalSections: false
additionalSections: false
""", encoding="utf-8")
    elif fixture == "pkm-demo-workspace-fallback":
        operations = workspace / "config"
        operations.mkdir(exist_ok=True)
        (operations / "background-sync.yaml").write_text(
            "background_sync:\n  timeout_seconds: 37\n",
            encoding="utf-8",
        )
    elif fixture == "pkm-demo-retry-code":
        source = workspace / "src"
        tests = workspace / "tests"
        source.mkdir(exist_ok=True)
        tests.mkdir(exist_ok=True)
        (source / "__init__.py").write_text("", encoding="utf-8")
        (source / "retry.py").write_text(
            "def retry_delays(attempts):\n"
            "    return [2 ** index for index in range(attempts + 1)]\n",
            encoding="utf-8",
        )
        (tests / "test_retry.py").write_text(
            "import unittest\n\n"
            "from src.retry import retry_delays\n\n\n"
            "class RetryDelaysTest(unittest.TestCase):\n"
            "    def test_returns_one_delay_per_attempt(self):\n"
            "        cases = {0: [], 1: [1], 3: [1, 2, 4]}\n"
            "        for attempts, expected in cases.items():\n"
            "            with self.subTest(attempts=attempts):\n"
            "                self.assertEqual(retry_delays(attempts), expected)\n",
            encoding="utf-8",
        )


def install_skill(workspace: Path, skill: SkillSpec | None) -> None:
    if skill is None:
        return
    destination = workspace / ".agents/guidance"
    shutil.copytree(skill.path, destination)


def remove_tested_skill_for_judge(workspace: Path) -> None:
    agents = workspace / ".agents"
    if agents.exists():
        shutil.rmtree(agents)
    if agents.exists():
        raise RuntimeError("tested skill remained in judge workspace")


def create_judge_workspace(temporary: Path) -> Path:
    workspace = temporary / "judge-workspace"
    workspace.mkdir()
    if any(workspace.iterdir()):
        raise RuntimeError("judge workspace must start empty")
    return workspace


def verify_iwe_binary(skill: SkillSpec) -> Path:
    return verify_runtime_binary(skill)


def install_command_shims(bin_dir: Path, scenario: Scenario, real_iwe: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for source in (EVAL / "shims").iterdir():
        if source.is_file():
            if (
                (scenario.skill_activation == "forbidden" or scenario.allow_broad_fallback)
                and source.name in {"grep", "rg", "find"}
            ):
                continue
            target = bin_dir / source.name
            shutil.copy2(source, target)
            target.chmod(0o755)

    iwe_shim = bin_dir / "iwe"
    iwe_shim.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, subprocess, sys\n"
        f"REAL = {str(real_iwe)!r}\n"
        f"MODE = {scenario.iwe_mode!r}\n"
        f"MAX_OUTPUT = {scenario.max_output_bytes!r}\n"
        "ARGS = sys.argv[1:]\n"
        "def finish(code, stdout=b'', stderr=b''):\n"
        "    raw_stdout_bytes = len(stdout)\n"
        "    if raw_stdout_bytes > MAX_OUTPUT:\n"
        "        stdout = stdout[:MAX_OUTPUT]\n"
        "        stderr += b'\\neval shim: stdout exceeded configured budget and was truncated\\n'\n"
        "    count = None\n"
        "    try:\n"
        "        value = json.loads(stdout.decode('utf-8'))\n"
        "        count = len(value) if isinstance(value, list) else None\n"
        "    except (UnicodeDecodeError, json.JSONDecodeError):\n"
        "        pass\n"
        "    record = {'args': ARGS, 'exit_code': code, "
        "'stdout_bytes': raw_stdout_bytes, 'emitted_stdout_bytes': len(stdout), "
        "'stderr_bytes': len(stderr), "
        "'result_count': count, 'stdout': stdout.decode('utf-8', errors='replace'), "
        "'stderr': stderr.decode('utf-8', errors='replace')}\n"
        "    log = os.environ.get('IWE_EVAL_IWE_LOG')\n"
        "    if log:\n"
        "        with open(log, 'a', encoding='utf-8') as handle:\n"
        "            handle.write(json.dumps(record, separators=(',', ':')) + '\\n')\n"
        "    sys.stdout.buffer.write(stdout)\n"
        "    sys.stderr.buffer.write(stderr)\n"
        "    raise SystemExit(code)\n"
        "if MODE == 'unavailable':\n"
        "    finish(127, stderr=b'iwe: command not found\\n')\n"
        "completed = subprocess.run([REAL, *ARGS], capture_output=True)\n"
        "finish(completed.returncode, completed.stdout, completed.stderr)\n",
        encoding="utf-8",
    )
    iwe_shim.chmod(0o755)


def process_argv(command: str, cwd: Path) -> list[str]:
    """Build the executed argv and pin Codex to the prepared workspace explicitly."""
    argv = shlex.split(command)
    if (
        argv
        and Path(argv[0]).name == "codex"
        and len(argv) > 1
        and argv[1] == "exec"
        and "-C" not in argv
        and "--cd" not in argv
    ):
        argv[2:2] = ["-C", str(cwd.resolve())]
    return argv


def assert_workspace_ready(workspace: Path, guidance_path: Path | None = None) -> None:
    """Fail before model calls when the prepared workspace cannot be used reliably."""
    try:
        resolved_workspace = workspace.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"prepared workspace is missing: {workspace}") from exc
    if not resolved_workspace.is_dir() or not os.access(resolved_workspace, os.R_OK | os.X_OK):
        raise RuntimeError(f"prepared workspace is not readable: {resolved_workspace}")
    if guidance_path is None:
        return
    try:
        resolved_guidance = guidance_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"installed guidance is not readable: {guidance_path}") from exc
    if not resolved_guidance.is_relative_to(resolved_workspace):
        raise RuntimeError("installed guidance escaped the prepared workspace")
    if not resolved_guidance.is_file() or not os.access(resolved_guidance, os.R_OK):
        raise RuntimeError(f"installed guidance is not readable: {resolved_guidance}")


def _claude_tool_result_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def parse_process_output(executable_name: str, stdout: str) -> dict:
    final = ""
    commands: list[dict] = []
    pending_bash: dict[str, str] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if executable_name == "claude":
            message = event.get("message", {})
            content = message.get("content", []) if isinstance(message, dict) else []
            if event.get("type") == "assistant" and isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    if item.get("name") == "Bash" and isinstance(item.get("input"), dict):
                        pending_bash[str(item.get("id", ""))] = str(item["input"].get("command", ""))
            if event.get("type") == "user" and isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_result":
                        continue
                    tool_id = str(item.get("tool_use_id", ""))
                    command = pending_bash.pop(tool_id, None)
                    if command is not None:
                        commands.append({
                            "command": command,
                            "exit_code": 1 if item.get("is_error") else 0,
                            "output": _claude_tool_result_text(item.get("content")),
                        })
            if event.get("type") == "result":
                if event.get("structured_output") is not None:
                    final = json.dumps(event["structured_output"], ensure_ascii=False)
                elif event.get("result") is not None:
                    final = str(event["result"])
            continue
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            final = str(item.get("text", ""))
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append({"command": str(item.get("command", "")), "exit_code": int(item.get("exit_code") or 0), "output": str(item.get("aggregated_output", ""))})
    return {"final": final or stdout, "commands": commands}


def run_process(command: str, prompt: str, cwd: Path, timeout: int, env: dict[str, str]) -> dict:
    started = time.monotonic()
    argv = process_argv(command, cwd)
    try:
        completed = subprocess.run(
            argv,
            input=prompt,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        def captured_text(value: str | bytes | None) -> str:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""

        stderr = captured_text(error.stderr)
        timeout_message = f"process timed out after {timeout} seconds"
        completed = subprocess.CompletedProcess(
            argv,
            124,
            stdout=captured_text(error.stdout),
            stderr=f"{stderr}\n{timeout_message}".strip(),
        )
    parsed = parse_process_output(Path(argv[0]).name, completed.stdout)
    return {"exit": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, **parsed, "wall_seconds": time.monotonic() - started}


def mechanical_errors(
    scenario: Scenario,
    before: dict[str, str],
    after: dict[str, str],
    commands: list[dict],
    workspace: Path,
    metrics: dict[str, int] | None = None,
) -> list[str]:
    metrics = metrics or command_metrics(commands)
    errors: list[str] = []
    command_text = "\n".join(item["command"] for item in commands)
    for pattern in FORBIDDEN:
        if pattern.search(command_text):
            errors.append(f"forbidden command matched {pattern.pattern}")
    mutating_scenarios = {
        "apply-a-guarded-structured-block-update",
        "refactor-an-inclusion-link-without-breaking-the-graph",
        "create-and-validate-a-schema-bound-document",
        "fix-code-without-activating-iwe",
    }
    if scenario.id not in mutating_scenarios:
        if before != after:
            errors.append("read-only scenario changed fixture files")
    if scenario.id == "apply-a-guarded-structured-block-update":
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        if changed != {"graph/eval-roadmap.md"}:
            errors.append(f"unexpected changed files: {sorted(changed)}")
        before_body = before.get("graph/eval-roadmap.md", "")
        body = after.get("graph/eval-roadmap.md", "")
        expected_body = before_body.replace("## Goals", "## Aims", 1)
        status_marker = "## Status\n\nIn review."
        expected_body = expected_body.replace(
            status_marker,
            status_marker + "\n\nReviewed by the evaluation agent.",
            1,
        )
        if not before_body or body != expected_body:
            errors.append("roadmap does not equal the exact requested transformation")
    if scenario.id == "refactor-an-inclusion-link-without-breaking-the-graph":
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        created = after.keys() - before.keys()
        if len(created) != 1 or changed != {"graph/eval-plan.md", *created}:
            errors.append("refactor changed files outside the source and one new note")
        source = after.get("graph/eval-plan.md", "")
        if "## Architecture" in source or "Use a graph-aware boundary." in source:
            errors.append("architecture section was not extracted")
        extracted = [
            key for key, value in after.items()
            if key.startswith("graph/")
            and key != "graph/eval-plan.md"
            and re.search(r"^#\s+Architecture\s*$", value, re.MULTILINE)
            and "Use a graph-aware boundary." in value
            and re.search(r"^#{2,3}\s+Storage\s*$", value, re.MULTILINE)
            and "Markdown files." in value
        ]
        if len(extracted) != 1:
            errors.append("extracted document not found")
        else:
            target = extracted[0][6:-3]
            standalone_link = re.compile(
                rf"^(?:\[Architecture\]\({re.escape(target)}\.md\)|"
                rf"\[\[{re.escape(target)}(?:\|Architecture)?\]\])$",
                re.MULTILINE,
            )
            if not standalone_link.search(source):
                errors.append("source does not contain an independent standalone inclusion link")
        if "## Delivery\n\nPreserve this section." not in source:
            errors.append("unrelated source section was not preserved")
    if scenario.id == "create-and-validate-a-schema-bound-document":
        created = [
            (key, after[key]) for key in after.keys() - before.keys()
            if key.startswith("graph/meetings/") and key.endswith(".md")
        ]
        valid = False
        if len(created) == 1:
            _, body = created[0]
            frontmatter = {}
            if body.startswith("---\n") and "\n---\n" in body[4:]:
                raw = body[4:body.find("\n---\n", 4)]
                try:
                    frontmatter = yaml.safe_load(raw) or {}
                except yaml.YAMLError:
                    frontmatter = {}
            attendees_valid = False
            attendees_match = re.search(
                r"^## Attendees\s*$\n(?P<value>.*?)(?=^##\s|\Z)",
                body,
                flags=re.MULTILINE | re.DOTALL,
            )
            if attendees_match:
                attendee_text = attendees_match.group("value").strip()
                try:
                    attendee_value = yaml.safe_load(attendee_text)
                except yaml.YAMLError:
                    attendee_value = attendee_text
                attendees_valid = attendee_value in (
                    "Ada and Alan",
                    ["Ada", "Alan"],
                )
            attendees_valid = attendees_valid or frontmatter.get("attendees") in (
                "Ada and Alan",
                ["Ada", "Alan"],
            )
            valid = (
                isinstance(frontmatter, dict)
                and frontmatter.get("type") == "meeting"
                and frontmatter.get("draft") is False
                and "# Evaluation Sync" in body
                and attendees_valid
                and "## Notes" in body
                and "Review the graph." in body
            )
        if not valid:
            errors.append("typed schema-bound meeting was not created")
    if scenario.id == "fix-code-without-activating-iwe":
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        if changed != {"src/retry.py"}:
            errors.append(f"unexpected changed files: {sorted(changed)}")
        check_environment = dict(os.environ)
        check_environment["PYTHONDONTWRITEBYTECODE"] = "1"
        focused = subprocess.run(
            [sys.executable, "-m", "unittest", "tests/test_retry.py"],
            cwd=workspace,
            env=check_environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if focused.returncode != 0:
            errors.append("focused retry test does not pass after the agent run")
    return errors


SKILL_FINGERPRINT_WIDTH = 64


def normalized_skill_text(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def tested_skill_fingerprints(skill: SkillSpec | None) -> frozenset[str]:
    if skill is None:
        return frozenset()
    fingerprints = set()
    for path in skill.path.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        normalized = normalized_skill_text(text)
        fingerprints.update(
            normalized[index:index + SKILL_FINGERPRINT_WIDTH]
            for index in range(len(normalized) - SKILL_FINGERPRINT_WIDTH + 1)
        )
    return frozenset(fingerprints)


def sanitize_judge_evidence(skill: SkillSpec | None, value):
    fingerprints = tested_skill_fingerprints(skill)

    def sanitize(item):
        if isinstance(item, str):
            normalized = normalized_skill_text(item)
            if any(
                normalized[index:index + SKILL_FINGERPRINT_WIDTH] in fingerprints
                for index in range(len(normalized) - SKILL_FINGERPRINT_WIDTH + 1)
            ):
                return "[TESTED_SKILL_TEXT_REDACTED]"
            return item
        if isinstance(item, list):
            return [sanitize(child) for child in item]
        if isinstance(item, dict):
            return {key: sanitize(child) for key, child in item.items()}
        return item

    return sanitize(value)


def judge_command_evidence(skill: SkillSpec | None, commands: list[dict]) -> list[dict]:
    tested_roots = (
        (f".agents/skills/{skill.name}", ".agents/guidance")
        if skill is not None else ()
    )
    evidence = []
    for item in commands:
        redacted = sanitize_judge_evidence(skill, dict(item))
        if not isinstance(redacted, dict):
            raise TypeError("sanitized command evidence must remain an object")
        if any(root in str(item.get("command", "")) for root in tested_roots):
            redacted["output"] = "[TESTED_SKILL_OUTPUT_REDACTED]"
        evidence.append(redacted)
    return evidence


def judge_prompt(
    skill: SkillSpec | None,
    scenario: Scenario,
    run: dict,
    before: dict,
    after: dict,
    errors: list[str],
    eval_config: EvalConfig | None = None,
    oracle: dict | None = None,
) -> str:
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    expectations = {
        "task_tool_calls": [scenario.min_tool_calls, scenario.max_tool_calls],
        "task_tool_output_bytes": [
            scenario.min_task_tool_output_bytes,
            scenario.max_task_tool_output_bytes,
        ],
    }
    scoring = scenario.scoring or {}
    eval_config = eval_config or load_eval_config()
    diagnostics = efficiency_diagnostics(scenario, run.get("metrics", {}))
    minimums = {name: scoring[name]["minimum_score"] for name in DIMENSIONS}
    oracle = oracle or independent_oracle_evidence(scenario, before, after, run.get("final", ""))
    guidance_condition = (
        "one tested skill guidance payload was installed for the tested agent"
        if skill is not None else "no skill guidance was installed for the tested agent"
    )
    applicability_instruction = (
        ""
        if skill is not None
        else (
            "For this explicit no-skill control, skill_compliance is not applicable and will be "
            "discarded from aggregation and publication. The output schema still requires an integer: "
            "return 0 with a concise N/A rationale, do not describe it as a substantive failure, and "
            "it must not affect any other dimension or the overall analysis. "
        )
    )
    return f"""You are an independent read-only judge for an AI skill evaluation. Inspect only the supplied sanitized evidence. The target condition is that {guidance_condition}. {applicability_instruction}You run in a separate empty workspace and separate HOME/CODEX_HOME, with no access to the tested agent workspace or any tested guidance. Do not invoke IWE, load any IWE skill, or use IWE output as an independent correctness oracle. Score each required dimension on the integer 0..5 scale and return only schema-valid JSON.

The independent oracle evidence was produced by directly parsing fixture snapshots without the tested CLI or skill. Use it as the source of truth for task correctness and artifact correctness. Runtime telemetry proves only what the tested runtime returned and how it was used; it is not independent proof that its result is factually correct. Use runtime telemetry for provenance, procedure compliance, boundedness, recovery behavior, and efficiency.

Use this global scale: {json.dumps(eval_config.score_scale, ensure_ascii=False)}
Metric-specific efficiency scales: {json.dumps(eval_config.efficiency_score_scale, ensure_ascii=False)}
For each metric, apply both the global scale and its scenario-specific excellent condition. For tool and resource efficiency, the metric-specific scale is authoritative when it is more precise than the global wording. Select the highest score fully supported by the evidence. Scores 0 through 5 are all valid. Do not average or weight metric scores.
Minimum scores: {json.dumps(minimums)}
Excellent efficiency targets: {json.dumps(expectations)}
Efficiency range diagnostics: {json.dumps(diagnostics)}
`task_tool_calls` counts tested-agent tool execution events and excludes at most one exact successful standalone activation read of the tested skill. `task_tool_output_bytes` is the UTF-8 byte volume returned by task tool events to the agent, excluding that activation; `estimated_task_input_tokens` is its explicit bytes/4 approximation. `result_records` remains telemetry only and is not a document-read metric. Judge purpose, necessity, sequencing, stopping point, relevance, duplication, and volume. Diagnostics are evidence, not a formula that assigns or caps a score. Efficiency defects affect only their respective metric scores. Correctness and safety still dominate.

Ideal semantic procedure: {json.dumps(scenario.procedure or {}, ensure_ascii=False)}
Use this procedure to judge the purpose, necessity, sequencing, and stopping point of tool calls. Equivalent bounded strategies and more efficient routes may receive full semantic credit; do not require an exact command transcript. A call count inside the excellent range never proves semantic efficiency, and a range miss must be interpreted using the observed evidence and its cause.

Scenario: {scenario.name}
Operator request: {scenario.request}
Rubric: {scenario.rubric}
Changed files: {json.dumps(changed)}
Validity observations: {json.dumps(errors)}
Mechanical metrics: {json.dumps(run.get('metrics', {}))}
Independent oracle evidence: {json.dumps(sanitize_judge_evidence(skill, oracle), ensure_ascii=False)}
Exact IWE telemetry: {json.dumps(sanitize_judge_evidence(skill, run.get('iwe_telemetry', [])), ensure_ascii=False)}
Agent commands: {json.dumps(judge_command_evidence(skill, run['commands']), ensure_ascii=False)}
Agent final response: {sanitize_judge_evidence(skill, run['final'])}
"""


def efficiency_range_diagnostic(
    observed: int,
    minimum: int,
    maximum: int,
) -> dict:
    """Describe distance from an ideal range without assigning a semantic score."""
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in (observed, minimum, maximum)):
        raise ValueError("efficiency counts and bounds must be non-negative integers")
    if minimum > maximum:
        raise ValueError("efficiency minimum must not exceed maximum")
    if minimum <= observed <= maximum:
        return {
            "observed": observed,
            "excellent_range": [minimum, maximum],
            "status": "within",
            "distance": 0,
            "deviation_percent": 0.0,
        }
    if observed < minimum:
        distance = minimum - observed
        denominator = minimum
        status = "below"
    else:
        distance = observed - maximum
        denominator = maximum
        status = "above"
    deviation = None if denominator == 0 else round(distance * 100 / denominator, 2)
    return {
        "observed": observed,
        "excellent_range": [minimum, maximum],
        "status": status,
        "distance": distance,
        "deviation_percent": deviation,
    }


def efficiency_diagnostics(
    scenario: Scenario,
    metrics: dict,
) -> dict:
    return {
        "task_tool_calls": efficiency_range_diagnostic(
            metrics.get("task_tool_calls", 0),
            scenario.min_tool_calls,
            scenario.max_tool_calls,
        ),
        "task_tool_output_bytes": efficiency_range_diagnostic(
            metrics.get("task_tool_output_bytes", 0),
            scenario.min_task_tool_output_bytes,
            scenario.max_task_tool_output_bytes,
        ),
        "unbounded_read": bool(metrics.get("unbounded_read_calls", 0)),
    }


def verdict(
    scenario: Scenario,
    critique: dict,
    mechanical: list[str],
    exits_ok: bool,
    procedure_errors: list[str] | None = None,
    deterministic_metric_failures: dict[str, str] | None = None,
) -> dict:
    normalized_critique = critique if isinstance(critique, dict) else {}
    raw_dimensions = normalized_critique.get("dimensions", {})
    dimensions = raw_dimensions if isinstance(raw_dimensions, dict) else {}
    scoring = scenario.scoring or {}
    scores = {}
    malformed_scores = []
    for name in DIMENSIONS:
        raw_dimension = dimensions.get(name, {})
        dimension = raw_dimension if isinstance(raw_dimension, dict) else {}
        raw = dimension.get("score", 0)
        if isinstance(raw, int) and not isinstance(raw, bool) and 0 <= raw <= 5:
            score = raw
        else:
            score = 0
            malformed_scores.append(name)
        scores[name] = score
    failures = {
        name: {"score": scores[name], "required": scoring[name]["minimum_score"]}
        for name in DIMENSIONS
        if scores[name] < scoring[name]["minimum_score"]
    }
    for name, reason in (deterministic_metric_failures or {}).items():
        failure = failures.setdefault(
            name,
            {"score": scores[name], "required": scoring[name]["minimum_score"]},
        )
        failure["deterministic"] = reason
    validation_errors = list(mechanical)
    if not exits_ok:
        validation_errors.append("agent or judge process failed")
    if malformed_scores:
        validation_errors.append(
            "missing or invalid metric scores: " + ", ".join(malformed_scores)
        )
    return {
        "valid": not validation_errors,
        "metric_scores": scores,
        "metric_failures": failures,
        "validation_errors": validation_errors,
        "procedure_errors": list(procedure_errors or []),
        "critique": critique,
    }


def profile_verdict(raw_verdict: dict, profile: ModelProfile) -> dict:
    """Classify immutable judge scores under the selected model profile."""
    scores = raw_verdict.get("metric_scores", {})
    raw_failures = raw_verdict.get("metric_failures", {})
    failures: dict[str, dict] = {}
    for name in DIMENSIONS:
        deterministic = (
            raw_failures.get(name, {}).get("deterministic")
            if isinstance(raw_failures.get(name), dict)
            else None
        )
        score = scores.get(name, 0)
        if score < profile.minimum_score[name] or deterministic:
            failure = {"score": score, "required": profile.minimum_score[name]}
            if deterministic:
                failure["deterministic"] = deterministic
            failures[name] = failure
    return {
        "name": profile.name,
        "minimum_score": dict(profile.minimum_score),
        "required_success_percent": dict(profile.required_success_percent),
        "metric_failures": failures,
    }


def required_successes(total: int, percent: int) -> int:
    if total < 1:
        raise ValueError("sample total must be positive")
    if not 1 <= percent <= 100:
        raise ValueError("required success percent must be in 1..100")
    return math.ceil(total * percent / 100)


def agent_metadata(command: str) -> dict[str, str]:
    tokens = shlex.split(command)
    executable = shutil.which(tokens[0])
    if not executable:
        raise RuntimeError(f"configured agent executable is unavailable: {tokens[0]}")
    version = subprocess.run(
        [executable, "--version"], text=True, capture_output=True, check=True
    ).stdout.strip()
    model_flag = "-m" if "-m" in tokens else "--model" if "--model" in tokens else None
    model = tokens[tokens.index(model_flag) + 1] if model_flag else "unknown"
    reasoning = "unknown"
    if "--effort" in tokens:
        reasoning = tokens[tokens.index("--effort") + 1]
    for index, token in enumerate(tokens[:-1]):
        if token == "-c" and tokens[index + 1].startswith("model_reasoning_effort="):
            reasoning = tokens[index + 1].split("=", 1)[1].strip('"')
            break
    return {
        "name": {"codex": "Codex CLI", "claude": "Claude Code"}.get(
            Path(executable).name, Path(executable).name
        ),
        "version": version.removeprefix("codex-cli "),
        "model": model,
        "reasoning": reasoning,
    }


def validate_shared_agent(config: dict, expected_agent: str) -> dict[str, dict[str, str]]:
    agent_name = Path(shlex.split(config["agent_command"])[0]).name
    judge_name = Path(shlex.split(config["judge_command"])[0]).name
    if agent_name != expected_agent or judge_name != expected_agent:
        raise ValueError(
            "tested runs and judges must use the same configured agent "
            f"{expected_agent!r}; got agent={agent_name!r}, judge={judge_name!r}"
        )
    return {
        "agent": agent_metadata(config["agent_command"]),
        "judge": agent_metadata(config["judge_command"]),
    }


def aggregate_results(
    results: list[dict],
    eval_config: EvalConfig | None = None,
    expected_samples: int | None = None,
    excluded_dimensions_by_target: dict[str, set[str]] | None = None,
    model_profile: ModelProfile | None = None,
) -> list[dict]:
    eval_config = eval_config or load_eval_config()
    model_profile = model_profile or resolve_model_profile(eval_config)
    excluded_dimensions_by_target = excluded_dimensions_by_target or {}
    grouped: dict[tuple[str | None, str], list[dict]] = {}
    for result in results:
        scenario = result["scenario"]
        scenario_id = result.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError(f"scenario_id missing from result: {scenario}")
        grouped.setdefault((result.get("target_id"), scenario_id), []).append(result)
    outcomes = []
    for (target_id, scenario_id), samples in grouped.items():
        scenario = samples[0]["scenario"]
        total = len(samples)
        sample_ids = [sample["sample"] for sample in samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError(f"duplicate samples for {target_id or 'single'} / {scenario}")
        if expected_samples is not None and set(sample_ids) != set(range(1, expected_samples + 1)):
            raise ValueError(f"incomplete samples for {target_id or 'single'} / {scenario}")
        metrics = {}
        for dimension in DIMENSIONS:
            if dimension in excluded_dimensions_by_target.get(target_id or "", set()):
                metrics[dimension] = {
                    "applicable": False,
                    "minimum_score": None,
                    "successful_samples": None,
                    "total_samples": total,
                    "success_percent": None,
                    "required_success_percent": None,
                    "required_successes": None,
                    "score_histogram": None,
                    "pass": True,
                }
                continue
            successful = sum(
                sample["verdict"].get("valid", False)
                and dimension
                not in profile_verdict(
                    sample["verdict"], model_profile
                )["metric_failures"]
                for sample in samples
            )
            percent = model_profile.required_success_percent[dimension]
            required = required_successes(total, percent)
            metrics[dimension] = {
                "applicable": True,
                "minimum_score": model_profile.minimum_score[dimension],
                "successful_samples": successful,
                "total_samples": total,
                "success_percent": successful * 100 / total,
                "required_success_percent": percent,
                "required_successes": required,
                "score_histogram": {
                    str(score): sum(
                        sample["verdict"].get("metric_scores", {}).get(dimension, 0) == score
                        for sample in samples
                    )
                    for score in range(6)
                },
                "pass": successful >= required,
            }
        invalid_samples = sum(not sample["verdict"].get("valid", False) for sample in samples)
        procedure_failure_samples = sum(
            bool(sample["verdict"].get("procedure_errors", [])) for sample in samples
        )
        procedure_error_counts: dict[str, int] = {}
        for sample in samples:
            for error in set(sample["verdict"].get("procedure_errors", [])):
                procedure_error_counts[error] = procedure_error_counts.get(error, 0) + 1
        outcome = {
            "scenario": scenario,
            "scenario_id": scenario_id,
            "model_profile": model_profile.name,
            "samples": total,
            "invalid_samples": invalid_samples,
            "procedure_failure_samples": procedure_failure_samples,
            "procedure_error_counts": dict(sorted(procedure_error_counts.items())),
            "metrics": metrics,
            "result_pass": invalid_samples == 0 and all(
                metrics[name]["pass"] for name in RESULT_DIMENSIONS
            ),
            "procedure_pass": all(metrics[name]["pass"] for name in PROCEDURE_DIMENSIONS),
            "pass": invalid_samples == 0 and all(item["pass"] for item in metrics.values()),
        }
        if target_id is not None:
            outcome["target_id"] = target_id
        outcomes.append(outcome)
    return outcomes


def replay_saved_report(
    report_dir: Path,
    output_path: Path,
    model_profile: ModelProfile,
    eval_config: EvalConfig | None = None,
) -> dict:
    """Reaggregate immutable raw samples under a selected model profile."""
    eval_config = eval_config or load_eval_config()
    source = report_dir.resolve()
    destination = output_path.resolve()
    if not source.is_dir():
        raise ValueError(f"saved report directory not found: {report_dir}")
    if source == destination or source in destination.parents:
        raise ValueError("replay output must be outside the immutable source report")

    results = []
    for path in sorted(source.rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in saved report: {path}") from exc
        if not isinstance(document, dict):
            continue
        if not {"scenario", "scenario_id", "sample", "verdict"} <= set(document):
            continue
        results.append(document)
    if not results:
        raise ValueError("saved report contains no raw samples")

    identities = [
        (result.get("target_id"), result["scenario_id"], result["sample"])
        for result in results
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("saved report contains duplicate raw sample identities")
    grouped_samples: dict[tuple[str | None, str], set[int]] = {}
    for result in results:
        grouped_samples.setdefault(
            (result.get("target_id"), result["scenario_id"]), set()
        ).add(result["sample"])
    sample_sets = list(grouped_samples.values())
    expected = set(range(1, max(max(values) for values in sample_sets) + 1))
    if any(values != expected for values in sample_sets):
        raise ValueError("saved report has incomplete or inconsistent sample cardinality")

    excluded_dimensions_by_target = {
        result["target_id"]: {"skill_compliance"}
        for result in results
        if result.get("target_id")
        and result.get("target_provenance", {}).get("skill_mode") == "none"
    }
    outcomes = aggregate_results(
        results,
        eval_config,
        expected_samples=len(expected),
        excluded_dimensions_by_target=excluded_dimensions_by_target,
        model_profile=model_profile,
    )
    replay = {
        "schema_version": 1,
        "source_report": str(source),
        "model_profile": model_profile.name,
        "minimum_score": model_profile.minimum_score,
        "required_success_percent": model_profile.required_success_percent,
        "raw_samples": len(results),
        "scenarios": outcomes,
    }
    atomic_write_json(output_path, replay)
    return replay


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--skill", help="skill id from the root config.toml")
    mode.add_argument("--experiment", type=Path, help="paired experiment TOML")
    parser.add_argument("--scenario", action="append", metavar="ID", help="exact scenario id (repeatable)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--samples", type=int)
    parser.add_argument(
        "--model-profile",
        choices=("medium", "weak"),
        default=None,
        help="tested-model profile; must match eval.agent_model_profiles for --agent",
    )
    parser.add_argument("--markdown-report", type=Path)
    parser.add_argument("--agent", choices=("codex", "claude"), default="codex")
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args()
    if args.markdown_report and not args.experiment:
        parser.error("--markdown-report requires --experiment")
    experiment = load_experiment(args.experiment, ROOT) if args.experiment else None
    skill = None if experiment else load_skill(args.skill)
    config_name = experiment.agent_judge_config if experiment else (args.config or args.agent)
    config_path = EVAL / "configs" / f"{config_name}.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    eval_config = load_eval_config()
    try:
        model_profile = resolve_agent_model_profile(eval_config, args.agent, args.model_profile)
    except ValueError as error:
        parser.error(str(error))
    scenarios = load_scenarios(eval_config=eval_config, model_profile=model_profile)
    if experiment:
        scenarios = select_scenarios(scenarios, list(experiment.scenario_ids))
    if args.scenario:
        try:
            scenarios = select_scenarios(scenarios, args.scenario)
        except ValueError as error:
            parser.error(str(error))
    if args.list:
        if experiment:
            for target in experiment.targets:
                skill_label = (
                    str(target.skill_path.relative_to(ROOT))
                    if target.skill_path is not None else "no skill"
                )
                print(
                    f"target {target.id}: {skill_label} @ IWE "
                    f"{target.runtime.version} ({target.runtime.source})"
                )
        for scenario in scenarios:
            print(f"{scenario.id}: {scenario.name} [{scenario.fixture}]")
        return 0
    if not scenarios:
        parser.error("no scenarios selected")
    shared_agent = validate_shared_agent(config, args.agent)
    if experiment and (args.jobs is not None or args.samples is not None):
        parser.error("experiment samples/jobs are authoritative; edit the manifest")
    if experiment:
        runtime_binaries = {
            target.id: verify_runtime_binary(target.runtime) for target in experiment.targets
        }
        canonical = {}
        for target in experiment.targets:
            binary = runtime_binaries[target.id]
            previous = canonical.setdefault(binary, target.runtime.version)
            if previous != target.runtime.version:
                raise RuntimeError(
                    f"targets resolve {binary} with conflicting versions; use distinct directory sources"
                )
        jobs = experiment.jobs
        samples = experiment.samples
    else:
        assert skill is not None
        iwe_binary = verify_iwe_binary(skill)
        runtime_binaries = {"single": iwe_binary}
        jobs = args.jobs or config["jobs"]
        samples = args.samples or config["samples"]
    cache = EVAL / ".cache"
    cache.mkdir(exist_ok=True)
    fixtures = {name: ensure_fixture(config, name, cache) for name in {s.fixture for s in scenarios}}
    suffix = f"-{experiment.name}" if experiment else ""
    report_dir = EVAL / "reports" / (dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ") + suffix)
    report_dir.mkdir(parents=True)

    def execute(task) -> dict:
        if isinstance(task, MatrixCell):
            scenario, sample = task.scenario, task.sample_index
            local_target = task.target
            local_skill = task.target if task.target.has_skill else None
            target_id, pair_id = task.target_id, task.pair_id
            local_iwe_binary = runtime_binaries[target_id]
        else:
            scenario, sample = task
            assert skill is not None
            local_target = skill
            local_skill, target_id, pair_id = skill, "single", None
            local_iwe_binary = runtime_binaries[target_id]
        temporary = Path(tempfile.mkdtemp(prefix="iwe-agent-eval-"))
        workspace = temporary / "workspace"
        base_name = "seventeen-centuries" if scenario.fixture.startswith("seventeen") else "pkm-demo"
        shutil.copytree(fixtures[scenario.fixture], workspace, ignore=shutil.ignore_patterns(".git"))
        prepare(workspace, scenario.fixture)
        install_skill(workspace, local_skill)
        activation_path = (
            workspace / ".agents/guidance/SKILL.md"
            if local_skill is not None
            else None
        )
        assert_workspace_ready(workspace, activation_path)
        before = snapshot(workspace)
        isolated_home = temporary / "home"
        codex_home = temporary / "codex-home"
        isolated_home.mkdir(); codex_home.mkdir()
        shim_bin = temporary / "shims"
        install_command_shims(shim_bin, scenario, local_iwe_binary)
        (isolated_home / ".bash_profile").write_text(
            f'export PATH="{shim_bin}:{local_iwe_binary.parent}:$PATH"\n',
            encoding="utf-8",
        )
        host_auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if host_auth.exists(): shutil.copy2(host_auth, codex_home / "auth.json")
        env = eval_environment(
            isolated_home, codex_home, shim_bin, local_iwe_binary, temporary, args.agent
        )
        prompt = agent_prompt(
            scenario,
            skill_installed=local_skill is not None,
            activation_path=activation_path,
        )
        agent = run_process(config["agent_command"], prompt, workspace, config["timeout_seconds"], env)
        telemetry = load_iwe_telemetry(temporary / "iwe-telemetry.jsonl")
        agent["iwe_telemetry"] = telemetry
        agent["metrics"] = command_metrics(
            agent["commands"], telemetry,
            tested_skill=local_skill.name if local_skill is not None else None,
            exclude_skill_activation=scenario.skill_activation == "required",
            activation_path=activation_path,
        )
        range_diagnostics = efficiency_diagnostics(scenario, agent["metrics"])
        after = snapshot(workspace)
        integrity_errors = mechanical_errors(
            scenario, before, after, agent["commands"], workspace, agent["metrics"]
        )
        procedural_errors = procedure_errors(
            scenario,
            agent["commands"],
            agent["metrics"],
            agent["iwe_telemetry"],
        )
        judge_schema = EVAL / "judge.schema.json"
        judge_command = config["judge_command"].format(
            judge_schema=shlex.quote(str(judge_schema)),
            judge_schema_json=shlex.quote(
                json.dumps(json.loads(judge_schema.read_text(encoding="utf-8")), separators=(",", ":"))
            ),
        )
        oracle = independent_oracle_evidence(scenario, before, after, agent["final"])
        deterministic_failures = deterministic_metric_failures(
            scenario,
            agent["commands"],
            oracle,
            metrics=agent["metrics"],
        )
        judge_prompt_text = judge_prompt(
            local_skill,
            scenario,
            agent,
            before,
            after,
            integrity_errors + procedural_errors + list(deterministic_failures.values()),
            eval_config,
            oracle,
        )
        remove_tested_skill_for_judge(workspace)
        judge_workspace = create_judge_workspace(temporary)
        judge_home = temporary / "judge-home"
        judge_codex_home = temporary / "judge-codex-home"
        judge_home.mkdir()
        judge_codex_home.mkdir()
        if host_auth.exists():
            shutil.copy2(host_auth, judge_codex_home / "auth.json")
        judge_tools = temporary / "judge-tools"
        judge_tools.mkdir()
        judge_executable = shutil.which(shlex.split(judge_command)[0])
        node_executable = shutil.which("node")
        if not judge_executable or not node_executable:
            raise RuntimeError("configured judge executable or its node runtime is unavailable")
        (judge_tools / Path(judge_executable).name).symlink_to(judge_executable)
        (judge_tools / "node").symlink_to(node_executable)
        judge_env = judge_environment(
            judge_home, judge_codex_home, judge_tools, args.agent
        )
        judge = run_process(
            judge_command,
            judge_prompt_text,
            judge_workspace,
            config["timeout_seconds"],
            judge_env,
        )
        try: critique = json.loads(judge["final"])
        except json.JSONDecodeError: critique = {"rationale": "invalid judge JSON", "evidence": [judge["final"]], "dimensions": {}}
        judge_errors = list(integrity_errors)
        if judge["commands"]:
            judge_errors.append("judge executed commands instead of inspecting supplied evidence only")
        raw_sample_verdict = verdict(
            scenario,
            critique,
            judge_errors,
            agent["exit"] == 0 and judge["exit"] == 0,
            procedure_errors=procedural_errors,
            deterministic_metric_failures=deterministic_failures,
        )
        sample_profile = profile_verdict(raw_sample_verdict, model_profile)
        result = {
            "scenario": scenario.name,
            "scenario_id": scenario.id,
            "sample": sample,
            "fixture": {
                "name": scenario.fixture,
                "commit": config["fixtures"][base_name]["commit"],
            },
            "agent_judge_config": {
                "name": config["name"],
                "agent_command_sha256": hashlib.sha256(config["agent_command"].encode()).hexdigest(),
                "judge_command_sha256": hashlib.sha256(config["judge_command"].encode()).hexdigest(),
            },
            "scoring_contract": {
                "scale": eval_config.score_scale,
                "dimensions": scenario.scoring,
            },
            "evaluation_profile": sample_profile,
            "efficiency_expectations": {
                "task_tool_calls": [scenario.min_tool_calls, scenario.max_tool_calls],
                "task_tool_output_bytes": [
                    scenario.min_task_tool_output_bytes,
                    scenario.max_task_tool_output_bytes,
                ],
                "max_iwe_calls": scenario.max_iwe_calls,
                "hard_max_task_tool_calls": scenario.hard_max_task_tool_calls,
            },
            "agent": agent,
            "efficiency_diagnostics": range_diagnostics,
            "judge": judge,
            "verdict": raw_sample_verdict,
            "workspace": str(workspace) if args.keep_workspaces else None,
        }
        if experiment:
            result["target_id"] = target_id
            result["pair_id"] = pair_id
            target_dir = report_dir / "targets" / target_id
            target_dir.mkdir(parents=True, exist_ok=True)
            local_skill_path = local_skill.path if local_skill is not None else None
            result["target_provenance"] = {
                "skill_mode": "installed" if local_skill is not None else "none",
                "skill_path": (
                    str(local_skill_path.relative_to(ROOT)) if local_skill_path is not None else None
                ),
                "skill_version": local_skill.skill_version if local_skill is not None else None,
                "skill_sha256": payload_hash(local_skill_path) if local_skill_path is not None else None,
                "contract_file": str(local_target.contract_file.relative_to(ROOT)),
                "contract_sha256": hashlib.sha256(local_target.contract_file.read_bytes()).hexdigest(),
                "runtime_source": local_target.runtime.source,
                "runtime_binary": str(local_iwe_binary),
                "declared_runtime_version": local_target.runtime.version,
                "observed_runtime_version": local_target.runtime.version,
            }
            raw_path = target_dir / f"{scenario.slug}--{sample}.json"
        else:
            raw_path = report_dir / f"{scenario.slug}--{sample}.json"
        atomic_write_json(raw_path, result)
        failures = sorted(result["evaluation_profile"]["metric_failures"])
        status = "VALID" if result["verdict"]["valid"] else "INVALID"
        suffix = f" metric_failures={failures}" if failures else ""
        print(f"{status} sample {sample} {scenario.name}{suffix}", flush=True)
        if not args.keep_workspaces: shutil.rmtree(temporary)
        return result

    tasks = build_matrix(experiment, scenarios) if experiment else [
        (scenario, sample) for scenario in scenarios for sample in range(1, samples + 1)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(jobs, len(tasks))) as executor:
        results = list(executor.map(execute, tasks))
    excluded_dimensions_by_target = {
        target.id: ({"skill_compliance"} if not target.has_skill else set())
        for target in experiment.targets
    } if experiment else {}
    outcomes = aggregate_results(
        results,
        eval_config,
        expected_samples=samples,
        excluded_dimensions_by_target=excluded_dimensions_by_target,
        model_profile=model_profile,
    )
    summary = {
        "configuration": config["name"],
        "skill": skill.name if skill else None,
        "experiment": experiment.name if experiment else None,
        "model_profile": model_profile.name,
        "minimum_score": model_profile.minimum_score,
        "required_success_percent": model_profile.required_success_percent,
        "scenarios": outcomes,
        "results": [
            ({"target_id": r["target_id"], "pair_id": r["pair_id"]} if experiment else {})
            | {"scenario_id": r["scenario_id"], "scenario": r["scenario"],
               "sample": r["sample"], "verdict": r["verdict"]}
            for r in results
        ],
    }
    snapshot_document = None
    if experiment:
        from compare import compare_results
        expected_pairs = {
            (cell.scenario_id, cell.sample_index): cell.pair_id
            for cell in tasks
            if isinstance(cell, MatrixCell)
        }
        comparisons = compare_results(
            results,
            tuple(target.id for target in experiment.targets),
            DIMENSIONS,
            expected_pairs,
            excluded_dimensions_by_target=excluded_dimensions_by_target,
        )
        summary["comparisons"] = comparisons
        snapshot_document = {
            "schema_version": 1, "name": experiment.name,
            "scenarios": [scenario.id for scenario in scenarios],
            "samples": samples, "jobs": jobs,
            "model_profile": model_profile.name,
            "minimum_score": model_profile.minimum_score,
            "required_success_percent": model_profile.required_success_percent,
            "agent_judge_config": experiment.agent_judge_config,
            "agent": shared_agent["agent"],
            "judge": {
                "model": shared_agent["judge"]["model"],
                "reasoning": shared_agent["judge"]["reasoning"],
            },
            "estimated_agent_calls": len(tasks), "estimated_judge_calls": len(tasks),
            "targets": [
                {"id": target.id,
                 "model_profile": model_profile.name,
                 "minimum_score": model_profile.minimum_score,
                 "required_success_percent": model_profile.required_success_percent,
                 "skill_mode": "installed" if target.has_skill else "none",
                 "skill_path": str(target.path.relative_to(ROOT)) if target.path else None,
                 "skill_version": target.skill_version,
                 "contract_file": str(target.contract_file.relative_to(ROOT)),
                 "runtime": {"cli": target.runtime.cli, "source": target.runtime.source,
                             "directory": str(target.runtime.directory), "version": target.runtime.version}}
                for target in experiment.targets
            ],
        }
        atomic_write_json(report_dir / "experiment.json", snapshot_document)
        for target in experiment.targets:
            atomic_write_json(report_dir / "targets" / target.id / "summary.json", {
                "target_id": target.id,
                "model_profile": model_profile.name,
                "minimum_score": model_profile.minimum_score,
                "required_success_percent": model_profile.required_success_percent,
                "scenarios": [outcome for outcome in outcomes if outcome.get("target_id") == target.id],
            })
        grouped_comparisons = {}
        for comparison in comparisons:
            key = f"{comparison['left_target_id']}--vs--{comparison['right_target_id']}"
            grouped_comparisons.setdefault(key, []).append(comparison)
        for key, values in grouped_comparisons.items():
            atomic_write_json(report_dir / "comparisons" / f"{key}.json", values)
    atomic_write_json(report_dir / "summary.json", summary)
    if args.markdown_report:
        from report_markdown import write_markdown

        assert snapshot_document is not None
        markdown_path = args.markdown_report
        if not markdown_path.is_absolute():
            markdown_path = ROOT / markdown_path
        write_markdown(markdown_path, snapshot_document, summary, report_dir)
    for outcome in outcomes:
        failed_metrics = [
            name for name, detail in outcome["metrics"].items() if not detail["pass"]
        ]
        details = []
        if failed_metrics:
            details.append(f"metric_failures={failed_metrics}")
        if outcome["invalid_samples"]:
            details.append(f"invalid_samples={outcome['invalid_samples']}")
        suffix = " " + " ".join(details) if details else ""
        target_prefix = f"{outcome.get('target_id')} / " if outcome.get("target_id") else ""
        print(f"{'PASS' if outcome['pass'] else 'FAIL'} aggregate {target_prefix}{outcome['scenario']}{suffix}")
    print(f"Reports: {report_dir}")
    return 0 if all(outcome["pass"] for outcome in outcomes) else 1

if __name__ == "__main__":
    sys.exit(main())
