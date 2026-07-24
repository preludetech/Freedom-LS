---
name: reference-webhook-qa-setup
description: Setup for manual browser QA of the webhooks feature (course.registered etc.) on DemoDev — reuse access-types courses + a fresh unenrolled student
metadata:
  type: reference
---

For manual browser QA of the webhooks feature on DemoDev, the tester needs three flows that each fire a webhook (e.g. `course.registered`): a fresh self-enrol, a free-course completion, and an application-gated apply (fires NO course.registered).

Reuse the two courses created by [[reference_course_access_types_command]] (`qa_create_course_access_types`) — they already satisfy the access_type needs and avoid duplicates:
- FREE, self-serve, completable: slug `qa-free-course-access-types`, `access_config={"access_type":"free"}`, 1 viewable Topic (single item = last item, so the player shows "Finish Course" immediately — fast to complete end-to-end).
- APPLICATION-GATED: slug `qa-application-gated-course-access-types`, `access_config={"access_type":"application_gated"}` → detail page "Apply now", enrol redirects to apply page.

The webhook student is separate from the access-types learner: `webhook_qa_student@email.com` (password == email, project login convention), verified+primary allauth EmailAddress, DemoDev site, and deliberately ZERO UserCourseRegistration + ZERO CourseApplication so course.registered fires fresh. Created via a one-off idempotent shell script (UserFactory + EmailAddress.update_or_create + delete regs/apps). If webhook requests recur, promote to a `qa_create_webhook_scenario` command. See [[reference_verified_student_setup]].
