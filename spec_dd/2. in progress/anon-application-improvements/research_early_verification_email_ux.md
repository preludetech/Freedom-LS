# Research: sending the verification / "continue your application" email early in a guest form

Scope: web research, done 2026-10-12. Complements `spec_dd/3. done/2026-10-12_18:37_ananomous-course-applications/research_guest_apply_ux_patterns.md` (not repeated). Items marked **[unsourced]** are general knowledge or reasoning, not verified at a URL. Source coverage was thin for Greenhouse, Workday, Lever, UCAS and Common App: searches returned no help-doc detail on their early or draft emails, so nothing is claimed about them.

## 1. Why services send early, and the downsides

Sourced:
- Save-and-return services email a resume link when the user saves: London Fire Brigade's job portal sends a resume link plus an access code on saving a part-completed form. Notts safeguarding form emails on every save and tells users to use the latest email (ref 5, 6).
- Form tools capture the email early so they can send abandonment reminders. One donation platform sequence runs about 1 hour, 1 day, 3 days and 7 days (refs 7, 8). A first reminder is gentle; later ones more urgent. The direct link back to the draft is the key element (ref 8). Formester (previous research) uses 24h, 3d and 7d.
- GOV.UK: a confirmed email shows only that the person could reach the address at that moment. It does not prove identity. Confirmation loops are for cases where email is the only channel or a wrong address would expose someone else's data (ref 1).

Reasoned **[unsourced]**: early send also catches typos while the applicant is still present, and gives a recoverable draft across devices.

Downsides:
- GOV.UK says the loop is disruptive: users must leave the service for their inbox and come back. Design to reduce confusion, don't assume everyone can reach their email, and take steps so mail isn't marked as spam (ref 1).
- Cross-device: in most magic-link systems the session is established on whichever device opens the link, so a user on a laptop who taps the link on a phone is signed in on the phone, not where they were working (ref 9). Okta and Auth0 refuse by default when the browser differs. SuperTokens requires a click-through action before consuming the token, which also stops email scanners using up the link (ref 9). Hanko argues for passcodes for better cross-device robustness (ref 9).
- **[unsourced]** Mid-form click risk: a user who clicks while the original tab is still open can end up with two sessions and a stale form; a user who stops to check the inbox may not return; every extra email adds spam-folder and sender-reputation risk.

## 2. What the early email should say and do

- GOV.UK One Login "save progress" email: tells the user progress is saved and how to resume. Its link goes to **sign-in**, not straight into the form. Returning users choose "Resume a saved report", sign in, then continue (ref 2). So GOV.UK's model is link then authenticate then draft, with no passwordless drop-in.
- GOV.UK confirm-an-email pattern: link is the usual method; a typed code is the alternative. Expire the link on first use, when a newer link replaces it, on expiry date, or when the email address changes. An expired or used link must say so and explain why (ref 1).
- Wording: sources use "save progress / resume" framing for drafts and "activate / confirm" framing for accounts. Framing the email as "continue your application" matches the user's goal; "verify your email" reads as an obstacle **[unsourced]**.
- Set password now or later: no source requires a password at the early stage. Baymard and NN/g (previous research) support deferring account creation to the end, when only a password is needed. Magic-link guidance pairs link login with no password (ref 9).
- Mid-application click: no source describes it directly. The reasoned best practice **[unsourced]**: the link lands on the draft at its last completed step, with the email now verified, and the browser holding the original session is not broken. Cross-device clicks carry the same risk noted above, so server-side draft state keyed to the pending application is the safe design.

## 3. Telling the applicant on screen without interrupting

GOV.UK's non-blocking loop: let users keep using the service, remind them to activate, show where the email went, and offer resend and change-address (ref 1). For blocking loops the "activate" screen is the only page shown. One Login shows a success panel after saving (ref 2). So a persistent, low-key banner on subsequent pages, with the address shown, a resend action and a change-address action, matches the sourced non-blocking pattern. Example copy: "We've emailed a link to x@y so you can come back to this. Carry on here." **[unsourced]** wording.

## 4. At submit and beyond

