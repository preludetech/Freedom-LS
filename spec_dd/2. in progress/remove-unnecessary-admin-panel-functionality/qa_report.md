# Frontend QA report: remove-unnecessary-admin-panel-functionality

Result: all tests passed. No failing records, no bug records.

## Methodology

Screenshots were collected into `spec_dd/2. in progress/remove-unnecessary-admin-panel-functionality/screenshots/`. Every image linked below exists beside this report. The run followed the plan in `3. frontend_qa.md` against the seeded dev site. It covered desktop for every test and mobile (375) and tablet (768) for the pages with front-end changes.

The branch was rebased onto main before QA: 35 commits replayed with no conflicts, 17,353 tests passed in the targeted tier, and the branch was pushed. The upstream-change review came back `unchanged`. The post-rebase front-end check was folded into this QA run, because it would visit the same QA-plan pages at the same three viewports.

## Diff scoping

Class: **FULL**. The diff touched 134 files. The front-end ones that triggered the class were:

- `freedom_ls/deadlines/templates/admin/deadlines/extend_deadline.html`
- `freedom_ls/deadlines/templates/admin/deadlines/pause_course.html`
- `freedom_ls/site_aware_models/static/site_aware_models/css/admin.css`

Nothing was skipped. All viewports and all plan tests ran.

## Smoke gate

Pass. Pages loaded: `/` and `/admin/`. The run did not abort.

## Design check

No design tests. There were no `design` records.

## Per-bug sections

None. There were no `bug` records.

## Layout probe

| Test | Viewport | URL | Screenshot | Result |
|---|---|---|---|---|
| 1 | desktop | /admin/ | [shot](screenshots/page-2026-11-24T16-09-43-347Z.png) | clean |
| 3 | desktop | /admin/freedom_ls_form_engine/formprogress/&lt;pk&gt;/change/ | [shot](screenshots/page-2026-11-24T16-10-29-561Z.png) | clean |
| 4 | desktop | /admin/freedom_ls_form_engine/questionanswerfile/ | [shot](screenshots/page-2026-11-24T16-11-04-728Z.png) | clean |
| 5 | desktop | /admin/freedom_ls_learner_progress/courseprogress/&lt;pk&gt;/change/ | [shot](screenshots/page-2026-11-24T16-11-48-249Z.png) | clean |
| 7 | desktop | /admin/freedom_ls_deadlines/learnercourseregistrationdeadlineconfig/add/ | [shot](screenshots/page-2026-11-24T16-14-02-106Z.png) | clean |
| 9 | desktop | /admin/freedom_ls_organisations/organisation/&lt;pk&gt;/permissions/ | [shot](screenshots/page-2026-11-24T16-14-47-108Z.png) | clean |
| 11 | desktop | /educator/organisations/qa-deadlines-org/cohorts/&lt;pk&gt; | [shot](screenshots/page-2026-11-24T16-15-32-682Z.png) | clean |
| 5 | mobile | /admin/freedom_ls_learner_progress/courseprogress/ | [shot](screenshots/page-2026-11-24T16-16-24-463Z.png) | clean |
| 3 | mobile | /admin/freedom_ls_form_engine/formprogress/&lt;pk&gt;/change/ | [shot](screenshots/page-2026-11-24T16-16-38-269Z.png) | clean |
| 7 | mobile | /admin/freedom_ls_deadlines/learnercourseregistrationdeadlineconfig/add/ | [shot](screenshots/page-2026-11-24T16-16-44-793Z.png) | clean |
| 11 | mobile | /educator/organisations/qa-deadlines-org/cohorts/&lt;pk&gt; | [shot](screenshots/page-2026-11-24T16-16-50-804Z.png) | clean |
| 5 | tablet | /admin/freedom_ls_learner_progress/courseprogress/ | [shot](screenshots/page-2026-11-24T16-16-59-661Z.png) | clean |
| 5b | tablet | /admin/freedom_ls_learner_progress/courseprogress/&lt;pk&gt;/change/ | [shot](screenshots/page-2026-11-24T16-17-06-765Z.png) | clean |
| 11 | tablet | /educator/organisations/qa-deadlines-org/cohorts/&lt;pk&gt; | [shot](screenshots/page-2026-11-24T16-17-16-187Z.png) | clean |
| 10 | desktop | /admin/freedom_ls_accounts/user/&lt;pk&gt;/delete/ | [shot](screenshots/page-2026-11-24T16-17-53-686Z.png) | clean |

## Test results

