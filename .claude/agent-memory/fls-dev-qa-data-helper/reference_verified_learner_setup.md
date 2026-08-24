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

`qa_create_cohort_progress` ends with `All learner passwords: testpass123`, but its
`_create_learner()` does `return User.objects.get(email=email)` when the user already
exists - **without resetting the password**. So for any learner that survived an earlier
run, the printed password is wrong.

Observed: `qa-carol.starter@example.com` (that command's "Carol Starter" persona) had
`check_password("testpass123") == False`; her real password was her own email address,
`qa-carol.starter@example.com`, matching the branch convention "password == email"
([[reference_form_engine_branch_qa_baseline]]).

Before reporting credentials to a tester, probe the candidates rather than quoting the
command's output:

```python
for cand in ["testpass123", u.email]:
    print(cand, u.check_password(cand))
```

Same trap applies to any `get_or_create`-style QA persona helper. If none match, say so
instead of guessing - and only rotate the password if you were actually asked to.
