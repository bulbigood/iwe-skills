#!/usr/bin/env python3
"""Run the production behavioral evaluation for config.toml's default skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = 5


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("samples must be at least 1")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all behavioral scenarios for config.toml's default_skill with production settings."
    )
    parser.add_argument(
        "--samples",
        type=positive_int,
        default=DEFAULT_SAMPLES,
        help=f"paired repetitions per scenario (default: {DEFAULT_SAMPLES})",
    )
    return parser.parse_args(argv)


def build_command(samples: int) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tests/eval/run.py"),
        "--config",
        "codex",
        "--samples",
        str(samples),
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return subprocess.call(build_command(args.samples), cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
