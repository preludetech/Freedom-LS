# Frontend QA report: panel framework core

## Methodology

Manual QA using the Playwright MCP against a dev server on port 8075, branch `educator-interface-1-panel-framework-core`. Three viewports were exercised: desktop (1920x1080), mobile (375x812) and tablet (768x1024). Screenshots were collected into `screenshots/` beside this report; every image linked below was confirmed to exist in that folder before linking.

## Diff scoping

Class: **FULL**. Changed files touched templates and static assets across the panel framework and educator interface (`freedom_ls/base/templates/_base.html`, `freedom_ls/base/static/base/js/alpine-components.js`, `freedom_ls/panel_framework/templates/**`, `freedom_ls/panel_framework/static/panel_framework/js/alpine-components.js`, `freedom_ls/educator_interface/templates/**`, `freedom_ls/panel_framework/*.py`, `freedom_ls/educator_interface/views.py` — roughly 150 files in total). Because `templates/` and `static/` paths were touched, the run was classed FULL: every test in `3. frontend_qa.md` ran, across all three viewports. Nothing was skipped.

## Smoke gate

Status: **pass**. Pages checked: `http://127.0.0.1:8075/` and `http://127.0.0.1:8075/educator/` (which redirected to `/educator/organisations/demodev/dashboard`). No failure.

## Results

### Desktop (1920x1080)

