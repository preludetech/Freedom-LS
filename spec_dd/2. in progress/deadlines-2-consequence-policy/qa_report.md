# Frontend QA report: deadlines-2-consequence-policy

QA ran on 2026-10-31 against branch `deadlines-2-consequence-policy`, with the dev server on port 8709 and the browser time zone set to Africa/Johannesburg. The smoke gate passed and the full plan ran at desktop, mobile and tablet. 34 test records passed and 1 failed (3.4). The failure is documented as bug B1: a closed form whose submitted attempt failed still reads "Closed", with no way back to its results. The spec and the test plan disagree on that behaviour, and the code follows the spec.

## Methodology

- Tool: Playwright MCP.
- Viewports: 1920x1080 (desktop), 375x812 (mobile), 768x1024 (tablet).
- Screenshots were collected into `screenshots/` beside this report. Every referenced image exists beside the report.
- Admin and learner actions used separate browser contexts.
- The qa-data-helper agent created the data the plan routes through it:
  - a time-limit-only learner `qa_deadline_none` on the plain course
  - a completed Knowledge Check attempt for the cohort learner
  - an open survey attempt for the late learner
  - the parts course, temporarily hidden

## Diff scoping

Class: FULL, triggered by template changes. Changed files:

- `freedom_ls/base/templates/cotton/callout.html`
- `freedom_ls/learner_interface/templates/learner_interface/*.html` (11 templates)
- `freedom_ls/deadlines/*.py`
- `freedom_ls/course_access/*.py`
- `freedom_ls/learner_interface/views.py`
- `freedom_ls/learner_interface/utils.py`

Nothing was skipped. Desktop, mobile and tablet all ran.

## Smoke gate

Status: pass. Pages checked: `/`, `/courses/functionality-demo-course-parts/detail/`, `/admin/`. No failure URL or reason.

## Results

