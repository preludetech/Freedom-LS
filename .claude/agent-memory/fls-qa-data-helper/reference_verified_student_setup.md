---
name: Verified student with course registration setup
description: Three pieces needed to create a QA student that can log in via browser and access a course
type: reference
---

To create a QA student user that can actually log in and view a course in the browser, three records are required:

1. `User` via `UserFactory(email=..., password=..., site=site)` from `freedom_ls.accounts.factories` — the factory's `post_generation` password hook sets password when extracted value is passed.
2. `allauth.account.models.EmailAddress` with `verified=True, primary=True` — without this, allauth redirects login to `/accounts/confirm-email/`. Use `get_or_create` keyed on `(user, email)`.
3. `UserCourseRegistration` via `UserCourseRegistrationFactory(user=user, collection=course, site=site)` from `freedom_ls.student_management.factories` — note the FK is `collection`, not `course`.

The DemoDev site is used for all QA data (see `feedback_use_demodev_site` in user-auto-memory, and `FORCE_SITE_NAME = "DemoDev"` in `config/settings_dev.py`).

Course lookups must filter by both `slug` AND `site` because `Course` is site-aware.

How to apply: When a QA tester asks for a test student who can log in and browse a course, make sure all three records exist. Wrap in idempotent get-or-create logic so re-running does not fail on unique constraints.
