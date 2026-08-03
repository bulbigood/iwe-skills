# IWE 0.18.0 CLI Reference
This file is generated from the complete `--help` output of `iwe 0.18.0`. Use it when exact command syntax matters. The workflow-oriented references explain when to use the commands; this file preserves the CLI contract.

Regenerate or verify it with:

```bash
python3 skills/iwe-memory-system/scripts/generate-cli-reference.py
python3 skills/iwe-memory-system/scripts/generate-cli-reference.py --check
```

## `iwe`

```text
Usage: iwe [OPTIONS] <COMMAND>

Commands:
  init         Initialize the current directory as an IWE project
  create       Create a document
  new          Create a new document from a title
  retrieve     Retrieve document content with expansion and context
  find         Search and discover documents
  count        Count documents matching a filter
               
  normalize    Normalize all markdown files in the project
  tree         Display document hierarchy as a tree
  squash       Consolidate linked documents into a single file
  export       Export the graph structure in various formats
  schema       Infer and display frontmatter schema
  stats        Display graph statistics
  rename       Rename a document and update all references to it
  delete       Delete a document and clean up all references to it
  extract      Extract a section to a new document with an inclusion link
  inline       Replace an inclusion link with the referenced document content
  update       Update document content or frontmatter
  attach       Attach a document as a block reference via configured attach actions
  completions  Generate shell completion script
  docs         Print built-in reference documentation
  help         Print this message or the help of the given subcommand(s)

Options:
  -v, --verbose <VERBOSE>  [default: 0]
  -h, --help               Print help
  -V, --version            Print version

Run 'iwe docs' for the built-in query language, configuration, and document schema references.
```

## `iwe init`

```text
Initialize the current directory as an IWE project.

Scans the existing markdown files, fits the configuration to what it finds, and
writes .iwe/config.toml. Nothing outside .iwe/ is touched unless the agent
artifacts are opted into.

At a terminal, init shows the detected settings next to the iwe defaults —
only the rows where they differ — with the number of files `iwe normalize`
would rewrite under each column. Answer y (or press Enter) to write the
detected settings, n to write the defaults, or q to quit without writing.
With no terminal attached, init behaves as --auto.

Detection covers the library directory, source format, link style and path
conventions, date formats, key naming, search language, and the markdown
formatting tokens. Every value is labelled detected, assumed, or overridden,
and each detected value is written with a comment citing its evidence.

Modes:
- --auto (-y): write the detected configuration without prompting
- --dry-run: print the proposed configuration and evidence, write nothing
- --defaults: write the static template, skipping detection entirely
- --json: emit a machine-readable report; combines with --auto and --dry-run

Per-setting overrides apply on top of detection in every mode:
--library, --link-format, --refs-extension, --format, --date-format

Exit codes:
- 0: configuration written, or dry run completed
- 2: already initialized
- 1: any other failure

Prerequisites:
- The .iwe directory must not already exist in the current location


Usage: iwe init [OPTIONS]

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -y, --auto
          Write the detected configuration without prompting

      --dry-run
          Print the proposed configuration and evidence, write nothing

      --defaults
          Write the static default template without detection

      --json
          Print a machine-readable report

      --library <LIBRARY>
          Subdirectory holding the markdown files

      --link-format <LINK_FORMAT>
          Link format to write
          
          [possible values: wiki, markdown]

      --refs-extension <REFS_EXTENSION>
          File extension written inside markdown links

      --format <FORMAT>
          Source format for the library
          
          [possible values: markdown, djot]

      --date-format <DATE_FORMAT>
          Date format used for keys of date-named documents

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Detect settings and choose between them at a terminal
  iwe init

  # Accept the detected settings without prompting
  iwe init --auto

  # Inspect the evidence before committing to anything
  iwe init --dry-run

  # Let an agent read the full report, then apply a reviewed decision
  iwe init --dry-run --json
  iwe init --auto --link-format wiki --library notes

  # Skip detection and write the static template
  iwe init --defaults

  # After initialization, edit config
  $EDITOR .iwe/config.toml

OUTPUT:

  Writes .iwe/config.toml, each detected value preceded by a comment citing
  its evidence. Prints a scan summary, any warnings, and how many files
  `iwe normalize` would rewrite.

  Exits 2 if .iwe already exists.
```

## `iwe create`

```text
Create a document in one of two explicit modes.

Content mode (the default) writes the document you pass, byte for byte: frontmatter
first, then the markdown, normally starting with the title heading. The key is
required -- it is the document's identity.

Template mode (--template NAME) composes the document from a named template in the
configuration. The template name is always required. Variables come from --var,
--vars-yaml and --vars-json, frontmatter fields from --set, and the key is derived
from the template's key_template unless you pass one.

--content and --template are mutually exclusive.


Usage: iwe create [OPTIONS] [KEY]

Arguments:
  [KEY]
          Document key. Required in content mode. In template mode, omit it to derive the key from the template's key_template. Subdirectory keys allowed (e.g. people/ada); omit the file extension.

Options:
  -c, --content <CONTENT>
          The complete document, frontmatter and title heading included, written verbatim. Use '-' to read from stdin.

  -v, --verbose <VERBOSE>
          [default: 0]

  -t, --template <NAME>
          Compose the document from the named template in the configuration

      --vars-yaml <YAML>
          YAML mapping of template variables. Values keep their YAML types: booleans, numbers, lists, nested maps. Requires --template.

      --vars-json <JSON>
          JSON object of template variables. Values keep their JSON types: booleans, numbers, arrays, nested objects. Requires --template.

      --var <NAME=VALUE>
          Set a single template variable, NAME=VALUE with VALUE used verbatim as a string. Repeatable; always overrides --vars-yaml/--vars-json, wherever it appears. Requires --template.

      --set <FIELD=VALUE>
          Set a single frontmatter field, FIELD=VALUE with VALUE parsed as YAML, written above the rendered document. Repeatable; the last one for a field wins. Requires --template.

  -i, --if-exists <IF_EXISTS>
          Behavior when the document already exists: fail (error), skip (do nothing), and in template mode suffix (append -1, -2, etc.) or override (overwrite). Default: fail, except in template mode without a key, where the derived key gets suffix.
          
          [possible values: suffix, override, skip, fail]

      --strict
          Validate the document against the configured schema before writing

  -e, --edit
          Open created file in $EDITOR

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Content mode -- the document is written exactly as passed
  # (continuation lines start at column 0, so these examples copy cleanly)
  iwe create projects/overview --content '# Overview

The first paragraph.'

  # Content mode from stdin
  cat doc.md | iwe create projects/overview

  # Template mode with the stock template
  iwe create --template default --var title="Standup notes"

  # Template mode with another template and frontmatter
  iwe create --template meeting --var title="Sync" --set type=note

  # All variables at once, keeping their types
  iwe create -t meeting --vars-yaml 'title: Sync
attendees: [ada, alan]
draft: false'

  iwe create -t meeting --vars-json '{"title": "Sync", "draft": false}'

CONTENT MODE:

  --content takes the whole document, including its frontmatter block and title
  heading, and writes it verbatim. '--content -' always reads stdin to the end,
  terminal included (finish with Ctrl-D); bare piped input is read the same way.
  --if-exists accepts fail (default) or skip; an explicit key names one
  document, so there is no suffix, and replacing a document is `iwe update`.

TEMPLATE MODE:

  --template NAME names the template to compose from; the name is always
  required. Nothing here is implicit: --var, --vars-yaml, --vars-json and --set
  all require --template.

  --var NAME=VALUE sets one variable and its VALUE is used verbatim as a string,
  never parsed: --var body='## Notes' is that heading, literally. Repeat it as
  needed; among --var flags the last assignment for a name wins.

  Typed values come from the bulk forms -- --vars-yaml '<YAML mapping>' or
  --vars-json '<JSON object>', at most one per command. Their booleans, numbers
  and lists reach the template as such, so {% if %} and {% for %} work. The bulk
  mapping is applied first and every --var overrides it, wherever the flags sit
  on the command line. Note that --var draft=false is the string "false", which
  {% if draft %} reads as true -- write 'draft: false' in --vars-yaml when you
  mean the boolean. A null value is rejected; pass '' for an empty value.

  By convention 'title' names the title and 'body' the prose slot; {{content}}
  is a legacy alias for {{body}}. Template mode never reads stdin -- piped input
  is content mode's. Every variable arrives through a flag; a variable no flag
  sets renders as empty.

  Multiline prose goes in a --vars-yaml block scalar:

    iwe create -t note --vars-yaml 'title: Release
body: |
  ## Notes

  Shipped.'

  slug, today, now and id are computed by iwe and cannot be set as variables.

  --set FIELD=VALUE sets one frontmatter field, written above the rendered
  document. Repeat it as needed; fields are applied in command-line order and the
  last one for a field wins. Unlike --var, VALUE is parsed as YAML -- variables
  are render text, frontmatter is data. There is no bulk frontmatter flag; write
  a mapping as repeated --set. Fields starting with _ $ . # or @ are reserved and
  dropped.

TEMPLATE VARIABLES:

  - {{title}}: from --var title=VALUE
  - {{body}}: from --var body=VALUE ({{content}} is an alias)
  - {{slug}}: URL-safe form of the title variable
  - {{today}}: current date (library.date_format for the key,
               markdown.date_format for the document)
  - {{now}}: current date and time (library.time_format for the key,
             markdown.time_format for the document; each falls back to the
             matching date_format when unset)
  - {{id}}: unique identifier

OUTPUT:

  Prints the absolute path to the created file:

    /path/to/library/projects/overview.md

  Returns empty output if --if-exists skip and the document exists.
```

