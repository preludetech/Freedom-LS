# Student interface: on-brand course content widgets

We need to display a richer set of **content widgets** to students inside course
content — callouts, pull quotes, glossary terms, figures, data tables, and so on.

These widgets are authored as cotton components (`<c-widget …>`) inside markdown
content. The markdown pipeline is: markdown → sanitise with nh3 against
`MARKDOWN_ALLOWED_TAGS` → render cotton components → safe HTML. Any new component
must be registered in `MARKDOWN_ALLOWED_TAGS` (`config/settings_base.py`).
Interactivity must come from Alpine.js (CSP build) or HTMX, not arbitrary JS.

## Source material

- Existing widgets to add to or edit: `@freedom_ls/content_engine/templates/cotton`
- Visual designs (external React prototype): `@ $HOME/workspace/lms/design/Course Widgets - Gallery.html`

The designs come from an external tool that is **not** aware of our codebase. They
assume functionality and intentions that don't always fit our stack. **Don't scope
creep.** Where a design implies heavy infrastructure, we have made a scoping
decision (see "Scope decisions" below) rather than rebuild the prototype literally.

## Theming

The prototype was drawn to match the **first_class** theme. Implement each widget
in the **default** theme using standard role tokens (`--color-primary`,
`text-on-surface`, `bg-surface`, status tokens, `--fls-radius-*`, etc.), then
override in the **first_class** theme only where the brand look needs it. The
brand colours/shapes in the prototype already flow from the first_class theme
tokens — widgets should not hardcode hex values.

## Widgets to implement

Only the categories below. Everything else in the gallery is explicitly out of scope.

### 01 — Callouts & admonitions
Extend the **existing** `c-callout` component **additively** (keep the current
`level="info|warning|error|success"` working — do not break existing content) to
cover the six design tones:
- **Note**, **Hint**, **Best practice**, **Caution**, **Do not fly** (critical),
  **Key takeaway**.
- Severity must read from text/icon/label, **never colour alone**. An optional
  badge (e.g. "Safety", "Critical") is supported.
- (There is no separate "Objectives" callout in our gallery — the "all except
  Objectives" note refers to the Learning Objective widget, which is **out of
  scope**, see below.)

### 02 — Annotation & emphasis
- **Pull quote** — `figure` / `blockquote` with attribution.
- **Glossary term + definition list** — inline terms that reveal a definition,
  plus a `<dl>` reference list. The reveal must be **accessible**: a focusable
  Alpine disclosure that opens on hover **and** focus, dismissable with Escape,
  associated via `aria-describedby` (WCAG 1.4.13). The always-visible `<dl>` is
  the accessible baseline so the definition never lives only in a popup.
- **Equation / formula block** — rendered with **KaTeX/MathJax** (real typeset
  math). ⚠️ This introduces a new math-rendering dependency and requires
  sanitiser/`MARKDOWN_ALLOWED_TAGS` changes for the rendered output (MathML or the
  library's markup). Prefer server-side rendering where possible. Flag for the
  plan security review.
- **Learning objective — OUT OF SCOPE** (see scope decisions).

### 03 — Media
- **Video** — keep the existing simple **YouTube iframe** embed (it already
  provides native captions, speed, fullscreen). Add an optional caption/title and
  an optional **static** chapter list authored in markdown (timestamps as text /
  `?t=` deep links). **No** custom seeking player, caption toggle, or language
  switcher.
- **Annotated diagram** — reuse the **figure/photo** widget. The annotated SVG/
  image is authored as an asset and dropped into the figure widget; do **not**
  build an interactive SVG-annotation engine. Lettered call-outs (A/B/C) need a
  text legend so they are meaningful to screen readers.
- **Figure / photo** — captioned still, building on the existing `picture`
  widget (figure/figcaption, optional caption/number, existing lightbox modal).
- **Image gallery — no carousel.** For multiple images, use a vertical stack of
  captioned figures, or a simple **static thumbnail grid** that opens the existing
  picture lightbox modal.
- **Audio — OUT OF SCOPE** (see scope decisions).

### 06 — Structured content
- **Data table** — semantic `<table>` (caption, `scope`, status pills with text
  labels) inside a **focusable horizontally-scrollable wrapper** for small screens
  (reuse the existing `scrollTableLabels` Alpine component). No automatic
  row-stacking — it breaks comparison tables and strips semantics.
- **Code / log block** — brand-styled monospace `<pre><code>` with filename/title
  chrome. **No** syntax highlighting and **no** copy button (both deferred — they
  add a dependency / sanitiser surface). Long lines use a focusable scroll
  container or wrapping (WCAG reflow).

## Scope decisions (heavy items — confirmed with the user)

- **Video:** simple iframe + optional static chapter list. No custom player.
- **Audio:** **skipped** entirely this pass.
- **Image gallery / carousel:** **no carousel** — stacked figures / thumbnail grid
  into the existing picture modal (carousels are UX-discouraged and hard to make
  accessible).
- **Code blocks:** plain styled monospace — **no** syntax highlighting, **no** copy
  button.
- **Equations:** **KaTeX/MathJax** (real math engine — user opted in despite the
  added dependency).
- **Learning objective widget:** **skipped** (the "except Objectives" instruction
  is treated as authoritative).

## Explicitly out of scope (whole categories)

- **04 Assessment** — separate spec.
- **05 Interactive content** (accordion/FAQ, tabbed panel, hotspot diagram,
  procedure/checklist) — separate spec.
- **07 Reference & social** (resources/downloads, discussion thread) — skip.

## Accessibility & responsiveness (cross-cutting requirements)

- Native semantics first, ARIA only to fill real gaps.
- Colour is never the sole signal (callout tones, table status pills, diagram
  call-outs all need text/icon labels).
- Everything works by keyboard; focus states are visible.
- Respect `prefers-reduced-motion`.
- Wide content (tables, code, equations, dense diagrams) lives in a **focusable**
  scroll container — never clipped with `overflow:hidden`.
- Media: lean on platform players for captions/controls; never autoplay with sound.
- Widgets look good across screen sizes within the reading column.

## Demonstration (testing + documentation)

Every new and existing course widget must be demonstrated inside one of the demo
courses in `@demo_content`. Each widget is explained and demonstrated, and every
flavour/option is shown (e.g. all six callout tones). This doubles as living
documentation and as QA fixtures. (Open question for the spec: add to an existing
`functionality_demo_*` course vs. a dedicated "widget gallery" demo course.)

## Research

Background research for this idea lives alongside it:
- `research-accessibility-and-responsiveness.md`
- `research-reference-implementations.md`
- `research-ux-pitfalls-and-heaviness.md`
