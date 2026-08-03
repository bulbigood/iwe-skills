## IWE Agentic AI Skills

Main repository is here https://github.com/iwe-org/iwe

## Available skills

### `iwe-v18`

Use the `iwe` skill when an agent is working inside an IWE knowledge graph and should prefer the `iwe` CLI for graph-aware reads and refactors instead of ad-hoc markdown edits.

Install with:

```bash
npx skills add iwe-org/skills --skill iwe-v18
```

Each published IWE release has its own skill directory. The root `config.toml`
maps skill ids to their directories and CLI versions; publishing and test tools
read that manifest instead of inferring versions from directory names.