| Test | Status | Note |
| --- | --- | --- |
| 1.1 | pass | `/educator/` redirected to DemoDev dashboard (admin's first organisation). |
| 1.2 | pass | Tab title "Dashboard — DemoDev — DemoDev"; h1 "Dashboard". |
| 1.3 | pass | One "Reporting" card, placeholder sentence, no tiles/lists. |
| 1.4 | pass | Switcher, TEACHING heading, four nav items with icons; Dashboard highlighted, no counts. |
| 1.5 | pass | Footer shows email only (admin has blank first/last name); no role, no settings link. |
| 1.6 | pass | `no.access` gets 404 on `/educator/` and on the RPAS Training dashboard. |
| 2.1 | pass | Clicking Cohorts is one XHR, no reload, heading/breadcrumb/title/highlight all update. |
| 2.2 | pass | `Vary` header includes HX-Request, HX-Target, HX-History-Restore-Request, Cookie. |
| 2.3 | pass | Back does a fresh GET (history-restore) of the dashboard, highlight returns to Dashboard. |
| 2.4 | pass | Forward refetches Cohorts, heading and highlight follow. |
| 2.5 | pass | htmx-config meta present with historyCacheSize 0 / historyRestoreAsHxRequest false; one `#scope-announcer` outside `#main-content`. |
| 3.1 | pass | Cohorts list shows Year 10 Science and Year 9 Maths with counts; Create Cohort button above table. |
| 3.2 | pass | Detail page: h1, one "Details" tab (current), then Details/Course Registrations/Learners cards. |
| 3.3 | pass | Delete button lives inside the Details card; nothing above the tab strip. |
| 3.4 | pass | Sidebar shows the cohort nested under Cohorts, highlighted. |
| 3.5 | pass | Breadcrumb "Cohorts › Year 9 Maths"; clicking Cohorts is one XHR, no reload. |
| 3.6 | pass | Sorting Learners by First Name only refreshes the panel region; one `section[data-panel="learners"]`, no nesting. |
| 3.7 | pass | Searching "Pri" narrows to Priya via panel XHR, keeping sort params. |
| 4.1 | pass | Activating the Details tab pushes `__tabs/details`, one XHR, three cards once each, focus stays sane. |
| 4.2 | pass | XHR body has the three cards plus an OOB `#scope-announcer` update; no sidebar/`<html>`. |
| 4.3 | pass | Back returns to the detail URL via a fresh history-restore GET. |
| 4.4 | pass | Opening the tab URL directly returns the full page, Details current. |
| 4.5 | pass | Bad tab/panel URL combinations 404 as expected. |
| 4.6 | pass | Replaying with `HX-Target: something-else` returns the full navigation bundle, never a bare fragment. |
| 5.1 | pass | Edit opens "Edit Year 9 Maths" modal with Name field. |
| 5.2 | pass | Duplicate name returns 422, modal stays open with the uniqueness error under the field. |
| 5.3 | pass | Rename triggers one POST then one GET per leaf panel (Details/Course Registrations/Learners), each targeting its own region; modal closes, name updates everywhere except the (expected) stale sidebar disclosure. |
| 5.4 | pass | Reload shows the new name in h1 and sidebar disclosure. |
| 5.5 | pass | Rename-back persisted after reload. |
| 6.1 | pass | Create Cohort modal has Save / Save and add another; new cohort redirects to its detail page. |
| 6.2 | pass | Delete confirmation reads "Are you sure you want to delete QA Empty Cohort?", no cascade list. |
| 6.3 | pass | Confirming redirects to the list with the cohort gone. |
| 6.4 | pass | "Save and add another" keeps the modal open, refreshes the list behind it without a reload; second cohort's own Save lands on its detail page. |
| 6.5 | pass | `qa_educator` sees only its own cohort, no Create/Edit buttons; delete is blocked with a "still has 1 course progress record" message and Close only. |
| 6.6 | pass | DELETE to the correct (post-spec-§159) action URL returns 422 with the blocked reason and correct `Vary`; the plan's own URL is stale (see General notes). |
| 7.1 | pass | Learners list search/sort/clear all work without a reload. |
| 7.2 | pass | Learner detail has Details card (sentence-case labels) and a Cohorts card scoped to that learner. |
| 7.3 | pass | Learner with no cohort shows an empty table with the empty-state message, not an error. |
| 8.1 | pass | Course list shows Title/Visibility/Interest/Active Learners/Active Cohorts/Cohorts columns. |
| 8.2 | pass | Course detail scopes Cohort Registrations to the current organisation. |
| 8.3 | pass | Switching organisation on a course page keeps the same course and re-scopes Cohort Registrations. |
| 9.1 | pass | `org.educator` lands on a dashboard for one of its two organisations; switcher lists both. |
| 9.2 | pass | Switching organisation on the cohorts list re-renders list, URL and sidebar, and announces via `#scope-announcer`. |
| 9.3 | pass | Switching away from a Northside cohort detail redirects to the RPAS cohorts list with a notice that the cohort isn't in this organisation. |
| 9.4 | pass | `legacy.educator` is correctly scoped to Year 9 Maths only (list, detail 404s, Learners column). |
| 11.1 | pass | Learner course player renders with a 3-part course outline sidebar, no console errors. |
| 11.3 | pass | Page source has only whitespace around the content grid; htmx-config meta present. |
| 12.1 | pass | The four removed qa management commands are gone from `manage.py help`. |
| 12.2 | pass | No Course Progress tab/matrix remains; its tab URL 404s. |
| 12.3 | pass | No console/page errors and no Alpine `tabContainer` expression error after navigating tabs/sidebar. |

#### 1.3 / 1.4 / 1.5 — Dashboard reporting card and sidebar

![](screenshots/page-2026-09-26T14-18-54-143Z.png)

#### 2.1 / 3.1 — Cohorts list reached over htmx

![](screenshots/page-2026-09-26T14-19-42-999Z.png)

#### 3.2 / 3.3 / 3.4 — Cohort detail layout

![](screenshots/page-2026-09-26T14-20-07-693Z.png)

#### 3.7 — Learners card search narrows to Priya

![](screenshots/page-2026-09-26T14-21-12-015Z.png)

#### 5.1 — Edit Year 9 Maths modal

![](screenshots/page-2026-09-26T14-22-52-439Z.png)

#### 5.2 — Duplicate-name validation error

![](screenshots/page-2026-09-26T14-23-45-891Z.png)

#### 6.2 — Delete confirmation, no cascade list

![](screenshots/page-2026-09-26T14-24-29-988Z.png)

#### 6.4 — Save and add another keeps the modal open

![](screenshots/page-2026-09-26T14-24-47-901Z.png)

#### 6.5 — qa_educator's blocked delete

![](screenshots/page-qa-educator-delete-confirm.png)

#### 7.2 — Learner detail (Priya)

![](screenshots/page-learner-priya.png)

#### 8.1 — Course list columns

![](screenshots/page-courses-list.png)

#### 8.3 — Course detail after switching to Northside

![](screenshots/page-course-northside.png)

#### 9.2 — Cohorts list after switching organisation

![](screenshots/page-org-switch-cohorts.png)

#### 9.3 — Notice after switching away from a Northside cohort

![](screenshots/page-org-switch-notice.png)

#### 11.1 — Learner course player, desktop

![](screenshots/page-player-desktop.png)

### Mobile (375x812)

| Test | Status | Note |
| --- | --- | --- |
| 10.1 | pass | Sidebar closed on load; nav toggle opens a bottom sheet with switcher, TEACHING group and footer. |
| 10.2 | pass | Tapping Cohorts in the sheet is one XHR, no reload, sheet closes. |
| 10.3 | pass | Tab strip and three cards stack in one column; Details rows stack label above value; no page-level horizontal overflow; Edit modal fits the viewport. |
| 10.4 | pass | Device Back closes an open sheet before navigating. |
| 11.2 | pass | Course player outline becomes a bottom sheet below 1024px, closes with Escape. |

#### 10.1 — Mobile navigation sheet

![](screenshots/page-2026-09-26T14-30-02-491Z.png)

#### 10.2 — Cohorts list loaded from the sheet

![](screenshots/page-mobile-cohorts.png)

#### 10.3 — Cohort detail, single-column layout

![](screenshots/page-mobile-cohort-detail.png)

#### 10.3 — Edit modal fits the mobile viewport

![](screenshots/page-mobile-edit-modal.png)

#### 11.2 — Course outline as a mobile sheet

![](screenshots/page-mobile-player-sheet.png)

### Tablet (768x1024)

| Test | Status | Note |
| --- | --- | --- |
| 10.1 | pass | At 768px the tablet uses the mobile navigation pattern: hidden sidebar, toggle opens the bottom sheet. |
| 10.2 | pass | Tapping Learners in the sheet loads the list over htmx with no horizontal overflow. |
| 10.3 | pass | Cohort detail cards are full-width single column; Details renders as label/value columns; Learners table fits with wrapped headers. |

#### 10.1 — Tablet navigation sheet

![](screenshots/page-tablet-sheet.png)

#### 10.2 — Learners list on tablet

![](screenshots/page-tablet-learners.png)

#### 10.3 — Cohort detail on tablet

![](screenshots/page-tablet-cohort-detail.png)

## Bugs

No failures were found during this run. There are no bug records to report.

## Bug status

There are no bugs to track this run.

## General notes

- No failures, so no bug records and Step 13 (fix loop) had nothing to do.
- Test plan step 6.6 uses a stale URL: `<detail-url>/__actions/delete` returns 404 by design, because spec item 159 moved DeleteAction from `CohortInstanceView` onto `CohortDetailsPanel`. The working URL is `<detail-url>/__tabs/details/__panels/details/__actions/delete` (422 + `Vary` as expected). The plan text should be updated.
- Course list (8.1): the Active Learners, Active Cohorts and Cohorts columns are not organisation-scoped. Every organisation lists DemoDev's "QA Modal Cohort" against Content Widgets. Same code as main; declared via `CourseConfig.check_access_exempt_reason`; planned in `spec_dd/1. next/educator-interface-6-cohort-administration`.
- Instance pages (cohort, learner, course detail) have a browser tab title of "<Organisation> — <site>" with no instance name. Same as main, not required by this plan.
- Learner detail h1 is the model `__str__` ("y9.learner2@example.com - RPAS Training") rather than the learner's name.
- Duplicate-name error reads "Cohort with this Site, Organisation and Name already exists." (Django `unique_together` default wording that exposes "Site").
- Edit/create modal has an empty footer strip below the Save row (desktop and mobile).
- The org-switch "that cohort isn't in this organisation" notice (9.3) shows as a bottom-right toast; the plan says "inline notice". Judged a pass.
- Cohort Learners card has only 3 learners, so pagination in 3.6 was not exercised (the plan makes it conditional). Northside has no cohort course registrations, so 8.3's "lists only Northside cohorts" showed an empty table; scoping was otherwise confirmed by Content Widgets' detail omitting DemoDev's cohort.
- The seed command `qa_create_educator_modal_target` needs a `SITE_NAME` argument (DemoDev), which plan §0.2 omits. Its summary text also says Delete is "top of the page", which is now out of date.
- `/educator/` for the admin lands on the DemoDev organisation's dashboard (first organisation), not RPAS Training; the plan allows "remembered or first".
- Debug toolbar panels open by default in fresh browser contexts and can intercept clicks; hidden via its Hide button during the run.
- Observation from test 1.5: the admin persona's footer shows email only (no name line) because that user's first/last name fields are blank — a data characteristic of the seeded admin account, not a defect.

status: ok
reason: report rendered, 0 bugs documented