## `iwe new`

```text
Create a new document from a title.

Creates a markdown file using the specified template, generates filename from the
title (slugified), and prints the absolute path to stdout. Supports content from
command-line argument or stdin pipe. Pass --key to set the document key yourself
and bypass the template's key derivation.

Templates support variables: {{title}}, {{slug}}, {{today}}, {{now}}, {{id}}, {{content}}

Usage: iwe new [OPTIONS] <TITLE>

Arguments:
  <TITLE>
          Title for the new document

Options:
  -t, --template <TEMPLATE>
          Template name from config

  -v, --verbose <VERBOSE>
          [default: 0]

  -c, --content <CONTENT>
          Content for the new document

  -k, --key <KEY>
          Explicit document key, bypassing the template's key derivation. Subdirectory keys allowed (e.g. people/ada); omit the file extension. Defaults --if-exists to fail.

  -i, --if-exists <IF_EXISTS>
          Behavior when file already exists: suffix (append -1, -2, etc.), override (overwrite), skip (do nothing), fail (error). Default: suffix, or fail when --key is given.
          
          [possible values: suffix, override, skip, fail]

  -e, --edit
          Open created file in $EDITOR

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Create document with default template
  iwe new "My Document Title"

  # Create with specific template
  iwe new "Meeting Notes" --template meeting

  # Create with inline content
  iwe new "Quick Note" --content "This is the body text"

  # Create from piped content
  echo "Generated content" | iwe new "Generated Doc"

  # Open in editor after creation
  iwe new "Draft Document" --edit

  # Handle existing files
  iwe new "Existing" --if-exists override  # Overwrite
  iwe new "Existing" --if-exists skip      # Do nothing
  iwe new "Existing" --if-exists suffix    # Create with -1, -2, etc.
  iwe new "Existing" --if-exists fail      # Error and exit non-zero

  # Create at an explicit key (bypasses key_template; fails if it exists)
  iwe new "Ada Lovelace" --key people/ada

TEMPLATE VARIABLES:

  Templates in config support these variables:
  - {{title}}: Document title as provided
  - {{slug}}: URL-safe filename derived from title
  - {{today}}: Current date (uses library.date_format for key,
               markdown.date_format for content)
  - {{now}}: Current date/time (uses library.time_format for key,
             markdown.time_format for content; falls back to the
             matching date_format when time_format is unset). Supports
             date (%Y, %m, %d) and time (%H, %M, %S) specifiers.
  - {{id}}: Unique identifier
  - {{content}}: Content from --content or stdin

OUTPUT:

  Prints the absolute path to the created file:

    /path/to/library/my-document-title.md

  Returns empty output if --if-exists skip and file exists.
```

## `iwe retrieve`

