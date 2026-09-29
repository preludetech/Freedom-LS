# Panel framework components

Spec 4 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

This spec builds the cotton components the mockups are made of. They live once in `panel_framework`, built on FLS role tokens, so that specs 6 to 10 assemble screens instead of styling them. Each component owns its own styling, and a theme can override it at the same loader path.

The kit is a supported public API. Downstream projects may use the components in their own panels, so component names and attributes are a contract. Breaking changes go in the upgrade notes.

## Why

The mockups in `../educator-interface-full-polish/Educator LMS Interface Design/` were drawn for the first-class brand, with Phosphor icons and their own CSS. They are the design, and the layouts, densities and component shapes are what we build to. None of their markup is FLS markup, though. If each feature spec styles its own cards and badges, the interface will look like four people built it.

## What is settled

### Inventory

`research_mockup_inventory.md` goes through the mockups screen by screen: variants, densities, mobile differences and every badge label. `research_existing_components.md` covers what FLS already has for each item.

- **Page header.** Title, optional subtitle, status badge and an action group, as in the profile block on 03 and the cohort header on 05. Composes `c-button-group` and sits under the existing breadcrumbs. It renders the page's one `h1` by default and takes a heading level for reuse lower down. List views have no `h1` today, and this fixes that. The instance view's header must keep emitting `id="instance-title"`, because the framework's JS updates that element.
- **Stat tile.** Value, label and an optional delta or sub-line, in a responsive row. Two shapes: the boxed tile (01, M01, and the small tiles in the quick view) and the card-less inline row inside the cohort header (05, M08). The caller says whether a rising value is good, because a higher count of learners needing attention is worse, not better. The tile never infers that from the sign. Deltas are text with a decorative icon. Colour only reinforces.
- **Status badge.** It takes a tone and a label. The tones are the names `c-chip` already uses: `success`, `warning`, `error`, `info`, `muted`. The badge wraps `c-chip` and inherits its tint styling. Solid success, error and info fills with white text fail WCAG AA at badge size, and the tint does not. Labels are sentence case. The badge owns no domain words. Each spec that owns a status maps its words to tones. Spec 10 maps progress and attention through `reports` (`AtRiskRule.severity` already emits these tone names), and specs 6, 7 and 9 map their administrative states. "Stalled" is not a status: spec 10 calls the same thing "inactive". `research_status_vocabulary.md` lists every status an educator screen shows, the two collisions on "inactive", and a suggested tone for each.
- **Avatar chip.** Initials and name, optionally with email or role under it (02, 03, 05). The initials are hidden from assistive tech, so the name is the accessible name. The background colour is picked from a small token palette by hashing the user's id, never the name.
- **Attention list.** A `<ul>` with one row per subject: a leading avatar chip or a severity icon, a reason, an optional badge and at most one action. The desktop learner rows (01) show all of it. The cohort-level rows (05) have an icon, text and a link. On mobile the row itself becomes the link, with a trailing chevron (M01, M08). The action's accessible name includes the subject ("Message Thandi Mokoena"), not just the verb.
- **Progress bar.** Percentage as visible text, and an optional label. Uses the native `<progress>` element, as `c-course-progress-bar` does, but fills with role tokens rather than the course accent. It stays a separate component. `c-course-progress-bar` is noted as a candidate to merge with it later.
- **Section card.** Heading, optional description, body and an optional actions footer, with at most three actions. It wraps the framework's panel container rather than replacing it. `_panel_base.html` keeps its plumbing (`data-panel`, the region id, the `panelChanged` self-refresh) and renders its header, body and actions blocks through the card. A bare panel and a hand-placed card then look the same and are themed from one file. A card is not a landmark unless a caller asks for one.
- **Definition list.** Label and value pairs, stacked below `md` and in columns above (03 learner details, 05 cohort details). Extract it from `_instance_details_base.html` and have that template call it. Keep that template's split between a `<dl>` and a `<table>`. Never restyle a real table into a stack.
- **Toolbar.** A search box with a real label, a slot for filter chips, a slot for primary actions, and the applied-filter chips. Each applied chip has its own labelled remove button, and "Clear all" appears only when a filter is applied. A filter toggle is a `<button aria-pressed>`. The toolbar is a plain container, not `role="toolbar"`. This spec owns how the toolbar looks. Spec 2 fills it with its declared filters and owns their query-string state.
- **Empty state.** An icon, one sentence and one action. The caller chooses the icon and wording, which covers first use, no results and error. The mockups draw none, so build it from the kit's own tokens and spacing. "No results" is not an error.
- **Tab bar.** Styling only, applied to `_tab_set_base.html`'s existing `<nav>` of links with `aria-current`. Spec 1 decided those links are navigation, not ARIA tabs. Do not add tab roles.
- **Skeleton blocks.** Shaped like the component they stand in for (a tile, a list row, lines of text), hidden from assistive tech, and still under `prefers-reduced-motion`. The region being loaded carries `aria-busy`. Spec 3 uses them in the quick view and decides when to show them. They are not for swaps that finish in a blink.

