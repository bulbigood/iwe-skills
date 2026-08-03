# Project Setup

Use this reference when you need to confirm whether the current workspace is an IWE project and how the project is configured.

## Contents

- [Project marker](#project-marker)
- [Example config](#example-config)
- [What to look at first](#what-to-look-at-first)
- [Working notes](#working-notes)

Official docs:

- `iwe init`: https://iwe.md/docs/cli/init/
- CLI reference: https://iwe.md/docs/cli/
- Documentation index: https://iwe.md/docs/

## Project marker

An IWE project is identified by its marker directory:

```text
.iwe/
```

Running `iwe init` creates that directory and a starter `.iwe/config.toml`.
The marker directory alone is sufficient for IWE to discover the project;
`config.toml` may be absent, in which case IWE uses its built-in defaults.

For IWE 0.18.0, prefer discovery before hand-authoring configuration:

```bash
iwe init --dry-run --json   # inspect detected settings and evidence
iwe init --auto             # write detected settings without prompting
# Read references/builtin-reference.md, section `config`, for the exact reference.
```

`iwe init --defaults` deliberately skips detection. Per-setting overrides such as `--library`, `--link-format`, `--refs-extension`, `--format`, and `--date-format` apply on top of detection. `init` writes only `.iwe/` unless agent artifacts are explicitly opted into.

## Example config

If `.iwe/config.toml` exists, read it before assuming file locations or
defaults. The following representative excerpt is based on generated config but
intentionally omits unrelated defaults and shows a few optional customizations:

```toml
# Generated config also contains a top-level `version` field.

[markdown]
# "" means links are written without an extension, e.g. [Doc](key)
# instead of [Doc](key.md).
refs_extension = ""

# Date format used when templates render dates into document content.
date_format = "%b %d, %Y"

[library]
# Where markdown notes live relative to the project root.
# "" means the root directory itself. "docs" would mean ./docs/.
path = ""

# Date format used by key-oriented template variables such as {{today}}.
date_format = "%Y-%m-%d"

# Optional. If set, plain `iwe new "Title"` uses this template.
# default_template = "journal"

[completion]
# Optional. Can be used to prefer markdown or wiki links in completions.
# link_format = "markdown"

[commands.default]
# Default command used by transform-style actions.
run = "claude -p"
timeout_seconds = 120

[actions.extract]
type = "extract"
title = "Extract"
link_type = "markdown"
key_template = "{{id}}"

[actions.extract_all]
type = "extract_all"
title = "Extract all subsections"
link_type = "markdown"
key_template = "{{id}}"

[actions.inline_section]
type = "inline"
title = "Inline section"
inline_type = "section"
keep_target = false

[actions.inline_quote]
type = "inline"
title = "Inline quote"
inline_type = "quote"
keep_target = false

[actions.today]
type = "attach"
title = "Today"
key_template = "daily/{{today}}"

[templates.default]
# File key/path for `iwe new`.
key_template = "{{slug}}"

# Initial markdown content for `iwe new`.
document_template = """
# {{title}}

{{content}}"""

[schemas.note]
# Resolves to .iwe/schemas/note.yaml and matches document keys.
match = "notes/**"
```

## What to look at first

- `library.path`: determines where notes actually live.
- `library.default_template`: changes what plain `iwe new` uses.
- `markdown.refs_extension`: affects whether links include `.md`.
- `actions.*`: `iwe extract --action ...` and `iwe inline --action ...` resolve here.
- `templates.*`: controls how `iwe new` and template-mode `iwe create` name files and render content.
- `schemas.*`: binds `.iwe/schemas/<name>.yaml` to document-key globs for `iwe schema validate`.
- The bundled `builtin-reference.md` configuration section is the exact 0.18.0 reference; use it before adding fields not already present in the workspace.

## Working notes

- Check `.iwe/config.toml` before searching for note files manually. If it is
  absent, use the built-in defaults documented in `builtin-reference.md`.
- If `iwe` behavior seems surprising, inspect config before assuming a bug.
- Re-running `iwe init` in an existing project does not overwrite the config.
- Read the bundled `builtin-reference.md` schema section before authoring a document schema, then run `iwe schema validate` after changes.
