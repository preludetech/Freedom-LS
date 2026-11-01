---
name: planning-references-in-code
description: Keep spec, plan, slice, batch, QA-bug and spec_dd/ references out of code comments, docstrings and test names. Use when writing or reviewing a comment while implementing a spec, plan or QA fix, and when a comment cites a section number, "this spec", a QA bug ID or a planning-document path.
---

# Planning references in code

Every comment, docstring, template comment, CSS header and test docstring must make sense to a
reader who has never seen the spec, plan, research note, QA plan or QA report behind it. State the
fact itself, never a pointer to where the fact was written down.

These all point at planning documents:

| Kind | Examples |
|---|---|
| Section numbers | `§4b`, `spec §6.1`, `per plan §8`, `research §5`, `section 0.2 of the QA plan` |
| Spec, slice, batch and phase numbers | `Specs 6 to 9 add…`, `from slice 5 onward`, `Slice 7 still has to…`, `Phase 2 of themable-implementations`, `spec 12's visual check` |
| Relative references | `this spec`, `a later spec`, `the spec requires`, `the spec's table`, `the success criterion this slice exists for` |
| QA references | `QA §12.1`, `Regression for QA Bug 2`, `QA bug B1`, `bugs surfaced in qa_report.md` |
| Paths into the spec tree | `spec_dd/2. in progress/order-tracking/3. frontend_qa.md` |

They rot for three reasons:

- **Numbers repeat.** Every effort has its own spec 1, slice 3, §4b and QA Bug 2. "Spec 6" names
  a different document in every effort, so the reader can't tell which one it means.
- **Documents move.** Spec directories move from `next` to `in progress` to archived, and sections get
  renumbered, so a once-right path or number goes stale.
- **The code is the source of truth once it ships.** A reason that lives only in a planning doc is
  one the maintainer doesn't have. It belongs in the comment, or in git history.

**Rewrite each reference as the fact it stood for.** Open the document if needed, find what the
reference meant, and write that down. If the comment was only a citation, delete it.

```python
# BAD
"""Domain event names the order service's actions fire.

Specs 6 to 9 add ORDER_REFUNDED and ORDER_SHIPPED consumers; this
spec declares all four names now so later specs have nothing left to name.
"""

# GOOD
"""Domain event names the order service's actions fire.

All four names are declared here, including ones nothing listens for yet, so
every action fires events from one fixed list instead of inventing names.
"""
```

```python
# BAD
# §4a — stale-attempt safety net: finalise any stale incomplete attempt

# GOOD
# Finalise any stale incomplete attempt before reading progress state.
# No-op for auto-saving forms.
```

```django
{% comment %}Breadcrumbs (spec §6.1){% endcomment %}                          ← BAD
{% comment %}Copy does NOT promise an email (spec §7.2, §10){% endcomment %}  ← BAD
{% comment %}Copy does not promise an email: nothing sends one when the item publishes.{% endcomment %}  ← GOOD
```

Section numbers also turn a history comment into a puzzle:

```python
# §4c additions          ← BAD: means nothing once the diff is merged
# §4d — submit_and_close          ← BAD heading above tests whose names already say it
```

The same rule applies while you implement a plan: its slice and batch numbers and the spec's section
numbers are scaffolding and stay out of the code.

## Regression tests

A regression test's name and docstring describe the broken behaviour, not the bug's ID in a
report:

```python
# BAD
"""Regression for QA Bug 2: per spec, newest toast sits at the bottom."""

# GOOD
"""The newest toast sits closest to the viewport edge. It used to stack on top."""
```

## Quick checklist

Before you leave a comment in, ask:

1. Does it point at a spec, plan, research note, QA plan or QA report (a section, a spec/slice/phase
   number, "this spec", a QA bug ID, a `spec_dd/` path)? → replace it with the fact it stood for.
