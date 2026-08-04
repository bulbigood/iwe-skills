---
name: iwe-v18
description: Use for IWE knowledge-graph retrieval and safe Markdown refactors. Route 95% of tasks from this file alone.
compatibility: Requires IWE CLI >=0.18.0.
metadata:
  version: "0.3.0"
---

# IWE problem-solving policy

IWE is authoritative in an IWE Markdown workspace. Classify the outcome, choose the narrowest route, derive parameters from known context, and stop when it succeeds.

## Hard execution rules

- Do not run routine preflight such as version, status, schema, configuration, or command-help checks.
- Do not use web search, `grep`, `rg`, `find`, recursive listing, or broad file reads to duplicate IWE.
- Do not install, update, configure, or repair IWE.
- Default result limit: 20. Use a smaller request-derived limit.
- Request JSON and only the fields or content needed for reasoning.
- Never pass 0 as a result, depth, distance, document, or token bound; 0 is unlimited.
- Prefer one call. A normal read gets a second only for ambiguity, one bounded page, or one failed refinement. Do not run a second query when the first result supports the answer.
- Mutation safety overrides efficiency: preview and guarded apply are mandatory; verify once only when success cannot prove final state.

## Route and compute parameters mentally

Use only the request, conversation, and prior IWE output; do not read other sources merely to choose parameters.

| Need | Direct route | Output |
|---|---|---|
| Keys, titles, fields, relationships, blocks, lines | `find` | projected JSON or keys |
| Full prose, synthesis, finite related context | `retrieve` | bounded JSON |
| Quantity | `count` | integer |
| Inclusion hierarchy / flattened hierarchy | `tree` / `squash` | JSON, Markdown |
| Schema shape / validation / binding | `schema` / `schema validate` | JSON |
| Graph health / duplicates / visualization | `stats` / `stats similarity` / `export` | JSON, CSV, DOT |
| New simple / typed document | `new` / `create` | created path |
| Metadata or local body edit | `update` | guarded mutation |
| Key, section, inclusion, attachment refactor | `rename`, `extract`, `inline`, `attach` | affected keys |
| Document removal / global normalization | `delete` / `normalize` | destructive guarded result |

1. **Selector:** exact key → `--key`; typed field → `--filter`; known graph anchor → relationship flag; incomplete title/key → `--fuzzy`; body concepts → `--lexical`.
2. **Search phrase:** keep distinctive names, nouns, quoted terms, and shared topic; comparisons include every entity plus their relation/topic.
3. **Count:** exact note/synthesis = 1; explicit N = N; “a few” = 5; otherwise requested facets, capped at 20.
4. **Shape:** identities → keys; fields → projection; sections/lines → blocks/matches; prose → retrieve. No bodies for lists/counts.
5. **Graph bounds:** direct = 1; stated hops = that number. Authored synthesis = 1 document; otherwise cap the useful cited set, normally 3–12.
6. **Token bounds:** fact = 800/document; summary = 1200; detail = 2000; authored synthesis = 4500. Total = per-document × documents, normally ≤8000.
7. **Typed values:** preserve booleans, numbers, lists, and maps in YAML/JSON. Quote numeric-looking or boolean-looking strings.
8. **Guards:** exact mutation uses document `--expect 1`; batch uses a user-derived count/range; every block operator gets inline `expect`. Explicit new keys default to collision policy `fail`.
9. **Stop:** enough evidence means no confirmation query. For synthesis, cite the synthesis key as primary evidence; cite underlying keys only when the returned content explicitly identifies them and they materially support the answer.

## Cluster A — identify, list, and inspect without full bodies

Use one projected `find`:

```bash
iwe find --lexical "<distinctive terms>" --limit 5 --project 'key=$key,title=$title' --format json
```

- **A1 Exact identity:** key selector, limit 1, key/title projection.
- **A2 Partial identity:** fuzzy distinctive title/key fragment, limit 1–5.
- **A3 Body concept:** lexical content nouns and compact projection.
- **A4 Typed cohort:** filter copied from stated frontmatter criteria; project requested fields.
- **A5 Roots:** roots selector for flat entry-point list; use tree only when hierarchy is requested.
- **A6 Inclusion neighborhood:** included-by for descendants, includes for containers; positive request-derived depth.
- **A7 Reference neighborhood:** references for documents linking to an anchor, referenced-by for documents linking from it; positive distance.
- **A8 Heading/block:** exact key plus one block predicate using header, within, text, paragraph, or references.
- **A9 Matching lines:** exact key plus matches only for an actual literal/regex text-pattern request.
- **A10 Ranked records:** filter/query plus known-field sort (`1` ascending, `-1` descending), projection, and limit.

If an ambiguous winner needs a body, call 2 retrieves only its key.

