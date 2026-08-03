---
name: iwe-v18
description: Use for IWE 0.18 knowledge-graph retrieval and safe Markdown refactors. Prefer bounded IWE commands over filesystem discovery.
compatibility: Requires IWE CLI >=0.18.0 and <0.19.0.
metadata:
  version: "0.2.0"
---

# IWE 0.18 execution policy

Use IWE for graph-aware discovery, retrieval, querying, and structural changes in an IWE Markdown workspace. IWE is authoritative for operations supported by this contract.

## Mandatory rules

- Start with the known IWE 0.18 command that directly answers the request.
- Do not run routine preflight such as version, status, schema, or command-help checks.
- Do not use web search, `grep`, `rg`, `find`, recursive directory listing, or broad multi-file reads to duplicate supported IWE discovery.
- Do not install, update, configure, or repair IWE.
- Do not consult external IWE documentation or invoke the built-in documentation command.
- Default result limit: 20. Use a smaller limit when it is sufficient.
- Request JSON and only the fields or content needed for the task.
- Never use `0` for a result, depth, distance, document, or token limit; in IWE 0.18 it means unlimited.
- Prefer one precise command over several broad commands.
- Stop as soon as the returned evidence is sufficient.

## Default read workflow

1. Translate the request into one bounded `find` or `retrieve` command.
2. Use `find --fuzzy` for partial title/key discovery and `find --lexical` for body text.
3. Use filters or relationship flags when the request already supplies structured criteria or an anchor key.
4. Project metadata without full content when titles, keys, fields, or relationships are enough.
5. Use `retrieve` when full content or bounded graph expansion is required.
6. Reuse returned document keys. Do not search again by filename when a key is known.
7. Stop after the first command when its result is unambiguous.

Do not run a second query merely to confirm evidence that is already clear. A second IWE command is allowed only to retrieve selected keys, resolve genuinely ambiguous results, or refine one well-formed query that returned no result.

### Bounded discovery

```bash
iwe find --lexical "<terms>" --limit 20 --project 'key=$key,title=$title' --format json
```

Combine fuzzy and lexical matching in this same command when both title/key tolerance and body relevance matter. Add a filter or relationship anchor to narrow results rather than increasing the limit.

### Bounded graph retrieval

```bash
iwe retrieve --lexical "<terms>" --limit 5 --expand-included-by 1 --max-documents 12 --max-tokens 6000 --max-document-tokens 1200 --format json
```

Seed limits apply before expansion. Pair expansion with all three maxima above and use positive depths. For a known key use `iwe retrieve --key "<key>" --limit 1 --max-documents 1 --max-tokens <positive> --max-document-tokens <positive> --format json`; the key is not positional.

## Query selection

Use fuzzy search for incomplete titles, keys, or spelling fragments. Use lexical search for concepts or words expected in document bodies. Use `--filter` for frontmatter values and graph predicates. Use relationship flags for included, including, referenced, or referencing documents.

Simple filters belong directly in the command. Read `references/query-language.md` only when the required nested boolean, comparison, projection, sort, or graph predicate cannot be expressed by the patterns in this file.

An empty result is not proof that IWE is unusable. Refine the IWE query once after checking the intended search mode and quoting; use a narrower or alternate well-formed query.

## Precise mutation workflow

Use IWE structural operations instead of hand-editing graph links or reconstructing whole documents. For localized body changes:

1. Locate the exact document and blocks with one bounded `find --key ... --blocks ...`, `--matches`, or targeted retrieval.
2. Combine independent block operators for the same document in one guarded `update` when practical.
3. Preview with `--dry-run`; require document-level `--expect` plus inline `expect` on every block operator.
4. Apply the identical command with `--strict` after the preview is exact.
5. Retrieve the affected key once and verify the intended changes and unrelated content.

```bash
iwe update --key "<key>" --replace-text '{ $header: "<old>", to: "<new>", expect: 1 }' --append '{ $header: "<section>", content: "<text>", expect: 1 }' --expect 1 --strict --dry-run
```

After the preview, remove only `--dry-run` for the real mutation. Do not use body-overwrite mode for a section, paragraph, list, heading, or isolated text change.

For section extraction, the source key is positional and the heading uses `--section`:

```bash
iwe extract "<source-key>" --section "<heading>" --dry-run --format keys
```

After an exact preview, remove only `--dry-run`, capture the generated key from the real operation, then retrieve the source and generated keys for verification. Do not guess unsupported `--header`, `--target-key`, or update operators; use command-specific help only after the CLI rejects known syntax.

Keep typed template variables separate from frontmatter. Example: `iwe create --template <name> --vars-json '{"title":"<title>","attendees":["<name>"],"body":"<text>"}' --set type=<type> --set draft=false --strict --if-exists fail`. `title` and `body` are conventional; do not rename `body` after its rendered heading. JSON preserves types and `--set` parses YAML, so `draft=false` is boolean. Create has no `--format` flag and prints a path; the key omits `graph/` and `.md`. Strict creation already validates the schema, so do not add validation or update calls after success.

## Destructive operations

Deletion, inlining that removes its target, normalization, and broad mutations can discard data. Preview the exact affected keys, establish a rollback point when practical, and obtain fresh, focused confirmation immediately before the destructive command.

Default to preserving the target when resolving inclusion links. Never use an empty filter for update or delete unless the user explicitly requests a workspace-wide operation and the required confirmation has just been obtained. Efficiency budgets never override mutation safety, preview, confirmation, or verification.

## Failure handling

If a command fails, read stderr. Correct an obvious input or shell-quoting error once. If stderr reports an unknown command or option, run only `iwe <command> --help`, correct the syntax, and retry once. Do not run global help, version checks, documentation commands, web searches, or repeated speculative retries.

Read `references/errors.md` only when stderr does not explain the failure or when deciding whether the narrow fallback conditions below are satisfied.

## Fallback

Fallback repository tools are allowed only when IWE cannot execute, explicitly reports the operation unsupported, the requested source is outside the indexed IWE workspace, or one well-formed refinement still returns no result. They are also allowed when the user explicitly requests another mechanism.

Before fallback, state briefly why IWE cannot perform the operation, and include that reason in the final response. Use one narrow targeted read or search when the exact source is known. For Markdown, read a bounded span of the exact file and interpret its headings; do not search for frontmatter-style `Heading:` text when the target is a `## Heading` section. If that fallback fails, report the failure instead of broadening or repeating it. Do not perform a recursive scan or duplicate successful IWE output.

## Completion

Report the keys used and any truncation warning relevant to confidence. For writes, report preview scope and post-write verification. Finish when every claim needed for the request is backed by bounded IWE output and no redundant discovery was performed.
