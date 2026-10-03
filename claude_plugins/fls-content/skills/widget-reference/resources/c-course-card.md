# `c-course-card`

Clickable card for a COURSE; works anywhere markdown does, not only inside a course. Links to the course's detail page and shows its access badge. It has no status, progress or details link. Renders nothing when the course is hidden or missing.

**Allowed attributes:** `path`, `variant`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `path` | Yes | | Path to the `course.md`, relative to the file holding the widget |
| `variant` | No | `"row"` | `"row"` (default) or `"compact"` |

```markdown
<c-course-card path="../functionality_demo_price_fixed/course.md"></c-course-card>

<c-course-card path="../functionality_demo_price_fixed/course.md" variant="compact"></c-course-card>
```

`content_validate` fails if `path` does not resolve to a content file, or resolves to a file that is not a COURSE. Place cards inside [`c-grid`](c-grid.md) to tile them.
