# Allow anonymous course applications

## Problem

A new visitor who clicks "Apply now" on an application-gated course is sent to signup before they have
seen a single question. Some of them never come back. We want the application form to be the first
thing they see, with the account created only at the end.

## What we are doing

An anonymous visitor can start and submit a `CourseApplication` without an account. The visitor
types an email address when they submit. The application is then **unclaimed**: it has an email but
no `user`. Straight after submitting, the site sends the visitor to authenticate. On their first
verified login in that browser the application is **claimed**: its `user` is set and it appears on
their dashboard like any other application.

"Unclaimed" and "claim" are new words. An unclaimed application is a `CourseApplication` whose
`user` is null; claiming is the single step that sets `user` on it and on its sitting
(`FormProgress`). Nothing else in the system has those names.

### The anonymous journey

1. "Apply now" on the course page goes straight into the application form, or to the confirmation
   page for a course that names no form. No signup or login interstitial.
2. The visitor fills in the pages as today, uploads included. The draft lives in the database and is
   tied to the visitor's browser session. Closing the browser or letting the session expire loses
   the draft; the interface says so rather than implying it can be resumed later.
3. On the check-your-answers page (or the confirmation page for a no-form course) the visitor types
   their email address and submits. Submission is the same whole-form check as today, so every
   required answer is already in place before the email is asked for.
4. The application is now submitted and unclaimed. The analytics submission event fires here, as
   it does today.
5. The site sends the visitor to the signup page with the email prefilled and `next` pointing at a
   claim landing page. The signup page already carries a "Log in" switch for people who have an account.
   The site never tells the visitor whether the typed email has an account.
6. The first login in that browser with a verified email equal to the typed one claims the
   application, and the visitor lands on its status page.

### The signed-in journey

Unchanged, with one addition: the check-your-answers page and the confirmation page show the account
email read-only ("Your decision will be sent to name@example.com"). A signed-in applicant's
application is created under their account from the start, so there is no claim step.

## Settled decisions

**Submission precedes authentication.** The application reaches reviewers the moment the anonymous
visitor submits it, keyed on an email address nobody has verified yet. Reviewers and the admin see
it under that email, marked as unclaimed, and know the address is unverified until it is claimed.

**Data model.** `CourseApplication.user` and `FormProgress.user` become nullable and
`CourseApplication` gains an `email` field, filled from the account for signed-in applicants and
from the typed address otherwise. The `(site, user, course)` unique constraint stays as it is;
Postgres treats nulls as distinct, so unclaimed rows are exempt and owned rows stay unique. There
is no uniqueness on `(site, email, course)`: the email is unverified, and a stranger typing someone
else's address must never block that person's own application. The future review state machine
noted in the model docstring is untouched; an unclaimed application is a draft-state row with no
owner, and `research_anonymous_application_data_model.md` sets out how its partial index and
`submit` transition stay compatible.

**The browser session is the credential for an unclaimed application.** Every page of an unclaimed
application, and every upload and download on it, requires the application's id to be in the
visitor's session. The URL alone grants nothing, matching the existing rule that ownership, never
unguessability, is the control. A wrong, foreign or expired id answers 404, identical to a missing
one. An anonymous GET never creates rows; only a POST does.

**The claim rule.** An application is claimed only when all three hold: the claimant is logged in on
this site; the application's id is in the claimant's session; and the claimant has a verified
`EmailAddress` equal to the application's `email`. A mismatch leaves the application unclaimed and
tells the applicant that this account's email differs from the one on the application. Claiming is
one atomic, single-use, idempotent transition. Claim never happens by email match alone: a draft
planted against a victim's address must not attach to the victim when they sign up.

**Claim runs from two places with one function.** A `user_logged_in` receiver, so a late
verification link or a login through the switch button still claims; and the claim landing page
that `next` points at, which only reports the result and redirects. The claim does not run from
signup, `pre_login` or `save_user`, because ownership of the email is unproven there.

