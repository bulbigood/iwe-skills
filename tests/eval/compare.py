"""Pure fail-closed paired comparison for evaluation results."""
from __future__ import annotations

import itertools
from collections import Counter


def _histogram(rows, metric):
    counts = Counter(row["verdict"].get("metric_scores", {}).get(metric, 0) for row in rows)
    return {str(score): counts[score] for score in range(6)}


def compare_results(
    results: list[dict],
    target_ids: tuple[str, ...],
    dimensions: tuple[str, ...],
    expected_pairs: dict[tuple[str, int], str] | None = None,
) -> list[dict]:
    by_target = {target: {} for target in target_ids}
    for row in results:
        target = row["target_id"]
        if target not in by_target:
            raise ValueError(f"unknown target result: {target}")
        key = (row["scenario_id"], row["sample"])
        if key in by_target[target]:
            raise ValueError(f"duplicate pairing cell: {target} {key}")
        by_target[target][key] = row
    key_sets = {target: set(rows) for target, rows in by_target.items()}
    if len({frozenset(keys) for keys in key_sets.values()}) != 1:
        raise ValueError(f"mismatched pairing-key sets: {key_sets}")
    if expected_pairs is not None:
        expected_keys = set(expected_pairs)
        for target, keys in key_sets.items():
            if keys != expected_keys:
                raise ValueError(
                    f"missing expected pairing cells for {target}: "
                    f"missing={sorted(expected_keys - keys)} unexpected={sorted(keys - expected_keys)}"
                )
    for key in next(iter(key_sets.values()), set()):
        pair_ids = {by_target[target][key].get("pair_id") for target in target_ids}
        expected_pair_id = expected_pairs.get(key) if expected_pairs is not None else None
        if len(pair_ids) != 1 or None in pair_ids or (
            expected_pairs is not None and pair_ids != {expected_pair_id}
        ):
            raise ValueError(f"conflicting pair_id provenance for {key}: {sorted(map(str, pair_ids))}")

    output = []
    for left, right in itertools.combinations(target_ids, 2):
        for scenario in sorted({key[0] for key in key_sets[left]}):
            keys = sorted(key for key in key_sets[left] if key[0] == scenario)
            left_rows = [by_target[left][key] for key in keys]
            right_rows = [by_target[right][key] for key in keys]
            metrics = {}
            for metric in dimensions:
                left_success = [row["verdict"].get("valid", False) and metric not in row["verdict"].get("metric_failures", {}) for row in left_rows]
                right_success = [row["verdict"].get("valid", False) and metric not in row["verdict"].get("metric_failures", {}) for row in right_rows]
                metrics[metric] = {
                    "left_wins": sum(a and not b for a, b in zip(left_success, right_success)),
                    "ties": sum(a == b for a, b in zip(left_success, right_success)),
                    "left_losses": sum(not a and b for a, b in zip(left_success, right_success)),
                    "success_rate_delta_percentage_points":
                        (sum(left_success) - sum(right_success)) * 100 / len(keys),
                    "score_histograms": {left: _histogram(left_rows, metric), right: _histogram(right_rows, metric)},
                }
            valid_pairs = [(a, b) for a, b in zip(left_rows, right_rows)
                           if a["verdict"].get("valid", False) and b["verdict"].get("valid", False)]
            efficiency_names = sorted(set.intersection(*[
                {name for name, value in row.get("agent", {}).get("metrics", {}).items()
                 if isinstance(value, int) and not isinstance(value, bool)}
                for pair in valid_pairs for row in pair
            ])) if valid_pairs else []
            output.append({
                "left_target_id": left, "right_target_id": right, "scenario_id": scenario,
                "paired_cells": len(keys),
                "invalid_cells": {
                    left: sum(not row["verdict"].get("valid", False) for row in left_rows),
                    right: sum(not row["verdict"].get("valid", False) for row in right_rows),
                },
                "efficiency": {
                    "excluded_cells": len(keys) - len(valid_pairs),
                    "paired_deltas": {
                        name: [a["agent"]["metrics"][name] - b["agent"]["metrics"][name]
                               for a, b in valid_pairs]
                        for name in efficiency_names
                    },
                },
                "metrics": metrics,
            })
    return output
