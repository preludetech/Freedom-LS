---
name: course-player-qa-student-command
description: Management command that seeds a login-ready student exercising the three course-player redirect/resume cases
metadata:
  type: reference
---

`uv run python manage.py qa_create_course_player_student [SITE_NAME]` (default `DemoDev`) seeds a single login-ready student for QA of the student course player. Command file: `freedom_ls/qa_helpers/management/commands/qa_create_course_player_student.py`. Idempotent.

It creates student `demodev_s1@email.com` (password == email, the project login convention; the `UserFactory` already defaults password to email) with a verified+primary allauth `EmailAddress` (required because `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`), and sets up:

- (a) Enrolled, NO progress, course WITH parts: `functionality-demo-course-parts` -> bare URL resolves to item 1. Stale `CourseProgress` is deleted to guarantee this.
- (b) Enrolled, WITH progress, resumes mid-course: `functionality-demo-show-end-with-topic`, `last_accessed_item` -> item 3 (a Form a few items in). Items 1-2 completed, item 3 started; pct ~29.
- (c) NOT enrolled: `functionality-demo-show-end-with-quiz` -> bare URL redirects to `/courses/<slug>/preview/`.

Resume logic lives in `freedom_ls/student_interface/utils.py::get_resume_index`: it reads `CourseProgress.last_accessed_content_type` + `last_accessed_object_id` (a GenericFK) and maps to a 1-based index in `course.viewable_items()`. To set a resume point, set those two fields directly (not via factory completion hooks). See [[reference_completing_a_course]] for why the save-hook approach and the missing-site gotcha bite here.

The 5 demo course slugs are: `content-widgets-demo-reference`, `functionality-demo-course-parts`, `functionality-demo-show-end-with-quiz`, `functionality-demo-show-end-with-topic`, `standard-markdown-demo-finance`. NOTE: these are NOT auto-loaded by `create_demo_data` (which only seeds sites/users/cohorts). Course CONTENT must be loaded per-course-dir with `uv run python manage.py content_save "demo_content/<course_dir>" DemoDev` — this validates + saves topics/forms/course + images, is idempotent (update_or_create keyed on UUID in frontmatter), and re-running picks up edited markdown. A fresh worktree DB may have zero courses until content_save is run. See [[reference_demo_content_loader]].

Note: there is no separate StudentProfile model — a "student" is just a `User` plus registrations. See [[reference_verified_student_setup]].
