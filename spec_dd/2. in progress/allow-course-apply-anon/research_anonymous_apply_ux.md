# Research: UX of "apply first, create an account at the end"

Topic: patterns and pitfalls for letting an anonymous visitor apply for a course and authenticate at the end, mapped onto the existing multi-page application form. Builds on `spec_dd/3. done/2026-06-23_13:04_applying-for-courses/research_multistep_ux.md` (wizard, check-your-answers, persisted draft); that material is not repeated.

## 0. Today's flow, in one paragraph

An anonymous visitor who clicks "Apply now" is sent to signup first (`acquisition_login_required`; docs/product/learner-experience.md, "Deferred-login Intent Completion"). Only after authenticating does `apply` create the `CourseApplication` and, if the course names an application form, a draft sitting (`FormProgress`) and land on page 1. Every later view (`application_form_page`, `application_check_answers`, `application_status`) is `@login_required` and looks the application up by `pk` plus `user=request.user`. Submission is one-way from the check-your-answers page (`form_progress.complete()`), then a toast and the dashboard. A form-less course shows `apply.html` ("Submit application") instead. The idea inverts this: the authentication wall moves from before page 1 to after the check-your-answers page, and the application is "claimed" by the account afterwards.

## 1. Reference patterns: what do they do with the email?

| System | Account needed to start? | Email | Source |
|---|---|---|---|
| Baymard-studied e-commerce checkouts | No (guest checkout) | Asked inside the checkout; account offered as optional | Baymard |
| GOV.UK "Create accounts" pattern | Only if users must return to the data | "Let users get as far through the service as they can before asking them to create an account"; keep the sign-up screen focused; do not make them re-enter information | design-system.service.gov.uk |
| GOV.UK One Login "save progress" (optional account) | No | Account created when the user chooses "Save and complete later"; link sits under the primary button on every page | sign-in.service.gov.uk |
| GOV.UK "Confirm an email address" | n/a | Confirm only when critical functionality depends on the email or a wrong address would expose sensitive information; link or security code | design-system.service.gov.uk |
| Email-first form tools (abandoned-form recovery plugins, e.g. RescueFill) | No | Captured on step 1 so the visitor can be emailed back; consent handling is a paid-tier concern | wordpress.org listing |
| Greenhouse / Lever / Workable job boards, Common App, UCAS | Not verified | I could not confirm from public sources whether these take email first, last, or require an account. Common App and UCAS are account-first by my recollection; treat that as unverified. Do not cite these as evidence for either side. | search returned only scrapers/aggregators |

What the evidence supports:

- **Forced account creation costs completions.** Baymard's survey of 1,026 US adults found 18% had abandoned an order rather than create an account (an earlier version of the article, and Baymard's cart-abandonment guide, say 19%). It is self-reported, not measured drop-off, so cite it as "about 1 in 5 say they have abandoned". Baymard also found 62% of sites do not make guest checkout the most prominent option, and that an option users miss is as bad as none. For FLS: the "Apply now" click must go straight into the form; a signup-or-login interstitial that offers "continue without an account" as a small link is the failure Baymard describes.
- **GOV.UK's stance is "go as far as you can before asking for an account"**, and "don't make users enter the same information more than once". That is the idea in the brief. It also says the create-account step should be distraction-free, and that the difference between creating an account and signing in must be unmistakable (side-by-side buttons are not enough).
- **Email is treated as the identifier, not a gate.** GOV.UK's confirm pattern says a confirmed email proves access to that inbox at that time, not identity. For a course application that is the right strength: the reviewer needs a reachable applicant, not a verified person.

## 2. Where in the form: first page or last?

