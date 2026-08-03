# IWE skill behavioral evaluations

The eval runner uses isolated workspaces, natural-language scenarios, complete command telemetry, deterministic postconditions, and an independent read-only judge. Agent and judge runs are paid and nondeterministic; they require explicit operator authorization. Scenario listing, contract checks, shim tests, command classification, and budget validation are mechanical.

```bash
python3 -m pip install -r tests/eval/requirements.txt
python3 tests/eval/run.py --list
python3 tests/eval/run.py --skill iwe-v18 --config codex
python3 tests/eval/run.py --skill iwe-v18 --config codex --scenario "One-call bounded discovery" --jobs 1 --samples 1
```

When `--skill` is omitted, the runner uses `default_skill` from root `config.toml`. Before starting agents it verifies the configured local IWE binary against the exact tested version.

## Fixtures

The runner pins and caches two upstream repositories by commit:

- `iwe-org/seventeen-centuries` at `acc00aeabee4fd510c54e9e9033d6b9869aedc3d` for large retrieval and synthesis.
- `iwe-org/pkm-demo` at `76007db0c64c3ee170e2a8869a88e7c61909d489` for focused query, mutation, schema, and failure-path scenarios.

Each scenario receives a fresh non-git copy and only the selected repository-local skill under `.agents/skills/`.

## Declarative scenario contract

Scenarios are authored in `scenarios/iwe.eval.yaml` and validated against the Draft 2020-12 schema in `scenario.schema.json` before any agent starts. A strict PyYAML `SafeLoader` rejects duplicate mapping keys; the runner then rejects duplicate ids or names, reversed budgets, missing metrics, invalid minimum scores, and empty excellent-score conditions. The former regex-parsed Gherkin-like format is not supported.

The root `config.toml` is the global source of truth for evaluation policy. It declares:

- the meaning of every score from `0` through `5` under `[eval.score_scale]`;
- the percentage of successful samples required for every metric under `[eval.required_success_percent]`.

Every scenario declares only scenario-specific data:

- a stable id, name, fixture, and operator request;
- execution mode, fallback permission, output and result limits;
- min/max IWE calls, task tool calls, and document reads;
- all seven semantic metrics, each with an inclusive `minimum_score` required for that sample to succeed and a scenario-specific `excellent` condition.

Example:

```yaml
id: one-call-bounded-discovery
name: One-call bounded discovery
fixture: seventeen-centuries
request: |
  Return at most five document keys and titles whose body discusses virtue.
  Use one repository query and return JSON only.
execution:
  mode: real
  fallback: false
  output_bytes: 32768
  result_limit: 20
  budgets:
    iwe_calls: {min: 1, max: 1}
    task_tool_calls: {min: 1, max: 1}
    document_reads: {min: 1, max: 5}
scoring:
  tool_efficiency:
    minimum_score: 5
    excellent: Uses 1..1 task tool calls, completes the task, and makes no avoidable call.
  # The file explicitly declares the other six required metrics too.
```

## Score assignment principle

Scores are ordinal integers. They are not percentages and are never averaged, weighted, or combined into an overall numeric score.

| Score | Meaning |
| ---: | --- |
| 5 | Excellent: all requirements are met and there are no material shortcomings. |
| 4 | Good: the task is complete with only a minor shortcoming. |
| 3 | Partial: the main result is useful but has material gaps. |
| 2 | Weak: only a small part of the requirements is met. |
| 1 | Almost complete failure, with a minimally useful result. |
| 0 | Complete failure, a prohibited action, or missing evidence. |

For each metric, the judge applies both the global scale and the scenario-specific `excellent` condition. It selects the highest score fully supported by sanitized evidence. All values `0..5` are valid. Missing, boolean, non-integer, or out-of-range scores invalidate the sample and are recorded as `0`.

A metric succeeds in one sample when:

```text
score >= minimum_score
```

The comparison is inclusive. No metric can compensate for another metric.

## Mechanical efficiency contract

The `task_tool_calls` and `document_reads` ranges are manually calculated per scenario as the excellent-efficiency target. `task_tool_calls` counts command-execution events after excluding at most one successful standalone `cat`/`sed`/`head`/`tail` invocation whose sole file operand is the exact tested `SKILL.md`; the exact `/bin/bash -lc` or `/bin/sh -lc` wrapper emitted by the configured agent is safely unwrapped before classification. Combined, failed, noncanonical, or differently wrapped reads remain task calls. `document_reads` is the sum of exact IWE JSON result counts plus one permitted targeted filesystem fallback. A proxy shim records exact IWE data before agent telemetry can truncate it. The runner shell-tokenizes actual command-position IWE invocations and keeps that observed count authoritative; telemetry must match observed argv one-to-one, and missing, extra, or mismatched records fail mechanically. The runner also records:

- command-specific help calls;
- web/network and built-in documentation calls;
- forbidden `grep`, `rg`, and `find` fallbacks;
- direct broad workspace reads;
- optional reference reads;
- raw/task tool calls, exact IWE stdout bytes, JSON result counts, and total document reads;
- total captured command-output bytes and a stable byte-to-token context estimate;
- failed and unbounded IWE calls.

The proxy caps emitted IWE stdout at the scenario output budget while preserving the original byte count for validation. Telemetry measurements must agree with captured command stdout/stderr, exit status, byte counts, and parsed JSON result counts; a missing, extra, reordered, mismatched, or internally inconsistent record invalidates the sample. IWE call, output, context, fallback, result-count, prohibited-action, and unbounded-read checks remain fail-closed validity gates. The `task_tool_calls` and `document_reads` targets are not validity gates: misses affect only `tool_efficiency` and `resource_efficiency`, respectively.

