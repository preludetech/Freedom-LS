# Frontend QA report: organisation-courses

## Methodology

- Driven manually with Playwright MCP against a dev server on port 8504 running branch `organisation-courses`.
- The dev DB was wiped and reseeded from the plan's §0 (`3. frontend_qa.md`).
- Screenshots are collected in `screenshots/` beside this report. Every image referenced here exists in that folder.
- A pre-step rebase onto main was done first. Its conflicts were import-only, and one post-rebase test-import fix commit was needed. The full suite then passed (9402 passed).
- The rebase's front-end smoke check was folded into this run's three-viewport matrix (desktop 1920, tablet 768, mobile 375). See the `frontend-check` record below: the same pages were visited at the same three viewports, with no 500, no traceback, nav and main present, and no error-level console entries apart from expected 404 resource loads.

## Diff scoping

- Class: **FULL**.
- Triggered by these changed template files:
  - `freedom_ls/learner_interface/templates/cotton/organisation-byline.html`
  - `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`
  - `freedom_ls/learner_interface/templates/learner_interface/partials/course_organisation_chip.html`
  - `freedom_ls/educator_interface/templates/educator_interface/modal/reregister_confirmation.html`
- Skipped: nothing. Desktop, mobile and tablet all ran.

## Smoke gate

Status: **pass**. Pages checked:

- `http://127.0.0.1:8504/` (dashboard as demodev_s1)
- `http://127.0.0.1:8504/courses/workplace-safety-essentials-2/detail/` (course detail as demodev_s1)

## Results

### Scenario 1: Learner outside any organisation (demodev_s1)

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 1.2 | desktop | pass | ![](screenshots/page-2026-10-25T11-56-49-607Z.png) | s1 dashboard: one Northwind "Workplace Safety Essentials" card (byline "Northwind Logistics"); no Harbour card; other cards have no byline. |
| 1.3 | desktop | pass | ![](screenshots/page-2026-10-25T11-56-58-218Z.png) | /courses/ lists only the Northwind course; Harbour absent. No byline on the all-courses list (out of scope per spec). |
| 1.4 | desktop | pass | — | As s1: the Harbour course's detail, player home, /1/ and /access/ all return 404. |
| 1.5 | desktop | pass | ![](screenshots/page-2026-10-25T11-57-10-281Z.png) | Northwind detail page renders; start button reads "Enrol for free". |
| 1.6 | desktop | pass | ![](screenshots/page-2026-10-25T11-57-23-307Z.png) | Enrol lands in the player (also ![](screenshots/page-2026-10-25T11-57-16-217Z.png)). In progress shows the Northwind card with no byline. |
| 1.7 | desktop | pass | ![](screenshots/page-2026-10-25T11-57-55-414Z.png) | Admin registration learner reads "demodev_s1@email.com - DemoDev". The changelist column shows only "demodev_s1". |

### Scenario 2: Organisation learner (demodev_s2, Harbour College)

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 2.1 | desktop | pass | — | Admin Learner add page (select2 autocomplete) saved a Harbour College Learner row for demodev_s2. |
| 2.3 | desktop | pass | ![](screenshots/page-2026-10-25T12-00-08-928Z.png) | Harbour card with muted byline "Harbour College" under the title (name only, no logo) on Start here page 1. Northwind card with byline on page 2 (also ![](screenshots/page-2026-10-25T12-00-07-459Z.png)). |
| 2.4 | desktop | pass | — | Harbour detail returns 200 for s2; "Enrol for free" leads into the player. |
| 2.5 | desktop | pass | ![](screenshots/page-2026-10-25T12-00-29-927Z.png) | Player outline chip reads "HC Harbour College". In progress shows the Harbour card with byline (also ![](screenshots/page-2026-10-25T12-00-41-470Z.png)). |
| 2.5 | mobile | pass | ![](screenshots/page-mobile-player-outline.png) | "Open course outline" opens a bottom sheet; chip shows "HC / Harbour College" (initials, logo cleared). |
| 2.5 | tablet | pass | ![](screenshots/page-tablet-player.png) | Player at 768 renders, 200, no horizontal scroll. |
| 2.6 | desktop | pass | ![](screenshots/page-2026-10-25T12-01-18-146Z.png) | Admin registration reads "demodev_s2@email.com - Harbour College - Workplace Safety Essentials". |
| 2.7 | desktop | pass | ![](screenshots/page-2026-10-25T12-00-51-533Z.png) | Northwind enrol works; admin registration reads "demodev_s2@email.com - DemoDev". Northwind In progress card has no byline; Harbour card keeps its byline. |

