# Pagination UI Inconsistency Research

## Executive Summary

The FreedomLS educator interface has **two distinct pagination styles** scattered across different views. The `/educator/users` list uses full numbered pagination buttons, while `/educator/cohorts/<uuid>` course progress table uses simple prev/next buttons with range indicators. This research identifies all pagination instances and recommends consolidation into a reusable `<c-pagination>` cotton component.

---

## 1. Pagination Implementations Found

### 1.1 Data Table Pagination (Main Tables)
**Used in:** `/educator/users`, `/educator/cohorts`, `/educator/courses`

| Aspect | Details |
|--------|---------|
| **View File** | `/freedom_ls/educator_interface/views.py` (lines 80-175, 212-241, 777-859) / `/freedom_ls/panel_framework/tables.py` (lines 35-60) |
| **View Classes** | `CohortDataTable`, `UserDataTable`, `CourseDataTable`, `CohortCourseRegistrationDataTable`, etc. |
| **Template** | `/freedom_ls/base/templates/cotton/data-table.html` |
| **Renders As** | `<c-data-table>` cotton component |
| **Pagination Style** | **Dual-mode responsive design**: Mobile (prev/next + "Page X of Y"), Desktop (First, prev, numbered buttons 1-2...N-1-N, next, Last) |
| **Styling** | `btn btn-outline` buttons with `btn btn-primary` for current page |
| **HTMX** | Yes - `hx-get` on each button with query params; `hx-target="#{{ table_id }}"` |
| **URL Pattern** | Query string: `?page=N&sort=...&order=...&search=...` |
| **Controller Logic** | `DataTable.get_rows()` creates Django `Paginator` object and returns `page_obj` (lines 56-60 in tables.py) |

**Data Table Template Snippet** (lines 106-197 in data-table.html):
- Mobile: Shows "Previous", "Page X of Y", "Next" (lines 109-135)
- Desktop: Shows "First", "Previous", numbered buttons 1-2...N-1-N with ellipsis logic, "Next", "Last" (lines 138-196)
- Conditional display with `{% if page_obj and page_obj.paginator.num_pages > 1 %}`

### 1.2 Course Progress Panel Pagination
**Used in:** `/educator/cohorts/<uuid>/__tabs/course_progress`

| Aspect | Details |
|--------|---------|
| **View File** | `/freedom_ls/educator_interface/views.py` lines 259-710 (class `CohortCourseProgressPanel`) |
| **Template** | `/freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html` |
| **Pagination Objects** | TWO separate paginators: `col_page` (columns/items) and `student_page` (students) |
| **Pagination Style** | **Minimal prev/next only**: "« Prev" / "Next »" buttons with range display "Items X–Y of Z" / "Students X–Y of Z" |
| **Styling** | `btn btn-outline px-4 py-3 sm:px-3 sm:py-1 text-xs` |
| **HTMX** | Yes - `hx-get` on each button with multiple query params: `registration`, `col_page`, `page` |
| **URL Pattern** | Query string: `?registration=<uuid>&col_page=N&page=M` |
| **Controller Logic** | Lines 303-304 and 338-339: Manual `Paginator` instantiation for course items and students |

**Course Progress Panel Template Snippet** (lines 157-198 in course_progress_panel.html):
- Column pagination: "Items X–Y of Z" with prev/next buttons (lines 159-177)
- Student pagination: "Students X–Y of Z" with prev/next buttons (lines 180-198)
- Buttons shown conditionally with `{% if col_page.has_previous %}` / `{% if col_page.has_next %}`

### 1.3 Student Interface Form Pagination
**Used in:** `/student/<slug>/courses/<slug>/<index>/fill_form/<page_number>/`

| Aspect | Details |
|--------|---------|
| **View File** | `/freedom_ls/student_interface/views.py` lines 175-230 (function `form_fill_page()`) |
| **Template** | `/freedom_ls/student_interface/templates/student_interface/course_form_page.html` |
| **Pagination Style** | **Page number button links** + "Back/Next" navigation buttons (lines 130-183) |
| **Styling** | `c-form-page-link` cotton component for each page button, `c-button` for Back/Next |
| **HTMX** | No - full page navigation, uses regular `<a>` links |
| **URL Pattern** | URL path: `/courses/<slug>/<index>/fill_form/<page_number>/` |
| **Controller Logic** | Manual page counting: `page_number = form_progress.get_current_page_number()` (not using Django Paginator) |
| **Note** | This is **form pagination**, not table pagination — different use case, custom component `c-form-page-link` |

---

## 2. All Pagination Call Sites

