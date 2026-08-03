#!/usr/bin/env python3
"""Synchronize a curated frozen IWE contract with the configured local CLI."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from skill_manifest import ROOT, load_skill


def run(iwe: str, *args: str) -> str:
    completed = subprocess.run(
        [iwe, *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{' '.join((iwe, *args))} failed:\n{completed.stdout}")
    return completed.stdout.rstrip()


def command_args(name: str) -> tuple[str, ...]:
    return tuple(name.split("."))


def synchronized_contract(contract: dict, iwe: str, tested_version: str) -> dict:
    actual = run(iwe, "--version")
    expected = f"iwe {tested_version}"
    if actual != expected:
        raise ValueError(f"expected {expected!r}, got {actual!r}")

    result = json.loads(json.dumps(contract))
    commands = result.get("commands")
    if not isinstance(commands, dict):
        raise ValueError("contract commands must be an object")
    for name, command in commands.items():
        help_text = run(iwe, *command_args(name), "--help")
        for flag in command.get("supported_flags", []):
            if flag not in help_text:
                raise ValueError(f"{name} contract flag is absent from CLI help: {flag}")
        command["help_sha256"] = hashlib.sha256(
            (help_text + "\n").encode("utf-8")
        ).hexdigest()
    return result


def render(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    spec = load_skill(args.skill)
    contracts_root = (ROOT / "contracts").resolve()
    if not spec.contract_file.resolve().is_relative_to(contracts_root):
        raise SystemExit(f"refusing contract outside {contracts_root}: {spec.contract_file}")
    iwe = shutil.which(spec.runtime_cli)
    if not iwe:
        raise SystemExit(f"missing configured IWE executable: {spec.runtime_cli}")

    current_text = spec.contract_file.read_text(encoding="utf-8")
    current = json.loads(current_text)
    expected_text = render(synchronized_contract(current, iwe, spec.tested_version))
    if current_text == expected_text:
        print(f"{spec.contract_file.relative_to(ROOT)}: up to date")
        return 0
    if args.check:
        sys.stdout.writelines(
            difflib.unified_diff(
                current_text.splitlines(keepends=True),
                expected_text.splitlines(keepends=True),
                fromfile=str(spec.contract_file.relative_to(ROOT)),
                tofile="generated",
            )
        )
        return 1
    spec.contract_file.write_text(expected_text, encoding="utf-8")
    print(f"wrote {spec.contract_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