### Scenario 3: Deactivating the organisation Learner row

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 3.1 | desktop | pass | — | "Is active" unticked on s2's Harbour College Learner row in admin; saved. |
| 3.2 | desktop | **fail** | ![](screenshots/page-2026-10-25T12-02-39-418Z.png) | Learner row inactive, registration still active: Harbour card gone from In progress, player /1/ returns 404 (![](screenshots/page-2026-10-25T12-02-38-586Z.png)), /access/ returns 404 instead of redirecting to detail. See B1. |
| 3.3 | desktop | pass | — | With the registration also deactivated: no Harbour card; detail page 404. |
| 3.4 | desktop | pass | — | Learner row and registration reactivated through admin. |

### Scenario 4: Admin registration guards

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 4.3 | desktop | pass | ![](screenshots/page-2026-10-25T12-03-40-877Z.png) | LearnerCourseRegistration for demodev_s1 (DemoDev) + Harbour course not saved; course field error "This course is not open to the organisation." The course autocomplete offers two identical "Workplace Safety Essentials" options. |
| 4.4 | desktop | pass | — | Northwind for demodev_s1 hit the unique-together error (Scenario 1 had already registered s1; plan ordering clash, not a bug). Same save for demodev_s3 went through. |
| 4.5 | desktop | pass | ![](screenshots/page-cohort-refusal.png) | CohortCourseRegistration: Cohort 2025.03.04 + Harbour refused with the same message; Northwind saved, then deactivated. |
| 4.6 | desktop | pass | ![](screenshots/page-rule-refusal.png) | RegistrationRule: DemoDev + Harbour refused; Harbour College + Harbour saved ("QA rule"). |

### Scenario 5: Course admin

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 5.2 | desktop | pass | ![](screenshots/page-course-admin-filter.png) | Changelist has an "Organisations" column (Harbour College / Northwind Logistics on the two rows, empty elsewhere). "By organisations" filter for Harbour College leaves one row. |
| 5.3 | desktop | pass | ![](screenshots/page-course-admin-harbour.png) | Harbour change page: Organisations "Harbour College" and Audience "Organisation learners" read-only in first fieldset. Northwind shows "Northwind Logistics" / "Public". |

### Scenario 6: Educator interface

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 6.2 | desktop | pass | ![](screenshots/page-educator-courses-demodev-p2.png) | Superuser at /educator/organisations/demodev/courses (page 2): every no-organisation course plus Northwind; no Harbour course. |
| 6.3 | desktop | pass | ![](screenshots/page-educator-courses-harbour-college-p2.png) | Harbour College Courses list has both Harbour and Northwind plus shared courses. The two rows both read "Workplace Safety Essentials". |
| 6.3 | mobile | pass | ![](screenshots/page-mobile-educator-courses.png) | Courses list at 375 switches to stacked cards; no horizontal scroll. |
| 6.3 | tablet | pass | ![](screenshots/page-tablet-educator-courses.png) | Table at 768 fits (718px) inside an overflow-x:auto wrapper; no page scroll. |
| 6.4 | desktop | pass | ![](screenshots/page-2026-10-25T12-08-10-734Z.png) | Cohort 2025.03.04 > Courses > Register: picker offers Northwind and shared published courses; no Harbour. |
| 6.4 | mobile | pass | ![](screenshots/page-mobile-educator-register.png) | Register modal at 375 is full-width; picker has no Harbour; no horizontal scroll. |
| 6.4 | tablet | pass | ![](screenshots/page-tablet-educator-register.png) | Register modal at 768 centred (512px wide); picker has no Harbour. |
| 6.5 | desktop | pass | ![](screenshots/page-educator-learner-register.png) | Learner demodev_s10 > Register for course: same picker contents as cohort picker. |
| 6.6 | desktop | pass | ![](screenshots/page-educator-denied.png) | Out-of-organisation Harbour course URL returns 404 (OrganisationScopeDenied, an Http404 subclass); course not shown. No separate "denied" page exists, by existing design. |

### Scenario 7: Course card embed

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 7.2 | desktop | pass | ![](screenshots/page-2026-10-25T12-09-18-969Z.png) | Temporary `<c-course-card>` embeds placed in the public article "Getting started with articles" (reverted). As demodev_s1: Northwind card renders; Harbour embed renders nothing, no error. |

### Scenario 8: Content loading

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 8.2 | desktop | pass | — | With `organisations: [no-such-org]`, content_save exits 1 with `ValueError: Unknown organisations ['no-such-org'] ...` and valid slugs listed. Load is atomic; course keeps harbour-college / organisation_learners. Error surfaces as a raw traceback. |
| 8.3 | desktop | pass | — | After reverting the file, content_save succeeds. |

