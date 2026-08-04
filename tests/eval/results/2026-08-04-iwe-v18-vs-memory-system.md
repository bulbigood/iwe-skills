# IWE skill paired A/B result — 2026-08-04

## Run configuration

- Scenario: `Discover and retrieve bounded multi-hop context`
- Paired samples: `5`
- Agent calls: `10`
- Judge calls: `10`
- Current target: `iwe-v18` skill `0.2.0` with IWE CLI `0.18.0`
- Legacy target: `iwe-memory-system` skill `0.0.67` with IWE CLI `0.18.0`
- Shared inputs: agent/judge configuration, prompt, fixture, independent oracle, metrics, thresholds, and pair identities
- Reproduction command: `python3 scripts/run_iwe_skill_ab_eval.py`

The stored judge outputs were reclassified under the current independent result/procedure aggregation model. No additional paid calls were made for the reclassification.

## Aggregate results

| Target | Result verdict | Procedure verdict | Overall | Valid samples | Procedure-clean | Task correctness | Scenario compliance | Skill compliance | Safety | Evidence quality | Tool efficiency | Resource efficiency |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `iwe-v18` | **PASS** | **FAIL** | **FAIL** | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 3/5 | 2/5 |
| `iwe-memory-system` | **PASS** | **FAIL** | **FAIL** | 5/5 | 0/5 | 5/5 | 5/5 | 0/5 | 5/5 | 5/5 | 0/5 | 0/5 |

Required successful samples were `5/5` for task correctness, scenario compliance, skill compliance, safety, and evidence quality, and `4/5` for tool and resource efficiency.

## Score histograms

Histogram keys are judge scores `0..5`; values are sample counts.

### `iwe-v18`

| Metric | Histogram |
| --- | --- |
| Task correctness | `5: 5` |
| Scenario compliance | `5: 5` |
| Skill compliance | `5: 5` |
| Safety | `5: 5` |
| Evidence quality | `4: 1, 5: 4` |
| Tool efficiency | `3: 1, 4: 1, 5: 3` |
| Resource efficiency | `3: 1, 4: 2, 5: 2` |

### `iwe-memory-system`

| Metric | Histogram |
| --- | --- |
| Task correctness | `5: 5` |
| Scenario compliance | `5: 5` |
| Skill compliance | `2: 4, 3: 1` |
| Safety | `5: 5` |
| Evidence quality | `4: 1, 5: 4` |
| Tool efficiency | `1: 2, 2: 2, 4: 1` |
| Resource efficiency | `0: 1, 1: 3, 2: 1` |

## Legacy procedure failures

All five legacy samples had procedure failures without result-integrity failures:

| Procedure error | Affected samples |
| --- | ---: |
| Deprecated positional `iwe find` query | 5/5 |
| Unbounded IWE discovery or retrieval | 5/5 |
| Telemetry measurements conflicted with observed command evidence | 5/5 |
| Telemetry arguments did not match observed command invocations | 3/5 |
| Telemetry was missing for an observed invocation | 3/5 |
| IWE output exceeded the configured capture budget | 2/5 |

The legacy answers remained correct, safe, scenario-compliant, and supported by the independent fixture oracle. The procedure failures are therefore reported through skill compliance, tool efficiency, resource efficiency, and explicit `procedure_errors`; they do not erase result-quality scores.

## Artifacts

The original per-sample reports, agent events, commands, judge evidence, independent oracle snapshots, runtime provenance, and pairwise telemetry remain in the gitignored local report directory:

`tests/eval/reports/20260804T094536Z-iwe-v18-vs-memory-multihop/`
