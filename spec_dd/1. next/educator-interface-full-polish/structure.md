# Feature: Educator interface full polish

We need to make sure that the educator interface can reach what it needs to reach, and has a
polished look.

This means we need to make sure that:

- the panel framework is fully functional and exposes the correct APIs
- the panel framework looks good
- the educator interface is implemented.

The app is `freedom_ls/panel_framework`. Singular "panel framework", not "panels framework". The
`Panel` class is one specific thing inside it (see below), so don't use the word loosely.

## Out of scope

New functionality such as learner-facing comms.

## Design

The design lives alongside this idea, in `Educator LMS Interface Design/`. It is a set of
`.dc.html` artboards: eight desktop screens (dashboard, learners table, learner detail, message
panel, cohort detail, roles and permissions, create-cohort modal, bulk-import modal) and eleven
mobile ones, plus a shared `Sidebar` artboard the others import.

This design was created by a third-party tool that is not aware of our data structures or
processes.

We need to make sure our visual elements line up with the design as far as they can. Note also
that this design was based on the "first-class" brand, and uses Phosphor icons and its own
`colors_and_type.css`. Use FLS role tokens and `c-icon` instead. See the `fls-dev:frontend-styling`
and `fls-dev:icon-usage` skills.

Use cotton components or separate template partial files for major widgets so that we can override
them if we ever need to.

## Panel framework functionality

The panel framework exposes an API for specifying the layout of an interface. A host app passes
`panel_framework_view` a `config`: a dict of `ListViewConfig` subclasses keyed by `url_name`. The
educator interface builds that dict as `interface_config` in
`freedom_ls/educator_interface/views.py`. Each `ListViewConfig` is one **section** of the
interface, and carries a `menu_label`, a `list_view` (a `DataTable`) and an `instance_view`.

The dispatcher resolves everything from one path string, using the reserved segments `__panels/`,
`__tabs/` and `__actions/`. HTMX navigation swaps `#main-content` and sends the sidebar,
breadcrumbs and document title back out of band.

### Areas

- **Sidebar** (`partials/sidebar_nav.html`, `#sidebar-nav`)
    - The host app slots its own content above the nav. The educator interface puts the
      organisation switcher there. That switcher is educator-interface code, not framework code.
    - **Sidebar nav** proper: one menu item per section, built by `_build_menu_items`. The active
      section is marked `aria-current="page"` and gets a left accent border. When you are looking
      at an instance, that section grows a collapsible child list holding the current instance, so
      the sidebar shows where you are two levels deep. The expand/collapse toggle is the Alpine
      `sidebarMenuItem` component.
    - Below `lg` the whole sidebar is a modal bottom sheet that slides up over the page behind a
      backdrop, opened from the button next to the breadcrumbs. It is a native `<dialog>` driven by
      the shared `sidePanel` Alpine controller in `_base_interface.html`. That shell belongs to
      `base` and is shared with the learner interface, so changes there hit both.

- **Content header** (`_base_interface.html`)
    - **Breadcrumbs** (`partials/breadcrumbs.html`) on the left, built by `_build_breadcrumbs`:
      root label, then section, then instance. Delegates to the shared `c-breadcrumbs`.
    - The sidebar toggle button, mobile only, sits beside them.
    - **Page title**: an `<h1>` from `partials/page_title.html`, fed by the resolved object's
      `menu_label`.

- **Main content area** (`partials/main_content.html`, `#main-content`): the thing you are actually
  looking at. Either a list view or an instance view.

- **Quick-view drawer**: a drawer that slides in from the right without a backdrop, so the main
  content area stays interactive and an educator can click straight from one row or cell to the
  next and watch the drawer contents swap. Not built yet, and it is **not** a framework `Panel`.
  It is a `role="region"` on desktop and a `role="dialog"` sheet below `md`. It has its own idea at
  `spec_dd/1. next/educator-interface-quick-view-panel/`, which this work should not duplicate.

- **Modal** (`partials/modal_form.html`, wrapping the `c-modal` cotton component): a centred
  dialog over a backdrop. Today every modal comes from a `PanelAction`, so it always holds a form.
  We also want to open one for read-only content, for example rendering a topic's markdown at
  reading width so an educator can check what the learner sees.

### Main area

Two shapes, and the dispatcher picks between them by path depth.

- **List view**: a section's `DataTable`, rendered through `partials/list_view.html` into the
  `c-data-table` cotton component. Any list-level actions (the "Create cohort" button and its
  modal) render above it.

