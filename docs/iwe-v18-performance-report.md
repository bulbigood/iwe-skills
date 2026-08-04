# IWE v18 performance improvement report

## Scope

This change reorganizes `iwe-v18` from a command-oriented policy into problem clusters with explicit one-call or, when necessary, two-call solutions. The work was based on the exact configured IWE `0.18.0` binary, not online documentation.

Supporting artifacts:

- [Raw IWE 0.18.0 CLI help inventory](iwe-0.18.0-cli-help.md)
- [Problem, parameter, and solution catalog](iwe-v18-case-catalog.md)
- [Generated paired 5-sample evaluation](../tests/eval/results/2026-08-04-iwe-v18-case-routing.md)
- [Final expanded-skill 5-sample regression](../tests/eval/results/2026-08-04-iwe-v18-expanded-skill.md)
- [Metric definitions](evaluation-metrics.md)

## What changed

### Complete CLI coverage

The frozen contract now records 20 top-level commands, 2 nested commands, positional arguments, command-specific options, and global options. The previous contract exposed only 7 curated operations. `docs` remains explicitly marked as control-plane-only.

The main `SKILL.md` now contains all 62 cataloged cases, grouped into nine solution families:

1. projected identification and discovery;
2. content retrieval and multi-document synthesis;
3. counting, schema validation, and graph analysis;
4. hierarchy and artifact rendering;
5. document creation;
6. atomic metadata and block updates;
7. structural graph refactors;
8. destructive or workspace-wide operations;
9. initialization and control-plane tasks.

Every case has a preferred IWE-only route, an alternative where useful, and a rule for deriving selectors, query terms, limits, graph depth, token budgets, typed values, collision behavior, and mutation guards from the user request and already-known context. The main file also contains a compact glossary for all 22 contract operations. Command-specific help is reserved for a rare syntax/default/detail absent from the skill, rather than routine parameter discovery.

### Skill architecture

`iwe-v18` is now version `0.3.0`. Its main body is organized as:

`problem cluster → direct operation → mental parameter calculation → stopping rule`

The important multi-hop rule is now explicit: include every named entity plus the shared topic in one lexical retrieval, prefer an authored synthesis note, and stop when that note covers every requested entity. The old generic workflow encouraged agents to discover broadly and then retrieve a selected note, even when one retrieval could find the synthesis directly.

The enforced maximum was raised by exactly 50%, from 2,600 to 3,900 estimated tokens; corresponding line and word gates increased from 180/1,800 to 270/2,700. The final skill remains bounded at 219 lines, one triggered reference, no external URLs, and no more than 3,900 estimated tokens. The only reference covers nine explicitly named rare failure classes; it contains no normal task case.

## Paired evaluation

The comparison used the same pinned fixture, IWE `0.18.0` runtime, operator request, scenario, oracle, judge, score scale, thresholds, and five pair IDs for both targets.

- Baseline: `iwe-v18 0.2.0` from commit `5676a03796d70239086873477e917fee4e295401`
- Candidate: `iwe-v18 0.3.0` from this branch
- Scenario: `discover-and-retrieve-bounded-multi-hop-context`
- Agent: Codex CLI `0.146.0`, `gpt-5.6-terra`, medium reasoning
- Judge: `gpt-5.6-sol`, low reasoning
- Paid calls: 10 agent + 10 judge
- All samples mechanically valid and procedure-clean

All `N/5` values below are successful-sample counts, not ordinal averages.

| Metric | v0.2.0 | v0.3.0 | Change |
| --- | ---: | ---: | --- |
| Overall | **FAIL** | **PASS** | Candidate passes every independent gate |
| Task correctness | 5/5 | 5/5 | Preserved |
| Scenario compliance | 5/5 | 5/5 | Preserved |
| Skill compliance | 5/5 | 5/5 | Preserved |
| Safety | 5/5 | 5/5 | Preserved |
| Evidence quality | 5/5 | 5/5 | Acceptance preserved; candidate histogram was `4:1, 5:4` versus baseline `5:5` |
| Tool efficiency | 0/5 | 5/5 | +5 successful samples; candidate score 5 in every pair |
| Resource efficiency | 0/5 | 5/5 | +5 successful samples; candidate score 5 in every pair |