## Cluster B — read, summarize, compare, and gather context

Use one bounded `retrieve`:

```bash
iwe retrieve --lexical "<all named entities> <shared topic>" --limit 1 --max-documents 1 --max-tokens 5000 --max-document-tokens 4500 --format json
```

- **B1 Known note:** one key, one document; 800/1200/2000 tokens for fact/summary/detail.
- **B2 Topic summary:** lexical topic, requested evidence count or 3, finite per-document and total caps.
- **B3 Named comparison:** all entities plus shared topic; use the template's 1 document, 4500 document tokens, and 5000 total. Never derive 3 documents from 3 entities or use the 2000 detail budget. Stop if that synthesis covers all entities.
- **B4 Children bodies:** expand includes only to requested positive depth; use child-edge metadata instead when identities suffice.
- **B5 Parent context:** expand included-by, normally one level.
- **B6 Cited sources:** expand references only when source bodies are required; otherwise use returned edges.
- **B7 Backlinks/reception:** expand referenced-by; suppress unneeded backlink metadata when appropriate.
- **B8 Mixed context:** combine only requested expansion directions; cap to the maximum answerable cited set.
- **B9 Ambiguous winner:** projected find of 2–5 candidates, then one exact-key retrieve.
- **B10 Bounded next page:** one second retrieval excluding already returned keys; never re-read old results or raise limits reflexively.

If a synthesis facet is absent, Refine the IWE query once with that facet and shared topic.

## Cluster C — quantify, validate, and analyze

- **C1 Cohort count:** `count` with typed filter. Use a positive limit only for “at least N?”; otherwise exact count is intentional.
- **C2 Graph count:** count roots or one finite relationship scope; never infer content from a count.
- **C3 Schema overview:** `schema` for field types, coverage, and values in a selected cohort.
- **C4 One field:** schema narrowed by field when only that field matters.
- **C5 Validation:** `schema validate` by key/filter; use an explicitly supplied schema file only when requested.
- **C6 Binding trace:** schema validation explain mode when binding—not validity—is the question.
- **C7 Health/connectivity:** `stats` for aggregate graph health; exact key for one-document complexity/connectivity; CSV only for requested tables.
- **C8 Duplicate review:** `stats similarity`; threshold 0.95 near-exact, 0.85 normal review, 0.70 deliberately broad overlap.

Do not discover before a direct selector.

## Cluster D — hierarchy and reusable artifacts

- **D1 Workspace hierarchy:** `tree` with requested positive depth; Markdown for direct presentation, JSON for reasoning.
- **D2 Subtree:** tree from one or more already-known roots.
- **D3 Filtered hierarchy:** tree with filter/relationship scope and projected node fields.
- **D4 Linear inclusion artifact:** `squash` one root to requested inclusion depth.
- **D5 Graph visualization:** `export` one key/subgraph to DOT with finite depth.
- **D6 Filtered graph:** export a filter/relationship scope; include headers only for section-level visualization.

Do not retrieve documents before an artifact command.

## Cluster E — create documents

- **E1 Quick note:** `new` with title/body; suffix collision is acceptable unless explicit identity is required.
- **E2 Known template:** `create` with typed JSON/YAML variables, repeated typed frontmatter sets, strict validation, explicit collision policy.
- **E3 Exact complete document:** create explicit key with complete frontmatter/body content, strict, collision fail.
- **E4 Idempotent optional creation:** skip only when already-existing is an acceptable success state.
- **E5 Deliberate replacement:** override only with explicit overwrite intent; otherwise fail or suffix.

Use `new` for simple title/body work; `create` for exact keys, complete/template/schema-bound documents, or typed values. Conventional variables are `title` and `body`; include `"body":"<text>"`. Put variables in typed JSON/YAML and frontmatter in repeated sets. Create has no `--format` flag. Strict success needs no validation/update call.

## Cluster F — atomic metadata and local body edits

Use `update`; combine disjoint same-document operators atomically. Never overwrite a whole body for a local edit.

```bash
iwe update --key "<key>" --replace-text '{ $header: "<old>", to: "<new>", expect: 1 }' --append '{ $header: "<section>", content: "<text>", expect: 1 }' --expect 1 --strict --dry-run
```

- **F1 Frontmatter:** set/unset typed fields; exact key or narrow cohort filter.
- **F2 Heading rename:** replace-text selected by exact header; omit `from` only for whole own-text replacement.
- **F3 Local text replacement:** within/text selector plus exact from/to.
- **F4 Whole block replacement:** replace only when the selected block is fully authoritative.
- **F5 Insert sibling:** insert-before/after according to the literal requested position.
- **F6 Append child:** append under an exact section/container.
- **F7 Delete local block:** block delete with exact selector and expected count; this is not document deletion.
- **F8 Whole body:** content overwrite only when the complete new body is authoritative.

