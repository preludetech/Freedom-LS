# `c-flashcard`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

Two-sided flip card. Both sides are markdown-rendered. The content lives in named slots.

**Allowed attributes:** `size`

| Attribute | Values | Purpose |
|---|---|---|
| `size` | `standard` (default), `wide` | A wide card fills more of the content column on a large screen and left-aligns both faces, so an answer holding a table or a code block reads properly. An unrecognised value renders a standard card. |

Named slots:

| Slot | Purpose |
|---|---|
| `front` | Prompt / question face |
| `back` | Answer / reveal face |

**An answer wider than the card scrolls rather than stretching it.** A table or fenced code
block that will not fit becomes its own horizontal scroll container inside the face — on a phone
that is most tables, whatever the `size`. Nothing is lost, but a learner has to swipe for it, so
reach for `size="wide"` when the answer is genuinely tabular and keep recall prompts short.

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

The `front` and `back` slots are passed via `c-slot` — see [`c-slot.md`](c-slot.md).

Use `size="wide"` when the answer is a table or a code block:

```markdown
<c-flashcard size="wide">
<c-slot name="front">

**Which status code should a REST API return for a validation failure?**

</c-slot>
<c-slot name="back">

| Code | Meaning | Client should |
| --- | --- | --- |
| `400` | Malformed request | Fix the payload |
| `422` | Well-formed but invalid | Fix the values |

</c-slot>
</c-flashcard>
```
