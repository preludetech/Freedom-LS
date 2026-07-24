# `c-file-download`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Download button (does not display the file inline).

**Allowed attributes:** `src`, `text`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB) |
| `text` | No | `"Download file"` | Button label |

```markdown
<c-file-download src="sample.pdf" text="Get the PDF"></c-file-download>
```