```text
Retrieve documents from the knowledge graph and expand the graph around them.

By default only the requested document(s) are returned. Each --expand-* flag
follows one edge kind out from every seed and pulls the reached documents in:

1. Seed documents (-k, search, or stdin)
2. Children (--expand-includes N levels down)
3. Parent context (--expand-included-by N levels up)
4. Outbound reference links (--expand-references N levels)
5. Inbound reference links (--expand-referenced-by N levels)

Without -k, --filter, --lexical/--fuzzy, or stdin, the command exits with an
error. -k accepts repeats and resolves to $key (1 key = $eq, 2+ = $in). Use
--filter / --included-by / --references / etc. to narrow the seed set; explicit
keys are intersected with the filter. Empty intersection produces an empty result.
With --lexical/--fuzzy the seeds are found by relevance within that set; --limit
caps the seeds before expansion.


Usage: iwe retrieve [OPTIONS]

Options:
      --expand-includes [<N>]
          Expand into child documents to depth N (bare = 1, 0 = unbounded, omitted = not followed).

  -v, --verbose <VERBOSE>
          [default: 0]

      --expand-included-by [<N>]
          Expand into parent documents to depth N (bare = 1, 0 = unbounded, omitted = not followed).

      --expand-references [<N>]
          Expand along outbound reference links to depth N (bare = 1, 0 = unbounded, omitted = not followed).

      --expand-referenced-by [<N>]
          Expand along inbound reference links to depth N (bare = 1, 0 = unbounded, omitted = not followed).

      --lexical <LEXICAL>
          Seed search: BM25 full-text query on title and body.

      --fuzzy <FUZZY>
          Seed search: fuzzy query on title and key.

  -e, --exclude <EXCLUDE>
          Exclude document key(s) from results (can be specified multiple times)

  -b, --backlinks [<BACKLINKS>]
          Include incoming references (--backlinks false to disable)
          
          [default: true]
          [possible values: true, false]

  -f, --format <FORMAT>
          [default: markdown]
          [possible values: markdown, keys, json, yaml]

      --children
          Populate the `includes` array with child document edges

      --limit <LIMIT>
          Cap the number of seed documents kept before expansion — top-N by relevance when searching, the first N of the selection otherwise (0 = unlimited)

      --max-documents <MAX_DOCUMENTS>
          Cap the number of documents returned after expansion, trimming periphery first (0 = unlimited)

      --max-tokens <MAX_TOKENS>
          Cap total content tokens across all documents (0 = unlimited)

      --max-document-tokens <MAX_DOCUMENT_TOKENS>
          Cap content tokens per document (0 = unlimited)

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

OUTPUT FORMATS:

MARKDOWN (default, -f markdown):
  Each document is wrapped in a four-backtick fenced block with the info
  string "markdown #<key>". Inside the fence: YAML frontmatter, a blank
  line, then the rendered markdown body.

    ````markdown #doc-a
    ---
    title: Document A
    includedBy:
      - key: parent-doc
        title: Parent Doc
    ---

    # Document A

    Content here...
    ````

  Multiple documents are separated by one blank line between blocks.
  Empty edge lists (includedBy, includes, referencedBy) are omitted
  from frontmatter.

KEYS (-f keys):
  One document key per line, suitable for piping:

    doc-a
    child-doc
    parent-doc

JSON (-f json):
  Flat array of document objects:

    [{"key": "...", "title": "...", "content": "...",
      "includedBy": [...], "includes": [...],
      "referencedBy": [...]}]

YAML (-f yaml):
  Same shape as JSON, rendered as YAML.

FILTER FLAGS (narrow the result set):

  --filter "EXPR"             Inline filter expression (YAML).
  -k, --key KEY               $key match. Repeatable: 1 key uses $eq, 2+ uses $in.
  --includes KEY[:DEPTH]      $includes anchor.
  --included-by KEY[:DEPTH]   $includedBy anchor.
  --references KEY[:DIST]     $references anchor.
  --referenced-by KEY[:DIST]  $referencedBy anchor.
  --max-depth N               Default maxDepth for inclusion anchors. Default 1.
  --max-distance N            Default maxDistance for reference anchors. Default 1.

EXPANSION (pull related documents into the result; nothing is followed by default):

  --expand-includes [N]       Follow child (block-ref) documents down N levels.
  --expand-included-by [N]    Pull N levels of parent context.
  --expand-references [N]     Follow outbound reference links N levels.
  --expand-referenced-by [N]  Pull documents that reference a seed, N levels.
  Bare flag = 1 level; N = 0 = unbounded; omitted = not followed.

SEED SEARCH (find seeds by relevance instead of naming keys):

  --lexical QUERY             BM25 full-text query over title and body.
  --fuzzy QUERY               Fuzzy query over title and key. Fuses with --lexical (RRF).

SHAPE FLAGS:

  --children                  Populate the includes array with child document edges.
  -b, --backlinks             Include incoming references (referencedBy). On by default.
  -e, --exclude KEY           Exclude document key(s) from results. Repeatable.

LIMITS (bound output for context-limited callers; off by default):

  --limit N                   Cap the seed documents kept before expansion — top-N by
                              relevance when searching, first-N of the selection otherwise.
  --max-documents N           Cap the documents returned after expansion; the periphery is
                              trimmed first.
  --max-tokens N              Cap total tokens across all documents. Whole documents are
                              dropped from the periphery once the budget is reached.
  --max-document-tokens N     Cap body tokens per document. A longer body is head-truncated
                              with a "⋯ truncated (N tokens omitted)" marker.
  0 = unlimited for every knob. Tokens count each document's body plus its edge lists
  (JSON/YAML structural overhead is not counted); the count is an approximate proxy and the
  truncation marker itself is uncounted, so a clipped body lands slightly over the cap. The
  main document(s) come first and survive; budgets trim the deepest expansion / context, so a
  clipped result set is not relationally closed (a kept child may lose its parent-context
  doc). When output is truncated a warning is printed to stderr; stdout stays clean. Page
  with --exclude: fetch, note the returned keys, then re-run excluding them.

EXAMPLES:

  iwe retrieve -k doc-a                                # single document (doc-only)
  iwe retrieve -k doc-a --expand-includes 2            # two levels of children
  iwe retrieve -k doc-a --children -f json             # includes array populated
  iwe retrieve -k x -k y -k z                          # multiple specific keys
  iwe retrieve --included-by projects/alpha -f keys    # keys inside alpha
  iwe retrieve --lexical "topic" --limit 5 --expand-included-by   # top-5 seeds + parents
  iwe retrieve -k doc-a --expand-includes 3 --max-tokens 8000     # bound total output size
```

## `iwe find`

