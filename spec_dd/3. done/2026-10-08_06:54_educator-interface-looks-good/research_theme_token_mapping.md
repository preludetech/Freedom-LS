# Research: mapping the design's treatments onto FLS theme tokens, components and icons

Sources read: `.claude/skills/brand-guidelines/{SKILL,visual}.md`, `claude_plugins/fls-dev/skills/{frontend-styling,icon-usage}/SKILL.md`, `freedom_ls/themes/default/static/themes/default/theme.css`, `tailwind.components.css`, `freedom_ls/icons/semantic_names.py`, `freedom_ls/base/templates/cotton/*`, `freedom_ls/panel_framework/templates/cotton/*`, `_base_interface.html`, `educator_interface/.../organisation_switcher.html`, and the design screenshots (learners table, learner detail, cohort detail, create cohort, mobile list, drawer, filter sheet). No design hex, font or px value is carried over below.

## Headline

The design's look is a calm, flat, bordered-card look with small uppercase labels, status chips, thin progress bars and initials avatars. FLS already has all of those as components. The theme can express almost everything. What it cannot express is listed under "Drop".

## Tokens and gotchas that matter here

- Surfaces: `bg-surface` (page, cards, modal), `bg-surface-2` (table header, hover, tinted panel, muted chip), `bg-sidepanel` (the nav surface; aliases surface, themes can repoint), `border-border`, `text-on-surface`, `text-muted`.
- Roles pair with `on-*`: `bg-primary text-on-primary`. Status tints are `-light` and pair with `on-*-light`.
- Only the seven coloured roles have `*-hover`. Surface, border and muted hover: use `hover:bg-surface-2` (the existing pattern).
- No `*-bold` series. `--fls-course-accent-*` is only for `.course-accent-N` / `.course-progress-N`, and is not for educator chrome.
- Radii: only `rounded-sm|md|lg|full` (`--fls-radius-*`). Default to `rounded-md`; cards use `rounded-lg`; chips `rounded-lg`.
- Fonts: `font-sans`, `font-display`, `font-mono` only. Headings, body, `th`, `td`, `label`, `dl` take NO classes (base layer sizes them).
- Shadows: brand principle says surfaces stay flat. Shadow only where a component already has one (`shadow-sm` on inputs, `shadow-xl` in `c-modal`, the side-panel body shadow on mobile).
- Icons: `<c-icon name="...">` with a semantic name only. Sizes `size-3/4/5/6`.

## Mapping table

