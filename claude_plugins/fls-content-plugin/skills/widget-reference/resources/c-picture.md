# `c-picture`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Responsive image with keyboard-accessible lightbox modal.

**Allowed attributes:** `src`, `alt`, `title`, `description`, `number`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `src` | Yes | — | File path (resolved from DB via `get_file_by_path`) |
| `alt` | Yes | — | Alt text for screen readers; use `alt=""` for decorative images |
| `title` | No | `""` | Visible caption under thumbnail and lightbox heading |
| `description` | No | `""` | Longer description shown only in the lightbox |
| `number` | No | `""` | Figure number; prefixes `title` with "Figure N" |

```markdown
<c-picture src="images/landscape.svg" alt="Blue sky over mountains" title="A scenic landscape" number="1"></c-picture>
```

**Do not duplicate `alt` and `title`.** `alt` is for screen readers; `title` is visible text for all users.

Image paths are relative to the content file (resolved to the course root by `content_save`).
