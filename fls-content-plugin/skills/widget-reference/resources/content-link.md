# `c-content-link` and `c-slot`

---

## `c-content-link`

Internal link to another content item (Topic or Form). The link text is the slot content.

**Allowed attributes:** `path`

| Attribute | Required | Notes |
|---|---|---|
| `path` | Yes | Relative file path to the target content item |

```markdown
<c-content-link path="01. introduction.md">the introduction chapter</c-content-link>

<c-content-link path="03. quiz/form.md">take the quiz</c-content-link>
```

The `path` uses the content file's path as stored in the DB (relative to the course root). If the target content is not found in the DB, the link renders as a `<span class="text-error">` with the path in the title — this is a reminder to run `content_save` to register the target.

**Important:** `c-content-link` links to content items in the DB, not to arbitrary files. The target must be a valid FLS content file that has been saved by `content_save`.

---

## `c-slot`

`c-slot` is **not a standalone widget** — it is an internal cotton mechanism for passing named content into widgets that use named slots. Authors use it only inside `c-flashcard`.

**Allowed attributes:** `name`

| Attribute | Required | Notes |
|---|---|---|
| `name` | Yes | `"front"` or `"back"` for `c-flashcard` slots |

Do not use `<c-slot>` outside of `c-flashcard`. It has no visible output on its own and is stripped if used standalone.

For the full `c-flashcard` example showing both slots, see [`interactive-widgets.md`](interactive-widgets.md).
