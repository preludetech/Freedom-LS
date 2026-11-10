---
name: reference-course-content-preview-command
description: qa_create_course_content_preview - educator course content preview QA seed (4 courses, widget-rich Welcome topic with real uploaded File rows, quiz+conditional survey, other-org course); delete-and-recreate so pks change every run
metadata:
  type: reference
---

`uv run python manage.py qa_create_course_content_preview [--site-name DemoDev]`
(educator-interface-course-content-preview, Nov 2026). Delete-and-recreate by slug
(qa-preview-course / qa-empty-course / qa-draft-outline / qa-other-org-course, children
slug-prefixed by course slug, Files under `qa-preview-files/`), so EVERY pk changes per run:
always report pks from the run's output. Reuses users/orgs/cohorts. Calls
`qa_create_single_org_educator` for qa-other-educator@example.com.

Facts learned:
- Course now HAS `organisations` m2m + `audience` (older memory saying "no org FK" is out of date
  for this). A course with no organisations is open to every org; set organisations=[X] with
  audience organisation_learners to keep it out of demodev.
- Educator course list = `courses_visible_to` (open-to-org published, or held via cohort/learner reg).
- Widget files: create `File` rows with FileFactory(file__data=..., file__filename=...); `src`
  resolves via `calculate_path_from_root(topic.file_path)`, so give topics a file_path.
- `c-content-link` calls `Topic.preview_url`, which reverses a commented-out URL: ANY topic holding
  a content-link 500s on render (Reading does in this seed, deliberately, per caller).
- Cohort registration fans out a CourseProgress per member; purge CourseProgress before Course.
