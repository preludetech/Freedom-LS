# `c-flashcard`

All `c-*` tags must stay within their registered attribute sets. Any attribute outside the set is **silently stripped** by the nh3 sanitiser.

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

The `front` and `back` slots are passed via `c-slot` — see [`c-slot.md`](c-slot.md).