Call 1 is exact dry-run; call 2 removes only dry-run. Verify one exact key when guarded output cannot prove content/preservation. Ask when key, selector, old text, or expected count is unknown.

## Cluster G — structural graph refactors

```bash
iwe extract "<source-key>" --section "<known heading>" --dry-run --format keys
```

- **G1 Rename key:** `rename old new`; preview then apply; references are rewritten.
- **G2 Extract section:** extract by known heading, or by block only when its number is already known.
- **G3 Section inventory:** extract list is a one-call answer only when inventory is requested.
- **G4 Safe inline:** inline known inclusion with keep-target; optional quote form only when requested.
- **G5 Inline and remove target:** omit keep-target only with explicit deletion intent and focused confirmation.
- **G6 Attach:** attach one source to one or more already-known configured destinations in one preview/apply pair.
- **G7 Attach-action inventory:** attach list only when available actions are the requested outcome.

Preview, apply identical arguments, then verify affected keys only when output cannot prove the graph result.

## Cluster H — destructive and workspace-wide work

- **H1 Delete one note:** exact key, expect 1, strict dry-run, affected keys, rollback when practical, then fresh, focused confirmation and apply.
- **H2 Delete cohort:** narrow user-defined filter and expected count/range; never classify “obsolete” speculatively or use an empty workspace-wide filter.
- **H3 Normalize:** entire-library in-place rewrite with no preview; require explicit scope, established rollback, and fresh, focused confirmation.

Safety calls are not waste. Refuse destructive work when scope or recovery is insufficient.

## Cluster I — setup, control plane, and recovery

- **I1 Initialization proposal:** `init` dry-run JSON; overrides only from already-supplied library, link, extension, source-format, or date-format choices.
- **I2 Initialize:** auto-apply accepted detection; static defaults only when explicitly preferred.
- **I3 Completions:** `completions` for the already-known shell.
- **I4 Embedded reference:** `docs` query/config/schema only when that reference itself is requested; never as routine task discovery.
- **I5 Exact command help:** after selecting a command, use `iwe <command> --help` only when a rare syntax, default, or option detail missing here is necessary; then execute the task without global help or repeated lookups.

## Command glossary

- `init` — initialize detected workspace configuration.
- `create` — create exact, templated, typed, or validated documents.
- `new` — create a simple title/body document.
- `find` — discover metadata, relations, blocks, or lines.
- `retrieve` — return content and finite graph context.
- `count` — count a selected set.
- `tree` — render inclusion hierarchy.
- `squash` — flatten inclusions into Markdown.
- `schema` — infer frontmatter shape and coverage.
- `schema validate` — validate documents or explain binding.
- `stats` — report structure and connectivity.
- `stats similarity` — find near-duplicate pages.
- `export` — render a selected graph as DOT.
- `update` — atomically mutate metadata or body blocks.
- `rename` — change key and rewrite references.
- `extract` — move a section into an included document.
- `inline` — replace an inclusion with target content.
- `attach` — include a source under configured destinations.
- `delete` — remove documents and clean references.
- `normalize` — canonically rewrite the whole library.
- `completions` — print completion scripts.
- `docs` — print requested embedded reference.

## Complex IWE queries

Filters are one inline YAML mapping. Plain fields mean equality. Use `$and`, `$or`, or `$not` only when one mapping cannot express the condition; `$in` for alternatives; comparisons for numeric/time bounds; `$exists` for presence; `$regex` for an actual pattern. Keep finite `maxDepth`/`maxDistance` in nested graph predicates.

Projection replaces defaults; additive fields retain them. Project content only when needed and pair it with token caps. One block predicate may select header, text, within, paragraph, or references. Carry the exact selector into mutation and add inline expect. Relationship flags are preferred for one anchor; nested predicates are for boolean combinations.

## Rare errors and fallback reference

First correct one obvious quoting/YAML error, look up unknown syntax once, refine one empty query once, narrow after truncation, and stop on schema/expectation failure.

Read `references/errors.md` only for: missing executable; still-unknown command/option; unexplained invalid YAML; empty result after refinement; unsupported operation; source outside index; unexplained truncation; permission/I/O failure; or unclear schema/expectation failure. It defines one response, fallback eligibility, reporting class, and retry ceiling—no normal task cases.

Fallback is allowed only when IWE cannot execute, reports unsupported operation, the source is outside the index, or one refinement stays empty. State why, read one known source narrowly, disclose it, and never scan/duplicate output.

## Completion

Report keys actually used, meaningful truncation, mutation preview scope, and any independent verification. Finish when every requested claim is supported and no redundant discovery, retrieval, or verification call remains.
