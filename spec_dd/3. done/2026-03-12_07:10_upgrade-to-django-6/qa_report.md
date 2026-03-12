# QA Report: Django 6 Upgrade — Frontend QA

**Date:** 2026-03-11
**Tested by:** Automated QA via Playwright MCP
**Viewports tested:** Desktop (1920x1080), Mobile (375x812), Tablet (768x1024)

---

## Summary

Overall the frontend is in good shape after the Django 6 upgrade. All major pages load without 500 errors. Template rendering, HTMX interactions, Cotton components, and CSP headers all work correctly. A few issues were found:

- **1 functional issue:** "TODO" text visible on form completion page
- **1 console error:** Alpine.js CSP Parser Errors on educator pages
- **1 data/content issue:** Missing PDF file causes 404 in embedded iframe

---

## Issues Found

### Issue 1: "TODO" text visible on form completion page

**Test:** Test 2 — Course Content (form completion)
**Severity:** Low
**URL:** `/courses/functionality-demo-show-end-with-topic/3/complete`

**Expected:** The "Your Results" section should show category scores without any placeholder text.

**Actual:** The word "TODO" is displayed between the "Your Results" heading and the category score cards.

![Form complete page showing TODO text](screenshots/desktop_2.10_form_complete.png)

---

### Issue 2: Alpine.js CSP Parser Errors on Educator Interface

**Test:** Test 3 — Educator Interface
**Severity:** Medium
**Pages affected:** Educator cohort list, cohort detail, and any page using the educator dropdown/search components.

**Expected:** No JavaScript errors in the console.

**Actual:** Multiple `CSP Parser Error: Expected PUNCTUATION` errors from `@alpinejs/csp@3.15.8/dist/cdn.min.js`. These appear on the educator cohort pages where Alpine.js expressions are used (e.g., course dropdown, search box). The errors do not appear to break functionality visually, but they indicate that some Alpine.js expressions are not compatible with the CSP build's parser.

The errors were consistently reproducible on:
- `/educator/cohorts` (1 error)
- `/educator/cohorts/<uuid>` (3 errors)

---

### Issue 3: Missing PDF file causes 404 in content iframe

**Test:** Test 2 — Course Content
**Severity:** Low (demo data issue)
**URL:** `/courses/functionality-demo-show-end-with-topic/1/`

**Expected:** An embedded PDF viewer should display the sample PDF document.

**Actual:** The iframe shows a Django 404 error: the file `/media/content_engine/samplea5ee5374-01b6-4266-a212-3c595ea9d286.pdf` does not exist on disk.

![Content page with PDF 404](screenshots/desktop_2.6_content_with_callout.png)

This is likely a demo data issue (the PDF file was not included or was deleted), not a code issue.

---

## Tests Passed

### Test 1: Student Interface — Course List and Home Page
- Home page loads correctly with course cards, progress bars, descriptions
- "Your Courses", "Recommended Courses", "Learning History" sections all render
- HTMX-loaded content appears (courses loaded via `/partials/courses/`)
- "All Courses" page loads with 4 courses displayed
- No template rendering errors

![Home page](screenshots/desktop_1.1_home_page.png)
![All courses](screenshots/desktop_1.2_all_courses.png)

### Test 2: Course Content — Partials and Cotton Components
- Course home page with TOC renders correctly (icons, status indicators, numbering)
- Nested TOC with collapsible sections works (Remote Pilot Certificate)
- Topic content renders markdown correctly (headings, bold, italic, blockquotes, code, images, links, lists, horizontal rules)
- Callout components render with correct styling for all levels (info, warning, error, success)
- Deadline badges display in sidebar TOC
- Form page renders with radio button inputs and required field indicators
- Form submission works and redirects to completion page with category scores
- Navigation between pages works (Previous/Next buttons)

![Course home](screenshots/desktop_2.1_course_home.png)
![Topic content](screenshots/desktop_2.2_topic_content.png)
![Nested TOC](screenshots/desktop_2.5_course_toc_nested.png)
![Callouts](screenshots/desktop_2.7_callouts.png)
![Form page](screenshots/desktop_2.9_form_page.png)

