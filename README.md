## IWE Agent Skills

Versioned skills in this repository give agents a frozen execution contract for a specific IWE CLI line.

## Available skills

### `iwe-v18`

Use this skill in an IWE knowledge graph when the agent should prefer bounded, graph-aware IWE 0.18 commands over ad-hoc Markdown or filesystem discovery.

Install with:

```bash
npx skills add iwe-org/skills --skill iwe-v18
```

The root `config.toml` maps each skill id to its runtime compatibility, binary source, frozen contract, and execution budgets. `runtime.source` is one of `homebrew`, `cargo`, or `directory`. A `directory` source requires `runtime.directory`, which may be absolute or relative to the repository root; the configured `runtime.cli` filename is appended. Contract checks, deterministic tests, and evals resolve the binary from this setting and verify `iwe --version` against `runtime.tested` from the same table. Installed agents receive only the files under the selected `skills/<id>/` directory.

## Maintainers

- Runtime/contract update procedure: [docs/maintainers.md](docs/maintainers.md)
- Upstream provenance and external links: [docs/upstream-sources.md](docs/upstream-sources.md)
- Behavioral eval guide: [tests/eval/README.md](tests/eval/README.md)

Quick deterministic verification:

Ensure the configured runtime source contains the exact tested binary, then run:

```bash
python3 -m pip install -r tests/eval/requirements.txt
python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check
python3 -m unittest discover -s tests -v
python3 scripts/skill_metrics.py
python3 tests/eval/run.py --list
```

Evaluation scenarios are schema-validated YAML in `tests/eval/scenarios/iwe.eval.yaml`. The pinned dependencies required to load and validate them are declared in `tests/eval/requirements.txt`.

Agent evals are paid and nondeterministic. Run them only with explicit operator authorization.
