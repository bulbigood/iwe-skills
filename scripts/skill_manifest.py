#!/usr/bin/env python3
"""Load and validate versioned IWE skill mappings from the repository manifest."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: Path
    skill_version: str
    runtime_cli: str
    supported: str
    tested_version: str
    contract_file: Path
    upstream_revision: str
    normal_tool_calls: int
    maximum_search_results: int
    maximum_output_bytes: int
    network_allowed: bool
    forbidden_fallbacks: tuple[str, ...]

    @property
    def iwe_cli_version(self) -> str:
        """Compatibility alias for callers not yet migrated to tested_version."""
        return self.tested_version

    def as_json(self, root: Path) -> dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path.relative_to(root)),
            "skill_version": self.skill_version,
            "runtime": {
                "cli": self.runtime_cli,
                "supported": self.supported,
                "tested": self.tested_version,
            },
            "contract": {
                "file": str(self.contract_file.relative_to(root)),
                "upstream_revision": self.upstream_revision,
            },
            "execution": {
                "normal_tool_calls": self.normal_tool_calls,
                "maximum_search_results": self.maximum_search_results,
                "maximum_output_bytes": self.maximum_output_bytes,
                "network_allowed": self.network_allowed,
                "forbidden_fallbacks": list(self.forbidden_fallbacks),
            },
        }


def _frontmatter(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid frontmatter in {skill_file}")
    return match.group(1)


def _frontmatter_value(skill_file: Path, key: str) -> str:
    value = re.search(
        rf"^{re.escape(key)}:[ \t]*[\"']?([^\s\"']+)",
        _frontmatter(skill_file),
        re.MULTILINE,
    )
    if not value:
        raise ValueError(f"missing top-level {key} in {skill_file}")
    return value.group(1)


def _frontmatter_scalar(skill_file: Path, key: str) -> str:
    value = re.search(
        rf"^{re.escape(key)}:[ \t]*(.+?)[ \t]*$",
        _frontmatter(skill_file),
        re.MULTILINE,
    )
    if not value:
        raise ValueError(f"missing top-level {key} in {skill_file}")
    return value.group(1).strip().strip("\"'")


def _frontmatter_metadata_value(skill_file: Path, key: str) -> str:
    metadata = re.search(
        r"^metadata:[ \t]*\n((?:[ \t]+[^\n]*(?:\n|$))*)",
        _frontmatter(skill_file),
        re.MULTILINE,
    )
    if not metadata:
        raise ValueError(f"missing metadata in {skill_file}")
    value = re.search(
        rf"^  {re.escape(key)}:[ \t]*(.+?)[ \t]*$",
        metadata.group(1),
        re.MULTILINE,
    )
    if not value:
        raise ValueError(f"missing metadata.{key} in {skill_file}")
    return value.group(1).strip().strip("\"'")


def _mapping(raw: object, field: str, skill: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"skill {skill} requires a {field} table")
    return raw


def _string(raw: dict, field: str, context: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} requires {field} string")
    return value


def _integer(raw: dict, field: str, context: str) -> int:
    value = raw.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{context} requires positive {field}")
    return value


def load_skills(root: Path = ROOT) -> tuple[str, dict[str, SkillSpec]]:
    root = root.resolve()
    manifest_file = root / "config.toml"
    data = tomllib.loads(manifest_file.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported manifest schema in {manifest_file}")
    default_skill = data.get("default_skill")
    entries = data.get("skills")
    if not isinstance(default_skill, str) or not isinstance(entries, dict):
        raise ValueError(f"invalid skill manifest: {manifest_file}")

    specs: dict[str, SkillSpec] = {}
    for name, value in entries.items():
        raw = _mapping(value, "skill", name)
        relative_path = _string(raw, "path", f"skill {name}")
        skill_version = _string(raw, "skill_version", f"skill {name}")
        runtime = _mapping(raw.get("runtime"), "runtime", name)
        contract = _mapping(raw.get("contract"), "contract", name)
        execution = _mapping(raw.get("execution"), "execution", name)

        path = (root / relative_path).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"skill path escapes repository root: {relative_path}")
        if not path.is_dir() or path.name != name:
            raise ValueError(f"invalid skill directory for {name}: {path}")
        metadata_name = _frontmatter_value(path / "SKILL.md", "name")
        if metadata_name != name:
            raise ValueError(f"manifest name {name} does not match {metadata_name}")
        metadata_version = _frontmatter_metadata_value(path / "SKILL.md", "version")
        if metadata_version != skill_version:
            raise ValueError(
                f"manifest skill_version {skill_version} does not match {metadata_version}"
            )

        contract_relative = _string(contract, "file", f"skill {name} contract")
        contract_file = (root / contract_relative).resolve()
        if not contract_file.is_relative_to(root):
            raise ValueError(f"contract path escapes repository root: {contract_relative}")
        if not contract_file.is_file():
            raise ValueError(f"contract file does not exist: {contract_file}")

        tested = _string(runtime, "tested", f"skill {name} runtime")
        supported = _string(runtime, "supported", f"skill {name} runtime")
        line_match = re.match(r"^(\d+)\.(\d+)\.", tested)
        expected_range = (
            f">={line_match.group(1)}.{line_match.group(2)}.0 "
            f"<{line_match.group(1)}.{int(line_match.group(2)) + 1}.0"
            if line_match
            else ""
        )
        if supported != expected_range:
            raise ValueError(f"tested version {tested} does not match supported range {supported}")
        compatibility = _frontmatter_scalar(path / "SKILL.md", "compatibility")
        expected_compatibility = (
            f"Requires IWE CLI {supported.split()[0]} and {supported.split()[1]}."
        )
        if compatibility != expected_compatibility:
            raise ValueError(
                "skill compatibility does not match configured supported runtime: "
                f"{compatibility!r} != {expected_compatibility!r}"
            )

        maximum_results = _integer(execution, "maximum_search_results", f"skill {name} execution")
        contract_data = json.loads(contract_file.read_text(encoding="utf-8"))
        if contract_data.get("schema_version") != 1:
            raise ValueError(f"unsupported contract schema in {contract_file}")
        if contract_data.get("cli_line") != ".".join(tested.split(".")[:2]):
            raise ValueError(f"contract cli_line does not match tested version {tested}")
        if contract_data.get("default_limit") != maximum_results:
            raise ValueError("contract default_limit does not match maximum_search_results")
        commands = contract_data.get("commands")
        required_operations = {
            "find",
            "retrieve",
            "update",
            "create",
            "extract",
            "delete",
            "schema.validate",
        }
        if not isinstance(commands, dict) or set(commands) != required_operations:
            raise ValueError(
                f"contract operations must equal {sorted(required_operations)}: {contract_file}"
            )
        if "docs" in commands:
            raise ValueError("runtime contract must not expose iwe docs")

        fallbacks = execution.get("forbidden_fallbacks")
        if not isinstance(fallbacks, list) or not all(isinstance(item, str) for item in fallbacks):
            raise ValueError(f"skill {name} execution requires forbidden_fallbacks strings")
        network_allowed = execution.get("network_allowed")
        if not isinstance(network_allowed, bool):
            raise ValueError(f"skill {name} execution requires network_allowed boolean")

        specs[name] = SkillSpec(
            name=name,
            path=path,
            skill_version=skill_version,
            runtime_cli=_string(runtime, "cli", f"skill {name} runtime"),
            supported=supported,
            tested_version=tested,
            contract_file=contract_file,
            upstream_revision=_string(contract, "upstream_revision", f"skill {name} contract"),
            normal_tool_calls=_integer(execution, "normal_tool_calls", f"skill {name} execution"),
            maximum_search_results=maximum_results,
            maximum_output_bytes=_integer(execution, "maximum_output_bytes", f"skill {name} execution"),
            network_allowed=network_allowed,
            forbidden_fallbacks=tuple(fallbacks),
        )

    if default_skill not in specs:
        raise ValueError(f"default skill is not configured: {default_skill}")
    return default_skill, specs


def load_skill(name: str | None = None, root: Path = ROOT) -> SkillSpec:
    default_skill, specs = load_skills(root)
    selected = name or default_skill
    if selected not in specs:
        raise ValueError(f"unknown skill {selected}; choose from {', '.join(sorted(specs))}")
    return specs[selected]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill")
    parser.add_argument(
        "--field",
        choices=("name", "path", "tested_version", "contract_file"),
        help="print one field for the selected skill",
    )
    parser.add_argument("--json", action="store_true", help="print every skill as JSON")
    args = parser.parse_args()

    if args.json:
        default_skill, specs = load_skills()
        print(json.dumps({
            "schema_version": 1,
            "default_skill": default_skill,
            "skills": [spec.as_json(ROOT) for spec in specs.values()],
        }, separators=(",", ":")))
        return 0

    spec = load_skill(args.skill)
    if args.field:
        value = getattr(spec, args.field)
        print(value.relative_to(ROOT) if isinstance(value, Path) else value)
    else:
        print(spec.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
