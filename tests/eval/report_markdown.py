"""Deterministic Markdown rendering for paired evaluation summaries."""

from __future__ import annotations

import json
import os
from pathlib import Path


METRIC_LABELS = {
    "task_correctness": "Task correctness",
    "scenario_compliance": "Scenario compliance",
    "skill_compliance": "Skill compliance",
    "safety": "Safety",
    "evidence_quality": "Evidence quality",
    "tool_efficiency": "Tool efficiency",
    "resource_efficiency": "Resource efficiency",
}


def _cell(metric: dict) -> str:
    if not metric.get("applicable", True):
        return "—"
    value = f"{metric['successful_samples']}/{metric['total_samples']}"
    return value if metric["pass"] else f"{value} **(FAIL)**"


def _one_line(value: object) -> str:
    return " ".join(str(value).split())


def _skill_metadata_line(target: dict) -> str:
    if target.get("skill_mode") == "none":
        return "- Skill guidance: `none` (control)"
    return f"- Skill version: `{target['skill_version']}`"


def _relative_link(target: Path, report_path: Path | None) -> str:
    if report_path is None:
        return target.as_posix()
    return Path(os.path.relpath(target, report_path.parent)).as_posix()


def _sample_reports(report_dir: Path, outcome: dict) -> list[tuple[Path, dict]]:
    scenario_id = outcome.get("scenario_id")
    if not scenario_id:
        raise ValueError(f"scenario_id missing from outcome: {outcome.get('scenario')}")
    reports = []
    for sample in range(1, int(outcome["samples"]) + 1):
        path = (
            report_dir
            / "targets"
            / outcome["target_id"]
            / f"{scenario_id}--{sample}.json"
        )
        if not path.is_file():
            raise FileNotFoundError(f"expected sample telemetry report is missing: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report.get("target_id") != outcome["target_id"]
            or report.get("scenario_id") != scenario_id
            or report.get("sample") != sample
        ):
            raise ValueError(f"sample telemetry identity mismatch: {path}")
        reports.append((path, report))
    return reports


def _outcomes_with_scenario_ids(outcomes: list[dict], report_dir: Path) -> list[dict]:
    """Require stable IDs; scenario names are display labels only."""
    for outcome in outcomes:
        if not isinstance(outcome.get("scenario_id"), str) or not outcome["scenario_id"]:
            raise ValueError(f"scenario_id missing from outcome: {outcome.get('scenario')}")
    return outcomes


def _problem_lines(
    reports: list[tuple[Path, dict]],
    report_path: Path | None,
    excluded_metrics: set[str] | None = None,
) -> list[str]:
    excluded_metrics = excluded_metrics or set()
    problems = []
    for telemetry_path, report in reports:
        verdict = report.get("verdict", {})
        validation_errors = verdict.get("validation_errors", [])
        procedure_errors = verdict.get("procedure_errors", [])
        metric_failures = {
            name: detail
            for name, detail in verdict.get("metric_failures", {}).items()
            if name not in excluded_metrics
        }
        if verdict.get("valid") and not validation_errors and not procedure_errors and not metric_failures:
            continue
        problems.append((
            telemetry_path,
            report,
            verdict,
            validation_errors,
            procedure_errors,
            metric_failures,
        ))

    lines = ["", "### Problem ledger", ""]
    if not problems:
        return [*lines, "No sample-level problems detected.", ""]

    lines.extend([
        "Every invalid sample, procedural violation, and failed metric is listed below. "
        "The linked raw JSON contains the complete agent transcript, IWE telemetry, "
        "independent oracle, judge output, and deterministic verdict.",
        "",
    ])
    for (
        telemetry_path,
        report,
        verdict,
        validation_errors,
        procedure_errors,
        metric_failures,
    ) in problems:
        sample = report["sample"]
        critique = verdict.get("critique") or {}
        lines.extend([
            f"#### Sample {sample}",
            "",
            f"- Telemetry: [raw sample JSON]({_relative_link(telemetry_path, report_path)})",
            f"- Valid: **{'yes' if verdict.get('valid') else 'no'}**",
        ])
        rationale = critique.get("rationale")
        if rationale:
            lines.append(f"- Analysis: {_one_line(rationale)}")
        else:
            lines.append(
                "- Analysis: No valid judge critique was available; the deterministic "
                "validation and procedure diagnostics below are authoritative."
            )
        if validation_errors:
            lines.append("- Validation problems:")
            lines.extend(f"  - {_one_line(error)}" for error in validation_errors)
        if procedure_errors:
            lines.append("- Procedure problems:")
            lines.extend(f"  - {_one_line(error)}" for error in procedure_errors)
        if metric_failures:
            lines.append("- Failed metrics:")
            dimensions = critique.get("dimensions", {})
            for name, failure in metric_failures.items():
                detail = dimensions.get(name, {})
                label = METRIC_LABELS.get(name, name)
                score = failure.get("score", detail.get("score", "?"))
                required = failure.get("required", "?")
                lines.append(f"  - **{label}: {score}/5 (required {required}/5).**")
                if failure.get("deterministic"):
                    lines.append(
                        f"    - Deterministic gate: {_one_line(failure['deterministic'])}"
                    )
                if detail.get("rationale"):
                    lines.append(f"    - Analysis: {_one_line(detail['rationale'])}")
                evidence = detail.get("evidence", [])
                if evidence:
                    lines.append("    - Evidence:")
                    lines.extend(f"      - {_one_line(item)}" for item in evidence)
        lines.append("")
    return lines


