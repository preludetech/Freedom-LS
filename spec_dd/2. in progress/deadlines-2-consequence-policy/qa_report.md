# Frontend QA report: deadlines-2-consequence-policy

This run tested the deadline consequence policy against the test plan in `3. frontend_qa.md`: the Deadlines admin configuration, deadline chips and lines, closed items, ended course access, the course time limit override, regression pages, and system checks. There are 35 test records: 34 pass and 1 fails (3.5). One bug was found (B1): Locked outline rows past their close instant still say "Closes <past date>."

## Methodology

- Playwright MCP against a dev server on port 8557 for branch `deadlines-2-consequence-policy`.
- Browser time zone: Africa/Johannesburg.
- Viewports: 1920x1080 (desktop), 375x812 (mobile), 768x1024 (tablet).
- Screenshots were collected into `screenshots/` beside this report, and every referenced image exists there.
- The section 0 seed ran: `content_save demo_content DemoDev` and `qa_create_deadlines_seed`.
- Extra data was made through the qa-data-helper agent:
  - `qa_deadline_timelimit@email.com`, a learner whose only missed deadline is the course time limit.
  - Five completed topics for the late learner, so sequential unlock offers Course Feedback.
  - A passed Knowledge Check attempt for the cohort learner.
  - An open survey attempt on the plain course for the late learner.
  - A temporary hidden visibility on the parts course (restored).
- Admin config and override changes were made through the admin and removed after each test.
- The run started with a rebase onto main (24 commits replayed, no conflicts). The pre-step front-end smoke check was not run separately, because this full QA run covers the same pages.

## Diff scoping

Class: FULL. Front-end files among the 64 changed paths that triggered it:

- `freedom_ls/base/templates/cotton/callout.html`
- `freedom_ls/learner_interface/templates/learner_interface/_course_base.html`
- `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`
- `freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`
- `freedom_ls/learner_interface/templates/learner_interface/course_item_closed.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_deadline_line.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html`
- `freedom_ls/learner_interface/templates/learner_interface/partials/deadline_labels.html`

Nothing was skipped. Everything ran at desktop, mobile and tablet.

## Smoke gate

Status: pass. Pages checked: `/` and `/courses/functionality-demo-course-parts/detail/`. No failure.

## Results

