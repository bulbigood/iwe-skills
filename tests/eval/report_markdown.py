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
    "tool_efficiency": "Tool-call efficiency",
    "resource_efficiency": "Token/resource efficiency",
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


def _profile_tables(target: dict) -> list[str]:
    profile = target["model_profile"]
    minimums = target["minimum_score"]
    required = target["required_success_percent"]
    lines = [
        f"## Evaluation profile — `{target['id']}`",
        "",
        f"- Model profile: **`{profile}`**",
        "",
        "| Metric | Minimum PASS score |",
        "| --- | ---: |",
    ]
    for name, label in METRIC_LABELS.items():
        lines.append(f"| {label} (`{name}`) | {minimums[name]}/5 |")
    lines.extend([
        "",
        "| Metric | Required success percent |",
        "| --- | ---: |",
    ])
    for name, label in METRIC_LABELS.items():
        lines.append(f"| {label} (`{name}`) | {required[name]}% |")
    lines.append("")
    return lines


def _aggregate_metric_tables(targets: dict[str, dict], outcomes: list[dict]) -> list[str]:
    target_ids = tuple(dict.fromkeys(outcome["target_id"] for outcome in outcomes))
    lines: list[str] = []
    for target_id in target_ids:
        target = targets[target_id]
        target_outcomes = [item for item in outcomes if item["target_id"] == target_id]
        heading = "## Aggregate metrics"
        if len(target_ids) > 1:
            heading += f" — `{target_id}`"
        lines.extend([
            heading,
            "",
            "| Metric | Passing samples | Minimum sample score | "
            "Required passing samples per scenario | Verdict |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for name, label in METRIC_LABELS.items():
            metrics = [outcome["metrics"][name] for outcome in target_outcomes]
            applicable = [metric for metric in metrics if metric.get("applicable", True)]
            if not applicable:
                lines.append(f"| {label} | — | — | — | N/A |")
                continue
            passing = sum(metric["successful_samples"] for metric in applicable)
            total = sum(metric["total_samples"] for metric in applicable)
            requirements = {
                (
                    metric["required_successes"],
                    metric["total_samples"],
                    metric["required_success_percent"],
                )
                for metric in applicable
            }
            if len(requirements) == 1:
                required, samples, percent = requirements.pop()
                requirement = f"{required}/{samples} ({percent}%)"
            else:
                requirement = "varies"
            passed = all(metric["pass"] for metric in applicable)
            lines.append(
                f"| {label} | {passing}/{total} | {target['minimum_score'][name]}/5 | "
                f"{requirement} | **{'PASS' if passed else 'FAIL'}** |"
            )
        lines.append("")
    return lines


def _format_deltas(values: list[int | float], *, precision: int | None = None) -> str:
    if precision is not None:
        return ", ".join(f"{value:.{precision}f}" for value in values)
    return ", ".join(str(value) for value in values)


def _comparison_tables(comparisons: list[dict]) -> list[str]:
    if not comparisons:
        return []
    lines = [
        "## Paired efficiency comparison",
        "",
        "Deltas are left target minus right target for valid paired cells; lower raw usage and time are better.",
        "No averaging is applied.",
        "",
    ]
    for comparison in comparisons:
        left = comparison["left_target_id"]
        right = comparison["right_target_id"]
        lines.extend([
            f"### `{comparison['scenario_id']}` — {left} − {right}",
            "",
            "| Judge metric | Left wins / ties / losses | Success-rate delta |",
            "| --- | ---: | ---: |",
        ])
        for name, metric in comparison["metrics"].items():
            if not metric.get("applicable", True):
                continue
            lines.append(
                f"| {METRIC_LABELS.get(name, name)} | {metric['left_wins']} / "
                f"{metric['ties']} / {metric['left_losses']} | "
                f"{metric['success_rate_delta_percentage_points']:+g} pp |"
            )
        efficiency = comparison["efficiency"]
        lines.extend([
            "",
            "| Raw paired diagnostic | Per-sample deltas |",
            "| --- | --- |",
            "| Worker wall time (seconds) | `"
            + _format_deltas(efficiency.get("worker_wall_seconds_deltas", []), precision=3)
            + "` |",
        ])
        raw_labels = {
            "task_tool_calls": "Task tool calls",
            "task_tool_output_bytes": "Task tool-output bytes",
            "estimated_task_input_tokens": "Estimated task-input tokens (bytes/4)",
        }
        for name, label in raw_labels.items():
            if name in efficiency.get("paired_deltas", {}):
                lines.append(
                    f"| {label} | `"
                    + _format_deltas(efficiency["paired_deltas"][name])
                    + "` |"
                )
        lines.extend([
            f"| Excluded invalid pairs | `{efficiency['excluded_cells']}` |",
            "",
        ])
    return lines


def _median_cell(value: int | float, *, seconds: bool = False) -> str:
    if seconds:
        return f"{value:.3f}"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _relative_change(baseline: int | float, comparison: int | float) -> str:
    if baseline == 0:
        return "N/A"
    return f"{(comparison - baseline) * 100 / baseline:+.1f}%"


def _performance_table(performance: dict[str, dict]) -> list[str]:
    if not performance:
        return []
    if len(performance) != 2:
        raise ValueError("performance comparison requires exactly two arms")
    baseline_id, comparison_id = performance
    baseline = performance[baseline_id]
    comparison = performance[comparison_id]
    lines = [
        "## Worker performance medians",
        "",
        "Medians use every worker sample across all selected scenarios. Token counts are provider-reported.",
        f"Change is `{comparison_id}` relative to `{baseline_id}`; positive values mean greater consumption.",
        "",
        f"| Metric | {baseline_id} median | {comparison_id} median | {comparison_id} change |",
        "| --- | ---: | ---: | ---: |",
    ]
    rows = (
        ("Input tokens", "input_tokens_median", False),
        ("Output tokens", "output_tokens_median", False),
        ("Tool calls", "tool_calls_median", False),
        ("Wall time (seconds)", "wall_seconds_median", True),
    )
    for label, field, seconds in rows:
        lines.append(
            f"| {label} | {_median_cell(baseline[field], seconds=seconds)} | "
            f"{_median_cell(comparison[field], seconds=seconds)} | "
            f"{_relative_change(baseline[field], comparison[field])} |"
        )
    lines.append(
        f"| Samples included | {baseline['samples']} | {comparison['samples']} | — |"
    )
    lines.append("")
    return lines


def _quality_comparison_table(
    outcomes: list[dict], target_ids: tuple[str, str]
) -> list[str]:
    baseline_id, comparison_id = target_ids
    lines = [
        "## Quality and efficiency acceptance",
        "",
        "Change is the passing-sample rate for the second arm minus the first arm, in percentage points.",
        "",
        f"| Metric | {baseline_id} | {comparison_id} | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    by_target = {
        target_id: [outcome for outcome in outcomes if outcome["target_id"] == target_id]
        for target_id in target_ids
    }
    for name, label in METRIC_LABELS.items():
        cells: list[tuple[int, int] | None] = []
        for target_id in target_ids:
            metrics = [outcome["metrics"][name] for outcome in by_target[target_id]]
            applicable = [metric for metric in metrics if metric.get("applicable", True)]
            if not applicable:
                cells.append(None)
            else:
                cells.append((
                    sum(metric["successful_samples"] for metric in applicable),
                    sum(metric["total_samples"] for metric in applicable),
                ))
        rendered = [
            "N/A" if cell is None else f"{cell[0]}/{cell[1]} ({cell[0] * 100 / cell[1]:.1f}%)"
            for cell in cells
        ]
        if None in cells:
            change = "N/A"
        else:
            baseline, comparison = cells
            assert baseline is not None and comparison is not None
            change = (
                f"{comparison[0] * 100 / comparison[1] - baseline[0] * 100 / baseline[1]:+.1f} pp"
            )
        lines.append(f"| {label} | {rendered[0]} | {rendered[1]} | {change} |")
    lines.append("")
    return lines


def _profile_metric_failures(report: dict) -> dict:
    profile = report.get("evaluation_profile")
    if isinstance(profile, dict) and isinstance(profile.get("metric_failures"), dict):
        return profile["metric_failures"]
    return report.get("verdict", {}).get("metric_failures", {})


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
            for name, detail in _profile_metric_failures(report).items()
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
        f"- Guidance accounting: `{experiment.get('guidance_accounting', 'exclude_activation')}`",
        f"- Worker scheduling: `{experiment.get('worker_scheduling', 'streaming')}`",
        "",
        "[Metric and score definitions](../../../docs/evaluation-metrics.md)",
        "",
    ]
    for target in targets.values():
        lines.extend(_profile_tables(target))
    outcomes = _outcomes_with_scenario_ids(summary["scenarios"], report_dir)
    lines.extend(_aggregate_metric_tables(targets, outcomes))
    if len(targets) == 2:
        lines.extend(_quality_comparison_table(outcomes, tuple(targets)))
    lines.extend(_performance_table(summary.get("performance", {})))
    lines.extend(_comparison_tables(summary.get("comparisons", [])))
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
