We need to implement a few more course content widgets and make a few other changes.

This stays high level on purpose — the detailed contract is the spec's job. Background research lives in `research_admonition_systems.md`, `research_flashcard_ux.md`, and `research_accordion_disclosure.md`.

# Background

Course content is authored in markdown and rendered through the pipeline in
`freedom_ls/markdown_rendering/markdown_utils.py`: markdown → nh3 sanitize (allowlist in
`MARKDOWN_ALLOWED_TAGS`) → django-cotton render. Widgets are cotton components in
`freedom_ls/content_engine/templates/cotton/` and are authored with the `c-` prefix
(e.g. `<c-admonition>`, not `<admonition>` — the bare tags in the examples below are shorthand).

Interactivity uses **Alpine.js**; styling uses **Tailwind** with theme **role tokens**
(`--color-info`, `--color-warning`, etc., plus `-light` tints and `on-*-light` foregrounds).
Colours therefore adapt to the active theme automatically — a widget that references a role
token looks right in every theme without per-theme code.

# Widgets

## Callout → move to base (application-level only)

The existing `c-callout` cotton component is for **application-level alerting**, not course content.

- Move it into the `base` app.
- **Remove `c-callout` from `MARKDOWN_ALLOWED_TAGS`** (`config/settings_base.py`). It is no
  longer a content widget, so the nh3 allowlist must not whitelist it — any `<c-callout>` left
  in markdown content will then be stripped during sanitization rather than rendered. Register
  the new `c-admonition` here instead.
- Remove it from all other content markdown rendering functionality and from demo content.
- Existing content that used `c-callout` is migrated to the new `c-admonition` (below) where
  appropriate.

## Admonition (new content widget)

A styled, labelled box for supplementary content — the content-layer replacement for `c-callout`.

### Attributes
- `type`: note, tip, important, remember, key_takeaways, checklist, … (default fallback when
  unknown)
- `title` (optional): overrides the type's default label.

### Configurable types
Each `type` maps to an **icon**, a **colour role token**, and a default **label**. The mapping
is a **deploy-time settings dict** (`ADMONITION_TYPES`), shaped like `MARKDOWN_ALLOWED_TAGS`:

```python
ADMONITION_TYPES = {
    "note":         {"label": "Note", "icon": "info", "color": "info"},
    "regulation":   {"label": "Regulation", "icon": "scale", "color": "warning"},
    "default":      {"label": "Note", "icon": "info", "color": "info"},
}
```

- Downstream projects/themes add domain types (aviation → `regulation`, parenting →
  `try_this_with_your_child`) by overriding the dict in their own settings. No DB, no migration,
  no admin UI.
- "Different per theme": because `color` is a role token, the same type looks right in every
  theme automatically. A theme that wants a *different set* of types simply ships a settings
  override. (A future per-site DB layer can be added later with resolution order
  DB → settings → default — out of scope here, but the template lookup should not preclude it.)
- **Graceful fallback**: an unknown `type` renders using the `default` entry — never an error,
  never an empty render.

### Content
- markdown (rendered via `{% markdown slot %}`, as `c-callout` does today).

