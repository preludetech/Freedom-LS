---
name: reference-application-docs-scenario-command
description: qa_create_application_docs_scenario command — premium gated course + learner with in-flight CourseApplication + in-progress free course, for course-applications product-doc screenshots
metadata:
  type: reference
---

`qa_create_application_docs_scenario <SITE_NAME>` (default DemoDev) seeds a
presentable scenario for documenting the course-applications feature:

- Learner `demodev_applicant@email.com` (password == email), verified+primary
  allauth EmailAddress, login-ready. Distinct from `demodev_access_learner@email.com`
  used by [[reference_course_access_types_command]] (that one has ZERO apps/regs).
- GATED course slug `advanced-product-analytics-masterclass`,
  `access_config={"access_type":"application_gated"}`, ADVANCED difficulty,
  ~18 hours, 5 learning_outcomes, rich description + content, one viewable Topic.
  Learner has NO UserCourseRegistration to it (so "Apply now" CTA shows) but
  HAS exactly one in-flight `CourseApplication` (dashboard panel + status page render).
- FREE course slug `getting-started-with-product-metrics`, learner enrolled +
  in-progress (1 of 2 topics complete, CourseProgress.progress_percentage=50)
  so the dashboard "in progress" section is populated.

GOTCHAS confirmed while building this:
- `TopicProgress` completion field is `complete_time` (no 'd'); `FormProgress`
  uses `completed_time`. Easy to mix up — they share the `CourseItemProgress`
  base but declare different `completion_field_name`.
- `UserCourseRegistration` FK to the course is `collection` (not `course`).
- Course-applications URLs are mounted at `/applications/` (config/urls.py);
  status name is `course_applications:status`, path `/applications/status/<uuid:pk>/`.
- `CourseApplication` has a unique constraint on (site, user, course); use
  get_or_create. Backend is `ApplicationCourseAccessBackend`
  (settings.COURSE_ACCESS_BACKEND).

See [[reference_course_access_types_command]] for the related free/gated access
fixture and the children() memoisation gotcha.