```text
Search and discover documents in your knowledge base.

Ranks results with two independent rankers, selected explicitly:

  --fuzzy QUERY    Subsequence match on title and key. Tolerant of partial
                   words and dropped characters (auth matches Authentication);
                   it matches a subsequence of characters, not substitutions.
  --lexical QUERY  BM25 full-text match on title and body. Stemmed exact
                   tokens, ranked by term frequency, rarity, and length.

Supplying both fuses the two rankings with Reciprocal Rank Fusion. A bare
positional QUERY still works but is deprecated (defaults to --fuzzy and prints
a warning); use --fuzzy or --lexical instead.

Text queries are bag-of-words: word order is ignored and quoted phrases are
not matched as phrases (find "a b" and find "b a" are identical). --lexical
also drops stop words, so a query of only common words (e.g. "the") matches
nothing.

Without a query, documents are sorted by popularity (incoming reference and
inclusion count); with --sort, frontmatter sort wins and the query acts as a
membership filter.

Filter shorthand flags map onto the query operators (--key, --included-by,
--references, --referenced-by, etc.). Use --filter for inline YAML predicates
such as --filter 'status: draft'.


Usage: iwe find [OPTIONS] [PATTERN]

Arguments:
  [PATTERN]
          DEPRECATED: bare query defaults to fuzzy; use --fuzzy or --lexical

Options:
      --fuzzy <FUZZY>
          Fuzzy match on document title and key

  -v, --verbose <VERBOSE>
          [default: 0]

      --lexical <LEXICAL>
          Lexical (BM25) full-text match on title and body

  -l, --limit <LIMIT>
          Maximum results (0 = unlimited)

      --max-tokens <MAX_TOKENS>
          Cap total content tokens across all results (0 = unlimited)

      --max-document-tokens <MAX_DOCUMENT_TOKENS>
          Cap projected `$content` tokens per result (0 = unlimited)

      --project <PROJECT>
          Projection: comma-list (name, name=path, name=$selector, $selector) or inline YAML mapping. Replaces the default.

      --add-fields <ADD_FIELDS>
          Additive projection: same grammar as --project, extends defaults rather than replacing.

      --blocks <PRED>
          Locate blocks: adds a `blocks` field listing each block matching the predicate. PRED is an inline block predicate, e.g. '{ $within: Goals, $text: Q3 }'.

      --matches <PATTERN>
          Grep over blocks: restricts results to documents whose content matches PATTERN and adds a `matches` field with the matching lines. PATTERN is a Rust regex.

      --sort <SORT>
          Sort by frontmatter field. Format: field:1 (asc) or field:-1 (desc).

  -f, --format <FORMAT>
          [default: markdown]
          [possible values: markdown, keys, json, yaml]

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

QUERY FLAGS (rank the results; compose via AND with the filter flags):

  --fuzzy QUERY               Subsequence match on title and key (typo/partial tolerant).
  --lexical QUERY             BM25 full-text match on title and body (stemmed exact tokens).
  QUERY (positional)          DEPRECATED alias for --fuzzy; prints a warning.
  Setting both --fuzzy and --lexical fuses the two with Reciprocal Rank Fusion.
  Queries are bag-of-words (word order ignored, no quoted-phrase matching).

FILTER FLAGS (compose via AND with the query):

  --filter "EXPR"             Inline filter expression (YAML).
                              Example: --filter 'status: draft'
  -k, --key KEY               $key match. Repeatable: 1 key uses $eq, 2+ uses $in.
  --includes KEY[:DEPTH]      $includes anchor. DEPTH defaults to --max-depth.
  --included-by KEY[:DEPTH]   $includedBy anchor. DEPTH defaults to --max-depth.
  --references KEY[:DIST]     $references anchor. DIST defaults to --max-distance.
  --referenced-by KEY[:DIST]  $referencedBy anchor. DIST defaults to --max-distance.
  --max-depth N               Default maxDepth for inclusion anchors without :DEPTH. Default 1.
  --max-distance N            Default maxDistance for reference anchors without :DIST. Default 1.

SHAPE FLAGS:

  --project SPEC              Projection (replaces defaults). Accepts: comma-list
                              (name, name=path, name=$selector, $selector) or YAML mapping.
  --add-fields SPEC           Additive projection (extends defaults). Same grammar as
                              --project. Mutually exclusive with --project.
  --sort field:1|-1           Sort by frontmatter field (1=asc, -1=desc).
  -l, --limit N               Cap results (0 = unlimited).

LIMITS (bound output for context-limited callers; off by default):

  --max-tokens N              Cap total projected `$content` tokens across all results.
                              Rows are dropped whole once the budget is reached.
  --max-document-tokens N          Cap projected `$content` tokens per result, head-truncating
                              with a "⋯ truncated (N tokens omitted)" marker.
  0 = unlimited. Token budgets only act when `$content` is projected; a metadata index
  carries no content tokens, so use --limit to bound it. A truncation warning is printed
  to stderr when output is clipped.

OUTPUT FORMATS:

  -f markdown (default)       Compact index, one line per document; body only when
                              $content is projected.
  -f keys                     One key per line.
  -f json                     Structured array of result objects.
  -f yaml                     Same shape as JSON, rendered as YAML.

EXAMPLES:

  iwe find --fuzzy rust                                # subsequence on title/key
  iwe find --lexical rust                              # BM25 on title/body
  iwe find --fuzzy rust --lexical rust                 # both, fused with RRF
  iwe find --filter 'status: draft'                    # all drafts
  iwe find --lexical rust --filter 'status: draft'     # BM25 AND status==draft
  iwe find --included-by projects/alpha:5              # descendants within 5 levels
  iwe find --included-by projects/alpha:0              # all descendants (unbounded)
  iwe find --references people/dmytro                  # docs that reference dmytro
  iwe find --filter 'priority: { $gt: 3 }' --sort modified_at:-1
  iwe find --project title,status -f json              # only two fields
  iwe find --add-fields 'body=$content' -f json        # default projection + body
```

## `iwe count`

```text
Count documents matching the given filter.

Accepts the same filter flags as `iwe find` (--filter, --key, --included-by, --references, etc.). Prints a single integer to stdout.


Usage: iwe count [OPTIONS]

Options:
  -l, --limit <LIMIT>
          Cap the number of matches counted (0 = unlimited)

  -v, --verbose <VERBOSE>
          [default: 0]

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:
    iwe count
    iwe count --filter 'status: draft'
    iwe count --included-by projects/alpha
    iwe count --included-by projects/alpha:5
```

## `iwe normalize`

```text
Perform comprehensive document normalization across all markdown files.

Operations performed:
- Update link titles to match target document headers
- Adjust header levels for consistent hierarchy
- Renumber ordered lists
- Fix markdown formatting (newlines, indentation)
- Standardize list formatting
- Normalize document structure

Usage: iwe normalize [OPTIONS]

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -h, --help
          Print help (see a summary with '-h')

OPERATIONS PERFORMED:

  - Link titles: Update link text to match target document headers
  - Header levels: Ensure consistent hierarchy within documents
  - Ordered lists: Renumber sequential list items
  - Formatting: Standardize newlines, indentation, spacing
  - List formatting: Consistent bullet and numbering styles
  - Document structure: Fix structural inconsistencies

EXAMPLES:

  # Normalize all documents
  iwe normalize

  # Preview changes with verbose logging
  RUST_LOG=debug iwe normalize --verbose 2

OUTPUT:

  Modifies files in place. No stdout output on success. Changes are
  written directly to the markdown files in your library.
```

## `iwe tree`

