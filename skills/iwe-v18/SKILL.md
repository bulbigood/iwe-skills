---
name: iwe-v18
description: Use IWE CLI to find, retrieve, analyze, create, update, or safely refactor an IWE Markdown knowledge graph.
compatibility: Requires IWE CLI >=0.18.0.
metadata:
  version: "0.6.0"
---

# IWE problem-solving policy

IWE is authoritative for indexed graph and note content. Choose the narrowest route that can answer the request, then stop.

## Decision order

Apply these rules top to bottom. A terminal rule ends route selection; a later general rule cannot reopen it.

1. **Hard stop.** Hard stops run before every IWE-first rule. For an undefined destructive criterion, scope, or recovery, use no task tools. Explain what is missing and request the minimum criteria, scope, rollback, and fresh, focused confirmation needed to proceed. Never discover candidates merely to make an unsafe request concrete.
2. **Out of scope.** Do not activate IWE for ordinary source-code work or unrelated workspace tasks.
3. **Known direct operation.** When the request or prior evidence supplies the exact target and operation, execute that route directly. Do not run discovery or validation as preflight.
4. **Single rich read.** Mixed-output requests use the richest single route that returns every required evidence class. If bounded `retrieve` returns prose, keys, fields, and relationship metadata, do not prepend `find` or append a second read.
5. **Candidate discovery.** Use `find` only when identity is unresolved or projected metadata is itself the answer. Relevance gate before every candidate retrieval. An unrelated candidate is a terminal miss, not ambiguity.
6. **Fallback.** Use the narrow fallback policy only after IWE cannot execute, lacks the operation, stays empty after one justified refinement, or returns only unrelated candidates.
7. **Stop.** Stop after sufficient evidence. Never issue a confirmation query merely to improve richness.

## Hard execution rules

- Do not use web search. Work offline.
- Do not run routine preflight, global help, version, status, docs, recursive listing, broad file reads, or filesystem search before the selected IWE route.
- Do not install, update, configure, or repair IWE.
- Exact command help is allowed once as `iwe <command> --help` only after that command fails and its error cannot support one direct correction.
- Default result limit: 20. Prefer a smaller request-derived positive limit; zero means unlimited and is forbidden.
- Prefer one read call. A second IWE read is the final read call. Mutation preview/apply calls are separate.
- A second retrieve is allowed only when a material named facet is absent and the answer would otherwise be incomplete. Refine the IWE query once with that facet plus the shared topic; do not repeat existing evidence or raise limits reflexively.
- Use typed YAML/JSON values. Preserve booleans, numbers, lists, and maps; quote numeric-looking or boolean-looking strings when they are strings.
- Treat a stated semantic class such as project, task, person, or meeting as a hard typed filter or creation type.

## Core routes

| Request shape | First route | Stop or continue |
|---|---|---|
| Exact key plus fact or body | bounded `retrieve --key` | Stop when the fact is present |
| Prose summary, comparison, relationship explanation, or mixed prose plus metadata | one bounded `retrieve` containing all named entities and the shared topic | Stop when all material named facets are present |
| Unknown identity, projected fields, keys, titles, blocks, matching lines, or a candidate list | shaped `find` | Stop if projection answers; otherwise apply relevance before one candidate retrieve |
| Count | `count` with the narrow selector | Stop; do not infer content from quantity |
| Hierarchy or flattened inclusion artifact | `tree` or `squash` | Stop after the requested bounded artifact |
| Schema shape, validation, or binding | `schema` or `schema validate` | Stop after direct validation evidence |
| Health, duplicates, or graph visualization | `stats`, `stats similarity`, or `export` | Use a finite selected scope |
| Known create/update/refactor target | direct guarded mutation route | Preview/apply only when required below |

Mixed-output requests use the richest single route. Relationship metadata needed alongside prose does not independently require `find`. Literal graph edges must come from returned references/includes; thematic co-retrieval is not an edge.

### Route parameters

- **Selector:** exact key uses `--key`; typed fields use `--filter`; incomplete identity uses `--fuzzy`; body concepts use `--lexical`; known graph anchors use the appropriate relationship selector.
- **Query:** preserve distinctive names, nouns, and quoted terms. Comparisons include every named entity and the shared topic.
- **Count:** one named or prepared target uses limit 1. Explicit N uses N. “A few” uses 5. Use 2–5 only for a genuinely ambiguous relevant candidate set.
- **Shape:** identities use keys; metadata uses projection; sections use blocks; literal line matching uses matches; prose uses retrieve. Do not return bodies for lists or counts.
- **Graph bounds:** direct context uses depth/distance 1 unless the request states another positive finite bound.
- **Token bounds:** use about 800 tokens per document for a fact, 1200 for a summary, 2000 for detail, and up to 4500 for one authored synthesis. Keep the total normally at or below 8000.

### Relevance and stopping

