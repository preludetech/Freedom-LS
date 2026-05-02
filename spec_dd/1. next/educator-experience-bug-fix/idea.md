# Educator Experience Bug Fix

Two related issues with educator-facing data tables. Research details are in:

- `research_recursive_table.md`
- `research_pagination.md`

## Bug 1: Recursive table when filtering/sorting a panel data table

**Symptom**

On `/educator/cohorts/<uuid>/__tabs/details`, when the user filters or sorts the students table, the HTMX response replaces only the inner table div but the response body contains the *entire* surrounding panel. Each filter/sort nests another full panel inside the table div, so the output looks recursive.

**Root cause**

`DataTablePanel.render()` (in `freedom_ls/panel_framework/panels.py`) does not detect HTMX requests, so it always returns the full `panel_container` wrapper. The HTMX target is the inner table div (`#table-<panel_name>`) with `hx-swap="outerHTML"`, so the panel wrapper is incorrectly stuffed inside the table div on each interaction.

The list view at `/educator/users` is unaffected because it uses `DataTable` directly (no panel wrapper), so the response naturally matches the swap target.

The correct pattern already exists in `CohortCourseProgressPanel.render()` (`educator_interface/views.py` lines 706–710), which checks `HX-Request` and returns just the content for HTMX requests.

**Scope of the fix**

Fix the `DataTablePanel` base class so all 5 affected panels are repaired in one change:

1. `CohortStudentsPanel` — `/educator/cohorts/<uuid>/__tabs/details` (the reported bug)
2. `CourseRegistrationsPanel` — same details tab
3. `UserCohortsPanel` — `/educator/users/<user_pk>`
4. `CourseCohortRegistrationsPanel` — `/educator/courses/<uuid>`
5. `CourseStudentRegistrationsPanel` — `/educator/courses/<uuid>`

**Approach**

In `DataTablePanel`, override `render()` to detect `HX-Request` and return only `get_content(...)` for HTMX requests, falling back to the wrapped `super().render(...)` for full page loads. Mirror the existing pattern in `CohortCourseProgressPanel`.

**Must not regress**

- `/educator/users` (and other list views that render `DataTable` directly) must continue to filter/sort cleanly.
- Initial full-page loads of any panel must still render with the panel surface, header, and actions.

## Bug 2: Inconsistent pagination across data tables

**Symptom**

Pagination controls have two distinct visual styles:

- Numbered buttons (First / Previous / 1 2 … N / Next / Last) — used by `cotton/data-table.html` for `/educator/users`, `/educator/cohorts`, `/educator/courses`, and the panel data tables.
- Minimal "« Prev / Next »" buttons with a "Items X–Y of Z" range indicator — used only by the course progress panel (`course_progress_panel.html`), which has two independent paginators (course items + students).

The numbered-button style is the desired standard.

**Approach**

Create a single reusable `<c-pagination>` cotton component and use it everywhere.

- New component lives at `freedom_ls/base/templates/cotton/pagination.html`.
- Models the existing data-table numbered-button style (responsive: prev/next + "Page X of Y" on mobile, full numbered buttons on desktop).
- Inputs cover all current call sites (`page_obj`, `base_url`, `table_id`, `sort_by`, `sort_order`, `search_query`, plus a way to pass extra query params for cases like the course progress panel where multiple paginators share a URL).
- HTMX-driven by default with a fallback `href` for progressive enhancement.

**Migration**

1. Refactor `cotton/data-table.html` to delegate its pagination block to `<c-pagination>` (no visual change for users — same buttons, same behavior).
2. Replace the two prev/next blocks in `course_progress_panel.html` with `<c-pagination>` calls. Both course-items and student paginators should use the unified numbered-button style.

**Must not regress**

- All existing data tables (`/educator/users`, `/educator/cohorts`, `/educator/courses`, and panel tables) keep their current sort + search + filter + HTMX behavior.
- Query parameters (sort, order, search, registration, col_page, page) are preserved across pagination clicks.
- Course progress panel: clicking page on the course-items paginator must not reset the students paginator, and vice versa.

## Out of scope

- Student-interface form page navigation (`c-form-page-link`) — different use case, not table pagination.
- Backend changes (no view or model changes needed).
- Page-size changes or other styling tweaks not required to address these two bugs.
