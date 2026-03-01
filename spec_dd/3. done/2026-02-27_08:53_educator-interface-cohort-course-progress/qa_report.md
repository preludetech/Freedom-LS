# QA Report: Cohort Course Progress Panel

**Date:** 2026-02-21
**Tester:** Automated QA via Playwright MCP
**Viewport (Desktop):** 1920x1080
**Viewport (Mobile):** 375x812

---

## Desktop Results Summary

| Test | Description | Result |
|------|-------------|--------|
| 1 | Panel appears on cohort detail page | PASS |
| 2 | Course selection dropdown | PASS |
| 3 | Empty states | PASS |
| 4 | Progress grid layout | PASS |
| 5 | Course part headers | PASS |
| 6 | Student sorting | PASS |
| 7 | Topic cell content | PASS |
| 8 | Quiz form cell content | PASS |
| 9 | Non-quiz form cell content | PASS |
| 10 | Column pagination | PASS |
| 11 | Student (row) pagination | PASS |
| 12 | Cohort deadlines in headers | PASS |
| 13 | Student deadline overrides | PASS |
| 14 | Overdue highlighting | PASS |
| 15 | Student name links | PASS |

**All 15 desktop tests passed.**

---

## Desktop Screenshots

### Test 1: Panel on Cohort Detail Page
![Test 1](screenshots/test01_panel_on_cohort_detail_desktop.png)

### Test 2: Course Selection & Dropdown
![Test 2 - Closeup](screenshots/test02_course_progress_panel_closeup_desktop.png)
![Test 2 - Remote Pilot](screenshots/test02_course_selection_remote_pilot_desktop.png)

### Test 3: Empty States
![Test 3](screenshots/test03_empty_states_desktop.png)

### Tests 4-7: Grid Layout and Cell Content
![Tests 4-7](screenshots/test04_07_grid_layout_cells_desktop.png)

### Test 8: Quiz Form Cells
![Test 8](screenshots/test08_quiz_form_cells_desktop.png)

### Test 10: Column Pagination (Page 2)
![Test 10](screenshots/test10_column_pagination_page2_desktop.png)

### Test 11: Row Pagination
![Test 11](screenshots/test11_row_pagination_page1_desktop.png)

### Test 13: Deadline Override Cell
![Test 13](screenshots/test13_deadline_override_cell_desktop.png)

### Test 14: Overdue Cell
![Test 14](screenshots/test14_overdue_cell_desktop.png)

---

## Mobile Results Summary

| Test | Description | Result | Notes |
|------|-------------|--------|-------|
| 1 | Panel appears on cohort detail page | PASS | Sidebar must be manually collapsed |
| 2 | Course selection dropdown | PASS | Dropdown text truncated but functional |
| 3 | Empty states | PASS | |
| 4 | Progress grid layout | PASS | Horizontal scroll works via overflow-auto |
| 5 | Course part headers | PASS | Two-row headers render, visible via scroll |
| 6 | Student sorting | PASS | |
| 7 | Topic cell content | PASS | Visible when scrolling horizontally |
| 8 | Quiz form cell content | PASS | Visible when scrolling horizontally |
| 9 | Non-quiz form cell content | PASS | Visible when scrolling horizontally |
| 10 | Column pagination | PASS | Pagination controls visible below grid |
| 11 | Student (row) pagination | PASS | "Students 1-20 of 25" with Next button |
| 12 | Cohort deadlines in headers | PASS | Visible when scrolling |
| 13 | Student deadline overrides | PASS | Override icon visible when scrolling |
| 14 | Overdue highlighting | PASS | Visible when scrolling |
| 15 | Student name links | PASS | Links work on mobile |

**All 15 mobile tests passed functionally**, but with mobile responsiveness observations below.

---

## Mobile Responsiveness Observations

These are not test failures but UX observations for mobile viewports.

### 1. Sidebar Does Not Auto-Collapse on Mobile

**Affected tests:** All mobile tests
**Observed behavior:** When navigating to any page on a mobile viewport, the sidebar navigation is expanded by default. It overlaps the main content area, making the page content unreadable until the user manually clicks "Toggle sidebar".
**Expected behavior:** On small viewports, the sidebar should either be collapsed by default or use a mobile-friendly hamburger menu pattern.

![Sidebar expanded on mobile](screenshots/mobile_full_page.png)
![After collapsing sidebar](screenshots/mobile_sidebar_collapsed.png)

### 2. Course Dropdown Text Truncation

**Observed behavior:** The course selection dropdown shows truncated text (e.g., "Functionality Demo - show" instead of the full course name "Functionality Demo - show end with Topic"). This makes it difficult to distinguish between similarly named courses.
**Impact:** Low - users can still select courses, and the full name is visible once the dropdown is opened.

![Dropdown on mobile](screenshots/mobile_course_progress_panel.png)

### 3. Grid Shows Only Student Column Without Scrolling

**Observed behavior:** On mobile, the progress grid initially shows only the Student name column and a sliver of the next column. Users must scroll horizontally to see any progress data.
**Impact:** Medium - the grid is functional with horizontal scroll, but users may not immediately realize there is more content to the right. A visual indicator (e.g., a scroll hint or fade effect on the right edge) could improve discoverability.

![Grid on mobile](screenshots/mobile_course_progress_panel.png)

---

## Mobile Screenshots

### Course Progress Panel on Mobile
![Mobile Course Progress](screenshots/mobile_course_progress_panel.png)

### Empty State on Mobile
![Mobile Empty State](screenshots/mobile_empty_state.png)

### Quiz Course on Mobile
![Mobile Quiz Course](screenshots/mobile_quiz_course_progress.png)

### Large Cohort Pagination on Mobile
![Mobile Large Cohort](screenshots/mobile_large_cohort_pagination.png)
![Mobile Pagination Controls](screenshots/mobile_large_cohort_pagination_controls.png)

### Remote Pilot (Course Parts) on Mobile
![Mobile Remote Pilot](screenshots/mobile_remote_pilot_course_parts.png)

---

## Test Setup Notes

- The QA test plan references cohort name "Demo Cohort" in setup commands, but the actual cohort name in the database was "Cohort 2025.03.04". The commands were re-run with the correct cohort name.
- Cohorts used for testing:
  - **Cohort 2025.03.04** (11 members, 3 course registrations) - main test cohort
  - **Cohort 2025.04.06** (0 members, 0 registrations) - empty state test
  - **QA Large Cohort** (25 members, 1 registration) - row pagination test
  - **QA Empty Students Cohort** (0 members, 1 registration) - empty students test

## Peripheral Observations

- The Django Debug Toolbar (DJDT) tab is visible on the right edge of the screen on both desktop and mobile. This is expected in development but should be disabled in production.
- The sidebar "Toggle sidebar" button state does not persist across page navigations. When using HTMX to switch courses (which doesn't trigger a full page load), the sidebar state is preserved. But full page navigations reset it to expanded.
