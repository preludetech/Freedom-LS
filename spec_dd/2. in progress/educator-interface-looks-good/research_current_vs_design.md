# Research: current educator interface vs Claude Design (screen-by-screen)

Sources read: `freedom_ls/educator_interface/views.py`, `.../templates/educator_interface/{interface.html,partials/organisation_switcher.html,panels/dashboard.html}`, `freedom_ls/base/templates/_base_interface.html`, `freedom_ls/panel_framework/templates/**` (cotton components, panels, views, partials), `freedom_ls/panel_framework/tables.py`, `docs/product/educator-interface.md`, `docs/product/screenshots/educator_*.png`, and the design screenshots in `design_screenshots/`. I did not read `design_source/*.dc.html`. The screenshots were enough for structure.

Caveat: `docs/product/screenshots/educator_learners_list.png` and `educator_panel.png` look stale. They show tables and underlined links with no `panel-card` chrome. Treat them as a rough baseline only. The templates are the source of truth.

## 1. What the educator interface is today

**Routing and sections**
- One view, `interface()` in `views.py`, serves `/educator/<organisation_slug>/<path_string>`.
- `interface_config` has one `NavGroup("Teaching", ...)` with Dashboard, Cohorts, Learners and Courses.
- Dashboard is a placeholder `Panel`: the text "On-screen reporting ... arrives in a later release" (`educator_interface/panels/dashboard.html`).
- There is no Administration group (no Educators, Roles & permissions, Organisation settings).

**Shell** (`educator_interface/interface.html` extends `_base_interface.html`)
- Site header bar (the First Class blue header, not part of the design) sits above a two-column grid: sidebar and `#interface-main`.
- The sidebar is a single `<dialog class="side-panel-dialog">` driven by the `sidePanel` Alpine controller.
  - Desktop (lg and up): docked, sticky, `bg-sidepanel`, 16rem wide.
  - Below lg: modal overlay. The educator interface does not override `sidebar_presentation`, so it uses the default `bottom-sheet`, not a left drawer. A `side-drawer` variant already exists in the base CSS.
- Sidebar content, in order:
  - `organisation_switcher.html`: a `c-dropdown-menu` showing the organisation name and a dropdown icon. It becomes static text when only one organisation is accessible.
  - `panel_framework/partials/sidebar_nav.html`: a group `<h2>` heading, then links with an icon, a label and an optional count. The active item gets `bg-surface-2` and a left `border-primary` border. Instance sub-items expand and collapse.
  - A user block at the bottom of the sidebar content: full name and email. It is not pinned to the sidebar bottom, and it has no avatar and no settings icon.
- Main content header (`_base_interface.html`):
  - Breadcrumbs on the left.
  - On mobile, a `table_of_contents` icon button on the RIGHT of the breadcrumbs opens the sidebar.
  - A `page_title` region sits underneath, deliberately empty for the educator interface.
  - A desktop-only bottom border.
- There is NO mobile top bar showing the organisation name or title, and NO bottom tab bar. The nav on mobile is only reachable through that icon button.

**List views** (`views/_list_view_base.html`)
- `c-panel-page-header` shows the h1 and a right-aligned action button group. Below it is the data-table panel inside a `c-panel-card`.
- Cohorts has a "Create Cohort" `CreateCohortAction` (see section 3).

**Data tables** (`cotton/data-table.html`, `partials/table_toolbar.html`, `partials/table_sheet.html`, `cotton/data-table-card.html`)
- Desktop: a plain `<table>` with a sortable-header link and icon, link cells, and pagination below.
- Search is a plain `type=search` input. The toolbar also supports filter chips, "Add filter", "Clear all", "Sorted by" text and export, all driven by `DataTable.get_filters()`.
- `LearnerDataTable` and `CohortDataTable` declare NO filters (`get_filters()` returns `[]`), and the learners table has no `card_template`.
- Below md: a card list. The primary column is bold, and the secondary columns are a muted wrapped line. This is the default; no `card_template` is set.
- Below md: an existing Filter / Sort sheet. It is a bottom-sheet `<dialog>` with a chip-style multi-select fieldset, a `select` widget, and sort radio rows with a check icon. Its footer buttons are Cancel and "Show results", and its heading row has "Reset".
- On the learners table, the mobile toolbar renders only a "Sort" text button. The "Filter" button is guarded by `{% if toolbar %}` and there are no filters.
- Learners table columns: First Name (sortable, link), Last Name (sortable, link), Email, Cohorts (links), Registered Courses. Column cells render through `cotton/data-table-cells/*`.

