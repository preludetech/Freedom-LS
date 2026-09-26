# Research: accessible markup for the panel-framework component kit

Scope: the twelve components listed in the idea's "Inventory" (`idea.md`), read against what FLS
already does for a11y (`panel_framework` tab set/announcer, `base` cotton components, `icons`,
`course-progress-bar.html`) and what spec 1 already decided (`research_tabs_and_history.md`,
`1. spec.md` in the done spec-1 folder). No new dependency, no ARIA widget invented where a native
element or spec-1's plain-link pattern already does the job — that is the house style this repo has
already chosen twice (tab set, icon renderer).

Stack constraint restated: everything below is server-rendered Django cotton + Tailwind utilities +
`c-icon`. No client-side ARIA widget library. Alpine is available for the small bits of state
(`x-data`, `aria-*` bindings) that HTMX/plain HTML can't express (e.g. a filter chip's pressed
state), per the framing in `idea.md`.

---

## 0. What FLS already has (don't re-decide these)

- **`c-icon`** (`freedom_ls/icons/templates/cotton/icon.html`, `freedom_ls/icons/render.py`): every
  icon gets an `aria-label` by default (falls back to the semantic/glyph name), i.e. icons are
  **labelled by default**, not hidden by default. `c-button` and `c-chip` show the repo's actual
  convention for *decorative* icons: wrap in `<span aria-hidden="true">` when adjacent text already
  carries the name (`base/templates/cotton/button.html` lines 32, 49-50). Follow that wrapping
  convention for every decorative icon in the new components; don't rely on `c-icon`'s default label
  when the icon is purely ornamental next to a text label.
- **Tabs are plain navigation links with `aria-current="page"`, not an ARIA `tablist`/`tab`/`tabpanel`
  triple.** This was a deliberate, researched decision in spec 1
  (`spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/research_tabs_and_history.md`
  §3, and `1. spec.md` step 19): each tab is a full-page URL, htmx swaps the region, and a document-level
  `htmx:afterSwap` handler moves `aria-current` because the nav sits outside the swapped region. Reasons
  given: real tabs (APG pattern) imply arrow-key-only navigation and same-page panel switching that
  doesn't match "each tab is its own URL", and Adrian Roselli's point that ARIA tab roles are for
  same-document panel switching, not site navigation between real pages. **Spec 4's tab bar styles this
  existing pattern — it must not add `role="tablist"`/`role="tab"`.**
- **Live region**: one persistent `#scope-announcer` (`aria-live="polite" aria-atomic="true"`,
  `sr-only`) lives outside `#main-content` (`partials/announcer_host.html`); updates go through an
  OOB `innerHTML` swap (`partials/announcer.html`) specifically because outerHTML-swapped live regions
  are silently dropped by some screen readers. Reuse this region; don't add a second one per component.
- **Definition-list-for-narrow / table-for-wide** is already the pattern for instance details
  (`panel_framework/panels/_instance_details_base.html`): `<dl>` stacked below `md`, a real `<table>`
  with `<th>` row headers above `md`, both driven from the same `rows` data so nothing is duplicated
  or re-authored per breakpoint.
- **`<h1 id="instance-title">`** is already rendered by `_instance_view_base.html` for instance
  pages; list views (`_list_view_base.html`) currently render **no** page-level heading at all in
  `main` (the title only reaches the document `<title>` via `partials/page_title.html` /
  `document_title.html`, OOB-swapped). This is the fact the page-header component's "who owns the h1"
  question has to resolve against — see §1.
- **Native `<progress>`**, not `role="progressbar"`, already ships in
  `learner_interface/templates/cotton/course-progress-bar.html`, with the comment recording *why*:
  "native `<progress>` already exposes an implicit progressbar role and its value/max to assistive
  tech, so no role/aria-value* is added". The new progress-bar component should be this same pattern
  moved/generalised into `panel_framework`, not a reinvention.
- **Role tokens** (`--color-<role>` with an `on-<role>` pair tuned for WCAG AA, per
  `frontend_styling.md`) are what give status/semantic colour its contrast guarantee for free —
  badges, chips and progress fills should use `bg-<role>`/`on-<role>` pairs rather than one-off
  colours so AA text contrast isn't re-litigated per component.