### Scenario 9: Responsive, visibility override and anonymous

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 9.2 | desktop | pass | ![](screenshots/page-s2-dashboard-1280.png) | s2 dashboard at 1920 and 1280: no horizontal scroll; byline is a single 20px line (nowrap, ellipsis). Long organisation name truncates with an ellipsis at 1920/1280/768/375; card width unchanged (![](screenshots/page-s2-logo-1280.png)). |
| 9.2 | mobile | pass | ![](screenshots/page-mobile-dashboard.png) | s2 at 375: dashboard, Harbour detail, player and /courses/ all 200; no horizontal scroll; header nav present; no console errors; byline on one line with ellipsis. |
| 9.2 | tablet | pass | ![](screenshots/page-tablet-dashboard.png) | s2 at 768: two-column grid; Harbour byline under title, Northwind without; all pages 200; no horizontal scroll; no console errors. |
| 9.3 | mobile | pass | ![](screenshots/element-2026-10-25T12-11-09-863Z.png) | With a logo on Harbour College: 72x24 opaque (white background) logo box before the name, level with text. img alt="" (decorative), so the name is read once. Checked at 375/768/1280/1920. |
| 9.4 | desktop | pass | ![](screenshots/page-2026-10-25T11-56-05-471Z.png) | Anonymous dashboard: Northwind card with "Free" badge and byline "Northwind Logistics"; no Harbour card. Harbour detail returns 404 (![](screenshots/page-2026-10-25T11-56-16-971Z.png)). |
| 9.5 | desktop | pass | ![](screenshots/page-2026-10-25T12-12-25-701Z.png) | Override on: demodev@email.com (not in Harbour College) sees the Harbour card with byline; Harbour detail returns 200. The plan's env-var step did not work as written (see General notes). |

### Cross-cutting

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| frontend-check | desktop | pass | — | The pre-step rebase's front-end smoke check (plan pages at 1920/375/768: no 500, no traceback, nav and main present, no error-level console entries other than expected 404 loads) was folded into this run's matrix. |

## Design check

No design states tested.

## Bug B1: A registration through an inactive organisation Learner row loses access to the organisation course

**Manifestations**

- Test 3.2, desktop

**Screenshots**

![](screenshots/page-2026-10-25T12-02-39-418Z.png)

![](screenshots/page-2026-10-25T12-02-38-586Z.png)

**Expected**

Test plan Scenario 3.2: after the learner's Harbour College Learner row is deactivated, the active registration still exempts them from the audience rule. The Harbour course stays in In progress with its byline, the player renders, and `/access/` redirects to the detail page without re-registering.

**Actual**

The Harbour card disappears from the dashboard, and the player, detail and `/access/` URLs all return 404. `is_registered_for_course` and `is_registered_for_course_expression` only count registrations whose `learner__is_active=True`. The branch has a test asserting this 404 (`test_initiate_access_deactivated_learner_of_the_course_organisation_gets_404`). The spec's "in the audience" definition ("or the user is registered for it") does not say whether a registration through an inactive Learner row counts.

## Bug status

- **RESOLVED (working as intended)** — A registration through an inactive organisation Learner row loses access to the organisation course (reason: red lane — the test plan expects access to be kept, while the code and a branch test (`test_initiate_access_deactivated_learner_of_the_course_organisation_gets_404`) deliberately 404; choosing which is right is a product decision, and it is access-control behaviour). Decision: 404 is correct; a registration through a deactivated Learner row grants no access. The spec, plan and QA plan Scenario 3 now say so; no code change.

## General notes

- The plan's `/courses/<slug>/` URL is the login-required player home. The public detail page is `/courses/<slug>/detail/`.
- The admin and educator course pickers and lists show two identical "Workplace Safety Essentials" entries that cannot be told apart.
- The admin registration changelist shows only the username in the learner column, while the change page shows the full learner label.
- Scenario 4.4 clashed with Scenario 1's existing registration for demodev_s1, so demodev_s3 was used instead.
- Content Widgets is `coming_soon`, so the embed check (7.2) used the public articles page.
- The unknown-slug error from content_save surfaces as a raw traceback, unlike the formatted YAML-error output.
- The plan's override step (env var) does not work because `config/settings_dev.py` hard-codes `OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE = False` and never reads the environment. The test flipped it temporarily, then reverted it.
- Scenario 6.6 gives a 404 rather than a distinct "denied" page, by existing design.
- The Harbour College logo set for 9.3 was cleared again when the organisation name was restored.

status: ok
reason: 1 bug — 0 fixed, 1 unresolved; report rendered, screenshots verified
