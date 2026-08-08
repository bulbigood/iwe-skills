# Repository retrieval routes

Use exactly one matching route below. Replace only angle-bracket placeholders with terms or keys stated in the request.

**One typed project by concept, with title and summary:**
```bash
iwe retrieve --lexical "<concept>" --filter '{ type: project }' --limit 1 --max-documents 1 --max-tokens 1200 --max-document-tokens 1200 --format json
```

**Compare named people on one topic from local notes:**
```bash
iwe retrieve --lexical "<names and topic>" --limit 1 --max-documents 1 --max-tokens 5000 --max-document-tokens 4500 --format json
```
Build `<names and topic>` by joining the names and topic stated in the request.

**Graph neighborhoods for two named note keys:**
```bash
iwe find --key "<first-key>" --key "<second-key>" --limit 2 --add-fields 'references=$references,referencedBy=$referencedBy,includes=$includes,includedBy=$includedBy' --format json
```

Answer only from that command's evidence, then stop. Do not read or activate the IWE skill. Do not call `iwe --help`, subcommand help, or documentation. Do not scan with `rg`, `grep`, filesystem `find`, broad listings, or file-by-file reads. Do not guess alternative filters or retry unless the exact command fails to execute.