**Claim collision.** If the claimant already has an application for the course, the existing one
wins and the applicant is sent to it. The unclaimed duplicate stays where it is for manual cleanup.

**No email is sent from the anonymous step.** The only mail is allauth's own signup and verification
mail, which is already rate-limited and enumeration-safe. There is no resume link and no reminder.

**Abuse controls replace the cost of an account.** Creating unclaimed applications and uploading to
them get a per-IP cap, following the hashed-IP cache counter in `referral_tracking/hits.py`, with
its own setting so tests can prove it fires. The email field reuses the signup honeypot pattern.
Every unclaimed-application page sends `Cache-Control: no-store` and a same-origin referrer policy.

**Hidden and coming-soon courses.** The anonymous entry point runs the hidden-course check first, so
a hidden slug 404s like a missing one, and a coming-soon course redirects to its express-interest
control. The claim repeats the check, so a course hidden after the draft began is not claimed.

**Unclaimed applications are cleaned up by hand.** There is no expiry job. The admin lists unclaimed
applications under their email, and an administrator can delete one together with its sitting and
files. Deleting an unclaimed application is the only exception to the admin's no-delete rule for
applications, because no account erasure will ever remove it.

**Closed-signup sites keep today's behaviour.** Where the site is closed for signups, "Apply now"
sends an anonymous visitor to login with `next` set, as now. A visitor with no account cannot claim,
so there is no point letting them fill in the form.

**Storage keys for uploads can no longer be built from the user id.** Anonymous sittings have none,
and files do not move at claim. `research_anonymous_application_data_model.md` compares the
options; the consequence for the erasure procedure is that it must find files through the rows, not
by prefix.

## Collisions to manage

- `spec_dd/1. next/educator-interface-full-polish/application-review-ui/` adds the `state` field,
  a `submit` transition that needs an actor, and the partial unique index that replaces the current
  constraint. Unclaimed applications need a submit with no actor and a `user IS NOT NULL` condition
  on that index. Whichever lands second reads the other.
- `spec_dd/1. next/referral-attribution-over-time/` hooks application creation as a conversion event
  with a user. For an unclaimed application that user arrives at claim time.
- `spec_dd/1. next/failed-login-follow-up/` captures emails of visitors who got stuck at login after
  clicking Apply. This idea removes most of that case.
- `spec_dd/1. next/test-organisation-and-hygene-7-course-access-and-applications/` moves the tests
  this work edits.

## Privacy note for the operator

An unclaimed application holds an email address, free-text answers and possibly an identity
document for a person who has no account and has accepted no terms. The email field carries a short
plain statement of what the address is used for, linking the site's privacy document; no
`LegalConsent` row is written for an anonymous visitor. The product documentation for security and
data handling gains this data class, with the same "starting point, not a finished assessment"
framing as signup attribution. See `research_abuse_and_security.md`, threat T7.

## Not in scope

- Resuming a draft from another browser or device, or any emailed resume or claim link.
- Login by code. allauth 65.15 has no signup-by-code path, so it cannot serve a new applicant.
- A "Continue your application" label on the course page for a visitor with a draft in progress;
  the apply link resumes the session's draft under the existing "Apply now" label.
- Any webhook or notification for an unclaimed application.
- A CAPTCHA, unless abuse is observed.

## Research

- `research_anonymous_application_data_model.md`: nullable owners, the unique constraint, the claim
  transaction, upload keys.
- `research_auth_handoff_and_claim.md`: how `next` survives signup and verification today, its
  same-browser and fifteen-minute limits, the allauth hooks, and why signup-with-prefill beats an
  account lookup or a magic link.
- `research_anonymous_apply_ux.md`: where to ask for the email, the handoff sequence, copy in the
  brand voice, and the failure modes to design for.
- `research_abuse_and_security.md`: nine threats with the existing and recommended mitigations.
- `research_existing_flow_touchpoints.md`: every `path:line` that assumes an authenticated
  applicant, the tests that pin the old behaviour, and the product docs that change.
