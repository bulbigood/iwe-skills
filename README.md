# IWE Agent Skills

A collection of versioned AI-agent skills for working with [IWE](https://iwe.md/) knowledge-graph projects.

These skills help AI agents manage projects backed by an installed IWE system efficiently and safely. They favor bounded, graph-aware IWE operations over broad filesystem scans, unnecessary context loading, ad-hoc Markdown edits, and external lookups. The goal is predictable project discovery, focused retrieval, evidence-backed answers, and safe structural refactoring with few tool calls.

## What this repository is for

Use these skills when an AI agent needs to work inside an IWE Markdown workspace—for example, to:

- discover and retrieve relevant project context;
- navigate document keys, links, inclusions, and graph relationships;
- query structured frontmatter;
- create or update schema-aware notes;
- perform guarded structural refactors;
- preserve unrelated content and avoid unsafe broad mutations;
- keep tool calls, document reads, and model context bounded.

The repository freezes agent-facing behavior against a specific IWE CLI line. This avoids silently teaching an agent commands from an incompatible IWE release.

## Available skills

- **`iwe-v18`** — Supports IWE CLI `>=0.18.0`; tested with `0.18.0`. This is the current, supported skill for bounded retrieval, graph-aware project work, and safe Markdown refactoring. Skill version: `0.2.0`.
- **`iwe-memory-system` [deprecated]** — Legacy, unversioned IWE workflow skill. It does not declare a supported IWE CLI range and is retained only for compatibility and historical reference. Do not use it for new projects; use `iwe-v18` instead. Skill version: `0.0.67`.

## Requirements

- An IWE workspace with IWE installed locally.
- For `iwe-v18`, IWE CLI version `>=0.18.0`.
- An AI-agent runtime that can load repository or user skills.

The skills do not install, update, configure, or repair IWE. Runtime availability remains the operator's responsibility.

## Installation

Install the current skill with the Skills CLI:

```bash
npx skills add bulbigood/iwe-skills --skill iwe-v18
```

Then make the skill available to the agent working in the IWE project. Installation details depend on the agent runtime.

## Versioned runtime contract

The root [`config.toml`](config.toml) is the machine-readable source of truth for supported skills. It maps each maintained skill to:

- its skill version and directory;
- the supported and exactly tested IWE CLI versions;
- the configured runtime binary source;
- a frozen CLI contract;
- execution and context budgets;
- offline and fallback policy.

The current runtime source can be `homebrew`, `cargo`, or `directory`. A relative `directory` source is resolved from the repository root. Contract checks, deterministic tests, and behavioral evals all resolve and exact-version-check the binary from this declarative configuration rather than trusting an arbitrary `iwe` executable on `PATH`.

Only files under the selected `skills/<id>/` directory are installed into the agent's skill payload.

## Efficiency and safety principles

The maintained skill is designed around several practical rules:

- start with the narrow IWE operation that directly answers the request;
- use explicit non-zero limits for discovery and retrieval;
- request only the fields and content needed;
- reuse known document keys instead of rediscovering files;
- avoid web access, broad scans, and filesystem fallbacks for IWE-supported work;
- preview and guard structural mutations;
- stop when the available evidence is sufficient.

These constraints are intended to reduce tool calls, token usage, accidental workspace damage, and behavior drift between agents.

## Verification and evaluation

Install the development dependencies and run deterministic checks:

```bash
python3 -m pip install -r tests/eval/requirements.txt
python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check
python3 -m unittest discover -s tests -v
python3 scripts/skill_metrics.py
python3 tests/eval/run.py --list
```

Behavioral evaluations use pinned fixture repositories, isolated agent and judge workspaces, exact runtime telemetry, independent fixture-based correctness evidence, and per-metric repeated-sample acceptance thresholds. The scenarios are schema-validated YAML in [`tests/eval/scenarios/iwe.eval.yaml`](tests/eval/scenarios/iwe.eval.yaml).

Agent and judge runs invoke paid, nondeterministic model services. Run them only with explicit operator authorization.

## Maintainer documentation

- [Runtime and contract update procedure](docs/maintainers.md)
- [Upstream provenance and external links](docs/upstream-sources.md)
- [Behavioral evaluation guide](tests/eval/README.md)