### In Educator Interface

| Route | View/Panel | Template File | Line Numbers | Paginates What | Page Size |
|-------|------------|---------------|--------------|-----------------|-----------|
| `/educator/users` | `UserDataTable.get_rows()` | `cotton/data-table.html` | 106-197 | User list | 5 (default) |
| `/educator/cohorts` | `CohortDataTable.get_rows()` | `cotton/data-table.html` | 106-197 | Cohort list | 5 (default) |
| `/educator/courses` | `CourseDataTable.get_rows()` | `cotton/data-table.html` | 106-197 | Course list | 5 (default) |
| `/educator/cohorts/<uuid>/__tabs/details` | `CohortStudentsPanel` (DataTable) | `cotton/data-table.html` | 106-197 | Students in cohort | 5 (default) |
| `/educator/cohorts/<uuid>/__tabs/details` | `CourseRegistrationsPanel` (DataTable) | `cotton/data-table.html` | 106-197 | Course registrations | 5 (default) |
| `/educator/cohorts/<uuid>/__tabs/course_progress` | `CohortCourseProgressPanel` | `course_progress_panel.html` | 157-198 | Course items + Students | 15 items, 20 students |
| `/educator/cohorts/<uuid>/students` | `CohortStudentsPanel` (DataTable) | `cotton/data-table.html` | 106-197 | Students | 5 (default) |
| `/educator/courses/<uuid>/students` | `CourseStudentRegistrationsPanel` (DataTable) | `cotton/data-table.html` | 106-197 | Direct student registrations | 5 (default) |
| `/educator/courses/<uuid>/cohorts` | `CourseCohortRegistrationsPanel` (DataTable) | `cotton/data-table.html` | 106-197 | Cohort registrations | 5 (default) |

### In Student Interface

| Route | Controller | Template File | Pagination Type |
|-------|-----------|---------------|-----------------|
| `/student/courses/<slug>/<index>/fill_form/<page_number>/` | `form_fill_page()` | `course_form_page.html` | Custom form page navigation (not standard Django paginator) |

---

## 3. Current Cotton Components

### Existing Cotton Components (Base Templates)
Located in: `/freedom_ls/base/templates/cotton/`

**Pagination-Adjacent Components:**
- `button.html` — Basic button component with variant support (primary, outline, etc.)
- `button-group.html` — Button group layout
- `data-table.html` — **Primary table component** with built-in pagination (lines 106-197)
- `form-page-link.html` — Custom link for form page navigation
- `scroll-table-labels.html` — Table wrapper with sticky headers

**Data Table Cell Components:**
- `data-table-cells/text.html` — Simple text display
- `data-table-cells/link.html` — Link rendering
- `data-table-cells/boolean.html` — Boolean/checkbox display

### No Existing Pagination Component
**Finding:** There is **NO standalone `<c-pagination>` component** currently. Pagination is tightly coupled to `<c-data-table>` (lines 106-197 of data-table.html).

---

## 4. Pagination Implementations - Code Locations

### Django Paginator Usage (Backend)

**In `panel_framework/tables.py`:**
```python
# Lines 56-60
page_number = request.GET.get("page", 1)
paginator = Paginator(queryset, cls.page_size)
page_obj = paginator.get_page(page_number)
```

**In `educator_interface/views.py`:**
```python
# Lines 303-304 (column pagination)
col_paginator = Paginator(items, self.COLUMN_PAGE_SIZE)  # COLUMN_PAGE_SIZE = 15
col_page = col_paginator.get_page(col_page_num)

# Lines 338-339 (student pagination)
student_paginator = Paginator(memberships, self.STUDENT_PAGE_SIZE)  # STUDENT_PAGE_SIZE = 20
return student_paginator.get_page(page_num)
```

### Pagination Template Implementations

**1. Data Table Pagination** (`cotton/data-table.html`, lines 106-197):
- Variables passed: `page_obj`, `sort_by`, `sort_order`, `search_query`, `base_url`, `table_id`
- Mobile: Responsive `{% if page_obj and page_obj.paginator.num_pages > 1 %}` with Previous/Next
- Desktop: Full number buttons with ellipsis logic
- HTMX integration: `hx-get`, `hx-target="#{{ table_id }}"`, `hx-swap="outerHTML"`

**2. Course Progress Panel Pagination** (`educator_interface/partials/course_progress_panel.html`, lines 157-198):
- Variables: `col_page`, `student_page`, `base_url`, `selected_reg`, `col_page_num`, `student_page_num`
- Prev/next only (no numbered buttons)
- Two separate pagination sections (columns + students)
- Manual HTMX: `hx-get` with multiple query parameters

