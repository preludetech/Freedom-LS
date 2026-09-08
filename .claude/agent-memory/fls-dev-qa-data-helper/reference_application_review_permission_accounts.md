---
name: reference-application-review-permission-accounts
description: qa_create_application_review_accounts — applicant/bystander/reviewer trio for the "three view_ perms do not open the admin" walkthrough; SuperuserOnlyAdmin is why
metadata:
  type: reference
---

`qa_create_application_review_accounts [--site-name DemoDev]`
(`freedom_ls/qa_helpers/management/commands/`) seeds three DemoDev accounts,
password == email, verified+primary allauth `EmailAddress`, fully idempotent
(re-running RESETS flags, password, perms, groups and purges apps/registrations):

- `qa_applicant@email.com` (pk 73) — plain learner, `Learner` row in the DemoDev
  default organisation via `LearnerFactory` (which delegates to `ensure_learner`),
  zero `CourseApplication`, zero registrations.
- `qa_bystander@email.com` (pk 74) — identical shape.
- `qa_reviewer@email.com` (pk 75) — `is_staff=True`, `is_superuser=False`, exactly
  three permissions granted DIRECTLY on the user, no groups.

## App label is `freedom_ls_form_engine`, not `form_engine`

Every FLS app's `AppConfig.label` is prefixed. The three codenames are
`freedom_ls_form_engine.view_questionanswer` / `.view_formprogress` /
`.view_questionanswerfile`. Resolve permissions through
`ContentType.objects.get_for_model(Model)` rather than hard-coding an app label —
it is right whatever the label is, and it fails loudly if the row is missing.

## Direct `user_permissions` grants are fine here

No project convention forbids them: `qa_create_report_fixtures` and
`form_engine/tests/test_admin.py` both use `user.user_permissions`. Guardian
`assign_perm` is for OBJECT-level grants (`view_cohort` on a cohort), a different
axis — do not reach for it when the ask is a model permission.

## Why the three perms buy nothing (the assertion under test)

`FormProgressAdmin` / `QuestionAnswerAdmin` / `QuestionAnswerFileAdmin` all mix in
`SuperuserOnlyAdmin` (`freedom_ls/form_engine/admin.py:30`), which overrides
`has_view_permission` / `has_change_permission`. Probed with a rolled-back logged-in
`Client`: `/admin/` returns **200** (staff, so the index renders) while all three
changelists return **403**. So "no admin access" means the model pages 403 and are
absent from the index — it does NOT mean the login bounces.

## Purge order when resetting an existing account

`CourseProgress.learner_registration` is **PROTECT**, so progress rows go before
`LearnerCourseRegistration`. Cohort-granted courses are removed by deleting the
learner's `CohortMembership`, never the `CohortCourseRegistration` (that belongs to
the cohort, not the person). Use `_base_manager` throughout — a command has no
ambient site.

DemoDev is Site **id 3, domain `127.0.0.1:8324`** on this branch (older notes say
`:8000` — always re-read `Site.objects`). No `SiteSignupPolicy` rows exist and
`ADDITIONAL_REGISTRATION_FORMS == []`, so nothing gates these logins after
verification.
