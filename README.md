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

- **`iwe-v18`** — maintained skill for IWE CLI `>=0.18.0`; tested with `0.18.0`. Skill version: `0.3.0`.
- **`iwe-memory-system` [deprecated]** — legacy workflow retained only for compatibility and A/B comparison. Skill version: `0.0.67`.

## Latest paired A/B snapshot

- **Scenario:** `discover-and-retrieve-bounded-multi-hop-context`
- **Paired samples per target:** `5`
- **Agent:** Codex CLI `0.146.0`; `gpt-5.6-terra`, medium reasoning
- **Judge:** `gpt-5.6-sol`, low reasoning

| Target | Skill version | IWE CLI | Overall | Valid | Procedure-clean (info) | Task correctness | Scenario compliance | Skill compliance | Safety | Evidence quality | Tool efficiency | Resource efficiency |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `iwe-v18` | `0.3.0` | `0.18.0` | **PASS** | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| `iwe-memory-system` | `0.0.67` | `0.18.0` | **FAIL** | 5/5 | 0/5 | 5/5 | 5/5 | 1/5 **(FAIL)** | 5/5 | 5/5 | 0/5 **(FAIL)** | 0/5 **(FAIL)** |

Every `N/5` value is a successful-, valid-, or clean-sample count as labelled, never an average score. See [metric and score definitions](docs/evaluation-metrics.md).

Reproduce the standard five-sample comparison:

```bash
python3 scripts/run_iwe_skill_ab_eval.py
```

[Full paired A/B results](tests/eval/results/2026-08-04-iwe-v18-vs-memory-system.md)

## Documentation

- [Performance design and measured results](docs/iwe-v18-performance-report.md)
- [Complete problem and solution catalog](docs/iwe-v18-case-catalog.md)
- [IWE 0.18.0 command inventory](docs/iwe-0.18.0-cli-help.md)
- [Evaluation metrics and score semantics](docs/evaluation-metrics.md)
- [Behavioral evaluation guide](tests/eval/README.md)
- [Runtime and contract maintenance](docs/maintainers.md)
- [Upstream provenance](docs/upstream-sources.md)
- [`config.toml` runtime and evaluation source of truth](config.toml)