| Test | Viewport | Status | Note | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | pass | Six Deadlines admins listed; Inherit/On/Off selects; all-Inherit row saves and reopens unchanged | ![](screenshots/page-2026-10-30T17-40-49-871Z.png) |
| 1.2 | desktop | pass | Duplicate course/site/cohort configs refused with form errors; negative grace gives a field error, no IntegrityError | ![](screenshots/page-2026-10-30T17-42-48-872Z.png) |
| 1.3 | desktop | pass | Effective-policy panel shows the right value and source for late, cohort and fresh learners | ![](screenshots/page-2026-10-30T17-44-08-613Z.png) |
| 2.1 | desktop | pass | mark_overdue off removes the chip and leaves "Deadline ..." text; back on restores it | ![](screenshots/page-2026-10-30T17-44-59-135Z.png) |
| 2.1 | mobile | pass | Compact card reads "Deadline Welcome Jan 31, 2024, 11:59 PM." with no chip; no overflow | ![](screenshots/page-2026-10-30T17-45-20-270Z.png) |
| 2.2 | desktop | pass | Plan's late learner shows Welcome, not the time limit; separate time-limit learner used and passes | ![](screenshots/page-2026-10-30T17-52-00-000Z.png) |
| 3.2 | desktop | pass | Closed Welcome shows the closed notice, only Next in the footer, no complete button | ![](screenshots/page-2026-10-30T17-47-30-212Z.png) |
| 3.4 | desktop | pass | Knowledge Check (item 5) closed; refused routes redirect to the closed notice; resubmit gives no 500 | ![](screenshots/page-2026-10-30T17-47-44-319Z.png) |
| 3.5 | desktop | **fail** | Sequential unlock holds, but Locked rows past close still print "Closes <past date>." (B1) | ![](screenshots/page-2026-10-30T17-47-30-212Z.png) |
| 3.6 | desktop | pass | Fresh learner: "Missed deadline" only, opens normally, no Closes/Closed text | none |
| 3.7 | desktop | pass | Completed Welcome shows no deadline line or chip and opens under outline_and_results | ![](screenshots/page-2026-10-30T17-49-29-737Z.png) |
| 4.1 | desktop | pass | Ended card shows ACCESS ENDED eyebrow, no Continue; detail shows the ended message, no button | ![](screenshots/page-2026-10-30T17-53-00-000Z.png) |
| 4.1 | mobile | pass | Compact row shows eyebrow and date, no Continue; eyebrow columns wrap (cramped); no overflow | ![](screenshots/page-2026-10-30T17-54-00-000Z.png) |
| 4.2 | desktop | pass | Welcome opens; every other item and route redirects to /detail/ | ![](screenshots/page-2026-10-30T17-49-29-737Z.png) |
| 4.3 | desktop | pass | Plain course under "nothing": ended message, no content section, item routes redirect | ![](screenshots/page-2026-10-30T17-55-00-000Z.png) |
| 4.5.1 | desktop | pass | /access/ redirects to /detail/; no registration created | none |
| 3.1 | desktop | pass | Course Feedback (item 7) shows "Closes Nov 1, 2026", linked, no Closed chip, starts normally | ![](screenshots/page-2026-10-30T17-50-54-013Z.png) |
| 3.3 | desktop | pass | Override moved back: row reads Closed, notice shown, no Start Form, gates redirect to /7/ | ![](screenshots/page-2026-10-30T17-56-00-000Z.png) |
| 4.4 | desktop | pass | Restored learner shows "Access ends Nov 29, 2026" and opens; fresh learner has no Access ends line | ![](screenshots/page-2026-10-30T17-57-00-000Z.png) |
| 4.5.2 | desktop | pass | Deactivated registration shows the normal not-registered state, not the ended message | ![](screenshots/page-2026-10-30T18-00-00-000Z.png) |
| 4.5.4 | desktop | pass | completed_time set: course moves to Learning history as COMPLETED, not Access ended | ![](screenshots/page-2026-10-30T18-01-00-000Z.png) |
| 5.1 | desktop | pass | Fixed-date time-limit override restores access; a 10:00 time is refused; yesterday ends access again | ![](screenshots/page-2026-10-30T17-52-11-118Z.png) |
| 5.2 | desktop | pass | Cohort-level time-limit override saves; learner card and course open | none |
| 4.2.6 | desktop | pass | Completed attempt results page ("Quiz passed", 100%) renders for the ended learner | ![](screenshots/page-2026-10-30T18-03-00-000Z.png) |
| 4.3.3 | desktop | pass | Submit-and-exit on the plain course redirects to /3/complete, 200, no traceback | none |
| 6.1 | desktop | pass | /courses/, dashboard, topic and form start render; no overflow or console errors | ![](screenshots/page-2026-10-30T18-02-00-000Z.png) |
| 6.1 | mobile | pass | Same pages at 375: scrollWidth 375, no console errors | ![](screenshots/page-2026-10-30T18-02-05-000Z.png) |
| 6.3 | desktop | pass | `manage.py check` clean; E001 and E002 system checks fire on bad settings | none |
| 4.5.3 | desktop | pass | Hidden course: ended learner reaches /detail/ (200); anonymous visitor gets 404 | ![](screenshots/page-2026-10-30T18-05-00-000Z.png) |
| 6.2 | desktop | pass | Anonymous parts-course detail shows "Enrol for free", no ended message or deadlines | ![](screenshots/page-2026-10-30T18-06-00-000Z.png) |
| 3.4 | mobile | pass | Closed-form player fits at 375: chip, wrapped notice, adequate touch targets | ![](screenshots/page-2026-10-30T18-07-00-000Z.png) |
| 3.2 | mobile | pass | Bottom-sheet outline opens; closed Knowledge Check row shows its Closed date; no overflow | ![](screenshots/page-2026-10-30T18-07-30-000Z.png) |
| 4.1 | tablet | pass | Ended card on one line with icon; detail in one column; no overflow | ![](screenshots/page-2026-10-30T18-08-10-000Z.png) |
| 3.2 | tablet | pass | Sidebar hidden, outline drawer button offered; scrollWidth 768 | ![](screenshots/page-2026-10-30T18-08-00-000Z.png) |
| 1.1 | tablet | pass | Course deadline config add form at 768: no horizontal overflow | ![](screenshots/page-2026-10-30T18-08-30-000Z.png) |

### Detail by test

