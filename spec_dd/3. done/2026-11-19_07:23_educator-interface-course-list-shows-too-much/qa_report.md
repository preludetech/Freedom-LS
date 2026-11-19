# Frontend QA report: educator-interface-course-list-shows-too-much

## Methodology

- Playwright MCP at three viewports: desktop 1920x1080, mobile 375x812, tablet 768x1024.
- Screenshots were collected into `screenshots/` beside this report, and every image referenced here exists there.
- Before QA, a pre-step rebase onto main replayed 34 commits and resolved one conflict in `freedom_ls/educator_interface/forms.py`. The resolution kept main's `files` argument and the branch's `CourseChoiceField`. The full test suite then passed (15941 passed).
- The rebase's front-end check was covered by this QA run itself, which visits the same plan URLs at all three viewports.
- Dev-tool overlays (debug toolbar, branch badge) were hidden before shots.
- Test plan: `3. frontend_qa.md` in this spec directory.

## Diff scoping

Classification: **FULL**. Skipped: nothing.

Changed areas considered:
- `freedom_ls/educator_interface/templates/...`
- `freedom_ls/educator_interface/*.py`
- `freedom_ls/learner_management/queries.py`
- `freedom_ls/content_engine/*`
- `demo_content/functionality_demo_organisation_course_northwind*`

## Smoke gate

Status: **pass**. Pages checked: `/`, `/educator/organisations/harbour-college/courses`. No failure URL or reason.

## Results by test

