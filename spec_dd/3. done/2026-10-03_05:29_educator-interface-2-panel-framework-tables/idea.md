# Panel framework tables

Spec 2 of 12 in the educator interface rebuild effort. Read the "Educator interface rebuild"
section of `spec_dd/1. next/roadmap.md` first. It holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Finish the framework's data table. Move its markup out of `base`, and give every table its own query-string namespace so several tables can share a page. Add declared filters that survive pagination, row selection with a hook for bulk actions, and a CSV export hook. Below the `md` breakpoint, render rows as stacked cards.

## Why

Two behaviours block everything the mockups' learner table needs, and both are live in the code
spec 1 left.

- `DataTable.get_rows` reads unprefixed `search`, `sort`, `order` and `page` off `request.GET`.
  `CohortDetailsStack` renders two `DataTablePanel`s on one tab, so a full-page load of `?page=2`
  pages both.
- Links are hand-built strings over a fixed set of names. Any filter added to a table would have
  to be hand-threaded through `c-pagination`'s `extra_params` escape hatch at every call site. The
  sort-header links in `cotton/data-table.html` also put the search text into the URL without
  encoding it. The pagination links were fixed already.

Spec 1 deferred exactly this scope to spec 2. The TODO in `educator_interface/views.py` (checkboxes
and bulk actions, CSV export, top-level filters) is this spec's work and can go once it lands.

The table layer is built locally. `research_tables2_viability.md` costs django-tables2 against
FLS's rendering, htmx and multi-tenancy constraints and finds the two missing behaviours take
about twenty lines each to build locally. The library would need an FLS-owned template copy, a
mixin ban enforced by test, and a hard dependency. Copy only its query-string prefix convention. Do
not reopen this without new evidence.

## What is settled

**Location.** `cotton/data-table.html` and `cotton/data-table-cells/` move to `panel_framework`.
Cotton's component namespace is flat, so call sites and theme overrides do not notice.
`cotton/pagination.html` stays in `base` as a general component. The table stops using
`pagination_suffix`/`join_query` and builds its page links like every other link (below).

