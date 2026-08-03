# Complex IWE 0.18 queries

Read this file only when the required nested boolean, comparison, projection, sort, or graph predicate cannot be expressed with the examples in `SKILL.md`.

## Filter form

`--filter` accepts one inline YAML mapping. Plain fields mean equality.

```bash
--filter 'status: draft'
--filter 'priority: { $gt: 3 }'
--filter '{ $and: [status: published, priority: { $gte: 2 }] }'
```

Use `$and`, `$or`, and `$not` only when a single mapping cannot express the condition. Keep the complete filter in one shell argument.

## Value predicates

- Equality and inequality: `$eq`, `$ne`
- Ordering: `$gt`, `$gte`, `$lt`, `$lte`
- Membership: `$in`, `$nin`
- Existence: `$exists`
- Pattern matching: `$regex`

Preserve YAML scalar types. Quote values that must remain strings, especially numeric-looking strings and booleans.

## Graph predicates

Use command shorthand flags for one anchor. Use the equivalent filter predicate only when it must be nested inside boolean logic:

- `$includes`: document includes the anchor.
- `$includedBy`: document is included by the anchor.
- `$references`: document references the anchor.
- `$referencedBy`: document is referenced by the anchor.

Always set a finite `maxDepth` or `maxDistance`. A value of `0` is unbounded and is forbidden in normal execution.

## Projection and sorting

Use `--project` to replace default fields and `--add-fields` to retain defaults. Prefer compact metadata:

```bash
--project 'key=$key,title=$title,status'
--add-fields 'body=$content'
--sort 'modified_at:-1'
```

Project `$content` only when the body is required, and pair it with token limits. Sort does not replace a result limit.

## Block predicates

`--blocks` accepts one inline block predicate and may appear once per command. Use separate targeted commands only for unrelated selectors.

```bash
--blocks '{ $within: Goals, $text: "Q3" }'
--blocks '{ $header: Status }'
```

Do not invent infix expressions. For mutation, carry the exact selector into the operator and add an inline `expect` guard.
