---
name: iwe-memory-system
description: "Use this skill when working in an IWE knowledge-graph workspace, especially to help an agent read, navigate, retrieve context from, query frontmatter, and safely refactor Markdown notes with the `iwe` CLI instead of ad-hoc file edits. Covers project discovery, inclusion links, context-building, analysis, the frontmatter query language, and the IWE 0.18.0 command surface: `init`, `create`, `new`, `retrieve`, `find`, `count`, `normalize`, `tree`, `squash`, `export`, `schema`, `stats`, `rename`, `delete`, `extract`, `inline`, `update`, `attach`, `completions`, and `docs`."
metadata:
  version: 0.0.69
  iwe_cli_version: 0.18.0
---

# IWE

IWE is local-first and markdown-based. Prefer `iwe` commands for graph-aware reads and refactors, and only fall back to direct file edits when the CLI does not cover the task.

IWE does not impose a single graph structure or file naming convention. Do not assume a particular hierarchy, naming scheme, or note layout unless the workspace itself shows one.

Bundled references (use these first; they are pinned to IWE 0.18.0):

- Docs index: https://iwe.md/docs/
- Agentic tools: https://iwe.md/docs/agentic/
- Inclusion links: https://iwe.md/docs/concepts/inclusion-links/
- Query language: https://iwe.md/docs/concepts/query-language/
- CLI reference: https://iwe.md/docs/cli/

The linked files below contain the complete CLI help and every built-in
`iwe docs` topic. An agent using this skill should not need internet access,
`iwe --help`, `iwe <command> --help`, or `iwe docs` for normal 0.18.0 work.

## Compatibility

This skill is adapted and mechanically checked against **IWE CLI 0.18.0**. The
skill version (`metadata.version`) and the adapted CLI version
(`metadata.iwe_cli_version`) are independent.

Do **not** run `iwe --version` merely because this skill is loaded. Use the
installed CLI normally. Investigate a version mismatch only after an IWE
interaction fails or behaves unexpectedly. First consult the bundled complete
references. If they still disagree with runtime behavior, run `iwe --version`,
report the incompatible instruction, and only then consult installed help.

## Quick start

1. Confirm the workspace is an IWE project by checking for the `.iwe/` marker directory.
2. If `.iwe/config.toml` exists, read it before assuming where notes live;
   `library.path` may point to a subdirectory. If it is absent, use IWE's defaults.
3. Use `iwe find --fuzzy`, `iwe find --lexical`, `iwe tree`, and `iwe retrieve`
   to explore before editing. Bare positional queries to `find` are deprecated.
4. Use `iwe schema` to learn the frontmatter shape, then `iwe find --filter` / `iwe count --filter` to query by frontmatter.
5. Use `iwe stats` for analysis and `iwe squash` when one linear markdown artifact is more useful than graph-shaped retrieval.
6. For structural note changes, prefer `iwe new`, `iwe extract`, `iwe inline`, `iwe rename`, and `iwe delete`. For frontmatter mutations, prefer `iwe update --set` / `--unset`.
7. Use preview modes such as `--dry-run` only when the specific command supports
   them. Consult `references/cli-reference.md` when exact flags matter; do not
   infer shared options across commands.

## Precise markdown edits

When changing a heading, paragraph, list, or content inside a known section, do
not use body-overwrite mode (`iwe update -c`) and do not reconstruct the whole
document. Use structured block mutation:

1. Locate the exact target with `iwe find -k KEY --blocks PREDICATE` (or
   `--matches` for regex discovery). `--blocks` accepts one inline mapping and
   may appear only once per command. Run separate `find` commands when you need
   to inspect two unrelated selectors; do not repeat the flag or invent an
   expression syntax such as `type == "reference"`.
2. Preview the intended `iwe update` block operator with `--dry-run`.
3. Put an inline `expect` guard in every block operator and a document-level
   `--expect`; use `--strict` for the real mutation.
