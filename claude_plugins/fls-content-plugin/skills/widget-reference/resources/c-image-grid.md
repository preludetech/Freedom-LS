# `c-image-grid`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Layout wrapper for multiple `c-picture` children. Tiles into columns.

**Allowed attributes:** `columns`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `columns` | No | `"3"` | `"2"`, `"3"`, or `"4"`; other values fall back to 3 |

**Critical authoring quirks:**
1. Always use the **closed form** `<c-picture ...></c-picture>` — never self-closing `/>`.
2. Leave a **blank line between each child** so the markdown parser treats them as separate block elements.

```markdown
<c-image-grid columns="2">

<c-picture src="images/a.svg" alt="Image A" title="First image"></c-picture>

<c-picture src="images/b.svg" alt="Image B" title="Second image"></c-picture>

</c-image-grid>
```
