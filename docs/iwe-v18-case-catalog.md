# IWE 0.18 problem and solution catalog

This maintainer analysis is derived from the exact configured IWE `0.18.0` binary. The raw command and option inventory is in [`iwe-0.18.0-cli-help.md`](iwe-0.18.0-cli-help.md). This document maps that surface to agent problems; the installed skill remains a compact decision policy rather than a CLI manual.

## Mental parameter derivation

The agent must derive arguments from the request and facts already present in the conversation. It must not read documentation, inspect configuration, or issue a discovery call merely to decide syntax.

1. **Select by known fact.** Use `--key` for an exact key, `--filter` for typed metadata, relationship flags for a known graph anchor, `--fuzzy` for an incomplete title/key, and `--lexical` for concepts expected in title or body. Combine fuzzy and lexical only when both identity tolerance and body relevance matter.
2. **Select the smallest output shape.** Use keys for identity only, `--project` for named metadata, `--blocks`/`--matches` for local excerpts, and `retrieve` only when prose is needed. Use `--add-fields` only when defaults plus one extra field are required.
3. **Compute result count.** Exact item or authored synthesis: `--limit 1`. A requested list of N items: `--limit N`. “A few” means 5. Otherwise use the number of named entities/facets, capped at 20. Never use 0.
4. **Compute graph bounds.** Direct parent/child/reference means depth or distance 1. “Two levels” means 2. Use the explicit hop count in the request; when absent, use 1. Never use 0. Set `--max-documents` to the maximum evidence items the answer can cite: seed count plus explicitly requested related items, normally 3–12.
5. **Compute token bounds.** Fact/excerpt: 400–800 tokens per document. Short summary: 1,200. Detailed single-note read: 2,000. Authored synthesis: 4,500. Set total tokens to per-document tokens × maximum documents, capped near 8,000 for an ordinary answer.
6. **Build search text.** Remove request verbs and filler. Keep distinctive nouns, names, quoted terms, and the shared relation/topic. For comparisons, include every named entity plus the shared topic; this favors an authored synthesis over separate entity notes.
7. **Build filters.** Copy only user-stated fields and values. Preserve YAML types: booleans and numbers stay typed; quote numeric-looking or boolean-looking strings. Use equality by default; use `$in` for alternatives, ranges for numeric/time bounds, `$exists` for presence, and `$regex` only for an actual pattern requirement.
8. **Choose collision and mutation guards.** New explicit keys use `--if-exists fail`; auto-derived template keys use `suffix` unless the user requires uniqueness failure. A single-document mutation uses `--expect 1`; a known batch uses the expected count or a narrow `{ min, max }`. Every block operator gets its own `expect`.
9. **Stop.** Do not issue a second call when the first result already supports the answer. A second call is allowed only for one ambiguous winner, one failed well-formed query refinement, or preview followed by the identical mutation without `--dry-run`.

## Parameter utility map

### Shared selection and graph parameters

- `--key`: exact document identity; repeat for a known set. Positional keys are used only by commands whose help declares them.
- `--filter`: typed frontmatter and nested boolean/graph predicates.
- `--fuzzy`: incomplete title/key or dropped characters.
- `--lexical`: body concepts and named-topic synthesis.
- `--includes` / `--included-by`: documents that include an anchor / are included by an anchor. Append `:N` for explicit finite depth.
- `--references` / `--referenced-by`: outbound / inbound inline-reference relation. Append `:N` for finite distance.
- `--roots`: entry points with no incoming inclusion edge.
- `--max-depth` / `--max-distance`: defaults for relationship flags when the suffix is omitted; use a positive request-derived hop count.
- `--limit`: seed/result cap. `--max-documents`: post-expansion cap. `--max-tokens` and `--max-document-tokens`: total/per-document content caps. Zero means unlimited and is forbidden.
- `--format keys`: identities only. `json`: model synthesis or structured fields. `yaml`: human-readable structured output. `markdown`: rendered prose/tree. `csv`: statistics export.
- `--project`: replace defaults with exactly needed fields. `--add-fields`: retain defaults and add fields. `--sort field:1|-1`: order by a known frontmatter field; it never replaces a limit.

### Command-specific parameters

