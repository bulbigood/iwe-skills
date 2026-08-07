# IWE v0.18 Skill and Eval Coverage Remediation Plan

> **For Hermes:** Execute this plan task-by-task with strict TDD and preserve the one-arm `iwe-v18` production evaluation policy.

**Goal:** Make `iwe-v18` self-contained for all basic/frequent read-write workflows, make coverage claims mechanically reproducible, and expand production evals from representative examples to an explicit core-capability matrix.

**Architecture:** Keep three separate SSOT layers: the exact binary-derived CLI contract (`contracts/iwe-v18.json`), a maintainer capability taxonomy/matrix, and compact model-facing routing in `skills/iwe-v18/SKILL.md`. Do not turn the skill into raw help text. Generate coverage reports from the contract and scenario declarations so percentages cannot drift through optimistic prose—the traditional fate of percentages left unattended.

**Tech Stack:** Python 3, unittest, JSON/TOML/YAML, IWE CLI 0.18.0, existing evaluation harness.

---

## Baseline and scoring model

The audit must report three distinct metrics rather than one ambiguous percentage:

1. **Command-family coverage:** whether the skill has a usable route for each of 20 top-level and 2 nested command entrypoints.
2. **Capability coverage:** whether each user-visible workflow derived from `iwe <command> --help` has routing, parameter derivation, safety, and stopping guidance.
3. **Executable-route coverage:** whether the skill contains enough exact syntax to execute the workflow without proactive help/docs, consistent with its own hard rule.

For basic/frequent coverage, classify these command families as core:

- Read/data: `find`, `retrieve`, `count`, `tree`, `schema`, `schema validate`.
- Create/write/refactor: `new`, `create`, `update`, `rename`, `extract`, `inline`, `attach`, `delete`.

Treat `init`, `normalize`, `squash`, `export`, `stats`, `stats similarity`, `completions`, and `docs` as setup, bulk, analysis, artifact, or control-plane functionality—not core read/write. Keep them in total coverage.

A capability is **covered** only when the skill supplies all four: route, essential selectors/options, safety/collision/expectation behavior, and stop/verification behavior. Partial items must be reported separately, not rounded up.

## Current evidence

- Live binary: `/home/linuxbrew/.linuxbrew/Cellar/iwe/0.18.0/bin/iwe`, verified as `iwe 0.18.0`.
- Frozen contract check: `python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check` passes.
- Raw inventory: 20 top-level commands plus `schema validate` and `stats similarity`.
- Current skill names/routes all 22 entrypoints and mirrors all 62 cases in `docs/iwe-v18-case-catalog.md`.
- The current production scenario set has 10 scenarios, but only 6 are positive IWE workflows. The positive set exercises five core command families: `find`, `retrieve`, `create`, `update`, and `extract`. The other four scenarios cover refusal, runtime fallback, post-miss fallback, and activation exclusion.

## Current gaps to close

The skill is semantically broad but not uniformly self-contained at exact-route level. Add compact exact syntax or unambiguous flag names for:

- Read: retrieve expansion flags, `--children`, `--backlinks false`, `--exclude`, finite relationship depth/distance flags.
- Create: `create --content`, `--vars-json` parity, `new --content`/stdin behavior where useful.
- Update: `--unset`, `--insert-before`, `--insert-after`, local block `--delete`, whole-body `--content` syntax.
- Structural writes: inline `--reference`/`--keep-target`, attach `--to`, and configured `--action` only where action choice is already known.
- Setup/control: exact `init --auto --json` combinations and the intentional exclusion of interactive `--edit`, cosmetic `--quiet`, routine `--verbose`, and proactive docs/help.
- Contract correctness: document stdin as an input path for `create`, `new`, `retrieve`, and `update` where the live help supports it; `retrieve.required_any` currently omits stdin.

The eval suite lacks positive coverage for `count`, `tree`, `schema validate`, `new`, metadata set/unset, body overwrite, block replace/insert/delete variants, `rename`, `inline`, `attach`, and a fully scoped guarded `delete` preview/apply flow.

---

### Task 1: Add a mechanically generated coverage matrix

**Objective:** Establish a reproducible denominator and stop hand-maintained 95%/100% claims from drifting.

**Files:**
- Create: `scripts/report_iwe_coverage.py`
- Create: `docs/iwe-v18-coverage-matrix.md`
- Modify: `tests/test_iwe_skills.py`
- Modify: `README.md`

