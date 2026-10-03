# Research: the table layer as spec 1 left it

Read against `idea.md` and the "Educator interface rebuild" section of `spec_dd/1. next/roadmap.md`.
Spec 1 landed at `spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/`. Its
spec explicitly deferred this ground: "The table layer's query-state prefixing, filters, selection
and export (spec 2). This spec keeps `DataTable` and its dotted column `attr` paths. It must not
make spec 2 harder." (`1. spec.md:38`), and "Table column paths and `resolve_url_path_template` stay
dotted until spec 2 rebuilds the table layer." (`1. spec.md:53`). So the whole idea is still current
scope; what follows is what exists to build on and which of the idea's factual claims changed.

## How a table is declared today

`freedom_ls/panel_framework/tables.py` — `DataTable`:
- `page_size = 5` (class attr, still the old default the idea wants raised, `tables.py:11`).
- `search_fields: list[str] = []` — a table opts into search by listing model paths
  (`__icontains`, OR'd), e.g. `LearnerDataTable.search_fields = ["user__first_name", ...]`
  (`freedom_ls/educator_interface/views.py:127`).
- `get_queryset(request)` (abstract, `@staticmethod`) — the base queryset. `get_columns()`
  (abstract, `@staticmethod`) — a `list[dict]`, each dict: `header`, `template` (a cotton cell
  template path), `attr`/`text_attr` (dotted, e.g. `"user.first_name"`, resolved by the cell
  template, not by `DataTable` itself), `sortable`, `url_name`/`url_path_template` for links,
  `header_class`/`cell_class`. No column class exists — columns are plain dicts, not declared
  objects.
- `_prepare_columns()` derives `sort_field` from `text_attr`/`attr` for sortable columns, turning
  `.` into `__` (`tables.py:23-31`) — this is the only place dotted attrs become ORM lookups.
- `get_rows(request, columns, queryset)` (`tables.py:33-58`) reads **`request.GET["search"]`**,
  **`request.GET["sort"]`**, **`request.GET["order"]`** (`"asc"`/`"desc"`), **`request.GET["page"]`**
  — all global, unprefixed names, read directly off the request. No table declares or reads a
  `<key>-...` namespaced param anywhere in the codebase.
- `get_context(request, queryset, base_url, table_id)` assembles the render context: `columns`,
  `rows`/`page_obj`, `sort_by`, `sort_order`, `base_url`, `show_search`, `search_query`, `table_id`.

Panel binding, `freedom_ls/panel_framework/panels.py` — `DataTablePanel` (`panels.py:191-217`):
holds `data_table: type[DataTable]`, scopes rows in `get_queryset(request)` (narrow via
`super().get_queryset(request).filter(...)`), and calls `data_table.get_context(request,
self.get_queryset(request), base_url=self.ctx.base_url, table_id=self.region_id)`. **`table_id` is
always `self.region_id`** — see "id/key" below, there is no separate declared key.

Six `DataTable` subclasses exist today, all in `freedom_ls/educator_interface/views.py`:
`CohortDataTable`, `LearnerDataTable`, `CohortCourseRegistrationDataTable`, `CourseDataTable`,
`CourseCohortRegistrationDataTable`, `CourseLearnerRegistrationDataTable`. None declares a filter,
a selection checkbox column or an export flag. `views.py:79-87` still carries the pre-spec-1 TODO
comment (kept per CLAUDE.md, not deleted): `Checkboxes and bulk actions`, `Export as csv`,
`top level filters (searchable dropdown)` — this is spec 2's own scope note, still in the code.

## Templates: `data_table.html` region rendering

`panel_framework/templates/panel_framework/panels/`:
- `data_table.html` → `_data_table_base.html` → extends `panel.html` (the leaf panel frame) and
  `{% include region_template_name %}` (`_data_table_base.html:4`).
- `data_table_region.html` → `_data_table_region_base.html`, one line:
  `<c-data-table :columns=... :table_id="table_id" ... />` — this **is** the htmx swap fragment.

The cotton component it calls is `freedom_ls/base/templates/cotton/data-table.html` (still in
`base`, not moved). It renders `<div id="{{ table_id }}">...</div>` (`data-table.html:13`) wrapping
search form, `<table>`, and `<c-pagination>`. Sort headers are `<a href="..." hx-get="..."
hx-target="#{{ table_id }}" hx-swap="outerHTML">`.

**Search-text URL-encoding bug: still present, but only in the sort-header links.** The sort
`<a>`/`hx-get` URLs in `data-table.html` (lines 46, 55, 66) interpolate `search_query` raw:
`?sort={{ column.sort_field }}&order=desc{% if search_query %}&search={{ search_query }}{% endif %}`
— no `urlencode`, so a search containing `&`, `+` or `#` breaks the query string. By contrast,
`freedom_ls/base/templatetags/pagination_tags.py`'s `pagination_suffix()` tag (used by
`c-pagination`'s page-number links) **does** call `django.utils.http.urlencode()`
(`pagination_tags.py:43`) — so the same bug the idea describes for "sort links" is confirmed live
today, but the equivalent pagination-link bug has already been fixed since the idea was written.
Only the sort links still need the fix.

**No `{% querystring %}` (Django 6 tag) anywhere.** Grepped the whole tree; no template uses it.
Links are hand-built strings (`?sort=...&order=...{% if search_query %}&search=...{% endif %}`),
not built from a copy of `request.GET`. **No `hx-push-url`/`hx-replace-url` on any table
interaction** — sort, search and page all swap in place with a plain `hx-get`/`hx-swap="outerHTML"`
and never touch the browser URL. The idea's whole "Pushing state" section (search-as-you-type
debounced+replaced, sort/filter/page pushed, reload/share working) is unbuilt, not partially built.
(The search input does debounce: `hx-trigger="submit, input delay:300ms from:#{{ table_id }}-search"`,
`data-table.html:19` — but it replaces the table region via a normal swap, not a history entry.)