Relevance gate before every candidate retrieval:

1. Compare the requested distinctive entity, facet, or direct synonym with the candidate key/title and shaped metadata.
2. Generic document-type words do not establish relevance.
3. No distinctive overlap means terminal miss; do not retrieve the candidate.
4. Ambiguous relevant candidate sets may receive one bounded retrieve of the best supported winner.
5. If discovery output already answers the requested scope, stop without retrieving.

Examples:

```bash
iwe find --lexical "<distinctive terms>" --limit 5 --project 'key=$key,title=$title' --format json
iwe retrieve --lexical "<all named entities> <shared topic>" --limit 1 --max-documents 1 --max-tokens 5000 --max-document-tokens 4500 --format json
iwe update --key "<key>" --replace-text '{ $header: "<old>", to: "<new>", expect: 1 }' --append '{ $header: "<section>", content: "<text>", expect: 1 }' --expect 1 --strict --dry-run
iwe extract "<source-key>" --section "<known heading>" --dry-run --format keys
```

## Mutation routes

### Create

Use `new` for a simple title/body note. Use `create` for an explicit key, template, typed document, or schema-bound document. Supply all known variables and typed frontmatter in one call, use strict validation, and declare collision behavior. Explicit keys default to collision `fail`; suffixing is acceptable only when identity is not fixed. Template body is a variable such as `"body":"<text>"`; do not duplicate it as frontmatter. Create has no `--format` flag. A successful strict create proves the final key and schema result; stop.

### Local update

Use `update` and combine disjoint same-document operations atomically. Prefer exact key and exact block/header selectors. Every local block operator carries inline `expect`; the document selection carries `--expect`. Call 1 is the exact dry-run and call 2 removes only `--dry-run`. Do not overwrite a whole body for a local edit. Verify one exact key only when guarded output cannot prove preservation or final content.

### Structural refactor

Use `rename`, `extract`, `inline`, or `attach` directly when source, destination, and section are known. Preview and apply identical arguments. After extract, verify only with one bounded source retrieve if the command result cannot prove the new inclusion. Do not discover relationships or retrieve the newly created target merely to verify an extract. Omitting `keep-target` during inline is destructive and requires explicit deletion intent and confirmation.

### Destructive work

The hard stop in Decision order always runs first.

- Exact one-note deletion: establish recovery when practical, preview the exact key with strict expectation 1, inspect affected keys, obtain fresh, focused confirmation, then apply unchanged.
- Cohort deletion: require a user-defined criterion and scope, preview a narrow typed filter with a user-derived expected count/range, inspect affected keys, confirm, then apply unchanged. Never decide what “obsolete” means.
- Normalize: this is a workspace-wide in-place rewrite without preview. Require explicit scope, established rollback, and fresh, focused confirmation; verify afterward.

Safety calls are necessary work, not efficiency waste.

## Fallback

Fallback is allowed only for a missing executable, unsupported operation, source outside the index, one still-empty refinement, or unrelated candidates. Failed and corrected IWE attempts count toward the two-read-call budget; never call IWE a third time.

- If the requested source scope is IWE, graph, notes, or docs, report not found and stop without scanning files.
- For a workspace/project question with a known path, read only that path or named section. Do not discover filenames or headings.
- For an unknown path, begin with one targeted hidden-aware content search. Search one literal request-derived field token. Do not require related terms to occur on the same line. Do not emit a workspace-wide inventory.
- After one content miss, refine once or use one narrowly globbed filename. If search output proves both value and source path, stop; otherwise read only the candidate source.
- Stay local and expose no unrelated matches. Say “IWE is unavailable” only after execution failure; otherwise state that the information was found outside IWE.

## Complex IWE queries

Filters are one inline YAML mapping. Plain fields mean equality. Use `$and`, `$or`, or `$not` only when one mapping cannot express the condition; `$in` for alternatives; comparisons for numeric/time bounds; `$exists` for presence; `$regex` only for an actual pattern. Keep graph depth and distance finite.

Projection is `alias=source`. Aliases are free; sources must be `$key`, `$title`, or exact fields from the request, schema, or prior output. If no source is known, omit projection. If an optional shaping flag is rejected, remove only that flag/value, preserve the rest of the command, and retry once.

Relationship flags take known key anchors, not booleans. Carry selectors and expectations unchanged from mutation preview to apply.

## Rare errors

A self-explanatory missing executable goes directly to fallback. Otherwise read `references/errors.md` only after an actual failure remains unclear. It covers invalid YAML, still-unknown command or option, empty refinement, unsupported operation, source outside index, truncation, permission/I/O failure, and schema/expectation failure. Do not read the reference proactively.

## Completion

Report `Result`, supporting `Keys` or source path, any `Truncation`, and for mutations the `Scope` and `Verification`. Distinguish literal graph relationships from thematic synthesis. Stop when every claim is supported.