### Test 3: Educator Interface
- Educator dashboard loads with sidebar navigation
- Cohort list table renders correctly with links, student counts, courses
- Cohort detail page shows progress table with status icons, deadline info, course selector
- Students list with search, sorting, and pagination works
- Course registrations table renders

![Cohort list](screenshots/desktop_3.1_educator_cohorts.png)
![Cohort detail](screenshots/desktop_3.2_cohort_detail.png)

### Test 4: Admin Interface (Unfold)
- Admin dashboard loads with Unfold theme
- All model admin sections visible (Accounts, Content Engine, Student Management, Student Progress)
- Users list view renders with search, filters, pagination
- Courses list view renders correctly
- Recent actions sidebar displays

![Admin dashboard](screenshots/desktop_4.1_admin_dashboard.png)
![Admin users](screenshots/desktop_4.2_admin_users.png)

### Test 5: Email Flows
- **5a:** Standard registration generates email in `gitignore/emails/` with inline CSS (django-premailer working)
- **5b:** Registration with `+` character (`test+upgrade@example.com`) succeeds without errors, email generated
- **5c:** Password reset email generated with inline CSS, correct links

All emails have:
- Inline CSS styles on HTML elements (no `<style>` blocks)
- Correct branding (DemoDev header)
- Proper links and content

### Test 6: CSP Headers
- `Content-Security-Policy-Report-Only` header is present
- Contains expected directives: `default-src 'self'`, `script-src 'self' 'unsafe-inline'`, `style-src 'self' 'unsafe-inline'`, `img-src 'self' data:`, `frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com`
- No CSP violations blocking functionality (report-only mode)
- No errors or warnings on the home page console

### Test 7: Form Validation
- Empty form submission prevented by browser native validation
- Mismatched passwords show inline error: "You must type the same password each time."
- Error messages display correctly within the form

![Validation error](screenshots/desktop_7.1_validation_error.png)

### Test 8: HTMX Interactions
- Course list loads via HTMX (`/partials/courses/` returns 200)
- HTMX content renders in correct target elements
- Form submission via HTMX works (Course Feedback Survey)
- No CSRF errors observed
- No CSP blocking of HTMX fetch requests

---

## Responsive Testing

### Mobile (375x812)
- Navigation uses hamburger icon with dropdown menu (Profile, Educator Interface, Admin Panel, Sign Out)
- Course cards stack in single column, buttons are touch-friendly
- Topic content fills width correctly, sidebar hidden with "Open sidebar" button
- Educator cohort table wraps text, remains readable
- Forms render at full width

![Mobile home](screenshots/mobile_1.1_home_page.png)
![Mobile nav](screenshots/mobile_nav_menu.png)
![Mobile topic](screenshots/mobile_2.1_topic_content.png)
![Mobile educator](screenshots/mobile_3.1_educator_cohorts.png)

### Tablet (768x1024)
- Navigation shows desktop-style text menu (email + dropdown)
- Course cards display in 2-column grid
- Topic content fills width, sidebar collapsed with toggle
- Educator progress table scrolls horizontally, remains functional
- Callouts render at reasonable width

![Tablet home](screenshots/tablet_1.1_home_page.png)
![Tablet callouts](screenshots/tablet_2.1_callouts.png)
![Tablet cohort detail](screenshots/tablet_3.1_cohort_detail.png)

---

## Notes

- The `upgrade-to-django-6` debug badge (pink label in bottom-left) appears on all pages. This is a development-only indicator and will not appear in production.
- Console shows "Loading the script ... No further action has been taken" info messages on every page — these are CSP report-only notifications about CDN scripts (Alpine.js, HTMX, etc.) and are expected behavior in report-only mode.
- The Unfold admin uses its own bundled Alpine.js which generates "Evaluating a string as JavaScript violates CSP" info messages — this is expected since Unfold does not use the CSP build of Alpine.