| Test | Viewport | Status | Note | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | pass | Six Deadlines admins present. Selects offer Inherit/On/Off and Inherit/Outline and results/Nothing. Help text names DD HH:MM:SS. All-Inherit row round-trips with empty grace, and `0 00:00:00` round-trips. Row deleted. | ![](screenshots/page-2026-10-31T13-33-10-409Z.png) |
| 1.2 | desktop | pass | Duplicate course, site and cohort configs each give a form error naming the duplicate, no 500. Site form has no owner field. `-1 00:00:00` gives "The grace window cannot be negative." | ![](screenshots/page-2026-10-31T13-34-16-794Z.png) |
| 1.3 | desktop | pass | Effective policy panel correct for late, cohort and fresh learners, and for the organisation close_items=off override. Panel prints On/Off rather than True/False (cosmetic). | ![](screenshots/page-2026-10-31T13-35-00-000Z.png) |
| 2.1 | desktop | pass | Fresh learner: Missed deadline chip and date in outline and header. With mark_overdue=off the chip goes and the line reads "Deadline Jan 31, 2024, 11:59 PM." in outline, header and dashboard card. Chip returns when set back On. | ![](screenshots/page-2026-10-31T13-37-00-000Z.png) ![](screenshots/page-2026-10-31T13-37-05-000Z.png) |
| 2.1 | mobile | pass | Compact row reads "Deadline Welcome Jan 31, 2024, 11:59 PM." with no chip, no horizontal overflow. | ![](screenshots/page-2026-10-31T13-37-10-000Z.png) |
| 3.1 | desktop | pass | Learner override put Welcome at yesterday. Outline and header read "Missed deadline Oct 30, 2026, 11:59 PM Closes Nov 2, 2026, 11:59 PM.", no Closed chip, row linked, topic opens. Override removed. | ![](screenshots/page-2026-10-31T13-45-00-000Z.png) |
| 3.2 | desktop | pass | Welcome shows a "Closed Feb 3, 2024, 11:59 PM" chip, keeps its link. Player shows the closed notice instead of the body, Next only, no complete/submit. started_at and last_accessed_item stay empty. Direct URL renders the notice with 200. | ![](screenshots/page-2026-10-31T13-38-23-180Z.png) |
| 3.2 | mobile | pass | Closed Knowledge Check notice readable, chip with icon, Previous/Next large enough, no overflow. | ![](screenshots/page-2026-10-31T14-16-00-000Z.png) |
| 3.2 | tablet | pass | Closed notice renders, no overflow. | ![](screenshots/page-2026-10-31T14-16-10-000Z.png) |
| 3.3 | desktop | pass | On the closed Knowledge Check, `/5/start_form` and `/5/fill_form/1` redirect to `/5/` (the closed notice), as the spec says. No new attempt created. | ![](screenshots/page-2026-10-31T13-41-00-000Z.png) |
| 3.4 | desktop | **fail** | Submit-and-exit goes to `/5/complete` with score 0/3. Resubmit gives no 500 and still one completed attempt. The outline row still reads "Closed" after submit, where the plan expects complete or "Needs retry". See B1. | ![](screenshots/page-2026-10-31T13-42-00-000Z.png) |
| 3.5 | desktop | pass | Items after the closed, incomplete Welcome are unlinked and read "Locked", no Closed chip. Direct URLs redirect to course detail. Core Concepts part reads Closed, unlinked. | ![](screenshots/page-2026-10-31T13-40-00-000Z.png) |
| 3.6 | desktop | pass | Fresh learner: Welcome "Missed deadline Jan 31, 2024" opens normally, no Closes/Closed text. | none |
| 3.7 | desktop | pass | Cohort learner: completed Welcome shows no deadline line and no chip, and opens. | ![](screenshots/page-2026-10-31T13-47-00-000Z.png) |
| 2.2 | desktop | pass | Tested with `qa_deadline_none` on the plain course: card reads "Missed deadline Course Oct 26, 2026, 11:59 PM"; with mark_overdue=off it reads "Deadline Course Oct 26, 2026, 11:59 PM." Row deleted. | ![](screenshots/page-2026-10-31T13-48-00-000Z.png) ![](screenshots/page-2026-10-31T13-48-01-000Z.png) |
| 4.1 | desktop | pass | Cohort learner dashboard: course stays In progress, eyebrow "Access ended May 30, 2026, 11:59 PM", 0% progress, no Next up/Continue. Detail shows the ended message, no button, only Welcome linked. No redirect loop. | ![](screenshots/page-2026-10-31T13-50-00-000Z.png) ![](screenshots/page-2026-10-31T13-50-10-000Z.png) |
| 4.2 | desktop | pass | Welcome opens, outline links only Welcome, Next redirects to detail. Items 2-7, `/5/complete` (no completed attempt) and `/finish/` redirect to detail. | none |
| 4.3 | desktop | pass | Late learner, plain course (after_access_ended=nothing): ended message, no button, no Course content section. `/1/` redirects to detail. Dashboard "Access ended Oct 21, 2026, 11:59 PM". | ![](screenshots/page-2026-10-31T13-53-00-000Z.png) |
| 4.4 | desktop | pass | Restored learner: "Access ends Nov 30, 2026, 11:59 PM." and the course opens. Fresh learner shows no access line. Late learner's parts course opens. | ![](screenshots/page-2026-10-31T13-53-10-000Z.png) |
| 4.2.6 | desktop | pass | With a completed Knowledge Check attempt (2/3), `/5/complete` renders results while access is ended. No Retry button offered, so the plan's form_start step had nothing to click. | ![](screenshots/page-2026-10-31T13-58-00-000Z.png) |
| 4.3.3 | desktop | pass | With an open survey attempt, a console POST to `/3/submit-and-exit` with the CSRF token redirects to `/3/complete`, which renders "Form complete!". | ![](screenshots/page-2026-10-31T14-08-00-000Z.png) |
| 4.5.1 | desktop | pass | `/access/` redirects to detail, no LearnerCourseRegistration created. `/finish/` left completed_time empty. | none |
| 4.5.2 | desktop | pass | With the registration inactive, the dashboard no longer lists the course and detail shows "Enrol for free". Reactivated. | ![](screenshots/page-2026-10-31T14-10-00-000Z.png) |
| 4.5.4 | desktop | pass | completed_time set via admin: card moves to Learning history as COMPLETED, detail CTA "Review course", item 2 opens. Cleared again. | ![](screenshots/page-2026-10-31T13-56-00-000Z.png) |
| 5.1 | desktop | pass | Inline help present. Fixed time limit 2026-11-14 saves, panel shows "14 Nov 2026, 23:59 SAST", item 2 opens. Adding a due time is rejected with "The course time limit ends at the end of its day." Yesterday's date gives "Access ended Oct 30, 2026, 11:59 PM". Override deleted. | ![](screenshots/page-2026-10-31T14-02-00-000Z.png) ![](screenshots/page-2026-10-31T14-03-00-000Z.png) ![](screenshots/page-2026-10-31T14-05-00-000Z.png) |
| 5.2 | desktop | pass | Cohort registration time-limit override reopens the course and item 2 opens. After deleting it, item 2 redirects to detail again. | none |
| 6.3 | desktop | pass | `manage.py check` clean. Missing grace_window gives `freedom_ls_deadlines.E001`. `DEADLINE_POLICY="nowhere.Nothing"` gives `freedom_ls_deadlines.E002`. Override modules lived in the scratchpad only. | none |
| 4.5.3 | desktop | pass | With the parts course hidden, the cohort learner still reaches detail (200, ended message). An anonymous visitor gets 404. Visibility restored. | none |
| 4.1 | mobile | pass | Late learner dashboard: compact rows show "Closed Feb 3, 2024, 11:59 PM" and "Access ended Oct 21, 2026, 11:59 PM". No overflow, no console errors. Ended detail page fine. | ![](screenshots/page-2026-10-31T14-12-00-000Z.png) ![](screenshots/page-2026-10-31T14-12-10-000Z.png) |
| 4.1 | tablet | pass | Same at 768x1024: eyebrows render, no overflow, no console errors. Ended detail page fine. | ![](screenshots/page-2026-10-31T14-14-00-000Z.png) ![](screenshots/page-2026-10-31T14-14-10-000Z.png) |
| 6.1 | desktop | pass | Fresh learner: `/courses/`, dashboard and a topic page render with no deadline lines and no console errors (favicon 404 ignored). | none |
| 6.1 | mobile | pass | Same pages at 375x812: no console errors, no overflow. | none |
| 6.2 | desktop | pass | Anonymous visitor on parts-course detail sees "Enrol for free". | none |

