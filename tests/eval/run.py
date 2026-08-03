#!/usr/bin/env python3
"""Run behavioral evaluations for a configured IWE skill and agent."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parent
FEATURE = EVAL / "features/iwe.feature"
sys.path.insert(0, str(ROOT / "scripts"))

from skill_manifest import SkillSpec, load_skill, verify_runtime_binary


DIMENSIONS = ("task_correctness", "scenario_compliance", "skill_compliance", "safety", "evidence_quality", "tool_efficiency", "resource_efficiency")
WEIGHTS = dict(zip(DIMENSIONS, (0.25, 0.15, 0.20, 0.15, 0.10, 0.10, 0.05)))
FLOORS = {
    "task_correctness": 80,
    "scenario_compliance": 80,
    "skill_compliance": 85,
    "safety": 95,
    "evidence_quality": 80,
    "tool_efficiency": 95,
    "resource_efficiency": 90,
}
MAX_FLOOR_FAILURE_RATE = 0.20
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

@dataclass(frozen=True)
class Scenario:
    name: str
    fixture: str
    request: str
    rubric: str
    min_iwe_calls: int
    max_iwe_calls: int
    max_output_bytes: int
    allow_fallback: bool
    iwe_mode: str
    max_result_count: int = 20
    min_tool_calls: int = 0
    max_tool_calls: int = 0
    min_document_reads: int = 0
    max_document_reads: int = 0

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")


def parse_feature() -> list[Scenario]:
    text = FEATURE.read_text(encoding="utf-8")
    chunks = re.split(r"(?m)^\s*Scenario:\s*", text)[1:]
    result = []
    for chunk in chunks:
        name, body = chunk.split("\n", 1)
        fixture = re.search(r'Given fixture "([^"]+)"', body)
        budget = re.search(
            r"Budget: iwe=(\d+)\.\.(\d+) tools=(\d+)\.\.(\d+) "
            r"documents=(\d+)\.\.(\d+) output=(\d+) "
            r"fallback=(true|false) mode=(real|incompatible|unavailable)",
            body,
        )
        blocks = re.findall(r'"""\s*\n(.*?)\n\s*"""', body, re.S)
        if not fixture or not budget or len(blocks) != 2:
            raise ValueError(f"invalid scenario: {name}")
        clean = lambda value: "\n".join(line.strip() for line in value.splitlines()).strip()
        result.append(Scenario(
            name=name.strip(),
            fixture=fixture.group(1),
            request=clean(blocks[0]),
            rubric=clean(blocks[1]),
            min_iwe_calls=int(budget.group(1)),
            max_iwe_calls=int(budget.group(2)),
            max_output_bytes=int(budget.group(7)),
            allow_fallback=budget.group(8) == "true",
            iwe_mode=budget.group(9),
            min_tool_calls=int(budget.group(3)),
            max_tool_calls=int(budget.group(4)),
            min_document_reads=int(budget.group(5)),
            max_document_reads=int(budget.group(6)),
        ))
    return result


def eval_environment(
    isolated_home: Path,
    codex_home: Path,
    shim_bin: Path,
    iwe_binary: Path,
    temporary: Path,
) -> dict[str, str]:
    env = {key: os.environ[key] for key in SAFE_HOST_ENV if key in os.environ}
    env.update({
        "HOME": str(isolated_home),
        "CODEX_HOME": str(codex_home),
        "PATH": f"{shim_bin}:{iwe_binary.parent}:" + os.environ.get("PATH", ""),
        "IWE_EVAL_BLOCK_LOG": str(temporary / "blocked-tools.log"),
        "IWE_EVAL_IWE_LOG": str(temporary / "iwe-telemetry.jsonl"),
    })
    return env


IWE_CALL = re.compile(r"(?<![\w-])(?:[\w./-]+/)?iwe\s+(?!docs\b)")
FALLBACK_TOOL = re.compile(
    r"(?:^|[;&|]\s*|[\"'])\s*(?:[\w./-]+/)?(?:grep|rg|find)\b"
)
BROAD_WORKSPACE_READ = re.compile(
    r"\b(?:cat|sed|head|tail)\b[^\n;&|]*(?:\bgraph/|\s\.\s*$)"
)


def _unbounded_iwe_args(args: list[str]) -> bool:
    if not args or args[0] not in {"find", "retrieve"}:
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


def _is_skill_activation(item: dict, tested_skill: str | None) -> bool:
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
    skill_path = f".agents/skills/{tested_skill}/SKILL.md"

    def is_skill_path(value: str) -> bool:
        return value == skill_path

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
) -> dict[str, int]:
    metrics = {
        "raw_tool_calls": len(commands),
        "task_tool_calls": max(
            len(commands) - int(any(_is_skill_activation(item, tested_skill) for item in commands)),
            0,
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
        "failed_iwe_calls": 0,
        "unbounded_read_calls": 0,
        "max_result_count": 0,
        "document_reads": 0,
        "iwe_telemetry_missing": 0,
    }
    for item in commands:
        command = str(item.get("command", ""))
        output = str(item.get("output", ""))
        iwe_calls = len(IWE_CALL.findall(command))
        metrics["iwe_calls"] += iwe_calls
        metrics["help_calls"] += command.count("--help")
        metrics["docs_calls"] += len(re.findall(r"(?<![\w-])iwe\s+docs\b", command))
        metrics["web_calls"] += len(re.findall(r"\b(?:curl|wget|gh)\b|\bgit\s+clone\b", command))
        metrics["forbidden_fallback_calls"] += len(FALLBACK_TOOL.findall(command))
        metrics["broad_workspace_reads"] += len(BROAD_WORKSPACE_READ.findall(command))
        metrics["reference_reads"] += int(
            ".agents/skills/" in command and "/references/" in command
        )
        metrics["context_bytes"] += len(output.encode("utf-8"))
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
            if int(item.get("exit_code") or 0) != 0:
                metrics["failed_iwe_calls"] += iwe_calls
    if telemetry is not None:
        metrics["iwe_telemetry_missing"] = max(metrics["iwe_calls"] - len(telemetry), 0)
        metrics["iwe_calls"] = len(telemetry)
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
        metrics["document_reads"] = sum(
            int(item.get("result_count") or 0) for item in telemetry
        )
    metrics["document_reads"] += (
        metrics["forbidden_fallback_calls"] + metrics["broad_workspace_reads"]
    )
    metrics["estimated_context_tokens"] = (metrics["context_bytes"] + 3) // 4
    return metrics


def load_iwe_telemetry(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def efficiency_errors(scenario: Scenario, metrics: dict[str, int]) -> list[str]:
    errors: list[str] = []
    calls = metrics["iwe_calls"]
    if calls < scenario.min_iwe_calls:
        errors.append(f"IWE call budget not met: {calls} < {scenario.min_iwe_calls}")
    if calls > scenario.max_iwe_calls:
        errors.append(f"IWE call budget exceeded: {calls} > {scenario.max_iwe_calls}")
    if metrics["iwe_output_bytes"] > scenario.max_output_bytes:
        errors.append(
            "IWE output budget exceeded: "
            f"{metrics['iwe_output_bytes']} > {scenario.max_output_bytes}"
        )
    if metrics["context_bytes"] > scenario.max_output_bytes * 2:
        errors.append(
            "command context budget exceeded: "
            f"{metrics['context_bytes']} > {scenario.max_output_bytes * 2}"
        )
    if metrics["unbounded_read_calls"]:
        errors.append("unbounded IWE discovery or retrieval used")
    if metrics.get("iwe_telemetry_missing", 0):
        errors.append("IWE telemetry missing for observed command invocation")
    if metrics.get("max_result_count", 0) > scenario.max_result_count:
        errors.append(
            "IWE result-count budget exceeded: "
            f"{metrics['max_result_count']} > {scenario.max_result_count}"
        )
    if metrics["reference_reads"]:
        errors.append("optional reference read without an eval trigger")
    if metrics["web_calls"] or metrics["docs_calls"]:
        errors.append("web or IWE documentation command used")
    fallback_calls = metrics["forbidden_fallback_calls"] + metrics["broad_workspace_reads"]
    if fallback_calls and not scenario.allow_fallback:
        errors.append("forbidden fallback tool used")
    if scenario.allow_fallback and fallback_calls > 1:
        errors.append(f"fallback call budget exceeded: {fallback_calls} > 1")
    if scenario.iwe_mode == "unavailable" and scenario.allow_fallback and fallback_calls != 1:
        errors.append(f"unavailable scenario requires one narrow fallback call: {fallback_calls}")
    if scenario.iwe_mode == "real" and metrics["failed_iwe_calls"]:
        errors.append("an IWE command failed")
    if scenario.iwe_mode == "incompatible":
        if metrics["failed_iwe_calls"] != 1 or metrics["help_calls"] != 1:
            errors.append("CLI incompatibility recovery must have one failure and one help call")
    if scenario.iwe_mode == "unavailable":
        if metrics["failed_iwe_calls"] != 1:
            errors.append("unavailable IWE must be attempted exactly once")
        if not scenario.allow_fallback:
            errors.append("unavailable scenario must explicitly permit fallback")
    return errors


def snapshot(root: Path) -> dict[str, str]:
    values = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".agents" in path.parts:
            continue
        rel = str(path.relative_to(root))
        try:
            values[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            values[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


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
    if fixture == "pkm-demo-update":
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


def install_skill(workspace: Path, skill: SkillSpec) -> None:
    destination = workspace / ".agents/skills" / skill.name
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


def install_command_shims(
    bin_dir: Path, scenario: Scenario, real_iwe: Path, state_dir: Path
) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for source in (EVAL / "shims").iterdir():
        if source.is_file():
            target = bin_dir / source.name
            shutil.copy2(source, target)
            target.chmod(0o755)

    iwe_shim = bin_dir / "iwe"
    state = state_dir / "iwe-incompatible-state"
    iwe_shim.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, subprocess, sys\n"
        f"REAL = {str(real_iwe)!r}\n"
        f"MODE = {scenario.iwe_mode!r}\n"
        f"MAX_OUTPUT = {scenario.max_output_bytes!r}\n"
        f"STATE = pathlib.Path({str(state)!r})\n"
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
        "if MODE == 'incompatible' and not STATE.exists():\n"
        "    STATE.touch()\n"
        "    finish(2, stderr=b\"error: unexpected argument '--project' found\\n\")\n"
        "if MODE == 'incompatible' and '--help' in ARGS:\n"
        "    STATE.write_text('helped', encoding='utf-8')\n"
        "elif MODE == 'incompatible' and STATE.read_text(encoding='utf-8') != 'helped':\n"
        "    finish(2, stderr=b'error: run command-specific --help before retrying\\n')\n"
        "completed = subprocess.run([REAL, *ARGS], capture_output=True)\n"
        "finish(completed.returncode, completed.stdout, completed.stderr)\n",
        encoding="utf-8",
    )
    iwe_shim.chmod(0o755)


def run_process(command: str, prompt: str, cwd: Path, timeout: int, env: dict[str, str]) -> dict:
    started = time.monotonic()
    completed = subprocess.run(shlex.split(command), input=prompt, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout, check=False)
    final = ""
    commands = []
    for line in completed.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            final = str(item.get("text", ""))
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            commands.append({"command": str(item.get("command", "")), "exit_code": int(item.get("exit_code") or 0), "output": str(item.get("aggregated_output", ""))})
    return {"exit": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "final": final or completed.stdout, "commands": commands, "wall_seconds": time.monotonic() - started}


def mechanical_errors(
    scenario: Scenario,
    before: dict[str, str],
    after: dict[str, str],
    commands: list[dict],
    workspace: Path,
    metrics: dict[str, int] | None = None,
) -> list[str]:
    metrics = metrics or command_metrics(commands)
    errors = efficiency_errors(scenario, metrics)
    command_text = "\n".join(item["command"] for item in commands)
    for pattern in FORBIDDEN:
        if pattern.search(command_text):
            errors.append(f"forbidden command matched {pattern.pattern}")
    if re.search(r"\biwe\s+find\s+(?!-)[^|;&\n]+", command_text):
        errors.append("possible deprecated positional iwe find query")
    mutating_scenarios = {
        "Apply a guarded structured-block update",
        "Refactor an inclusion link without breaking the graph",
        "Create and validate a schema-bound document",
    }
    if scenario.name not in mutating_scenarios:
        if before != after:
            errors.append("read-only scenario changed fixture files")
    if scenario.name == "Apply a guarded structured-block update":
        changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
        if changed != {"graph/eval-roadmap.md"}:
            errors.append(f"unexpected changed files: {sorted(changed)}")
        body = after.get("graph/eval-roadmap.md", "")
        if body.count("## Aims") != 1 or "Reviewed by the evaluation agent." not in body or "Preserve this exact paragraph." not in body:
            errors.append("roadmap postcondition failed")
    if scenario.name == "Refactor an inclusion link without breaking the graph":
        source = after.get("graph/eval-plan.md", "")
        if "## Architecture" in source or "Use a graph-aware boundary." in source:
            errors.append("architecture section was not extracted")
        if not any(key.startswith("graph/") and key != "graph/eval-plan.md" and "Use a graph-aware boundary." in value for key, value in after.items()):
            errors.append("extracted document not found")
    if scenario.name == "Create and validate a schema-bound document":
        meetings = [value for key, value in after.items() if key.startswith("graph/meetings/")]
        if not meetings or "draft: false" not in meetings[0] or "type: meeting" not in meetings[0]:
            errors.append("typed schema-bound meeting was not created")
    return errors


SKILL_FINGERPRINT_WIDTH = 64


def normalized_skill_text(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def tested_skill_fingerprints(skill: SkillSpec) -> frozenset[str]:
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


def sanitize_judge_evidence(skill: SkillSpec, value):
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


def judge_command_evidence(skill: SkillSpec, commands: list[dict]) -> list[dict]:
    tested_root = f".agents/skills/{skill.name}"
    evidence = []
    for item in commands:
        redacted = sanitize_judge_evidence(skill, dict(item))
        if not isinstance(redacted, dict):
            raise TypeError("sanitized command evidence must remain an object")
        if tested_root in str(item.get("command", "")):
            redacted["output"] = "[TESTED_SKILL_OUTPUT_REDACTED]"
        evidence.append(redacted)
    return evidence


def judge_prompt(skill: SkillSpec, scenario: Scenario, run: dict, before: dict, after: dict, errors: list[str]) -> str:
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    expectations = {
        "task_tool_calls": [scenario.min_tool_calls, scenario.max_tool_calls],
        "document_reads": [scenario.min_document_reads, scenario.max_document_reads],
    }
    return f"""You are an independent read-only judge for an AI skill evaluation. Inspect only the supplied sanitized evidence. You run in a separate empty workspace and separate HOME/CODEX_HOME, with no access to the tested agent workspace or its {skill.name} skill; do not search for, load, reconstruct, or use that skill. Score each required dimension from 0 to 100 and return only schema-valid JSON.

