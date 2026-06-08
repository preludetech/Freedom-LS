---
name: code-comments
description: "Best practices for code comments, docstrings, and inline explanations in the FreedomLS codebase, plus how to clean up stale or noisy comments. Use whenever you write or review a comment in Python, Django templates, JS, or CSS — and especially while implementing a spec/plan/research doc, so section citations (§4b, spec §6.1, per plan §8) never leak into the code. Consult this whenever you catch yourself writing a comment that restates the code, narrates implementation history, or points at an external document."
---

# Code Comments

A comment is a promise to the future reader that the code can't keep on its own. Most
comments break that promise: they restate what the code already says, narrate how the code
got written, or cite a document the reader doesn't have. Those comments rot — and rotten
comments are worse than none, because the reader trusts them.

The single rule: **a comment must explain *why*, not *what*.** The code already says what.

---

## Never cite spec / plan / research section numbers

This is the most common rot in this codebase. While implementing a spec, it's tempting to
tag the code with the section it came from:

```python
# §4b — start screen context: truthful, derivable facts   ← BAD
"question_count": count_form_questions(form),
```

```django
{% comment %}Breadcrumbs (spec §6.1){% endcomment %}      ← BAD
{% comment %}Progress bar … (research §5){% endcomment %}  ← BAD
```

These are dead weight:

- The section number points at a document that gets **renumbered the next time anything is
  specced**. `§4b` today is `§3a` next sprint and gone the sprint after.
- A future reader doesn't have that document version. The citation tells them *nothing*.
- The spec is not the source of truth for *maintenance* — the code is. Once shipped, the
  reason a line exists has to live in the code or in git history, not in a planning doc.

**If a comment is only a citation, delete it.** If it's carrying real reasoning that
happened to originate in the spec, **keep the reasoning and drop the citation:**

```python
# BAD
# §4a — stale-attempt safety net: finalise any stale incomplete attempt

# GOOD
# Finalise any stale incomplete attempt before reading progress state.
# No-op for save-on-exit forms.
```

---

## Don't narrate implementation history

The reader doesn't care what order the code was written in, or that a block was added later.

```python
# §4c additions          ← BAD: means nothing once the diff is merged
# the block below preserves the existing category display logic   ← BAD
```

Git already records history. A comment that describes *the change* instead of *the code*
is stale the moment the next change lands.

---

## Don't restate the code

If the comment and the line say the same thing, the comment is noise — and it's a second
thing to keep in sync.

```python
# BAD: the call says exactly this
# set Cache-Control: no-store on GET runner responses
response["Cache-Control"] = "no-store"

# GOOD: explains the why that the line can't
# Runner pages must re-fetch on back-nav so the answered count is never stale.
response["Cache-Control"] = "no-store"
```

In templates, don't list the Tailwind classes that are visible right below:

```django
{% comment %}Progress bar: track bg-border rounded-pill, fill bg-secondary{% endcomment %}  ← BAD
```

A short region label (`Progress bar`, `Hero`, `Sign-up panel`) is fine when it helps someone
scan a long template — keep the label, drop the class inventory and the citation.

---

## Tests document themselves

Test and function names are the documentation. Don't head a group of tests with a spec
section number:

```python
# §4d — form_submit_and_exit          ← BAD
```

A plain-English divider label is acceptable when a file has several distinct groups
(`# form_submit_and_exit`), but if the test names directly below already say it, drop the
divider entirely.

---

## What a good comment looks like

Good comments capture what the code *cannot*:

- **Non-obvious constraints:** "No-op for save-on-exit forms."
- **Edge-case rationale:** why a value is excluded, guarded, or defaulted — e.g. excluding
  the current page's questions so an in-browser tally isn't double-counted.
- **Why-not-the-obvious-thing:** why we redirect instead of dereferencing `None` and 500ing.
- **Scope limits that aren't enforced in the signature:** "Only set for QUIZ forms; non-quiz
  forms have no numeric percentage."

If you can't articulate a *why*, the line probably doesn't need a comment.

---

## Respect protected comments

Per `CLAUDE.md`: **never delete `TODO` or `@claude` comments** unless the TODO is actually
done. When you find one carrying a stale spec citation, don't delete it and don't just strip
the citation into a vacuum — **replace the citation with the concrete detail it was standing
in for**, so the TODO says what it actually needs:

```django
{# BAD #}
{% comment %}TODO: … Do not delete — see spec §8 and plan §8.{% endcomment %}

{# GOOD #}
{% comment %}TODO: render per-category scores once marking is complete. Keep the block
below — it displays each category's quiz score and must not be removed.{% endcomment %}
```

---

## Quick checklist

Before you leave a comment in, ask:

1. Does it cite a spec/plan/research section? → strip the citation; keep any real reasoning.
2. Does it describe *the change* rather than *the code*? → delete it; git has the history.
3. Does it say the same thing as the line below? → delete it.
4. Could a reader who's never seen the spec act on it? → if not, it's not pulling its weight.
5. Is it a `TODO`/`@claude`? → keep it; improve it; never silently delete it.
