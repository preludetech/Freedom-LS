---
name: reference-admonition-scenarios-command
description: qa_create_admonition_scenarios - callout QA seed (TOC-in-dev widgets course, demodev paused/ended/quiz registrations, qa-solo-org sole admin, delete cascade/blocked cohorts, refused-move race); where each callout comes from
metadata:
  type: reference
---

`uv run python manage.py qa_create_admonition_scenarios [--site-name DemoDev]` (misure-of-admonitions,
Nov 2026). Idempotent; never touches demodev@'s password. Tested helpers (dev_tooling marker).

Where the callouts come from (verified with test client, force_login):
- Learner detail `/courses/<slug>/detail/`: `paused_at`/`planned_resume_on` from an open `CoursePause`
  (use `deadlines.actions.pause_course(record, planned_resume_on=, now=)`); `access_ended_at` from
  `LearnerCourseRegistrationDeadlineConfig(end_course_access=ON)` + a FIXED course-level
  `LearnerDeadlineOverride` in the past. Pause wins over ended.
- Educator course page `/educator/organisations/<org>/courses/<pk>` stacks the content panel
  (`__panels/content`); preview_available = `is_course_available_to_organisation` (course with no
  organisations m2m is open to all orgs).
- "Only staff member" intro needs StaffMember/role rows: a superuser with no row is NOT staff.
  The self row offers only Deactivate role (`staff/__actions/deactivate_role?user=7&role=organisation_admin`),
  not Deactivate staff member; that dialog carries the only-admin warning.
- The ONLY educator DeleteAction is `DeleteEmptyCohortAction` (cohort Settings > Status). Cohort has no
  PROTECT relations, so "blocked" = known reason (non-empty / import running): only via the two-tab race
  (open dialog on empty cohort, add a member elsewhere, confirm -> 422) or a raw GET of the action URL.
  Cascade list = empty cohort with CohortDeadlineConfig + CohortMessagingConfig.
- Move refusal (move_confirmation `refusal`) only via race: pick destination, add the learner to it
  in another tab, click Move -> 422 "Choose a cohort from the list." Needs another joinable cohort left.
