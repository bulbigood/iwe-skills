# Advanced and control-plane IWE routes

Read this reference only when the request explicitly needs graph analytics, duplicate review, reusable artifacts, whole-library normalization, workspace initialization, shell completion, embedded reference text, or unresolved CLI syntax after a failed direct correction. Normal `find`, `retrieve`, `count`, `tree`, `schema`, create, update, and structural write work is complete in `SKILL.md`; do not read this file for those routes.

## Analyze and render uncommon artifacts

- **C7 Health/connectivity:** `iwe stats --format json`; use `--key <key>` for one-document complexity/connectivity and CSV only for a requested table.
- **C8 Duplicate review:** `iwe stats similarity --threshold 0.85`; use `0.95` for near-exact duplicates and `0.70` only for deliberately broad overlap.
- **D4 Linear inclusion artifact:** `iwe squash <key> --depth <positive-depth>` emits one Markdown artifact.
- **D5 Graph visualization:** `iwe export --key <key> --depth <positive-depth> --format dot`; add `--include-headers` only for section-level visualization.
- **D6 Filtered graph:** `iwe export --filter '<mapping>' --depth <positive-depth> --format dot`; relationship flags may narrow one known anchor.

These commands are read-only unless their stdout is redirected into a file. Do not retrieve documents first.

## Whole-library work

- **H3 Normalize:** `iwe normalize` rewrites the entire library in place and has no dry-run. Require explicit scope, an established rollback point, and fresh focused confirmation. Verify afterward.

## Setup and control plane

- **I1 Initialization proposal:** `iwe init --dry-run --json`; add only already-supplied `--library`, `--link-format`, `--refs-extension`, `--format`, or `--date-format` choices.
- **I2 Initialize:** `iwe init --auto <accepted-overrides>` applies detected conventions. Use `--defaults` only when static defaults are explicitly preferred.
- **I3 Completions:** `iwe completions <bash|elvish|fish|nushell|powershell|zsh>` for an already-known shell.
- **I4 Embedded reference:** `docs <query|config|schema>` is the IWE subcommand route only when that reference itself is requested, never as routine task discovery.
- **I5 Exact command help after error:** after a command fails, first make one direct correction supported by stderr. If syntax remains unknown, call `iwe <command> --help` once and retry once. Never call global help proactively.

Interactive `--edit`, cosmetic `--quiet`, routine `--verbose`, and global `--version` are intentionally excluded from autonomous data routes.
