---
name: code-comments
description: "Best practices for code comments, docstrings, and inline explanations, plus how to clean up stale or noisy comments. Use whenever you write or review a comment in Python, Django templates, JS, or CSS. Consult this whenever you catch yourself writing a comment that restates the code, narrates implementation history, or points at an external document."
---

# Code Comments

A comment is a promise to the future reader that the code can't keep on its own. Most comments break
it: they restate what the code already says, narrate how the code got written, or cite a document the
reader doesn't have. Those comments rot, and rotten comments are worse than none, because the reader
trusts them.

The single rule: **a comment must explain *why*, not *what*.** The code already says what.

---

## Don't narrate implementation history

The reader doesn't care what order the code was written in, or that a block was added later.

```python
# added later for the new export flow          ← BAD: means nothing once the diff is merged
# the block below preserves the existing category display logic   ← BAD
```

Git records history. A comment that describes *the change* instead of *the code* is stale the moment
the next change lands.

---

## Don't restate the code

If the comment and the line say the same thing, the comment is noise and a second thing to keep in
sync.

```python
# BAD: the call says exactly this
# set Cache-Control: no-store on GET results responses
response["Cache-Control"] = "no-store"

# GOOD: explains the why that the line can't
# The results page must re-fetch on back-nav so the order count is never stale.
response["Cache-Control"] = "no-store"
```

In templates, don't list the Tailwind classes visible right below:

```django
{% comment %}Progress bar: track bg-border rounded-pill, fill bg-secondary{% endcomment %}  ← BAD
```

A short region label (`Progress bar`, `Hero`, `Sign-up panel`) is fine when it helps someone scan a
long template. Keep the label, drop the class inventory and any citation.

```django
{% comment %}Copy does not promise an email: nothing sends one when the item publishes.{% endcomment %}
```

---

## Tests document themselves

Test and function names are the documentation. Don't head a group of tests with a label the test
names below already say:

```python
# --- submit_and_close ---          ← BAD when every test below is named test_submit_and_close_*
```

A plain-English divider label is acceptable when a file has several distinct groups, but if the test
names directly below already say it, drop the divider.

---

## What a good comment looks like

Good comments capture what the code *cannot*:

- **Non-obvious constraints:** "No-op for auto-saving forms."
- **Edge-case rationale:** why a value is excluded, guarded, or defaulted, e.g. excluding the current
  page's questions so an in-browser tally isn't double-counted.
- **Why-not-the-obvious-thing:** why we redirect instead of dereferencing `None` and 500ing.
- **Scope limits that aren't enforced in the signature:** "Only set for graded forms; ungraded forms
  have no numeric percentage."

```python
"""Domain event names the order service's actions fire.

Both ORDER_PLACED and ORDER_CANCELLED are declared here, including ones nothing
listens for yet, so every action fires events from one fixed list instead of
inventing names.
"""
```

If you can't articulate a *why*, the line probably doesn't need a comment.

---

## Respect protected comments

**Never delete `TODO` or `@claude` comments** unless the TODO is actually done. When one carries a
stale citation, don't delete it and don't strip the citation into a vacuum. **Replace the citation
with the concrete detail it was standing in for**, so the TODO says what it needs:

```django
{# BAD #}
{% comment %}TODO: render per-section totals. Do not delete, see the design doc.{% endcomment %}

{# GOOD #}
{% comment %}TODO: render per-section totals once the order is paid. Keep the block
below: it displays each section's subtotal and must not be removed.{% endcomment %}
```

---

## Quick checklist

Before you leave a comment in, ask:

1. Does it describe *the change* rather than *the code*? → delete it; git has the history.
2. Does it say the same thing as the line below? → delete it.
3. Could a reader who's never seen the originating discussion act on it? → if not, it's not pulling its weight.
4. Is it a `TODO`/`@claude`? → keep it; improve it; never silently delete it.
