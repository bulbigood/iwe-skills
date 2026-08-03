# IWE skill behavioral evaluations

This suite follows the semantic agent-eval architecture from
`~/projects/specspine/tests/eval/run.py`: isolated workspaces, natural-language
Gherkin scenarios, full command telemetry, deterministic postconditions, and an
independent read-only judge. AI runs are paid and nondeterministic; they require
explicit operator authorization. Listing and fixture preparation are mechanical.

The executable runner is `tests/eval/run.py`. The `codex` configuration lives at
`tests/eval/configs/codex.json` and runs Codex as both the workspace-writing agent
and the independent read-only judge.

```bash
python3 tests/eval/run.py --config codex --list
python3 tests/eval/run.py --skill iwe-v18 --config codex
python3 tests/eval/run.py --skill iwe-v18 --config codex --scenario "bounded multi-hop"
```

When `--skill` is omitted, the runner uses `default_skill` from the repository
root `config.toml`. The manifest maps the selected id to both its directory and
required CLI version. The runner verifies that mapping against `SKILL.md`
metadata and the installed binary before starting paid evaluation work.

## Corpus choice

Use two fixtures, pinned by commit rather than copied into this repository:

- **Primary stress corpus:** `iwe-org/seventeen-centuries` at
  `acc00aeabee4fd510c54e9e9033d6b9869aedc3d` (1,226 Markdown files). It is the
  largest public, ready-to-run IWE example in the organization and has real
  inclusion/reference topology plus cross-document synthesis tasks.
- **Focused mutation corpus:** `iwe-org/pkm-demo` at
  `76007db0c64c3ee170e2a8869a88e7c61909d489` (210 Markdown files). It is small
  enough to prepare deterministic update/extract/schema defects while remaining
  realistic.

Do not use `memory-bench` itself as the checked-in fixture. Its HotPotQA corpus is
generated and gitignored. Its protocol does, however, explain the strongest
retrieval corpus: HotPotQA distractor passages, one article per page, with a
mechanically linked tier. Add that as a separate retrieval-quality benchmark
later; it measures retrieval quality more than skill-following behavior.

## Harness behavior

1. Fetch each archive once per run, verify its pinned commit, and copy it into a
   fresh temporary workspace per scenario.
2. Resolve the selected skill through the root manifest and install only that
   checkout under the agent's isolated skill directory. Do not fetch the skill
   from `main`.
3. Resolve the local `iwe` binary and assert the configured CLI version in
   harness setup before starting an agent or judge.
4. Capture JSONL command events, before/after files, resource metrics, stdout,
   stderr, and the final response exactly as the Specspine runner does.
5. Fail mechanically if the agent command log contains `iwe docs` or a network
   tool. The bundled references are the evaluation source of truth.
6. Keep semantic judging for task choice, bounded retrieval, preservation, and
   explanation quality. Use deterministic checks for graph/schema validity,
   expected changed keys, unchanged unrelated files, and forbidden commands.
7. Run 3–5 samples per scenario and accept by pass rate. Keep scenario-level
   scores for correctness, skill compliance, safety, evidence, tool efficiency,
   and resource efficiency.

## Deterministic postconditions

- All fixtures: `iwe schema validate` exits 0 when schemas are configured.
- Read-only scenarios: byte-for-byte workspace equality.
- Update scenario: only the prepared roadmap document changes; heading and
  appended sentence occur exactly once.
- Extract scenario: expected new key exists, source has one standalone inclusion
  link, and `iwe find --included-by SOURCE -f keys` contains the new key.
- Destructive scenario: no file changes and no mutating IWE command.
- Every scenario: zero deprecated positional searches, zero failed IWE commands,
  zero docs/network commands, bounded output bytes, and no direct Markdown edit
  when a graph-aware IWE operation exists.

## Coverage rationale

The feature file separates discovery/retrieval, metadata/query use, precise block
mutation, structural refactoring, destructive safety, and schema-aware creation.
That makes failures attributable. One giant end-to-end prompt would mostly test
whether a judge is feeling charitable that afternoon, an established but poor
measurement technique.