def render_markdown(
    experiment: dict,
    summary: dict,
    report_dir: Path,
    report_path: Path | None = None,
) -> str:
    targets = {target["id"]: target for target in experiment["targets"]}
    lines = [
        "<!-- Generated by tests/eval/report_markdown.py; do not edit manually. -->",
        "",
        f"# Paired evaluation result — {experiment['name']}",
        "",
        "## Run configuration",
        "",
        f"- Scenarios tested: `{', '.join(experiment['scenarios'])}`",
        f"- Paired samples per target: `{experiment['samples']}`",
        f"- Agent: {experiment['agent']['name']} `{experiment['agent']['version']}`",
        f"- AI model: `{experiment['agent']['model']}`; reasoning: `{experiment['agent']['reasoning']}`",
        f"- Judge AI model: `{experiment['judge']['model']}`; reasoning: `{experiment['judge']['reasoning']}`",
        f"- Agent calls: `{experiment['estimated_agent_calls']}`",
        f"- Judge calls: `{experiment['estimated_judge_calls']}`",
        f"- Agent/judge configuration: `{experiment['agent_judge_config']}`",
        "",
        "[Metric and score definitions](../../../docs/evaluation-metrics.md)",
        "",
    ]
    outcomes = _outcomes_with_scenario_ids(summary["scenarios"], report_dir)
    for outcome in outcomes:
        target = targets[outcome["target_id"]]
        runtime = target["runtime"]
        procedure_clean = outcome.get("samples", 0) - outcome.get("procedure_failure_samples", 0)
        lines.extend([
            f"## {outcome['scenario']} — `{outcome['target_id']}`",
            "",
            _skill_metadata_line(target),
            f"- IWE CLI version: `{runtime['version']}`",
            f"- Samples: `{outcome['samples']}`",
            f"- Overall: **{'PASS' if outcome['pass'] else 'FAIL'}**",
            f"- Valid samples: `{outcome['samples'] - outcome['invalid_samples']}/{outcome['samples']}`",
            "",
            "| Metric | Successful samples | Required samples | Verdict | Score histogram |",
            "| --- | ---: | ---: | --- | --- |",
            f"| Procedure-clean | {procedure_clean}/{outcome['samples']} | — | Informational | — |",
        ])
        for name, label in METRIC_LABELS.items():
            metric = outcome["metrics"][name]
            if not metric.get("applicable", True):
                lines.append(f"| {label} | — | — | N/A | — |")
                continue
            histogram = ", ".join(
                f"{score}: {count}" for score, count in metric["score_histogram"].items() if count
            ) or "none"
            lines.append(
                f"| {label} | {_cell(metric)} | {metric['required_successes']}/{metric['total_samples']} "
                f"| **{'PASS' if metric['pass'] else 'FAIL'}** | `{histogram}` |"
            )
        errors = outcome.get("procedure_error_counts", {})
        if errors:
            lines.extend(["", "### Procedure errors", "", "| Error | Samples |", "| --- | ---: |"])
            lines.extend(f"| {error} | {count}/{outcome['samples']} |" for error, count in errors.items())
        excluded_metrics = {
            name for name, metric in outcome["metrics"].items()
            if not metric.get("applicable", True)
        }
        lines.extend(_problem_lines(
            _sample_reports(report_dir, outcome), report_path, excluded_metrics
        ))
    lines.extend([
        "## Artifacts",
        "",
        f"[Machine-readable report directory]({_relative_link(report_dir, report_path)})",
        "",
    ])
    return "\n".join(lines)


def write_markdown(path: Path, experiment: dict, summary: dict, report_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        render_markdown(experiment, summary, report_dir, report_path=path),
        encoding="utf-8",
    )
    temporary.replace(path)