| Test | Viewport | Status | Screenshot | Notes |
|---|---|---|---|---|
| 1.1 | desktop | pass | ![](screenshots/page-2026-11-19T04-43-47-759Z.png) | Page 1 of 2: ten no-organisation demo courses, no Forklift. The capture-check shot `page-2026-11-19T04-43-38-595Z.png` has the debug toolbar open, so it was re-shot after hiding it. |
| 1.1 | desktop | pass | ![](screenshots/page-2026-11-19T04-44-00-596Z.png) | Page 2: Northwind Workplace Safety Essentials with muted "Shared by Northwind Logistics" line, Harbour's plain. 15 courses total, no Forklift Safety Basics on either page. |
| 1.2 | desktop | pass | ![](screenshots/page-2026-11-19T04-44-19-613Z.png) | Shared Northwind course detail: Details, Course content outline (Course details and Safety on site, each with Preview), Cohort and Direct registration panels. |
| 1.2 | desktop | pass | ![](screenshots/page-2026-11-19T04-44-28-222Z.png) | Course details preview dialog titled "Workplace Safety Essentials (Preview)", hero names Northwind Logistics, closes. See general note 2. |
| 1.2 | desktop | pass | ![](screenshots/page-2026-11-19T04-44-46-308Z.png) | Topic preview "Safety on site (Preview)" is read-only (no inputs). See general note 3. |
| 1.3 | desktop | pass | ![](screenshots/page-2026-11-19T04-45-04-186Z.png) | Forklift course detail URL returns 404. Direct preview_course_details action URL returns 404, while the same action on the shared course returns 200. No Forklift text leaked. See general note 1. |
| 1.4 | desktop | pass | ![](screenshots/page-2026-11-19T04-45-31-496Z.png) | Cohorts course filter lists "Workplace Safety Essentials (Northwind Logistics)" and the plain "Workplace Safety Essentials", no Forklift. The learners list filter is identical: ![](screenshots/page-2026-11-19T04-45-36-754Z.png) |
| 1.4 | desktop | pass | ![](screenshots/page-2026-11-19T04-46-01-141Z.png) | Cohort register picker ![](screenshots/page-2026-11-19T04-45-54-515Z.png) offers the owner-named shared course and Harbour's plain one, no Forklift. Registering on the shared course adds an Active row with "Shared by Northwind Logistics". |
| 1.4 | desktop | pass | ![](screenshots/page-2026-11-19T04-46-32-923Z.png) | Solo learner register picker ![](screenshots/page-2026-11-19T04-46-23-369Z.png) and the bulk register picker on the learners list have the same contents, no Forklift. Both cancelled. |
| 3 | desktop | pass | ![](screenshots/page-2026-11-19T04-47-06-812Z.png) | Northwind educator Courses list: Forklift Safety Basics and Northwind Workplace Safety Essentials (own, no Shared-by line) plus no-organisation courses, 15 total, no Harbour course. A Harbour course id under northwind-logistics returns 404. |
| 4.1 | desktop | pass | ![](screenshots/page-2026-11-19T04-47-22-581Z.png) | qa_harbour_learner opens Northwind Workplace Safety Essentials from the dashboard, and topic "Safety on site" renders. |
| 4.2 | desktop | pass | ![](screenshots/page-2026-11-19T04-47-43-819Z.png) | qa_harbour_solo browse lists both Northwind public courses. The Forklift detail offers "Enrol for free" ![](screenshots/page-2026-11-19T04-47-36-437Z.png), and joining opens the course topic. See general note 4. |
| 1.1 | mobile | pass | ![](screenshots/page-2026-11-19T04-48-15-823Z.png) | Card layout, "Shared by Northwind Logistics" under the title inside the card, no horizontal scroll. The earlier shot `page-2026-11-19T04-48-08-354Z.png` had the fixed dev branch badge over that line, so it was re-shot with dev badges hidden. |
| 1.1 | tablet | pass | ![](screenshots/page-2026-11-19T04-48-26-463Z.png) | Table layout, "Shared by Northwind Logistics" wraps inside the Title cell, page scrollWidth 768. |
| 2.1 | desktop | pass | ![](screenshots/page-2026-11-19T04-50-57-965Z.png) | Share revoked. The Courses list still lists the Northwind course with its Shared-by line (held by the cohort registration). The detail shows Details and registration panels, and the Course content panel reads "Content preview isn't shared with your organisation." with no outline and no Preview buttons. Direct preview_course_details URL returns 404. |
| 2.1 | desktop | pass | ![](screenshots/page-2026-11-19T04-51-11-895Z.png) | Solo learner register picker no longer offers Northwind Workplace Safety Essentials (only Harbour's plain one). Closed without registering. |
| 2.1 | mobile | pass | ![](screenshots/page-2026-11-19T04-51-19-976Z.png) | Not-shared message centred in the Course content card, cards stack, no horizontal scroll. |
| 2.1 | tablet | pass | ![](screenshots/page-2026-11-19T04-51-28-176Z.png) | Panels full width, tables fit, not-shared message centred. |
| 2.2 | desktop | **fail** | ![](screenshots/page-2026-11-19T04-54-06-389Z.png) | The plan's step 2 cannot be followed: the Registrations row for the inactive registration on the no-longer-shared course shows no Reactivate button (registration-action-slot empty). See bug B1. |
| 2.3 | desktop | pass | ![](screenshots/page-2026-11-19T04-54-28-856Z.png) | course.md restored with git checkout and content_save re-run, `git status -- demo_content` clean. The course detail outline and Preview buttons are back. The Reactivate button reappears on the row, and confirming reactivates it (row Active, Deactivate offered). |

## Design check

No design states tested.

## B1: QA plan section 2.2 expects a Reactivate button the code now hides for an unavailable course

Manifestations:
- Test 2.2, desktop.

Screenshot:

![](screenshots/page-2026-11-19T04-54-06-389Z.png)

Expected (per `3. frontend_qa.md` section 2.2): the Registrations row offers Reactivate. Pressing it and confirming keeps the dialog open with "This course is not open to the organisation."

Actual: there is no Reactivate button on the row. `RegistrationRow.can_reactivate`, added in review-fix commit 2c318d39c ("Offer Reactivate only for a course available to the learner's organisation"), hides it. The server-side refusal still works when the `reactivate_registration` action is opened directly: confirming keeps the dialog open with "This course is not open to the organisation." and the row stays Inactive. The plan and the code disagree. Which is right is a product decision, and the plan likely needs updating to "no Reactivate is offered".

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1.1 | desktop | /educator/organisations/harbour-college/courses | ![](screenshots/page-2026-11-19T04-43-38-595Z.png) | clean |
| 1.1 | desktop | /educator/organisations/harbour-college/courses?courses-page=2 | ![](screenshots/page-2026-11-19T04-44-00-596Z.png) | clean |
| 1.2 | desktop | /educator/organisations/harbour-college/courses/26c2e0d5-534f-40dc-86de-8218355233e5 | ![](screenshots/page-2026-11-19T04-44-19-613Z.png) | clean |
| 1.1 | mobile | /educator/organisations/harbour-college/courses?courses-page=2 | ![](screenshots/page-2026-11-19T04-48-15-823Z.png) | clean |
| 1.1 | tablet | /educator/organisations/harbour-college/courses?courses-page=2 | ![](screenshots/page-2026-11-19T04-48-26-463Z.png) | clean |
| 2.1 | desktop | /educator/organisations/harbour-college/courses/26c2e0d5-534f-40dc-86de-8218355233e5 | ![](screenshots/page-2026-11-19T04-50-57-965Z.png) | clean |
| 2.1 | mobile | /educator/organisations/harbour-college/courses/26c2e0d5-534f-40dc-86de-8218355233e5 | ![](screenshots/page-2026-11-19T04-51-19-976Z.png) | clean |
| 2.1 | tablet | /educator/organisations/harbour-college/courses/26c2e0d5-534f-40dc-86de-8218355233e5 | ![](screenshots/page-2026-11-19T04-51-28-176Z.png) | clean |

## Data changes

| What | Via | Files |
|---|---|---|
| Loaded demo_content into DemoDev | content_save (test plan section 0.2 seed) | none |
| Created or reused QA educators (Harbour, Northwind), QA Harbour Cohort with qa_harbour_learner, and qa_harbour_solo. Removed a stale cohort registration and a stale solo registration left from prior-run data, plus their empty CourseProgress rows. | sdd:qa-data-helper | `freedom_ls/qa_helpers/management/commands/qa_create_org_course_scope_scenario.py` |
| Deleted `shared_with:` from `demo_content/functionality_demo_organisation_course_northwind/course.md` and re-ran content_save (restored in 2.3) | test plan section 2.1 steps 1-2 | none |
| Created inactive LearnerCourseRegistration 54e5c603-e33e-45f6-a4da-1df6304308c1 for qa_harbour_solo on Northwind Workplace Safety Essentials (unshared at the time) | sdd:qa-data-helper | `.claude/agent-memory/sdd-qa-data-helper/reference_org_course_registration.md` |

## Bug status

| Bug | Title | Status |
|---|---|---|
| B1 | QA plan section 2.2 expects a Reactivate button the code now hides for an unavailable course | **UNRESOLVED** (reason: the QA plan and the code disagree on whether Reactivate shows for a course no longer available; choosing which is right is a product decision, so no auto-fix) |

## General notes

1. Test 1.3's "not-found page" is Django's DEBUG technical 404 in dev, raised by the educator interface view. That is correct for DEBUG.
2. The course details preview dialog title is "Workplace Safety Essentials (Preview)" without the owner. The spec limits owner-naming in titles to register dialogs, so this passes.
3. The topic preview's centred reading column comes from the earlier course-content-preview spec (max-w-reading) and is intended.
4. A Harbour learner's self-enrolment on Northwind's unshared public course (test 4.2) does not appear on that learner's educator page. This is pre-existing behaviour, not this branch. The source probe (`.sdd-work/qa_probe_self-enrol-registration-hidden.md`) found that the educator panels do not filter by course: `LearnerRegistrationsPanel` queries `learner=<the Learner row viewed>` (`freedom_ls/educator_interface/views.py:838-842`). Self-enrol (`freedom_ls/learner_interface/views.py:1099-1105`) calls `own_organisation_for_course(request.user, course) or get_default_organisation(site)`. Harbour does not own the course (`freedom_ls/learner_management/queries.py:446-455`), so the result falls back to the default organisation. `self_register` then calls `ensure_learner(user, default_org)` (`freedom_ls/learner_management/learner_actions.py:348-372`), which finds or creates a separate Learner row and files the registration there. The public-course gate passes (`open_to_organisation_expression`, `queries.py:283-299`). The spec's `research_codebase.md` (lines 18-25) already records this fallback and says the write-path gate must not narrow so the self-join keeps working. The branch changes educator visibility only, not `self_register` or the Learner chosen. The probe did not read `visible_registrations_with_progress`, so the Courses tab narrowing is unchecked. It is a quirk worth a follow-up.
5. The Northwind educator sees 0 active learners and cohorts on its own shared course although Harbour's cohort is registered. Counts are scoped to the viewing organisation, which is consistent with isolation.

status: ok · reason: 1 bug — 0 fixed, 1 unresolved (red lane: product decision); report rendered, screenshots verified
