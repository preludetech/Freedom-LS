# Anonymous course applications

## Why

Anonymous visitors who click **Apply** are sent to the full signup page today. That means a
password, consent boxes and mandatory email verification, and only after that do they come back to
the course application. Many get derailed there and never apply. Checkout research points the same way. It
says to defer the account and the password, not the contact details (`research_guest_apply_ux_patterns.md`).

## Starting over

An earlier attempt at this went through several iterations and ended up far more complicated than
the problem calls for. The `allow-course-apply-anon` branch, its worktree and its spec directory are off
limits. We reuse nothing from them and reference nothing in them. Keeping the result simple is a goal in its
own right.

## What we are doing

1. **Authenticated users: no change.** Applying works exactly as it does now.
2. **Anonymous users get an extra first step: the applicant details step.** It asks for what signup
   normally asks for, minus the password. That is email, first name, last name, and the
   Terms/Privacy checkboxes when the site's `SiteSignupPolicy` requires them, plus the signup
   honeypot. The step looks like any other page of the application form and uses the same
   `form_engine` input widgets. It sits in the page sequence ahead of the application form's own
   pages, and Previous on the first form page returns to it.
3. **This applies to every application-gated course.** A course with an application form gets the
   details step and then its form pages. A course with no form gets the details step and then the
   existing "Apply to <course>?" confirmation.
4. **This works even when the site has signups closed.** `SiteSignupPolicy.allow_signups` does not
   switch the anonymous path off.

## Settled decisions

- **Never interrupt the applicant.** Once the details step is done, the visitor goes straight into
  the form. They are not asked to check their inbox, enter a code or log in, and everything they
  type and upload is stored as they go. The applicant must make progress without detours.
- **Staff see the application as soon as it is submitted.** Until the applicant verifies their
  email, every screen where staff review it shows a clear unverified flag.
- **After submitting, the applicant gets an email.** Following its link proves they own the address.
  It completes their account so they can set a password and come back to check on the application.
  A new email gets a new account. Registration forms (`ADDITIONAL_REGISTRATION_FORMS`) apply as
  usual once they are signed in.
- **An email that already has an account does not stop the applicant.** The details step responds
  identically whether the email is new or already registered, so it never reveals which addresses
  have accounts (the site runs with `ACCOUNT_PREVENT_ENUMERATION`). The application joins the
  existing account only after the email link is followed. Nothing typed on the details step
  overwrites the existing account's profile.

## Constraints the spec has to resolve

These come from the code as it stands (`research_current_apply_and_signup_flow.md`):

- `CourseApplication`, `FormProgress`, `LegalConsent` and `SignupAttribution` all require a user.
  Uploaded answer files are stored under the user's id. An anonymous visitor has no user, and an
  existing account can't be handed to them. The spec decides where an in-progress anonymous
  application lives until the email is verified. It does that in the simplest way that meets
  "never interrupt" and "attach on verify".
- `User.email` is globally unique although users are site-scoped. An email already registered on
  another site counts as "already has an account" and gets the same treatment.
- Today's signup side effects are wired to allauth's signup view: the `user.registered` webhook,
  the sign-up analytics event, `SignupAttribution`, `LegalConsent` and the signup rate limit. The
  spec decides which of these the anonymous path keeps and when each one fires. Firing for an
  unverified address must be a deliberate choice, not an accident.
- `UserManager.create_user` refuses to create a user without a password.
- After the details step, the application pages, check-your-answers, the status page and the
  post-submit dashboard redirect all require login today.
- Page numbering is positional across URLs, page links, resume and check-your-answers. The details
  step is not a `FormPage`.

## Security requirements

From `research_anonymous_apply_security.md`, which also covers the reasoning:

- An unverified email never grants access to an existing account or its data. The applicant's
  access during the application covers that application and nothing else.
- Turning an anonymous applicant into a signed-in user rotates the session. Following the email
  link invalidates anything an impostor could have left on the account.
- The details step is rate-limited per IP and per email address, and keeps the honeypot. One visitor
  can't use it to flood someone else's inbox.
- Uploads from unverified applicants stay within the form's existing limits and are private to the
  applicant and staff.
- Unverified applications and drafts nobody finishes do not live forever. The spec sets a retention
  period and makes sure such data can still be erased by email address.
- Consent captured on the details step keeps the document version, hash and IP that signup records
  today.
- Everything is site-scoped.

## Out of scope

- Changing the normal signup page, or making it passwordless.
- Changing how authenticated applicants apply.
- CAPTCHA. The honeypot and rate limits are the bot defence for now.

# IMPORTANT
There is currently a work tree in progress that attempts to do the same thing, but the process is overly complicated because it was initially implemented incorrectly. So we're starting from scratch, hoping to make a simpler implementation.