- **No `prefers-reduced-motion` or `forced-colors` handling exists anywhere in `freedom_ls/` today**
  (grep found none). Both are new ground for this spec — see §8 and §12.

---

## 1. Page header (idea.md: title, subtitle, status badge, action group — mockups 03, 05)

**Who owns the `h1`?** There must be exactly one `h1` per page (WCAG 2.4.6 Headings and Labels /
2.4.10 Section Headings; also the base rule screen-reader users rely on for "jump to main heading").
Today that's `_instance_view_base.html`'s inline `<h1 id="instance-title">`. Two honest options for
the spec to pick between (flag both, pick one, don't dodge it in this research):

- **A — the component renders the `h1`.** `c-panel-page-header` takes `title` and renders
  `<h1>{{ title }}</h1>` itself; `_instance_view_base.html` and `_list_view_base.html` are both
  updated to use the component instead of their own ad hoc heading (list view gains its
  first visible `h1` — arguably a bug fix, since a list page with no `h1` at all is itself an
  a11y gap). This keeps "one heading, one place" as an invariant enforced by the component.
- **B — the component takes a slot for the heading**, so the *page template* still emits
  `<h1>`/`<h2>` (matching whether it's a top-level list/instance view or a nested tab), and the
  component only lays out title-row + subtitle + badge + actions around whatever heading level is
  handed to it. This avoids forcing `h1` when the header is reused inside a panel that is not the
  page's top-level section (e.g. a section card's own header, which should be `h2`/`h3`, not `h1`).

Recommendation: **A for top-level page headers, but make the heading level a `c-vars` prop
(`heading_level="h1"`)** so the same component can't accidentally be reused at `h1` inside a
sub-panel — the default is `h1`, callers inside nested sections explicitly pass `heading_level="h2"`.
Don't hardcode the tag; interpolate it via `{% if heading_level == "h1" %}<h1 ...>{% else %}<h2 ...>{% endif %}`
(cotton/Django templates can't parametrise a tag name directly).

```html
<c-vars title subtitle="" heading_level="h1" />
<div class="flex flex-wrap items-start justify-between gap-4">
  <div>
    {% if heading_level == "h1" %}<h1 class="text-2xl font-semibold text-on-surface">{{ title }}</h1>
    {% else %}<h2 class="text-2xl font-semibold text-on-surface">{{ title }}</h2>{% endif %}
    {% if subtitle %}<p class="mt-1 text-sm text-muted">{{ subtitle }}</p>{% endif %}
  </div>
  <div class="flex items-center gap-3">
    {{ badge_slot }}
    <c-button-group variant="right">{{ actions_slot }}</c-button-group>
  </div>
</div>
```

The status badge sits in the header as a sibling to the title, **not** wrapped by the `h1` itself
(don't put non-heading inline content, e.g. a coloured pill, inside the `<h1>` — it changes what gets
read as "the heading text" for users who navigate by heading list, e.g. NVDA's Insert+F7). WCAG:
1.3.1 (Info and Relationships), 2.4.6.

## 2. Stat tile (value, label, optional delta — mockup 01/M01)

Use `<dl>`/`<dt>`/`<dd>` — this is a label→value pair, which is exactly what `dl` is for
(`_instance_details_base.html` already establishes this pattern in the same codebase; the student
widgets research at `spec_dd/3. done/2026-06-01_.../research-accessibility-and-responsiveness.md` §3
independently reaches the same conclusion for label/value content). Mockups draw the value large and
first, the label small underneath — but DOM/reading order must still be **label then value**
(WCAG 1.3.2 Meaningful Sequence): a screen reader user should hear "Active learners: 42", not "42:
Active learners". Get the visual "value on top" purely with CSS, not by reversing the DOM:

```html
<c-vars label value delta="" />
<dl class="flex flex-col-reverse">
  <dt class="text-sm text-muted">{{ label }}</dt>
  <dd class="text-3xl font-semibold text-on-surface tabular-nums">
    {{ value }}
    {% if delta %}<span class="ml-2 text-sm {{ delta_class }}">{{ delta_text }}</span>{% endif %}
  </dd>
</dl>
```

`flex-col-reverse` (or a CSS grid with `order-*`) flips paint order without touching DOM/reading
order — the same trick already used in this codebase's philosophy of "utilities on the markup"
rather than reordering source.

**Deltas must be text, not colour/arrow alone** (WCAG 1.4.1 Use of Color): "+12% vs last week" or
"−3 this week", with an `c-icon` arrow that is `aria-hidden` (the text already says up/down) — don't
ship a bare green/red triangle. If the delta is meant to update live (unlikely for a stat tile that's
part of a full-page render, more likely if a future spec live-refreshes it), it is *not* an
`aria-live` region by default — a stat tile that re-renders via HTMX swap already gets announced (if
at all) by the existing `#scope-announcer`, not by making every tile its own live region (that would
spam multiple live regions firing at once).

## 3. Status badge (fixed vocabulary — active/inactive/pending/complete/in progress/stalled)

Confirmed by the idea itself: **"Badges carry text, not just colour."** Concretely: the badge is a
`<span>`/`c-chip` with the status **word visible as text** (not screen-reader-only, not delivered
purely via `title`/`aria-label` on a colour swatch) — sighted users need the same text sighted
screen-reader users get, that's the whole point of 1.4.1. Icon-plus-text is a nice-to-have (a solid
dot glyph is still "colour" if it is itself the only carrier — pair a shape difference or omit it and
just use text). Follow `c-chip`'s existing shape (`base/templates/cotton/chip.html`) with the six
statuses mapped to role-token variants (`chip-success`, `chip-warning`, `chip-muted`, etc. — spec 10
decides the mapping; this component only needs the variant slots).

**Is it a live region? No.** A status badge rendered as part of a normal page/panel HTMX swap is
already inside content that the browser just placed; wrapping every badge in `aria-live` would cause
duplicate/unwanted announcements on ordinary navigation (the same reasoning spec 1 used for *not*
wrapping the whole swapped region in a live region — announcements go through the one dedicated
`#scope-announcer`, triggered deliberately by server-rendered `OOB` message swaps, not by tagging
every piece of content that might change). If a specific *action* changes a badge in place without a
full swap (e.g. an inline "mark active" toggle a later spec adds), that specific interaction should
announce through `#scope-announcer`, not by making the badge element itself `aria-live`.

```html
<c-vars status /> {# status in {active, inactive, pending, complete, in_progress, stalled} #}
<span class="chip chip-{{ status_variant }}">{{ status_label }}</span>
```

## 4. Avatar chip (initials + name, mockups 02, 05)

Initials are decorative shorthand for the name that's already printed next to them — hide them from
assistive tech and let the visible name text be the accessible name, exactly the pattern `c-button`
already uses for its icons:

```html
<c-vars name email="" role_label="" />
<div class="flex items-center gap-3">
  <span aria-hidden="true" class="avatar-initials size-8 rounded-full ...">{{ initials }}</span>
  <div>
    <p class="text-sm font-medium text-on-surface">{{ name }}</p>
    {% if email or role_label %}<p class="text-xs text-muted">{{ email }}{% if email and role_label %} · {% endif %}{{ role_label }}</p>{% endif %}
  </div>
</div>
```

If the whole chip is a link (e.g. to the learner's detail page), the link's accessible name comes
from the visible name text; don't add a redundant `aria-label` repeating it, and don't let the
initials span be inside the link with its own competing text — `aria-hidden` on the initials avoids
that double-read regardless.

## 5. Attention list (row per learner, a reason, a badge, one action — mockups 01, M01)

"The attention list is a list" (idea.md) — literally: `<ul>`/`<li>`, not a `<div>` soup with
flexbox rows pretending to be a list (a `<div>`-only "list" gives screen-reader users no item count,
no "list of 6" announcement, no item-to-item navigation). Each row's action needs an accessible name
that disambiguates *which* learner it acts on — "Message" repeated six times is useless out of
context; either visually-hidden text extends the accessible name, or the whole row action carries the
learner's name:

```html
<ul class="divide-y divide-border">
  {% for row in rows %}
  <li class="flex items-center justify-between gap-4 py-3">
    <div class="flex items-center gap-3">
      {# avatar chip #}
      <div>
        <p class="text-sm font-medium">{{ row.learner_name }}</p>
        <p class="text-xs text-muted">{{ row.reason }}</p>
      </div>
      <span class="chip chip-{{ row.status_variant }}">{{ row.status_label }}</span>
    </div>
    <c-button href="{{ row.action_url }}" size="small">
      {{ row.action_label }}<span class="sr-only"> for {{ row.learner_name }}</span>
    </c-button>
  </li>
  {% endfor %}
</ul>
```
(WCAG 2.4.4 Link Purpose (In Context) / 4.1.2 Name, Role, Value — the accessible name must be
unambiguous without relying on surrounding visual layout that AT users don't get for free.)

## 6. Progress bar (percentage, optional label — mockups 01, 03)

Follow `course-progress-bar.html` exactly: native `<progress value max>` with `aria-label`, no
`role="progressbar"`, no manual `aria-valuenow`/`aria-valuemin`/`aria-valuemax` — the native element
already exposes all of that (4.1.2 Name, Role, Value is satisfied by the element itself, for free,
in every browser/AT combination; a `role="progressbar"` `<div>` re-implementing this by hand is
strictly worse and is the WCAG "ARIA as last resort" anti-pattern the cross-cutting research already
flagged). The one thing to get right that's new for spec 4: **the percentage must be announced
once, not twice.** `course-progress-bar.html`'s own comment plus its markup already do this
correctly — the visible `{{ percentage }}%` span sits *outside* the `<progress>` element as sighted
affordance, while the `<progress>`'s own fallback text content (`{{ percentage }}%`) is what old/non-
supporting browsers see; a modern AT reads the element's native value once via its accessible value,
not the fallback content, so there's no double announcement in practice. Do **not** additionally
wrap the whole thing in `aria-live` — a progress bar that's part of a normal render is not dynamic
content requiring a live announcement; only the (out-of-scope) case of a bar advancing in place
without a page swap would need one, and that's specifically not what this static-render component
inventory covers.

```html
<c-vars percentage="0" label="Progress" suffix="" />
<div class="flex items-center gap-2">
  <progress class="w-full h-2 rounded-full overflow-hidden" aria-label="{{ label }}"
            value="{{ percentage|default:0 }}" max="100">{{ percentage|default:0 }}%</progress>
  <span class="text-sm tabular-nums text-muted whitespace-nowrap">{{ percentage|default:0 }}%{{ suffix }}</span>
</div>
```

**Forced-colors / dark mode for progress bars**: Windows High Contrast (the `forced-colors` media
query) replaces author backgrounds with system colours and can visually erase a `<progress>` bar's
fill against its track if both collapse to the same forced colour, or the element gets `appearance:
none` styling. Test (or, at minimum, note as a QA check for spec 12) that the bar keeps a visible
border/outline in `forced-colors: active` — add a `forced-colors:border forced-colors:border-[CanvasText]`
utility (or the FLS-equivalent) rather than relying purely on background-colour fill, since
`forced-colors` mode can suppress background-image/colour fills on some browsers. This is new ground
for FLS (no existing `forced-colors` handling in the repo) — call it out explicitly in the spec as an
open decision on how deep to go, with a floor of "the bar's boundary and track remain visible; the
text percentage is always present as the fallback source of truth" since text is never suppressed by
forced-colors.

## 7. Section card (heading, description, body, actions footer)

Use a real heading (`h2`/`h3`, matching where it nests — pass `heading_level` the same way as §1) plus
a `<section>` **only if the card is landmark-worthy**, i.e. distinct enough content that a user
navigating by landmark ("jump to region") benefits. The idea itself flags the risk: "section +
heading, landmark overuse". Concretely: a *page* built from six section cards stacked vertically
should not become six `<section>` landmarks with generic/duplicate accessible names — screen-reader
users navigating by region get a wall of unlabelled or identically-labelled "region"s, which is worse
than no landmarks at all. Recommendation: the section card element is a plain `<div class="surface">`
with a heading (this already matches `_panel_base.html`'s existing `<section class="surface">ative
<header><h2>` shape — reuse the h2/header shape, don't add a *second*, ARIA-labelled landmark on
top of what the panel base already provides for the exact same "titled block" concept). Only promote
to an explicit ARIA landmark (`role="region"` + `aria-labelledby` pointing at the heading `id`) for
cards that are genuinely page-level navigation targets (e.g. a "Learner details" card that a skip
link or in-page nav jumps to) — not for every stat/list card on a dashboard.

```html
<c-vars title description="" heading_level="h2" />
<section class="surface">
  <header class="mb-4">
    {% if heading_level == "h2" %}<h2 id="{{ card_id }}-heading">{{ title }}</h2>{% else %}<h3 id="{{ card_id }}-heading">{{ title }}</h3>{% endif %}
    {% if description %}<p class="text-sm text-muted mt-1">{{ description }}</p>{% endif %}
  </header>
  <div>{{ slot }}</div>
  {% if actions_slot %}<div class="mt-4 pt-4 border-t border-border">{{ actions_slot }}</div>{% endif %}
</section>
```

Open item flagged in idea.md ("Whether the section card replaces the framework's panel container
outright") is exactly this heading structure question — resolve it together in the spec: if section
card *replaces* `_panel_base.html`'s header block, there is only one heading pattern to get right, not
two slightly different ones drifting apart.

## 8. Definition list (label/value pairs, responsive — mockup 03 "Learner details")

Already solved in this codebase (`_instance_details_base.html`): `<dl>` stacked on narrow screens,
`<table>` with `<th>` row headers from `md` up, both from the same `rows` — do not re-derive this,
lift/generalise that exact pattern into the new `panel-definition-list` cotton component so the
instance-details panel can eventually consume it instead of duplicating the markup (noted as a
possible later-move candidate per the idea's "general enough for the learner interface" clause, or at
minimum a "merge with the existing partial" note for the plan). Key constraint carried over from the
cross-cutting research: **don't `display:flex`/`grid` a real `<table>`'s cells to "stack" it** —
that can strip native table semantics in some browsers (Safari) — the safe pattern is exactly what
`_instance_details_base.html` already does: two *separate* markup blocks (`<dl>` for narrow, `<table>`
for wide), toggled with `md:hidden` / `hidden md:table`, not one table forced to reflow via CSS.

## 9. Toolbar (search, filter chips, primary actions — mockup 02)

**`role="toolbar"` only if you're prepared to implement roving-tabindex arrow-key navigation for it**
(WAI-ARIA APG Toolbar pattern requires: only one control in the toolbar is a Tab stop at a time; Left/
Right — or Up/Down for a vertical toolbar — move focus between the toolbar's controls, roving
`tabindex="-1"`/`"0"`, with `Home`/`End` jumping to first/last). A search input, a row of filter
chips and one or two primary buttons, each independently Tab-reachable in natural order, is **not**
an ARIA toolbar — it's a plain `<div>` (or `<form>`) of ordinary controls, and that's the right choice
here: implementing real roving-tabindex for a mixed search+chips+buttons row is a nontrivial amount of
Alpine/JS for a benefit (slightly faster keyboard traversal) this component set doesn't need. Recommend
explicitly **not** using `role="toolbar"`.

- **Search labelling**: a visible label (even if visually small) or, minimum, `aria-label`/
  `<label class="sr-only">` — never a bare `placeholder` as the only name (placeholders vanish on
  input, aren't announced consistently, and fail 1.3.1/4.1.2 "label" requirements in strict audits).
  `data-table.html`'s existing search input (`placeholder="Search..."`, no `<label>`/`aria-label`) is
  itself a small existing gap — the new toolbar's search box should not repeat it: add
  `aria-label="Search {{ noun }}"` or a `sr-only` `<label for>`.
- **Filter chip toggle state**: a filter chip is a toggle button, not a checkbox and not a link —
  `<button type="button" aria-pressed="true|false">`. This is the correct ARIA state for "this
  control has two states and pressing it flips the state" (APG Button pattern, pressed variant);
  don't use `aria-selected` (that's for elements inside a `listbox`/`tablist`/`grid`, which a filter-
  chip row is not).

  ```html
  <button type="button"
          aria-pressed="{{ chip.active|yesno:'true,false' }}"
          hx-get="{{ chip.toggle_url }}" hx-target="#{{ list_region_id }}" hx-swap="innerHTML"
          class="chip chip-outline aria-pressed:chip-primary">
    {{ chip.label }}
  </button>
  ```

- **Applied-filter removal buttons** ("chips with an ×"): each is its own `<button>` (not a span with
  a click handler) whose accessible name states what it removes — `aria-label="Remove filter: {{
  filter.label }}"` — because a bare "×" glyph as the only content has no accessible name at all
  unless labelled. Removing it should move focus predictably (to the next remaining chip, or to the
  toolbar's search input if none remain) rather than dropping focus to `<body>` — this is the same
  general "don't lose focus on removal" principle the cross-cutting a11y research flagged for
  carousels/dismissible content, and it applies just as much to a filter chip list.

## 10. Empty state (icon, sentence, one action)

Nothing exotic: an icon that's decorative (`aria-hidden`, since the sentence right below it carries
the meaning — same convention as everywhere else in this component set), a plain sentence (`<p>`,
not a heading unless the empty state fully replaces a section that would otherwise have had one — if
it's swapped in under an existing section-card heading, don't add another `h2`/`h3` for it), and one
`c-button`/link action. No live region needed if it renders as part of a normal page/swap — same
reasoning as §3/§6: this is placed content, not a dynamic notification. (An HTMX swap that replaces a
populated list with an empty state *is* already a legitimate use for `#scope-announcer` if the change
happens without a full navigation, e.g. "No learners match these filters" after a filter toggle —
route that through the existing announcer partial, don't invent a second live region on the empty
state markup itself.)

## 11. Tab bar (styling only vs ARIA tabs — mockups 03, 05)

**Styling only.** Spec 1 already decided this (see §0 above) and researched it thoroughly
(`research_tabs_and_history.md` §3, citing the WAI-ARIA APG Tabs pattern and Adrian Roselli's "Don't
Use ARIA Menu Roles for Site Nav"). Spec 4's job is purely to give `tab_set.html`'s existing
`<nav aria-label><ul><li><a aria-current="page">` markup its final visual treatment (underline/
pill/whatever the mockup shows) via utilities — **do not** add `role="tablist"`/`role="tab"`/
`role="tabpanel"`/`aria-selected` to it. If a *different* screen in the mockups shows same-page,
JS-only panel switching (no URL change, no full-page swap) that's a genuinely different interaction
model from the spec-1 tab set — flag that to whoever owns that screen rather than silently converting
it to the same "plain nav link" pattern, since a same-page tab switch with no URL is exactly the case
where real ARIA tabs *are* the right pattern per the APG.

## 12. Skeletons (loading states — spec 3)

- **`aria-busy="true"` goes on the region being replaced**, not on the skeleton block itself — the
  container that HTMX is about to swap should carry `aria-busy="true"` while the request is in
  flight and it should be removed (or simply vanish, since the container's content is replaced
  entirely) once the real content lands. This tells AT "this region's content is not yet final,
  don't read it as settled" (a standard aria-busy usage; note there isn't universal AT support for
  aria-busy suppressing announcement, so it's a hint, not a guarantee — the load itself shouldn't be
  the sole way meaningful state changes get communicated; that's what `#scope-announcer` is for on
  completion, if the change is significant enough to announce, per FLS's existing announcer use).
- **Hide skeleton placeholder blocks from assistive tech**: `aria-hidden="true"` on the skeleton
  wrapper, so a screen reader doesn't read out a stack of meaningless "blank, blank, blank" divs
  while content loads — `base/templates/cotton/loading-indicator.html` gets this half right today
  (it has a real text message "Loading...", which is good — a plain skeleton block with *no* text
  fallback needs the `aria-hidden` treatment instead, since it has no accessible content worth
  reading). If the skeleton is content-shaped (grey boxes mimicking a stat tile / list), that shape
  is 100% decorative — `aria-hidden="true"` the whole wrapper; don't try to make individual skeleton
  boxes accessible.
- **Respect `prefers-reduced-motion`** for the shimmer/pulse animation — this is new ground for FLS
  (§0 confirms no existing `prefers-reduced-motion` usage in the repo). Minimum: wrap the
  animation utility so it's disabled under the media query, e.g. Tailwind's
  `motion-reduce:animate-none` variant on the pulsing skeleton class (Tailwind ships this variant
  out of the box, no plugin needed) so a vestibular-disorder user doesn't get a continuously
  pulsing block if the swap happens to be slow.

```html
<div id="{{ region_id }}" aria-busy="{% if loading %}true{% else %}false{% endif %}">
  {% if loading %}
    <div aria-hidden="true" class="space-y-3 animate-pulse motion-reduce:animate-none">
      <div class="h-4 w-1/3 rounded bg-surface-2"></div>
      <div class="h-4 w-2/3 rounded bg-surface-2"></div>
    </div>
  {% else %}
    {{ content }}
  {% endif %}
</div>
```

---

## Cross-cutting notes for the spec

- **Dark mode + badges/progress**: both already ride on role tokens (`bg-<role>`/`on-<role>`), which
  are defined once and themed once (per `frontend_styling.md`) — as long as every badge/progress fill
  uses the token pair rather than a raw Tailwind colour (`bg-green-500` etc.), dark mode contrast is
  inherited for free and doesn't need separate a11y sign-off. Flag in the plan: audit that no
  component in this spec introduces a raw colour utility for anything status-bearing.
- **Forced-colors (Windows High Contrast)**: new ground for FLS. The two places it bites hardest here
  are (a) the progress bar's fill-vs-track distinction collapsing (§6) and (b) filter-chip
  pressed/unpressed state (§9) potentially losing its visual distinction if it's colour-only — since
  the chip already carries visible text, the *state* (pressed or not) is the one thing at risk of
  losing its only-visual cue (e.g. a filled vs outline chip) under forced-colors; consider adding a
  text/icon delta for the pressed state (e.g. a checkmark) rather than relying purely on fill vs.
  outline, or at minimum verify a `forced-colors:` border variant keeps the two states visually
  distinct. This is a "note it, let spec 12's accessibility/QA pass verify in a real browser" item,
  not something to over-engineer at spec-writing time.
- **WCAG success criteria touched by this component set** (for the spec's traceability, not
  exhaustive): 1.3.1 Info and Relationships (stat tile `dl`, definition list, list semantics),
  1.3.2 Meaningful Sequence (stat tile reading order), 1.4.1 Use of Color (status badge, deltas,
  filter-chip state), 1.4.3 Contrast Minimum / 1.4.11 Non-text Contrast (badge/progress-bar
  boundaries against role tokens), 2.4.4 Link Purpose in Context (attention-list action names),
  2.4.6 Headings and Labels (page header, section card), 2.4.7 Focus Visible / 2.4.3 Focus Order
  (toolbar, filter-chip removal focus management), 4.1.2 Name, Role, Value (progress bar via native
  element, filter chip `aria-pressed`, avatar chip accessible name), 4.1.3 Status Messages (routing
  through the existing `#scope-announcer` rather than ad hoc live regions per component).

---

## Sources

- WAI-ARIA APG, Tabs pattern: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/ (already cited in spec 1's research; re-confirmed here as the reason spec 4 must not add tab roles)
- WAI-ARIA APG, Button pattern (toggle button / `aria-pressed`): https://www.w3.org/WAI/ARIA/apg/patterns/button/
- WAI-ARIA APG, Toolbar pattern: https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/
- Adrian Roselli, "Don't Use ARIA Menu Roles for Site Nav": http://adrianroselli.com/2017/10/dont-use-aria-menu-roles-for-site-nav.html
- Adrian Roselli, "A Responsive Accessible Table": https://adrianroselli.com/2017/11/a-responsive-accessible-table.html
- WCAG 2.2, Use of Color (1.4.1): https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- WCAG 2.2, Contrast Minimum (1.4.3): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- WCAG 2.2, Non-text Contrast (1.4.11): https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- WCAG 2.2, Headings and Labels (2.4.6): https://www.w3.org/WAI/WCAG22/Understanding/headings-and-labels.html
- WCAG 2.2, Status Messages (4.1.3): https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- MDN, ARIA live regions: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions
- MDN, `prefers-reduced-motion`: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion
- MDN, `forced-colors`: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors
- In-repo: `spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/research_tabs_and_history.md` (tab decision), `1. spec.md` (tab_set markup, announcer_host)
- In-repo: `spec_dd/3. done/2026-06-01_13:49_student-interface-content-widgets-on-brand/research-accessibility-and-responsiveness.md` (cross-cutting principles reused above: native semantics first, colour never sole signal, focusable scroll containers, reduced motion)

status: ok