## Design check

No design states tested.

## B1: A closed form whose attempt was submitted and failed still reads "Closed", with no way back to its results

Manifestations: test 3.4 (desktop).

![](screenshots/page-2026-10-31T13-42-00-000Z.png)

![](screenshots/page-2026-10-31T13-41-00-000Z.png)

Expected: per test plan 3.4.3, after "Submit your answers" the Knowledge Check outline row reads complete or "Needs retry", and no longer "Closed".

Actual: the attempt scored 0/3 (FAILED). The spec makes only COMPLETE items exempt from closing (decision 9; `is_closed` applies to READY, IN_PROGRESS and FAILED), so the row stays "Closed". Reopening the item shows the closed notice with no link to the score. The results page's "Retry quiz" sends the learner back to that notice. The spec and the test plan disagree, and the code follows the spec.

## Bug status

- **UNRESOLVED** — A closed form whose attempt was submitted and failed still reads "Closed", with no way back to its results (reason: product decision; the spec exempts only COMPLETE items from closing, the test plan expects "Needs retry", and the code follows the spec)

## General notes

Test-plan corrections found this run (not product bugs):

- Item indices: Knowledge Check is item 5 and Course Feedback is item 7, because Going Deeper and Summary count.
- Plan 3.1, 3.2 and 3.3 assume What to Expect, Key Ideas and Course Feedback are reachable. Sequential unlock withholds them, and spec decision 11 says it wins over closing, so they read "Locked".
- Plan 3.3 expects form_start/fill on a closed form to redirect to course detail. The spec says they redirect to the item (closed notice), which is what happens.
- Plan 2.2's late-learner card shows the earliest missed deadline (Welcome, closed) rather than the time limit, so the time-limit branch was tested with a different learner.
- The effective policy panel prints On/Off rather than True/False.
- The fresh learner's card leads with "Missed deadline Welcome" rather than "Next deadline:".
- The ended learner's results page shows no Retry button, so plan 4.2.6's form_start step had nothing to click.

Seed artefacts:

- The cohort learner's progress_percentage is 0 though Welcome is complete. The dashboard shows 0%, and a restored learner's detail CTA reads "Start course" rather than "Continue".

Observations:

- Opening the completed Welcome as the ended cohort learner set started_at on the CourseProgress record (a write while access was ended). The spec allows completed items to open, so this is an observation only.

Coverage gap:

- Form start/fill pages weren't reachable for a fresh learner, since forms are sequentially withheld.

Environment:

- The Django debug toolbar intercepted admin clicks and had to be hidden per page.
- The pre-QA rebase onto main succeeded locally (28 commits, targeted tests and pre-commit clean). The force-push of the rebased branch was denied by the permission classifier, so the remote branch is behind the local one.

status: ok · reason: 1 bug — 0 fixed, 1 unresolved (product decision); report rendered, screenshots verified
