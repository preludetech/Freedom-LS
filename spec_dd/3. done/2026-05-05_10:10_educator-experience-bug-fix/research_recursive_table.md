# Research: Recursive Table Nesting Bug in Educator Interface

## Bug Summary
On the educator cohort details page (`/educator/cohorts/<uuid>/__tabs/details`), when filtering or sorting the student table at the bottom, the HTMX response arrives and replaces only the *inside* of the table div, causing the table HTML to nest recursively (table contains another table inside it).

By contrast, the educator users data-table at `/educator/users` works correctly.

## Root Cause Analysis

### The Problem: DataTablePanel HTMX Rendering

When a **DataTablePanel** renders for an HTMX request, it incorrectly wraps the table content in the full panel container instead of returning just the table HTML.

**Flow for CohortStudentsPanel (broken):**

1. Initial page load: `/educator/cohorts/<uuid>/__tabs/details`
   - CohortInstanceView renders with tabs
   - The "details" tab contains CohortStudentsPanel (a DataTablePanel)
   - Panel.render() returns: `<section class="surface"><header>Students</header><div>{{ table html }}</div></section>`
   - Result: Full panel with table inside

2. User clicks sort/filter button
   - HTMX request sent with `hx-get` to panel URL: `/educator/cohorts/<uuid>/__tabs/details/__panels/students`
   - `hx-target="#table-students"` (the inner div containing the table)
   - `hx-swap="outerHTML"`

3. Panel response
   - The panel is resolved and Panel.render() is called
   - Returns: `<section class="surface"><header>Students</header><div><div id="table-students">{{ table html }}</div></div></section>`
   - BUT the HTMX target is `#table-students` (the inner div)

4. HTMX swap
   - The outerHTML of `#table-students` is replaced with the ENTIRE response
   - The response contains the full panel_container, including the `<div id="table-students">` wrapper
   - This causes the outer div with id="table-students" to become nested, and the table to nest recursively on each filter/sort

### Why `/educator/users` Works Correctly

The `/educator/users` page uses a **ListViewConfig** with a **DataTable** (not a DataTablePanel):

1. The page renders the list view directly: `UserDataTable.render()`
2. No panel_container wrapper is added
3. When filtering/sorting, the HTMX response is just the table div from DataTable.render()
4. The hx-target `#data-table-container` is replaced with just the table content
5. No nesting occurs

**Note:** If you navigate to `/educator/users/{user_pk}` (a user instance), you'd see the same bug in UserCohortsPanel when filtering, since it's a DataTablePanel inside flat panels.

## File Locations

### Views
- **File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/educator_interface/views.py`
  - Line 243-248: `CohortStudentsPanel` - uses DataTablePanel
  - Line 191-196: `UserCohortsPanel` - uses DataTablePanel (will have same bug in user instance)
  - Line 251-256: `CourseRegistrationsPanel` - uses DataTablePanel (affected)
  - Line 897-902: `CourseCohortRegistrationsPanel` - uses DataTablePanel (affected)
  - Line 949-954: `CourseStudentRegistrationsPanel` - uses DataTablePanel (affected)
  - Line 706-710: `CohortCourseProgressPanel.render()` - **Already has HTMX detection** (correct pattern)

### Panel Framework
- **File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/panel_framework/panels.py`
  - Line 47-67: `DataTablePanel` class - **MISSING HTMX detection**
  - Line 15-44: `Panel` class - renders content wrapped in panel_container
  - Line 31-44: `Panel.render()` - wraps content in `panel_framework/partials/panel_container.html`

- **File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/panel_framework/tables.py`
  - Line 62-88: `DataTable.render()` - returns just the table template
  - Line 56: `table_id` is set (e.g., "table-students")

### Templates
- **File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/base/templates/cotton/data-table.html`
  - Line 13: `<div id="{{ table_id }}">` - the target for HTMX
  - Lines 16-20, 48-49, 66-69, etc.: `hx-target="#{{ table_id }}"` and `hx-swap="outerHTML"`

- **File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/panel_framework/templates/panel_framework/partials/panel_container.html`
  - Wraps content in `<section class="surface">` with header and actions

## HTMX Attributes Analysis

### CohortStudentsPanel (Broken)
- **hx-target:** `#table-students` (the inner table div)
- **hx-swap:** `outerHTML` (replace the entire target element)
- **Response includes:** Full panel_container wrapper
- **Issue:** Panel_container is replacing the table div, causing nesting

