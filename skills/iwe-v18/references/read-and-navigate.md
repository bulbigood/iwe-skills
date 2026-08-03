# Read And Navigate

Use this reference for read workflows: discovery, hierarchy inspection, targeted retrieval, and context building.

## Contents

- [`iwe find`](#iwe-find)
- [`iwe tree`](#iwe-tree)
- [`iwe retrieve`](#iwe-retrieve)
- [`iwe count`](#iwe-count)
- [`iwe schema`](#iwe-schema)
- [`iwe stats`](#iwe-stats)
- [`iwe squash`](#iwe-squash)
- [`iwe export`](#iwe-export)

Official docs:

- Agentic tools: https://iwe.md/docs/agentic/
- CLI reference: https://iwe.md/docs/cli/
- CLI workflows: https://iwe.md/docs/cli/workflows/
- Query language: https://iwe.md/docs/concepts/query-language/
- `iwe squash`: https://iwe.md/docs/cli/squash/

For full filter syntax (operators, graph operators, projection, sort, `$set` / `$unset`), see [./query-language.md](./query-language.md). The sections below show how each read command consumes filter expressions.

## `iwe find`

Use `find` for discovery. The official docs describe it as the entry-point for fuzzy search, and the current CLI also sorts results by popularity when you omit the query.

```bash
iwe find
```

Use it to discover entry points, narrow to roots, inspect note relationships, or produce keys/JSON for the next step.

Current formats:

- `-f markdown`: human-readable titles with `#key` suffix and optional parent context
- `-f keys`: one key per line for piping
- `-f json`: structured results with metadata such as `incoming_refs` and `parent_documents`

Useful examples:

```bash
iwe find --fuzzy "authentication" --filter '$nor: [{ $includedBy: { match: {} } }]' -f keys
iwe find --filter '$nor: [{ $includedBy: { match: {} } }]' -f json
iwe find --references authentication              # docs that reference authentication
iwe find --referenced-by index                    # docs that index references
iwe find --lexical "$QUERY" --limit 5 -f keys
```

Frontmatter filter, projection, sort, and limit:

```bash
iwe find --filter 'status: draft'
iwe find --filter 'priority: { $gt: 3 }' --sort modified_at:-1
iwe find --filter '$or: [{ status: draft }, { status: review }]' -f keys
iwe find --included-by projects/alpha:5 --filter 'type: note'
iwe find --project title,status -f json
iwe find --add-fields 'body=$content' -f json
iwe find --matches '(?i)todo|fixme'
iwe find --blocks '{ $within: Goals, $text: "Q3" }'
iwe find --lexical "release notes" --max-tokens 4000 --max-document-tokens 1200 \
  --add-fields '$content'
```

Inline-YAML filters compose with `--fuzzy` / `--lexical` and the graph anchor flags via AND. See [./query-language.md](./query-language.md) for the full operator set.

Workflow:

1. Start with `iwe find --fuzzy "topic"` for title/key discovery, `iwe find --lexical "topic"` for BM25 title/body search, or `iwe find --filter '...'` when you know the frontmatter shape. Do not use the deprecated bare positional query.
2. If results are broad, add `--limit` or a tighter `--filter`. To select roots,
   use the supported `--roots` flag or the equivalent explicit filter
   `--filter '$nor: [{ $includedBy: { match: {} } }]'`.
3. Use `--references` / `--referenced-by` / `--includes` / `--included-by` when you already know one anchor key and want relationship-based discovery.
4. Use `--project` or `--add-fields` to shape JSON output before passing it on.
5. Pass the chosen key into `retrieve`.

## `iwe tree`

Use `tree` for hierarchy inspection.

```bash
iwe tree
```

Useful examples:

```bash
iwe tree
iwe tree --depth 5
iwe tree -k project-overview
iwe tree -f json
iwe tree --filter 'status: published'        # roots become docs with status==published
iwe tree --project status -f json            # add status to each tree node
```

Current behavior worth knowing:

- Default depth is `4`
- Without `-k`, `tree` starts from root documents
- With `-k`, `tree` starts from the specified key even if the note is not a root
- Formats are `markdown`, `keys`, and `json`
- In `-f keys`, nested children are indented with tabs rather than flattened into an unstructured list

Use `tree` for orientation, not full content retrieval. Increase depth only when you need a broader structural view.

## `iwe retrieve`

Use `retrieve` for context building.

```bash
iwe retrieve -k <KEY> \
  --expand-includes 1 \
  --expand-included-by 1
```

Parameters worth knowing:

- `-k` can be repeated to retrieve multiple anchor documents in one call.
- `--expand-includes [N]` follows child inclusion edges.
- `--expand-included-by [N]` follows parent inclusion edges.
- `--expand-references [N]` follows outbound inline-reference edges.
- `--expand-referenced-by [N]` follows inbound inline-reference edges.
- A bare expansion flag means depth 1; `0` means unbounded; omission means that edge is not followed.
- `-e KEY` excludes already-known document keys and is repeatable.
- `--children` populates each result's `includes` array; `--backlinks` is on by default and controls `referencedBy` metadata.
- `--limit` caps seeds before expansion. `--max-documents`, `--max-tokens`, and `--max-document-tokens` bound the final context.
- `retrieve` has neither `--dry-run` nor `--no-content`.

Practical defaults:

- Focused read: `iwe retrieve -k topic --expand-includes 1 --expand-included-by 1`
- Minimal read: `iwe retrieve -k topic`
- Broader bounded context: `iwe retrieve -k topic --expand-includes 2 --expand-included-by 2 --max-documents 25`
- Programmatic chaining: `iwe retrieve -k topic -f keys`
- Search and retrieve: `iwe retrieve --lexical "authentication flow" --limit 3 --expand-references 1`

Start without expansion, add only the graph directions the task needs, and use the output limits before requesting unbounded expansion.

Typical workflow from the official docs:

```bash
iwe find --fuzzy "authentication" --filter '$nor: [{ $includedBy: { match: {} } }]' -f keys
iwe retrieve -k authentication --expand-includes 2 --expand-included-by 1
iwe retrieve -k login-flow -e authentication
```

That is the core loop: discover an entry point, retrieve enough context, then follow adjacent notes with `-e` to avoid duplication.

## `iwe count`

Use `count` when the question is "how many?" rather than "which ones?". It accepts the same filter and graph flags as `find` and prints a single integer.

```bash
iwe count
iwe count --filter 'status: draft'
iwe count --filter 'priority: { $gte: 3 }'
iwe count --included-by projects/alpha
iwe count --included-by projects/alpha:5
```

Use `count` to size up a filter before running `find`, `update`, or `delete` against it. Combine with `--limit` to short-circuit large workspaces.

## `iwe schema`

Use `schema` to infer the frontmatter schema across the workspace. It is the right starting point before composing a non-trivial filter, because it shows which fields exist, their types, coverage, and (for low-cardinality fields) the actual value distribution.

```bash
iwe schema
iwe schema --filter 'type: post'
iwe schema --field status
iwe schema --field engagement -f json
iwe schema -f json > schema.json
```

Current behavior worth knowing:

- Only enumerable values are listed: null, booleans, numbers, and strings made of `[A-Za-z0-9_.-/]`. Free-text values are counted in coverage and types but not in the values listing.
- Value distribution is omitted for fields with more than 100 distinct enumerable values.
- `--filter` restricts analysis to a subset; `--field` drills into one field and its children.
- `--project` and `--add-fields` do not apply here; `schema` always reads raw frontmatter.
- Formats: `markdown` (aligned table), `json`, `yaml`.

Use `iwe schema validate` for the distinct task of validating documents against
schemas bound in `.iwe/config.toml`:

```bash
iwe schema validate
iwe schema validate -k notes/intro
iwe schema validate -k notes/intro --schema-file draft.yaml -f json
```

Clean validation prints nothing and exits 0. Violations exit 1; schema or
configuration errors exit 2.

## `iwe stats`

Use `stats` when the task is analytical rather than navigational.

```bash
iwe stats
```

Useful examples:

```bash
iwe stats
iwe stats -f csv > stats.csv
iwe stats -f csv | tail -n +2 | sort -t, -k12 -nr | head -5
iwe stats -k project-overview -f json
iwe stats similarity
iwe stats similarity --threshold 0.9
```

Use `stats` before proposing large reorganizations. Prefer `csv` only when another script should consume the output.

Current formats:

- `-f` and `--format` are equivalent
- `-f markdown`: overview plus reference, size, structure, and network sections
- `-f csv`: per-document rows with graph and content metrics

## `iwe squash`

Use `squash` when you want one combined markdown artifact.

```bash
iwe squash <KEY> [OPTIONS]
```

Useful examples:

```bash
iwe squash project-overview
iwe squash project-overview --depth 4
```

Current behavior worth knowing:

- Default depth is `2`
- `squash` writes combined markdown to stdout
- When linked content is inlined, headers are shifted down to preserve hierarchy

Use `squash` when you want one linear artifact for review, export, or LLM context. `squash` gives merged structure; `retrieve` gives navigable graph context.

## `iwe export`

Use `export` when you need a graph artifact for visualization or downstream tooling.

```bash
iwe export -f dot
```

Useful examples:

```bash
iwe export -f dot
iwe export -f dot --key project-overview --depth 1
iwe export -f dot --key project-overview --depth 1 --include-headers
```

Current behavior worth knowing:

- The only supported export format is currently `dot`
- Without `--key`, export starts from root notes
- `--include-headers` adds document structure detail to the graph output
- `export` writes the DOT graph to stdout and does not mutate notes
