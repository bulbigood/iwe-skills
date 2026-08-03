## IWE Agent Skills

Versioned skills in this repository give agents a frozen execution contract for a specific IWE CLI line.

## Available skills

### `iwe-v18`

Use this skill in an IWE knowledge graph when the agent should prefer bounded, graph-aware IWE 0.18 commands over ad-hoc Markdown or filesystem discovery.

Install with:

```bash
npx skills add iwe-org/skills --skill iwe-v18
```

The root `config.toml` maps each skill id to its runtime compatibility, frozen contract, and execution budgets. Installed agents receive only the files under the selected `skills/<id>/` directory.

## Maintainers

- Runtime/contract update procedure: [docs/maintainers.md](docs/maintainers.md)
- Upstream provenance and external links: [docs/upstream-sources.md](docs/upstream-sources.md)
- Behavioral eval guide: [tests/eval/README.md](tests/eval/README.md)

Quick deterministic verification:

Ensure the tested `iwe 0.18.0` binary is on `PATH`, then run:

```bash
python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check
python3 -m unittest discover -s tests -v
python3 scripts/skill_metrics.py
python3 tests/eval/run.py --list
```

Agent evals are paid and nondeterministic. Run them only with explicit operator authorization.
