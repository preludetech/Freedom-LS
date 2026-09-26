# Research: stacked-card tables below `md`, and the "Filter and sort" sheet

Researched 2026-09-26 for `educator-interface-2-panel-framework-tables` (spec 2 of the educator
interface rebuild — see the "Educator interface rebuild" section of `spec_dd/1. next/roadmap.md`).
Scope: how the framework's data table renders as cards below the `md` breakpoint, and the sheet
that replaces inline sort/filter controls there. No new dependencies (Django 6, htmx 2, Alpine CSP
build, TailwindCSS, django-cotton).

**Coordinator course correction, factored in below:** row selection and bulk actions must work on
the mobile stacked-card layout too — a checkbox on the card and an "n selected" bar, not a
desktop-only feature. See §4.

## What the mockups actually show

### M03 — `Educator Mobile Learners.dc.html`, "Learners — list" (390×844)

Top app bar (52px): hamburger icon, "Learners" heading, a mono-font count ("31") pinned right.
Below it, a white toolbar block: a full-width 44px search input ("Search learners"), then a row of
controls — an active removable filter chip ("Stalled" with an `x`, primary-tinted), a neutral
"Filter" chip/button (funnel icon), and, pushed right by `margin-left:auto`, a neutral "Sort"
button (arrows icon). Neither "Filter" nor "Sort" carries a count or current-value label in this
screen; the current status filter is shown separately as the removable chip.

Below that, the card list. Each card is one flex row, 14px vertical padding, bottom border, white
background:
- a 40×40 circular avatar with initials (`grey-100` background);
- a flexible content column: first line is the learner's name (14.5px, semibold) plus an inline
  status badge (pill, colour keyed to status: warning-tinted "Stalled", error-tinted "Retake due",
  neutral "In progress", neutral-muted "Invited"); second line is a single meta string combining
  the course/cohort name with a status-specific fragment (`"RPAS Basic — Lagos · 14 days idle"`,
  `"Advanced BVLOS · attempt 2 of 3"`, `"Airspace & Regulation · never signed in"`); third line is
  a thin progress bar plus a mono percentage (or, for the invited learner, an empty bar track and
  "0%" in muted colour);
- a trailing chevron-right icon, right-aligned.

No checkbox, no row menu (⋯) — the desktop table's row-menu affordance is dropped and the whole
card is presumably a tap target to the learner's detail (M05). A primary-coloured floating action
button ("+", add learner) sits bottom-right above a 4-item bottom tab bar (Dashboard, Cohorts,
Learners active, More). The tab bar and FAB are the open bottom-tab-bar question from spec 1
(roadmap §"Unknowns resolved inside a spec"); this research doesn't resolve it, only notes that a
mobile "n selected" bulk-action bar (§4) needs to coexist with whatever spec 1 lands there.

### M04 — "Filter & sort sheet" (390×844)

A dimmed backdrop (`rgba(15,23,42,0.5)`) over the same list screen, with a bottom sheet (rounded
top corners, `max-height: 640px`, so roughly the top 200px of the screen — including the app bar —
stays visible behind the scrim). Structure, top to bottom:
- a centred 36×4px grab handle;
- a header row: "Filter & sort" heading, a "Reset" text-link pinned right (primary colour);
- a **Status** section: an overline label, then a wrapped row of pill toggle buttons — one per
  status ("Stalled" shown selected: primary border, tinted `grey-100` background, primary text;
  "In progress", "Retake due", "Complete", "Invited" shown unselected: neutral border, `fg-2`
  text). Visually this reads as a multi-select chip group, though the desktop toolbar's equivalent
  ("Status: Stalled" with one `x`) is currently single-value — the spec should decide whether
  mobile status filtering becomes multi-select or stays single-value styled as chips;
