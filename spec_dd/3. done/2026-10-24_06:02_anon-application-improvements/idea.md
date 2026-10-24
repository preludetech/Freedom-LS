# Anonymous application improvements

Changes to the anonymous course application flow built by
`spec_dd/3. done/2026-10-12_18:37_ananomous-course-applications/`. Its settled decisions stand
unless this idea changes them.

## Why

- The claim link goes out only after the whole application is submitted. An applicant who stops
  halfway, loses their session or switches device has no way back to their draft. They also
  don't find out about a mistyped email address until it is too late to fix.
- An anonymous applicant who leaves the application and returns to the dashboard sees nothing of
  it, so the draft their browser holds is as good as lost. Signed-in learners see their incomplete
  applications at the top of the dashboard. Anonymous applicants should too.

## What we are doing

### 1. Send the claim email after the applicant details step

- For a course with an application form, the claim email goes out as soon as the applicant
  details step is submitted, not at check-your-answers.
- For a course with no application form, nothing changes. The email is still sent on the
  "Apply to <course>?" confirmation, because no application exists before that one click.
- **Never interrupt the applicant still holds.** After the details step they carry straight on
  into the form. The page shows a notice naming the address and saying a link has been sent so
  they can come back to the application. They don't have to open their inbox.
- The email is framed as "continue your application". Proving the address is what following the
  link does, not what the email leads with. It shouldn't promise a review, because nothing has been
  submitted yet.
- **No second email at submit.** The early email is the only claim email unless the applicant
  asks for another (section 3, or an expired claim link's "send a new link").

### 2. A claim link works on a draft

Following the claim link before the application is submitted does what it does for a submitted
one. It verifies the address, completes or joins the account, signs the applicant in (setting a
password if they need one) and drops them back into their draft, on whatever device they opened it.
From then on they are an ordinary signed-in applicant.

This reverses today's rule that a claim link on an unsubmitted application is invalid. Accepted
consequences:

- An account, `LegalConsent` rows and the `user.registered` webhook can now exist for an applicant
  who never submits.
- To staff, "email verified" no longer means "submitted". Staff already see drafts, flagged
  unverified until claimed.
- The original browser's session stops resolving the draft once it is claimed elsewhere. The
  applicant continues signed in.

### 3. Recovering from a wrong email address

A mistyped address means the link never arrives and the applicant can't claim their application.
They need a way to fix it.

- While drafting, they go back to the details step (Previous from the first form page) and
  correct the address.
- After submitting, they land on the status page, the final page of the application. For an
  unverified applicant it says the email was sent and shows the address it went to. It offers to
  resend the link, and to change the address and send to the new one. Today the address is frozen
  once the application is submitted and the page only offers a resend. That changes.

Either way, a change of address invalidates every earlier link and sends a fresh one to the new
address. Without that, a link already sent to the old address would claim the application for the
new one, because the claim token holds only the applicant's id. Same address, or a name-only change:
nothing is sent.

### 4. Show the anonymous applicant's incomplete applications on the dashboard

- An anonymous visitor whose session holds draft applications sees the same "Your applications"
  panel signed-in learners get, at the top of the dashboard, one row per draft, newest first.
- Each row shows the course title, the "Incomplete" chip and "Continue application", which
  resumes the draft at the page they left. It shows no name, email address or answers, because
  the dashboard may be on a shared computer.
- Only drafts appear. Submitted applications don't, and neither does anything the session no longer
  owns (claimed, erased, or another session's).
- Once the applicant claims the application, they are signed in and the normal signed-in panel
  shows it.

### 5. The course page matches

When the session holds a draft for a course, that course's call to action is the one a signed-in
learner with an application gets: "View my application", leading to the status page (which
resumes a draft), instead of "Apply now".

## Constraints the spec has to resolve

From `research_current_anon_apply_flow.md`:

- The dashboard panel comes from `get_dashboard_contributions(user)`, which never sees the request,
  and `dashboard` builds panels only for authenticated visitors. The session has to reach the
  panel without `learner_interface` importing `course_applications`. The course-page CTA has the
  same gap: `ApplicationCourseAccessBackend.get_access(user, course)` sees no session either.
- `attach_to_user`'s tie-break, where a submitted application beats a draft, can now meet an
  incoming draft. A claim for a course the account has already applied to must not quietly lose
  answers the applicant expects to keep.
- How invalidation works when the address changes: bind the token to the address, or record
  which link is current. The existing rate limits (`application_details`, and
  `application_claim_email` at 3/h per address) cover both the details step and the status page's
  change-address form. Both must respond identically whether or not the address has an account.
- A change of address after submit alters an application staff may already be reviewing. Staff
  screens show the current address, and the "unverified" flag stays until the new address is
  claimed.
- The claim page and status page copy assume a submitted application. The draft case needs its
  own wording.
- An email that fails to send at the details step must not block the applicant. The notice says
  so, and the spec decides how they get another link while still in a draft (today a draft has no
  resend).

## Out of scope

- A "Not you? Discard" action on the dashboard.
- Reminder emails for drafts that go quiet.
- Automatic purging of unclaimed drafts, and changing the session lifetime (two weeks).
- Any change for signed-in applicants.

Research: `research_current_anon_apply_flow.md` (the code as it stands),
`research_early_verification_email_ux.md` (early-email and save-and-return patterns),
`research_resume_anonymous_draft_ux.md` (showing a guest's draft on return).
