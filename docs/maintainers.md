# Maintaining versioned IWE skills

This documentation is repository-only. Do not copy it into an installed skill.

## Runtime/maintainer boundary

`skills/iwe-v18` is the frozen model-facing contract for the IWE 0.18 line. It contains one execution policy and two rare-case references. External provenance, release history, update instructions, contracts, tests, and eval infrastructure remain outside that directory.

The runtime agent must not browse upstream documentation, invoke `iwe docs`, regenerate references, install IWE, or read `contracts/iwe-v18.json` during an ordinary task. Build tooling, CI, and evals consume the machine-readable contract.

## Why the skill uses direct CLI

IWE 0.18 already provides concise structured commands with native result, document, token, depth, and format limits. A wrapper would mostly proxy flags and add another compatibility surface. The project therefore uses direct CLI commands.

The decision must be revisited only when a wrapper can demonstrate at least one of these outcomes against the eval suite:

- fewer agent-visible tool calls for a representative task;
- materially fewer bytes/tokens entering context;
- stable normalization across incompatible command shapes;
- enforcement that cannot be expressed with native IWE limits.

A pass-through script does not qualify. Measured runtime budgets are one IWE call for simple discovery and at most two for discovery followed by targeted retrieval.

## Release update

1. Add the next versioned skill directory instead of silently changing the IWE 0.18 contract to a later CLI line.
2. Update the root `config.toml` with the skill path, skill version, runtime source (`homebrew`, `cargo`, or `directory`), supported range, exact tested CLI version, contract path, provenance, and execution budgets. For `directory`, set an absolute directory or one relative to the repository root.
3. Install the exact tested CLI version through the configured source. All deterministic tooling resolves that source and validates the binary against `runtime.tested`; it does not silently take another `iwe` from `PATH`.
4. Update the curated command/flag set in `contracts/<skill>.json` only after reviewing the release behavior.
5. Synchronize help hashes:

```bash
python3 scripts/sync_iwe_contract.py --skill iwe-v18
python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check
```

6. Keep `SKILL.md` within the expanded hard caps of 270 lines, 2,700 words, and 3,900 estimated tokens (50% above the prior enforced maxima). Prefer 60–225 lines when completeness permits. Keep normal commands, all cataloged cases, parameter derivation, the command glossary, limits, failure policy, fallback policy, and mutation safety in that file.
7. Keep no more than two narrow references unless a measured eval regression proves another is necessary. Every reference requires a precise read trigger.
8. Update `docs/upstream-sources.md` with the synchronization date, release/source revision, and divergence notes.
9. Keep `tests/eval/scenarios/iwe.eval.yaml` schema-valid. Every scenario must explicitly declare all seven `0..5` scoring rubrics, attainable score conditions, dimension floors and weights, minimum weighted score, and mechanical budgets. Do not reintroduce a regex-parsed feature DSL.
10. Install the pinned eval dependencies and run deterministic verification:

```bash
python3 -m pip install -r tests/eval/requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/skill_metrics.py
python3 tests/eval/run.py --list
```

11. Inspect the package boundary and ensure model-facing files contain no external URLs or maintainer procedures.
12. After explicit authorization for paid execution, run focused efficiency scenarios before the full suite:

```bash
python3 tests/eval/run.py --skill iwe-v18 --scenario "One-call bounded discovery" --jobs 1 --samples 1
python3 tests/eval/run.py --skill iwe-v18 --scenario "Ambiguous discovery" --jobs 1 --samples 1
python3 tests/eval/run.py --skill iwe-v18 --scenario "CLI option incompatibility" --jobs 1 --samples 1
python3 tests/eval/run.py --skill iwe-v18 --scenario "IWE is unavailable" --jobs 1 --samples 1
```

The default complete run is ten scenarios, one agent plus one judge per scenario. Increase samples only when the expected cost and variance justify it.

## Acceptance gates

- Contract sync and all unit tests pass.
- Installed payload has zero external URLs and exactly two references.
- The normal discovery budget is one IWE call; discovery plus targeted retrieval is at most two.
- Command-specific help appears only after selecting the task command and needing a rare syntax/default/detail absent from `SKILL.md`, or after that command rejects known syntax; global help remains prohibited.
- Network and forbidden fallback tools are blocked and logged by eval shims.
- Mechanically measurable behavior is not delegated to the AI judge.
- Mutation safety budgets permit preview, guarded application, and verification.
- The skill ships a short glossary of every task command, not a flag-by-flag CLI manual.