- Blocking vs non-blocking (ref 1): non-blocking means not everyone will confirm, so features may be limited until they do. GOV.UK permits starting non-blocking and switching to blocking later, which suits "let them submit; require verification for the account/attachment step".
- Unverified applicant: reminders (ref 1). Define status and expiry for unverified submissions (previous research).
- Second "received" email: not covered by any source found. Previous research suggests a confirmation email with reference and route back. If an early email already exists, a received email is still useful as a receipt; it should not contain a second verification demand unless the user is still unverified **[unsourced]**.
- Resend: GOV.UK says let users resend (mistyped address or non-arrival) (ref 1). Each new link invalidates the old one (ref 1), but the previous research records the complaint that old links then land on a blank form, so an invalidated link should explain itself and offer a fresh one.
- Changing a mistyped email: GOV.UK says offer resend to a different address, and in a non-blocking loop let the user change the address and confirm the new one (ref 1). It also says users should always be able to change their email (ref 3). Changing the address should invalidate old links (ref 1).

## 5. GOV.UK summary

- No pure "magic link" pattern: save-and-return goes through One Login sign-in; email confirmation pattern is link or code (refs 1, 2, 4).
- Don't create accounts unless needed (previous research). Confirm email only when the channel is critical or a wrong address would leak data (ref 1).
- Expire links, say why when expired, and show the target address on screen (ref 1).

## 6. Complaints and pitfalls

Sourced:
- Multiple saves produce multiple emails and users must be told to use the latest (ref 6).
- Cross-device and different-browser links fail with errors in Okta and Auth0 by default (ref 9).
- Email scanners can consume single-use links (ref 9).
- Previous research: hard to retrieve resume links, stale old links landing on a blank form, unreliable resume.
- Reminders suit people who went quiet, not those who only just started (ref 8).

**[unsourced]**: spam-folder delivery, typo'd addresses silently losing applicants, double emails (early link plus claim at submit) causing confusion about which to use, users stopping to verify and never returning.

## Recommendations for this idea

1. Frame the early email as "continue your application" (link back to the draft), with verification as a side effect of clicking, not the headline.
2. Send it immediately after page 1 and show the address on the next page in a non-blocking banner with resend and change-address controls (ref 1 non-blocking pattern). Do not stop the flow.
3. Keep draft state server-side so a click from another device or after the session ends still resumes the draft. Make the link single-use per newest-wins, with a clear "expired / replaced" page offering a fresh link (ref 1).
4. Use a click-through confirmation step before consuming the token to avoid scanner consumption and accidental sign-in on the wrong device (ref 9). Decide whether the link signs the user in. GOV.UK sends to sign-in; this app's passwordless first page suggests the link verifies and signs in, with the password set later (on submit or after). This is a spec decision.
5. Changing the email address must invalidate prior links and re-send to the new address (ref 1).
6. Consolidate emails at submit: if already verified, send only an "application received" receipt; if not, include a resend link in the receipt rather than a second competing claim email.
7. Enforce the existing-account rule from previous research: attach only after proof via the link; use the same on-screen message either way.
8. Consider a reminder only for drafts that go quiet (for example 1 day, then 3 days), capped and with an unsubscribe route. This is optional and not requested.

## References

1. GOV.UK Design System, Confirm an email address: https://design-system.service.gov.uk/patterns/confirm-an-email-address/
2. GOV.UK One Login, Let users create a GOV.UK One Login to save progress: https://sign-in.service.gov.uk/documentation/design-recommendations/save-progress
3. GOV.UK Design System, Create a username: https://design-system.service.gov.uk/patterns/create-a-username/
4. GOV.UK Design System, Create accounts: https://design-system.service.gov.uk/patterns/create-accounts/
5. London Fire Brigade, how to apply: https://jobs.london-fire.gov.uk/how-to-apply/
6. Nottinghamshire safeguarding form: https://nottinghamshire.gov.uk/care/safeguarding/adult-safeguarding-hub/saved
7. Fundraiseup, abandoned donation reminder FAQ: https://fundraiseup.com/support/abandon-donation-email-faq/
8. Fillout, form abandonment: https://support.fillout.com/help/form-abandonment ; Wishlist abandonment reminders: https://wishlist-docs.webcontrive.com/abandonment-reminder-email-bring-customers-back-to-their-wishlist
9. Magic link cross-device and scanners: https://uxdesign.cc/user-friendly-magic-links-e39023ec3e2 ; https://developer.okta.com/docs/guides/email-magic-links-overview/main/ ; https://support.auth0.com/center/s/article/Open-Email-Passwordless-Magic-Link-from-any-Browser ; https://www.hanko.io/blog/magic-links-vs-email-passcodes ; https://appmaster.io/blog/passwordless-magic-links-ux-security-checklist

status: ok