**Steps:**
1. Write a failing test that requires the report to enumerate all 22 contract entrypoints and every declared core capability.
2. Run the focused test and confirm failure because the reporter does not exist.
3. Implement a small reporter that reads `contracts/iwe-v18.json`, a declarative capability map, `skills/iwe-v18/SKILL.md`, and scenario tags.
4. Emit command-family, capability, executable-route, and eval-coverage percentages with numerator/denominator and missing IDs.
5. Add `--check` mode that fails on undocumented contract commands, duplicate capability IDs, stale scenario references, or an unexplained percentage change.
6. Replace README's unsupported “roughly 95%” statement with generated evidence or a link to the matrix.
7. Verify: `.venv/bin/python -m unittest tests.test_iwe_skills -v` and `python3 scripts/report_iwe_coverage.py --check`.

### Task 2: Correct the frozen input contract

**Objective:** Represent non-flag stdin input routes exposed by the exact 0.18.0 help.

**Files:**
- Modify: `scripts/sync_iwe_contract.py`
- Modify: `contracts/iwe-v18.json`
- Modify: `tests/test_iwe_skills.py`
- Modify: `docs/iwe-0.18.0-cli-help.md` only if regeneration proves drift

**Steps:**
1. Add failing tests for stdin-capable `create`, `new`, `retrieve`, and `update` modes, especially retrieval seed input.
2. Verify the tests fail against the current `required_any` representation.
3. Extend the contract schema with explicit `stdin_modes` or equivalent structured metadata; do not encode stdin as a fake flag.
4. Regenerate/synchronize from the exact binary.
5. Verify help hashes remain pinned and `python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check` passes.

### Task 3: Fill self-contained read-route gaps in the skill

**Objective:** Make all frequent read workflows executable without proactive help/docs.

**Files:**
- Modify: `skills/iwe-v18/SKILL.md`
- Modify: `docs/iwe-v18-case-catalog.md`
- Modify: `tests/test_iwe_skills.py`

**Steps:**
1. Add failing static-policy tests for exact bounded forms of expansion, edge-only children, backlink suppression, and second-page exclusion.
2. Add compact recipes using `--expand-includes`, `--expand-included-by`, `--expand-references`, `--expand-referenced-by`, `--children`, `--backlinks false`, and repeatable `--exclude`.
3. Preserve the one/two-call budget and positive nonzero bounds.
4. Ensure relationship direction is described once as an SSOT rather than repeated per command.
5. Run focused tests, skill metrics, then the deterministic suite.

### Task 4: Fill self-contained write-route gaps in the skill

**Objective:** Cover every core write mode with exact safe syntax.

**Files:**
- Modify: `skills/iwe-v18/SKILL.md`
- Modify: `docs/iwe-v18-case-catalog.md`
- Modify: `tests/test_iwe_skills.py`

**Steps:**
1. Add failing tests for exact routes for complete-content creation, JSON/YAML typed template variables, frontmatter unset, whole-body update, insert-before/after, local block delete, safe inline, and attach.
2. Add minimal examples for `create --content`, `--vars-json`, `new --content`, `update --unset`, `--insert-before`, `--insert-after`, block `--delete`, `inline --reference --keep-target`, and `attach --to`.
3. Preserve preview/apply identity, document/block expects, strict mode, collision policy, deletion confirmation, and rollback requirements.
4. Keep interactive `--edit` explicitly out of autonomous routes.
5. Verify static policy tests, contract sync, metrics, and full deterministic suite.

### Task 5: Add scenario capability metadata

**Objective:** Make eval coverage measurable without guessing commands from prose or agent telemetry.

**Files:**
- Modify: `tests/eval/scenario.schema.json`
- Modify: `tests/eval/scenarios/iwe.eval.yaml`
- Modify: `tests/eval/run.py`
- Modify: `tests/test_eval_scoring.py`

**Steps:**
1. Add failing schema/loader tests for required `capabilities` and optional `expected_command_families` fields.
2. Tag each current scenario with capability IDs such as `read.retrieve.synthesis`, `write.update.block.replace-text`, and `safety.destructive.undefined-scope`.
3. Validate that positive IWE scenarios name at least one core capability and forbidden/fallback scenarios use non-core behavioral tags.
4. Report unique core capabilities covered, not scenario count; two retrieval scenarios must not masquerade as two different capabilities.
5. Verify list mode and report rendering remain backward-compatible where needed.

### Task 6: Add missing P0 read evals

**Objective:** Cover common read/data operations not represented today.

**Files:**
- Modify: `tests/eval/scenarios/iwe.eval.yaml`
- Modify: `tests/eval/scenario.schema.json` if new oracle fields are required
- Modify: `tests/eval/run.py`
- Add/modify fixtures under the existing fixture-preparation code
- Modify: `tests/test_eval_scoring.py`

**Scenarios:**
1. Exact-key bounded read with no discovery.
2. Typed metadata projection and sort.
3. Count a typed cohort with an independent expected integer.
4. Render a bounded subtree with independently parsed inclusion edges.
5. Retrieve one seed plus finite parent/child context, proving expansion direction and limits.
6. Validate one schema-bound document using configured binding.

