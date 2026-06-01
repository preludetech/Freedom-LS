# Configurable content admonitions

> **Split out of** `student-interface-content-widgets-on-brand`. The original
> widget idea folded "Callouts & admonitions" into the on-brand widgets pass, but
> the requirement grew: we don't want a fixed set of tones, we want a **flexible,
> configurable admonition system**. That is a bigger design question, so it lives
> in its own spec.

## The need

Course content needs **admonition blocks** — Note, Hint, Best practice, Caution,
"Do not fly" (critical), Key takeaway, and so on. Crucially, **different FLS
implementations will want different types**: one deployment might add "Try this at
home", another "How to practice", another "Lab safety". We therefore need a system
where a **builder can define admonition types** and associate each with a **colour
(role token)**, an **icon**, a **label**, and an optional **badge** — rather than a
hardcoded enum baked into a template.

The six design tones above ship as the **default seed set**; installs extend or
override from there.

## Relationship to the existing `c-callout`

The existing `c-callout` widget (`level="info|warning|error|success"`) stays as-is
and is repurposed mentally as the widget for **application-level notifications**, not
content. The new configurable system is a **separate content widget** (working name
`c-admonition`). Do not break `c-callout` or any existing demo content that uses it.

## Open design question (resolve during spec)

How are admonition types configured?
- **Django settings registry** — e.g. `CONTENT_ADMONITION_TYPES`, a dict mapping
  `type` key → `{label, icon, color role-token, badge?}`. Lightest; per-install;
  no DB/migration; fits FLS's "extend via settings" model.
- **Per-site DB model** — a site-aware `AdmonitionType` model configured via Django
  admin; defaults seeded by migration. Per-site customisation without a deploy, but
  a new model + admin + per-render query. Heavier.
- **Settings now, model later** — ship the settings registry, leave a documented
  extension point for a DB model.

Lean: settings registry first (least surprise, no scope creep), DB model only if a
real per-site need is confirmed.

## Hard requirements (carried from research)

- **Severity is never colour alone** (WCAG 1.4.1): every type reads from its **text
  label + icon**; colour is supplementary. Optional badge (e.g. "Safety",
  "Critical") supported.
- Tone label must be **real text in the DOM**, not a CSS `::before` pseudo-element.
- Wrap in a landmark-capable element with `role="note"` and an accessible name via
  `aria-labelledby` pointing at the visible title. **Do not** use `role="alert"` for
  static lesson content.
- Decorative tone icons get `aria-hidden="true"`.
- Tinted backgrounds must meet contrast (4.5:1 body text) in **both** the default and
  first_class themes — check the lightest tints.
- Style with **role tokens** (`--color-*`, `bg-surface`, `--fls-radius-*`), no
  hardcoded hex; colours flow from the active theme.

## Reference material

- Background research (in the sibling widgets spec folder):
  `research-reference-implementations.md` (callout taxonomy survey — MkDocs/GitHub/
  Docusaurus/Sphinx tone sets, naming lessons), `research-accessibility-and-responsiveness.md`
  (section 1, Callouts/Admonitions).
- Existing component: `freedom_ls/content_engine/templates/cotton/callout.html`.
- Pipeline: new tag must be registered in `MARKDOWN_ALLOWED_TAGS`
  (`config/settings_base.py`); see the markdown rendering notes in the sibling spec.

## Demonstration

Every admonition type (all defaults + a custom example) must be demonstrated in a
demo course (the widgets pass introduces `functionality_demo_content_widgets` — add a
callouts/admonitions topic there, or to whichever demo course is current).
