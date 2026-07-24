---
name: reference-additional-registration-form-qa
description: How to require a post-verification "Complete your registration" form on a site for QA (Workflow 7), and why demodev@email.com can't be the test subject
metadata:
  type: reference
---

Workflow 7 = a brand-new signup, after email verification, is routed to a
"Complete your registration" page when its site requires an
`additional_registration_forms` entry.

To require one on a site (data-only, no app-code change):
1. There is NO real (non-test) registration Form class shipped in the app.
   The only in-repo implementations are TEST FIXTURES in
   `freedom_ls/accounts/tests/_completion_view_fixtures.py`:
   - `PhoneNumberForm` — valid `forms.Form`, protocol-compliant, one
     `phone_number` field, `applies_to` returns False for staff/superuser,
     `is_complete` checks in-process dict `STORED_PHONE_NUMBERS`.
   - `AlwaysIncompleteForm` — never complete (forces the redirect forever).
   Dotted path e.g.
   `freedom_ls.accounts.tests._completion_view_fixtures.PhoneNumberForm`.
   It loads cleanly through `load_registration_form_classes`. Using a form
   from `tests/` is the only option when told "no application code changes".
   Caveat: PhoneNumberForm's completion state lives in an in-process dict, so
   a `runserver` restart re-gates anyone who "completed" it (fine/repeatable
   for QA).
2. Create the site policy:
   `SiteSignupPolicy.objects.update_or_create(site=dd, defaults={
     "allow_signups": True, "additional_registration_forms": [FORM_PATH]})`.
   The dev global default `ADDITIONAL_REGISTRATION_FORMS = []`, so a policy
   row is REQUIRED to require a form on DemoDev.

GOTCHA — creating a `SiteSignupPolicy` row overrides ALL settings fallbacks
for that site, incl. `require_terms_acceptance`. `settings_dev.py` sets
`REQUIRE_TERMS_ACCEPTANCE = True` (base is False). Without a row DemoDev
inherited True; a fresh row defaults it to False, silently weakening the
signup flow. Set `require_terms_acceptance=True` explicitly on the row to
preserve dev behavior. Helpers: `get_effective_*` in
`freedom_ls.accounts.utils`.

GOTCHA — `demodev@email.com` (created by `create_demo_data`) is a
STAFF+SUPERUSER, not a plain learner. `get_incomplete_forms` short-circuits
superusers to `[]`, so the registration gate NEVER fires for it. To exercise
Workflow 7 you need a non-staff verified learner (e.g. the
`demodev_access_learner@email.com` from `qa_create_course_access_types`, or a
genuinely new browser signup). Verify the gate with
`get_incomplete_forms(learner, forms)`.

See [[reference_course_access_types_command]] and [[reference_verified_student_setup]].