**Per-table key.** Every table declares a stable key (`learners`, `registrations`), never a
position. Today the DOM id is `DataTablePanel.region_id`, which is derived from the panel's URL
path, and that changes. Keys match `[a-z0-9_]+`, so `<key>-sort` reads unambiguously and no key
can collide with another key plus a suffix. Two tables that can render on the same page may not
share a key. That is enforced when the configuration loads, with `ImproperlyConfigured`, the way
`sections_by_url_name()` already rejects duplicate section names. A future top-level query
parameter (spec 3's possible `?peek=`) must not collide with any table's prefix.

Everything derives from the key: the DOM id and the query parameters `<key>-sort` (leading `-` for
descending), `<key>-page`, `<key>-q` for search, and `<key>-<filter>` for each declared filter. A
table reads only its own keys.

**Building links.** Python on the table computes a small changes dict per link, for example
`{"learners-sort": "-name", "learners-page": None}` for a sort header. The template merges it with
`{% querystring request.GET changes %}`. The template passes `request.GET` explicitly, because a
positional dict on its own replaces `request.GET` instead of merging with it and would drop every
other table's state. Dashed keys work as dict keys. `None` removes a key, and a list sets a repeated key. Every
sort, filter and search change includes `"<key>-page": None`, so resetting the page falls out of
link building instead of being a separate code path. The tag URL-encodes every value, which fixes
the search-text bug. `Paginator.get_page` already clamps a stale or invalid page, so it stays.

**Pushing state.** Sort, filter and page changes push the URL. Search-as-you-type replaces it,
debounced with `hx-trigger="input changed delay:300ms, search"` and cancelled in flight with
`hx-sync="this:replace"`. The native `search` event avoids the `eval` that htmx's own active-search
example needs for its key filter.

A nested table's htmx request has to go to its panel sub-URL (`…/__panels/<name>`) so that
`panel_framework_view` can dispatch it. That sub-URL must never reach the address bar, so the
`hx-push-url` attribute cannot be used. The server sets `HX-Push-Url` and `HX-Replace-Url` response
headers carrying the real page URL with the merged query string. `PanelContext.base_url` is the
panel's own path segment, so the page URL has to be carried down to nested panels. The pushed URL renders the full page on a plain GET, so reload and share work.

The search form and the mobile filter-and-sort form carry the rest of the current query string as
hidden inputs, which covers the other tables' state and this table's own sort and filters. They
submit to a URL with no query string. That way a JS-off submit and the htmx request build the same
URL, and htmx, which appends form values rather than merging them, never sees a duplicate key. A
submit resets only the table's page.

**History.** Spec 1 set `historyCacheSize: 0` and `historyRestoreAsHxRequest: false`. Back and
forward through a pushed table URL are therefore a full-page server round trip. No stale fragment
is restored, and selection resets. The spec adds one Playwright test: sort or page, go back,
and check that the address bar and the rendered table agree.

**Announcement and focus.** A table swap announces its result ("Showing 1–25 of 143, sorted by
Name") through the existing `announcer.html` out-of-band partial, as `tab_response.html` does for
tabs. Unlike tabs, every control that triggers a swap sits inside the swapped root, so the focused
element is destroyed on each swap. After a table swap, focus moves to a `tabindex="-1"` anchor at
the top of the new fragment.

**Declared filters.** Filters are a small purpose-built class, not Django form fields. A table
declares them with `get_filters()` beside `get_columns()`. There are three kinds:

- A choice filter has static `(value, label)` pairs, or `get_choices(request)` when the choices
  must be scoped, as a cohort list must be scoped to the educator's organisation.
- A related-object filter is a choice filter whose choices come from a scoped queryset.
- A boolean toggle ("show inactive") narrows the rows when present and means "don't care" when
  absent.

Scoping uses the same request-taking shape as `DataTable.get_queryset(request)`. Choice filters
take several values (`learners-status=stalled&learners-status=invited`). A value that does not
validate against the declaration is dropped silently, as `CompletionListFilter` does in
`site_aware_models/admin_filters.py`. A filter with a fiddly value can delegate to a single
`forms.Field.clean()` without the table adopting a `Form`.

The validated applied-filter state is one small serialisable value. It narrows the rows, renders
the toolbar, rides along in the export URL and goes into the bulk-action payload. The toolbar
follows screen 02's three filter states:

- Not added: reachable only through "Add filter".
- Added but unset: a dropdown pill such as "Cohort". A table can choose to always show one.
- Set: a chip reading "Status: Stalled, Invited" with a remove control.

A "Clear all" sits beside the chips.

**Narrowing rows once.** Search, sort and declared filters narrow rows through one path that the
paginated view, the export and bulk-action selection all share. Pagination is the only step the
last two skip.

**Row selection.** A checkbox column and a tri-state header checkbox (`aria-checked="mixed"`). Each
checkbox is named for its row. An "n selected" bar appears when anything is checked and is an
`aria-live="polite"` region. The consumer registers bulk actions. The payload has one contract with
two modes:

- `{"mode": "keys", "keys": [...]}` holds the checked primary keys on the rendered page.
- `{"mode": "all_matching", "query_string": "<the table's own prefixed params>", "excluded":
  [...]}` is for "select all matching". `excluded` lists rows deselected afterwards.

This spec ships `keys` and the `mode` field. Spec 8 adds `all_matching` without a second contract.
An action handler never sees the payload or raw keys. The framework resolves the selection to a
queryset that is re-scoped and permission-filtered through the table's own scoping at submit time.
The confirmation count ("This will affect 312 learners") comes from the same resolution, so it
cannot disagree with what the action does. A server-side cap limits how many rows one request may
act on.

Selection belongs to the rendered page. It lives in Alpine state, clears on any `<key>-*` change
(page, sort, filter, search) and is never in the URL. The checkboxes and action buttons form a real
`<form>`, so `keys` mode works with JavaScript off. The search form cannot nest inside it, so its
controls are linked with the `form` attribute instead. Confirmation is a real intermediate step, the
confirm-then-act shape `DeleteAction` already uses, not a modal only. This spec ships the mechanism
with one stub action under test. Spec 8 registers the first real actions.

**Export hook.** A table exports by declaring `get_export_columns()`, a list separate from
`get_columns()`. Each entry has a header and either a dotted path, resolved with the same
`getattr_str` the cells use, or a small callable. A column can therefore be export-only (email),
screen-only (checkboxes, action buttons, cells with no plain value) or both. The export is served
at the table's own URL with `?<key>-export=csv`, so the panel's existing scoping, permission check
and query state apply unchanged, and one place decides who can read a table's rows. It honours
search, sort and filters, and skips pagination.

The response streams, using Django's `csv.writer` over `StreamingHttpResponse`. It passes
`chunk_size` to `.iterator()` so prefetches still apply. Cells get the same formula-injection
escaping and the same UTF-8 BOM as `site_aware_models/admin_exports.py`. That is one
implementation, moved wherever both apps can import it, not a copy. Filenames are built from the
table key, a URL-safe scope slug and an ISO date, so they stay ASCII. Spec 10 uses the hook for the
roster.

**Mobile.** Below `md`, rows render as stacked cards per `Educator Mobile Learners` screen M03. The
server renders both markups inside the same fragment root: a real `<table>` for `md` and up, and a
list of cards below. Responsive display utilities switch between them, so no JavaScript and no
second request are involved. A restyled `<table>` with `data-label` would risk table semantics and
still need per-cell labels.

Columns declare a primary, secondary or `md`-only grouping, so simple tables get a default card. A
table whose card is denser can supply its own card-row template, the way it already supplies cell
templates. The learner card folds cohort into a status-specific meta line and drops the row menu
for a chevron. Every row-menu action must stay reachable from the detail page the card opens.

Sort and filters move into a "Filter and sort" sheet (M04). It is a real GET form using the same
query parameters, with sort as a radio group and choice filters as toggle chips. It has a plain
"Show results" submit and a "Reset". The sheet chrome uses the `bottom-sheet` variant of the
existing side-panel `<dialog>` in `_base_interface.html`, or spec 3's shared dialog if that has
landed. It does not become a third dialog implementation. The two specs share Alpine's JS file,
and whoever lands second rebases.

Selection works on cards too. Each card gets a leading checkbox with a 44×44px tap target, always
visible and never a long-press. A "Select all on this page" toolbar control stands in for the
header checkbox. The "n selected" bar is fixed to the bottom of the screen. Spec 1 kept the sidebar
sheet and added no bottom tab bar, so nothing there competes for the space.

**Invariants kept.** The table's fragment root stays a `<div>` whose id comes from its key, swapped
with `outerHTML`. The panel's outer `<section>` carries no id when `region_template_name` is set.
The Playwright tests in `panel_framework/tests/playwright/test_data_table_panel_htmx.py` keep
asserting, through `expect_no_nested_panel`, that a swap never nests a `section`. Every URL a table
can push renders a full page on a normal GET with JavaScript off. Tables check permissions only
through spec 1's hooks (`Panel.has_permission`, `authorise_instance`, the table's scoped
`get_queryset`). Spec 5 changes that contract, so this spec invents no checks of its own.

**Page size.** The default moves from 5 to 25, and a table can declare its own.

## Open until the spec

- How the page URL reaches nested panels. Either a new `PanelContext` field set at `_bind_root`, or
  stripping the `__panels`/`__tabs` segments off `base_url`.
- Whether the key is declared on `DataTable` or on `DataTablePanel`. The same `DataTable` could in
  principle appear twice on a page under different keys.
- The server-side cap on rows per bulk request.

## Out of scope

- The bulk actions themselves, "select all matching" UI, the CSV import and the roster export's
  content. Specs 8 and 10.
- Column-level permissions. If a role must not see a column, the consumer declares a different
  table.
- A viewer-controlled column picker (screen 02's icon), counts on filter choices, a live result
  count on the mobile sheet's button, and shift-click range selection.
- Export as a permission separate from viewing (spec 5), and export as an audited event (spec 11).
  The query-flag URL accommodates either.
- Whether authenticated pages should be bfcache-eligible. It is still open from spec 1 and is not
  this spec's to settle.

## Resources

- `research_current_table_layer.md` covers the table layer as spec 1 left it: declarations,
  templates, callers, the fragment contract and permission hooks.
- `research_query_state_and_history.md` gives the `{% querystring %}` source behaviour, the
  `HX-Push-Url` reasoning, history under spec 1's config, and announcement and focus.
- `research_filter_declarations.md` has screen 02's filter states and the reference designs
  (admin `SimpleListFilter`, django-filter, Wagtail, Filament) behind the filter class.
- `research_row_selection_bulk_actions.md` covers the payload modes, re-scoping, JS-off behaviour,
  accessibility and mobile selection.
- `research_csv_export.md` covers streaming, formula injection, Excel compatibility, export columns
  and the URL design.
- `research_mobile_stacked_rows.md` describes M03 and M04 exactly and compares the rendering
  techniques.
- `research_tables2_viability.md` explains why the table layer is built locally.
- `../educator-interface-full-polish/htmx-modal-drawer-url-state.md`, section 3.
- Mockups: `../educator-interface-full-polish/Educator LMS Interface Design/Educator Learners.dc.html`
  screen 02, and `Educator Mobile Learners.dc.html` screens M03 and M04.
- Skills: `fls-dev:template`, `ds:htmx`, `fls-dev:alpine-js`, `fls-dev:frontend-styling`,
  `fls-dev:playwright-tests`, `fls-dev:multi-tenant`.