For each scenario, add an independent deterministic oracle, exact stop condition, prohibited broad fallback, and semantic efficiency range. Start with one deterministic sample/list validation; do not run paid production evaluation yet.

### Task 7: Add missing P0 write evals

**Objective:** Cover the normal write lifecycle rather than one create, one compound update, and one extract example.

**Files:** Same harness/scenario files as Task 6.

**Scenarios:**
1. Quick `new` with explicit collision behavior.
2. Set and unset typed frontmatter while preserving body bytes.
3. Whole-body replacement while preserving frontmatter.
4. Insert-before or insert-after with exact block guard.
5. Local block deletion with document and block expects.
6. Rename a key and independently verify all references changed.
7. Inline an inclusion with `--keep-target` and verify both source and target.
8. Attach a source through a known configured action and prove idempotency.
9. Delete one exact note through preview/confirmation/apply in an authorization-aware test harness, with independent reference-cleanup oracle.

Split compound operator coverage across scenarios only when an independent postcondition can distinguish each behavior. Do not reward merely invoking the expected command.

### Task 8: Add P1 advanced/regression evals

**Objective:** Protect total CLI coverage without bloating the main production gate.

**Scenarios:**
- `stats similarity` threshold routing.
- `squash` finite depth.
- filtered `export` with optional headers.
- initialization dry-run JSON without mutation.
- normalize refusal when rollback is absent.
- stdin content/retrieval paths.

Keep these in a focused regression suite unless usage data justifies promotion to production.

### Task 9: Rebalance production evaluation

**Objective:** Keep production testing representative, bounded, and `iwe-v18`-only.

**Files:**
- Modify: `scripts/run_iwe_skill_ab_eval.py` (rename later only if compatibility permits)
- Modify: `tests/test_eval_scoring.py`
- Modify: `README.md`

**Steps:**
1. Select a stratified production set covering core read, core write, structural refactor, destructive safety, fallback, and activation exclusion.
2. Preserve 10 samples per production scenario and only the `iwe-v18` target.
3. Keep exact weak-profile gates: correctness/evidence 90%, safety 100%, others 80%, score 5 except efficiency 4.
4. Avoid running every rare command in every production cycle; use focused regression suites for P1 capabilities.
5. Replay the latest passing production result before tightening policy, then run the new production matrix.
6. Publish per-skill scenario tables with `N/10` as successful counts, not averages.

### Task 10: Final verification and evidence update

**Objective:** Close the work with auditable metrics and no unsupported claims.

**Verification:**
- `/home/linuxbrew/.linuxbrew/Cellar/iwe/0.18.0/bin/iwe --version`
- `python3 scripts/sync_iwe_contract.py --skill iwe-v18 --check`
- `python3 scripts/report_iwe_coverage.py --check`
- `.venv/bin/python -m unittest discover -s tests -v`
- `python3 tests/eval/run.py --skill iwe-v18 --list`
- focused one-sample smoke runs for every new scenario
- 10-sample `iwe-v18`-only production run after smoke and replay gates pass
- `git diff --check`
- final local/remote SHA equality after requested commit/push

**Acceptance criteria:**
- 22/22 command families mapped.
- 100% of declared core capabilities have self-contained executable routes or an explicit, justified autonomous exclusion.
- Every core capability is either covered by an eval or listed as an explicit gap in the generated report.
- P0 production set covers at least one scenario in each of: discovery, retrieval, metadata read, creation, metadata mutation, body/block mutation, structural refactor, destructive safety, fallback, and activation exclusion.
- No scenario depends on agent self-report as its correctness oracle.
- Skill payload remains within the repository's enforced size budget.

## Risks and trade-offs

- Adding exact flags can improve reliability but increase activation tokens. Prefer compact shared syntax maps over examples for every permutation.
- Command invocation coverage is not behavioral coverage. Oracles must inspect final files/graph independently.
- A large production matrix is expensive and slows iteration. Keep rare/control-plane commands in focused suites.
- Destructive evals need isolated fixtures and harness-owned authorization; never weaken real safety policy to make them executable.
- The old 62-case catalog is broad but hand-maintained. It should become input to—or output from—the coverage reporter, not a second unaudited SSOT.

## Alternatives considered

- **Count only commands:** rejected because 22/22 would conceal missing modes and flags.
- **Count every flag occurrence equally:** rejected because shared selectors repeated across commands would dominate the score and make cosmetic flags look as important as write safety.
- **Put all raw help into the skill:** rejected because it would damage context efficiency and routing quality.
- **Add every new scenario to production immediately:** rejected because deterministic smoke/focused suites should catch harness defects before paid 10-sample runs.
