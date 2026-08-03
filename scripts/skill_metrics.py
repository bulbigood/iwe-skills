#!/usr/bin/env python3
"""Report deterministic size and offline-contract metrics for installed skills."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from skill_manifest import ROOT, load_skills


def measure(path: Path, contract_file: Path) -> dict[str, int | str]:
    skill_file = path / "SKILL.md"
    skill = skill_file.read_text(encoding="utf-8")
    runtime_files = [item for item in path.rglob("*") if item.is_file()]
    runtime_text = "\n".join(item.read_text(encoding="utf-8") for item in runtime_files)
    references = list((path / "references").glob("*.md"))
    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    return {
        "name": path.name,
        "skill_lines": len(skill.splitlines()),
        "skill_bytes": len(skill.encode("utf-8")),
        "estimated_tokens": math.ceil(len(skill) / 4),
        "reference_files": len(references),
        "reference_bytes": sum(item.stat().st_size for item in references),
        "external_urls": len(re.findall(r"https?://", runtime_text)),
        "contract_operations": len(contract["commands"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _, skills = load_skills(ROOT)
    payload = {"skills": [measure(spec.path, spec.contract_file) for spec in skills.values()]}
    if args.json:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        for item in payload["skills"]:
            print(
                f"{item['name']}: {item['skill_lines']} lines, "
                f"{item['skill_bytes']} bytes, ~{item['estimated_tokens']} tokens, "
                f"{item['reference_files']} references/{item['reference_bytes']} bytes, "
                f"{item['external_urls']} external URLs, "
                f"{item['contract_operations']} contract operations"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