**Learner detail** (`LearnerInstanceView` with `LearnerPanelStack`)
- `c-panel-page-header` shows the learner's `str()` as the title.
- Two stacked `panel-card`s:
  - "Details": a `panel-definition-list` of First name, Last name and Email.
  - "Cohorts": a `DataTablePanel` that reuses `CohortDataTable`.
- There are NO tabs, avatar, status badge, ID, edit button or message button.

**Cohort detail** (`CohortInstanceView` with `CohortTabSet`)
- The page header holds the Edit and Delete actions. Edit is inline, through `CohortForm`, which has the single field `name`.
- `TabSet` has ONE child ("details", titled "Details") on a `_tab_set_base.html` underline tab nav. It contains three `panel-card`s: Details (name), "Course Registrations" and "Learners".
- The product doc mentions a Course Progress matrix tab, but it is not wired into `CohortTabSet` in `views.py`. Do not design around it.

**Create cohort** (`CreateCohortAction`, `partials/modal_form.html`, `cotton/modal.html`)
- It EXISTS: a "Create Cohort" button opens a `c-modal` with one `name` field and a submit button. On success it redirects to the new cohort (event `cohortCreated`).
- The modal is centred on all breakpoints: `rounded-lg`, a header with a border and a close icon, and a footer `c-button-group`. There is no bottom-sheet or full-height variant on mobile.

**Shared components already available**
- Cards, tables and layout: `panel-card`, `panel-page-header`, `panel-definition-list` and `panel-definition-row`, `panel-toolbar`, `panel-search-field`, `panel-filter-toggle`, `panel-applied-filter`, `panel-empty-state`, `panel-skeleton`.
- Display: `panel-avatar-chip`, `panel-status-badge`, `panel-progress-bar`, `panel-stat-row`, `panel-stat-tile`, `panel-attention-list` and `panel-attention-row`.
- Other: `c-chip`, `c-button`, `c-dropdown-menu`.
- The stat, progress, avatar and badge components are NOT used by any educator screen today. The data to feed them does not exist in educator queries (see the out-of-scope list in section 2).

## 2. Screen-by-screen gap analysis

Legend for "Lands in": **PF** = shared `panel_framework`/`base` code, so every panel user is affected. **EI** = `educator_interface` only.

### Desktop

| Design screen | What exists to restyle | Concrete visual and layout differences | Lands in |
|---|---|---|---|
| Left nav + org switcher (`Sidebar.dc.html`, `sidebar__264.png`) | Docked sidebar with the org dropdown, `sidebar_nav.html` and the user name/email block | Design is a full-height column with a brand row at the top, a small caps "Organization" label, and an outlined, bordered org switcher. Nav items are denser, with a rounded filled active state, a primary-tint active colour and icons (the design draws a count pill on the right). The user block is pinned to the bottom, separated by a border. Today the switcher is a borderless, hover-only text button, nav groups are indented with a left-border active marker, and the user block floats directly under the nav. | Nav item and group style: PF (`sidebar_nav.html`). Switcher and user block: EI. The container is in `_base_interface.html` (PF, shared with the learner interface). |
| 02 Learners table | Learners list page header, search, sortable table | Design has the toolbar and table as one card (rounded border) with an uppercase small-caps header row. A page-header row carries a breadcrumb and the actions. The search box has a leading icon. Pagination is a footer under the card. The learner cell is a two-line name/email block. Today the table is flat, link cells are underlined, the header has a grey band, and search is a plain input above it. | Table, search and card chrome: PF (`data-table.html`, `table_toolbar.html`). Learner cell composition: EI (a new cell template next to the existing `data-table-cells/*.html`). |
| 03 Learner detail: header, tabs, sections | Page header with the learner `str()` title; two stacked cards (Details, Cohorts) | Design has a header block with a large avatar, name, email and ID/status badges, then a tab strip, then a details card in a multi-column labelled grid. Today it is a title only and the definition list is a stacked label/value layout. | Page header: PF (`panel-page-header`) and EI (the badge/meta slots are available). Definition grid: PF (`panel-definition-list`). Tabs: see section 3. |
| 05 Cohort detail | Header with Edit/Delete, one tab, Details/Course Registrations/Learners cards | Design has the cohort name as a large title, a status chip and code line above it, a stat strip on the right, and a tab strip. A two-column body has a main column of cards and a narrow right column of side cards. Today it is a single column of stacked cards. The tab nav already has an underline style close to the design. | Header and tab styling: PF (`panel-page-header`, `_tab_set_base.html`). Column layout of the stack: PF (`_panel_stack_base.html`) or EI. |
| 07 Create cohort dialog | Existing modal with the `name` field | Design has a larger, rounded dialog with a title and subtitle, labelled inputs with a stronger focus ring, and a footer bar with Cancel and a primary Create button. Today it is a plain bordered modal with one field. | PF (`cotton/modal.html`, `partials/modal_form.html`, form widgets) |

