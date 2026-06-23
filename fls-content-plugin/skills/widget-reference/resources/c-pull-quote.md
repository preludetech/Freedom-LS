# `c-pull-quote`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Pull quote with optional attribution. Body is markdown-rendered.

**Allowed attributes:** `attribution`, `cite`, `source`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `attribution` | No | `""` | Who said it (plain text) |
| `source` | No | `""` | Work title (rendered in `<cite>`) |
| `cite` | No | `""` | URL linking back to the source |

```markdown
<c-pull-quote attribution="Ada Lovelace" source="Notes on the Analytical Engine" cite="https://example.com">
The Analytical Engine weaves algebraic patterns, just as the Jacquard loom weaves flowers and leaves.
</c-pull-quote>
```
