---
name: reference-course-visibility-command
description: qa_create_course_visibility command — student+educator and 4 courses (published/coming_soon/hidden/hidden-registered) for the Coming Soon & Hidden Courses feature QA
metadata:
  type: reference
---

`qa_create_course_visibility <SITE_NAME>` (default DemoDev) seeds the
"Coming Soon & Hidden Courses" course-visibility feature QA scenario. Idempotent.

Accounts (login-ready: verified+primary EmailAddress, password == email):
- Student `demodev_visibility_student@email.com`
- Educator `demodev_visibility_educator@email.com` (owns `QA Visibility Cohort`,
  granted object-level `view_cohort`, cohort registered for the published course)

Courses (4, each with one viewable Topic):
- `qa-published-free-visibility` — visibility=published, access_config={"access_type":"free"}
- `qa-coming-soon-visibility` — visibility=coming_soon
- `qa-hidden-visibility` — visibility=hidden, student NOT registered (command deletes any such row each run)
- `qa-hidden-registered-visibility` — visibility=hidden, student IS registered (mid-course access)

Student registered in `qa-hidden-registered-visibility` + `qa-published-free-visibility` only.
NO CourseInterest rows are pre-created — tester makes those via the UI.

Key model facts for this feature (branch `courses_coming_soon`):
- `Course.visibility` CharField, choices `CourseVisibility` in `freedom_ls/content_engine/models.py`:
  `published` / `coming_soon` / `hidden`, default `published`.
- `course_interest` app: `CourseInterest(user, course, created_at)` with
  unique (user, course). Factory `CourseInterestFactory` (FKs `user`, `course`).
- Educator interface (`/educator/...`) is gated ONLY by `@login_required` — no
  staff flag needed. `CourseDataTable` shows ALL site courses (`Course.objects.all()`,
  site-aware), with `Visibility` and `Interest` (annotated `interest_count`) columns.
  `CourseInstanceView.panels["interest"] = CourseInterestPanel` (interested-students drill-down).
- Demo content course "Content Widgets - Demo Reference"
  (`demo_content/functionality_demo_content_widgets/course.md`) has `visibility: coming_soon`
  in frontmatter, but is only present on DemoDev if `content_save` has been run — the command
  creates its own coming-soon course to stay self-contained.

GOTCHA repeated from [[reference_course_access_types_command]]: `Course.viewable_items()`/
`children()` are memoized per instance — re-query a fresh `Course.objects.get(pk=...)`
before counting viewables after adding a `ContentCollectionItem`.

See [[reference_verified_student_setup]], [[reference_educator_cmodal_trigger]] (view_cohort perm).
