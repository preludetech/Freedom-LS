---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/course_applications/templates/course_applications/email/application_claim_subject.txt
  - freedom_ls/course_applications/templates/course_applications/email/application_claim_message.txt
  - freedom_ls/course_applications/templates/course_applications/email/application_claim_message.html
  - freedom_ls/course_applications/templates/course_applications/application_status.html
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
  - freedom_ls/course_applications/templates/course_applications/claim.html
  - freedom_ls/course_applications/templates/course_applications/form_page.html
  - freedom_ls/course_applications/templates/course_applications/partials/claim_link_notice.html
  - freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html
  - freedom_ls/learner_interface/templates/learner_interface/dashboard.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: anon-application-improvements

An anonymous applicant on a course with an application form now gets the claim email straight
after the applicant details step, not at submit. That link claims a draft as well as a submitted
application. The applicant can change the address on a draft (details step) and on a submitted
unverified application (status page), and every link sent to the earlier address stops working.
The dashboard's "Your applications" panel shows the drafts an anonymous session holds, and the
course page shows "View my application" for an application the session owns.

## Breaking changes

- **`send_application_claim_email` takes a required `is_submitted` keyword.**
  `freedom_ls.course_applications.emails.send_application_claim_email(request, applicant, *, is_submitted)`
  picks the email's wording from it. A downstream call without the keyword raises `TypeError`.
- **`attach_to_user` returns an `AttachResult`, not the application.**
  `freedom_ls.course_applications.claims.attach_to_user` now returns
  `freedom_ls.course_applications.claims.AttachResult`, with `.application` (the application the
  account holds for the course afterwards) and `.discarded_draft`. A caller that used the return
  value as a `CourseApplication` must read `.application`. The merge rule also changed: a held
  **draft** no longer beats an incoming draft. The incoming application loses only when the held one
  is submitted; otherwise the held draft and its sitting are deleted and the incoming one is attached.
- **`ApplicantDetailsForm.tripped_honeypot` is gone.** The property on
  `freedom_ls.course_applications.forms.ApplicantDetailsForm` was replaced by the module function
  `freedom_ls.accounts.forms.tripped_honeypot(form)`, which works on any form that carries the
  honeypot field. A downstream form or view that read the property gets `AttributeError`.
- **Claim token payload changed.** `freedom_ls.course_applications.claims.claim_token` now signs
  `{"a": <applicant pk>, "v": <claim_link_version>}` instead of a bare pk string. Links already in
  mailboxes keep working: `read_claim_token` reads a bare-pk token as version 0, which is what
  every existing row gets from the migration. They stop working once the applicant changes their
  address. Only code that builds or parses claim tokens itself is affected.
- **Claim email wording branches on `is_submitted`.** The three templates under
  `freedom_ls/course_applications/templates/course_applications/email/` now render draft wording
  ("Continue your application", "You started an application for …") when `is_submitted` is false
  and the previous wording when it is true. A downstream project that overrides any of them keeps
  sending "We received your application" to applicants who have not submitted. Add the branch.
- **Dashboard panels render for anonymous visitors.** `learner_interface`'s dashboard view now
  calls `get_dashboard_contributions_for_request(request=request)` for every visitor and the
  template no longer wraps the panel loop in `{% if user.is_authenticated %}`. The base default
  returns `[]` for an anonymous request, so a backend that only overrides
  `get_dashboard_contributions(user=...)` still shows nothing to a visitor. A downstream override
  of `freedom_ls/learner_interface/templates/learner_interface/dashboard.html` that kept the old
  guard hides the anonymous drafts panel.

## New extension points

`freedom_ls.course_access.backends.CourseAccessBackend` gains two request-aware methods. Neither
changes the signature of an existing method, so a downstream backend that overrides
`get_access(self, *, user, course)` keeps working.

- `get_access_for_request(self, *, request, course)`. Default: `self.get_access(user=request.user, course=course)`.
  The course detail page now calls this one.
- `get_dashboard_contributions_for_request(self, *, request)`. Default: `[]` for an anonymous
  request, otherwise `self.get_dashboard_contributions(user=request.user)`. The dashboard now
  calls this one.

`freedom_ls.course_access.backends.VisibilityEnforcingBackend` applies its coming-soon, hidden and
free-override checks in `get_access_for_request` and forwards both methods to the wrapped backend.

`freedom_ls.course_applications.backends.ApplicationCourseAccessBackend` overrides both: for an
anonymous session it returns "View my application" for an application the session owns, and the
session's unfinished drafts as the dashboard panel. **A downstream subclass that overrides
`get_access` or `get_dashboard_contributions` must also override the matching request-aware
method**, otherwise its signed-in behaviour and the anonymous behaviour diverge: the request-aware
methods call `self.get_access` or `self.get_dashboard_contributions` only for a signed-in user.

## Manual steps

1. Run `manage.py migrate`. The migration
   `freedom_ls_course_applications.0007_anonymousapplicant_claim_link_version` adds
   `AnonymousApplicant.claim_link_version` (`PositiveIntegerField`, default 0).
2. Review any override of the templates listed in `changed_template_paths`:
   - The three claim email templates need the `is_submitted` branch described above.
   - `application_status.html` gains a change-of-address form posting to the new URL
     `course_applications:change_applicant_email` (`status/<uuid:pk>/change-email/`, POST only)
     and no longer says the email was sent on submission.
   - `form_page.html` and `check_your_answers.html` include the new
     `course_applications/partials/claim_link_notice.html` partial for an unverified draft.
   - `claim.html` has draft wording and says which application survives when the address's owner
     already holds one for the course.
   - `dashboard.html` drops the `is_authenticated` guard around the panel loop.
3. If a downstream backend subclasses `ApplicationCourseAccessBackend` and overrides `get_access`
   or `get_dashboard_contributions`, override `get_access_for_request` or
   `get_dashboard_contributions_for_request` too.
4. Update any downstream call to `send_application_claim_email` to pass `is_submitted=`, and any
   caller of `attach_to_user` to read `.application` from the result.
5. If the webhook consumer assumes `user.registered` means an application was submitted, stop
   assuming it: a claim can now create the account for a draft, so the event can fire before any
   submission.

No settings, Python packages or npm packages changed. Every Tailwind utility class the changed
templates use was already in the bundle, so no rebuild is needed.