---

## 5. Visual Style Analysis

### Data Table Style (Current - "Buttons" Style)

**Desktop View (hidden sm:flex):**
```
[First] [Previous] [1] [2] ... [N-1] [N] ... [Next] [Last]
         with current page highlighted: <span class="btn btn-primary">{{ num }}</span>
```

**Mobile View (flex sm:hidden):**
```
[Previous] "Page X of Y" [Next]
```

**Button Classes:** `btn btn-outline` (inactive), `btn btn-primary` (current page)

### Course Progress Panel Style (Current - "Prev/Next" Style)

```
Items 1–15 of 45    [« Prev]  [Next »]
Students 1–20 of 100 [« Prev]  [Next »]
```

**Button Classes:** `btn btn-outline px-4 py-3 sm:px-3 sm:py-1 text-xs`
**Layout:** Flex with gap, separate sections

### Desired Unified Style
**Per the bug report:** Use the style from `/educator/users` (the "buttons at the bottom" — data-table style) as the standard.

---

## 6. HTMX Pagination Patterns

### Pattern 1: Data Table (Current)
```html
<a href="?page={{ num }}{% if sort_by %}&sort={{ sort_by }}&order={{ sort_order }}{% endif %}"
   hx-get="{{ base_url }}?page={{ num }}..."
   hx-target="#{{ table_id }}"
   hx-swap="outerHTML"
   class="btn btn-outline">
    {{ num }}
</a>
```

### Pattern 2: Course Progress Panel (Current)
```html
<button hx-get="{{ base_url }}?registration={{ selected_reg.pk }}&col_page={{ col_page.next_page_number }}&page={{ student_page.number }}"
        hx-target="#course-progress-content"
        hx-swap="outerHTML"
        class="btn btn-outline px-4 py-3 sm:px-3 sm:py-1 text-xs">
    Next »
</button>
```

**Differences:**
- Data table uses `<a>` with fallback href; panel uses `<button>`
- Data table includes multiple query params in HTMX target
- Inconsistent query parameter naming

---

## 7. Proposed Component Specification

### Component: `<c-pagination>`

**Location:** `/freedom_ls/base/templates/cotton/pagination.html`

**Inputs (c-vars):**
```
page_obj         — Django Page object (required; provides: number, has_next, has_previous,
                   next_page_number, previous_page_number, paginator.num_pages,
                   start_index, end_index, paginator.count)
base_url         — Base URL for pagination links (e.g., "/educator/users")
sort_by          — Current sort column name (optional)
sort_order       — Current sort order: 'asc' or 'desc' (optional)
search_query     — Current search term (optional)
table_id         — Target container ID for HTMX swap (required for HTMX)
extra_params     — Additional query parameters as dict (optional; for multi-page cases)
show_range       — Show "X–Y of Z" text indicator (boolean; default: true)
show_page_text   — Show "Page X of Y" on mobile (boolean; default: true)
responsive       — Enable mobile/desktop responsive pagination (boolean; default: true)
button_class     — Additional button classes (string; optional)
container_class  — Additional container classes (string; optional)
```

**Rendering Logic:**
1. If `responsive=true`:
   - Mobile: Previous, "Page X of Y" text, Next
   - Desktop: First, Previous, numbered buttons (1-2...N-1-N), Next, Last
2. Ellipsis logic for numbered buttons (show first 2, last 2, current ±2)
3. HTMX on all buttons: `hx-get`, `hx-target="#{{ table_id }}"`, `hx-swap="outerHTML"`
4. Fallback `href` for non-HTMX users

**Call Sites (Migrations):**
1. `cotton/data-table.html` (lines 106-197) → Extract to `c-pagination` component
2. `educator_interface/partials/course_progress_panel.html` (lines 157-198) → Use `c-pagination` twice (once per section)

---

## 8. Convention Findings

### Cotton Component Conventions (Based on Existing Components)

1. **File Location:** `/freedom_ls/base/templates/cotton/<component-name>.html`
2. **Input Pattern:** Use `<c-vars>` tag at top with all possible inputs and defaults
3. **Variable Passing:** Use `:attribute="value"` syntax for dynamic values in cotton usage
4. **Styling:**
   - Use Tailwind utility classes
   - Apply `btn btn-<variant>` for buttons
   - Use spacing: `gap-2`, `px-4`, `py-3`, `mt-6`, etc.