| Design treatment (in-scope screens) | FLS equivalent | Notes / gotcha |
|---|---|---|
| Page background and card surfaces (white cards on a faintly tinted page) | `bg-surface` + `border border-border rounded-lg` via `<c-panel-card>`; tint via `bg-surface-2` | Do not add a page-tint token. |
| Card with title and a "View" or "Curriculum" link top-right (Cohort details, Module completion, Needs attention, Instructors) | `<c-panel-card title=… >` with `header_action` slot | Already has header border, `px-4 sm:px-6` padding. |
| Hairline borders, 1px dividers between rows | `border-border`, `divide-y divide-border`; table rows already get `border-b border-border` from the base layer | |
| Rounded corners (cards ~12px, inputs ~8px, chips pill-ish) | `rounded-lg` cards, `rounded-md` inputs and buttons, `rounded-lg` chips (`.chip`), `rounded-full` avatars | Not a new radius. Pill status chips: stay with `.chip` shape, do not add `--fls-radius-*`. |
| Drop shadows on modal, mobile sheet, sticky bars | `c-modal` already `shadow-xl`; side-panel mobile body already has a shadow | Do not add shadow utilities to cards or rows. |
| Modal scrim | `.modal-backdrop-host::backdrop` / `.modal-backdrop` (shared) | |
| Create cohort dialog (title + subtitle, bordered header, body fields, footer with hint text left and Cancel / Primary right) | `<c-modal title=… >` with the `footer` slot (`c-button-group variant="space-between"`), `<c-button variant="secondary">` Cancel and `variant="primary"` | Header has no subtitle slot: put the subtitle line as muted text at the top of the body, or drop it. Footer tint (`surface-2`) differs from `c-modal`'s `bg-surface` footer: drop. |
| Form fields: bold-ish label above, input with border and focus ring, helper text under | Base layer styles `label`, `input`, `select`, `textarea`, checkbox (`border-border rounded-md shadow-sm focus:ring-primary`); helper text `text-sm text-muted` | Form fields take no classes. Date inputs in design use mono text: drop (use the default input font). |
| Mobile create cohort sheet, filter and sort sheet, nav drawer | The shared `<dialog class="side-panel-dialog">` machinery: `data-variant="bottom-sheet"` (rounded top corners, 85vh) and `side-drawer` (80%, max 24rem) in `_base_interface.html`; `sidePanel` Alpine controller | Reuse; do not build a second sheet. The design's drag handle on the sheet: no equivalent, drop. |
| Primary button (filled brand colour), secondary (outlined), ghost | `<c-button variant="primary|secondary|ghost">`; small via `size="small"` | Secondary is `border-primary text-primary`, not neutral grey: accept (design's neutral outlined buttons are not expressible without a token). |
| Round floating "+" button on mobile list | none in FLS | Drop, or use the page-level `<c-button variant="primary">` with `add` icon in `panel-page-header` actions. Do not add a FAB component. |
| Status chips (Stalled, Submitted, Retake due, Complete, In progress, Invited, Active) | `<c-panel-status-badge tone="warning|info|error|success|muted" label=…>` (wraps `c-chip` `xs`, `-light` tints) | Map by meaning: Stalled=warning, Retake due=error, Complete/Active=success, Submitted=info, In progress and Invited=muted (or info). Badge owns no domain words; caller passes sentence case. |
| Non-status labels (cohort code, counts) | `<c-chip variant="muted|primary" size="xs">` | |
| Filter pills (Cohort dropdown, "Status: Stalled x", "+ Add filter") | `panel-toolbar` slots (search, filters, actions, applied), `<c-panel-applied-filter>`, `<c-panel-filter-toggle>`, `<c-dropdown-menu>`; add_filter and sheet features already exist in `data-table` | Style via those components only. Pressed state uses check icon + primary, per component. |
| Search input with leading magnifier | `<c-panel-search-field>` (`search` icon, `pl-9`) | |
| Table: small uppercase letter-spaced header, bordered rounded container, comfortable row height, hover row | `<c-data-table>` (base layer `thead bg-surface-2`, `th text-sm font-semibold text-muted`, `td text-sm`, `tbody tr hover:bg-surface-2`, sortable headers with `sort_asc|sort_desc|sort_neutral`) | Uppercase tracking on `th` is not in the base layer: dropping is the safe path; adding `uppercase tracking-wide text-xs` per column would be a one-off (already used by `panel-definition-row` `dt`). Rounded border around the table: wrap in `rounded-lg border border-border overflow-hidden` only if the spec wants it (utilities, no new token). |
| Row checkboxes and "1 selected" bar | `bulk_actions` in `data-table` + `table_selection_bar.html` | Exists. |
| Mobile list rows (name, status chip inline, subtitle, thin progress bar, chevron) | `<c-data-table-card>` through `primary_column`, `secondary_columns`, `card_template`, rows in `ul.divide-y divide-border md:hidden` | Chevron: `next` icon `size-4 text-muted`. |
| Pagination (Previous, 1 2 3, Next) | `<c-pagination>` | Filled current page = primary: component's call. |
| Avatar initials circle (grey/blue tinted), larger on detail header | `<c-panel-avatar-chip name user_id size="md|lg" secondary=…>` (six `color-mix` slots) | Design's single navy filled avatar (user at bottom of nav, instructor): no equivalent, use the avatar chip's tinted slot. Small "SA" / "FC" square org badges: drop. |
| Progress bar (thin rounded, teal fill, % beside, grey track) | `<c-panel-progress-bar percentage label show_label>` (fill `--color-primary`, track `surface-2`, `h-2 rounded-full`, `tabular-nums` %) | Teal fill is not expressible; primary is it. NOT `c-course-progress-bar` (course accent tint is for learner views). |
| Locked / passed / attention per-module row icons (circle-check, circle-alert, padlock) | `complete`/`success`, `warning`/`error`, `locked`, `in_progress`, `not_started` semantic icons | Colour via `text-success`, `text-error`, `text-muted`. |
| Label/value grid with small uppercase caps labels (Learner details, Cohort details) | `<c-panel-definition-list columns="3|4">` + `<c-panel-definition-row label=…>` (`dt text-xs font-semibold uppercase tracking-wide text-muted`) | This already is the uppercase-label treatment. Mono values (dates, ids): drop. |
| Header stats row (Learners 31, Avg progress 78%, Pass rate 91%) | `<c-panel-stat-tile variant="inline|boxed">` / `panel-stat-row` in `panel-page-header` `stats` slot | |
| Page header: title, status badge beside it, code line, actions top-right | `<c-panel-page-header title subtitle>` slots `badge`, `meta`, `stats`, `actions` | Mono ID text: drop mono, use `meta` slot (`text-sm text-muted`). |
| Breadcrumb with back arrow ("< Learners > Name") in a top bar | `<c-breadcrumbs>`; `previous` icon | Top-bar border: existing header has `lg:border-b lg:border-border`. |
| Tabs (Overview, Courses & progress, ... underlined active) | No tab component in cotton. Underline treatment: `border-b-2 border-primary text-primary` active, `text-muted hover:text-on-surface` inactive, container `border-b border-border` | Utilities only, built from existing tokens, on links. Check spec before adding a component; tab content scope is the spec's call. |
| "Needs attention" list with icon, text, action link | `<c-panel-attention-list>` / `<c-panel-attention-row>` | Exists. |
| Callout "One retake remaining" (amber border and tint) | `<c-callout level="warning">` | Out of scope (quick view panel). |
| Instructors list (avatar + name + role) | `<c-panel-avatar-chip secondary=role>` | |
| Desktop left nav: sections with small uppercase labels (Teaching, Administration), items with icon + label + right-aligned count, active item tinted with left accent and bold | Existing sidebar in `educator_interface/interface.html` over `_base_interface.html`'s `bg-sidepanel`. Items: `hover:bg-surface-2`; active: `bg-surface-2 font-semibold text-primary` (+ `border-l-2 border-primary` if wanted) with `aria-current="page"`; counts `text-xs text-muted tabular-nums`; section labels `text-xs font-semibold uppercase tracking-wide text-muted` | No `primary-light`/`primary-soft` token exists: do not add one. `bg-primary/10` is already in use (`btn-ghost` hover) and is the closest tint. Nav counts are a data/scope question for the spec; the design draws them but the spec decides. |
| Organisation switcher (bordered box with name + up/down chevron, list of other orgs) | `partials/organisation_switcher.html` over `<c-dropdown-menu>`, `dropdown` icon, `check` for current, `hover:bg-surface-2` | Restyle only: add `border border-border rounded-md` to the trigger. Org initials badge: drop. |
| Brand block at top of nav ("FC First Class") and user block at bottom (avatar, name, role, gear) | Brand: whatever the shell shows today. User: `<c-panel-avatar-chip>`, `settings` icon | Design brand mark is another product's: drop. User block only if spec says (it is not in the existing nav). |
| Mobile top bar (hamburger, title, count) | Existing content header: `table_of_contents` icon button (`lg:hidden`, `text-muted hover:bg-surface-2`) in `_base_interface.html`; `menu_open` / `menu_close` also exist | Reuse the existing toggle. |
| Mobile bottom tab bar (Dashboard, Cohorts, Learners, More) | none in FLS | Spec decision. If kept, build from utilities (`fixed bottom-0 border-t border-border bg-surface`, items `c-icon` `cohort|user|…` + `text-xs`, active `text-primary`). No new component or token. Icons: Cohorts=`cohort`, Learners=`user`, Courses=`course`, More=`more_options`; Dashboard has no educator dashboard (out of scope), so there is no icon to choose. |
| Typography: bold page title, semibold section titles, small caps labels, body regular, muted secondary text, tabular numerals | Base layer `h1`..`h4`, `text-muted`, `text-sm`, `tabular-nums`, `font-semibold` | Never set heading sizes. Design title is smaller than FLS `h1`: accept FLS scale (or `heading_level` on panel components). |
| Density/spacing (compact rows, 16-24px card padding, gap-4 to gap-6) | Tailwind scale: `px-4 py-4 sm:px-6` (card), `td px-4 py-3`, `gap-x-6 gap-y-4` (definition list), `space-y-6` for page sections | Spacing only from the Tailwind scale. |
| Icons: search, filter, chevron, plus, upload, edit, send, close, sort, grid (dashboard), cohort people, learner person, book (courses), educators, shield (roles), building (org settings), cog | `search`, `filter`, `dropdown`/`expand`, `add`, `download` (no upload), `edit`, none for send/message, `close`, `sort_asc`/`sort_desc`/`sort_neutral`, `cohort`, `user`, `course`, `settings` | Import (upload), Send message, Educators, Roles and permissions, Organisation settings, Dashboard have no semantic icon and their screens are out of scope or not existing. Do not add semantic names for them; omit the icon or keep text-only. |

## Existing components to reuse (do not rebuild)

`c-panel-card`, `c-panel-page-header`, `c-panel-toolbar`, `c-panel-search-field`, `c-panel-filter-toggle`, `c-panel-applied-filter`, `c-data-table` (+ `c-data-table-card`, cell templates, `table_selection_bar`, `table_toolbar` with add_filter and sheet), `c-pagination`, `c-panel-status-badge`, `c-chip`, `c-panel-avatar-chip`, `c-panel-progress-bar`, `c-panel-definition-list/row`, `c-panel-stat-tile/row`, `c-panel-attention-list/row`, `c-panel-empty-state`, `c-modal`, `c-dropdown-menu`, `c-button` / `c-button-group`, `c-breadcrumbs`, `c-callout`, and the shared `side-panel-dialog` (drawer and bottom-sheet variants).

## Where the look tempts a new token (and the alternative)

1. Pale brand tint for the active nav item / selected filter pill / selected row: tempting `primary-soft` or `primary-light`. Use `bg-primary/10` (precedent: `btn-ghost`) or `bg-surface-2` with `text-primary`. `bg-success-soft` is a success-only token, not a template.
2. Teal progress fill, distinct from the brand blue: use `c-panel-progress-bar` (primary fill). Do not use course accents.
3. Navy filled avatars and filled brand-coloured org badge: `c-panel-avatar-chip` slots (tinted). No avatar token.
4. Neutral outlined buttons (grey border, dark text): `variant="secondary"` is primary-outlined; `ghost` is borderless. Accept the difference.
5. Sidebar background different from page background: `--color-sidepanel` already exists but is a theme override, not a spec concern. Leave it at default.
6. Extra radius (pill chips, 12px cards, 16px sheets): stick with `rounded-lg`/`rounded-full`; the bottom sheet already carries its own 1rem top radius.
7. Mono face for ids, dates, counts: `font-mono` exists as a token, but the design uses it decoratively. Drop it except where FLS already uses it.
8. Shadows on cards and a raised sticky bar: drop (flat principle).
9. Warning/amber callout fill and other pastel panel fills: `c-callout`, `-light` tints through `c-chip`.

## Drop list (theme cannot express)

Design's own colours, fonts and radii; mono date/ID styling; mono nav counts font; drag handle on sheets; floating action button; org initials squares and brand logo block; footer tint in modals; shadowed cards; per-status chip pill shape beyond `.chip`; icons for upload, send, shield, building, educators, dashboard.

## References

All findings are from repo files listed at the top. No web sources.

status: ok
