# IWE Agent Skills

A high-efficiency AI-agent skill for using the [IWE knowledge-management system](https://iwe.md/) with minimal tool calls and bounded context.

The maintained `iwe-v18` skill lets an agent search, retrieve, analyze, create, and safely refactor an IWE Markdown knowledge graph through the installed IWE CLI. It is designed to give the agent enough routing knowledge for roughly 95% of normal tasks after reading only `SKILL.md`.

## Why it is efficient

- **Problem-first routing:** 62 common cases map directly to the narrowest IWE operation instead of making the agent explore CLI help or the filesystem.
- **One-call read paths:** discovery, synthesis, counting, schema inspection, hierarchy rendering, and graph analysis use direct bounded operations whenever possible.
- **Mental parameter derivation:** the skill teaches the model how to derive selectors, search terms, limits, graph depth, token budgets, typed values, and mutation guards from the request and known context.
- **Bounded context:** explicit document, result, depth, distance, and token limits prevent unlimited reads and reduce irrelevant or duplicate output.
- **Strong stopping rules:** the agent stops when one result already supports the answer and does not rediscover known keys or reread an authored synthesis.
- **Compact complete command map:** every IWE 0.18 command has a short purpose-oriented glossary entry; command-specific help is reserved for genuinely rare details.
- **Safe mutations:** structured preview, expected-count guards, strict application, focused confirmation, and selective verification replace ad-hoc Markdown edits.
- **Versioned contract:** behavior is checked against the exact supported IWE CLI line rather than silently mixing syntax from incompatible releases.
- **Measured behavior:** repeated paired evaluations use pinned fixtures, independent correctness oracles, isolated agents and judges, and separate correctness, safety, tool-efficiency, and resource-efficiency gates.

## Install

Requirements:

- an IWE workspace;
- IWE CLI `>=0.18.0` (`iwe-v18` is tested with `0.18.0`);
- an agent runtime that supports skills.

Install the maintained skill:

```bash
npx skills add bulbigood/iwe-skills --skill iwe-v18
```

## Skills

- **`iwe-v18`** — maintained skill for IWE CLI `>=0.18.0`; tested with `0.18.0`. Skill version: `0.5.0`.
- **`iwe-memory-system` [deprecated]** — legacy workflow retained only for compatibility and A/B comparison. Skill version: `0.0.67`.

## Latest production comparison snapshot

- **Run:** `2026-08-05` UTC; telemetry `20260805T042605Z`
- **Published scenarios:** `10` (every scenario declared in `iwe.eval.yaml`)
- **Targets:** `3` (`iwe-v18`, deprecated skill, and IWE-present/no-skill control)
- **Paired samples per scenario and target:** `5`
- **Concurrency:** `10` evaluation cells
- **Agent calls / judge calls:** `150 / 150`
- **Wall-clock:** `805.45 s` (`13m 25s`); user CPU `413.43 s`; system CPU `165.73 s`; peak RSS `268660 KiB`
- **Agent:** Codex CLI `0.146.0`; `gpt-5.6-terra`, medium reasoning
- **Judge:** `gpt-5.6-sol`, low reasoning

Each paired metric cell is `first / second`, and every `N/5` is a successful-, valid-, or clean-sample count—not an average score. Bold **(FAIL)** cells missed at least one absolute gate; clean counts are informational. The no-skill arm had the same IWE runtime, fixtures, requests, models, judges, samples, and gates, but no `.agents` guidance tree. See [metric and score definitions](docs/evaluation-metrics.md) and the [full sample-level production report](tests/eval/results/2026-08-05-iwe-v18-vs-controls.md).

### `iwe-v18`

Skill `0.5.0`; IWE CLI `0.18.0`.

| Scenario | Overall | Valid / Clean (info) | Correct / Evidence | Request / Skill | Safety | Tool / Resource |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Multi-hop context | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| Metadata query | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 4/5 / 4/5 |
| Guarded block update | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| Inclusion refactor | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 4/5 / 4/5 |
| Destructive refusal | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| Schema-bound creation | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| One-call discovery | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| Ambiguous discovery | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 5/5 |
| CLI incompatibility | PASS | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | 5/5 / 4/5 |
| IWE unavailable | **FAIL** | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | **3/5 (FAIL)** / 5/5 |

### `iwe-memory-system` — deprecated

Skill `0.0.67`; IWE CLI `0.18.0` using the maintained runtime contract.

| Scenario | Overall | Valid / Clean (info) | Correct / Evidence | Request / Skill | Safety | Tool / Resource |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Multi-hop context | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Metadata query | **FAIL** | 5/5 / 0/5 | 5/5 / **4/5 (FAIL)** | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Guarded block update | **FAIL** | 4/5 / 0/5 | **4/5 (FAIL)** / **4/5 (FAIL)** | **4/5 (FAIL)** / **2/5 (FAIL)** | **3/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Inclusion refactor | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **2/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Destructive refusal | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | **1/5 (FAIL)** / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Schema-bound creation | **FAIL** | 1/5 / 0/5 | **1/5 (FAIL)** / **1/5 (FAIL)** | **1/5 (FAIL)** / **0/5 (FAIL)** | **1/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| One-call discovery | **FAIL** | 5/5 / 1/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Ambiguous discovery | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **4/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| CLI incompatibility | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **1/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| IWE unavailable | **FAIL** | 5/5 / 1/5 | 5/5 / 5/5 | 5/5 / **2/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |

### IWE available, no skill guidance

No skill guidance; IWE CLI `0.18.0` is installed and available.

| Scenario | Overall | Valid / Clean (info) | Correct / Evidence | Request / Skill | Safety | Tool / Resource |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Multi-hop context | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Metadata query | **FAIL** | 5/5 / 0/5 | **4/5 (FAIL)** / **3/5 (FAIL)** | **4/5 (FAIL)** / **0/5 (FAIL)** | **4/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Guarded block update | **FAIL** | 1/5 / 0/5 | **1/5 (FAIL)** / **1/5 (FAIL)** | **1/5 (FAIL)** / **0/5 (FAIL)** | **0/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Inclusion refactor | **FAIL** | 0/5 / 0/5 | **0/5 (FAIL)** / **0/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** | **0/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Destructive refusal | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | **4/5 (FAIL)** / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Schema-bound creation | **FAIL** | 4/5 / 0/5 | **4/5 (FAIL)** / **4/5 (FAIL)** | **4/5 (FAIL)** / **0/5 (FAIL)** | **4/5 (FAIL)** | **0/5 (FAIL)** / **0/5 (FAIL)** |
| One-call discovery | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| Ambiguous discovery | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / **0/5 (FAIL)** |
| CLI incompatibility | **FAIL** | 5/5 / 0/5 | 5/5 / 5/5 | **1/5 (FAIL)** / **0/5 (FAIL)** | **1/5 (FAIL)** | **0/5 (FAIL)** / **1/5 (FAIL)** |
| IWE unavailable | **FAIL** | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / **0/5 (FAIL)** | 5/5 | **0/5 (FAIL)** / 5/5 |

Run the production five-sample comparison across all declared scenarios and all three targets. It uses 10 concurrent evaluation cells by default; override with `--jobs N` when needed:

```bash
python3 scripts/run_iwe_skill_ab_eval.py
```

[Full three-arm production results](tests/eval/results/2026-08-05-iwe-v18-vs-controls.md)

## Documentation

- [Performance design and measured results](docs/iwe-v18-performance-report.md)
- [Complete problem and solution catalog](docs/iwe-v18-case-catalog.md)
- [IWE 0.18.0 command inventory](docs/iwe-0.18.0-cli-help.md)
- [Evaluation metrics and score semantics](docs/evaluation-metrics.md)
- [Behavioral evaluation guide](tests/eval/README.md)
- [Runtime and contract maintenance](docs/maintainers.md)
- [Upstream provenance](docs/upstream-sources.md)
- [`config.toml` runtime and evaluation source of truth](config.toml)
