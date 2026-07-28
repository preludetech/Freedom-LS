# `c-card`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Static content card with optional header image, title, and markdown body. No lightbox — use `c-picture` for zoomable images.

**Allowed attributes:** `src`, `alt`, `title`, `size`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | No | `""` | Header image path (same resolution as `c-picture`) |
| `alt` | No | `""` | Alt text for header image |
| `title` | No | `""` | Visible heading above the body |
| `size` | No | `"medium"` | `"small"`, `"medium"`, or `"large"`; unknown falls back to `"medium"` |

Size widths: `small` → `max-w-xs`, `medium` → `max-w-md`, `large` → `max-w-2xl`.

```markdown
<c-card src="images/planning.svg" alt="Planning diagram" title="Planning your course" size="large">
Cards are good for highlighting a key concept or call-to-action with an image header.

You can use **markdown** inside the card body.
</c-card>

<c-card title="No image card">
A card without a header image.
</c-card>
```