### /educator/users (Working)
- **hx-target:** `#data-table-container` (or `#table-{panel_name}`)
- **hx-swap:** `outerHTML`
- **Response includes:** Just the table div, no wrapper
- **Result:** Works correctly because response matches target scope

## Pattern: CohortCourseProgressPanel (Correct Implementation)

The CohortCourseProgressPanel demonstrates the correct pattern for HTMX in panels:

**File:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/educator_interface/views.py` Lines 706-710

```python
def render(self, request, base_url: str = "", panel_name: str = "") -> str:
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        return self.get_content(request, base_url=base_url, panel_name=panel_name)
    return super().render(request, base_url=base_url, panel_name=panel_name)
```

- For HTMX requests: returns just the content (no panel wrapper)
- For full page loads: returns wrapped content (via super().render())

## Diagnosis

**Root cause:** DataTablePanel does not override the render() method to detect HTMX requests.

When an HTMX request arrives for filtering/sorting a data table inside a panel:
1. The panel's render() method is called
2. It calls super().render() (Panel.render()), which wraps the content in panel_container
3. The entire wrapped response is sent back
4. But the hx-target is only the inner table div
5. Replacing the target's outerHTML with the full panel response causes nesting

**Why /educator/users doesn't have this issue:**
- It's not a panel, it's a direct DataTable render
- The response is just the table div, matching the hx-target scope

## Affected Data Tables

All DataTablePanel instances will have this bug when filtering/sorting:

1. **CohortStudentsPanel** - `/educator/cohorts/<uuid>/__tabs/details` (REPORTED BUG)
2. **CourseRegistrationsPanel** - `/educator/cohorts/<uuid>/__tabs/details`
3. **UserCohortsPanel** - `/educator/users/<user_pk>` (panel view, not list view)
4. **CourseCohortRegistrationsPanel** - `/educator/courses/<uuid>`
5. **CourseStudentRegistrationsPanel** - `/educator/courses/<uuid>`

The list view pages (/educator/users, /educator/cohorts, /educator/courses) work fine because they render DataTable directly, not through a panel.

## Fix Recommendation

Add HTMX detection to **DataTablePanel** to match the pattern used in **CohortCourseProgressPanel**.

**File to modify:** `/home/sheena/workspace/lms/freedom-ls-worktrees/main/freedom_ls/panel_framework/panels.py`

**Change required:** Override render() method in DataTablePanel class

```python
class DataTablePanel(Panel):
    data_table: type[DataTable]

    def get_filters(self) -> dict:
        return {}

    def get_content(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        table_id = f"table-{panel_name}" if panel_name else "data-table-container"
        return self.data_table.render(
            request,
            filters=self.get_filters(),
            base_url=base_url,
            table_id=table_id,
        )

    def render(
        self, request: HttpRequest, base_url: str = "", panel_name: str = ""
    ) -> str:
        # NEW: Detect HTMX requests and return only the content
        is_htmx = request.headers.get("HX-Request") == "true"
        if is_htmx:
            return self.get_content(request, base_url=base_url, panel_name=panel_name)
        # For full page loads, wrap in panel container
        return super().render(request, base_url=base_url, panel_name=panel_name)
```

This change:
- Returns just the table content for HTMX filter/sort requests
- Still wraps in panel_container for initial page load
- Prevents recursive table nesting
- Fixes all 5 affected DataTablePanel instances
- Does NOT break the /educator/users page (it doesn't use panels for list view)

## Why This Fix Won't Regress the Users Page

The `/educator/users` page uses `UserDataTable` directly (not a panel), so it doesn't use the DataTablePanel render() method. The change only affects panels, so list views are unaffected.

Even if UserCohortsPanel (in the user instance view) is fixed, it will work correctly because:
1. The HTMX target will be the table div
2. The response will be just the table content (no panel wrapper)
3. The swap will replace the table content correctly
4. The panel title and structure remain intact on the page

## Summary

| Aspect | Cohort Students (Bug) | /educator/users (Works) |
|--------|----------------------|------------------------|
| View Type | Panel in Tab | Direct DataTable |
| Response on Filter | Full panel_container | Just table div |
| HTMX Target | #table-students | #data-table-container |
| Result | Table nests recursively | Table updates cleanly |
| Fix Needed | Add HTMX check to Panel.render() | None |
