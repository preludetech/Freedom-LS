---
name: code-comments
description: "Best practices for code comments, docstrings, and inline explanations in the FreedomLS codebase, plus how to clean up stale or noisy comments. Use whenever you write or review a comment in Python, Django templates, JS, or CSS — and especially while implementing a spec/plan/research doc, so references to planning documents (§4b, spec 6, this slice, a later spec, QA Bug 2, spec_dd/ paths) never leak into the code. Consult this whenever you catch yourself writing a comment that restates the code, narrates implementation history, or points at an external document."
---

# Code Comments

A comment is a promise to the future reader that the code can't keep on its own. Most
comments break that promise: they restate what the code already says, narrate how the code
got written, or cite a document the reader doesn't have. Those comments rot — and rotten
comments are worse than none, because the reader trusts them.

The single rule: **a comment must explain *why*, not *what*.** The code already says what.

---

## Write comments that stand without the planning documents

Every comment, docstring, template comment, CSS header and test docstring must make sense to a
reader who has never seen the spec, plan, research note, QA plan or QA report behind it. State the
fact itself, never a pointer to where the fact was written down.

This is the most common rot in this codebase. These all point at planning documents:

| Kind | Examples |
|---|---|
| Section numbers | `§4b`, `spec §6.1`, `per plan §8`, `research §5`, `section 0.2 of the QA plan` |
| Spec, slice, batch and phase numbers | `Specs 6 to 9 add…`, `from slice 5 onward`, `Slice 7 still has to…`, `Phase 2 of themable-implementations`, `spec 12's visual check` |
| Relative references | `this spec`, `a later spec`, `the spec requires`, `the spec's table`, `the success criterion this slice exists for` |
| QA references | `QA §12.1`, `Regression for QA Bug 2`, `QA bug B1`, `bugs surfaced in qa_report.md` |
| Paths into the spec tree | `spec_dd/2. in progress/schools/3. frontend_qa.md` |

They rot for three reasons:

- **Numbers repeat.** Every effort has its own spec 1, slice 3, §4b and QA Bug 2. "Spec 6" names
  a different document in every effort, so the reader can't tell which one it means.
- **Documents move.** Spec directories move from `next` to `in progress` to archived. Sections get
  renumbered. The path or number goes stale even when it was once right.
- **The code is the source of truth once it ships.** A reason that only lives in a planning doc is
  a reason the maintainer doesn't have. The reason belongs in the comment, or in git history.

**Rewrite each reference as the fact it stood for.** Open the document if you need to, find out
what the reference meant, and write that down. If the comment was only a citation, delete it.

```python
# BAD
"""Domain event names the educator interface's panel actions fire.

Specs 6 to 9 add REGISTRATION_CHANGED and EDUCATOR_CHANGED consumers; this
spec declares all four names now so later specs have nothing left to name.
"""

# GOOD
"""Domain event names the educator interface's panel actions fire.

All four names are declared here, including ones nothing listens for yet, so
every panel fires events from one fixed list instead of inventing names.
"""
```

```python
# BAD
# §4a — stale-attempt safety net: finalise any stale incomplete attempt

# GOOD
# Finalise any stale incomplete attempt before reading progress state.
# No-op for save-on-exit forms.
```

```django
{% comment %}Breadcrumbs (spec §6.1){% endcomment %}                          ← BAD
{% comment %}Copy does NOT promise a notification (spec §7.2, §10){% endcomment %}  ← BAD
{% comment %}Copy does not promise a notification: nothing sends one when the course launches.{% endcomment %}  ← GOOD
```

The same rule applies while you implement a plan. The plan's slice and batch numbers, and the
spec's section numbers, are scaffolding for the work. They stay out of the code you write.

### Regression tests

A regression test's name and docstring describe the broken behaviour, not the bug's ID in a
report:

```python
# BAD
"""Regression for QA Bug 2: per spec, newest toast sits at the bottom."""

# GOOD
"""The newest toast sits closest to the viewport edge. It used to stack on top."""
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

1. Does it point at a spec, plan, research note, QA plan or QA report (a section, a spec/slice/phase
   number, "this spec", a QA bug ID, a `spec_dd/` path)? → replace it with the fact it stood for.
2. Does it describe *the change* rather than *the code*? → delete it; git has the history.
3. Does it say the same thing as the line below? → delete it.
4. Could a reader who's never seen the spec act on it? → if not, it's not pulling its weight.
5. Is it a `TODO`/`@claude`? → keep it; improve it; never silently delete it.
