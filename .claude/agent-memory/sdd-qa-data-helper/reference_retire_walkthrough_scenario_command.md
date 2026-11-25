---
name: reference-retire-walkthrough-scenario-command
description: qa_create_retire_walkthrough_scenario — pre-retirement seed for the retire-removed-content branch (qa-retire-a/b fresh learners, QA Retire Cohort with qa-cohort-1/2 and scored Shuffled quiz sittings); collides with qa_create_retired_content_scenario on the cohort name
metadata:
  type: reference
---

Asked Nov 2026 (branch sacaa-...-2-retire-removed-content). Content is LIVE when it runs; the
tester retires things afterwards with their own content edits. Command:
`uv run python manage.py qa_create_retire_walkthrough_scenario [--site-name DemoDev]`.
It reuses `qa_create_retired_content_scenario` helpers (`_sit_quiz_before_retirement`,
`_complete_course_parts`, `_get_or_create_cohort`) and multiselect helpers.

- qa-retire-a/b@example.com: individual LCR on functionality-demo-shuffled-quiz, "Planets and
  the sky" done, NO Shuffled quiz FormProgress.
- "QA Retire Cohort" (org demodev, pk 7d1f92a3-...): members qa-cohort-1/2, sittings via
  complete() (served paper, asked). cohort-1 wrong on Moon->"The Sun" and sky->"Green" (7/9).

GOTCHA: the OLDER `qa_create_retired_content_scenario` uses the SAME cohort name and adds
qa.retire.a/b (dots) plus a registration on the retired show-end-with-topic course. That
registration is PROTECTED by those learners' CourseProgress, so it cannot be deleted without
deleting their progress; I set it is_active=False and deleted only their 2 memberships
(cascade nothing). Running the old command again re-adds them (it does not reactivate the reg).
demodev@ is superuser: cohort page 200 with no grant needed.