- `init`: `--dry-run --json` reviews detected configuration; `--auto` accepts detection; `--defaults` deliberately skips detection. `--library`, `--link-format`, `--refs-extension`, `--format`, and `--date-format` are used only when the operator already supplied those choices.
- `create`: `--content` writes a complete known document; `--template` uses a known convention. `--vars-json`/`--vars-yaml` preserve typed template variables; repeatable `--var` is string-only. Repeatable `--set` writes typed frontmatter. `--strict` validates before write. `--if-exists` makes collision intent explicit. `--edit` is for an interactive human, not an autonomous agent.
- `new`: title-first convenience creation. `--template`, `--content`, and `--key` apply already-known choices; `--if-exists` controls collision; `--edit` is human-interactive.
- `retrieve`: `--expand-includes`, `--expand-included-by`, `--expand-references`, and `--expand-referenced-by` pull finite related context. `--children` returns child edges without reading child bodies. `--backlinks false` suppresses unneeded incoming edges. Repeatable `--exclude` supports one bounded second page/refinement.
- `find`: `--blocks` locates structural blocks, `--matches` returns regex-matching lines, and content projection requires token caps.
- `count`: selectors define the counted set; `--limit` is useful only for “at least N?” checks, otherwise an exact whole-set count may be intentionally unbounded and must be explicitly justified.
- `tree`: `--depth` controls rendered hierarchy depth; selection flags choose roots; projection adds node metadata.
- `squash`: positional key is the root; `--depth` is the requested inclusion depth.
- `export`: `--depth` limits the visible graph neighborhood; `--include-headers` is only for section-level visualization; output is DOT in 0.18.
- `schema`: `--field` narrows inference to one field; selectors narrow the document population; structured format supports comparison.
- `schema validate`: `--schema-file` applies an explicitly named schema instead of configured bindings; `--explain` traces bindings rather than validating; selectors choose scope.
- `stats`: `--key` gives one document record; omit it for aggregate graph statistics. Format selects analysis or export shape.
- `stats similarity`: `--threshold` is 0.95 for near duplicates, 0.85 for ordinary duplicate review, and 0.70 only for deliberately broad thematic overlap.
- `rename`: positional old/new keys; `--dry-run` previews; `--format keys` minimizes affected-document output; `--quiet` is presentation only.
- `delete`: positional key or filter selects targets; `--expect`, `--strict`, and `--dry-run` guard scope; keys format reports affected identities.
- `extract`: positional source key plus `--section` when heading is known or `--block` when a prior result supplied its number. `--list` is only for a user-requested section inventory. `--action` names an already-known configured action.
- `inline`: positional container key plus known `--reference` or block. `--keep-target` is the safe default unless deletion is explicit; `--as-quote` follows requested presentation. `--list` and `--action` require already-known intent.
- `update`: `--content` is whole-body replacement only. `--set`/`--unset` mutate frontmatter. `--replace`, `--replace-text`, `--insert-before`, `--insert-after`, `--append`, and `--delete` perform disjoint block edits. Use `--expect --strict --dry-run` for guarded mutation; `--quiet` affects presentation only.
- `attach`: repeat `--to` for already-known configured destinations; `--key` is the source; `--list` is only when the user asks which actions exist; preview before applying.
- `normalize`: workspace-wide in-place rewrite with no preview flag. Use only after explicit scope and focused confirmation, with an external rollback point already established by the operator.
- `completions`: positional shell must come from the user/environment context: bash, elvish, fish, nushell, powershell, or zsh.
- `docs`: positional topic is `query`, `config`, or `schema`. This is control-plane output, never parameter discovery for an ordinary task.
- Global `--verbose` is diagnostics after a failure; `--help` is allowed only after unknown syntax; `--version` is maintainer/preflight evidence, not routine task work.

## Problem clusters and efficient recipes

Every recipe is one IWE invocation unless it explicitly shows `A → B`. Angle-bracket values are computed with the mental rules above.

### A. Identify, list, and inspect without loading full notes

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| A1 Exact key/title lookup | `iwe find --key <key> --limit 1 --project 'key=$key,title=$title' --format json` | If only a partial identity is known, replace key with `--fuzzy <distinctive fragment>` and keep limit 1–5. |
| A2 Find notes by body concept | `iwe find --lexical '<content nouns>' --limit <N> --project 'key=$key,title=$title' --format json` | Add fuzzy only when title/key tolerance also matters. |
| A3 Find by typed metadata | `iwe find --filter '<field mapping>' --limit <N> --project 'key=$key,title=$title,<fields>' --format json` | Add sort only when the request states newest/oldest/highest/lowest. |
| A4 Find roots or entry points | `iwe find --roots --limit <N> --project 'key=$key,title=$title' --format json` | Use `tree` instead when hierarchy, not a flat list, is requested. |
| A5 Find descendants/ancestors | `iwe find --included-by <anchor:N> ...` or `--includes <anchor:N>` | Direction comes from “inside/children of” versus “contains/parent of”; N is stated hops or 1. |
| A6 Find outbound/inbound references | `iwe find --references <anchor:N> ...` or `--referenced-by <anchor:N>` | Direction comes from “links to” versus “is linked from.” |
| A7 Locate a heading/section | `iwe find --key <key> --blocks '{ $header: <heading> }' --limit 1 --format json` | Add `$within`/`$text` when the request names nested text. |
| A8 Locate matching lines | `iwe find --key <key> --matches '<regex from literal pattern>' --limit 1 --format json` | Prefer blocks for structural headings/lists; regex is for actual text-pattern requirements. |
| A9 Return a compact evidence table | `find` with a projection containing only requested columns | Use `--add-fields` only when default key/title/edges plus one field are all needed. |
| A10 Rank filtered records | `iwe find --filter ... --sort '<field>:<1|-1>' --limit <N> --project ... --format json` | Ascending for earliest/lowest, descending for latest/highest. |