- **1.1 desktop (pass).** Six Deadlines admins listed. Selects offer Inherit/On/Off and Inherit/Outline and results/Nothing; help texts explain Inherit and the DD HH:MM:SS format. All-Inherit row saves and the list shows Inherit with grace "-"; reopening keeps Inherit and an empty grace. Grace 0 00:00:00 reopens as 00:00:00. List screenshot: ![](screenshots/page-2026-10-30T17-42-14-865Z.png)
- **1.2 desktop (pass).** Duplicate course config: "Course deadline config with this Course already exists.", list still 1 row. Site config form shows no owner field; a second one gives "Site deadline config with this Site already exists." (![](screenshots/page-2026-10-30T17-42-35-655Z.png)). Duplicate cohort config: form error. Grace -1 00:00:00: field error "The grace window cannot be negative.", no IntegrityError.
- **1.3 desktop (pass).** Late learner: mark_overdue On (settings), close_items On (registration), end_course_access Off (registration), notify_educators Off (settings), grace 3 days, 0:00:00 (registration), after_access_ended Outline and results (settings), no Access ends line. Cohort learner: end_course_access On (cohort), after_access_ended (cohort), "Access ends: 30 May 2026, 23:59 SAST". Fresh learner: all settings. Org close_items=off: late learner keeps (registration), cohort learner reads Off (organisation). Panel prints booleans as On/Off, timedelta as "3 days, 0:00:00" and time as 23:59; the plan's True/11:59 PM wording is approximate and the spec fixes no format.
- **2.1 desktop (pass).** Default: Welcome shows the "Missed deadline" chip + "Jan 31, 2024, 11:59 PM" in the outline and above the player title. With CourseDeadlineConfig mark_overdue=off: "Deadline Jan 31, 2024, 11:59 PM." and no chip in the outline and header; dashboard card "Deadline Welcome Jan 31, 2024, 11:59 PM." with no chip (![](screenshots/page-2026-10-30T17-45-18-280Z.png)). Back to on: the chip returns.
- **2.1 mobile (pass).** At 375x812 with mark_overdue=off the compact card reads "Deadline Welcome Jan 31, 2024, 11:59 PM." with no chip; no overflow.
- **2.2 desktop (pass).** The plan's late learner cannot show the time-limit branch: the card names the earliest missed deadline, which is Welcome (closed Feb 3, 2024), not the time limit (![](screenshots/page-2026-10-30T17-46-13-882Z.png)). qa-data-helper set up `qa_deadline_timelimit@email.com` instead (parts course registered 100 days ago, no config, every item override 30 days ahead). Its card reads "Missed deadline / Course Oct 20, 2026, 11:59 PM"; with CourseDeadlineConfig mark_overdue=off it reads "Deadline Course Oct 20, 2026, 11:59 PM." with no chip (![](screenshots/page-2026-10-30T17-52-30-000Z.png)), and the course still opens.
- **3.2 desktop (pass).** Late learner: Welcome is closed ("Closed Feb 3, 2024, 11:59 PM" chip with a clock icon, sr-only "Closed"). The player shows "Closed on Feb 3, 2024, 11:59 PM. Ask your educator if you need more time." in the reading column, with only Next in the footer: no complete button, no "Submit your answers". A guessed /1/ returns 200 with the notice. The admin record shows an empty last_accessed_item, and started_at predates the visits (set by the seed). What to Expect and Key Ideas are withheld by sequential unlock (Welcome is closed and incomplete), so they read Locked, not Closed. That is spec decision 11; the plan's expectation of linked closed rows doesn't fit this seed.
- **3.4 desktop (pass).** Knowledge Check (index 5, not 4 as the plan says) reads Closed with a link; the page shows the closed notice plus "Submit your answers". /5/fill_form/1 and /5/start_form redirect to /5/ (the closed notice), not course detail. The spec's Player gates section says a refused CLOSED item redirects to view_course_item, so the plan's "course detail" is wrong. Submitting renders the results page (0/3, "Quiz not passed"). The outline row still reads Closed because a FAILED item past its close instant is CLOSED per the spec (is_closed applies to READY/IN_PROGRESS/FAILED). Back plus resubmit, and a second fetch POST, both land on the results page with no 500. The admin shows one completed attempt.
- **3.5 desktop (fail).** Sequential unlock holds: What to Expect, Key Ideas and Course Feedback are unlinked with sr "Locked" and no Closed chip; /2/ by URL redirects to course detail. Parts: "Getting Started" and "Core Concepts" rows read Closed with no link. FAIL: a Locked row past its close instant still prints the future-tense line "Closes <date>." with a past date, e.g. What to Expect "Missed deadline Jul 29, 2026 · Closes Aug 1, 2026, 11:59 PM." and Key Ideas "Closes Aug 8, 2026" on Oct 30, 2026. See B1.
- **3.6 desktop (pass).** Fresh learner (no config): Welcome shows "Missed deadline" and opens normally; no "Closes"/"Closed" anywhere in the outline, header or dashboard.
- **3.7 desktop (pass).** Cohort learner: completed Welcome shows no deadline line and no chip, and opens under outline_and_results with its body rendered.
- **4.1 desktop (pass).** Cohort learner card: eyebrow "ACCESS ENDED MAY 30, 2026, 11:59 PM" with a clock icon, progress bar, no Next up, no deadline line, no Continue; title and Details link to /detail/. Detail (![](screenshots/page-2026-10-30T17-53-30-000Z.png)): "Your access to this course ended on May 30, 2026, 11:59 PM. Your progress is saved. Ask your educator to restore it.", no button. The outline links only Welcome. The course_home URL lands on /detail/. Admin: the cohort registration is still active and there is no individual registration.
- **4.1 mobile (pass).** Compact row shows the ACCESS ENDED eyebrow with its date and no Continue. The eyebrow label and date sit as two narrow side-by-side columns that each wrap ("ACCESS / ENDED" | "MAY 30, 2026, / 11:59 PM"), readable but cramped. Detail page at 375 (![](screenshots/page-2026-10-30T17-54-10-000Z.png)): no horizontal overflow (scrollWidth 375).
- **4.2 desktop (pass).** Cohort learner: Welcome (item 1) opens with no deadline line in the header; every other outline row is unlinked. Next (/2/), /3/, /4/, /5/, /7/, /5/complete (no completed attempt), /finish/ and /5/start_form each redirect to /detail/. 4.2.6 (completed attempt results page) is recorded separately.
- **4.3 desktop (pass).** Late learner, plain course under "nothing": detail shows the ended message (Oct 20, 2026, 11:59 PM), no button, no "Course content" section; /1/, /2/ and course_home redirect to /detail/. Card eyebrow "ACCESS ENDED OCT 20, 2026, 11:59 PM". 4.3.3 is recorded separately.
- **4.5.1 desktop (pass).** Cohort learner visiting /courses/functionality-demo-course-parts/access/ is redirected to /detail/; the admin shows no LearnerCourseRegistration for the learner.
- **3.1 desktop (pass).** qa-data-helper completed Welcome, What to Expect, Key Ideas, Going Deeper and Summary for the late learner so that sequential unlock offers Course Feedback. Under the plan's seed it stays Locked behind the closed, incomplete Welcome. Course Feedback (index 7, not 5 as the plan says) row: "Missed deadline Oct 29, 2026, 11:59 PM / Closes Nov 1, 2026, 11:59 PM.", no Closed chip, linked (/7/). /7/ renders the form start page with "Start Form", and the header repeats the chip and the Closes line.
- **3.3 desktop (pass).** Course Feedback override moved to 2026-10-20 in the admin inline: the row reads "Closed Oct 23, 2026, 11:59 PM" (sr "Closed"), still linked. /7/ shows "Closed on Oct 23, 2026, 11:59 PM. Ask your educator if you need more time." with no Start Form and no Submit your answers. /7/start_form and /7/fill_form/1 redirect to /7/ (the closed notice), which matches the spec's Player gates; the plan's "course detail" is out of date. Form progress list unchanged (only the Knowledge Check attempt). Override restored to 2026-10-29.
- **4.4 desktop (pass).** Restored learner: card "Access ends Nov 29, 2026, 11:59 PM." (today + 30) and the course opens at /1/. Fresh learner: deadline lines only, no "Access ends". A learner past the time limit with end_course_access off is covered in 2.2 by qa_deadline_timelimit: "Missed deadline Course Oct 20, 2026" and the course opens.
- **4.5.2 desktop (pass).** Late learner's plain-course registration deactivated in the admin: the dashboard no longer lists the plain course, and its detail page shows the normal not-registered "Enrol for free" state, not the ended message. Reactivated afterwards (admin list shows it active).
- **4.5.4 desktop (pass).** completed_time set on the cohort learner's record in the admin: "In progress" is empty, and the course sits in "Learning history" as COMPLETED, not Access ended. /2/ opens for review and detail offers "Review course". completed_time cleared afterwards.
- **5.1 desktop (pass).** Admin: a "Course time limit" fixed-date override of 2026-11-13 with no time saves with no error; the Effective column reads "Fixed 13 Nov 2026, 23:59 SAST" and the panel reads "Access ends: 13 Nov 2026, 23:59 SAST". The inline's collection-item help tooltip reads "A fixed date or a number of days on the course time limit restores ended access." Learner (![](screenshots/page-2026-10-30T17-58-00-000Z.png)): card "Access ends Nov 13, 2026, 11:59 PM.", title links into the player (/2/), and item 2 opens. Course detail shows "Start course" instead of "Continue"; the label is keyed on progress percentage and the seed leaves this record at 0% despite a completed Welcome, so it's a seed artifact. Adding a 10:00 time is refused with "The course time limit ends at the end of its day." (![](screenshots/page-2026-10-30T17-59-30-000Z.png)). Setting the date to yesterday ends access again (card "ACCESS ENDED OCT 29, 2026, 11:59 PM"). Override deleted.
- **5.2 desktop (pass).** Cohort course registration change page: a "Course time limit" fixed-date override of 2026-11-13 saves; the cohort learner's card reads "Access ends Nov 13, 2026, 11:59 PM." and the course opens. Override deleted.
- **4.2.6 desktop (pass).** qa-data-helper gave the cohort learner a finished Knowledge Check attempt (3/3). As the ended learner, /5/complete renders the results page ("Quiz passed", 100%). A passed quiz shows no "Try again" button; the form_start URL (/5/start_form) redirects to /detail/ with no new attempt (checked in 4.2).
- **4.3.3 desktop (pass).** Plain course form "Course Feedback Survey" is at index 3. qa-data-helper created an open attempt for the late learner (plain course access ended, after_access_ended=nothing). A fetch POST with CSRF to /courses/functionality-demo-show-end-with-topic/3/submit-and-exit redirects to /3/complete, which renders 200 ("Course Feedback Survey — Complete") with no traceback.
- **6.1 desktop (pass).** Fresh learner: /courses/ renders with no deadline lines; dashboard and topic page (/1/) render 200 with no horizontal overflow. Form start (Course Feedback /7/, as the late learner, since sequential unlock withholds every form from the fresh learner) shows Start Form; clicking it opens /7/fill_form/1 with its questions. No console errors or page errors on any of these pages.
- **6.1 mobile (pass).** At 375x812: /courses/, dashboard, topic page and form start render 200, scrollWidth 375 (no horizontal overflow), no console errors.
- **6.3 desktop (pass).** `manage.py check`: no issues. A throwaway settings module (in the session scratchpad, not the repo) importing settings_dev with DEADLINE_POLICY_DEFAULTS missing grace_window: freedom_ls_deadlines.E001 names the expected keys. DEADLINE_POLICY='nowhere.Nothing': freedom_ls_deadlines.E002 "is not an importable DeadlinePolicy subclass".
- **4.5.3 desktop (pass).** qa-data-helper set the parts course visibility to hidden. The cohort learner (ended) still reaches /detail/ (200, ended message); an anonymous visitor gets 404. Set back to published.
- **6.2 desktop (pass).** Anonymous visitor: the parts-course detail page renders 200 with the free "Enrol for free" state and no ended message or deadline lines.
- **3.4 mobile (pass).** At 375x812 the closed-form player shows the Closed chip with icon, the closed notice wrapped inside the column, and Previous/Next with adequate touch targets; no horizontal overflow. "Submit your answers" is absent because the attempt was already submitted in 3.4.
- **3.2 mobile (pass).** The "Open course outline" button opens the bottom-sheet outline; the closed Knowledge Check row shows "Closed Aug 15, 2026, 11:59 PM" with a clock icon; no overflow.
- **4.1 tablet (pass).** At 768x1024 the ended card reads "ACCESS ENDED MAY 30, 2026, 11:59 PM" on one line with its icon, plus progress and Details; no overflow. Ended detail page (![](screenshots/page-2026-10-30T18-08-20-000Z.png)) is laid out in one column with no overflow.
- **3.2 tablet (pass).** At 768 the player hides the sidebar and offers the "Open course outline" drawer button; content and footer fit (scrollWidth 768).
- **1.1 tablet (pass).** Course deadline config add form at 768: no horizontal overflow.