5. **Responsive Design:** Use `hidden sm:flex` / `flex sm:hidden` for mobile/desktop splits
6. **Conditional Rendering:** Use `{% if condition %}...{% endif %}` for optional sections
7. **Comments:** Include usage examples in `{% comment %}` block at end
8. **HTMX Integration:** Place `hx-*` attributes directly on interactive elements
9. **Fallback Links:** Pair HTMX with non-HTMX fallback `href` (progressive enhancement)
10. **Accessibility:** Use semantic HTML (`<a>`, `<button>`), text alternatives for icons

### Panel Framework Conventions

- `DataTable` subclasses define `get_queryset()`, `get_columns()`, `page_size`, and optionally `search_fields`
- All pagination calls happen in `get_rows()` classmethod which applies filtering, searching, sorting
- Context passed to template includes: `columns`, `rows`, `page_obj`, `sort_by`, `sort_order`, `base_url`, `search_query`, `table_id`, `show_search`

---

## 9. Key Implementation Notes

### Tight Coupling Issue
**Current Problem:** Pagination is deeply embedded in `data-table.html` (lines 106-197). The component mixes:
- Table structure (thead/tbody)
- Data rendering
- Pagination UI
- Search/filter UI

**Solution:** Extract pagination into standalone `<c-pagination>` component, which `data-table` will include.

### Two-Paginator Design in Course Progress Panel
**Context:** The course progress panel has **two independent paginators**:
- `col_page`: Courses items/topics/forms (15 per page)
- `student_page`: Students in cohort (20 per page)

Both must maintain their state when paginating. The new component must support:
```html
<c-pagination page_obj="col_page"
              extra_params="student_page={{ student_page.number }},registration={{ selected_reg.pk }}"
              base_url="{{ base_url }}"
              table_id="course-progress-content" />
<c-pagination page_obj="student_page"
              extra_params="col_page={{ col_page.number }},registration={{ selected_reg.pk }}"
              base_url="{{ base_url }}"
              table_id="course-progress-content" />
```

### Query Parameter Preservation
The component must preserve:
- `sort`, `order`, `search` (for data tables)
- `registration`, `col_page`, `page` (for course progress)
- Any custom params passed via `extra_params`

---

## 10. File Paths Summary

### Affected Files (Will Need Migration)

| Path | Type | Action |
|------|------|--------|
| `/freedom_ls/base/templates/cotton/data-table.html` | Template | Extract lines 106-197 to new component |
| `/freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html` | Template | Use new pagination component (lines 157-198) |
| `/freedom_ls/base/templates/cotton/pagination.html` | Template | **CREATE** new component |

### Supporting Code (No Changes Required)

- `/freedom_ls/panel_framework/tables.py` — Paginator logic (backend)
- `/freedom_ls/educator_interface/views.py` — View logic (backend)
- `/freedom_ls/panel_framework/views.py` — View framework

---

## 11. Component Input Requirements Matrix

Based on all pagination use cases, the `<c-pagination>` component needs:

| Input | Required | Type | Used By | Example |
|-------|----------|------|---------|---------|
| `page_obj` | Yes | Object | All | `col_page` or `student_page` |
| `base_url` | Yes | String | All | `/educator/users` |
| `table_id` | Yes | String | All (HTMX target) | `data-table-container` |
| `sort_by` | No | String | Data tables | `first_name` |
| `sort_order` | No | String | Data tables | `asc` or `desc` |
| `search_query` | No | String | Data tables | search term |
| `extra_params` | No | Dict | Course progress panel | `registration=<uuid>&page=2` |
| `responsive` | No | Boolean | All | `true` (default) |
| `show_range` | No | Boolean | All | `true` (default) |
| `show_page_text` | No | Boolean | Mobile | `true` (default) |
| `button_class` | No | String | Styling | `text-xs` |
| `container_class` | No | String | Styling | `mt-6` |

---

## Conclusion

The project has **two inconsistent pagination UIs** that should be consolidated into a single reusable `<c-pagination>` cotton component. The "numbered buttons" style from the data tables (`/educator/users`) should be standardized across all list views. The component should:

1. Support both mobile (prev/next) and desktop (full buttons) layouts
2. Handle multiple independent paginators (course progress panel use case)
3. Integrate seamlessly with HTMX via `hx-*` attributes
4. Preserve all query parameters (sort, search, filters)
5. Follow existing cotton component conventions

The implementation involves:
- Creating `/freedom_ls/base/templates/cotton/pagination.html`
- Refactoring `/freedom_ls/base/templates/cotton/data-table.html` to use the new component
- Updating `/freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html` to use the new component

No backend code changes are required; this is purely a frontend consolidation effort.
