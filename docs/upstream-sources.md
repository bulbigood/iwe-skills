# Upstream sources for IWE skills

This file is maintainer-facing and is not installed as part of `skills/iwe-v18`.
Runtime agents must use the frozen local contract rather than these links.

## IWE 0.18 line

- Official repository: https://github.com/iwe-org/iwe
- Official documentation: https://iwe.md/docs/
- CLI reference: https://iwe.md/docs/cli/
- Query language: https://iwe.md/docs/concepts/query-language/
- Agent Skills specification: https://agentskills.io/specification
- Agent Skills authoring guidance: https://agentskills.io/skill-creation/best-practices
- Last synchronized: 2026-08-03
- CLI release tested: `iwe 0.18.0`
- Contract provenance: local release binary, identified in `config.toml` as `iwe-cli-0.18.0`
- Frozen contract: `contracts/iwe-v18.json`

The repository does not currently pin a separate documentation-source commit. Until upstream publishes one alongside the release, the CLI release and the SHA-256 hashes of command-specific help captured in the frozen contract are the reproducible source of truth.

## Synchronization procedure

1. Install the exact CLI version in an isolated maintainer environment.
2. Run `python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check`.
3. Review every help-hash or supported-flag delta against the release source.
4. Update only the curated operation contract and runtime examples needed by the skill.
5. Run deterministic tests and inspect payload metrics.
6. Run agent evals only after explicit authorization for paid, nondeterministic execution.

## Divergence history

- `iwe-v18` intentionally omits installation, configuration tutorials, the built-in documentation command, completions, broad analytics, and full command manuals from its runtime payload.
- The runtime contract permits only the IWE 0.18 operations required by tested retrieval, graph navigation, safe mutation, structural refactoring, and schema validation workflows.
- The repository previously generated complete CLI and built-in manuals inside the skill. Those files were removed because they increased context and encouraged unnecessary reads.
- External documentation links were moved here so documentation changes cannot silently alter the installed IWE 0.18 execution policy.
