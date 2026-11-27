# Prior art: quiz time limits

Topic `prior_art`. Question: what has already been tried for quiz time limits, in this repo or elsewhere, and what happened?

## 1. In this repo

**Net finding: no timed quiz has ever been built or specced here.** Nothing on a QUIZ form is timed. There is no `Form` time-limit field and no countdown widget on the runner. The only countdowns in the repo are unrelated (content_engine `alpine-components.js:235`, a panel_framework poll). The only `time_limit` in the code is the course-level `Course.time_limit_days` (deadlines). Source: `spec_dd/1. next/sacaa-compliance-assessment-controls/research_attempts_and_scoring.md` section 2.

### 1.1 The earlier exit work (`submit_on_exit`, exit dialog, `form_submit_and_exit`)

Specs: `spec_dd/3. done/2026-06-08_21:06_Student interface — course test-exam UI/` (spec section 5, plan 4d and 5d, frontend_qa 5a-5c), then `2026-08-24_20:56_extract_forms_into_seperate_app/` (QA F5).

- Decided: `Form.submit_on_exit` is a content-authored boolean, default False. It has no scheduler behind it. It does three things:
  - It changes the exit dialog copy to "Leaving now will submit..." with a "Leave and submit" button.
  - It completes an abandoned open sitting lazily, the next time the learner opens the item. `finalise_stale_incomplete` does this from `view_course_item`, `form_start` and `start_attempt`. `kept_if_untouched_since` spares a sitting last touched before the latest course pause.
  - It does nothing else. Logout, closing the tab and a lost connection do nothing on the server. The `beforeunload` guard in `examRunner` deliberately never calls the server. A learner who never returns keeps an open sitting forever.
- The "Leave and submit" button is a submit button bound to the runner page form (`form="runner-page-form"`, `formaction`, `formnovalidate`). The current page's answers therefore travel with the submit. `form_submit_and_exit` saves the posted page with `require_answers=False`, then calls `complete()`. It refuses a non-`submit_on_exit` form unless the item is closed or access has ended, and skips the save when closed. This is the pattern the idea reuses for the expiry post.
- QA F5 passed. The learner answered page 1, pressed Exit without Next, and landed on results at 3/6 = 50%. The three page-1 answers were carried and the page-2 questions counted wrong, so the page posted with the exit is not dropped. Lesson: one failed quiz completes the sitting, but the item stays "Needs retry". `attempt_completes_form` treats a failed scored attempt as an attempt, not a finished item.
- Documented trap (from the attempts research, section 5): the `content_save` pipeline dumps every non-None schema field. A schema default of `False` resets the stored value when the key is removed. A `None` default drops out of the dump, so the model default applies and removing the key does not reset the stored value. This matters for "the current limit applies" (answers.md Q3): a removed limit must reset to none, so the schema default must be non-None, or the loader must clear it.
- `form_submit_and_exit` gained course-access and deadline checks in the `basic_reports` spec upgrade notes. It was moved into `learner_interface` by the forms-extract and rename specs.

### 1.2 Stale-sitting completion and sweeps

- `FormProgress.complete()` is idempotent on `completed_time`, so racing callers are safe. It has no reason field. Callers: last page of `form_fill_page`, `form_submit_and_exit`, `finalise_stale_incomplete`, the admin. Recorded completion reason is new work.
- `START_REUSE_WINDOW` (10 s) and the `select_for_update` lock on `CourseProgress` in `start_attempt` already guard double-starts. `form_start` is a GET that writes, so expiry enforcement on it must also be a write-on-GET.
- `run_housekeeping_sweeps()` (`deployment/housekeeping.py`) is the existing shape for "close rows a dead worker left open" (`mark_orphaned_running_reports_failed`, via `_base_manager`). Each sweep has its own try/except and appends to `sweep_failures`/`findings`/`notes`. Cadence is the operator's cron, so the sweep is minutes late at best; the research recommends request-time enforcement with the sweep as a safety net. `spec_dd/1. next/deadlines/research_deadline_integration_points.md` and `housekeeping-sentry-cron-checkin/idea.md` record that other specs add sweeps to the same function, and "whichever lands second rebases on `housekeeping.py`".
- Per-page save: answers are saved on POST only (`form_fill_page` -> `submit_page` -> `save_answers`). An unposted page is lost. The client must post the current page with the expiry submit, and the post must skip `require_answers` (`page_flow.py:122`).

### 1.3 Deadlines app history

