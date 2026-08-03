#!/usr/bin/env python3
"""Generate or verify bundled references for a configured IWE skill."""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

from skill_manifest import load_skill


DOC_TOPICS = ("query", "config", "schema")
COMMANDS = [
    (),
    ("init",),
    ("create",),
    ("new",),
    ("retrieve",),
    ("find",),
    ("count",),
    ("normalize",),
    ("tree",),
    ("squash",),
    ("export",),
    ("schema",),
    ("schema", "validate"),
    ("stats",),
    ("stats", "similarity"),
    ("rename",),
    ("delete",),
    ("extract",),
    ("inline",),
    ("update",),
    ("attach",),
    ("completions",),
    ("docs",),
]


def run(*args: str) -> str:
    completed = subprocess.run(
        ["iwe", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.rstrip()


def without_help_option(value: str) -> str:
    """Remove the universal help option from an otherwise exact command contract."""
    result: list[str] = []
    skipping_description = False
    for line in value.splitlines():
        if re.match(r"^\s*help\s+Print this message or the help of", line):
            continue
        if re.match(r"^\s*-h,\s*--help(?:\s|$)", line):
            skipping_description = True
            continue
        if skipping_description:
            if not line.strip():
                skipping_description = False
                continue
            if line[:1].isspace():
                continue
            skipping_description = False
        result.append(line)
    return "\n".join(result).rstrip()


def render_cli_reference() -> str:
    sections = [
        "# IWE CLI Reference\n",
        "This bundled reference preserves the exact command syntax. Workflow-oriented ",
        "references explain when to use each command.\n",
        "\n## Contents\n\n",
    ]
    for command in COMMANDS:
        display = "iwe" if not command else "iwe " + " ".join(command)
        sections.append(f"- [`{display}`](#{display.replace(' ', '-')})\n")
    for command in COMMANDS:
        display = "iwe" if not command else "iwe " + " ".join(command)
        arguments = ("--help",) if not command else (*command, "--help")
        sections.extend(
            [
                f"\n## `{display}`\n\n",
                "```text\n",
                without_help_option(run(*arguments)),
                "\n```\n",
            ]
        )
    return "".join(sections)


def render_builtin_reference() -> str:
    sections = [
        "# IWE Built-in Reference\n\n",
        "This bundled reference contains the complete query, configuration, and ",
        "document-schema contracts.\n",
        "\n## Contents\n\n",
    ]
    for topic in DOC_TOPICS:
        sections.append(f"- [`{topic}`](#{topic})\n")
    for topic in DOC_TOPICS:
        sections.extend([f"\n## `{topic}`\n\n", run("docs", topic), "\n"])
    return "".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    spec = load_skill(args.skill)
    actual_version = run("--version")
    expected_version = f"iwe {spec.iwe_cli_version}"
    if actual_version != expected_version:
        raise SystemExit(f"expected {expected_version!r}, got {actual_version!r}")

    expected = {
        spec.path / "references/cli-reference.md": render_cli_reference(),
        spec.path / "references/builtin-reference.md": render_builtin_reference(),
    }
    stale = False
    for path, value in expected.items():
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if existing == value:
            print(f"{path}: up to date")
            continue
        if args.check:
            stale = True
            sys.stdout.writelines(
                difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    value.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile="generated",
                )
            )
            continue
        path.write_text(value, encoding="utf-8")
        print(f"wrote {path}")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
