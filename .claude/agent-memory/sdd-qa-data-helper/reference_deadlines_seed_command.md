---
name: reference-deadlines-seed-command
description: qa_create_deadlines_seed builds the deadlines-1 frontend QA §0.3 seed (tz config, QA Deadlines Org/Cohort, 4 qa_deadline_* learners with back-dated CourseProgress.created_at)
metadata:
  type: reference
---

`uv run python manage.py qa_create_deadlines_seed [--site-name DemoDev]`
(`freedom_ls/qa_helpers/management/commands/qa_create_deadlines_seed.py`, dev_tooling test alongside).

- Run `content_save demo_content DemoDev` FIRST; the command refuses if the parts course's due
  defaults differ. Item titles in the DB are "What to Expect", "Key Ideas", "Course Feedback"
  (the QA plan writes them lower-case / "Feedback").
- The plan's "plain course" `Functionality Demo - End With Topic` is really titled
  `Functionality Demo - show end with Topic`, slug `functionality-demo-show-end-with-topic`.
- "Reg" date = `CourseProgress.created_at` (auto_now_add) -> back-date with
  `queryset.update(created_at=...)`. Solo = now-100d, so it drifts each re-run.
- Fresh learner's registration + record are deleted and rebuilt every run (new pks each time).
- Registrations mint CourseProgress via `transaction.on_commit`: fires in a shell/command, NEVER in
  a pytest transaction -> tests must build records with `CourseProgressFactory`.
- Leaves `qa_deadline_cohort2@email.com` (an extra cohort member from a QA run) alone.
- Admin app labels: `freedom_ls_learner_progress/courseprogress`,
  `freedom_ls_site_aware_models/sitetimezoneconfig`,
  `freedom_ls_learner_management/cohortcourseregistration`.

## qa_deadline_timelimit@email.com (deadlines-2, Nov 2026) -- NOT built by the seed
Time limit past (content 90d, record now-100d) but every item overridden FIXED today+60, no config
rows (policy = settings defaults). Asked for at least twice (user pk 78 already existed with a prior
build). Rebuild idempotently: `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_timelimit_script.py`
(imports the seed's helpers; wipes only this account's records/registrations/overrides; also
back-dates LearnerCourseRegistration.registered_at, which the resolver does not read). If asked a
third time, promote it to a qa_helpers command.
Run 3 (caller said: don't promote yet, just run). The script never touches CourseDeadlineConfig: a
course-wide parts row (mark_overdue=on) the tester made in the UI showed up and is shared by all 6
qa_deadline_* parts learners -- report it, don't delete it. Summary/Going Deeper have no due default, so no override.

## Add-on attempts asked for on top of the seed (deadlines-2, Nov 2026)
- cohort/parts: one COMPLETED Knowledge Check at 2/3 (fails the 80 pass mark) via
  `qa_create_report_cohort._complete_attempt(rec, form, item, site, qs, opts, {qs[2].order}, 0, start, end)`.
  Its `complete()` recalculates the record: the seed's Welcome TopicProgress is written with
  `_base_manager.create` (no recalc), so the stored 0% jumps to 14% (1/7). Report that move.
- solo/plain: the only form on `functionality-demo-show-end-with-topic` is the survey
  "Course Feedback Survey" (CATEGORY_VALUE_SUM), player index 3; open sitting via the seed's `_open_attempt`.
- The tester's browser edits records between your inspect and your write (cohort record's
  completed_time appeared mid-task): snapshot immediately before writing, not at inspect time.
- Asked a SECOND time (Nov 2026): now scripted. `uv run python manage.py shell < .claude/agent-memory/sdd-qa-data-helper/qa_deadline_addon_attempts_script.py`
  (atomic; asserts neither record has a CourseFormAttempt yet, so re-run only right after the seed).
  Result: KC scores {score 2, max 3}, 3 QuestionAnswers, record 0 -> 14; solo survey open, 0 answers.
  Solo may already hold an unrelated completed KC FormProgress on its PARTS record (tester's own) -- leave it.
  A third ask -> promote to a `--with-addon-attempts` flag on qa_create_deadlines_seed.

## Parts-course player order (gotcha, Nov 2026)
Viewable order: 1 Welcome, 2 What to Expect, 3 Key Ideas, 4 Going Deeper (topic), 5 Knowledge Check
(form), 6 Summary, 7 Course Feedback (form). Completing only the first THREE topics unlocks Going
Deeper, NOT Knowledge Check -- a caller asked for that and assumed KC came 4th. Flag it; do not add
a fourth completion unasked. Complete topics like the player does: `TopicProgress.objects.get_or_create(
course_progress=, collection_item=, defaults={site_id, topic})`, then set complete_time + save() (signal
recalcs; 3/7 = 43%). Verify unlock with `_fetch_player_progress_maps` + `get_content_status` in
learner_interface/utils.py. CourseProgress has `learner` (not `user`); user = cp.learner.user.