### Mobile

| Design screen | What exists today | Differences | Lands in |
|---|---|---|---|
| M01 top bar + bottom tab bar | Header with breadcrumbs and a right-side nav icon button; no tab bar | Design has a top bar with a left hamburger, the org name or screen title, and right-side search and bell icons. Fixed bottom tab bar: Dashboard, Cohorts, Learners, More. Neither the top bar nor the tab bar exists as a component. | Top bar: PF (`_base_interface.html` header) or an EI override. Tab bar: new markup (see section 3). |
| M02 nav drawer | Sidebar `<dialog>` as a bottom sheet | Design is a left-side drawer with a close X, the org switcher expanded inline into a list, and the same nav groups as desktop. The `side-drawer` variant already exists. | EI (one block override, `sidebar_presentation`) plus switcher: EI |
| M03 learners list | Card list (default `data-table-card.html`), search, Sort text button | Design has a larger search field, a row of applied-filter and Filter/Sort chips, and rows with an avatar, name, status badge, subtitle, thin progress bar and chevron. A floating add button sits bottom-right. Today it is a text-only card with a bold name and a muted wrapped line of columns. | Card shell: PF. Content: EI via `card_template` (supported hook on `DataTable`). |
| M04 filter and sort sheet | Existing sheet (`table_sheet.html`) | Design has a grabber handle, header with Reset, small-caps section labels, status chips, a cohort select, sort rows with a check, and a primary full-width button with a result count in its label. Existing sheet structure matches. Differences are styling, spacing, a "Show N learners" label vs "Show results", and a Sort-only mobile bar on learners because no filters are declared. | PF (`table_sheet.html`, `table_toolbar.html`) |
| M05 learner detail | Title plus two cards | Design has a top bar with a back arrow and a kebab, avatar, name, ID and badge, a tab strip, cards, and a sticky bottom action bar. | PF + EI (as desktop) |
| M08 cohort detail | Title, tab, three cards | Design has a back-arrow top bar, status chip, code, title, an inline stat strip, tabs and stacked cards. | PF + EI (as desktop) |
| M10 create cohort sheet | Centred `c-modal` | Design is a full-height sheet with a Cancel / title / Create header bar and stacked fields. | PF (`modal.html`) |

### Design elements with NO functionality behind them (exclude from the spec)

The design draws these. None of them exists in the educator interface today, so they are out of scope per `design.md`.

- Sidebar and nav:
  - The Dashboard content (stat tiles, "Needs attention", "This week").
  - The "Administration" nav group: Educators, Roles & permissions, Organization settings.
  - Nav counts. `sidebar_nav.html` supports `item.count`, but `NavGroup` and the configs set none. Adding counts would be new queries.
  - The brand mark and "EDU" tag row, and the user avatar and settings gear. The design is not on the project's theme.
  - Per-organisation initials chips in the switcher.
- Learners table:
  - The Progress bar column.
  - The "Last active" and Status columns, and the status badges.
  - Row checkboxes, bulk actions and row action menus. The bulk-action framework exists, but the learners table does not use it.
  - The "Import" and "Add learner" buttons. Learner add and import are admin-only per `docs/product/educator-interface.md`.
  - The Cohort filter, the "Status: Stalled" filter, "Add filter", and the column-picker button. `LearnerDataTable.get_filters()` is empty. Building any filter would be new functionality.
  - Sorts other than First name and Last name: "Last active", "Progress", "Enrolment date".
  - The "1 selected . showing 8 of 31" summary line, and numbered page links styled as in the design (the pagination component exists but is not styled like this).
- Learner detail:
  - Avatar, Learner ID (LRN-...), Retake due badge, Edit button, Send message button.
  - Tabs Courses & progress, Assessments, Certificates, Activity.
  - The Learner details grid fields Enrolled, Role, Licence held, Location, Instructor, Target completion, Last active.
  - The Module progress card.
  - The quick-view panel (out of scope per `design.md`).
  - M05 sticky Message and chart buttons, the kebab, and the "Course completion" card and warning callout.
