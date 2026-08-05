# Paired skill/runtime experiments

An experiment compares **skill payload + exact IWE runtime** targets. It does not measure a skill independently of its runtime.

```toml
schema_version = 1
name = "three-target-check"
scenarios = ["query-structured-metadata-without-scanning-files"]
samples = 5
jobs = 3
agent_judge_config = "codex"

[[targets]]
id = "candidate-a"
skill_path = "skills/iwe-v18"
skill_version = "0.4.0"
contract_file = "contracts/iwe-v18.json"
[targets.runtime]
cli = "iwe"
source = "directory"
directory = ".runtimes/iwe-0.18.0/bin"
version = "0.18.0"
```

Repeat `[[targets]]` for any `N >= 2` targets. IDs and scenarios must be unique; `samples` and `jobs` must be positive. Skill and contract paths must exist inside the repository. Runtime `version` is exact `x.y.z`, never a range. Matrix experiments require an explicit `directory` source so several installed versions cannot silently resolve to the same package-manager executable. The directory may be absent while listing, but its executable must exist and print exactly `iwe <version>` before execution starts.

The same skill path may be declared more than once to isolate runtime effects. Each target owns its complete runtime declaration; there is no global or inherited IWE version.

```bash
.venv/bin/python tests/eval/run.py --experiment tests/eval/experiments/example.toml --list
.venv/bin/python tests/eval/run.py --experiment tests/eval/experiments/example.toml
# Narrow the manifest's scenarios; samples/jobs still come from the manifest:
.venv/bin/python tests/eval/run.py --experiment tests/eval/experiments/example.toml --scenario query-structured-metadata-without-scanning-files
```

Before a paid run, budget `N × selected scenarios × X` agent calls and the same number of judge calls. `jobs` is one global concurrency bound, not a per-target limit.

Every `(scenario_id, sample_index)` is a pair shared by all targets. Targets use the same pinned fixture, request, independent fixture-snapshot oracle, judge configuration, seven metrics, rubrics, scale, and thresholds, while receiving isolated workspaces, HOME/state, skill payloads, and verified runtime binaries. Invalid cells remain visible and count as failures; missing or duplicate cells fail closed.

Each target gets its own absolute PASS/FAIL. Pairwise reports show threshold wins/ties/losses, validity counts, percentage-point success differences, raw `0..5` histograms, and valid-on-both efficiency deltas with exclusions. A relative win cannot turn an absolute FAIL into PASS. Ordinal scores must not be averaged or summarized with means, medians, weighted totals, or a single “best target” score.

Reports are separated under `reports/<timestamp>-<experiment>/targets/<target-id>/`; normalized provenance is in `experiment.json`, absolute outcomes in target summaries, and pairwise evidence under `comparisons/`.
