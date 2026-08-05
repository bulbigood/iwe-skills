#!/usr/bin/env python3
"""Reaggregate immutable eval samples under a named model profile."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tests/eval/run.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("iwe_eval_acceptance_runner", RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError(f"cannot load evaluator: {RUNNER_PATH}")
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
sys.modules[RUNNER_SPEC.name] = RUNNER
RUNNER_SPEC.loader.exec_module(RUNNER)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path, help="immutable raw report directory")
    parser.add_argument("--output", type=Path, required=True, help="derived JSON output outside the source report")
    parser.add_argument(
        "--model-profile",
        choices=("medium", "weak"),
        required=True,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = RUNNER.load_eval_config()
    profile = RUNNER.resolve_model_profile(config, args.model_profile)
    replay = RUNNER.replay_saved_report(args.report, args.output, profile, config)
    print(json.dumps({
        "source_report": replay["source_report"],
        "model_profile": replay["model_profile"],
        "raw_samples": replay["raw_samples"],
        "passing_scenarios": sum(item["pass"] for item in replay["scenarios"]),
        "total_scenarios": len(replay["scenarios"]),
        "output": str(args.output.resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