`cotton/pagination.html` (`c-pagination`, `base/templates/cotton/pagination.html`) stays in `base`
as the idea says it should. It supports `extra_params` (a pre-joined, already-encoded
`a=b&c=d` string, built with the `join_query` tag) and `page_param_name` (default `"page"`) as an
**escape hatch** for two tables/paginators sharing a page — exactly the manual thread-through the
idea's "Why" section describes needing for every added filter. No call site in the repo uses either
override today (grepped `page_param_name=`, `extra_params=` — none), so the escape hatch is unused
scaffolding, not yet exercised by a real two-table page.

`cotton/data-table-cells/` (`base/templates/cotton/data-table-cells/`): `text.html`, `link.html`,
`boolean.html`. Callers: every `DataTable.get_columns()` in `educator_interface/views.py`, plus
`educator_interface`'s own cell templates (`educator_interface/templates/educator_interface/
data-table-cells/{cohort_courses,cohort_links,learner_courses,progress_check,_link_to_cohort}.html`)
which extend/reuse the base cells. No other app (`content_engine`, `learner_interface`, themes,
`demo_content`) references `data-table.html`, `c-data-table` or `data-table-cells/` — `content_engine/
templates/cotton/table.html` is an unrelated, differently-named component (content rendering, not
the framework table). `c-pagination` is used only by `data-table.html` today; the idea's claim that
it "was also used by the deleted progress matrix" checks out against spec 1's own spec
(`1. spec.md:33,156`: the progress matrix, `CohortCourseProgressPanel`, was deleted in spec 1) — so
that matrix is gone and `c-pagination`'s only live caller now is the table layer itself, plus its
own unit test (`base/tests/test_pagination_component.py`).

## Stale files the idea says to delete

**Already deleted by spec 1.** `upgrade_notes.md`'s `changed_template_paths` front matter lists,
each marked `# deleted`: `educator_interface/templates/educator_interface/partials/
instance_details_panel.html`, `.../partials/list_view.html`, `.../partials/panel_container.html`
(plus `course_progress_panel.html` and several `panel_framework/templates/panel_framework/
partials/*` files). Confirmed by glob: no `list_view.html`, `instance_details_panel.html` or
`panel_container.html` exists anywhere under `educator_interface/`. The only `list_view.html` left
in the tree is the new one, `panel_framework/templates/panel_framework/views/list_view.html` (a
different file, part of the current API). **Idea's "What is settled" deletion item is already done;
nothing left for spec 2 to delete there.**

## The htmx fragment contract and id/key

Confirmed: the outermost DOM node a table swap replaces is `<div id="{{ table_id }}">` in
`cotton/data-table.html`, swapped `outerHTML` — matches the idea's "fragment root stays `<div
id="<key>">`" structurally. **But `table_id` is not a declared stable key.** It is always
`DataTablePanel.region_id` (`panels.py:110-117`): `"panel-" + slug(ctx.base_url)`, where `base_url`
is the panel's URL path built by the framework's path-resolution (`views.py: _bind_root`,
`_resolve_path`). For the top-level list table (`ListViewPanel`, `views.py:161-169`) `base_url` is
the section URL itself (e.g. `/educator/<org>/cohorts`); for a nested table panel (e.g.
`CohortLearnersPanel` under a tab) it is the full `__tabs/.../__panels/...` path. So today's id is
**derived from URL position**, exactly the thing the idea says a table must never use ("Every table
declares a stable key ... never a position", `idea.md:23`). No `DataTable`/`DataTablePanel` declares
a `key` attribute anywhere.

The Playwright tests asserting no nested `section` wrapper on a table swap:
`freedom_ls/panel_framework/tests/playwright/test_data_table_panel_htmx.py`
(`test_data_table_sort_does_not_nest_panel_wrappers`,
`test_data_table_pagination_does_not_nest_panel_wrappers`,
`test_list_view_data_table_swaps_keep_single_container`), using the shared helper
`expect_no_nested_panel` in `freedom_ls/panel_framework/tests/playwright/assertions.py`. The
panel's own frame (`<section data-panel="{{ name }}" ...>` in `_panel_base.html:8`) only carries
`id="{{ region_id }}"` **when the panel has no `region_template_name`** (`_panel_base.html:10`); a
`DataTablePanel` always sets `region_template_name`, so the outer `<section>` has no id and the
`<div id="{{ table_id }}">` inside it is the actual swap target — this is what keeps sort/page
swaps from nesting a second `<section>`. Spec 2 must keep that invariant.

## Two tables sharing a page — bug still reproduces

`CohortDetailsStack` (`educator_interface/views.py:303-309`) is a `PanelStack` with three children
rendered together on one tab: `CohortDetailsPanel`, `CourseRegistrationsPanel` (a `DataTablePanel`
over `CohortCourseRegistrationDataTable`), `CohortLearnersPanel` (a `DataTablePanel` over
`LearnerDataTable`). Both table panels render on the same page/URL simultaneously. Each one's
`DataTable.get_rows` reads the same unprefixed `request.GET["page"]` (and `sort`/`order`/`search`),
so a full page load of `?page=2` pages both tables at once — the exact bug the idea describes, live
and reproducible in the shipped code today, not hypothetical. Their swap targets (`table_id`) do
differ (different `region_id`s from different `base_url`s), so an htmx-driven click on one table's
pagination link only swaps that one table's fragment — but the fragment itself, and a plain GET/
reload of the page, still reads the shared global `page` param for whichever table's queryset it is
scoping, so the bug is in the full-page-load / bookmarked-URL path exactly as the idea says, not in
the htmx-swap path.

## Alpine components and bulk/export

`panel_framework/static/panel_framework/js/alpine-components.js` currently registers two Alpine
components: `sidebarMenuItem` (sidebar expand/collapse) and `listRefresh` (re-fetches a list's table
region on a named `HX-Trigger` event, e.g. after a create action — `panel_framework/templates/
panel_framework/partials/list_refresh.html`). No row-selection, "n selected" bar, filter-sheet, or
mobile-card component exists yet. `alpine-components.js` is also the file spec 3 (dialogs) will add
components next to, per the roadmap's caution that whoever lands second rebases onto the other's JS
file (`roadmap.md:73`).

`actions.py` has no CSV/export concept at all — no `ExportAction`, no CSV-serving code path, no
"declares that it exports" flag on `DataTable`. The bulk-action hook ("consumer registers bulk
actions that receive selected primary keys") also does not exist; `PanelAction`/`FormPanelAction`/
`CreateInstanceAction`/`EditAction`/`DeleteAction` are all single-instance actions bound to one
`ctx.instance`, not multi-row.

## Permission hook contract from spec 1

Tables/table panels must go through the same two hooks every other panel and action uses, not
invent their own:
- `Panel.has_permission(request) -> bool` (default `True`) — whether the panel/table renders at
  all for this request (`panels.py:60-69`). A `DataTablePanel` subclass overrides this the same way
  any other panel would; nothing table-specific exists.
- `SectionConfigBase.authorise_instance(request, instance)` (`views.py:87-95`, deny-by-default,
  raises `Http404`) — instance-level authorisation for a `ListViewConfig`'s detail view, e.g.
  `CohortConfig.authorise_instance` checking `cohorts_visible_to(...)`. Row-scoping for a table
  itself is done in `DataTablePanel.get_queryset`/`DataTable.get_queryset`, filtered by whatever the
  panel's caller passes in (e.g. `learners_visible_to(request.user, organisation)`), not by a
  separate table-level permission hook.
- `PanelAction.has_permission(request, instance)` — per-action, e.g. `DeleteAction` checks
  `request.user.has_perm(f"{app_label}.delete_{model_name}", instance)`.

The roadmap is explicit that spec 5 changes this contract ("Spec 5 changes the role definitions and
the framework's permission hook contract, so 2 and 3 should not invent their own permission checks",
`roadmap.md:73`) — so spec 2's row-selection/bulk-action hook and export hook should call through
`has_permission`/`authorise_instance` as they exist today, and expect spec 5 to touch that surface
later, not build a parallel check.

## Default page size

Still `5` (`tables.py:11`), unchanged since spec 1 (spec 1's spec explicitly left the table layer
alone apart from the `get_rows`/`get_context` signature change). The idea's "moves from 5 to
something sensible ... declared per table" is still fully open work for spec 2.

## Idea claim → still true / changed

- **"Sibling tables on one page share `?page`, `?sort` and `?search`"** → still true, reproduces
  today via `CohortDetailsStack`'s `CourseRegistrationsPanel` + `CohortLearnersPanel`.
- **"Pagination links rebuild the query string from a fixed set of names ... any filter added has
  to be hand-threaded through an escape hatch"** → still true; the escape hatch (`c-pagination`'s
  `extra_params`/`page_param_name`) exists but is unused by any real call site.
- **"The sort links also interpolate the search text into a URL without encoding it"** → still true
  for the sort headers in `data-table.html`. Narrower than it reads, though: the equivalent
  pagination-link path was already fixed (uses `urlencode` via `pagination_suffix`) since the idea
  was written — only the sort-header links still have the bug.
- **"`cotton/data-table.html` and `cotton/data-table-cells/` move to `panel_framework`"** →
  unchanged, still in `base`, still to do.
- **"`cotton/pagination.html` stays in `base`; it was also used by the deleted progress matrix"** →
  the progress matrix is confirmed deleted (spec 1); `c-pagination` confirmed still in `base` and
  now used only by the table layer.
- **"The unreferenced byte-identical copies of `list_view.html` and `instance_details_panel.html`
  under `educator_interface/partials/`, and the stale `panel_container.html` ... deleted if spec 1
  has not already done so"** → spec 1 already did this. Nothing left to delete here.
- **"Every table declares a stable key ... never a position. Its DOM id and query parameters derive
  from it"** → not built. Today's `table_id`/DOM id (`region_id`) is derived from URL position
  (`base_url`), and query params (`sort`, `order`, `page`, `search`) are global, unprefixed names
  with no per-table key at all. This is the idea's central ask, still fully open.
- **"Sort, filter and page changes push the URL. Search-as-you-type replaces it, debounced"** → not
  built. Search is debounced (300ms) but performs a normal in-place swap; nothing pushes or replaces
  the browser URL anywhere in the table layer today.
- **"Declared filters ... Row selection ... Export hook"** → none exist; `DataTable` has no filter
  declaration mechanism, no checkbox/selection column, no export flag. `actions.py` has no bulk or
  CSV concept. Confirms the idea's scope, not a stale claim.
- **"Mobile: stacked cards below `md`, sort/filter in a sheet"** → not built; `data-table.html`
  renders one `<table>` unconditionally, no responsive stacked-row variant, no Alpine sheet
  component.
- **"The table's fragment root stays `<div id="<key>">` swapped with `outerHTML`. Playwright tests
  keep asserting no nested `section` wrapper."** → structurally true today (`<div id="{{ table_id
  }}">`, `outerHTML`, tests in `panel_framework/tests/playwright/test_data_table_panel_htmx.py`) —
  but `<key>` is currently a position-derived id, not a declared key, so spec 2 must keep the
  `<div id=...>`/`outerHTML`/no-nested-`<section>` invariants while changing what the id is derived
  from.
- **"Default page size moves from 5 to something sensible"** → still 5, unchanged, fully open.
- **`{% querystring %}` limits mentioned in the resource doc** → not applicable yet; the tag isn't
  used anywhere in the current table code, so there's nothing "in use" to find the limits of — the
  resource doc's discussion is prospective, for spec 2 to apply.

status: ok
