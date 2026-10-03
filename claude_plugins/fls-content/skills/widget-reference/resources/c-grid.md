# `c-grid`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Layout wrapper for any children: pictures, article cards, course cards. One column on phones; 2, 3 or 4 columns from the `sm`/`lg` breakpoints.

**Allowed attributes:** `columns`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `columns` | No | `"3"` | `"2"`, `"3"`, or `"4"`; any other value falls back to 3 |

Leave a **blank line between each child** so the markdown parser treats them as separate blocks. Use the closed form `<c-picture ...></c-picture>` for pictures.

```markdown
<c-grid columns="2">

<c-article-card path="undated-notes.md" variant="compact"></c-article-card>

<c-course-card path="../functionality_demo_price_fixed/course.md" variant="compact"></c-course-card>

<c-picture src="images/landscape.svg" alt="A blue sky over a dark horizon"></c-picture>

</c-grid>
```

`c-image-grid` now renders through `c-grid` with the same `columns` attribute. Prefer `c-grid` in new content.
