#!/usr/bin/env python3
"""Load and validate versioned IWE skill mappings from the repository manifest."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: Path
    iwe_cli_version: str


def _frontmatter_value(skill_file: Path, key: str) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        raise ValueError(f"invalid frontmatter in {skill_file}")
    value = re.search(
        rf"^\s*{re.escape(key)}:\s*[\"']?([^\s\"']+)",
        match.group(1),
        re.MULTILINE,
    )
    if not value:
        raise ValueError(f"missing {key} in {skill_file}")
    return value.group(1)


def load_skills(root: Path = ROOT) -> tuple[str, dict[str, SkillSpec]]:
    manifest_file = root / "config.toml"
    data = tomllib.loads(manifest_file.read_text(encoding="utf-8"))
    default_skill = data.get("default_skill")
    entries = data.get("skills")
    if not isinstance(default_skill, str) or not isinstance(entries, dict):
        raise ValueError(f"invalid skill manifest: {manifest_file}")

    specs: dict[str, SkillSpec] = {}
    root_resolved = root.resolve()
    for name, raw in entries.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid manifest entry for {name}")
        relative_path = raw.get("path")
        configured_version = raw.get("iwe_cli_version")
        if not isinstance(relative_path, str) or not isinstance(configured_version, str):
            raise ValueError(f"skill {name} requires path and iwe_cli_version strings")

        path = (root / relative_path).resolve()
        if not path.is_relative_to(root_resolved):
            raise ValueError(f"skill path escapes repository root: {relative_path}")
        if not path.is_dir():
            raise ValueError(f"skill directory does not exist: {path}")
        if path.name != name:
            raise ValueError(f"skill {name} must use a matching directory name")

        skill_file = path / "SKILL.md"
        metadata_name = _frontmatter_value(skill_file, "name")
        metadata_version = _frontmatter_value(skill_file, "iwe_cli_version")
        if metadata_name != name:
            raise ValueError(f"manifest name {name} does not match {metadata_name}")
        if metadata_version != configured_version:
            raise ValueError(
                f"skill {name} version mismatch: config={configured_version}, "
                f"metadata={metadata_version}"
            )
        specs[name] = SkillSpec(name, path, configured_version)

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
        choices=("name", "path", "iwe_cli_version"),
        help="print one field for the selected skill",
    )
    parser.add_argument("--json", action="store_true", help="print every skill as JSON")
    args = parser.parse_args()

    if args.json:
        default_skill, specs = load_skills()
        payload = {
            "default_skill": default_skill,
            "skills": [
                {
                    **asdict(spec),
                    "path": str(spec.path.relative_to(ROOT)),
                }
                for spec in specs.values()
            ],
        }
        print(json.dumps(payload, separators=(",", ":")))
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
