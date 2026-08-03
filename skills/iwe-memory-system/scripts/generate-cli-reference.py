#!/usr/bin/env python3
"""Generate or verify the iwe-memory-system CLI reference from `iwe --help`."""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_DIR / "SKILL.md"
OUTPUT_FILE = SKILL_DIR / "references" / "cli-reference.md"
BUILTIN_DOCS_FILE = SKILL_DIR / "references" / "builtin-reference.md"
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


def adapted_version() -> str:
    text = SKILL_FILE.read_text(encoding="utf-8")
    match = re.search(r"^\s*iwe_cli_version:\s*[\"']?([^\s\"']+)", text, re.MULTILINE)
    if not match:
        raise SystemExit(f"missing metadata.iwe_cli_version in {SKILL_FILE}")
    return match.group(1)


def run(*args: str) -> str:
    completed = subprocess.run(
        ["iwe", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.rstrip()


def render(version: str) -> str:
    actual = run("--version")
    expected = f"iwe {version}"
    if actual != expected:
        raise SystemExit(f"expected {expected!r}, got {actual!r}")

    sections = [
        f"# IWE {version} CLI Reference\n",
        f"This file is generated from the complete `--help` output of `iwe {version}`. ",
        "Use it when exact command syntax matters. The workflow-oriented references explain ",
        "when to use the commands; this file preserves the CLI contract.\n\n",
        "Regenerate or verify it with:\n\n",
        "```bash\n",
        "python3 skills/iwe-memory-system/scripts/generate-cli-reference.py\n",
        "python3 skills/iwe-memory-system/scripts/generate-cli-reference.py --check\n",
        "```\n",
        "\n## Contents\n\n",
    ]
    for command in COMMANDS:
        display = "iwe" if not command else "iwe " + " ".join(command)
        anchor = display.replace(" ", "-")
        sections.append(f"- [`{display}`](#{anchor})\n")
    for command in COMMANDS:
        display = "iwe" if not command else "iwe " + " ".join(command)
        help_args = ("--help",) if not command else (*command, "--help")
        sections.extend(
            [
                f"\n## `{display}`\n\n",
                "```text\n",
                run(*help_args),
                "\n```\n",
            ]
        )
    return "".join(sections)


def render_builtin_docs(version: str) -> str:
    sections = [
        f"# IWE {version} Built-in Reference\n\n",
        f"This file is generated from every topic exposed by `iwe {version} docs`. ",
        "It is bundled so an agent can use the complete query, configuration, and ",
        "document-schema contracts without internet access or exploratory CLI help.\n",
        "\n## Contents\n\n",
    ]
    for topic in DOC_TOPICS:
        sections.append(f"- [`{topic}`](#{topic})\n")
    for topic in DOC_TOPICS:
        sections.extend(
            [
                f"\n## `{topic}`\n\n",
                run("docs", topic),
                "\n",
            ]
        )
    return "".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the generated reference differs")
    args = parser.parse_args()

    version = adapted_version()
    generated = render(version)
    generated_builtin_docs = render_builtin_docs(version)
    if args.check:
        expected = {
            OUTPUT_FILE: generated,
            BUILTIN_DOCS_FILE: generated_builtin_docs,
        }
        stale = False
        for path, value in expected.items():
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            if existing == value:
                print(f"{path}: up to date for iwe {version}")
                continue
            stale = True
            sys.stdout.writelines(
                difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    value.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile="generated",
                )
            )
        if not stale:
            return 0
        return 1

    OUTPUT_FILE.write_text(generated, encoding="utf-8")
    BUILTIN_DOCS_FILE.write_text(generated_builtin_docs, encoding="utf-8")
    print(f"wrote {OUTPUT_FILE} and {BUILTIN_DOCS_FILE} from iwe {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
