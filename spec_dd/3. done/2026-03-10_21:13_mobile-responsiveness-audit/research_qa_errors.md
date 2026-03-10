# QA Report Issues - Research Summary

Extracted from QA reports and frontend QA files across multiple features.

---

## Mobile Layout Issues

### 1. Educator Sidebar Overlaps Content on Mobile

**Source:** Cohort Course Progress QA Report (`2026-02-27_08:53_educator-interface-cohort-course-progress/qa_report.md`), Icon Migration QA Report (`2026-03-01_22:40_open-source-icons/qa_report.md`)

**Description:** On mobile viewports (375x812), the educator interface sidebar navigation is expanded by default. It overlaps/pushes the main content area off-screen to the right, making page content inaccessible until the user manually clicks "Toggle sidebar". This was flagged independently in two separate QA reports.

**Expected behavior:** On small viewports, the sidebar should either be collapsed by default or use a mobile-friendly hamburger menu pattern.

**Severity:** Medium

**Screenshots:** `mobile_full_page.png` (cohort progress report), `t07-progress-grid-mobile.png` and `t07-educator-sidebar-overlap-mobile.png` (icon migration report)

---

### 2. Sidebar Toggle State Does Not Persist Across Page Navigations

**Source:** Cohort Course Progress QA Report (`2026-02-27_08:53_educator-interface-cohort-course-progress/qa_report.md`)

**Description:** The sidebar "Toggle sidebar" button state does not persist across full page navigations. When using HTMX to switch courses (partial reload), the sidebar state is preserved. But full page navigations reset it to expanded, forcing the user to collapse it again each time on mobile.

**Severity:** Medium (compounds the sidebar overlap issue on mobile)

---

### 3. Progress Grid Shows Only Student Column on Mobile Without Scrolling

**Source:** Cohort Course Progress QA Report (`2026-02-27_08:53_educator-interface-cohort-course-progress/qa_report.md`)

**Description:** On mobile, the progress grid initially shows only the Student name column and a sliver of the next column. Users must scroll horizontally to see any progress data. There is no visual indicator (scroll hint, fade effect on right edge) to signal that more content exists to the right.

**Severity:** Medium

**Screenshot:** `mobile_course_progress_panel.png`

---

### 4. Course Dropdown Text Truncation on Mobile

**Source:** Cohort Course Progress QA Report (`2026-02-27_08:53_educator-interface-cohort-course-progress/qa_report.md`)

**Description:** The course selection dropdown in the progress panel shows truncated text on mobile (e.g., "Functionality Demo - show" instead of the full course name). This makes it difficult to distinguish between similarly named courses.

**Severity:** Low (full name visible when dropdown is opened)

**Screenshot:** `mobile_course_progress_panel.png`

---

### 5. Educator Data Tables Cramped on Mobile

**Source:** Icon Migration QA Report (`2026-03-01_22:40_open-source-icons/qa_report.md`)

**Description:** The cohort list table and student data tables are cramped on mobile with column names being cut off (e.g., "Cohort Name" becomes partially visible). Tables are horizontally scrollable which helps, but the experience is suboptimal. The first column (e.g., cohort name) gets clipped by the viewport edge.

**Severity:** Low

**Screenshot:** `t07-educator-sidebar-overlap-mobile.png`, `t08-data-table-headers-mobile.png`

---

## Missing Plugin / Console Errors

### 6. Alpine x-collapse Plugin Missing (Console Warnings)

**Source:** Icon Migration QA Report (`2026-03-01_22:40_open-source-icons/qa_report.md`)

**Description:** The browser console shows 6 Alpine.js warnings on every page with expandable course parts:
```
Alpine Warning: You can't use [x-collapse] without first installing the "collapse" plugin.
```
Expand/collapse toggling still works (visibility toggles), but without the smooth animated transition that `x-collapse` provides. This affects expand/collapse animation smoothness on both desktop and mobile.

**Severity:** Low (functionality works, animations absent)

---

## Content / Media Issues

### 7. Broken Image in Lightbox (404)

**Source:** Icon Migration QA Report (`2026-03-01_22:40_open-source-icons/qa_report.md`)

**Description:** The lightbox opens correctly but the image itself (`graph1.drawio...svg`) returns a 404 from `/media/content_engine/`. The lightbox chrome and close icon work properly; only the image content is missing.

**Severity:** Low (content/media issue, not a template issue)

**Screenshot:** `t12-lightbox-desktop.png`

---

## Deadline Display Issues

### 8. TOC Does Not Show Override Dates (Shows Original Deadline Instead)

**Source:** Deadlines QA Report (`2026-02-19_19:25_deadlines/qa_report.md`)

**Description:** When a StudentCohortDeadlineOverride extends a course-level deadline (e.g., from Mar 15 to Mar 20), the TOC still displays the original cohort deadline date rather than the overridden date. This is misleading for students who have been given an extension -- they see the original deadline rather than their actual effective deadline.

**Severity:** Medium (misleading information shown to students)

---

## Admin Interface Issues

### 9. Admin Content Type Dropdown Is Too Verbose

**Source:** Deadlines QA Report (`2026-02-19_19:25_deadlines/qa_report.md`)

**Description:** The content_type dropdown in the deadline admin inlines shows ALL content types in the system (including unrelated ones like "Authentication and Authorization | permission", "Guardian | group object permission", etc.). This makes it difficult to find the relevant content types.

**Recommendation:** Filter the dropdown to only show relevant content types (Topic, Form, Activity, CoursePart, Course).

**Severity:** Low (admin UX issue)

---

## Untested / Partially Tested Items

### 10. CoursePart Deadline Display Not Tested

**Source:** Deadlines QA Report (`2026-02-19_19:25_deadlines/qa_report.md`)

**Description:** Test 2d (CoursePart deadline display in TOC) could not be executed because the test course did not contain any CoursePart items. This remains unverified.

---

### 11. Deadline Override Priority Only Partially Verified

**Source:** Deadlines QA Report (`2026-02-19_19:25_deadlines/qa_report.md`)

**Description:** Tests 4a and 4b (override beats cohort deadline, item-level beats course-level) only partially passed. The override behavior could not be conclusively tested because all items affected by the override were already completed (completed items are accessible regardless of deadline status). A test with an incomplete item governed only by a course-level deadline (with no item-level deadline) is needed for full verification.

---

### 12. Cross-Client Email Rendering Not Fully Tested

**Source:** Email Templates QA Report (`2026-03-01_22:53_email_templates/qa_report.md`)

**Description:** Email templates were only tested in Chromium browser. Testing with actual Gmail, Outlook, and Apple Mail was not performed. This would require sending real emails or using a service like Litmus/Email on Acid.

---

## Behavioral Observations

### 13. Password Change Signs User Out

**Source:** Email Templates QA Report (`2026-03-01_22:53_email_templates/qa_report.md`)

**Description:** After changing a password, the user is signed out and redirected to the homepage with a "You have signed out" message. This may be intentional for security but could be surprising to users who expect to remain logged in.

**Severity:** Low (may be intentional behavior)

---

## Summary by Priority

| Priority | Count | Issues |
|----------|-------|--------|
| Medium   | 4     | Sidebar overlaps on mobile (#1), sidebar state not persisted (#2), grid scroll hint missing (#3), TOC shows wrong deadline (#8) |
| Low      | 6     | Dropdown truncation (#4), tables cramped (#5), Alpine plugin missing (#6), broken image (#7), admin dropdown verbose (#9), password change signout (#13) |
| Untested | 3     | CoursePart deadlines (#10), override priority (#11), cross-client email (#12) |