| Test | Viewport | Result | Notes |
|---|---|---|---|
| 1 | desktop | pass | The admin index has no Content engine or Learner management section. Form engine lists only Form progress records, Question answers and Question answer files. The other expected sections are present. The sidebar links to no removed model. |
| 2 | desktop | pass | All 7 removed admin URLs return 404. |
| 3 | desktop | pass | The changelist has 6 rows, no Add and no action dropdown. The by-form filter narrows correctly, including combined with completion. The sitting page renders the answers document read-only with only a Close button. The file answer downloads (200, attachment, application/pdf). The Application row links to the course application. `/add/` and `/<pk>/delete/` return 403. |
| 3 | mobile | pass | Two-column answers document, Download link visible, no overflow. |
| 4 | desktop | pass | Question answers (13 rows) and answer files (1 row) have no Add and no actions. Change pages are read-only. Download works. `/add/` and `/delete/` return 403. As the view-only `qa_reviewer`, the same pages open read-only. |
| 5 | desktop | pass | Course progress has no Add and no actions. Filters work, and there is no Learner filter. The paused record is read-only with no Pause/Resume/Extend. Deadlines show effective deadlines and policy. Pauses and extensions inlines are read-only. The Topics and Form attempts tabs link to read-only pages. `/pause/` redirects to the admin index and `/add/` returns 403. Topic progress and course form attempts filters narrow correctly. |
| 5 | mobile | pass | Rows render as cards with whole-word labels. Long values wrap and there is no horizontal scroll. |
| 5 | tablet | pass | Rows render as cards with right-aligned, wrapping values. |
| 5b | tablet | pass | The extended learner's record shows tabs, a Deadlines section, an empty Pauses inline and three read-only extension cards. No overflow. |
| 6 | desktop | pass | Course pauses and deadline extensions changelists render with a course dropdown filter and no Add. Change pages are read-only. |
| 7 | desktop | pass | All 10 add pages return 200. The deadline and messaging configs pick the learner by email plus Organisation (and Course) selects. A Course deadline config and a Learner registration deadline config saved and were then deleted. An unknown email shows a form error, not a 500. See the stale-plan note below. |
| 7 | mobile | pass | Email box and selects are full width with help text. No overflow. |
| 8 | desktop | pass | Both course application changelists have a Course dropdown filter that narrows. The change page shows course as plain text, with user and form sitting as links and the answers section rendering. |
| 9 | desktop | pass | The organisation page has no Cohorts or Learners inline and no learners link. The HR settings inline saves. Object permissions opens. Job titles list and add work. |
| 10 | desktop | pass | A user with a completed form sitting gets "Cannot delete user" with no confirm button. A user with no records can be deleted. The user and email address pages return 200. |
| 11 | desktop | pass | The educator cohort and learner pages render. No link points at a removed admin. |
| 11 | mobile | pass | Hamburger nav, stacked cards, lazy-loaded Needs attention. |
| 11 | tablet | pass | Six tabs on one row, details in three columns, Needs attention loads. |

## Data changes

| What changed | Made by | Files written |
|---|---|---|
| Loaded demo_content (`content_save ./demo_content DemoDev`) and ran `qa_create_form_first_course`, which `qa_create_standalone_form_sitting` needs but plan §0 does not list | test plan seed list | none |
| Created `qa_erase_blocked@email.com` (one completed Knowledge Check sitting) and `qa_erase_clean@email.com` (bare user) via the new command `qa_create_erase_users` | `sdd:qa-data-helper` | `freedom_ls/qa_helpers/management/commands/qa_create_erase_users.py`, `freedom_ls/qa_helpers/tests/management/commands/test_qa_create_erase_users.py` |

## Bug status

none (no `bug` records this run).

## General notes

Observations only, with no action attached to a bug.

- **Stale QA plan, two places.** Test 7 expects raw-id boxes for the learner and learner-registration pickers. The spec decided an email plus organisation/course picker instead, and the test passed under that decision. Section 0's seed list omits `qa_create_form_first_course`, which `qa_create_standalone_form_sitting` depends on. `content_save ./demo_content DemoDev` was also needed.
- **Stale doc sentence.** The upstream review noted one stale sentence in the fls-content plugin's `form-files.md` ("the admin shows it on the question"). The FormQuestion admin is gone.
- **Test 7 validation order.** With no course chosen, only "Course: This field is required" shows. The unknown-email error appears once a course is picked.
- **Test 3 full-page capture.** The sticky Close bar appears mid-page in the full-page screenshot. That is the capture of a sticky footer, not a layout fault.
- **Test 5 mobile.** The first card's Learner value sits under the collapsed debug toolbar tab but fits its cell.
- **Test 8 page title.** The title `CourseApplication(85, <uuid>)` is the model's deliberate ids-only `__str__`.
- **Console.** The only console error across the run was a `favicon.ico` 404.

status: ok · reason: report rendered, 0 bugs documented