4. Apply `--replace-text`, `--replace`, `--append`, `--insert-before`,
   `--insert-after`, or `--delete` as appropriate.
5. Retrieve the document by explicit key with `iwe retrieve -k KEY` and verify
   unrelated blocks were preserved.

Body-overwrite mode is only for a user-requested complete body replacement. It
is not a shortcut for a localized edit.

## Inclusion links

IWE treats a markdown link on its own line as structure, not just a normal inline reference. That standalone link creates a parent-child relationship in the knowledge graph.

In practice, an inclusion link should be surrounded by blank lines. If adjacent inclusion links are written back-to-back with no empty line between them, IWE can treat them as inline content instead of structural links.

This distinction matters:

- A standalone link is an inclusion link and affects hierarchy and graph
  expansion such as `retrieve --expand-includes` and
  `retrieve --expand-included-by`.
- A link inside a sentence is an inline link and only expresses a reference relationship.

Preserve that distinction. Keep inclusion links on their own lines with an empty line before and after each one. Do not append prose to an inclusion link line or rewrite it into inline text unless the user explicitly wants the hierarchy changed.

Example:

```md
# Photography

[Composition](composition)

[Lighting](lighting)

```

The two child links above are structural because each link is isolated by blank lines. They are not equivalent to writing a sentence like `See [Composition](composition) for more.`, and they should not be written back-to-back with no empty line between them.

## Reference map

- For project discovery and config assumptions, read [./references/project-setup.md](./references/project-setup.md).
- For read and navigation flows, read [./references/read-and-navigate.md](./references/read-and-navigate.md).
- For write and refactor flows, read [./references/write-and-refactor.md](./references/write-and-refactor.md).
- For the frontmatter query language used by `--filter` (operators, projection, sort, `$set` / `$unset`), read [./references/query-language.md](./references/query-language.md).
- For the complete `iwe 0.18.0 --help` contract for every command and nested
  subcommand, read [./references/cli-reference.md](./references/cli-reference.md).
- For the complete offline query-language, configuration, and document-schema
  manuals embedded in IWE 0.18.0, read
  [./references/builtin-reference.md](./references/builtin-reference.md).

## Guardrails

- Do not assume markdown files live at repository root; check `library.path`.
- Do not assume a particular graph structure or file naming convention.
- Do not hand-edit references if `iwe` already has a safe operation for that change.
- Do not place consecutive inclusion links with no blank line between them.
- Do not retrieve large context blindly. `retrieve` has no `--dry-run`; bound it
  with seed `--limit`, post-expansion `--max-documents`, `--max-tokens`, and
  `--max-document-tokens`, then expand deliberately.
- Preview `iwe delete`, establish the exact matched keys, and obtain fresh,
  focused confirmation immediately before the real deletion.
- Run `iwe inline` with `--keep-target` unless deleting the target document is
  explicitly intended. Preview and obtain fresh, focused confirmation before
  inlining without `--keep-target`.
- If the task is a structural change and the CLI supports it, use the CLI instead of editing markdown references by hand.
- For frontmatter changes on more than one document, prefer `iwe update --filter ... --set/--unset` over manual edits, and run with `--dry-run` first.
- Treat `iwe update --filter '{}'` and `iwe delete --filter '{}'` as workspace-wide operations; never run them without explicit user intent.
- If exact command arguments matter, consult the bundled CLI reference instead of guessing flags or invoking help.
- Do not proactively compare IWE versions. Only diagnose version compatibility
  after a real command problem reveals that this skill disagrees with runtime
  behavior; consult installed help only as the final compatibility fallback.
- Treat `iwe normalize` as an in-place bulk rewrite of the whole library, not a
  harmless read command. Establish a rollback point or backup when practical,
  then obtain fresh, focused confirmation immediately before running it.
- Treat `iwe export` and `iwe squash` as artifact-generation commands that do not mutate notes unless you redirect their output into files yourself.
- After a write operation, inspect affected files or rerun `find` or `retrieve` if you need to confirm the graph state.
