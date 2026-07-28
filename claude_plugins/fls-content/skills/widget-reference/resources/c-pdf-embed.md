# `c-pdf-embed`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Inline PDF viewer via `<iframe>`.

**Allowed attributes:** `src`, `caption`, `height`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB) |
| `caption` | No | `""` | Caption text beneath the viewer |
| `height` | No | `"600px"` | CSS height of the iframe |

```markdown
<c-pdf-embed src="sample.pdf" caption="Sample Document" height="800px"></c-pdf-embed>
```