### B. Read, summarize, compare, and gather graph context

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| B1 Read one known note | `iwe retrieve --key <key> --limit 1 --max-documents 1 --max-tokens <T> --max-document-tokens <T> --format json` | T is 800 fact, 1,200 short summary, 2,000 detailed read. |
| B2 Summarize a topic | `iwe retrieve --lexical '<topic nouns>' --limit <N> --max-documents <N> --max-tokens <N×T> --max-document-tokens <T> --format json` | N is requested evidence count or 3; exclude body-unrelated terms. |
| B3 Compare named entities | `iwe retrieve --lexical '<all entities> <shared topic/relation>' --limit 1 --max-documents 1 --max-tokens 5000 --max-document-tokens 4500 --format json` | If the result does not cover every entity, refine once with missing entity/topic terms and limit at most the missing facets. |
| B4 Read a note with children | Known-key retrieve plus `--expand-includes <depth>` and finite document/token caps | Use `--children` instead when child identities/edges are enough and bodies are not needed. |
| B5 Read parent context | Known-key/topic retrieve plus `--expand-included-by <depth>` | Use one level unless the user explicitly asks for more hierarchy. |
| B6 Follow cited sources | Retrieve plus `--expand-references <distance>` | Use only when source bodies are needed; otherwise ordinary JSON edge lists suffice. |
| B7 Gather backlinks/reception | Retrieve plus `--expand-referenced-by <distance>` | Set `--backlinks false` when incoming reference metadata is irrelevant. |
| B8 Mixed local context | One retrieve may combine multiple finite expansion directions | `max-documents` equals the maximum useful cited set, not the theoretical graph fan-out. |
| B9 Resolve one ambiguous candidate | bounded projected `find` → one exact-key `retrieve` | The first call returns 2–5 candidates; the second reads only the chosen key. |
| B10 One bounded second page | retrieve with exclusions from the first result | Repeat `--exclude <returned-key>`; do not broaden limits or re-read old results. |

### C. Quantify, validate, and analyze

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| C1 Count a typed cohort | `iwe count --filter '<mapping>'` | Add relationship selectors for graph-bounded counts. Use `--limit N` only for “at least N?” checks. |
| C2 Count roots/related notes | `iwe count --roots` or count with one relationship anchor | Use positive depth/distance; do not infer content from counts. |
| C3 Learn fields in a cohort | `iwe schema --filter '<cohort>' --format json` | Add `--field <name>` when only one field’s type/coverage/values matter. |
| C4 Validate one or many notes | `iwe schema validate --key <key> --format json` or `--filter <scope>` | Use `--schema-file` only when the exact file was supplied. |
| C5 Explain schema binding | `iwe schema validate --key <key> --explain --format json` | This traces binding and does not substitute for validation. |
| C6 Whole-graph health summary | `iwe stats --format json` | Use CSV only when the user requests tabular export. |
| C7 One-document complexity/connectivity | `iwe stats --key <key> --format json` | Key must already be known. |
| C8 Near-duplicate review | `iwe stats similarity --threshold 0.85` | 0.95 for near-exact duplicates; 0.70 only for intentionally broad overlap. |

### D. Render hierarchy and reusable artifacts

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| D1 Show workspace hierarchy | `iwe tree --depth <N> --format markdown` | Use JSON when the agent must synthesize relationships. |
| D2 Show a subtree | `iwe tree --key <anchor> --depth <N> --format json` | Repeat key for several already-known roots. |
| D3 Filtered hierarchy with fields | `iwe tree --filter ... --depth <N> --project ... --format json` | Use add-fields to retain defaults. |
| D4 Consolidate an inclusion tree | `iwe squash <key> --depth <N>` | One read-only markdown artifact; N is requested inclusion depth, default 2 only when request implies a small local document. |
| D5 Graph visualization | `iwe export --key <key> --depth <N> --format dot` | Add headers only for section-level diagrams; omit key only for an explicitly whole-graph export. |
| D6 Filtered graph artifact | `iwe export --filter ... --depth <N> --format dot` | Relationship selectors narrow around known anchors. |