```text
Display document hierarchy as a tree structure.

By default, shows root documents (entry points with no incoming block references)
and their children organized in a tree format. Each level of nesting represents
a block reference relationship between documents.

Use -k/--key to start the tree from specific document(s), regardless of whether
they are roots. -k accepts repeats: 1 key uses $eq semantics, 2+ uses $in.

Combine with --filter / --included-by / --references / etc. to narrow the
roots further (intersection). Empty intersection yields an empty tree.

Output formats:
  markdown  Nested list with links (default): - [Title](key)
  keys      Document keys only
  json      JSON array with nested structure
  yaml      YAML rendering of the same structure

Use -d/--depth to limit how deep to traverse (default: 4).


Usage: iwe tree [OPTIONS]

Options:
  -f, --format <FORMAT>
          Output format: markdown (nested list with links), keys, json, yaml
          
          [default: markdown]
          [possible values: markdown, keys, json, yaml]

  -v, --verbose <VERBOSE>
          [default: 0]

  -d, --depth <DEPTH>
          Maximum depth to traverse
          
          [default: 4]

      --project <PROJECT>
          Projection: comma-list (name, name=path, name=$selector, $selector) or inline YAML mapping. Replaces user-frontmatter additions.

      --add-fields <ADD_FIELDS>
          Additive projection: extends each tree node's default fields. Same grammar as --project.

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  iwe tree                                # full tree with markdown links
  iwe tree -f keys                        # tree with document keys only
  iwe tree -f json                        # tree as JSON
  iwe tree -f yaml                        # tree as YAML
  iwe tree -k my-doc                      # subtree starting from 'my-doc'
  iwe tree -k doc-a -k doc-b              # subtrees from multiple roots
  iwe tree --depth 2                      # 2 levels deep
  iwe tree --included-by projects/alpha   # roots are descendants of alpha
  iwe tree --filter 'status: published'   # roots are docs with status==published
  iwe tree --project status -f json       # add status to each tree node

FILTER FLAGS (intersection with -k):

  --filter "EXPR"             Inline filter expression (YAML).
  --included-by KEY[:DEPTH]   $includedBy anchor.
  --includes KEY[:DEPTH]      $includes anchor.
  --references KEY[:DIST]     $references anchor.
  --referenced-by KEY[:DIST]  $referencedBy anchor.
  --max-depth N               Default maxDepth for inclusion anchors. Default 1.
  --max-distance N            Default maxDistance for reference anchors. Default 1.

SHAPE FLAGS:

  --project SPEC              Projection: comma-list (name, name=path, name=$selector,
                              $selector) or YAML mapping. Adds fields to each tree node.
  --add-fields SPEC           Additive projection (extends defaults). Same grammar as
                              --project. Mutually exclusive with --project.
  -d, --depth N               Maximum depth to traverse (default 4).

CIRCULAR REFERENCES:

  When documents form circular references (A->B->C->A), they have no natural
  root. Use -k to start from any document in the cycle:
    iwe tree -k doc-a

PIPING:

  iwe tree | grep -i api          Find documents mentioning 'api'
  iwe tree -f keys | grep cli     Find documents with 'cli' in the key
```

## `iwe squash`

```text
Create a consolidated document by inlining linked content.

Starts from the specified document, follows inclusion links up to the
specified depth, and combines all content into a single markdown output.
Inclusion links are replaced with the actual content of the referenced
documents, with headers adjusted to maintain proper hierarchy.

Use --depth to control how many levels of references to follow. Default
depth is 2, meaning direct references and their direct references.


Usage: iwe squash [OPTIONS] <KEY>

Arguments:
  <KEY>
          Document key to squash

Options:
  -d, --depth <DEPTH>
          [default: 2]

  -v, --verbose <VERBOSE>
          [default: 0]

  -h, --help
          Print help (see a summary with '-h')

OUTPUT FORMAT:

  Single markdown document with inlined content:

    # Main Document

    Introduction text...

    ## Referenced Section

    Content from referenced document, headers adjusted down one level.

    ### Nested Reference

    Content from second-level reference, headers adjusted accordingly.

  Header levels are automatically adjusted to maintain hierarchy when
  content is inlined. The output preserves document structure while
  combining multiple files.

EXAMPLES:

  # Squash with default depth (2 levels)
  iwe squash project-overview

  # Shallow squash (direct references only)
  iwe squash index --depth 1

  # Deep squash (follow all references)
  iwe squash main --depth 5

  # Export to single file
  iwe squash documentation > full-docs.md
```

## `iwe export`

```text
Export graph structure in various formats for visualization and analysis.

Available formats:
- dot: Graphviz DOT format for graph visualization

Filter scope with -k/--key (repeatable) or filter flags (--filter,
--included-by, --references, etc.). Use --include-headers for detailed
visualization with section subgraphs. Combining -k with filter flags
intersects the two — only explicit keys that match the filter are exported.


Usage: iwe export [OPTIONS]

Options:
  -f, --format <FORMAT>
          Output format
          
          [default: dot]
          [possible values: dot]

  -v, --verbose <VERBOSE>
          [default: 0]

  -d, --depth <DEPTH>
          [default: 0]

      --include-headers
          Include section headers and create subgraphs for detailed visualization. When enabled, shows document structure with sections grouped in colored subgraphs

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

DOT OUTPUT FORMAT:

  Graphviz DOT language. Nodes use numeric ids labeled with document
  titles, note-shaped and filled with a per-document color:

    digraph G {
      rankdir=LR
      1[label="Document Title",fillcolor="#ffeaea",shape=note,style=filled]
      2[label="Other Document",fillcolor="#f6e5ee",shape=note,style=filled]
      1 -> 2
    }

  With --include-headers, sections become plain-shaped nodes grouped in
  colored subgraphs per document:

    digraph G {
      rankdir=LR
      1[label="Document Title",shape=note,style=filled]
      2[label="Section",shape=plain]
      subgraph cluster_0 {
        style=filled
        fillcolor="#fff9de"
        2
      }
      2 -> 1 [arrowhead="empty",style="dashed"]
    }

FILTER FLAGS (narrow the exported set):

  --filter "EXPR"             Inline filter expression (YAML).
  -k, --key KEY               Match by key. Repeatable.
  --includes KEY[:DEPTH]      $includes anchor.
  --included-by KEY[:DEPTH]   $includedBy anchor.
  --references KEY[:DIST]     $references anchor.
  --referenced-by KEY[:DIST]  $referencedBy anchor.
  --max-depth N               Default maxDepth for inclusion anchors. Default 1.
  --max-distance N            Default maxDistance for reference anchors. Default 1.

EXAMPLES:

  # Export entire graph
  iwe export

  # Export specific document(s) and connections (-k is repeatable)
  iwe export --key project-main
  iwe export -k project-main -k project-beta

  # Include section headers for detailed view
  iwe export --include-headers

  # Control connection depth
  iwe export --key index --depth 2

  # Restrict to a subtree via filter
  iwe export --included-by projects/alpha
  iwe export --included-by projects/alpha --filter '$nor: [{ $includedBy: archive }]'

USING DOT OUTPUT:

  # Generate PNG visualization
  iwe export > graph.dot
  dot -Tpng graph.dot -o graph.png

  # Generate SVG for web use
  iwe export --include-headers > detailed.dot
  dot -Tsvg detailed.dot -o detailed.svg

  # Interactive exploration with xdot
  iwe export | xdot -
```

## `iwe schema`