There is no independent head-to-head benchmark. The searches found analytics tooling (Zuko) that diagnoses drop-off per field and vendor marketing for email-first recovery (RescueFill's "68% never finish" figure is vendor copy, not research). So the honest answer is a trade-off, not a finding.

- **First page.** Pros: a draft can be linked to an address from the start, so an emailed "resume your application" link and abandonment recovery are possible; the application can be keyed on the email. Cons: it is a field before any value is shown, capturing an address before submission raises consent questions (the recovery tools sell consent modes for this reason), and it invites "email me a link" flows that have to be built, secured and rate-limited.
- **Last (on or just before check-your-answers).** Pros: zero extra friction up front, which matches the brief ("disrupted by the authentication flow"), and matches GOV.UK's "as far as you can". Cons: a visitor who closes the tab before the end loses the draft unless the draft is held by something other than an account (a browser cookie/session), and there is nothing to recover them with.
- **Hybrid used by GOV.UK One Login.** No email up front; a persistent "Save and complete later" link under the Continue button on every page. Clicking it is the moment the visitor volunteers an email. This gets recovery without a mandatory first-page field.

Recommendation for this project: ask for the email on the **check-your-answers page**, not page 1, and offer an optional "Save and finish later" on each form page (see section 5, lost drafts). Page 1 stays a real question, and the applicant reaches value (their own answers listed back) before being asked who they are. The existing research already established that drafts must survive logout and device switch; for an anonymous applicant that guarantee does not exist until an account or a resume link does, so say so in the interface rather than imply it.

Pitfall: the whole-form check on check-your-answers (`unanswered_required_in_form`) already runs there, so an email-and-verify step placed after it means the applicant has already fixed all errors before being asked to authenticate. Do not put the email field on a page that can 422 for a different reason, or the applicant cannot tell which error belongs to which step.

## 3. The end-of-flow handoff

The applicant has typed everything and now must prove the address. Observed patterns:

1. **Code in the same tab** ("we've sent a six-digit code to x@y"). Works across devices because the browser that started the flow receives the code. Costs a typing step and needs a short expiry. GOV.UK lists the security-code option in "Confirm an email address".
2. **Link in the email.** Smoothest on one device. Breaks when opened elsewhere: Auth0's passwordless links are device-bound and show "The link must be opened on the same device and browser from which you submitted your email address"; links opened in an in-app webview land in a different cookie jar and the original tab never signs in. Where links are not device-bound, the phone signs in while the laptop tab keeps showing the form, which generates support tickets (AppMaster).
3. **Hybrid: link and code together.** Click on the same device, type the code otherwise. This is the pattern that covers the failure modes in section 5 best.
4. **Inline password creation on the final page vs redirect to signup.** GOV.UK warns that a failed sign-up can block the service and says to keep the account screen free of distractions and not to re-ask for known information. A redirect to a generic signup page loses the "your application is waiting" context and re-asks for the email. Inline (email already filled, password asked on the same card, or no password at all if FLS login supports email-code sign-in) keeps context. The tradeoff: this project's signup may have extra registration forms (the existing doc says intent is preserved "even through the new-user signup path that requires completing additional registration forms"), so a sign-up that needs more pages must carry the unclaimed application through them.

Sequencing that reads well: check-your-answers page -> "Where should we send the decision?" (email, prefilled if signed in) -> "Check your email" (shows the address, resend, change address) -> verified -> claim -> status page.

### "This email already has an account" without leaking existence

OWASP's Authentication Cheat Sheet says registration should answer identically whether or not the user exists. Its correct example is "A link to activate your account has been emailed to the address provided." (incorrect: "This user ID is already in use."). It also says to keep HTTP status and response time consistent, and it concedes generic messages confuse some legitimate users.

Mapped to an application: the page after submitting an email always says "We've sent a code to x@y. Enter it to send your application." The email then differs by case: a new address gets "confirm and create your account"; an existing account gets "someone, probably you, applied for <course>; sign in to attach it". The applicant never learns from the web page whether an account exists. Two consequences to design for, not hide:

- The brand voice sample "This email is already registered. Try signing in" (voice.md) is the leaking form. For this flow it is a trade-off the spec must decide, with the anonymous-apply spec choosing the non-leaking form because the email is typed by an unauthenticated person, not by the account's owner.
- Because the verified email proves inbox access, the claim step can safely attach the application to the existing account after the owner signs in or enters the code. Without verification, never attach an anonymous application to an existing account: anyone could push applications onto someone else's account, or read a draft by guessing an email.

## 4. After submitting, before verifying

GOV.UK's confirm pattern says the waiting page must: show the address the message went to, explain that the applicant needs to act to continue, and offer "resend" and "use a different address". It also says expire the link on first use, when superseded by a resend, or when the address changes, and that an expired link must explain that it expired and why. It describes blocking vs non-blocking: blocking is simple but a missed email locks the user out; non-blocking lets them continue with reminders.

For FLS, the key product decision this research surfaces is the meaning of "submitted". GOV.UK's confirmation-page guidance is explicit that a confirmation page tells users a transaction is complete, with "what happens next", and that users bookmark it as a receipt. Applied here:

- Before verification the application is **not yet sent to reviewers**. Do not show the "received and pending review" copy that `application_status.html` shows today; that text would be false. Show a distinct unverified state: "Your application is saved. Confirm x@y to send it."
- If they never verify: say how long the draft is kept and what happens (it is discarded, the reviewer never sees it). GOV.UK does not give a retention figure; that is a spec decision. The confirmation-pages guidance says a bookmarked page should still respond helpfully (link to start again, contact someone), which fits an expired unclaimed application.
- Resend: always available, rate-limited, and the old code/link stops working when the new one is sent.
- The unverified status page cannot be `@login_required`, since there is no login yet; whatever identifies the application (an unguessable token held in the session and in the email) must not be the guessable `pk` alone.

## 5. Common failure modes

| Failure | What the sources say | Mapping to FLS |
|---|---|---|
| Lost draft when the browser closes | GOV.UK One Login's optional-account route exists because anonymous progress is lost on sign-out; it adds a "Save and complete later" link on every page and warns users with unsaved progress before sign-out. Draft survival is a core finding of the earlier multistep research too (>67% abandon on any complication). | An anonymous sitting survives only as long as its session cookie. Offer "Save and finish later" (emails a resume link or code) on each form page, and tell the applicant plainly that closing the browser without it loses their answers. |
| Duplicate applications | Not covered by the sources; it is a recurring pattern in any apply-before-account flow. | An existing signed-in applicant today gets redirected to their status page ("applying is idempotent"). An anonymous applicant who verifies an email that already has an application for that course should be sent to that application, not get a second one; say "You've already applied to this course" with a link, after authenticating, to avoid leaking existence. |
| Verification email in spam | Not studied directly; GOV.UK's blocking-loop note says "emails must be sent instantly, since a missed email locks the user out", and Baytech notes magic-link conversion depends on deliverability. | Tell the applicant the sender address, say "check spam", and always offer resend and change address. Do not let the only route to finish be the email link: use the hybrid (link plus code). |
| "Application submitted" confused with "account created" | GOV.UK separates the confirmation page (transaction done) from account creation; the create-accounts pattern keeps the sign-up screen focused on one task. | Name the two things separately in copy: the application is the thing being sent; the account is how they will come back to it. Never put "Account created" as the headline of the final screen. |
| Link opened on a different device | See section 3: Auth0 rejects it; others silently sign in the wrong device while the original tab sits unchanged. | Preferred fix: the code is entered in the tab that holds the draft. If a link is also sent, opening it on another device must say "Return to the device where you started, or enter this code there", not an opaque error, and should not partly claim the application. |

## 6. Signed-in applicants

Not covered by any source as a distinct pattern; GOV.UK's guidance on not re-asking known information (create-accounts) is the closest. Options:

- **Skip.** The application is already owned by the signed-in user; no email step. Simplest, but the applicant cannot see which address will receive the decision.
- **Read-only display.** Show "Decisions will be sent to x@y" on the check-your-answers page with a link to account settings. Equivalent in effect to skip, with the reassurance.
- **Editable, prefilled.** Matches the brief's wording ("autofilled") but is the riskiest: a different address on an application owned by a signed-in account creates two identities for one applicant, and the verified-email claim logic must then decide which wins.

Recommendation: prefill and show the email read-only for signed-in applicants, with the change route being the existing account settings, not the application. The brief's "autofilled" is satisfied (the value is shown), and the application does not get an address that disagrees with the account. If the product wants an editable contact address, that is a separate concept from the login email and the spec should name it separately. Also: a signed-in applicant needs no verification step, so the check-your-answers submit must remain a single click for them, as it is now.

## 7. Copy suggestions, in this project's voice

Voice rules applied (voice.md): direct, name the problem and the fix, no SaaS phrasing, routine actions end on a full stop. "Sign up" is avoided; GOV.UK recommends "Create an account" over "Register"/"Sign up", which is a consistent choice for a pattern-matching reader, though the project's current signup wording should win.

- **Email step (check-your-answers page).** "Where should we send your decision? We'll email you a code to confirm it's yours." Signed in: "Your decision will be sent to {email}."
- **Verify to finish.** "We've sent a code to {email}. Enter it to send your application for {course}." Below: "Not there? Check spam, resend, or use a different address."
- **Status page while unverified.** "Your application for {course} is saved but not sent yet. Confirm {email} and a reviewer will see it." (Not "received and pending review".)
- **Claim success.** "Email confirmed. Your application for {course} is with a reviewer, and it's on your dashboard under your new account."
- **Existing account (non-leaking form).** "We've sent a code to {email}. Enter it to send your application." (Same line as new addresses; the email itself carries the difference.)
- **Expired code.** "That code has expired. Request a new one and use the latest email."

## Sources

- Baymard, current state of checkout UX (18%, 1,026 US adults, 62% guest checkout prominence): https://baymard.com/blog/current-state-of-checkout-ux
- Baymard, cart abandonment (19% figure): https://baymard.com/blog/reduce-cart-abandonment
- Amazon Pay summary of Baymard on forced sign-ups: https://pay.amazon.com/blog/the-baymard-report-series-how-forcing-sign-ups-drives-down-sales
- GOV.UK Design System, Create accounts: https://design-system.service.gov.uk/patterns/create-accounts
- GOV.UK Design System, Confirm an email address: https://design-system.service.gov.uk/patterns/confirm-an-email-address
- GOV.UK Design System, Confirmation pages: https://design-system.service.gov.uk/patterns/confirmation-pages
- GOV.UK One Login, let users create an account to save progress: https://sign-in.service.gov.uk/documentation/design-recommendations/save-progress
- OWASP Authentication Cheat Sheet (account enumeration, registration messages): https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Auth0 community, link must be opened on same device: https://community.auth0.com/t/passwordless-magic-link-error-the-link-must-be-opened-on-the-same-device/109529
- Auth0 support, same-device error: https://support.auth0.com/center/s/article/passwordless-magic-link-error-The-link-must-be-opened-on-the-same-device-and-browser-from-which-you-submitted-your-email-address
- AppMaster, magic-link UX and security checklist: https://appmaster.io/blog/passwordless-magic-links-ux-security-checklist
- Baytech, magic links UX and growth (deliverability dependence): https://baytechconsulting.com/blog/magic-links-ux-security-and-growth-impacts-for-saas-platforms-2025
- RescueFill (email-first abandoned-form recovery, vendor claims): https://wordpress.org/plugins/?p=290003
- Zuko product overview (diagnostic form analytics): https://www.zuko.io/product-overview

Gaps: job-board behaviour (Greenhouse, Lever, Workable), Common App and UCAS account policy, and any independent email-first vs email-last benchmark could not be verified from public sources and are flagged rather than asserted. Typeform/Tally email-first behaviour was not searched.

status: ok