## Design check

No design states tested.

## Bugs

### B1: Locked outline rows past their close instant still say "Closes <past date>."

- **Manifestations:** 3.5 (desktop)
- **Screenshot:** ![](screenshots/page-2026-10-30T17-47-30-212Z.png)
- **Expected:** A row that sequential unlock withholds stays Locked with no Closed chip past its close instant (spec decision 11), and the labels add the close date only when the row will still close (`deadline_labels.html`: "adds when the row closes, if it will"). On 30 Oct 2026, What to Expect should not tell the learner it "Closes Aug 1, 2026".
- **Actual:** For the late learner (close_items on, grace 3 days), Locked rows read "Missed deadline Jul 29, 2026, 11:59 PM · Closes Aug 1, 2026, 11:59 PM." (What to Expect) and "Closes Aug 8, 2026, 05:00 PM." (Key Ideas): future-tense copy for a close instant three months past. `partials/deadline_labels.html` prints "Closes" whenever `child.closes_at` is set, without checking that it is still ahead.

## Bug status

- **FIXED** (commit: 9fd50a644) — Locked outline rows past their close instant still say 'Closes <past date>.'

  `_deadline_keys` now sets `closes_at` only on a closed row or while the close instant is still ahead. Re-verified in the browser: with a temporary course config `close_items=on`, the restored learner's Locked rows read only "Missed deadline <date>" (no "Closes"), while the late learner's Course Feedback, still inside its grace window, keeps "Closes Nov 1, 2026, 11:59 PM." in the outline and header. Closed chips and dashboard cards are unchanged.

  ![](screenshots/page-2026-10-30T18-20-00-000Z.png)

