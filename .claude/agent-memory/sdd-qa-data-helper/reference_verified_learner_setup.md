---
name: Verified learner with course registration setup
description: Three pieces needed to create a QA learner that can log in via browser and access a course
type: reference
---

To create a QA learner user that can actually log in and view a course in the browser, three records are required:

1. `User` via `UserFactory(email=..., password=..., site=site)` from `freedom_ls.accounts.factories` — the factory's `post_generation` password hook sets password when extracted value is passed.
2. `allauth.account.models.EmailAddress` with `verified=True, primary=True` — without this, allauth redirects login to `/accounts/confirm-email/`. Use `get_or_create` keyed on `(user, email)`.
3. `UserCourseRegistration` via `UserCourseRegistrationFactory(user=user, collection=course, site=site)` from `freedom_ls.learner_management.factories` — note the FK is `collection`, not `course`. The user FK is `user` (not `learner`); a query like `UserCourseRegistration.objects.filter(learner__user__email=...)` will raise `FieldError`.

The DemoDev site is used for all QA data (see `feedback_use_demodev_site` in user-auto-memory, and `FORCE_SITE_NAME = "DemoDev"` in `config/settings_dev.py`).

Course lookups must filter by both `slug` AND `site` because `Course` is site-aware.

How to apply: When a QA tester asks for a test learner who can log in and browse a course, make sure all three records exist. Wrap in idempotent get-or-create logic so re-running does not fail on unique constraints.

## Never trust a command's printed password for a pre-existing user

A `get_or_create`-style QA persona helper returns the existing user without resetting the
password, so for any learner that survived an earlier run the printed password may be wrong.
If none match, say so instead of guessing - and only rotate the password if you were actually
asked to.

## A persona without a verified EmailAddress is bounced to /accounts/confirm-email/

Symptom: **"the password is right but I land on Verify Your Email Address"** -> missing or
unverified `EmailAddress`, never a password problem.

**Use `update_or_create`, not `get_or_create`.** A persona who has already *tried* to log in
owns an `EmailAddress` row that allauth wrote with `verified=False, primary=False`.
`get_or_create` finds that row and leaves it broken; only `update_or_create(user=..., email=user.email, defaults={"verified":
True, "primary": True})` flips it.

`allauth.account.models.EmailAddress` has fields `(id, user, email, verified, primary)` and
**no site FK** -- it is not a `SiteAwareModel`, so "match the user's site" has nothing to set.

Password note: on this run all nine already hashed to `testpass123`, so nothing was rotated.
That does not repeal the warning above -- probe, never assume, in either direction.
