# Research: reference implementations of a timed quiz with countdown and auto-submit

Builds on `spec_dd/1. next/sacaa-compliance-assessment-controls/research_regulation_and_prior_art.md` (Moodle "when time expires" options, WCAG 2.2.1). That ground is not repeated here.

Confidence note: the Moodle `quiz_attempt.php` and `cronlib.php` findings come from fetched source (summarised by a fetch tool, not read line by line). The Moodle client timer source, the edx-proctoring source (raw GitHub paths 404'd), Google Forms and Django app code could not be read. Those parts rest on docs, changelogs and forum threads and are marked as such.

## 1. Moodle (best-documented, fetched source)

### Where the deadline lives
- No stored deadline column. `quiz_attempt::get_due_date()` computes it on demand: the earlier of `timestart + timelimit` and the quiz `timeclose`. A state of `inprogress` returns that. A state of `overdue` returns `duedate + graceperiod`. Any other state throws.
- Per-user and per-group overrides of limit and close time are applied to a copy of the quiz object before the check (`cronlib.php` loop, below).
- `timecheckstate` is a stored column, but it is not the deadline. It is a "next time to look at this attempt" marker for the sweep. `handle_if_time_expired()` sets it to the close time while time remains, to `null` when no limit applies, and to `close + graceperiod` when overdue. `process_going_overdue` sets it to the timestamp. `process_abandon` sets it to `null`. This makes the sweep an indexed query, not a scan of every open attempt.
- Source: https://github.com/moodle/moodle/blob/main/public/mod/quiz/classes/quiz_attempt.php (raw: https://raw.githubusercontent.com/moodle/moodle/main/public/mod/quiz/classes/quiz_attempt.php)

### What happens to a page posted late
- `process_submitted_actions()` does no time checks. The timing decisions are in `process_attempt($timenow, ...)`:
  - If `$timenow > $timeclose - QUIZ_MIN_TIME_TO_CONTINUE`, `$timeup` is forced true.
  - `$toolate` is true when `$timenow > $timeclose + $graceperiodmin`. `graceperiodmin` is a small fixed tolerance for clock skew and network delay.
  - If the learner is not finishing and the post is too late, the responses are not processed. The attempt goes overdue instead.
  - If the learner is finishing, `process_submit($timenow, !$toolate, $finishtime, true)` runs. The second argument is "process the responses", so late responses are dropped and the attempt finishes on stored answers. With no grace-period handling, `$finishtime` is clamped to the close time, so the recorded finish never exceeds the deadline.
- Takeaway for FLS: Moodle also drops a late post and finishes on stored answers. It adds a small fixed tolerance (`graceperiodmin`) that is separate from the user-facing grace period. The FLS answer is "no grace period". A few seconds of tolerance for the client's own expiry post is a separate question, because that post arrives after the deadline by network latency.

### The "when time expires" dispatcher
- `handle_if_time_expired($timestamp, $studentisonline)` is the single entry. Every path calls it: attempt page load, the sweep, review. It branches on `overduehandling`: `autosubmit` calls `process_submit` then `process_grade_submission`; `graceperiod` calls `process_going_overdue`; `autoabandon` calls `process_abandon`. This matches the idea's "any request that touches an expired open sitting completes it".
- The older design doc says the same: the check "runs when an attempt is loaded, and corrects it by triggering the right transition", and it warns that the browser timer, a teacher viewing the attempt, and cron can all act at once, so a clear protocol is needed. Moodle's answer is that each transition is idempotent on state: it re-reads state and acts only if the attempt is still `inprogress` or `overdue`. FLS should make `complete()` safe to call twice for the same reason.
- Design doc: https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts (Moodle 2.3 era, marked obsolete)
- Earlier draft: https://docs.moodle.org/dev/Quiz_time_controls_on_attempts and https://docs.moodle.org/dev/States_of_a_quiz_attempt

### The cron sweep
- `mod_quiz\task\update_overdue_attempts` calls the updater's `update_overdue_attempts($timenow, $processto)`. Older mirror of the class: https://git.interlegis.leg.br/ILB/moodle/src/branch/master/mod/quiz/cronlib.php
- `get_list_of_overdue_attempts($processto)` selects `quiz_attempts` where `state IN ('inprogress','overdue')` and `timecheckstate <= :processto`. It joins `quiz` and a per-user subquery for overridden close time and limit. It orders by course then quiz, so the loop reloads the quiz, course and course module only when they change.
- The loop builds a `quiz_attempt`, applies the user's overrides to a quiz copy, and calls `handle_if_time_expired($timenow, false)`. `false` means the student is not online.
- Each attempt is wrapped so a `moodle_exception` is logged with attempt id and quiz, the transaction is rolled back, and the loop continues. One bad row does not stop the sweep.
- Bug history worth knowing: MDL-35717 reports that the sweep did not close old attempts after the quiz closed. The cause was a lower time bound on the query. The fix removed it (https://tracker-old.moodle.org/browse/MDL-35717). Lesson: the sweep query must be "deadline in the past", never a window.
- Task cadence: the sweep's cadence is the site's cron schedule, so Moodle also relies on request-time enforcement for what a learner meets. Same as the idea.

### How the finish reason is recorded and shown
- Moodle records a state (`inprogress`, `overdue`, `finished`, `abandoned`) plus `timefinish`. It does not record "who or what finished it": `finished` looks the same whether the learner clicked submit or auto-submit fired. The state design doc floated a `finishedby` column but the page marks it as a proposal. I could not confirm it shipped.
- Teachers see state in the attempts list on the quiz view page, on the review page, and in the overview and responses reports (filterable by state). Statistics count only finished attempts.
- Gap Moodle leaves open, which the FLS idea fills: an auditor cannot tell a lapsed-clock result from a learner submit. FLS recording a reason is stronger than Moodle's model here.
- State doc: https://docs.moodle.org/dev/States_of_a_quiz_attempt

### Client timer, display and announcement
- Could not read `timer.js`. Evidence from docs and forums: the countdown is rendered from the server-supplied end time on each page load; the older design doc says the browser timer "no longer auto-submits at time-out" in the grace-period strategy and instead sends the student to the summary page. In autosubmit mode the JS submits the form.
- Moodle puts a CSS class like `timeleft99` on the timer in the last 100 seconds and styles it only in the last 15 seconds (https://moodle.org/mod/forum/discuss.php?d=399741). Accessibility of the timer has a history of gaps: MDL-27843 (timer needs ARIA, deferred) https://tracker-old.moodle.org/browse/MDL-27843. Moodle's VPAT: https://docs.moodle.org/en/VPAT. Quiz accessibility guidance from one site: https://www.lsuhsc.edu/moodledocs/f_accessibility_quizzes.aspx. Treat these as secondary.
- Moodle lets a learner hide the timer (a toggle). The timer is not announced to screen readers by default, which is the gap the FLS warnings at 5 minutes and 1 minute answer.

## 2. Canvas (Classic Quizzes and New Quizzes)

All sources are institutional guides and forum posts, not Canvas source.

- Deadline is per attempt: the limit runs from first open of the quiz. The quiz's Until date can cut it short: the quiz auto-submits at Until even if timer time remains, and extra time for a student does not override Until. Source: https://sites.usask.ca/gmcte/2020/10/06/understanding-canvas-classic-quizzes-timer-availability-and-accommodation-settings/ and https://www.uab.edu/ctl/learning-technologies/guides/adding-additional-time-and-attempts-to-canvas-quizzes-classic
- Enforcement relies on the client being open. If the student leaves the page, the submission stays "outstanding" (untaken) past the limit, and instructors can submit it by hand. Support's reported behaviour: it auto-submits the moment the student returns. Sources: https://community.canvaslms.com/t5/Admin-Group/Quiz-Timer-disconnection-auto-submit/m-p/462862 and https://community.canvaslms.com/t5/Question-Forum/Timed-Quiz-Did-Not-Auto-Submit-for-a-Student/m-p/418192
- Timing quirk: Canvas does not display seconds, so submit happens at the minute shown; guides advise buffer in the availability window (https://canvashelp.fullerton.edu/m/Making_the_Most_of_Canvas/l/1298983-what-issues-affect-time-limits-and-due-dates-of-online-quizzes).
- A forum report shows a log with work past the limit and no marker on the result (https://community.canvaslms.com/t5/Archived-Questions/Quizzes-automatically-submitted-before-time-runs-out/td-p/403428). That is the audit weakness the FLS reason field prevents.
- Takeaway: Canvas's "outstanding until student returns" is the case the FLS sweep exists to close. Canvas has no sweep for abandoned timed attempts that I could confirm.

## 3. Open edX timed exams (edx-proctoring)

Source files not readable. Evidence is from changelogs and docs.

- The attempt carries a status (`started`, `submitted`, `timed_out`, and later review statuses such as `verified`, `rejected`). `timed_out` is a recorded status distinct from `submitted`, and the instructor results report lists it. Docs: https://docs.openedx.org/en/ulmo/educators/references/proctored_exams/rpnow_proctored_exam_report.html
- The LMS timer is driven by polling a proctored exam attempt status endpoint; the server returns remaining seconds and the client counts down from that (changelog mentions a `time_remaining_seconds`-style field and a 3.2.1 fix to the status endpoint "that the LMS uses to drive the timer"). Changelog: https://pyup.io/packages/pypi/edx-proctoring/changelog?page=24 and https://pypi.org/project/edx-proctoring/
- Release 3.11.6 added logging of attempt status transitions caused by timeout or reattempt. So a transition record exists, with the cause logged.
- Takeaway: edx-proctoring is the closest match to the FLS reason field: `timed_out` is its own terminal status. It also supports the idea's "server sends remaining seconds, client counts down from it". Verify field names against source before citing them in the spec.

## 4. Google Forms

Native Google Forms has no quiz time limit. Time limits come from add-ons (for example Apps Script based form timers), which close the form or revoke responses on a trigger. Not researched in depth; it adds nothing the Moodle and Canvas findings do not cover. I could not verify specific add-on behaviour.

## 5. Django and Python quiz apps

- Community consensus (Django users group, Django forum, Stack Overflow) matches the idea: store the start time or end time in the database on the server; compute remaining time from it, clamped at zero; send that to the client; do not trust the browser clock; do not reset on refresh. Sources: https://groups.google.com/g/django-users/c/9LCCXUGf9LI/m/ErmO90DSBgAJ , https://forum.djangoproject.com/t/how-to-work-with-the-timer-to-the-quiz-fully-functionality/11271 , https://forum.djangoproject.com/t/django-countdown-timer/7060
- No Django quiz repo found showed a sweep or a recorded finish reason. Candidates seen but not read: https://github.com/RifasM/Django-Quiz , https://github.com/kallewesterling/django_quiz , https://github.com/TheChomas/GradeEz (says late answers are not accepted).

## 6. Timer display and announcement (platform-independent)

- `role="timer"` has implicit `aria-live="off"`, so a plain timer is not announced. MDN: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/ARIA_timer_role
- Common pattern: keep the ticking visual display out of the accessibility tree (`aria-hidden` on seconds), and put discrete warnings in a separate polite live region (`aria-live="polite"`, `aria-atomic="true"`), using `role="alert"`/assertive only for the final urgent warning. MDN live regions: https://developer.mozilla.org/docs/Web/Accessibility/ARIA/Guides/Live_regions . University summaries: https://dash.uga.edu/accessibility-techniques/time-limits/
- This supports the answers already taken: warnings at 5 and 1 minutes, none when the limit is 5 minutes or less, and a polite region for the 5-minute warning with a stronger announcement at 1 minute.

## 7. What carries over to FLS

| Question | What the references do | Fits the idea? |
| --- | --- | --- |
| Where the deadline is stored | Moodle and Django advice: compute from start time plus limit on demand; Moodle also keeps a separate "next check" column for the sweep | Yes. The idea computes from `start_time` plus current limit. A "next check" column is not needed while the sweep can compare `start_time + limit` to now, but the limit lives in the form content, so the sweep must read it per form (the sweep cannot filter in SQL on a limit that sits in front matter). This is a real design point for the spec. |
| Client sync | edx and Django advice: server sends remaining seconds on each load; client counts down from it | Yes, matches the recommendation. |
| Late post | Moodle: responses dropped, attempt finished on stored answers; small fixed tolerance for network delay | Matches "not saved". The client's own expiry post lands after the deadline by latency, so the spec must say whether it is accepted. Moodle's `graceperiodmin` tolerance is the precedent; the idea posts the page at zero, so a short tolerance (or a rule that the expiry post is the one exception) must be decided. |
| Entry point | Moodle: one `handle_if_time_expired` called from every path | Matches "any request that touches an expired open sitting completes it". Put one helper behind all four call sites. |
| Sweep | Moodle: query by "due time passed", per-row exception isolation, no lower bound | Use the same: no lower bound, catch per row, continue. |
| Idempotence | Moodle: browser, teacher view and cron can race; transitions check current state | `complete()` must tolerate a second call. |
| Finish reason | Moodle: state only, no reason (a gap). edx: `timed_out` is its own status. Canvas: no marker | The idea's reason field is stronger than Moodle and aligned with edx. |
| Teacher display | Moodle: state in attempts list, review page, reports filterable by state | The idea's attempt review and cohort report table match. Consider filtering or sorting by reason only if asked. |
| Timer a11y | Visual timer plus separate polite live region for warnings | Matches the answers taken. |

## Open points the spec should settle

1. Whether the client's expiry post is accepted when it arrives a few seconds after the deadline (Moodle's `graceperiodmin` precedent), given "no grace period" was decided for the user-facing grace.
2. The sweep cannot filter on a limit that lives in form content. It must load each open sitting's form limit, or filter in Python.
3. `complete()` called twice (client post, request-time check, sweep) must be a no-op the second time.
4. Recorded finish time on a lapsed sitting: Moodle clamps to the close time. Decide whether FLS records `start_time + limit` or the actual time of completion (audit: probably both are useful; the reason field says which).

Sources: all URLs inline above.

status: ok
