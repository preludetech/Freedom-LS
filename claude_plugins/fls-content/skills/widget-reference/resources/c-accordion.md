# `c-accordion`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Native collapsible disclosure widget (`<details>`/`<summary>`). Body is markdown-rendered.

**Allowed attributes:** `title`, `open`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `title` | No | `""` | Visible summary bar text (required in practice) |
| `open` | No | absent | When present, accordion starts expanded |

Write `open` as a bare attribute with no value. The sanitiser normalises it to `open=""` and the template handles it correctly.

```markdown
<c-accordion title="Why does Python use indentation?">
Python uses indentation to define code blocks rather than braces or keywords.
This enforces consistent style across all Python code.
</c-accordion>

<c-accordion title="Optional reading: deeper dive" open>
This section starts expanded and can be collapsed by the reader.

More content here...
</c-accordion>
```