- Cohort detail:
  - The Active status chip, cohort code, stat strip (Learners, Avg progress, Pass rate, Closes).
  - Enrol learners button (membership management is admin-only).
  - Tabs Learners (with count), Curriculum, Assessments, Schedule, Settings.
  - Fields Course, Delivery, Lead instructor, Starts, Ends, Capacity, Regulator, Pass mark, Attempts allowed.
  - The Needs attention, Instructors and Compliance cards, and the Module completion progress card.
- Create cohort:
  - Fields Course, Start date, End date, Lead instructor, Capacity, "Copy settings" checkbox, subtitle copy and footer notice copy. `CohortForm` has only `name`.
- Mobile general:
  - The bottom tab bar's "More" overflow and the Dashboard tab as designed, the search and bell icons in the top bar, and the floating add button.
  - The Filter/Sort result count in the button label ("Show 3 learners") unless the table already knows the count.

## 3. Design screens with no current counterpart

| Design screen | Status |
|---|---|
| Create cohort dialog (07, M10) | A create-cohort flow EXISTS (`CreateCohortAction`: modal, `name` only). Only the restyle is in scope. The M10 full-height sheet presentation does not exist, so the modal would need a sheet variant. |
| M04 filter and sort sheet | The sheet EXISTS in the framework (`table_sheet.html`). On Learners it shows only Sort, with no filters, so the filter half of the design has no content. |
| Mobile top bar + tab bar (M01) | NO counterpart. Neither the mobile top bar nor the bottom tab bar exists. A top bar is a restyle of the existing mobile header (hamburger, title). A bottom tab bar is new navigation chrome. It would have to reuse `interface_config` (Dashboard, Cohorts, Learners, Courses) and cannot invent a "More" tab without a destination. |
| Learner detail tabs (03, M05) | NO counterpart. Learner detail is a `PanelStack` with no `TabSet`. A tab strip would need a `TabSet` with at least two real tabs (for example Details and Cohorts), which is a structural change. Cohort detail already has a single-tab `TabSet`, where a one-tab strip looks odd. |
| Learner and cohort header "stats", avatar, badges | No data sources. `panel-stat-row`, `panel-avatar-chip` and `panel-status-badge` exist. An avatar chip could be fed from the learner's name alone (initials), but nothing else could. |
| Right-hand side column on cohort detail (05) | The side cards (Needs attention, Instructors, Compliance) have no content. Only the layout idea applies. |

## 4. Where changes land

**Shared `panel_framework` / `base` (affects every panel user, including Courses and any future concrete projects)**
- `sidebar_nav.html`: item density, active-state style and group heading style. Any panel interface using it changes.
- `_base_interface.html`: the content header (mobile top bar), the sidebar presentation, and the sticky and pinned sidebar regions. It is also the shell for the learner interface course TOC (`learner_interface/.../course_toc_header.html` uses `sidePanel`), so edits risk the learner side.
- `data-table.html`, `table_toolbar.html`, `table_sheet.html`, `data-table-card.html`: toolbar, card and sheet styling.
- `panel-card`, `panel-page-header`, `panel-definition-list`, `_tab_set_base.html`: surfaces, header, grid of definitions and tab styling.
- `cotton/modal.html` and `partials/modal_form.html`: dialog and sheet shape. `c-modal` is used outside the educator interface.
- `docs/product/screenshots/*` and `panel_framework/reference` (component reference page and its Playwright tests) will need regeneration if components change.

**`educator_interface` only**
- `organisation_switcher.html`: outlined trigger and inline mobile list.
- `interface.html`: user block, `sidebar_presentation` override (`side-drawer`) and the mobile tab bar if it is built.
- Cell templates (`data-table-cells/learner_courses.html`, `cohort_links.html`, `cohort_courses.html`) and a new learner row or card template wired through `DataTable.card_template`.
- `views.py` column selection (for example a combined name/email cell).
- Any `CohortTabSet` / `LearnerPanelStack` layout classes (stack columns, tab set).
- Existing tests that assert on this markup: `tests/test_sidebar.py`, `tests/test_organisation_switcher.py`, `tests/playwright/test_*` (sidebar, switcher, learners mobile).

## 5. Summary notes for the spec

- Most of the work is restyling shared `panel_framework` chrome, so every panel user changes with it. The spec should say so explicitly and keep to the existing component classes and theme tokens.
- Three design screens have no real counterpart: the mobile bottom tab bar, learner detail tabs, and the Filter content of the learners filter/sort sheet. The spec should include or drop them deliberately.
- The create-cohort flow and the filter/sort sheet already exist and are restyle-only.

status: ok