- **Instance view** (`InstanceView`): one object. Renders an `<h1>` with the object's `__str__`,
  an instance actions row under it, then either a flat stack of panels or a tab bar.

- A tab bar can itself contain a stack of panels per tab

#### Data tables

`DataTable` (`tables.py`) is a class with `get_queryset(request)` and `get_columns()`. It gives
every table the same four behaviours:

- **Search**: a single search box above the table, shown only when the table declares
  `search_fields`. Types trigger an HTMX GET after a 300ms debounce and swap the table.
- **Sort**: column headers with `sortable` become links carrying an ascending or descending
  caret. `sort_field` is derived from the column's attribute path.
- **Pagination**: `page_size` defaults to 5, rendered by the shared `c-pagination`.
- **Cells**: each column names a cell template. `base` ships `text`, `link` and `boolean`; the
  educator interface adds its own under `educator_interface/data-table-cells/`. The whole table
  scrolls horizontally inside `c-scroll-table-labels`.

The table's fragment root is `<div id="{{ table_id }}">` and every swap targets it with
`hx-swap="outerHTML"`.

Two known table problems are already written up in
`spec_dd/1. next/panel-framework-tables-and-panel-api- upgrades-and-design/`: sibling tables on one
page share the `?page` / `?sort` / `?search` parameters, and pagination drops any query parameter
outside its allowlist. Both block the filter and bulk-action work the design implies, so that spec
should land first or be folded in.

#### Panels

A `Panel` (`panels.py`) is one card in the main content area. `partials/panel_container.html`
renders it as a `<section class="surface">` with an optional `<h2>` header, the panel body, and a
right-aligned button group of actions below a divider. Three kinds exist:

- `Panel` itself, for hand-written content. The cohort course-progress matrix is one of these.
- `DataTablePanel`, which puts a `DataTable` inside a panel and can refresh just the table when
  HTMX targets it.
- `InstanceDetailsPanel`, a label/value list built from a `fields` list of dot paths, with an
  optional Edit action.

#### Tabs

A `Tab` (`tabs.py`) is a label plus a dict of panels. An `InstanceView` sets `tabs` instead of
`panels` when one object has too much on it for a single scroll. The cohort instance view is the
only current user.

`partials/tab_container.html` renders a horizontal tab bar with a bottom border and an underlined
active tab, `role="tablist"` over `<button role="tab">` elements, then one `role="tabpanel"` per
tab. Only the active tab's panels render on first load. The rest are `hidden` and fetch themselves
over HTMX on first click, showing a `c-loading-indicator` while they wait. The Alpine
`tabContainer` component handles the switch.

#### Actions

A `PanelAction` (`actions.py`) renders as a button. `FormPanelAction` subclasses open a modal
holding a form:

- `CreateInstanceAction`, on a list view. Its modal has both "Save" and "Save and add another",
  and the latter fires an HTMX event that refreshes the table underneath.
- `EditAction`, on an `InstanceDetailsPanel`.
- `DeleteAction`, which shows a confirmation listing what will cascade, or a plain sentence naming
  the blocker when a protected relation stops the delete.

There is a live bug here: `DeleteAction.render` gets a different second argument from each of its
three call sites, so returning one from `Panel.get_actions()` is a guaranteed 500. Written up in
the panel-framework idea linked above.

#### Other elements

- **Loading indicator**: `c-loading-indicator`, used by lazily loaded tabs.
- **Announcer**: `#scope-announcer`, a visually hidden `aria-live="polite"` region the educator
  interface uses to announce an organisation switch.
- **Document title**: `partials/document_title.html`, swapped out of band on HTMX navigation so
  the browser tab keeps up.

### Permissions and access

The framework's hooks, so the spec uses the right names:

- `ListViewConfig.check_access` is the entry point for detail-view authorisation. It runs a
  fail-closed prologue, then calls `authorise_instance`, which denies by default. Don't override
  `check_access`.
- `required_request_attrs` names request attributes that must be resolved and non-None before a
  detail view is served. The educator interface uses it for `request.organisation`.
- `check_access_exempt_reason` marks a config that deliberately isn't authorised yet.
  `CourseConfig` still carries one.
- `PanelAction.has_permission` gates a button.
- `Panel` has **no** permission hook, so panel visibility is all-or-nothing per instance. The
  design's roles-and-permissions screens may need one.
