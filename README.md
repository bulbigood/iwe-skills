1|# IWE Agent Skills
2|
3|A high-efficiency AI-agent skill for using the [IWE knowledge-management system](https://iwe.md/) with minimal tool calls and bounded context.
4|
5|The maintained `iwe-v18` skill lets an agent search, retrieve, analyze, create, and safely refactor an IWE Markdown knowledge graph through the installed IWE CLI. Its basic and common read/write routes are self-contained in `SKILL.md`; uncommon analytics and control-plane routes use one explicitly triggered reference.
6|
7|## Why it is efficient
8|
9|- **Problem-first routing:** 62 common cases map directly to the narrowest IWE operation instead of making the agent explore CLI help or the filesystem.
10|- **Measured coverage:** the [generated coverage report](docs/iwe-v18-coverage-matrix.md) checks all 22 command families and 62 catalogued capabilities against the frozen `0.18.0` contract and scenario metadata.
11|- **One-call read paths:** discovery, synthesis, counting, schema inspection, hierarchy rendering, and graph analysis use direct bounded operations whenever possible.
12|- **Mental parameter derivation:** the skill teaches the model how to derive selectors, search terms, limits, graph depth, token budgets, typed values, and mutation guards from the request and known context.
13|- **Bounded context:** explicit document, result, depth, distance, and token limits prevent unlimited reads and reduce irrelevant or duplicate output.
14|- **Strong stopping rules:** the agent stops when one result already supports the answer and does not rediscover known keys or reread an authored synthesis.
15|- **Precedence-first routing:** hard stops, direct operations, richest-route selection, relevance checks, bounded fallback, and stopping rules are evaluated in a fixed order.
16|- **Safe mutations:** structured preview, expected-count guards, strict application, focused confirmation, and selective verification replace ad-hoc Markdown edits.
17|- **Versioned contract:** behavior is checked against the exact supported IWE CLI line rather than silently mixing syntax from incompatible releases.
18|- **Measured behavior:** repeated paired evaluations use pinned fixtures, independent correctness oracles, isolated agents and judges, and separate correctness, safety, tool-efficiency, and resource-efficiency gates.
19|
20|## Install
21|
22|Requirements:
23|
24|- an IWE workspace;
25|- IWE CLI `>=0.18.0` (`iwe-v18` is tested with `0.18.0`);
26|- an agent runtime that supports skills.
27|
28|Install the maintained skill:
29|
30|```bash
31|npx skills add bulbigood/iwe-skills --skill iwe-v18
32|```
33|
34|## Skills
35|
36|- **`iwe-v18`** — maintained skill for IWE CLI `>=0.18.0`; tested with `0.18.0`. Skill version: `0.9.1`.
37|- **`iwe-memory-system` [deprecated]** — legacy workflow retained only for compatibility and A/B comparison. Skill version: `0.0.67`.
38|
39|## Latest production evaluation

- **Run:** `20260807T231105Z-iwe-v18-production-all-scenarios`; Codex CLI `0.146.0`; `gpt-5.6-luna` worker and `gpt-5.6-sol` judge.
- **Scope:** maintained `iwe-v18` only; all `24` declared scenarios; `10` samples per scenario.
- **Overall:** **FAIL**.
- **Scenario aggregates:** `19/24` passed; failures are documented in the full report.
- **Valid samples:** `240/240`; procedure-clean samples: `234/240`; all `240` worker and `240` judge processes exited successfully.
- **Wall-clock:** `15m 41.79s`; peak RSS `263012 KiB`.
- [Full production report](tests/eval/results/iwe-v18-production.md)

Reproduce the production evaluation with 10 concurrent cells:

```bash
python3 scripts/run_iwe_skill_ab_eval.py
```

## Documentation
117|
118|- [Performance design and measured results](docs/iwe-v18-performance-report.md)
119|- [Complete problem and solution catalog](docs/iwe-v18-case-catalog.md)
120|- [IWE 0.18.0 command inventory](docs/iwe-0.18.0-cli-help.md)
121|- [Evaluation metrics and score semantics](docs/evaluation-metrics.md)
122|- [Behavioral evaluation guide](tests/eval/README.md)
123|- [Runtime and contract maintenance](docs/maintainers.md)
124|- [Upstream provenance](docs/upstream-sources.md)
125|- [`config.toml` runtime and evaluation source of truth](config.toml)
126|