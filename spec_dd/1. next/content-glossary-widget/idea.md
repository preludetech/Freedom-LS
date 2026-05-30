# Glossary term + definition list widget

> **Split out of** `student-interface-content-widgets-on-brand`. Glossary was part of
> the original "Annotation & emphasis" widget group, but the accessible reveal
> interaction is non-trivial and worth its own pass, so it lives in its own spec.

## The need

Two related pieces:

1. **Inline glossary term** — an inline term inside running content that **reveals a
   definition** on interaction.
2. **Definition list** — a `<dl>` reference list (the always-visible accessible
   baseline) so the definition never lives *only* in a popup.

## Hard requirements (the reveal is the hard part)

- The inline trigger must be a **real focusable element** (`<button>`), reachable by
  Tab, opening on **hover *and* focus**, **dismissable with Escape**, **hoverable**
  and **persistent** (WCAG 1.4.13 Content on Hover or Focus).
- Associate the revealed definition via **`aria-describedby`**; `role="tooltip"` for a
  pure description (no interactive content inside it).
- **Touch parity**: a tap must toggle the definition (treat as a disclosure) — never
  hover-only.
- Build the reveal as a small **Alpine.js (CSP build)** disclosure component, not
  CSS-only hover.
- The reference `<dl>` uses real `<dl>/<dt>/<dd>` (direct children) so screen readers
  convey the term→definition relationship.
- Style with **role tokens**, no hardcoded hex; verify default + first_class themes.

## Open design question (resolve during spec)

How do the two pieces relate?
- **Two self-contained widgets** (lean): `c-glossary-term` carries its own
  term+definition inline; a separate `c-glossary` renders an authored `<dl>`. Purely
  presentational, no shared registry/data model.
- **Shared glossary registry**: inline terms reference entries defined once by key;
  the `<dl>` is generated. DRY for authors but needs a data model + lookup — heavier,
  edges toward scope creep.

## Reference material

- Background research (in the sibling widgets spec folder):
  `research-accessibility-and-responsiveness.md` (section 3, Glossary Term),
  `research-ux-pitfalls-and-heaviness.md` (hover-tooltip a11y traps),
  `research-reference-implementations.md` (section 6, definition lists / glossary).
- Pipeline: new tags must be registered in `MARKDOWN_ALLOWED_TAGS`
  (`config/settings_base.py`).
- Existing Alpine component patterns (CSP build) to model the disclosure on:
  `freedom_ls/base/static/base/js/alpine-components.js` (e.g. `pictureModal`,
  `dropdownMenu` — show/close/onEscape pattern).

## Demonstration

Demonstrate an inline term reveal and a `<dl>` reference list in a demo course.