- a **Cohort** section: an overline label, then a single 48px control styled like a select ("All
  cohorts" plus a caret) — a single-value filter;
- a **Sort by** section: an overline label, then a vertical list of four options, each a 48px row
  with a bottom divider (except the last): "Last active" is shown selected (bold text, primary
  check icon right-aligned), the other three ("Name (A–Z)", "Progress — lowest first", "Enrolment
  date") are unselected (regular weight, muted text, no icon). This is a single-select list with a
  trailing checkmark, not a `<select>` and not visible radio inputs — closer to an iOS-style
  picker list;
- a footer, outside the scrollable body, with two buttons: "Cancel" (fixed ~110px, outlined) and,
  filling the rest, a primary button reading **"Show 3 learners"** — the count of rows the
  in-progress selection would return, computed and shown before the sheet is dismissed.

### Screen 02 — desktop `Educator Learners.dc.html`, "Learners — data table" (1440×900), for comparison

A real `<table>`-shaped grid (`display:grid` in the mockup's own markup, 7 columns: checkbox 44px,
Learner 1.5fr, Cohort 1.4fr, Progress 200px, Last active 140px, Status 130px, row-menu 44px). The
toolbar above it has a search input, a "Cohort" dropdown filter, a removable "Status: Stalled"
chip, an "Add filter" affordance, a "Sorted by Last active" indicator and a column-visibility
icon button. Below the table: "N selected · showing 8 of 31 learners" plus pagination.

Compared with the card, the desktop row keeps the learner's email as a second line under the name,
keeps Cohort as its own column (not folded into a meta string), keeps a row-menu instead of a
chevron-to-detail, and keeps an explicit checkbox column. The card is not "the same columns with
some hidden" — it recomposes several columns' values into fewer, denser lines aimed at a tap-to-
open interaction rather than a scan-and-act one. This matters for the column-declaration design in
§2.

## 1. Rendering technique: one restyled `<table>` vs two markups vs CSS grid

**Single `<table>` restyled with CSS** (`display: block` on `tr`/`td`, headers hidden and their
text re-surfaced per cell via a `data-label` attribute read by `content: attr(data-label)` in a
`::before`) is the classic "responsive table" tutorial pattern (examples collected in
[CSS-Tricks, "Accessible, Simple, Responsive Tables"](https://css-tricks.com/accessible-simple-responsive-tables/)
and the USWDS `usa-table--stacked-header` variant, below). It has two independent accessibility
problems, not one:

- **Changing `display` on table elements used to strip table semantics** in several browsers —
  the element stopped being exposed to the accessibility tree as a table at all, so a screen
  reader lost `th`/`td` association and cell/row navigation entirely.
  [Adrian Roselli's "Tables, CSS Display Properties, and ARIA"](https://adrianroselli.com/2018/02/tables-css-display-properties-and-aria.html)
  (2018, updated through 2023) is the primary source: Chrome/Chromium stopped stripping semantics
  for `flex`/`grid`/`inline-block`/`contents` as of version 80 (Feb 2020); Firefox followed for
  everything except `display: contents`; Safari/WebKit was "the worst performer" and only caught
  up after "5¾ years" of open bugs, into Safari 17. The fix, where still needed, is explicit ARIA
  (`role="table"`, `role="row"`, `role="cell"`/`role="columnheader"`) restating what the CSS took
  away — Roselli's own caution: "If you are not able to test with a screen reader, maybe don't do
  this." The practical takeaway for 2026: current evergreen browsers mostly preserve table
  semantics through a `display` change, but the fix still depends on testing the actual assistive
  tech matrix, and it buys nothing — the resulting markup is still a table pretending to be a list
  of cards, fighting its own semantics the whole way.
- **The `data-label`/`::before` label itself is not read by screen readers regardless of the
  display-property bug.** CSS generated content is decorative per WCAG 1.3.1; NVDA and VoiceOver
  do not announce `content: attr(data-label)` text (WebAIM, cited via
  [Accessible Web's summary](https://accessibleweb.com/question-answer/how-is-css-pseudo-content-treated-by-screen-readers/),
  consistent with [MDN's table accessibility guide](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content/Table_accessibility)).
  A sighted mouse/touch user sees "Cohort: RPAS Basic"; a screen reader user gets only "RPAS
  Basic", unlabelled. Fixing it needs a real `aria-label` per cell (or a visually-hidden inline
  span) built from the same header text, which is more markup than the two-markup approach below
  and still leaves a table element trying to read as a card.

USWDS documents this pattern as `usa-table--stacked` (no header duplication, just re-ordered
borderless rows) and `usa-table--stacked-header` (duplicates the header text into each cell via
`data-label`, e.g. `<th data-label="Document title" scope="row">…</th>`). Its own docs warn against
combining the stacked variant with column sorting, because the column headers that sorting acts on
"don't appear at narrow widths" ([USWDS Table component](https://designsystem.digital.gov/components/table/)).
That is a direct warning against the CSS-trick approach for exactly the case FLS has: a sortable
table that also needs a mobile layout.

**Two markups — a real `<table>` for `md`+ and a genuinely different card/list markup below
`md`, both server-rendered, toggled with responsive display utilities.** This is what Shopify
Polaris does for `IndexTable`'s condensed mode: below the breakpoint the component renders an
`<ul>` of list items instead of `<table>`/`<tr>`, not a CSS-reshaped table (confirmed by search
result summarising Polaris's docs and GitHub issues; condensed mode "becomes an unordered list
instead of using the HTML table tag"). Each markup is what it claims to be — a `<table>` reads as a
table, a card list reads as a list — so there is no `display`-property or generated-content
accessibility problem to work around. The costs are a heavier response (both markups render every
time) and template duplication if the two views aren't compositionally related.

Against **FLS's htmx fragment convention** (idea.md, "Invariants kept": the fragment root stays
`<div id="<key>">` swapped with `outerHTML`), the two-markup approach is close to free: the whole
point of that convention is that one swap replaces one root, so both the `<table>` and the card
list live inside the same `<div id="<key>">` and a single sort/filter/page htmx request updates
both at once. There is no second request, no client-side breakpoint re-fetch, and — critically —
**no JavaScript is needed to pick the right markup**: `hidden md:block`/`md:hidden` (or
`hidden md:table`/`md:hidden` on the table itself) is a pure CSS media-query decision, so it works
identically whether or not Alpine/htmx has loaded and survives resize without a request. That is
the same reasoning the idea.md invariant "every URL a table can push renders a full page on a
normal GET, with JavaScript off" already commits the table layer to elsewhere.

**CSS grid/subgrid** is not really a third stacking technique — it's a layout tool that still
requires deciding between "the table stays a table" (subgrid can align a table's columns without
sacrificing `display: table` semantics, which is useful for the desktop grid-column-widths seen in
the mockup's own `display:grid` markup, itself already grid-based rather than an HTML `<table>`)
and "the mobile view is something else" (cards). It doesn't avoid the choice above; it only affects
how the chosen desktop markup lays out its columns.

**Recommendation for this axis:** two markups, one fragment root, CSS-only breakpoint switch. Given
the mockup's card is a genuine recomposition (§ "What the mockups actually show", desktop-vs-mobile
comparison) rather than a subset of the same columns, trying to drive both from one `<table>` with
per-column show/hide flags would still leave FLS writing a second, unrelated card template for
anything beyond the simplest tables — so there is no real markup-reuse saving from the single-table
trick to offset its accessibility cost.

## 2. Declaring what appears on a card

How other systems let a table declare mobile behaviour, from loosest to richest:

- **Filament** (`TextColumn::make('slug')->visibleFrom('md')`, with a matching `hiddenFrom()`) is
  the simple per-column visibility-by-breakpoint declaration, using Tailwind's own breakpoint names
  ([Filament docs](https://filamentphp.com/docs/3.x/tables/layout)). It answers "which columns
  disappear" but not "what the row looks like once several are gone" — Filament's table is still a
  table at every width, just with fewer columns, which is a materially simpler problem than
  restyling into a card.
- **MUI DataGrid** has no built-in responsive stacking at all. Column visibility is a manual
  `columnVisibilityModel`/`hideable` mechanism the consumer wires up themselves, and full mobile
  reflow into a single-column card layout is an open, unresolved feature request against the
  library (`mui/mui-x` issues #6460 and #9776, per search results). This is the "you're on your
  own" end of the spectrum, and closest to what building this locally in FLS already means.
- **GOV.UK Design System's** table component does not document a stacked/responsive variant in its
  current docs; **USWDS's** `data-label` attribute is effectively a per-column "the header text
  this cell should carry when stacked" declaration, i.e. the header string is the only thing
  carried forward — again, no support for recomposing several columns into one line.
- **Shopify Polaris `IndexTable`** condensed mode doesn't declare per-column visibility at all; it
  renders a wholly different `<li>` template that the consumer/library controls directly. This is
  the "just write the card" end of the spectrum — closest to the mockup's actual card, which pulls
  Cohort into the meta line, drops the row-menu for a chevron, and reformats "Last active" into a
  status-specific phrase.

**What this means for FLS's table declaration.** A blanket `visibleFrom`-style flag per column
(Filament's model) is the right shape for simple, low-column tables (the roadmap names
`registrations`, presumably `cohorts`) where the card is genuinely "the same fields, fewer of
them" — declare a column as primary (always shown, becomes the card's title line), secondary
(folds into the card's meta line, in declaration order), or `md`-only (dropped below `md`
entirely), and let a default card template compose those three groups automatically, the same way
the existing `cotton/data-table-cells/*.html` cell templates already let a column declare custom
rendering. For a table as bespoke as the mockup's learner list — where the meta line's second
fragment is computed per status, not a straight column value — the table declaration needs an
escape hatch: an optional card-row template a consumer supplies, the same pattern
`data-table.html`'s usage docs already establish for custom cell templates ("Custom templates for
complex cells"). Don't try to make the default composition smart enough to reproduce the mockup's
status-specific meta string; that belongs in a per-table override, not the framework's default.

## 3. The filter-and-sort sheet

**Don't build a second sheet/dialog primitive.** Spec 3
(`educator-interface-3-panel-framework-dialogs/idea.md`) is already adding the one shared
mechanism this needs: the roadmap's ordering note says specs 2 and 3 "both add Alpine components
next to the framework's existing ones, so whoever lands second rebases onto the other's JS file."
`_base_interface.html`'s existing `sidePanel` component is the working precedent both specs cite —
one `<dialog>`, `show()` on desktop / `showModal()` below a breakpoint, `data-variant="bottom-sheet"`
already producing exactly M04's rounded-top, slide-up-from-bottom, backdrop-scrimmed sheet with a
grab handle affordance built into its CSS (`_base_interface.html`'s `<style>` block, the
`bottom-sheet` variant rules). Whichever of spec 2 or 3 lands first should build the filter-and-sort
sheet as a second consumer of the same dialog mechanics spec 3 is formalising (or, if spec 2 lands
first, build it recognisably reusable so spec 3 doesn't have to redo it) — not invent a third
independent sheet implementation. `research_ux_pitfalls.md` and `htmx-modal-drawer-url-state.md`
(read for spec 3) already cover the mobile-flip, focus-return and backdrop-click mechanics for this
shape of dialog in detail; nothing here supersedes them.

**Sort: a single-select list with a checkmark, not a native `<select>`, not visible radio
buttons — but backed by radio inputs.** M04 draws sort as a vertical list of options with the
current one bold and checked, which is a very close visual match for a styled radio group
(`<input type="radio">` per option, `appearance-none`, a check icon shown via `:checked` and a
sibling selector) rather than a `<select>`. A `<select>` is more compact but doesn't match the
mockup and gives worse touch targets than 48px full-width rows. Real radios also mean the sheet
degrades correctly **with JavaScript off**: it is an ordinary `<form>` whose fields (status
checkboxes/radios, the cohort select, the sort radios) submit as a normal GET to the table's own
prefixed query-string keys (`<key>-sort`, `<key>-<filter>`, per idea.md's "Per-table key"
convention) — no different from the sortable column headers idea.md already commits to being real
`<a href>`s that htmx merely intercepts. The "sheet" chrome (the slide-up dialog, the scrim, the
grab handle) is what needs JavaScript; the filtering and sorting mechanism underneath it does not,
and the idea.md invariant that every table URL renders a full page on a plain GET already requires
that split. A concrete no-JS fallback: render the sheet's contents in the page as an ordinary
`<details><summary>Filter and sort</summary>…</details>` disclosure below `md` when JS/the dialog
isn't available, or simply let the `<dialog>` element itself degrade to block content without
`showModal()`'s backdrop/inertness when unstyled — either way, the controls must exist as plain,
submittable form markup on the page, not only inside an inert, JS-only overlay.

**Apply vs live update.** General filter-UX research converges on a hybrid for exactly this shape
of control — a full-screen/bottom-sheet overlay with a batch "Apply" action, but with the apply
button itself showing a live, ahead-of-commit count of matching results
([Pencil & Paper, mobile filter patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-mobile-filters);
general guidance collected via [Lollypop's filter UX write-up](https://lollypop.design/blog/2025/july/filter-ux-design/)
converges on: live-update only when the query is cheap and the result set is small, an explicit
Apply for anything backed by a real query). M04's "Show 3 learners" button is exactly that hybrid —
the count updates as the reader taps status chips or changes sort, but nothing is applied to the
underlying table/URL until they tap it. Implementing the live count means the sheet's own controls
`hx-get` a small count-only fragment (or the button's label) as they change, while the actual page
navigation only fires on submit — two different htmx requests with two different targets, both
scoped to the sheet, neither touching the table behind it until Apply. This is additional
complexity budget worth calling out to the spec: the simplest version ships without the live count
(the button just reads "Show results") and adds it only if the count query is cheap enough not to
fire on every chip tap.

**Reset** clears the table's own prefixed keys, matching idea.md's per-table query-string
ownership — it must not touch another table's state sharing the same page.

## 4. Row selection and row actions on cards

The coordinator's decision: **row selection and bulk actions must work on the mobile card layout,
not just desktop.** Neither M03 nor M04 draws a selection checkbox on the card — the mockups were
drawn for the first-class design system's brand, not FLS's actual capability list (roadmap
"Assumptions the ideas make": "the mockups are the visual language, not the scope"), and bulk
actions are exactly the kind of capability the source idea and idea.md commit to (row selection
with a bulk-action hook, spec 8 registers the first actions) that the mockup simply didn't draw for
mobile. Treat the gap as an omission to fill, not a signal that mobile selection is out of scope.

Concretely: add a checkbox to the card, sized to a real touch target rather than the default
checkbox render. WCAG 2.5.8 (AA) sets a 24×24px CSS-pixel floor; the de facto mobile-platform
minimum both Apple's HIG and Material Design converge on, and what WCAG 2.5.5 (AAA) encodes
directly, is 44×44px
([TestParty's WCAG 2.5.5 guide](https://testparty.ai/blog/wcag-2-5-5-target-size-2025-guide);
[TestParty's WCAG 2.5.8 guide](https://testparty.ai/blog/wcag-target-size-guide)). The pattern for
getting there without a visually oversized checkbox glyph is standard: a small (e.g. 20×20px) input
wrapped in a `<label>` whose padding brings the whole clickable/tappable box to 44×44px, with the
label absorbing the tap rather than the bare input. Placement: leading edge of the card, vertically
centred against the avatar, mirroring the desktop table's leading checkbox column — keeps the same
mental model ("selection is always the leftmost/first thing") across breakpoints. The row's own tap
target (chevron → detail) and the checkbox's tap target must not overlap; the mockup's card is
already a single full-row tap target to the learner's detail, so the checkbox needs its own
clearly-bounded hit area that doesn't fight that.

The "n selected" bar: on desktop the mockup places selection state as inline text above the table
("1 selected · showing 8 of 31 learners", screen 02) alongside pagination — there's room for it in
the flow. On mobile there is real contention for the same screen real estate the bottom tab bar and
the floating action button already claim (M03: a 68px tab bar plus a 56px FAB pinned bottom-right).
The bar should displace or sit above the tab bar when anything is selected (a sticky bar just above
the tab bar, pushing the FAB out of the way or replacing it while a selection is active, since "add
learner" and "act on N selected learners" are mutually exclusive concerns at that moment) rather
than floating over card content or requiring a scroll to the top of the list. This is a layout
decision the spec should make explicitly rather than inherit from the desktop screen, since the
desktop screen has no competing bottom chrome to negotiate with.

Row actions (the desktop row-menu, ⋯): the card mockup replaces it with a chevron-to-detail rather
than an inline menu, which reads as "on mobile, act on a learner by opening them" rather than
"open a menu from the row." That's a reasonable simplification consistent with mobile table
critiques generally (menus that only reveal on hover are already flagged as a common failure mode,
§5) — but it means any action available from the desktop row-menu that doesn't also live on the
detail screen becomes unreachable from the mobile list. Cross-check that everything the row-menu
offers is also reachable from wherever the chevron leads (M05, the learner detail) before treating
"drop the menu, keep the chevron" as settled.

## 5. Common complaints about mobile data tables

Recurring findings across UX write-ups on this topic
([Why Data Tables Fail, DEV Community](https://dev.to/137foundry/why-data-tables-fail-and-how-to-fix-the-most-common-ux-mistakes-4keo);
[Designing Mobile Tables, UXmatters](https://www.uxmatters.com/mt/archives/2020/07/designing-mobile-tables.php);
general survey via [Tenscope's mobile table UI piece](https://www.tenscope.com/post/table-ui-design-tips-common-issues)):

- **Horizontal-scroll-only "responsive" tables** (keep the table, let it overflow, scroll
  sideways) force the reader to scroll to compare any two columns and to zoom to read tiny text —
  named repeatedly as the worst-received "solution" precisely because it changes nothing about the
  table except making it harder to read. This is what FLS's current `scroll-table-labels.html`
  component does today (a horizontal-scroll table with a floating first-column-label overlay below
  768px) — worth naming directly: this spec's stacked-card treatment is the replacement for that
  workaround on any table it's applied to, not an addition beside it.
- **Menus/actions that only reveal on hover** are invisible to touch (and keyboard) — directly
  relevant to the row-menu-vs-chevron question in §4.
- **Shrinking type to fit more rows** trades readability for density; the card layout's larger,
  clearly-hierarchied text (name bold, meta muted, mono percentage) is the opposite move and should
  stay that way rather than being squeezed to fit more cards per screen.
- **Sorting/column headers that "don't appear at narrow widths"** breaks any control that depends
  on seeing the header — USWDS's own warning against combining `stacked` with sortable columns
  (§1) generalises: whatever exposes sort on mobile (the sheet, §3) must not depend on a header
  being visible in the card list itself.
- **Pagination without a total count** leaves the reader lost — M03's mono "31" in the app bar and
  the mockup's "showing N of M" pattern on desktop both already address this; keep the count
  visible on mobile too, not just in the (rare) fully-loaded state.

## Recommendation

Render the table twice inside the same fragment root, not once with CSS tricks. Ship the real
`<table>` for `md`+ (or whatever grid/subgrid layout the desktop redesign settles on) and a
separate, genuinely list-shaped card markup below `md`, both produced by one server response,
switched purely by responsive display utilities so no JavaScript and no second request decide
which one a reader sees — this is what the fragment-root invariant already buys, and it sidesteps
the `display`-on-table-elements accessibility history entirely rather than betting on it having
fully resolved everywhere FLS will be used. Don't reach for a `data-label`/`::before` restyled
table: the browser bug it depends on has substantially receded but never fully, and the label
technique itself needs a real `aria-label` per cell regardless, which is more work than just
writing the second markup properly.

For the column declaration, don't try to make one flag do both jobs. Give a table's declared
columns a lightweight primary/secondary/`md`-only grouping so a default card composes itself for
simple tables (this is Filament's `visibleFrom` idea, cheaply generalised), and let a table that
needs the learner mockup's denser, computed card — cohort folded into a status-specific meta
string, no row-menu, a chevron instead — supply its own card-row template the same way it already
supplies custom cell templates for complex columns. Building a "smart" default that infers the
mockup's composition from column metadata alone is not worth the complexity; it will only ever fit
one table well.

Build the filter-and-sort sheet as a second consumer of the dialog mechanism spec 3 is
standardising (the existing `sidePanel` bottom-sheet variant already renders the right visual
shape), not a bespoke implementation — the roadmap already flags this exact collision between specs
2 and 3 and says whoever lands second rebases. Render sort as a styled radio group and status as
styled checkboxes/toggle chips inside a real `<form>` that GETs the table's own prefixed
query-string keys, so the filtering mechanism works with JavaScript off and the sheet chrome is a
pure progressive enhancement on top of it, consistent with every other pushable table URL in this
spec rendering a full page on a plain GET. Ship the simple version of Apply first — a plain "Show
results" submit, no live count — and only add the live result-count-on-the-button refinement if a
cheap count query is available; it's a real UX improvement but not one worth adding request
plumbing for on the first pass.

Finally, treat mobile row selection as required scope, not a follow-on: put a properly-sized
(44×44px tap target) checkbox on the leading edge of each card, mirroring the desktop table's
leading checkbox column, and give the mobile "n selected" bar an explicit place to live that
accounts for the tab bar and FAB already claiming the bottom of the screen — most simply, a bar
that appears above the tab bar and takes the FAB's place while a selection is active, since adding
a learner and acting on several selected ones are not things a reader does in the same moment.
Confirm every action the desktop row-menu offers is reachable from the card's chevron-to-detail
path before treating the row-menu's removal as a safe simplification rather than a scope loss.

## Sources

- [Adrian Roselli, "Tables, CSS Display Properties, and ARIA" (2018, updated 2023)](https://adrianroselli.com/2018/02/tables-css-display-properties-and-aria.html)
- [CSS-Tricks, "Accessible, Simple, Responsive Tables"](https://css-tricks.com/accessible-simple-responsive-tables/)
- [MDN, HTML table accessibility](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content/Table_accessibility)
- [Accessible Web, "How is CSS pseudo content treated by screen readers?"](https://accessibleweb.com/question-answer/how-is-css-pseudo-content-treated-by-screen-readers/)
- [USWDS, Table component](https://designsystem.digital.gov/components/table/)
- [Filament, Table Builder layout docs (`visibleFrom`/`hiddenFrom`)](https://filamentphp.com/docs/3.x/tables/layout)
- [MUI X, Data Grid column visibility](https://mui.com/x/react-data-grid/column-visibility/)
- [MUI X GitHub issue #6460, mobile responsiveness support for DataGrid](https://github.com/mui/mui-x/issues/6460)
- [MUI X GitHub issue #9776, mobile column header regression](https://github.com/mui/mui-x/issues/9776)
- Shopify Polaris `IndexTable` condensed mode (list markup on mobile, bulk-action visibility tied to breakpoint) — via search summary of `polaris-react.shopify.com` docs and `Shopify/polaris-react` GitHub issues; the canonical docs page redirected during this research (`shopify.dev/docs/api/polaris`) and was not re-fetched.
- [Pencil & Paper, mobile filter UX pattern analysis](https://www.pencilandpaper.io/articles/ux-pattern-analysis-mobile-filters)
- [Lollypop, "Filter UX Design: Best Practices for SaaS Product Success"](https://lollypop.design/blog/2025/july/filter-ux-design/)
- [DEV Community, "Why Data Tables Fail and How to Fix the Most Common UX Mistakes"](https://dev.to/137foundry/why-data-tables-fail-and-how-to-fix-the-most-common-ux-mistakes-4keo)
- [UXmatters, "Designing Mobile Tables"](https://www.uxmatters.com/mt/archives/2020/07/designing-mobile-tables.php)
- [Tenscope, "How to design a mobile table and top table UI design tips"](https://www.tenscope.com/post/table-ui-design-tips-common-issues)
- [TestParty, WCAG 2.5.5 Target Size (Enhanced) guide](https://testparty.ai/blog/wcag-2-5-5-target-size-2025-guide)
- [TestParty, WCAG 2.5.8 Target Size (Minimum) guide](https://testparty.ai/blog/wcag-target-size-guide)
- Codebase read directly: `spec_dd/1. next/educator-interface-2-panel-framework-tables/idea.md`; `spec_dd/1. next/roadmap.md` ("Educator interface rebuild" section); `spec_dd/1. next/educator-interface-3-panel-framework-dialogs/idea.md`; `spec_dd/1. next/educator-interface-full-polish/Educator LMS Interface Design/Educator Mobile Learners.dc.html` (M03, M04); `.../Educator Learners.dc.html` (screen 02); `spec_dd/1. next/educator-interface-full-polish/htmx-modal-drawer-url-state.md`; `freedom_ls/base/templates/cotton/data-table.html`; `freedom_ls/base/templates/cotton/data-table-cells/{link,text,boolean}.html`; `freedom_ls/base/templates/cotton/scroll-table-labels.html`; `freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_base.html` and `_data_table_region_base.html`; `freedom_ls/base/templates/_base_interface.html` (`sidePanel`, bottom-sheet variant); `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`; `claude_plugins/fls-dev/resources/frontend_styling.md`; `claude_plugins/django-stack/resources/frontend_styling.md`.

status: ok
