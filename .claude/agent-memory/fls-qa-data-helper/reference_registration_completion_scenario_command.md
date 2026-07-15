---
name: reference-registration-completion-scenario-command
description: qa_create_registration_completion_scenario command + DB-backed QAProfileCompletionForm — gate new signups via RegistrationCompletionMiddleware while a seeded student stays complete
metadata:
  type: reference
---

`qa_create_registration_completion_scenario <SITE_NAME>` (default DemoDev)
seeds the Workflow-7 "forced registration completion" + course-access QA
scenario. It REUSES the factory-based builders from
[[reference_course_access_types_command]] (imports `_get_or_create_learner`,
`_ensure_verified_email`, `_get_or_create_course` + the slug/title constants),
so it produces the SAME learner + courses, then adds the policy/completion bits:

- FREE course slug `qa-free-course-access-types` (access `free`, published, in
  anon catalogue, 1 viewable Topic) — free-access flow at `/courses/<slug>/access/`
  (name `student_interface:initiate_course_access`).
- GATED course slug `qa-application-gated-course-access-types` (access
  `application_gated`, published, anon catalogue). Apply flow is mounted at
  `/applications/apply/<slug>/` (name `course_applications:apply`), NOT `/apply/`.
- Student `demodev_access_learner@email.com` (password == email), verified+primary
  allauth EmailAddress, ZERO regs/apps, and registration-COMPLETE.
- `SiteSignupPolicy` for the site: `allow_signups=True`, `require_name=True`,
  `require_terms_acceptance=True` (preserve dev defaults — a fresh policy row
  otherwise silently resets these to model defaults, see
  [[reference_additional_registration_form_qa]]),
  `additional_registration_forms=['freedom_ls.qa_helpers.registration_forms.QAProfileCompletionForm']`.

KEY DESIGN — why a NEW form/model instead of the `accounts/tests` fixtures:
`PhoneNumberForm`/`AlwaysIncompleteForm` track completion in a PROCESS-LOCAL
dict, so (a) a `runserver` restart re-gates everyone and (b) you canNOT make a
seeded student persistently "complete" from a management command (different
process). To satisfy "new signups gated BUT seeded student stays complete" you
need DB-backed completion. Added to the dev-only `qa_helpers` app (NOT core):
- `freedom_ls/qa_helpers/models.py` → `QARegistrationCompletion` (OneToOne user
  marker; migration `0001_initial`; app label `freedom_ls_qa_helpers`).
- `freedom_ls/qa_helpers/registration_forms.py` → `QAProfileCompletionForm`
  (protocol-compliant `forms.Form`; one field `how_did_you_hear`; `applies_to`
  = not staff/superuser; `is_complete` = a `QARegistrationCompletion` row exists;
  `save` upserts the row). Field name avoids the FORBIDDEN set {user,user_id,email}.
- `freedom_ls/qa_helpers/factories.py` → `QARegistrationCompletionFactory`
  (plain `DjangoModelFactory`, NOT SiteAware — model keys off the site-aware
  User; `django_get_or_create=("user",)` for idempotency).

Verify the gate with `get_incomplete_forms(user, policy.additional_registration_forms)`:
seeded student → `[]` (passes), a fresh non-staff user w/ no marker →
`['QAProfileCompletionForm']` (redirected to `accounts:complete_registration`).
`qa_helpers` is only in `config/settings_dev.py` INSTALLED_APPS (dev DB = the QA DB).
