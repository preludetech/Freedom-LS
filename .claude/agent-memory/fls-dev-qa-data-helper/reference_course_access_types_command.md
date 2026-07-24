---
name: reference-course-access-types-command
description: qa_create_course_access_types command — free + application-gated courses and an unenrolled verified learner for the Course Access Types feature QA
metadata:
  type: reference
---

`qa_create_course_access_types <SITE_NAME>` (default DemoDev) seeds the
"Course Access Types — Free & Application-Gated" feature QA scenario:

- Learner `demodev_access_learner@email.com` (password == email, per project login convention), verified+primary allauth EmailAddress, ZERO `UserCourseRegistration` and ZERO `CourseApplication` (the command deletes any for the learner each run to guarantee the clean first-time state).
- FREE course slug `qa-free-course-access-types`, `access_config={"access_type": "free"}`, one viewable Topic.
- GATED course slug `qa-application-gated-course-access-types`, `access_config={"access_type": "application_gated"}`, one viewable Topic.

`Course.access_config` is a JSONField; `{}` or missing access_type also means "free" (default backend). Valid `access_type` values for the shipped `ApplicationCourseAccessBackend`: `free`, `application_gated`.

GOTCHA: `Course.children()`/`children_flat()`/`viewable_items()` are memoized per instance (see model comment). If you create the `ContentCollectionItem` link AFTER having already called `viewable_items()` on that same Course instance, the in-process count stays 0 even though the DB row is correct. Re-query the Course (fresh instance) to see the link, or build the links before reading children. The command's inline summary can therefore print `viewable_items=0` while the DB is actually correct — verify with a fresh query.

Build viewable content via `ContentCollectionItemFactory(collection_object=course, child_object=topic, site=site)` (dual GenericFK). See [[reference_demo_content_loader]] and [[reference_verified_student_setup]].

DemoDev domain is stored as `127.0.0.1:8000` in the Site record, BUT in dev this domain is irrelevant to site resolution: `config/settings_dev.py` sets `FORCE_SITE_NAME = "DemoDev"`, so `get_cached_site()` (freedom_ls/site_aware_models/models.py) always returns DemoDev for EVERY request regardless of host/port. So `runserver` on ANY port (e.g. 127.0.0.1:8903) serves DemoDev data — no hosts file/domain/query-param needed. The header shows "FirstClass" because that is `HEADER_TITLE` branding in settings_dev.py, NOT a site; testers often mistake it for a different site.