Specs: `3. done/2026-02-19_19:25_deadlines`, `deadlines_deactivate`, `deadlines-1-dates-and-overdue`, `deadlines-2-consequence-policy`, `deadlines-3-extensions-and-pause`, `deadlines-8-per-placement-dates`, `deadlines-8-review-fixes`, `design_learner-interface-deadlines`.

- Deadlines are calendar-based and evaluated at request time. `close_instant`, `is_closed` and `has_access_ended` (`deadlines/consequences.py:29-57`) compare `now` with `due_at` plus a grace window. No row is written at expiry, and nothing completes an open attempt. The only finalisation on close is `form_submit_and_exit` accepting a closed item.
- Decision carried into this idea: reuse the idea (compare an instant with now on each request), not the model. Per-sitting expiry is `start_time + limit`.
- Learner-side deadline UI is static labels only (`learner_interface/tests/components/test_deadline_labels.py`). There is no live countdown, so there is no countdown precedent beyond the toast component.
- Pause and extension semantics (deadlines-3) apply to learning time, which the idea explicitly excludes from the quiz clock (wall clock keeps running while the course is paused). A reviewer may question this against `finalise_stale_incomplete`'s `kept_if_untouched_since`, which does spare sittings across a course pause. The new expiry rule must override that spare, or a paused course could keep an expired sitting open.

### 1.4 The SACAA effort

- Source brief (`spec_dd/1. next/sacaa-compliance-assessment-controls/idea.md`): "Allow setting a time_limit on Quizes. Show the time remaining to the learner. Once the time elapses, submit the form and redirect the learner."
- Regulation research (`research_regulation_and_prior_art.md`) maps the quoted line to Moodle's default "auto-submit open attempts". Its implication: "auto-submit at deadline scoring only answered questions". Disturbance (spec 5) and an auto-fail are separate. They need a completion-reason record and a failing-score representation. A fail marker must be a real score pair (e.g. 0 of `max_score`), because `quiz_percentage()` raises on missing keys and `quiz_verdict` then returns None, which counts as not failed.
- The same research file warns that a client timer is bypassable and recommends a server-side heartbeat as the source of truth. It also records the WCAG 2.2.1 "essential" exception that justifies no extend control.
- Collisions (attempts research section 6): specs 2, 3 and 5 all edit `finalise_stale_incomplete`, `start_attempt`, `get_or_create_incomplete`, `_form_start_gate`, the `Form` schema, the `examRunner` Alpine component and `form_submit_and_exit`. One migration and one schema edit is advised. Spec 2 (attempt limits) is in progress in another worktree. Spec 5 is not started.
- Done SACAA specs 1-4 (served paper, shuffle, question pools, attempt review) set conventions this spec inherits:
  - `max_score` follows the served paper, so an expired short sitting is marked out of the served count.
  - The attempt review is the educator surface where the completion reason will show.
  - `served_paper` is JSON on `FormProgress`, created by `ensure_served_paper` at start.
- CSP Alpine build: no inline expressions. A countdown needs a registered `Alpine.data` component. Copy the toast component's `Date.now()`-delta pattern in `base/static/base/js/alpine-components.js:250-370`. `visibilityPoller` is the hidden-tab precedent. A hidden tab must keep counting.

## 2. Elsewhere

### 2.1 Moodle