```text
Scan documents and infer the frontmatter schema.

For each field found across the workspace, displays:
- Field name (dot-notation for nested fields)
- Type distribution with percentages
- Coverage: how many documents contain this field
- Distinct: count of distinct enumerable values
- Value distribution for low-cardinality fields (omitted when more
  than 100 distinct enumerable values)

Only enumerable values are listed: null, booleans, numbers, and
strings made up of [A-Za-z0-9_.-/]. Free-text strings (titles,
URLs with `:`, prose) are counted in coverage and types but do not
appear in the values listing or distinct count.

Use --filter to restrict analysis to a subset of documents (e.g.,
only posts, only externals). Use --field to drill into a specific
field. The --project / --add-fields flags from `find` and `tree` do
not apply here -- schema operates on raw frontmatter.


Usage: iwe schema [OPTIONS] [COMMAND]

Commands:
  validate  Validate documents against their configured schemas
  help      Print this message or the help of the given subcommand(s)

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -f, --format <FORMAT>
          Output format for schema
          
          [default: markdown]
          [possible values: markdown, json, yaml]

      --field <FIELD>
          Restrict output to a specific field (and its children)

      --filter <FILTER>
          Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.

  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.

      --includes <INCLUDES>
          $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --included-by <INCLUDED_BY>
          $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.

      --references <REFERENCES>
          $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --referenced-by <REFERENCED_BY>
          $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.

      --roots
          Only match root documents (those with no incoming inclusion edges).

      --max-depth <MAX_DEPTH>
          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.

      --max-distance <MAX_DISTANCE>
          Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.

  -h, --help
          Print help (see a summary with '-h')

OUTPUT FORMATS:

MARKDOWN (default, -f markdown):
  Aligned table with columns: Field, Types, Coverage, Distinct, Values.

JSON (-f json):
  Top-level array of field objects. Each object has: field, types,
  coverage { count, percentage }, distinct, values [{ value, count }].

YAML (-f yaml):
  Same shape as JSON, rendered as YAML.

EXAMPLES:

  # Full workspace schema
  iwe schema

  # Schema for posts only
  iwe schema --filter 'type: post'

  # Drill into a specific field
  iwe schema --field status

  # JSON output for scripting
  iwe schema -f json

  # Schema for documents with a specific pillar
  iwe schema --filter 'pillar: ai-memory'

  # Nested field inspection
  iwe schema --field engagement -f json
```

## `iwe schema validate`

```text
Validate documents against their configured schemas

Usage: iwe schema validate [OPTIONS]

Options:
  -f, --format <FORMAT>                Output format for validation reports [default: text] [possible values: text, json]
  -v, --verbose <VERBOSE>              [default: 0]
      --schema-file <SCHEMA_FILE>      Validate the selected documents against this schema file directly, bypassing the [schemas] config bindings
      --explain                        Print the binding trace (which section/block bound to which schema entry) instead of validating
      --filter <FILTER>                Filter expression. Inline YAML; wrapped in `{}` and parsed as a filter document. Example: --filter 'status: pending'.
  -k, --key <KEY>                      Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in.
      --includes <INCLUDES>            $includes anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.
      --included-by <INCLUDED_BY>      $includedBy anchor. KEY or KEY:DEPTH (DEPTH defaults to --max-depth; 0 = unbounded). Lowers to scalar shorthand when DEPTH=1, full form { match: { $key: KEY }, maxDepth: N } otherwise. Repeatable; anchors are ANDed.
      --references <REFERENCES>        $references anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.
      --referenced-by <REFERENCED_BY>  $referencedBy anchor. KEY or KEY:DIST (DIST defaults to --max-distance; 0 = unbounded). Lowers to scalar shorthand when DIST=1, full form { match: { $key: KEY }, maxDistance: N } otherwise. Repeatable; anchors are ANDed.
      --roots                          Only match root documents (those with no incoming inclusion edges).
      --max-depth <MAX_DEPTH>          Default maxDepth applied to inclusion anchor flags without a colon-suffix. Default 1; 0 = unbounded.
      --max-distance <MAX_DISTANCE>    Default maxDistance applied to reference anchor flags without a colon-suffix. Default 1; 0 = unbounded.
  -h, --help                           Print help
```

## `iwe stats`

```text
Generate comprehensive statistics about your knowledge graph.

By default, returns aggregate stats across the whole graph. Use -k/--key to
restrict output to a single document's record; all -f formats apply.

Provides analytics including:
- Overview: document count, node count, path count
- Document stats: sections, paragraphs, top documents
- Reference stats: block/inline refs, orphans, leaves, most referenced
- Size stats: lines, words, largest documents
- Structure stats: lists, code blocks, tables, quotes
- Network analysis: connectivity, most connected documents


Usage: iwe stats [OPTIONS] [COMMAND]

Commands:
  similarity  List pages with near-identical, mutually-similar counterparts across the store
  help        Print this message or the help of the given subcommand(s)

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -f, --format <FORMAT>
          Output format for statistics
          
          [default: markdown]
          [possible values: markdown, csv, json, yaml]

  -k, --key <KEY>
          Document key for per-document stats. Omit for aggregate graph statistics.

  -h, --help
          Print help (see a summary with '-h')

OUTPUT FORMATS:

MARKDOWN (default, -f markdown):
  Human-readable formatted statistics with sections for overview,
  documents, references, lines, words, structure, and network analysis.

CSV (-f csv):
  Per-document statistics with columns:
  key, title, sections, paragraphs, lines, words, included_by_count,
  referenced_by_count, incoming_edges_count, includes_count,
  references_count, total_edges_count, bullet_lists, ordered_lists,
  code_blocks, tables, quotes

JSON (-f json):
  Aggregate graph statistics serialized as JSON.

YAML (-f yaml):
  Same shape as JSON, rendered as YAML.

PER-DOCUMENT STATS (-k <KEY>):
  Returns the record for a single document. Default -f markdown prints
  a bullet-list record; csv, json, and yaml are also supported.

SIMILARITY (stats similarity):
  Lists mutually near-identical page pairs, tab-separated. Use
  -t/--threshold to move the bar (default 0.85): lower reports looser
  matches, higher only closer ones.

EXAMPLES:

  # Generate human-readable statistics
  iwe stats

  # Export per-document statistics as CSV
  iwe stats --format csv > stats.csv

  # Aggregate stats as JSON
  iwe stats -f json

  # Aggregate stats as YAML
  iwe stats -f yaml

  # Per-document stats (markdown record by default)
  iwe stats -k my-document

  # Per-document stats as JSON or YAML
  iwe stats -k my-document -f json
  iwe stats -k my-document -f yaml

  # Near-identical page pairs, then a looser scan
  iwe stats similarity
  iwe stats similarity -t 0.5

  # Find most connected documents
  iwe stats -f csv | tail -n +2 | sort -t, -k12 -nr | head -5
```

## `iwe stats similarity`

```text
List pages with near-identical, mutually-similar counterparts across the store

Usage: iwe stats similarity [OPTIONS]

Options:
  -t, --threshold <THRESHOLD>  Match level a pair must clear in both directions. Lower reports looser matches, higher only closer ones. [default: 0.85]
  -v, --verbose <VERBOSE>      [default: 0]
  -h, --help                   Print help
```

## `iwe rename`

```text
Rename a document and update all references to it.

Renames the source document file to the new key and updates all block
references and inline links that point to the old document key. This
ensures referential integrity across the knowledge base after renaming.

Usage: iwe rename [OPTIONS] <OLD_KEY> <NEW_KEY>

Arguments:
  <OLD_KEY>
          Current document key

  <NEW_KEY>
          New document key

Options:
      --dry-run
          Preview changes without writing to disk

  -v, --verbose <VERBOSE>
          [default: 0]

      --quiet
          Suppress progress output

  -f, --format <FORMAT>
          Output format. `keys` prints affected document keys (one per line) and suppresses progress.
          
          [default: markdown]
          [possible values: markdown, keys]

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Rename a document
  iwe rename old-doc-key new-doc-key

  # Preview changes without writing
  iwe rename old-key new-key --dry-run

  # Rename quietly (no progress output)
  iwe rename old-key new-key --quiet

  # Output affected document keys for scripting
  iwe rename old-key new-key -f keys

OUTPUT:

  -f markdown (default): progress messages showing rename action and updated docs.
  -f keys: one affected document key per line (target plus every doc whose
    references were rewritten), suitable for piping. Matches `iwe find -f keys`
    in shape.

  --dry-run: shows what would happen without making changes.
```

