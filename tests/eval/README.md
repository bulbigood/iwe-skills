# IWE skill behavioral evaluations

The eval runner uses isolated workspaces, natural-language scenarios, complete command telemetry, deterministic postconditions, and an independent read-only judge. Agent and judge runs are paid and nondeterministic; they require explicit operator authorization. Scenario listing, contract checks, shim tests, command classification, and budget validation are mechanical.

```bash
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

## Mechanical efficiency contract

Every Gherkin scenario declares:

```text
Budget: iwe=MIN..MAX output=BYTES fallback=true|false mode=real|incompatible|unavailable
```

The runner counts actual IWE invocations, including chained commands, rather than command-execution events. A proxy shim records exact IWE data before agent telemetry can truncate it. The runner records:

- command-specific help calls;
- web/network and built-in documentation calls;
- forbidden `grep`, `rg`, and `find` fallbacks;
- direct broad workspace reads;
- optional reference reads;
- exact IWE stdout bytes and JSON result counts;
- total captured command-output bytes and a stable byte-to-token context estimate;
- failed and unbounded IWE calls.

The proxy caps emitted IWE stdout at the scenario output budget while preserving the original byte count for the mechanical verdict. These values are hard gates. The AI judge scores semantic correctness, safety, evidence, and explanation quality; it does not decide whether a countable budget was met.

## Isolation and shims

`tests/eval/shims/` blocks and logs `grep`, `rg`, `find`, `curl`, and `wget` by placing shims first on the tested agent's `PATH`. Command telemetry separately rejects `gh`, `git clone`, `iwe docs`, and known network commands. The agent receives an explicit environment allowlist rather than a copy of the host environment. The independent read-only judge receives evidence and exact IWE telemetry without inheriting failure shims.

The Codex configuration also enforces `workspace-write`, disables sandbox network access, and sets the generated shell environment to inherit nothing. Shims are defense in depth, not the network boundary. Any additional agent configuration must provide equivalent filesystem, environment, and network isolation.

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

## Deterministic postconditions

- Read-only scenarios preserve fixture bytes.
- Update changes only the prepared roadmap and preserves unrelated content.
- Extract creates a target document and replaces the source section with an inclusion edge.
- Schema-bound creation preserves typed frontmatter and produces a meeting document.
- Destructive refusal performs no mutation.
- Every scenario obeys its IWE/output/fallback budget, avoids deprecated positional `find`, and makes no web or documentation call.

## Running strategy

Run `python3 -m unittest discover -s tests -v` before any paid eval. Then run one sample of each focused efficiency scenario with `--jobs 1`. Run the full suite only after those pass. Reports are written under `tests/eval/reports/` and include raw commands, mechanical metrics/errors, judge output, and final verdicts.
