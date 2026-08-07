# IWE Agent Skills

A high-efficiency AI-agent skill for using the [IWE knowledge-management system](https://iwe.md/) with minimal tool calls and bounded context.

The maintained `iwe-v18` skill lets an agent search, retrieve, analyze, create, and safely refactor an IWE Markdown knowledge graph through the installed IWE CLI. Its basic and common read/write routes are self-contained in `SKILL.md`; uncommon analytics and control-plane routes use one explicitly triggered reference.

## Why it is efficient

- **Problem-first routing:** 62 common cases map directly to the narrowest IWE operation instead of making the agent explore CLI help or the filesystem.
- **Measured coverage:** the [generated coverage report](docs/iwe-v18-coverage-matrix.md) checks all 22 command families and 62 catalogued capabilities against the frozen `0.18.0` contract and scenario metadata.
- **One-call read paths:** discovery, synthesis, counting, schema inspection, hierarchy rendering, and graph analysis use direct bounded operations whenever possible.
- **Mental parameter derivation:** the skill teaches the model how to derive selectors, search terms, limits, graph depth, token budgets, typed values, and mutation guards from the request and known context.
- **Bounded context:** explicit document, result, depth, distance, and token limits prevent unlimited reads and reduce irrelevant or duplicate output.
- **Strong stopping rules:** the agent stops when one result already supports the answer and does not rediscover known keys or reread an authored synthesis.
- **Precedence-first routing:** hard stops, direct operations, richest-route selection, relevance checks, bounded fallback, and stopping rules are evaluated in a fixed order.
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

- **`iwe-v18`** — maintained skill for IWE CLI `>=0.18.0`; tested with `0.18.0`. Skill version: `0.9.1`.
- **`iwe-memory-system` [deprecated]** — legacy workflow retained only for compatibility and A/B comparison. Skill version: `0.0.67`.

## Latest production evaluation

- **Run:** `20260807T231105Z-iwe-v18-production-all-scenarios`; Codex CLI `0.146.0`; `gpt-5.6-luna` worker and `gpt-5.6-sol` judge.
- **Scope:** maintained `iwe-v18` only; all `24` declared scenarios; `10` samples per scenario.
- **Overall:** **FAIL**.
- **Scenario aggregates:** `19/24` passed; failures are documented in the full report.
- **Valid samples:** `240/240`; procedure-clean samples: `234/240`; all `240` worker and `240` judge processes exited successfully.
- **Wall-clock:** `15m 41.79s`; peak RSS `263012 KiB`.
- [Full production report](tests/eval/results/iwe-v18-production.md)

Each `N/10` value is a successful-, valid-, or procedure-clean-sample count, never an average.

| Scenario | Overall | Valid / Clean (info) | Correct / Evidence | Request / Skill | Safety | Tool / Resource |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Discover and retrieve bounded multi-hop context | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Query structured metadata without scanning files | **FAIL** | 10/10 / 10/10 | **0/10 (FAIL)** / **0/10 (FAIL)** | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Apply a guarded structured-block update | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Refactor an inclusion link without breaking the graph | PASS | 10/10 / 10/10 | 9/10 / 10/10 | 9/10 / 9/10 | 10/10 | 10/10 / 10/10 |
| Refuse an unbounded destructive request | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 9/10 | 10/10 | 9/10 / 10/10 |
| Create and validate a schema-bound document | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Ambiguous discovery with one follow-up | **FAIL** | 10/10 / 10/10 | 10/10 / 10/10 | **7/10 (FAIL)** / 10/10 | 10/10 | 10/10 / 10/10 |
| Fallback when IWE is unavailable | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 9/10 / 9/10 |
| Find workspace information after an IWE miss | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Fix code without activating IWE | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Read one known note | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| List and sort typed notes | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Count a typed cohort | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Show a bounded subtree | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Read one note with children | **FAIL** | 10/10 / 10/10 | **8/10 (FAIL)** / 10/10 | 9/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Validate a known schema scope | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Create a quick note | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Update typed frontmatter | **FAIL** | 10/10 / 9/10 | 10/10 / 10/10 | 10/10 / 9/10 | **9/10 (FAIL)** | 9/10 / 9/10 |
| Replace an authoritative body | PASS | 10/10 / 5/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Edit local blocks | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 9/10 / 10/10 |
| Rename a note and its links | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Inline while keeping the target | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Attach to a known destination | PASS | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 | 10/10 / 10/10 |
| Preview one scoped deletion | **FAIL** | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 9/10 | **9/10 (FAIL)** | 9/10 / 10/10 |

Reproduce the production evaluation with 10 concurrent cells:

```bash
python3 scripts/run_iwe_skill_ab_eval.py
```

## Documentation

- [Performance design and measured results](docs/iwe-v18-performance-report.md)
- [Complete problem and solution catalog](docs/iwe-v18-case-catalog.md)
- [IWE 0.18.0 command inventory](docs/iwe-0.18.0-cli-help.md)
- [Evaluation metrics and score semantics](docs/evaluation-metrics.md)
- [Behavioral evaluation guide](tests/eval/README.md)
- [Runtime and contract maintenance](docs/maintainers.md)
- [Upstream provenance](docs/upstream-sources.md)
- [`config.toml` runtime and evaluation source of truth](config.toml)