## `iwe delete`

```text
Delete documents and clean up all references to them.

Targets are selected by either a positional KEY (sugar for '$key: K') or
--filter EXPR (inline YAML filter document). Both may be
given; the union is deleted. Reference cleanup applies once over the
whole matched set. Use --dry-run to preview before applying.

Inclusion links to deleted documents are removed entirely; inline links
are converted to plain text.


Usage: iwe delete [OPTIONS] [KEY]

Arguments:
  [KEY]
          Document key to delete (sugar for --filter '$key: K')

Options:
      --filter <FILTER>
          Filter expression (inline YAML). Required if positional KEY omitted.

  -v, --verbose <VERBOSE>
          [default: 0]

      --expect <ARG>
          Document-level expect guard: assert the number of matched documents. ARG is N or '{ min: M, max: N }'.

      --strict
          Require the document-level --expect guard. Aborts before deleting if it is missing. Exempt under --dry-run.

      --dry-run
          Preview changes without writing to disk

      --quiet
          Suppress progress output

  -f, --format <FORMAT>
          Output format. `keys` prints affected document keys (one per line) and suppresses progress.
          
          [default: markdown]
          [possible values: markdown, keys]

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Single document
  iwe delete document-key

  # Filter-based delete
  iwe delete --filter 'status: archived'

  # Preview matches without deleting
  iwe delete --filter 'status: archived' --dry-run

  # Output affected keys for scripting
  iwe delete --filter 'status: archived' -f keys

REFERENCE HANDLING:

  - Inclusion links to deleted docs are removed entirely.
  - Inline links to deleted docs are converted to plain text.

OUTPUT:

  -f markdown (default): progress messages and updated count.
  -f keys: one affected document key per line (target plus every doc whose
    references were rewritten), suitable for piping.

  --dry-run: shows what would happen without making changes.
```

## `iwe extract`

```text
Extract a section to a new document with an inclusion link.

Creates a new document containing the extracted section content and
replaces the section in the source with an inclusion link. Use --list
to show all sections with their block numbers, then use --section or
--block to select which section to extract.

Usage: iwe extract [OPTIONS] <KEY>

Arguments:
  <KEY>
          Document key containing the section to extract

Options:
      --section <SECTION>
          Section title to extract (case-insensitive)

  -v, --verbose <VERBOSE>
          [default: 0]

      --block <BLOCK>
          Block number to extract (1-indexed)

      --list
          List all sections with block numbers

      --action <ACTION>
          Action name from config to use for extraction

      --dry-run
          Preview changes without writing to disk

      --quiet
          Suppress progress output

  -f, --format <FORMAT>
          Output format. `keys` prints affected document keys (one per line) and suppresses progress.
          
          [default: markdown]
          [possible values: markdown, keys]

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:
    # List all sections with block numbers
    iwe extract notes/project --list

    # Extract section by title
    iwe extract notes/project --section "Architecture"

    # Extract section by block number (unambiguous)
    iwe extract notes/project --block 2

    # Preview changes without writing
    iwe extract notes/project --section "Notes" --dry-run

    # Use a specific action from config
    iwe extract notes/project --section "Design" --action "my-extract"

    # Output affected document keys for scripting
    iwe extract notes/project --section "Notes" -f keys

OUTPUT:

    -f markdown (default): progress messages showing extract action.
    -f keys: one affected document key per line. Matches `iwe find -f keys`
        in shape.
```

## `iwe inline`

```text
Replace an inclusion link with the referenced document content.

Inlines the content of a referenced document at the reference location.
By default, deletes the target document and cleans up other references.
Use --list to show all inclusion links with their numbers, then use
--reference or --block to select which reference to inline.

Usage: iwe inline [OPTIONS] <KEY>

Arguments:
  <KEY>
          Document key containing the reference to inline

Options:
      --reference <REFERENCE>
          Reference key or title to inline

  -v, --verbose <VERBOSE>
          [default: 0]

      --block <BLOCK>
          Block number to inline (1-indexed)

      --list
          List all block references with numbers

      --action <ACTION>
          Action name from config to use for inlining

      --as-quote
          Inline as blockquote instead of section

      --keep-target
          Keep the target document after inlining

      --dry-run
          Preview changes without writing to disk

      --quiet
          Suppress progress output

  -f, --format <FORMAT>
          Output format. `keys` prints affected document keys (one per line) and suppresses progress.
          
          [default: markdown]
          [possible values: markdown, keys]

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:
    # List all inclusion links with numbers
    iwe inline notes/index --list

    # Inline by reference key
    iwe inline notes/index --reference "architecture"

    # Inline by block number (unambiguous)
    iwe inline notes/index --block 1

    # Preview changes without writing
    iwe inline notes/index --reference "design" --dry-run

    # Keep the target document after inlining
    iwe inline notes/index --block 2 --keep-target

    # Inline as blockquote instead of section
    iwe inline notes/index --reference "notes" --as-quote

    # Output affected document keys for scripting
    iwe inline notes/index --reference "design" -f keys

OUTPUT:

    -f markdown (default): progress messages showing inline action.
    -f keys: one affected document key per line. Matches `iwe find -f keys`
        in shape.
```

## `iwe update`

