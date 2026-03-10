# Mobile Responsiveness Audit & Bug Fixes

## Goal

Audit the entire user-facing application for mobile responsiveness issues and fix all bugs discovered in previous QA reports. The result should be an app that works well on mobile devices (360px+) across all user-facing interfaces.

## Scope

- Student interface (course browsing, content viewing, quizzes, progress tracking)
- Educator interface (cohort management, progress grids, student lists)
- Auth pages (login, signup, password change/reset, profile)
- Shared components (header, navigation, modals, buttons, data tables, cotton components)
- Excludes: Django admin interface

## Research

Research findings are in the same directory:
- `research_qa_errors.md` - All bugs extracted from previous QA reports
- `research_template_audit.md` - Template-by-template analysis of mobile responsiveness gaps
- `research_mobile_lms_best_practices.md` - Best practices for mobile LMS design

## Issues to Address

### Mobile Layout Issues

1. **Educator sidebar overlaps content on mobile** - On 375px viewports, sidebar is expanded by default and pushes content off-screen. Should be collapsed by default on mobile with a hamburger/toggle pattern. Flagged in 2 separate QA reports.

2. **Sidebar toggle state doesn't persist** - Collapsing the sidebar resets on full page navigation. State should persist (localStorage works for HTMX partial updates but not full navigations).

3. **Progress grid unusable on mobile** - Only the student name column is visible with no scroll hint. Needs a mobile-friendly layout.

4. **Course dropdown text truncated on mobile** - Course selection dropdown in progress panel shows truncated course names.

5. **Educator data tables cramped on mobile** - Column names clipped, content squeezed. Needs responsive table approach.

6. **YouTube embed has hardcoded 500px height** - Should use `aspect-video` for responsive sizing.

7. **Dropdown menu can render off-screen** - Fixed positioning with `w-40` and no viewport boundary detection.

8. **Form long-text input has `ml-4` indentation** - Breaks layout on mobile, should be responsive.

9. **Form page navigation buttons awkwardly spaced** - `justify-between` causes wide gaps on mobile.

10. **Pagination touch targets too small** - Links with `px-3 py-1` are below the 44px minimum.

11. **Instance details panel has no responsive styling** - Plain `<table>` with no overflow handling.

12. **Entrance/auth layout missing mobile side padding** - No `px-4` for small screens.

### Table/Grid Strategy for Mobile

For data tables on mobile: display the first column (e.g., student name) as a header above the rest of the row's data, rather than as a sticky/frozen column. Each row effectively becomes a mini-card with the identifier displayed prominently above the data cells.

### Non-Mobile Bugs (from QA reports)

13. **TOC shows original deadline instead of student's override** - When a student has a deadline override/extension, the TOC still shows the original cohort deadline.

14. **Alpine x-collapse plugin not installed** - Console warnings on every page with expandable sections. Expand/collapse works but without smooth animation.

15. **Broken image in lightbox (404)** - `graph1.drawio...svg` returns 404 from `/media/content_engine/`.

16. **Admin content type dropdown too verbose** - Shows all content types instead of only relevant ones (Topic, Form, Activity, CoursePart, Course). (Note: admin is out of scope for mobile but this is a functional bug worth fixing)

17. **Password change signs user out** - May be intentional but should be verified and either documented or fixed.

### Items Needing Verification

18. **CoursePart deadline display** - Never tested because test course lacked CourseParts.

19. **Deadline override priority with incomplete items** - Only partially verified because all affected items were already completed.

# IMPORTANT: Verify Before Fixing

Every issue must be confirmed to still exist before any fix is attempted:

1. **Frontend/UI issues** (responsiveness, layout, console errors, visual bugs): Use Playwright MCP to reproduce the issue at the relevant viewport size. If test data is needed, use the `qa-data-helper` agent to set up appropriate data in the development database.

2. **Backend/logic bugs** (incorrect data, wrong behaviour): Write a failing unit test that exposes the bug first, then implement the fix to make the test pass (TDD approach).
