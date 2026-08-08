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
npx skills add iwe-org/skills --skill iwe-v18
```

## Skills

- **`iwe-v18`** — maintained skill for IWE CLI `>=0.18.0`; tested with `0.18.0`. Skill version: `0.9.9`.
- **`iwe-memory-system` [deprecated]** — legacy workflow retained only for compatibility and A/B comparison. Skill version: `0.0.67`.

## Latest production evaluation

- **Run:** `20260808T111334Z`; weak production profile.
- **Scope:** maintained `iwe-v18` only; all `32` declared scenarios; `10` samples per scenario.
- **Overall:** **PASS — `32/32` scenario aggregates**.
- **Integrity:** `320/320` valid samples; safety `320/320`.
- **Execution:** `320` worker calls and `320` judge calls.
- [Full production report](tests/eval/results/iwe-v18-production.md)

Reproduce the production evaluation with 10 concurrent cells:

```bash
python3 scripts/run_iwe_skill_ab_eval.py
```

## Latest guidance-efficiency A/B evaluation

- **Run:** `20260808T164507Z`; `iwe-v18` guidance versus the same IWE `0.18.0` runtime without skill guidance.
- **Scope:** 3 retrieval-heavy scenarios, 10 samples per arm and scenario; `60` worker calls and `60` judge calls in six balanced 10-worker waves. Guidance activation and reference reads are included in the guided arm's costs.
- **Quality:** `iwe-v18` passed all 3 scenario aggregates; the no-guidance arm failed all 3 on efficiency. `59/60` samples were valid; one no-guidance sample was invalidated for a prohibited documentation command.
- **Worker timing:** guidance was faster in `26/30` matched pairs; median paired saving `11.6 s` and mean saving `17.2 s` (stratified bootstrap 95% CI for the mean: `13.8–20.6 s`). Arm-level no-guidance wall-time overhead was `+66.1%` by median and `+78.9%` by mean.
- [Full guidance-efficiency A/B report](tests/eval/results/iwe-v18-guidance-efficiency-ab.md)

Reproduce the focused A/B evaluation:

```bash
python3 scripts/run_iwe_guidance_efficiency_ab.py
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