- Settings doc: time limit with a "When time expires" option of auto-submit open attempts (default), grace period (the learner can submit but not change answers) or attempt must be submitted before expiry (otherwise the attempt does not count). https://docs.moodle.org/en/Quiz_settings
- Design history, "Better handling of overdue quiz attempts" (https://docs.moodle.org/dev/Better_handling_of_overdue_quiz_attempts). What went wrong before:
  - An attempt stayed "In progress" after expiry, but the student could no longer reach it to submit. This also blocked new attempts on multi-attempt quizzes.
  - Teachers had to extend the limit, log in as the student, submit, then restore the setting.
  - Attempts left by learners who logged out sat in limbo.
  - Fix: an explicit state column (in progress, overdue, finished, abandoned), instead of inferring state from `timefinish`.
  - Overdue is detected on load and by a cron task for unattended attempts, with a protocol against races between browser timer, teacher review and cron.
  - The same shape as this idea's four-place enforcement: request-time plus a sweep.
- Tracker MDL-3030 (overdue handling, fixed in 2.3): https://tracker-old.moodle.org/browse/MDL-3030
- Tracker MDL-54907: auto-submitted attempts recorded the finish time as when cron ran, not when time expired. https://tracker-old.moodle.org/browse/MDL-54907. Lesson: for a sweep-completed sitting, record the expiry instant (`start_time + limit`) as the audit time, or record both, so the auditor sees a lapsed clock rather than cron lag. Note that `complete()` stamps `completed_time` now, so the reason field alone does not record the true expiry instant.
- Tracker MDL-74543: finish time wrong when a grace period was used. https://tracker-old.moodle.org/browse/MDL-74543
- Tracker MDL-74378: a quiz that closes more than an hour after opening could stop autosaving and never auto-submit. Students who relied on auto-submit lost answers. https://tracker-old.moodle.org/browse/MDL-74378
- Forum: answers lost when submitted shortly after the close time even though the countdown was visibly running (https://moodle.org/mod/forum/discuss.php?d=219960). A related thread on changing the computer clock changing the countdown: https://moodle.org/mod/forum/discuss.php?d=383580. Another on definitive answers for quiz timing and saving: https://moodle.org/mod/forum/discuss.php?d=217504.
- Tracker MDL-58926 (not read in full): editing a quiz's time limit mid-attempt can leave open browsers out of sync so auto-submit fires too early or too late. https://tracker-old.moodle.org/browse/MDL-58926. Relevant to answers.md Q3, where the current limit applies and a content save can change it mid-sitting: the client countdown must re-sync from the server on every page load and never from a cached value.

### 2.2 General timer designs

- Server-owned clock, client display only: the start time and duration live on the server, the countdown survives a refresh or disconnect, and the server rejects late submissions even if the client timer is tampered with. The edX proposal (https://groups.google.com/g/edx-code/c/IOC_ih3BQDU/m/relqLy2HAwAJ), a Redis-TTL write-up (https://oneuptime.com/blog/post/2026-03-31-redis-online-exam-timer/markdown), a Mendix discussion (https://community.mendix.com/link/spaces/app-development/questions/145252) and the DEV write-up "The Exam Engine" (https://dev.to/insight105/the-exam-engine-206c) all converge on this. These are vendor blogs and forum posts, not a systematic review.
- Sync approaches: pass the server's current timestamp and start time to the client and compute from those, or poll a time endpoint. The sources do not settle which is better, and say little on tolerance windows or on a submission arriving just after expiry. Treat the answers.md "no grace period" decision as unvalidated by outside evidence on latency. One consequence: the final auto-post races the server clock, so the client should post a little before zero or accept that the last page may be dropped. This is an open design point for the spec.
- Talview's candidate docs describe timer and auto-submit behaviour for an objective assessment: https://docs.talview.com/candidates/assessments/ae/how-to/understanding-the-timer-and-auto-submit-in-an-objective-assessment (found by search, not read).

### 2.3 Accessibility

WCAG 2.2.1 Timing Adjustable: a limit may be unadjustable when it is essential, and a limit over 20 hours is exempt. https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html. The idea relies on the essential exception, so no extend control. The decided 5-minute and 1-minute screen-reader warnings fit this. WCAG-conformant timed tests also usually offer accommodations for extra time. The idea puts those out of scope. Moodle's per-user and per-group quiz overrides are the equivalent, and Moodle also supports them for time limits.

## 3. Lessons to carry into the spec

1. Never leave an expired sitting "open but unreachable" (Moodle's overdue limbo). Every touch of an expired open sitting completes it on the spot, and a sweep catches the rest. This matches the idea.
2. Auto-submit only marks what is stored. Post the current page with the expiry submit, with `require_answers` skipped. A page that arrives after expiry is dropped, by decision.
3. Record the true expiry instant for sweep-completed sittings (MDL-54907). A reason field alone will show cron lag as the finish time.
4. Client countdowns must be driven from server-sent remaining seconds, re-synced on every page load. A mid-sitting limit edit makes this mandatory (MDL-58926).
5. A `complete()` race between the browser's post, the sweep and a request-time check is real (Moodle needed a protocol). Our `complete()` is idempotent on `completed_time`, which covers it. The sweep should lock or re-read each row.
6. The `content_save` None-default trap decides whether removing the limit key clears the stored limit.
7. `finalise_stale_incomplete`'s `kept_if_untouched_since` pause rule conflicts with a wall-clock limit that ignores course pauses.
8. Specs 2, 3 and 5 edit the same functions. Plan for one migration and one rebase order.

status: ok
