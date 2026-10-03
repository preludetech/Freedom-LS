# `c-article-card`

Clickable card for a published ARTICLE. Shows the title, the description (if the article has one) and its byline (date and author, subject to the article's `show_date` / `show_author`). Renders nothing when the article is hidden, missing, or the blog app is not installed.

**Allowed attributes:** `path`, `variant`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `path` | Yes | | Path to the ARTICLE file, relative to the file holding the widget |
| `variant` | No | `"row"` | `"row"` (default) or `"compact"`; `compact` stacks its parts and suits narrow columns |

```markdown
<c-article-card path="undated-notes.md"></c-article-card>

<c-article-card path="unsigned-update.md" variant="compact"></c-article-card>
```

`content_validate` fails if `path` does not resolve to a content file, or resolves to a file that is not an ARTICLE. Place cards inside [`c-grid`](c-grid.md) to tile them.