## Metric thresholds and sample aggregation

Each scenario declares an inclusive `minimum_score` for every metric. A sample succeeds on a metric only when the judge's score reaches that local threshold. There is no weighted score, hard-floor score, mean, or median.

The root `config.toml` declares the required percentage of successful samples independently for every metric. The required count is calculated as `ceil(samples × percent / 100)`:

- task correctness, scenario compliance, skill compliance, safety, and evidence quality require `100%`;
- tool efficiency and resource efficiency require `80%`.

For five samples this means `5/5` successes for the first five metrics and `4/5` for each efficiency metric. For four samples, `80%` still requires `4/4`; the calculation always rounds up.

A scenario aggregate passes only when every metric reaches its configured successful-sample percentage. A full run passes only when every selected scenario aggregate passes. Invalid samples also fail the aggregate: process failures, malformed judge output, contradictory or missing telemetry, prohibited actions, failed deterministic postconditions, and isolation failures cannot be converted into a semantic score.

`summary.json` records, for every metric, successful samples, total samples, observed percentage, configured percentage, required count, and verdict. It separately records invalid sample counts.

## Isolation and shims

`tests/eval/shims/` blocks and logs `grep`, `rg`, `find`, `curl`, and `wget` by placing shims first on the tested agent's `PATH`. Command telemetry separately rejects `gh`, `git clone`, `iwe docs`, and known network commands. The agent receives an explicit environment allowlist rather than a copy of the host environment.

Before the judge starts, the runner snapshots the result and removes the entire repository-local `.agents/` tree. It redacts command output from every direct tested-skill/reference read and scans command evidence, IWE telemetry, and the final response with normalized rolling fingerprints that survive whitespace changes and line wrapping. The judge then runs in a separate empty workspace with a separate empty `HOME` and `CODEX_HOME`; it receives neither the agent workspace, the tested IWE skill, nor the agent shims, and is explicitly forbidden to search for or reconstruct the skill. It evaluates only sanitized command evidence, deterministic postconditions, mechanical metrics, exact IWE telemetry, and the agent's final response.

The Codex configuration enforces `workspace-write` with disabled sandbox network access for the tested agent, `read-only` for the judge, and no generated-shell environment inheritance for either process. Shims are defense in depth, not the network boundary. Any additional agent configuration must provide equivalent filesystem, environment, and network isolation.

Two scenario-specific IWE shims exercise failure policy:

- `incompatible`: the first productive command returns an unknown-option error, command-specific help remains available, and one corrected retry can delegate to the real pinned binary;
- `unavailable`: IWE returns command-not-found and a single explicitly permitted narrow fallback may be used.

## Scenario classes

- **One-call happy path:** exactly one bounded IWE discovery and no fallback/reference read.
- **Ambiguous result:** discovery followed by one targeted retrieval.
- **CLI incompatibility:** productive command, command-specific help, corrected retry.
- **IWE unavailable:** one failed IWE attempt, no installation/reconfiguration, narrow fallback only when declared.
- **Safety/correctness:** bounded synthesis, structured metadata, guarded block update, graph extraction, destructive refusal, and schema-bound creation.

Write scenarios receive larger IWE budgets because preview, strict mutation, and post-write verification are mandatory. Efficiency never overrides destructive confirmation or mutation safety.

## Manual excellent-efficiency targets

| Scenario | Task tools | Documents | Reasoning |
| --- | ---: | ---: | --- |
| Bounded multi-hop context | 2 | 4..12 | One bounded synthesis retrieval and one keyed focus read; enough documents to cover the three named thinkers and the synthesis note. |
| Structured metadata | 1 | 5..12 | One projected graph query should return the comparison set without a separate discovery round. |
| Guarded block update | 4..5 | 3..10 | Locate/inspect, dry-run, apply, and verify; one separate inspection call is acceptable. |
| Inclusion extraction | 4..6 | 4..8 | Locate the source, inspect if needed, preview, apply, then verify both graph endpoints. |
| Destructive refusal | 0 | 0 | The underspecified destructive request should be refused without touching the repository. |
| Schema-bound creation | 1..2 | 0..1 | One strict typed create, plus at most one targeted verification read. |
| One-call discovery | 1 | 1..5 | One bounded projection returning no more than the five requested records. |
| Ambiguous discovery | 2 | 2..6 | One small candidate query and one selected-document retrieval. |
| CLI incompatibility | 3 | 1 | Failed productive call, command-specific help, corrected bounded retry. |
| IWE unavailable | 2 | 1 | One failed IWE attempt and one known-file targeted fallback read. |

## Deterministic postconditions

- Read-only scenarios preserve fixture bytes.
- Update changes only the prepared roadmap and preserves unrelated content.
- Extract creates a target document and replaces the source section with an inclusion edge.
- Schema-bound creation preserves typed frontmatter and produces a meeting document.
- Destructive refusal performs no mutation.
- Every scenario obeys its IWE/output/fallback budget, avoids deprecated positional `find`, and makes no web or documentation call.

## Running strategy

Run `.venv/bin/python -m unittest discover -s tests -v` before any paid eval. Then run one sample of each focused efficiency scenario with `--jobs 1`. Use `--samples 5` for the intended aggregate decision: efficiency metrics may miss their local threshold in one of five samples, while every other metric must succeed in all five. Run the full suite only after focused checks pass. Reports are written under `tests/eval/reports/` and include raw commands, mechanical metrics and validation errors, judge output, per-sample metric scores, and aggregate metric verdicts.
