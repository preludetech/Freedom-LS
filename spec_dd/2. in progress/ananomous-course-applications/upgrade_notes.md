---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_applications/templates/course_applications/apply.html
  - freedom_ls/course_applications/templates/course_applications/application_status.html
  - freedom_ls/base/templates/allauth/layouts/manage.html
requires_settings_change: true
changed_settings:
  - ACCOUNT_RATE_LIMITS  # optional: only projects that define their own dict must add three keys
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: anonymous course applications

Anonymous visitors can now apply to an `application_gated` course without signing up first. A new
applicant details step at `course_applications:applicant_details` collects their name, email and
consent. Their `CourseApplication` is stored with no user. After they submit, an email sends them a
claim link (`course_applications:claim`), and following it creates or signs in their account and
attaches the application. Signed-in apply works as before.

## Breaking changes

- **`CourseApplication.user` and `FormProgress.user` can now be null.** An application or sitting
  that nobody has claimed yet has no user. Any downstream code that reads `application.user.…` or
  `form_progress.user.…` without checking for `None` needs updating. That includes signal receivers
  on `FormProgress`, admin customisations and reports. `CourseApplication` has new
  `applicant_email`, `applicant_name` and `is_email_verified` properties that work for both kinds
  of application, plus a new `anonymous_applicant` one-to-one to `AnonymousApplicant`.
- **The `unique_application_per_site_user_course` constraint is now conditional.** It covers only
  applications with no `anonymous_applicant`. A user can therefore hold two applications for the
  same course after a claim. `get_application_for_course` returns a submitted one ahead of any
  draft, and the newer among equals; `get_active_applications` lists each course once by the same
  rule, and the check-your-answers page sends a draft that a claimed submission has superseded to
  that submission's status page. Code that calls `CourseApplication.objects.get(user=…, course=…)`
  can raise `MultipleObjectsReturned`.
- **A claim onto an account that never verified the address revokes its password.** The claim
  verifies the address, revokes whatever password the account had, and sends the claimant to set
  a new one. This applies to an unconfirmed signup and to an account an operator created by hand,
  since neither password was set by someone who had proven they owned the mailbox. An account that
  had verified the address keeps its password. A verified account with no usable password is also
  sent to set one.
- **Deleting a `CourseApplication` deletes its user-less `FormProgress`.** A post-delete receiver
  removes the sitting, its answers and its stored files when the application had no user, so a
  course or applicant deletion no longer leaves an orphaned sitting behind. A sitting with a user
  is left alone. Downstream code that deleted such sittings by hand should use
  `filter(pk=…).delete()` rather than `get(pk=…)`, which now raises `DoesNotExist` for them.
- **Anonymous visitors are no longer redirected to signup by Apply now.** `apply`,
  `application_status`, `application_form_page`, `application_check_answers` and the form_engine
  file endpoints no longer use `login_required`. Access is limited to the requester's own
  application, either through their user or through their session. A project that relied on these
  views redirecting anonymous visitors to login will see the details step instead.
- **Anonymous uploads use a new storage key:**
  `user_uploads/anonymous/<form_progress_id>/form_answers/`. Any bucket policy or lifecycle rule
  keyed on `user_uploads/<user_id>/` should cover this prefix too.
- **`SiteAwareSignupForm._log_honeypot_trip` was removed.** It is now a module-level function in
  `freedom_ls/accounts/forms.py`. Subclasses that called or overrode the method must change. The
  signup form's field-building is now spread across the public helpers `honeypot_field`,
  `reject_honeypot`, `apply_signup_name_policy`, `add_consent_fields` and `accepted_legal_docs`.

## Manual steps

1. Run `uv run manage.py migrate`. Five new migrations:
   `freedom_ls_accounts` `0002_alter_legalconsent_consent_method` (new `application_details_step`
   consent method) and `0003_user_email_upper_index` (an index for case-insensitive email
   lookups), `freedom_ls_course_applications` `0004_anonymousapplicant_and_more` (the
   `AnonymousApplicant` model, nullable `CourseApplication.user`, the conditional constraint) and
   `0005_anonymousapplicant_claim_email_sent_at` (when the claim email last went out), and
   `freedom_ls_form_engine` `0008_alter_formprogress_user` (nullable `FormProgress.user`).
2. **If your project sets its own `ACCOUNT_RATE_LIMITS`**, add the three new actions. Without them,
   the details step, the claim email and file uploads have no rate limit. FLS's defaults are:

   ```python
   "application_details": "5/m/ip,5/h/key",
   "application_claim_email": "3/h/key",
   "form_file_upload": "20/m/key",
   ```

   The upload limit is keyed on the sitting, not the client address, so a room of learners behind
   one network address do not share a bucket; keep the `/key` suffix. A refused upload re-renders
   the file widget with the reason at HTTP 422. No system check enforces this. Projects that
   inherit FLS's `ACCOUNT_RATE_LIMITS` need do nothing.
3. In production, make sure `CACHES` points to a cache that all processes share (for example
   `DATABASE_CACHES` from `freedom_ls/deployment/settings_defaults.py`). A per-process local-memory
   cache lets each worker count separately, so the limits are not enforced as configured.
4. If you override any of these templates, re-apply your changes against the new versions:
   - `course_applications/apply.html`: shows a Previous button (`previous_page_url`) in place of
     Cancel when the details step came before it.
   - `course_applications/application_status.html`: new branch for an unverified application that
     tells the applicant to follow the emailed link.
   - `allauth/layouts/manage.html`: narrowed and centred layout.

   These templates are new and can be overridden for theming:
   `course_applications/applicant_details.html`,
   `course_applications/partials/applicant_details_field.html`, `course_applications/claim.html`
   and the claim email (`course_applications/email/application_claim_subject.txt`,
   `application_claim_message.txt`, `application_claim_message.html`).
5. Note: the claim link expires after allauth's `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`. Nothing
   needs to change unless you want a different lifetime.
6. No automatic purge runs. Unclaimed applicants and their applications stay until an operator
   deletes the `AnonymousApplicant` in the admin, which removes its application, sitting and files.
   Check that your privacy notice matches this.
