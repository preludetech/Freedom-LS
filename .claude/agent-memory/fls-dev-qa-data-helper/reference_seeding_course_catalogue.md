---
name: seeding-course-catalogue
description: How to populate the student course catalogue (/courses/) on a site — courses come from demo_content, NOT from create_demo_data
metadata:
  type: reference
---

To make the student course catalogue at `/courses/` show cards on a site (e.g. DemoDev):

- The catalogue is `get_course_listing(user)` -> `get_all_courses()` -> `Course.objects.all()` (site-aware manager). There is NO `published`/`visible`/`status` flag on `Course`. "Published/visible" simply means a `Course` row exists on the current site. Every Course on the site appears as a card; per-user status (NOT_REGISTERED / REGISTERED / IN_PROGRESS / COMPLETE) comes from `UserCourseRegistration` + `CourseProgress`.
- `Course.save()` assigns `accent_slot = Course.objects.filter(site_id=...).count() % len(PALETTE)` on first save, so loading N courses in sequence yields distinct accent slots 0,1,2,... — load several demo courses to exercise multiple accent palette slots.

GOTCHA: `student_management/management/commands/create_demo_data.py` does NOT create any courses or content. It only creates Sites, superusers, student users (demodev_s1..N), cohorts, and memberships. Running it on an empty DB leaves `/courses/` empty. To get courses you MUST load demo content separately.

Load courses with `content_save` (see [[reference-demo-content-loader]]), one dir per course:
`uv run python manage.py content_save "demo_content/<dir>" DemoDev`
Demo course dirs (each = one Course): functionality_demo_content_widgets, functionality_demo_standard_markdown, functionality_demo_end_with_topic, functionality_demo_end_with_quiz, functionality_demo_course_parts.

To enroll demodev_s1 in courses WITH progress for free, run the existing command
`uv run python manage.py qa_create_course_player_student DemoDev`
(djclick). It enrolls demodev_s1 in functionality-demo-course-parts (0% / REGISTERED) and functionality-demo-show-end-with-topic (~29% / IN_PROGRESS, resumes item 3), leaves functionality-demo-show-end-with-quiz NOT enrolled. Requires those 3 course dirs be content_save'd first or it raises ClickException listing available slugs. See [[reference_course_player_student_command]] and [[reference_verified_student_setup]].
