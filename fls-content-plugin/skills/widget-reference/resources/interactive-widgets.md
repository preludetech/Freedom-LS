# Interactive Widgets

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

---

## `c-admonition`

Typed callout box. Body is markdown-rendered.

**Allowed attributes:** `type`, `title`

| Attribute | Required | Default | Notes |
|---|---|---|---|
| `type` | No | `"default"` | Admonition type — see below |
| `title` | No | `""` | Overrides the default label for the type |

```markdown
<c-admonition type="warning" title="Watch out">
This is important to check before proceeding.
</c-admonition>

<c-admonition type="note">
A plain note with the default label.
</c-admonition>

<c-admonition type="checklist">
- [ ] Step one
- [ ] Step two
- [ ] Step three
</c-admonition>
```

### Admonition types are deployment-configurable

The valid `type` values for **your project** are declared in `.fls-content.yaml` at the repo root, which always exists (set up with `/fls-content:init`). The FLS base set is:

`note`, `tip`, `important`, `warning`, `danger`, `key_takeaways`, `checklist`, `default`

This base set is **fully overridable** — a deployment may add, remove, or rename types. Never treat the base set as exhaustive. An unknown `type` falls back **silently** to the `default` style at render time with no error, which is why you must use the types declared in your project's `.fls-content.yaml`.

The `checklist` type renders `- [ ]` markdown task items as read-only disabled checkboxes.

---

## `c-flashcard`

Two-sided flip card. Both sides are markdown-rendered. No attributes — all content lives in named slots.

**Allowed attributes:** (none)

Named slots:

| Slot | Purpose |
|---|---|
| `front` | Prompt / question face |
| `back` | Answer / reveal face |

**Blank lines inside `<c-slot>` tags are required** — they let the markdown parser treat content as block elements (paragraphs, lists, bold text). Without them, content renders as inline text only.

```markdown
<c-flashcard>
<c-slot name="front">

**What is a variable?**

</c-slot>
<c-slot name="back">

A named container for a value that can change over time.

</c-slot>
</c-flashcard>
```

### `c-slot` (inside `c-flashcard` only)

`c-slot` is **not a standalone widget** — it is an internal cotton mechanism for passing
named content into a `c-flashcard`'s `front` and `back` slots (shown above).

**Allowed attributes:** `name` — `"front"` or `"back"`.

Do not use `<c-slot>` outside of `c-flashcard`. It has no visible output on its own and is
stripped if used standalone.

---

## `c-accordion`

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

---

## `c-card`

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