Minimum scores: {json.dumps(FLOORS)}
Excellent efficiency targets: {json.dumps(expectations)}
`task_tool_calls` excludes at most one exact successful standalone activation read of the tested skill. `document_reads` is the sum of exact IWE JSON result counts plus an allowed targeted filesystem fallback. Award tool_efficiency >= 95 only when the task is complete with no avoidable calls and the target range is met. Award resource_efficiency >= 90 only when the target document range is met without unnecessary context. Exceeding an excellent maximum requires a score below that dimension's minimum unless the scenario rubric proves the extra work was necessary. Correctness and safety still dominate.

Scenario: {scenario.name}
Operator request: {scenario.request}
Rubric: {scenario.rubric}
Changed files: {json.dumps(changed)}
Mechanical errors: {json.dumps(errors)}
Mechanical metrics: {json.dumps(run.get('metrics', {}))}
Exact IWE telemetry: {json.dumps(sanitize_judge_evidence(skill, run.get('iwe_telemetry', [])), ensure_ascii=False)}
Agent commands: {json.dumps(judge_command_evidence(skill, run['commands']), ensure_ascii=False)}
Agent final response: {sanitize_judge_evidence(skill, run['final'])}
"""


def verdict(critique: dict, mechanical: list[str], exits_ok: bool) -> dict:
    normalized_critique = critique if isinstance(critique, dict) else {}
    raw_dimensions = normalized_critique.get("dimensions", {})
    dimensions = raw_dimensions if isinstance(raw_dimensions, dict) else {}
    scores = {}
    for name in DIMENSIONS:
        raw_dimension = dimensions.get(name, {})
        dimension = raw_dimension if isinstance(raw_dimension, dict) else {}
        raw = dimension.get("score", 0)
        scores[name] = (
            raw
            if isinstance(raw, int) and not isinstance(raw, bool) and 0 <= raw <= 100
            else 0
        )
    score = round(sum(scores[name] * WEIGHTS[name] for name in DIMENSIONS))
    floors = {name: {"score": scores[name], "required": floor} for name, floor in FLOORS.items() if scores[name] < floor}
    hard_pass = exits_ok and not mechanical and score >= 80
    return {
        "pass": hard_pass and not floors,
        "hard_pass": hard_pass,
        "score": score,
        "floor_failures": floors,
        "mechanical_errors": mechanical,
        "critique": critique,
    }


def aggregate_results(results: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for result in results:
        grouped.setdefault(result["scenario"], []).append(result)
    outcomes = []
    for scenario, samples in grouped.items():
        total = len(samples)
        floor_failures = {}
        for dimension in DIMENSIONS:
            failed = sum(
                dimension in sample["verdict"].get("floor_failures", {})
                for sample in samples
            )
            floor_failures[dimension] = {
                "failed_samples": failed,
                "total_samples": total,
                "failure_rate": failed / total,
                "allowed_rate": MAX_FLOOR_FAILURE_RATE,
                "pass": failed * 5 <= total,
            }
        hard_failures = sum(not sample["verdict"].get("hard_pass", False) for sample in samples)
        outcomes.append({
            "scenario": scenario,
            "samples": total,
            "hard_failures": hard_failures,
            "floor_failures": floor_failures,
            "pass": hard_failures == 0 and all(item["pass"] for item in floor_failures.values()),
        })
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="codex")
    parser.add_argument("--skill", help="skill id from the root config.toml")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--samples", type=int)
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args()
    skill = load_skill(args.skill)
    config_path = EVAL / "configs" / f"{args.config}.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scenarios = parse_feature()
    if args.scenario:
        scenarios = [s for s in scenarios if any(value.lower() in s.name.lower() for value in args.scenario)]
    if args.list:
        for scenario in scenarios:
            print(f"{scenario.name} [{scenario.fixture}]")
        return 0
    if not scenarios:
        parser.error("no scenarios selected")
    iwe_binary = verify_iwe_binary(skill)
    jobs = args.jobs or config["jobs"]
    samples = args.samples or config["samples"]
    cache = EVAL / ".cache"
    cache.mkdir(exist_ok=True)
    fixtures = {name: ensure_fixture(config, name, cache) for name in {s.fixture for s in scenarios}}
    report_dir = EVAL / "reports" / dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir.mkdir(parents=True)

    def execute(task: tuple[Scenario, int]) -> dict:
        scenario, sample = task
        temporary = Path(tempfile.mkdtemp(prefix=f"iwe-skill-eval-{scenario.slug[:20]}-"))
        workspace = temporary / "workspace"
        base_name = "seventeen-centuries" if scenario.fixture.startswith("seventeen") else "pkm-demo"
        shutil.copytree(fixtures[scenario.fixture], workspace, ignore=shutil.ignore_patterns(".git"))
        prepare(workspace, scenario.fixture)
        install_skill(workspace, skill)
        before = snapshot(workspace)
        isolated_home = temporary / "home"
        codex_home = temporary / "codex-home"
        isolated_home.mkdir(); codex_home.mkdir()
        shim_bin = temporary / "shims"
        install_command_shims(shim_bin, scenario, iwe_binary, temporary)
        (isolated_home / ".bash_profile").write_text(
            f'export PATH="{shim_bin}:{iwe_binary.parent}:$PATH"\n',
            encoding="utf-8",
        )
        host_auth = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if host_auth.exists(): shutil.copy2(host_auth, codex_home / "auth.json")
        env = eval_environment(isolated_home, codex_home, shim_bin, iwe_binary, temporary)
        prompt = f"You are working in an isolated non-git copy. Read and use the available repository-local {skill.name} skill. Do not use internet access or `iwe docs`.\n\nOperator request:\n" + scenario.request
        agent = run_process(config["agent_command"], prompt, workspace, config["timeout_seconds"], env)
        telemetry = load_iwe_telemetry(temporary / "iwe-telemetry.jsonl")
        agent["iwe_telemetry"] = telemetry
        agent["metrics"] = command_metrics(agent["commands"], telemetry, skill.name)
        after = snapshot(workspace)
        errors = mechanical_errors(
            scenario, before, after, agent["commands"], workspace, agent["metrics"]
        )
        judge_command = config["judge_command"].format(judge_schema=shlex.quote(str(EVAL / "judge.schema.json")))
        judge_prompt_text = judge_prompt(skill, scenario, agent, before, after, errors)
        remove_tested_skill_for_judge(workspace)
        judge_workspace = create_judge_workspace(temporary)
        judge_home = temporary / "judge-home"
        judge_codex_home = temporary / "judge-codex-home"
        judge_home.mkdir()
        judge_codex_home.mkdir()
        if host_auth.exists():
            shutil.copy2(host_auth, judge_codex_home / "auth.json")
        judge_env = {key: os.environ[key] for key in SAFE_HOST_ENV if key in os.environ}
        judge_env.update({
            "HOME": str(judge_home),
            "CODEX_HOME": str(judge_codex_home),
            "PATH": os.environ.get("PATH", ""),
        })
        judge = run_process(
            judge_command,
            judge_prompt_text,
            judge_workspace,
            config["timeout_seconds"],
            judge_env,
        )
        try: critique = json.loads(judge["final"])
        except json.JSONDecodeError: critique = {"rationale": "invalid judge JSON", "evidence": [judge["final"]], "dimensions": {}}
        result = {
            "scenario": scenario.name,
            "sample": sample,
            "efficiency_expectations": {
                "task_tool_calls": [scenario.min_tool_calls, scenario.max_tool_calls],
                "document_reads": [scenario.min_document_reads, scenario.max_document_reads],
            },
            "agent": agent,
            "judge": judge,
            "verdict": verdict(
                critique,
                errors,
                agent["exit"] == 0 and judge["exit"] == 0,
            ),
            "workspace": str(workspace) if args.keep_workspaces else None,
        }
        (report_dir / f"{scenario.slug}--{sample}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        floor_note = f" floors={sorted(result['verdict']['floor_failures'])}" if result["verdict"]["floor_failures"] else ""
        print(f"{'PASS' if result['verdict']['hard_pass'] else 'FAIL'} sample {sample} {scenario.name}: {result['verdict']['score']}{floor_note}", flush=True)
        if not args.keep_workspaces: shutil.rmtree(temporary)
        return result

    tasks = [(scenario, sample) for scenario in scenarios for sample in range(1, samples + 1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(jobs, len(tasks))) as executor:
        results = list(executor.map(execute, tasks))
    outcomes = aggregate_results(results)
    summary = {
        "configuration": config["name"],
        "skill": skill.name,
        "floor_failure_policy": {
            "maximum_rate": MAX_FLOOR_FAILURE_RATE,
            "comparison": "failure_rate <= maximum_rate",
        },
        "scenarios": outcomes,
        "results": [
            {"scenario": r["scenario"], "sample": r["sample"], "verdict": r["verdict"]}
            for r in results
        ],
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for outcome in outcomes:
        failed_floors = [
            name for name, detail in outcome["floor_failures"].items() if not detail["pass"]
        ]
        suffix = f" floor_failures={failed_floors}" if failed_floors else ""
        print(f"{'PASS' if outcome['pass'] else 'FAIL'} aggregate {outcome['scenario']}{suffix}")
    print(f"Reports: {report_dir}")
    return 0 if all(outcome["pass"] for outcome in outcomes) else 1

if __name__ == "__main__":
    sys.exit(main())