- **UNRESOLVED** — full run after the fixes left tests failing (reason: 24 failures in `tests/test_update_concrete_projects.py` — `test_every_new_allow_verb_matches_a_spelled_command_form` (23 parametrisations) and `test_every_spelled_project_command_form_is_allowed_or_prompts_by_design`. They fail identically right after the rebase and before the fix; the branch changes none of the files involved, so main's commit 22ad3e36b "Pin concrete-project allow rules to exact paths" caused them. Full run: 24 failed, 10568 passed.)

## General notes

- The test plan is out of date in several places; the implementation matches the spec:
  - (a) Player indices: Knowledge Check is item 5 and Course Feedback item 7, not 4 and 5.
  - (b) A refused CLOSED form's `start_form`/`fill_form` redirect to the item's closed notice (`view_course_item`), per the spec's "Player gates", not to course detail.
  - (c) With the plan's seed the late learner's Welcome is closed and incomplete, so sequential unlock (spec decision 11) withholds What to Expect, Key Ideas and Course Feedback as Locked. The plan's section 3.1/3.2 expectations of linked closed rows need extra completed topics.
  - (d) Section 2.2's late-learner card shows the earliest missed deadline (Welcome, closed Feb 3, 2024), not the course time limit, so a separate learner was used.
  - (e) A FAILED quiz past its close instant stays "Closed" after "Submit your answers" (spec: is_closed applies to FAILED rows), where the plan expected "Needs retry"/complete.
  - (f) The effective-policy panel prints On/Off, "3 days, 0:00:00" and 23:59 rather than the plan's True/False and 11:59 PM; the spec fixes no format.
- Ended-learner course detail still heads the side panel with "Free · open to everyone / One click. No credit card." above the ended message (![](screenshots/page-2026-10-30T17-53-30-000Z.png)). It is not forbidden wording, but it is an enrolment pitch to a learner whose access ended.
- At 375px the compact dashboard row's "ACCESS ENDED" eyebrow and its date sit in two narrow side-by-side columns that each wrap (![](screenshots/page-2026-10-30T17-54-00-000Z.png)). At 768 it fits on one line.
- The cohort learner's course detail said "Start course" while restored (the label follows progress percentage, and the seed leaves that record at 0% despite a completed Welcome). This is a seed artifact.
- The only console errors seen were a `/favicon.ico` 404 and one 404 from a mistyped admin URL by the tester.
- After the rebase, 24 tooling tests in `tests/test_update_concrete_projects.py` fail. The branch changes none of the files involved, so the failures come from main's commit 22ad3e36b ("Pin concrete-project allow rules to exact paths").
- 37 leftover screenshots from an earlier run today were moved out of the capture directory before this run so they would not be attributed to it.

status: ok · reason: 1 bug — 1 fixed, 0 unresolved; report rendered, screenshots verified