The mockups also show a callout on 03, 08, M06 and M11. Use `c-callout` from `base` for it. The stepper, the file chip and the column-mapping rows (08, M11) belong to spec 8. The kebab trigger is `c-dropdown-menu`'s business, and the floating action button is not wanted.

### Tokens and icons

FLS role tokens only, per `fls-dev:frontend-styling`. There are no raw colour utilities, least of all on anything that carries a status. Radius, spacing and shadow follow the existing FLS scale, not the first-class README. FLS has no dark theme, and this spec builds none. Components that use only role tokens will follow one when a theme adds it.

Icons come through `c-icon` only, per `fls-dev:icon-usage`, and no Phosphor. Where the kit needs a concept that has no semantic name, add the name to the icon registry and map it in every shipped icon set. The kit needs add, search, filter, and trend up and down. Add only the names these components use. Feature specs add their own the same way. `research_mockup_inventory.md` §4 maps every mockup icon to its closest semantic name and lists the gaps.

### Where and how

- Components live under `freedom_ls/panel_framework/templates/cotton/` with a `panel-` prefix (`panel-stat-tile`, `panel-status-badge`). Cotton's namespace is flat. The prefix matches how `course-` and `content-` are used elsewhere, and no existing name collides with it. Tailwind's existing `@source` glob already picks the directory up.
- Utilities go on the markup. An `@layer components` block goes inside a component only where no utility exists. Nothing goes in `tailwind.components.css`. Every markup change sets `requires_tailwind_rebuild` in the upgrade notes.
- A component that would suit the learner interface is noted for a later move, not moved now.

### Reference page

One `panel_framework` view renders every component in every state from static example data, with no database queries. Each example carries a one-line "use when" note and a stable anchor that spec 12's visual check can target. The view is registered twice:

- In a new `panel_framework/urls.py`, which a project includes under `if settings.DEBUG:`, the way `config/urls.py` includes `debug_toolbar` today. The view also requires staff. It does not check `DEBUG` itself.
- Unconditionally, in the framework's test-only URLconf. Django forces `DEBUG` off under pytest, so a URL gated on `DEBUG` never exists in a Playwright run.

`research_reference_page.md` weighs this against a contrib app, a test-only page and a static HTML dump.

### Accessibility

Text carries every status, never colour alone. A stat tile is a `<dl>` read label then value; CSS puts the value on top visually. Any change announced after a swap goes through the framework's existing `#scope-announcer`, never through a live region on a component. `research_accessibility.md` has markup for each component and the WCAG criteria it touches.

## Open until the spec

- How the page header's actions collapse on mobile: a second row, or an overflow menu. No design system reviewed solves this with CSS alone.
- How far to go with forced colours (Windows high contrast). The minimum is that the progress bar's track and a pressed filter chip stay distinguishable.
- Whether the avatar palette reuses the course accent slots or needs its own tokens.

## Out of scope

- Charts. If spec 10 wants a chart, it uses the `dataviz` skill then.
- Changes to `base` components, `c-callout` and `c-chip` included. If one needs to change, note it and leave it.
- A dark theme.
- The mockups' assessment states ("Retake due", "Submitted"), since retakes and review are out of scope for the effort. Also "Invited", which the roadmap calls "pending".
- Marketing or learner-facing pages.

## Resources

- `research_mockup_inventory.md`: components, variants and badge labels by screen, the mobile differences, and icon mapping.
- `research_existing_components.md`: what FLS has for each item, cotton name resolution, how spec 1's templates are styled.
- `research_status_vocabulary.md`: statuses by entity, the token list with contrast ratios, and a suggested tone for each status.
- `research_design_system_patterns.md`: how GOV.UK, Polaris, Carbon, Atlassian and others shape these components, and the common pitfalls.
- `research_accessibility.md`: markup and WCAG notes per component.
- `research_reference_page.md`: options for the reference page.
- The mockups, all screens. Their `_ds/README.md` describes the first-class system and is context, not instruction.
- `claude_plugins/fls-dev/resources/templates_and_cotton.md`, with `cotton/flashcard.html` as the reference implementation.
- Skills: `brand-guidelines`, `domain-glossary`, `fls-dev:frontend-styling`, `fls-dev:icon-usage`, `fls-dev:template`, `ds:frontend-styling`.