### E. Create documents

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| E1 Quick title/body note | `iwe new '<title>' --content '<body>' --if-exists suffix` | Add explicit key and `fail` when location/identity is specified. |
| E2 Known-template note | `iwe create --template <known-template> --vars-json '<typed variables>' --set <typed-field> --strict --if-exists <policy>` | `new --template` is shorter only when variables are limited to title/content and no strict typed schema work is needed. |
| E3 Exact complete document | `iwe create <key> --content '<complete markdown>' --strict --if-exists fail` | Use update, not override, for an existing document. |
| E4 Idempotent optional creation | create/new with `--if-exists skip` | Use only when “already exists” is an acceptable success state. |
| E5 Deliberate replacement collision | template create with `--if-exists override` | Requires explicit overwrite intent; otherwise fail or suffix. |

### F. Atomic metadata and local body edits

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| F1 Set/unset frontmatter | guarded `iwe update --key <key> --set/--unset ... --expect 1 --strict --dry-run` → identical apply | Batch uses a narrow filter and a user-derived expected range. |
| F2 Rename heading text | guarded `--replace-text '{ $header: <old>, to: <new>, expect: 1 }'` preview → apply | Omit `from` only for whole own-text replacement. |
| F3 Replace text within one block | guarded `--replace-text` with `$within`, `$text`, `from`, `to`, and expect | Selector terms come directly from the named section and exact old text. |
| F4 Replace one block | guarded `--replace` with exact selector/content preview → apply | Use only when the whole selected block should change. |
| F5 Insert sibling before/after | guarded `--insert-before` or `--insert-after` preview → apply | Direction is literal from the request. |
| F6 Append under a section | guarded `--append` with `$header` preview → apply | Combine independent same-document operators in one atomic command. |
| F7 Delete a local block | guarded block `--delete` preview → apply | This is not document deletion; require an exact selector and expected count. |
| F8 Replace an entire body | `iwe update --key <key> --content '<complete body>'` | Only when the entire body is authoritative; never for a local edit. |

### G. Structural graph refactors

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| G1 Rename a document key | `iwe rename <old> <new> --dry-run --format keys` → identical apply | Old/new keys must be explicit; command rewrites references. |
| G2 Extract a known section | `iwe extract <source> --section '<heading>' --dry-run --format keys` → apply | Use block only when its number is already known. |
| G3 Inventory extractable sections | `iwe extract <source> --list --format keys` | This is itself the requested result, not routine preflight. |
| G4 Inline while preserving target | `iwe inline <container> --reference <target> --keep-target --dry-run --format keys` → apply | Preserve is default safety policy. |
| G5 Inline and delete target | same without `--keep-target`, preview → focused confirmation and apply | Only when target deletion is explicit. Add `--as-quote` only on request. |
| G6 Attach to one/many known collections | `iwe attach --key <source> --to <action>... --dry-run` → apply | Repeat destinations already stated or known; do not list actions first. |
| G7 List configured attach actions | `iwe attach --list` | Use only when action discovery is the user’s requested outcome. |

### H. Destructive or workspace-wide operations

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| H1 Delete one exact note | `iwe delete <key> --expect 1 --strict --dry-run --format keys` → focused confirmation and apply | No call is made while scope/intent remains ambiguous. |
| H2 Delete a known cohort | `iwe delete --filter '<narrow criteria>' --expect '<range>' --strict --dry-run --format keys` → confirmation and apply | Criteria and range must come from user-stated policy, not speculative classification. |
| H3 Normalize the workspace | `iwe normalize` after focused confirmation and an already-established rollback point | No preview exists; refuse if recovery is unavailable or scope is ambiguous. |

### I. Workspace and control-plane tasks

| Case | Best solution | Alternative / derivation |
| --- | --- | --- |
| I1 Inspect initialization proposal | `iwe init --dry-run --json` | One read-only proposal; overrides only use values already supplied by the operator. |
| I2 Initialize from detected conventions | `iwe init --auto <known overrides>` | Use defaults only when the operator explicitly chooses static defaults over detection. |
| I3 Generate shell completions | `iwe completions <known shell>` | Shell comes from the explicit request or already-known environment. |
| I4 Print embedded reference | `iwe docs <query|config|schema>` | Only when the requested output is the reference itself; never to select parameters for another task. |
| I5 Diagnose a rejected command | `iwe <rejected-command> --help` → one corrected retry | Only after stderr says unknown command/option; no global help, docs, or speculative retries. |

## Coverage and exclusions

The catalog covers all 20 top-level commands, both nested commands (`schema validate`, `stats similarity`), all positional arguments, all command-specific long options, and the three global options exposed by IWE 0.18.0. Interactive `--edit`, diagnostic `--verbose`, global `--version`, and control-plane help/docs are intentionally excluded from ordinary autonomous task routes. They remain documented because “available” and “efficient for normal work” are not the same thing. Civilization survives another distinction.
