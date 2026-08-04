# IWE v18 expanded-skill focused regression

Date: 2026-08-04

This result covers the final expanded `iwe-v18 0.3.0` skill after moving every cataloged case into `SKILL.md`, adding the complete command glossary, and raising the enforced skill-size cap by 50%.

Metric semantics and gates are defined in [docs/evaluation-metrics.md](../../../docs/evaluation-metrics.md) and the executable scenario/rubric source of truth is [iwe.eval.yaml](../scenarios/iwe.eval.yaml). Values such as `5/5` are successful-sample counts, not score averages.

## Command

```bash
.venv/bin/python tests/eval/run.py \
  --skill iwe-v18 \
  --scenario "Discover and retrieve bounded multi-hop context" \
  --samples 5 \
  --jobs 5 \
  --agent codex
```

Raw report directory: `tests/eval/reports/20260804T200324Z`

## Result

- Aggregate: **PASS**
- Valid samples: 5/5
- Procedure-clean samples: 5/5

| Metric | Successful samples | Score histogram |
|---|---:|---|
| Task correctness | 5/5 | `5:5` |
| Scenario compliance | 5/5 | `5:5` |
| Skill compliance | 5/5 | `5:5` |
| Safety | 5/5 | `5:5` |
| Evidence quality | 5/5 | `4:1, 5:4` |
| Tool efficiency | 5/5 | `5:5` |
| Resource efficiency | 5/5 | `5:5` |

Every final sample used one bounded retrieval and returned the authored synthesis note without a redundant second read.

## Iteration evidence

The first post-expansion run passed its aggregate but only achieved 4/5 Tool and Resource efficiency successes. One sample used a 2,000-token detail budget, clipped an authored synthesis, and reread the same key. The class-level rule was corrected so a named multi-entity comparison uses one synthesis document, 4,500 per-document tokens, and 5,000 total tokens rather than deriving document count from entity count. The table above is the independent five-sample rerun after that correction; no threshold was changed.
