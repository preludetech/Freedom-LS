# Research: how mature design systems specify admin/dashboard components

Input to spec 4 (panel framework cotton components). Compares GOV.UK Design System, Shopify Polaris,
GitHub Primer, Atlassian Design System, IBM Carbon, and Tailwind UI (Catalyst) / Flowbite, per
component in the spec 4 inventory, plus documentation approach and common pitfalls.

## Page header (title, meta, status, actions)

- **Polaris**: page header composes a title, optional badge/status, breadcrumb, and an actions
  group; "primary" action stays visible, secondary actions collapse into an overflow menu on
  narrow viewports rather than wrapping or disappearing (Polaris has open issues tracking header
  actions still being inconsistent on mobile web, which is itself a signal that this is a genuinely
  hard responsive problem, not a solved one). Common actions guidance: put the action associated
  with the page's core resource (e.g. "Add") in the header; put actions scoped to a sub-section
  (a table) in that section instead of the page header. [Common actions](https://polaris.shopify.com/patterns/common-actions), [mobile header issue](https://github.com/Shopify/polaris/issues/706)
- **Catalyst** (Tailwind UI): `Heading`/`Subheading` are plain typographic components, composed
  by hand into a header row with a button group; no built-in collapse behaviour — the pattern
  relies on flex-wrap and the surrounding page template. [Catalyst heading](https://catalyst.tailwindui.com/docs/heading)
- **GOV.UK**: no dedicated "page header" component — GOV.UK services use an H1 plus a phase/tag
  banner and keep actions minimal (mostly one primary link), consistent with the service's
  "do less, do it well" ethos rather than a dense admin toolbar.

Takeaway: none of these systems solve mobile action-overflow elegantly by CSS alone; Polaris's own
issue tracker shows this is still being iterated on. Treat "how actions collapse on mobile" as a
decision to make explicitly (stack into a second row under the title, or fall back to a single
"more actions" menu triggered by HTMX/disclosure) rather than assume flex-wrap is enough.

## Stat tile / metric card

- **Carbon** tiles are generic flexible containers (base/clickable/selectable/expandable); Carbon's
  differential/trend indicator pattern is the relevant piece: a delta value must carry a `+`/`-`
  sign, a chevron/arrow icon, **or** text — colour is explicitly optional and never the only
  carrier of meaning. [Status indicators](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
- **Streamlit's `st.metric`** (not a full design system, but the sharpest prior art for the
  "higher is worse" problem) exposes `delta_color="inverse"`/`"off"` precisely because a raw `+2.3%`
  is ambiguous without knowing whether the metric wants to go up or down — a metric like a
  "stalled learner count" or "overdue count" needs its polarity flipped or its colour removed.
- **Tailwind UI "Stats"** blocks are presentational only (value, label, optional trend chip) with
  no built-in semantics; the polarity/colour decision is left entirely to the consumer, which is
  exactly the ambiguity Carbon and Streamlit call out. [Tailwind stats](https://tailwindcss.com/plus/ui-blocks/application-ui/data-display/stats)

Takeaway for FLS: a stat tile component needs a `direction`-of-good prop (or a pre-computed
tone, decided by the caller/spec 10 — not by the component guessing from the sign of the number),
units and a sub-line as plain text, and delta communicated with an icon + text, colour as
reinforcement only. Screen-reader order should read label, then value, then delta as a sentence
("up 3 from last week"), matching the "readable as label then value" accessibility note already in
the idea.

## Status badge / tag

This is the pattern with the most convergent guidance across systems, and the most relevant one
for FLS's "fixed vocabulary" decision:

- **GOV.UK tag**: 9 colour tones (grey, green, teal, blue, purple, magenta, red, orange, yellow, plus
  default grey), one tag per status, **sentence case not uppercase** (GOV.UK moved away from
  uppercase because it's harder to read for longer labels), never interactive/clickable, uses
  adjectives not verbs, and explicitly "do not use colour alone to convey information." [Tag](https://design-system.service.gov.uk/components/tag/)
- **Atlassian lozenge**: 6 semantic tones (neutral, success, warning, danger, information,
  discovery) plus 9 non-semantic accent colours for user-chosen categories — i.e. Atlassian
  deliberately separates "this colour means something in the product" from "this colour is just a
  label a user picked," which is a useful split if FLS ever lets educators tag things themselves
  vs. the system computing a status. [Lozenge](https://atlassian.design/components/lozenge/examples)
- **Polaris badge**: tone-based (success/warning/critical/attention/info/new, roughly), sized
  small/medium, used "to inform merchants of the tone of an object or an action taken" — Polaris
  guidance elsewhere warns against badge overuse: a table with a badge in every column stops
  drawing the eye to the one badge that matters.
- **Flowbite**: purely presentational colour tokens (blue/gray/red/green/yellow/indigo/purple/pink)
  with no semantic mapping — a caution, not a model: this is what "colour vocabulary" looks like
  before it's been disciplined into a fixed domain vocabulary. [Flowbite badge](https://flowbite.com/docs/components/badge/)

Takeaway: FLS's plan (one fixed vocabulary — active, inactive, pending, complete, in progress,
stalled — mapped to a small number of semantic tokens) matches GOV.UK/Atlassian practice, not
Flowbite's open colour palette. Keep it sentence case per current GOV.UK guidance rather than the
older uppercase convention some other systems (and the mockups, possibly) may still use — check
mockup casing against this before committing. Badge text must carry the word, not just colour;
reserve badges for the one or two facts per row that matter — don't badge everything a row has.

## Avatar with initials

- **Primer** (GitHub) and most avatar-with-initials implementations surveyed generate the fallback
  colour deterministically from a hash of the user's identifier (name/id), not randomly and not
  from a designer-picked "assign the next colour in sequence" scheme — this guarantees the same
  person gets the same colour everywhere without a lookup table. [Primer/avatar prior art](https://marcoslooten.com/blog/creating-avatars-with-colors-using-the-modulus/)
  General pattern across implementations: pick from a small fixed palette (6-10 colours) via
  `hash(identifier) % palette.length`, not free-form colour.
  Sizes are typically a small fixed scale (e.g. xs/sm/md/lg), reused for both image and
  initials fallback so they interchange without layout shift.

Takeaway: FLS's avatar chip should hash the learner/educator's stable id (not display name, which
can change) into one of the FLS role-token colour slots, fall back to initials when there's no
photo (FLS likely has no photos at all yet, so this *is* the only state), and share one size scale
with the rest of the kit rather than inventing avatar-specific sizing.

## "Needs attention" / action list pattern

None of the six systems has an exact off-the-shelf component named this, but two map closely:

- **GOV.UK task list**: a list where each row is a task name + a status tag, explicitly reserved
  for cases where "users need flexibility in task ordering" or work spans sessions — GOV.UK
  guidance says *don't* use it for a strictly sequential flow (simplify the service instead), and
  it uses `aria-describedby` to associate each task's accessible name with its status so a screen
  reader announces "Learner name, stalled" rather than the two being read as unrelated. [Task list](https://design-system.service.gov.uk/components/task-list/)
- **GOV.UK summary card actions** and **Atlassian lozenge with a single primary action** both
  reinforce the same shape: one row = one identity + one status + at most one or two actions, not
  a menu.

Takeaway: the attention list in spec 4 (a row per learner, a reason, a badge, one action) is
structurally GOV.UK's task list minus the "in this session" framing — reuse its accessibility
pattern (badge described alongside the learner name, not a bare coloured tag floating in a table
cell) and its restraint on actions (one action per row, not a menu).

## Progress bar

Convergent and unremarkable across systems: a horizontal determinate bar, a numeric percentage
label (visible, not just `aria-valuenow`), and an optional caption/label above or beside it. No
system surveyed recommends an indeterminate/animated variant for this use (that's what
spinners/skeletons are for). Carbon and GOV.UK both treat "percentage as text" as non-negotiable
for accessibility, not decorative — same principle as badges: colour/fill alone isn't the message.

Takeaway: matches what's already settled in the idea ("percentage and optional label"); no changes
needed, just confirm the FLS progress bar always renders the number as text (not `aria-hidden`),
and stays determinate-only — no busy/indeterminate mode is in scope.

## Card / section with header and footer actions

- **GOV.UK summary card**: title + up to 2-3 header-level actions that apply to the *whole* card
  (not a per-row action), with explicit guidance to keep the action count small and consider a
  confirmation step for anything irreversible. [Summary list/card](https://design-system.service.gov.uk/components/summary-list/)
- **Carbon tile**: deliberately minimal/structural — a tile is a container, not a component with
  opinions about header/footer slots; Carbon leaves composition to the consumer.
- **Tailwind UI "Card headings"**: header is a heading + optional description + an action slot,
  footer (if present) is a separate bordered region for actions — the header/body/footer split
  FLS's idea already describes.

Takeaway: FLS's section card (heading, optional description, body, footer actions) matches the
GOV.UK summary card + Tailwind UI card heading shape. Cap footer/header actions at 2-3 like GOV.UK
does — this is a good concrete constraint to write into the spec so downstream screens don't turn
every card into a button bar.

## Definition / summary list

- **GOV.UK summary list**: the canonical reference for this exact component. Rows are
  label/value pairs; borders between rows help users who zoom or use assistive tech scan rows;
  missing/empty values get a link in the *value* column ("Add license number") rather than a
  disabled or blank cell; row actions are "Change X" links with visually-hidden context text so a
  screen reader announces which field is being changed, not a bare "Change". [Summary list](https://design-system.service.gov.uk/components/summary-list/)
- **Catalyst description list**: `DescriptionList`/`DescriptionTerm`/`DescriptionDetails` compose
  the same term/value pairing with a plain heading (`Subheading`) above, and defines a responsive
  behaviour (stacking term above value on narrow screens vs. side-by-side on wide). [Catalyst description list](https://catalyst.tailwindui.com/docs/description-list)

Takeaway: FLS's "Learner details" definition list (mockup 03) should follow GOV.UK's empty-value
rule (an actionable link/hint in the value slot, not a blank dash) if any field can be genuinely
missing, and Catalyst's stack-on-mobile/side-by-side-on-desktop responsive rule. If row actions are
in scope, hidden context text ("Edit email" not just "Edit") is the one non-negotiable a11y detail
to carry over.

## Toolbar with search and filter chips

- Convergent across Carbon, PatternFly, and UK government design systems (MOJ/DWP/CMS all publish
  a "filter chip"/"selected filters" pattern independently, which is itself a signal this is a
  well-worn admin-UI problem): applied filters render as a row of removable chips above or beside
  the results, each chip has its own dismiss (×), and there is a single "Clear all"/"Clear filters"
  action that appears once at least one filter is applied (not shown when the filter set is empty).
  [Carbon filtering](https://carbondesignsystem.com/patterns/filtering/), [MOJ filter](https://design-patterns.service.justice.gov.uk/components/filter/)

Takeaway: FLS's toolbar (search + filter chips + primary actions) should render the "clear all"
control conditionally (only with ≥1 active filter), and each chip needs its own dismiss control,
not just a global clear — matches what's already implied by "filter chips" in the idea.

## Empty states

- **Polaris** is the most explicit here: empty state = image/icon + heading + one sentence + one
  action, and it distinguishes at least three cases in its own documented usage: **first-use /
  onboarding** (guide the user to create the first thing), **no-results** (a search/filter query
  matched nothing — Polaris explicitly says this should render as an empty state, *not* a
  validation error), and by implication **error** states use the same shell with an
  alert/error icon instead of the neutral one. [Empty state icons](https://shopify.dev/docs/api/pos-ui-extensions/latest/polaris-web-components/layout-and-structure/empty-state)

Takeaway: FLS's single empty-state component (icon, sentence, one action) is right-sized for scope
— the variance across first-use/no-results/error should be expressed by which icon and which
sentence/action the *caller* passes in, not by three separate components. Keep the no-results case
distinct in callers' minds from a validation error (no-results is not a failure).

## Tabs

No system surveyed treats tab *styling* as separate from tab *behaviour* at the component level —
all of them ship one component that owns both the look (underline/pill) and the keyboard/ARIA
behaviour (roving tabindex, `role="tablist"`/`"tab"`/`"tabpanel"`, arrow-key navigation) because
the two are accessibility-coupled: change the visual affordance without the ARIA wiring and you get
a tab bar that looks right but fails screen readers/keyboards.

Takeaway: the idea's "tab bar styling shared with the framework's tab container" phrasing suggests
spec 4 supplies styling only, deferring behaviour to the framework's existing tab container — this
research doesn't contradict that split, but flags it as the one place where styling-only ownership
is riskier than elsewhere: verify the framework's existing tab container already owns full ARIA
behaviour, because no external system treats that behaviour as separable from style with a clean
seam.

## Skeleton loading

- **NN/g** confirms skeleton screens measurably improve perceived performance and reduce bounce
  vs. a blank page or spinner for *page-level* loads, but the broader guidance converges on: don't
  use skeletons for small/fast-loading elements (a skeleton that flashes for 100ms is worse than
  nothing), don't use them for transient UI (toasts, menus, modals — the container, not its
  contents), and reserve them for content that takes long enough to matter (roughly >1 second).
  [NN/g skeleton screens](https://www.nngroup.com/articles/skeleton-screens/)
- **Flowbite** ships skeleton primitives per content shape (text lines, image block, list row,
  card) rather than one generic grey box, animated with `animate-pulse`. [Flowbite skeleton](https://flowbite.com/docs/components/skeleton/)

Takeaway: FLS's skeleton blocks (used by spec 3) should be shaped per the component they stand in
for (a stat-tile skeleton, a table-row skeleton) rather than one generic rectangle, and spec 3/the
caller should gate them on actual latency (HTMX request taking >~300-500ms) rather than always
flashing one on every request — an instant swap with no skeleton is preferable to a skeleton that
appears and disappears within a frame.

## How these systems document the kit

Every system surveyed publishes the same shape of artefact: a **living page per component** with
the rendered example, the do/don't usage guidance, and the code/markup right next to it — GOV.UK's
component pages, Carbon's usage/style/code tabs, Polaris's component + pattern pages, and (for teams
without design-side tooling) Storybook's auto-generated docs-per-component serve the same job for
engineering-only teams. The common thread is **one example of every state on one page**, not a
separate demo per variant scattered across the app.

Takeaway: this is exactly what spec 4's "reference page" (a dev-only page rendering every component
in every state) already plans to be — no change needed, but note that GOV.UK/Carbon pages also pair
each rendered example with a one-line usage rule ("use when… don't use when…"), which is cheap to
add as a comment/caption on the reference page and pays for itself the first time a downstream spec
(6-10) picks the wrong component.

## Pitfalls called out repeatedly across sources

- **Too many variants / props explosion**: component libraries that let every consumer add a new
  prop or colour end up with buttons/cards with 12+ props or 1000+ variant combinations that no one
  can reason about; the fix used across sources is composition (slots) over flags, and treating a
  new visual axis as a new decision to justify, not a default yes.
- **Colour-only meaning**: GOV.UK, Carbon, and WCAG all converge on the same rule independently —
  every colour-coded status must also carry text (or an icon+text), never colour alone.
- **Badge/tag overuse**: badging every cell in a table (or every field in a card) defeats the
  purpose of a badge, which is to make the one status that matters easy to spot; reserve badges for
  facts that change routing/attention, not for restating data already legible as plain text.
- **Uppercase tags**: GOV.UK's own design system moved *away* from uppercase tags because it hurts
  readability for longer text — worth checking against the mockups before locking in casing.
- **Skeletons that flash**: shipping a skeleton unconditionally, even for near-instant HTMX swaps,
  trains users to associate the skeleton with "something is wrong" rather than "still loading."

## Recommendations specific to FLS's scope (spec 4)

1. **Status badge**: fix the vocabulary token-for-token as already planned (active, inactive,
   pending, complete, in progress, stalled → a small semantic token set), render in sentence case
   (not uppercase — check mockups), and require the component to render visible text alongside the
   token colour; never allow a caller to invoke the badge with colour only.
2. **Stat tile**: give the component (or its caller) an explicit "which direction is good" signal
   rather than inferring it from the sign of the delta — this is the one place FLS has a real
   "stalled learner count" style metric where naive +/- colouring would be backwards. Delta is
   icon + text; colour is reinforcement, not the only signal.
3. **Avatar chip**: derive the fallback colour deterministically from the learner/educator's stable
   id (hashed into the existing FLS role-token palette), not name (which can change) and not
   insertion order; reuse one size scale across the whole kit.
2b. **Attention list**: cap actions at one per row (matches idea already); associate the badge with
   the row's subject in markup (e.g. `aria-describedby`) so assistive tech reads them together, per
   GOV.UK task list precedent.
4. **Section card**: cap header/footer actions at 2-3, matching GOV.UK summary card guidance — write
   this as an explicit constraint in the component's usage note on the reference page, since nothing
   else will stop a downstream spec from stacking five buttons in a footer.
5. **Definition list**: if any field can be genuinely empty, render an actionable hint/link in the
   value slot rather than a blank dash (GOV.UK rule); stack label above value on narrow screens,
   side-by-side on wide (Catalyst rule); hidden context text on any row action link ("Edit email"),
   not a bare "Edit".
6. **Toolbar/filter chips**: only show "clear all" once ≥1 filter chip is active; every chip carries
   its own dismiss control.
7. **Empty state**: one component, three callers' worth of icon/sentence/action (first-use,
   no-results, error) — don't build three components for this. Explicitly do not treat "no results"
   as an error state.
8. **Tabs**: confirm the framework's existing tab container owns full keyboard/ARIA behaviour before
   spec 4 supplies styling-only on top of it; no system surveyed treats tab style as cleanly
   separable from tab behaviour.
9. **Skeletons**: build them per-component-shape (a stat-tile skeleton looks like a stat tile), and
   make sure spec 3's usage gates them on real latency rather than flashing on every swap.
10. **Reference page**: pair every rendered state with a one-line usage note (use when / don't use
    when), following GOV.UK/Carbon precedent — cheap now, saves a wrong-component choice in specs
    6-10 later.
11. **General discipline**: resist adding a prop/colour/variant to any of these components unless a
    named downstream spec (6-10) needs it; composition (slots) over flags when a component's shape
    needs to vary; keep the badge/tag colour vocabulary closed (FLS's domain statuses only, not an
    open palette a future spec could quietly extend).

## Sources

- [GOV.UK Design System — Tag](https://design-system.service.gov.uk/components/tag/)
- [GOV.UK Design System — Summary list](https://design-system.service.gov.uk/components/summary-list/)
- [GOV.UK Design System — Task list](https://design-system.service.gov.uk/components/task-list/)
- [GOV.UK Design System — Notification banner](https://design-system.service.gov.uk/components/notification-banner/)
- [Shopify Polaris — Common actions pattern](https://polaris.shopify.com/patterns/common-actions)
- [Shopify Polaris — mobile header actions issue #706](https://github.com/Shopify/polaris/issues/706)
- [Shopify Polaris (POS UI extensions) — empty state icons](https://shopify.dev/docs/api/pos-ui-extensions/latest/polaris-web-components/layout-and-structure/empty-state)
- [Atlassian Design System — Lozenge examples](https://atlassian.design/components/lozenge/examples)
- [Atlassian Design System — components overview](https://atlassian.design/components)
- [IBM Carbon Design System — Status indicator pattern](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
- [IBM Carbon Design System — Filtering pattern](https://carbondesignsystem.com/patterns/filtering/)
- [Catalyst UI Kit — Heading](https://catalyst.tailwindui.com/docs/heading)
- [Catalyst UI Kit — Description list](https://catalyst.tailwindui.com/docs/description-list)
- [Tailwind UI — Stats blocks](https://tailwindcss.com/plus/ui-blocks/application-ui/data-display/stats)
- [Flowbite — Badge](https://flowbite.com/docs/components/badge/)
- [Flowbite — Skeleton](https://flowbite.com/docs/components/skeleton/)
- [MOJ (justice.gov.uk) Design Patterns — Filter](https://design-patterns.service.justice.gov.uk/components/filter/)
- [NN/g — Skeleton Screens 101](https://www.nngroup.com/articles/skeleton-screens/)
- [Avatar fallback colour hashing prior art](https://marcoslooten.com/blog/creating-avatars-with-colors-using-the-modulus/)

status: ok