```text
Update document content or frontmatter.

Two modes, selected by which flags are present:

  Body-overwrite mode (-k KEY -c CONTENT)
    Rewrites the full markdown body of one document. Use '-' as --content
    to read from stdin.

  Mutation mode (--filter EXPR | -k KEY) + one or more operators
    Applies frontmatter operators (--set / --unset) and block operators
    (--replace, --replace-text, --insert-before, --insert-after, --append,
    --delete) to every document matched by the filter, as one atomic
    update. -k KEY is sugar for '$key: K'; combine with --filter to AND
    further constraints. Each block operator takes '{ <selector>, payload }'
    where the $-keys are the block predicate and the bare keys are the
    payload (content, from/to) plus an optional expect guard. The whole
    update validates before anything is written; on failure it prints the
    offending blocks and exits non-zero.

Body and mutation flags cannot be combined; pass exactly one mode.


Usage: iwe update [OPTIONS]

Options:
  -k, --key <KEY>
          Match by document key. Repeatable: 1 key uses $eq, 2+ uses $in. Body-overwrite mode requires exactly one.

  -v, --verbose <VERBOSE>
          [default: 0]

  -c, --content <CONTENT>
          New full markdown content (body-overwrite mode). Use '-' to read from stdin.

      --filter <FILTER>
          Filter expression for frontmatter mutation mode (inline YAML). Combined with -k via AND.

      --set <SET>
          Frontmatter $set assignment FIELD=VALUE. VALUE is parsed as a YAML scalar.

      --unset <UNSET>
          Frontmatter $unset field name.

      --replace <ARG>
          $replace: replace each selected block. ARG is '{ <selector>, content: <markdown> }'.

      --replace-text <ARG>
          $replaceText: rewrite own text of each selected block. ARG is '{ <selector>, from: X, to: Y }'; omit 'from' and 'to' replaces the entire own text.

      --insert-before <ARG>
          $insertBefore: insert sibling content before each selected block. ARG is '{ <selector>, content: <markdown> }'.

      --insert-after <ARG>
          $insertAfter: insert sibling content after each selected block. ARG is '{ <selector>, content: <markdown> }'.

      --append <ARG>
          $append: append child content to each selected container. ARG is '{ <selector>, content: <markdown> }'.

      --delete <ARG>
          $delete: remove each selected block. ARG is the '{ <selector> }' mapping ('{}' selects every block).

      --expect <ARG>
          Document-level expect guard: assert the number of matched documents. ARG is N or '{ min: M, max: N }'.

      --strict
          Require an expect guard on every mutating application (document-level --expect and each block operator's expect). Aborts before writing if any is missing. Exempt under --dry-run.

      --dry-run
          Preview without writing

      --quiet
          Suppress progress output

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # Content overwrite
  iwe update -k notes/draft -c "# Draft\n\nNew content."
  cat new-content.md | iwe update -k notes/draft -c -

  # Frontmatter mutation on a single document
  iwe update -k notes/draft --set status=published --set priority=10

  # Frontmatter mutation across many documents
  iwe update --filter 'status: draft' --set 'reviewed=true'
  iwe update --filter 'status: archived' --unset draft_notes

  # Precision text edit of one located block
  iwe update -k projects/roadmap \
    --replace-text '{ $within: Goals, $text: "Q3 Milestones", from: "Q3 Milestones", to: "Q3 2026 Milestones", expect: 1 }'

  # Rename a header (whole-text rewrite: omit 'from')
  iwe update -k projects/roadmap \
    --replace-text '{ $header: Goals, to: Aims, expect: 1 }'

  # Append a line under a section, and stamp frontmatter, atomically
  iwe update --filter 'type: project' \
    --set reviewed=true \
    --append '{ $header: Status, content: "Reviewed 2026-07-08." }'

  # Delete every paragraph linking to a retired doc, refusing a runaway match
  iwe update --filter '{}' \
    --delete '{ $paragraph: { $references: archive/old-plan }, expect: { max: 20 } }'

  # Preview without writing
  iwe update --filter 'status: draft' --set status=published --dry-run

VALUE PARSING:

  --set FIELD=VALUE parses VALUE as a YAML scalar:
    --set 'priority=5'       -> integer 5
    --set 'reviewed=true'    -> boolean true
    --set 'status=draft'     -> string "draft"
    --set 'tags=[a, b]'      -> list ["a", "b"]
    --set 'count="5"'        -> string "5"

NOTES:

  - The --content mode overwrites the whole body and does not touch
    frontmatter. Mutation mode combines frontmatter (--set/--unset) and
    block operators in one atomic update; frontmatter-only edits preserve
    the body verbatim, while any block edit re-normalizes the body.
  - Frontmatter is re-serialized as YAML 1.2 after mutation, so quote
    styles may change on untouched fields.
  - Mutation mode protects reserved frontmatter fields (names starting
    with _, $, ., #, or @) from being set or unset.
  - Block operator selections must be disjoint; each operator appears at
    most once per invocation.
```

## `iwe attach`

```text
Attach a source document as a block reference under one or more configured
attach actions defined in `.iwe/config.toml`.

For each --to <NAME>:
1. Look up <NAME> in [actions]; the action must be of type `attach`.
2. Render the action's key_template to compute the target key
   (e.g. `daily/{{today}}` becomes `daily/2026-04-25`).
3. If the target document doesn't exist yet, create it with the action's
   `title` as the H1 and the new block reference as the body.
4. If the target exists, append the new block reference.
5. If the source is already attached in the target, that target is silently
   skipped — no error, no warning, no duplicate write.

The reference text on the new block is the source document's title.


Usage: iwe attach [OPTIONS]

Options:
      --to <TO>
          Configured attach action(s) to attach to. Repeatable for multiple targets.

  -v, --verbose <VERBOSE>
          [default: 0]

  -k, --key <KEY>
          Source document key to attach

      --list
          List configured attach actions

      --dry-run
          Preview without writing

      --quiet
          Suppress progress output

  -h, --help
          Print help (see a summary with '-h')

CONFIGURATION:

  Define an attach action in `.iwe/config.toml`:

    [actions.today]
    type = "attach"
    title = "{{today}}"
    key_template = "daily/{{today}}"

EXAMPLES:

  # Discover available attach actions
  iwe attach --list

  # Attach a document under one configured target
  iwe attach --to today -k meetings/standup

  # Attach the same document under multiple targets at once
  iwe attach --to today --to weekly -k meetings/standup

  # Preview without writing
  iwe attach --to today --to weekly -k meetings/standup --dry-run
```

## `iwe completions`

```text
Generate a shell completion script for the iwe CLI.

The script is written to stdout. Pipe it into the location your shell loads
completions from, or source it directly.

Supported shells: bash, elvish, fish, nushell, powershell, zsh.


Usage: iwe completions [OPTIONS] <SHELL>

Arguments:
  <SHELL>
          Target shell
          
          [possible values: bash, elvish, fish, nushell, powershell, zsh]

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -h, --help
          Print help (see a summary with '-h')

EXAMPLES:

  # bash (user)
  iwe completions bash > ~/.local/share/bash-completion/completions/iwe

  # zsh (place on $fpath, e.g. ~/.zsh/completions)
  iwe completions zsh > ~/.zsh/completions/_iwe

  # fish
  iwe completions fish > ~/.config/fish/completions/iwe.fish

  # nushell (source the file from your config.nu)
  iwe completions nushell > ~/.config/nushell/completions/iwe.nu

  # one-off, current shell only
  source <(iwe completions bash)
```

## `iwe docs`

```text
Print built-in reference documentation.

The reference docs are embedded in the binary, so they always describe the
exact version you are running and work offline. Without a topic, lists the
available topics. With a topic, prints that reference as markdown to stdout
— read it before writing queries, editing .iwe/config.toml, or authoring
document schemas.

Usage: iwe docs [OPTIONS] [TOPIC]

Arguments:
  [TOPIC]
          Reference topic to print
          
          [possible values: query, config, schema]

Options:
  -v, --verbose <VERBOSE>
          [default: 0]

  -h, --help
          Print help (see a summary with '-h')

TOPICS:

  query    Query language: filters, graph operators, search, projection,
           and block operations for find/count/update/delete
  config   Configuration: every .iwe/config.toml section, field, and default
  schema   Document schemas: validating markdown structure and frontmatter
           with `iwe schema validate`

EXAMPLES:

  iwe docs           # list the topics
  iwe docs query     # the query language reference
  iwe docs config    # the configuration reference
  iwe docs schema    # the document schema reference
```