### Accessibility (non-negotiable, see research)
- `role="note"` container, `aria-labelledby` on the visible label.
- Label is always real DOM text (defaults to the type's registry label); never colour-alone.
- Icon is decorative (`aria-hidden="true"`).
- Use the `-light` background + `on-*-light` foreground token pairs for legible contrast.

### Example
```html
<admonition type="regulation">Under SACAA's Part 101 framework, commercial work generally requires the pilot's **RPC** and the operation's **UASOC** as two separate things. Only *private* operation sits outside this.</admonition>
```

## Key takeaways → an admonition type (not a separate widget)

A summary box of "what was covered". **Decision:** ship as a built-in admonition `type`
(`key_takeaways`) in the default registry with its own icon/colour. No separate widget — it
inherits all admonition theming and keeps authoring consistent.

```html
<admonition type="key_takeaways">
- A drone operation is flight planning, the flight itself, and post-flight work — and the flying is the smallest slice.
- The real skill is judgement and good planning, not the time on the sticks.
- Safety is a culture built on consistent habits, not a checklist you tick once.
</admonition>
```

## Checklist → a static admonition type (not a separate widget)

**Decision:** ship as a built-in admonition `type` (`checklist`) with a checkbox icon. The body
is a standard markdown task list (`- [ ]` / `- [x]`), rendered **read-only**. No persistence,
no per-learner state.

> Interactive, persisted checklists (learner ticks boxes, progress saved) are a much larger
> feature — new model, progress tracking, HTMX — and would need their own spec. Explicitly out
> of scope here. Leave room for it but do not build it.

```html
<admonition type="checklist">
- [ ] Pre-flight inspection
- [ ] Check NOTAMs
- [x] Battery charged
</admonition>
```

## Flash card (new content widget)

A two-sided flip card. The user clicks/taps the card to flip it; front and back both allow
markdown.

- **Authoring:** named cotton slots `front` and `back`, each markdown-rendered.
- **Interaction:** single click/tap to toggle (never hover — breaks on touch). Front = prompt,
  back = answer/explanation.
- **Implementation:** Alpine.js state + Tailwind 3D transform. Use the **flex-based** layout
  (not absolute positioning) so the card grows to the taller face — the classic variable-height
  trap.
- **Accessibility (non-negotiable, see research):**
  - Trigger is a real `<button>` (keyboard Enter/Space for free); whole card surface is the
    target (≥44×44px).
  - `aria-pressed` reflects flip state; accessible name on the button.
  - The hidden face is removed from the a11y tree (`aria-hidden` toggled per face), and its
    interactive children get `tabindex="-1"` so focus can't land on an unseen link.
  - Honour `prefers-reduced-motion`: keep the flip, drop the animation.

```html
<c-flashcard>
  <c-slot name="front">What is the capital of France?</c-slot>
  <c-slot name="back">**Paris** — capital since the 10th century.</c-slot>
</c-flashcard>
```

## Accordion (new content widget)

A collapsible disclosure with a clickable title that expands to reveal the body. For "optional
depth" content the learner may open.

### Attributes
- `title`
- `open`: open by default?

### Content
- markdown body.

### Implementation (see research)
- Build on native `<details>`/`<summary>` for free keyboard support, no-JS fallback, and
  Ctrl+F / print / deep-link visibility. Layer Alpine.js `x-collapse` purely for smooth
  animation.
- Do **not** re-add `role="button"`/`aria-expanded` to `<summary>` — the browser sets these.
- Rotate a chevron on the open state; honour `prefers-reduced-motion`.
- Single independent disclosure (not a one-open-at-a-time group). No nested accordions.
- Use only for elective depth — never hide required/assessed content behind it.

```html
<c-accordion title="Why two-stroke engines need oil mixed in" open>
Body markdown here…
</c-accordion>
```

# Demo content

`demo_content/` is the reference course set that demonstrates all course functionality, and it
must showcase everything in this change so it is visible end-to-end (and usable for QA).

- **Showcase every new widget** in `demo_content/functionality_demo_content_widgets/` (the
  existing widget-demo course — e.g. extend or add a markdown file there): the admonition with
  several `type`s including `key_takeaways` and `checklist`, plus a domain/custom type to prove
  configurability; the flash card (front/back markdown); and the accordion (both default-closed
  and `open`). Use real, readable example content, not lorem ipsum.
- **Migrate `c-callout` out of content.** `c-callout` currently appears in several demo topic
  files (`functionality_demo_standard_markdown/3. topic.md`,
  `functionality_demo_end_with_topic/1. topic.md` & `2. topic.md`,
  `functionality_demo_end_with_quiz/2. topic.md` & `4. topic.md`). Replace each content-layer
  use with the appropriate `c-admonition` type so no demo content references `c-callout` once it
  has moved to `base`.
- If any custom admonition `type` is shown in demo content, the matching `ADMONITION_TYPES`
  entry must exist so it actually renders (don't demo a type that falls back to default).
- Keep the demo content's existing structure/voice; this is additive plus the callout migration.

# Out of scope (noted, not built)
- Per-site database-backed admonition type configuration (settings dict is enough for now;
  keep the template lookup open to a DB layer later).
- Interactive / persisted checklists with saved per-learner state.
- Collapsible admonitions (the accordion widget covers the hide/reveal need).
