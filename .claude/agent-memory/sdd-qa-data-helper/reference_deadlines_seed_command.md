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