The baseline repeatedly used discovery followed by retrieval, and sometimes further retrieval. It returned 5–20 discovery records before reading the already-identifiable synthesis note. Judges scored Tool efficiency `3` in all five samples and Resource efficiency `2–3`.

The candidate used one bounded retrieval in every sample, returned the authored `virtue-across-centuries` synthesis, and stopped. Tool and Resource efficiency scored `5` in all five samples. Paired telemetry shows the candidate removed 0–2 task calls and 5–20 unnecessary result records per pair while preserving correctness and safety.

The runner exited with status 1 because the experiment intentionally contains an absolute failing baseline target. The candidate aggregate itself passed. This is expected fail-closed experiment behavior, not a harness failure.

### Post-expansion regression

Because the complete 62-case skill materially changed the model-facing payload after the paired comparison, the final file received another five-sample run of the same multi-hop scenario. The first iteration passed the aggregate but one sample clipped the authored synthesis with the generic 2,000-token detail budget and reread the same key. The instruction was corrected at the class level: named multi-entity comparisons now always use one synthesis document, 4,500 per-document tokens, and 5,000 total tokens rather than deriving document count from entity count.

The independent five-sample rerun passed with Task correctness, Scenario compliance, Skill compliance, Safety, Tool efficiency, and Resource efficiency all scoring 5 in every sample. Evidence quality passed 5/5 with histogram `4:1, 5:4`. No threshold was changed.

## What improved

- Multi-hop synthesis became a stable one-call route rather than discovery followed by retrieval.
- The agent stopped after sufficient evidence in all five candidate samples.
- Tool and resource efficiency moved from 0/5 to 5/5 successful samples.
- Correctness, compliance, safety, and validity did not regress.
- Parameter selection is now computed from task semantics instead of inferred through help, docs, configuration reads, or broad discovery.
- Less common IWE operations now have concrete problem routes without turning the installed skill into a flag reference.
- All 62 cataloged cases now reside in the normal single-read payload, together with a short glossary of every command.
- Bounded pagination, synthesis citation discipline, and safety-driven post-mutation verification are explicit.

## What became worse or riskier

- Static skill size increased to nearly the full expanded 3,900-token budget because it now routes all 62 cases and carries the command glossary.
- One candidate sample received Evidence quality score 4 rather than 5. The judge considered a few cited underlying keys less independently traceable than the main synthesis note. The metric still passed 5/5, but citation discipline can be tightened.
- The paid evaluation covers one read-only multi-hop scenario. It does not establish that the new two-call mutation routes outperform the previous preview/apply/verify workflows across update, extract, rename, inline, attach, delete, or normalization.
- Expanding the frozen contract from 7 to 22 operations enlarges the maintenance surface. Future CLI updates must synchronize more help hashes.

## Recommended next improvements

1. Add focused 5-sample evaluations for one structured update, one extraction, and one schema-bound creation before claiming broad performance improvement beyond retrieval.
2. Measure activation-token cost and task-output savings together. The candidate spends more static instruction context but substantially less task context in the evaluated scenario.
3. Audit the case catalog against future IWE releases mechanically and keep the installed skill clustered; do not copy the raw flag inventory into it.
4. Preserve the explicit safety exception for independent mutation verification rather than weakening guards to satisfy a universal call budget.

## Verification

- Frozen contract synchronized against exact IWE `0.18.0`: PASS
- Deterministic unit suite: 68/68 PASS
- Eval scenario listing and schema validation: PASS
- Skill size and package-boundary checks: PASS
- Git whitespace check: PASS
- Paired five-sample candidate aggregate: PASS
- Final expanded-skill five-sample regression: PASS; Tool and Resource efficiency 5/5
