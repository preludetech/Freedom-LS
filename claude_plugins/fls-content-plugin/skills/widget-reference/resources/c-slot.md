# `c-slot` (inside `c-flashcard` only)

`c-slot` is **not a standalone widget** — it is an internal cotton mechanism for passing
named content into a `c-flashcard`'s `front` and `back` slots (see [`c-flashcard.md`](c-flashcard.md)).

**Allowed attributes:** `name` — `"front"` or `"back"`.

Do not use `<c-slot>` outside of `c-flashcard`. It has no visible output on its own and is
stripped if used standalone.
