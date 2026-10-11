# Research: UX patterns for applying without an account first

Scope: web research only. Items marked **[unsourced]** are from general knowledge and were not verified against a URL in this run. Confidence is flagged where sources conflict or were thin.

## 1. Evidence for the problem

- Baymard: forcing account creation is a measurable abandonment cause. Baymard's cart-abandonment guide lists ~19% of users abandoning when forced to create an account. A Baymard survey of 1,026 US adults reports 18%. Secondary sites quote 26% (a "2025 study") and "10-30% conversion uplift"; those could not be confirmed against Baymard and should not be cited. Use "roughly 1 in 5" at most. This is e-commerce data, not applications, so it is directional evidence. (refs 1, 2)
- Baymard: guest checkout must be the most prominent option; a missed guest option is "as bad as not offered" (62% of sites fail this). Better strategy: move account creation to the confirmation step, where only a password is needed because details are already entered. 84% of sites don't offer that. Tell users at the choice step that they can create an account at the end. (refs 2, 3)
- NN/g, "Login walls": users are rarely more annoyed than at a login wall; it forces a recall-or-register cost before users can judge value. Recommends letting users proceed until they commit, offering guest checkout, and deferring registration until after the transaction, then offering to save details (reciprocity). Infrequent users and mobile users forgetting passwords are the key victims. Guest access must be as visible as sign-in/sign-up. (ref 4)
- GOV.UK Design System, "Create accounts": do not create accounts if the service works without them; accounts are a barrier that raises drop-out. Alternative for one-off transactions: a unique reference number, sent by email or text, usable with name or email to check status. (ref 5)

## 2. How comparable products handle it

- **GOV.UK**: question pages, then one "Check answers" page immediately before the confirmation page; "Change" links return to check-answers; the submit button names the action. Transaction is not complete until confirmed. (ref 6) For save-and-return, GOV.UK One Login's pattern is "Save and complete later" under the primary button on every form page. It leads into the sign-in journey (create or sign in), then a confirmation email, and the resume link goes to sign-in (not straight to the form). Progress is lost if the user doesn't save. So GOV.UK's answer is identity on demand, at the moment the user wants to leave, not up front. Guidance doesn't cover retention or expiry. (ref 7)
- **Greenhouse (ATS)**: applications are submitted without a candidate account; a candidate portal (MyGreenhouse) exists only if the employer enables it, and shows coarse status (Active/Inactive). Greenhouse says it won't share status itself; employers must. Status is mostly communicated by email from the recruiter. (ref 8; third-party, medium confidence.) Lever and Workable: no sourced detail found. **[unsourced]** general knowledge: major ATS job forms are account-less, email-keyed, and send a confirmation email; the "account" is a recruiter-side candidate profile, not a login.
- **Moodle**: guest access is view-only (no quizzes, forums, assignments), so it isn't an "apply" analogue; real participation requires an account/enrolment. (ref 9)
- **Teachable / Thinkific / Kajabi**: no sourced detail found. **[unsourced]** general knowledge: they collect name + email + password at enrolment/checkout, i.e. account creation is inline with enrolment, with email-first on some and a "set password" email or magic-link login on others. Verify before relying on this.
- **University / bootcamp portals**: no sourced detail found. **[unsourced]** the common pattern is "create an applicant account (email + password) first, then fill in the application" (the pattern this idea replaces), with save-and-return through that account.
- **Form tools (Cognito, Formester, Jotform, MachForm)**: save-and-resume via emailed link, no password. Formester captures email early and sends a reminder with a prefilled resume URL after 24h/3d/7d if unsubmitted. (refs 10, 11)

When accounts get created after the fact (consolidated pattern from refs 2, 4, 7): at the confirmation step ("set a password to track your application"), or via emailed link/magic link, or never (reference number + email).

## 3. Placement of the identity step: first vs last

| | Email/identity first | Identity last (before check answers or at confirmation) |
|---|---|---|
| Friction up front | Slightly higher (a page of fields before any real question) | Lowest; users invest first (sunk cost) |
| Save and resume / recovery | Strong: you hold an email from page 1, so abandoned drafts can get a resume link or reminder (Formester model) | Weak: abandoned drafts are anonymous and unrecoverable unless held in a session/cookie |
| Duplicate/existing-account detection | Early, so you can route before data is entered | Late; detection after the user has done all the work, risking derailment at the end |
| Fit with GOV.UK | GOV.UK normally asks contact details as ordinary question pages in the flow; accounts only when the user opts to save | Baymard/NN/g: defer *account* to confirmation; but they still collect contact details during checkout |

Key distinction: the research defends deferring the *account/password*, not deferring *contact details*. An application needs email and name anyway. Putting email first is compatible with the evidence provided it is presented as a normal question page with no password. Trade-off: first-page identity enables recovery of abandoners but adds one page before value; last-page identity maximises completion but loses all drop-off recovery and makes the email-collision case painful.

A hybrid noted in the sources: capture email first (minimal), collect the rest of the signup details at the end or on a "your details" question page, so the first screen is low-effort.

## 4. Email already belongs to an account

Options seen:
1. **Generic response (OWASP)**: never confirm or deny the email exists. Registration with existing email should return the same message as new: e.g. "A link to activate your account has been emailed to the address provided." Also keep timing and status codes uniform. Cost: legitimate users may be confused; OWASP suggests a support route. (ref 12)
2. **Attach after verification (email-link proof)**: accept the application as a pending submission keyed to the entered email; send "Confirm your email" link. On click, bind the application to the existing account (if any) or create a new one. This avoids enumeration and avoids derailing the user, because the page is identical in both cases. The cost is that submission is only finalised after the click (or is "submitted, unverified").
3. **Inline "log in" prompt** ("You already have an account, sign in"): best UX for the individual, but it is account enumeration on a public form (OWASP says avoid). Acceptable only if the risk is judged low, or rate-limited/CAPTCHA'd (OWASP notes CAPTCHA/throttling as supporting controls; GOV.UK advises against CAPTCHAs on accessibility grounds, ref 5).
4. **Do not attach by unverified email** to an existing account: otherwise anyone could add applications to, or pollute, someone else's account. Any binding must follow proof of email control. (reasoned from refs 12, 7; **[unsourced]** as an explicit rule)

## 5. Post-submit experience

- Confirmation page: GOV.UK treats it as a distinct page after Check answers (ref 6; its own confirmation-page guidance was not retrievable here). **[unsourced]** typical good content: what happens next, timeline, reference number, "we've emailed a copy to <email>", and, if an account was created, a plain statement of that fact.
- Follow-up email: confirm receipt, include reference, and carry the route back (magic link or "set a password"). GOV.UK One Login's resume email links to sign-in, not the form (ref 7). Baymard recommends offering password creation on the confirmation step with 1-2 fields (ref 2).
- Returning later: options are reference number + email (GOV.UK, ref 5), magic link, or password set post-submit. Greenhouse shows status only if the employer enables a portal, and otherwise relies on email (ref 8).
- Complaints (documented): resume links hard to retrieve or resend (MachForm), each "save" generating a new link with old ones landing on a blank form (Mandeep), and resume reliability issues (Jotform) (ref 10). Others **[unsourced]**: "I didn't know an account was created", duplicate accounts from typing a different email, unverified emails never clicked, confirmation emails in spam, and typo'd emails that silently lose the applicant.

## 6. Pitfalls with guest flows

- Hidden or de-emphasised guest option is effectively absent (refs 2, 4).
- Returning users can't find sign-in if the guest path dominates; give both visible choices and say an account isn't required (ref 2).
- Resume links: must be stable, re-issuable, with clear expiry; test cross-device (ref 10).
- Email typos: no password means email is the only identity; confirm the email (verification link, or type-twice) or the applicant is lost. **[unsourced]**
- Silent account creation surprises users; say so plainly. **[unsourced]**
- Don't use the email as a stable identifier if users can change it (GOV.UK One Login migration note, via search summary; ref 7 area).
- Avoid asking the same information twice, and make "create account" vs "sign in" visually distinct (ref 5).
- Enumeration through different messages, timing or status codes (ref 12).

## Implications for this idea

Options (not a plan):

A. **Identity as first question page (the proposed idea), no password, then deferred account.** Consistent with the evidence (defer password, not contact details). Wins: lowest practical friction relative to signup-first, early email for recovery/reminders, early collision handling. Costs: one extra page before the first real question; needs a story for what happens if email matches an account and for unverified emails.
B. **Identity last (before Check answers).** Highest completion for those who start, but no recovery of abandoners and collisions are discovered late.
C. **Email-only first page, remaining details later.** Lowest first-step effort plus recovery; slightly more complex flow. Probably the best compromise if the "usual signup details" are many.
D. **Reference number + email, no account at all** (GOV.UK default). Simplest but does not give learners a login to the LMS afterwards.

Cross-cutting decisions:
- Account creation timing: at submit (silent, with explicit disclosure), post-submit "set a password" / magic link (Baymard/NN/g-endorsed), or on verification click.
- Existing email: generic "check your email" with attach-on-verification (option 2) is the enumeration-safe route; inline login prompt is better UX but leaks existence. Choose by risk appetite. Never attach to an existing account on unverified email.
- Verification: unverified applications need a defined status and expiry; decide whether submission counts before the email click.
- Return path: stable re-issuable magic/resume link; the confirmation page and email must say what was created and how to return.
- Authenticated users keep their flow; the anonymous variant should look like the other question pages (consistent with GOV.UK question-page pattern).
- Evidence caveat: the abandonment numbers are e-commerce checkout data (about 18-19%); applications are higher-commitment, so effect size is uncertain. ATS/bootcamp/Teachable specifics were thin; verify before citing.

## References

1. Baymard, Reduce Cart Abandonment: https://baymard.com/blog/reduce-cart-abandonment
2. Baymard, checkout flow / account creation at confirmation: https://baymard.com/blog/checkout-flow-average-form-fields
3. Baymard, current state of checkout UX: https://baymard.com/research-articles/current-state-of-checkout-ux
4. NN/g, Login walls: https://www.nngroup.com/articles/login-walls/
5. GOV.UK Design System, Create accounts: https://design-system.service.gov.uk/patterns/create-accounts/
6. GOV.UK Design System, Check answers: https://design-system.service.gov.uk/patterns/check-answers/
7. GOV.UK One Login, save progress: https://sign-in.service.gov.uk/documentation/design-recommendations/save-progress ; migrating users: https://sign-in.service.gov.uk/documentation/design-recommendations/migrating-users
8. Greenhouse support, candidate inquiries about application status: https://support.greenhouse.io/hc/en-us/articles/360037854231-Candidate-inquiries-about-application-status ; https://careery.pro/blog/greenhouse-application-status-meaning
9. Moodle guest access: https://docs.moodle.org/19/en/Guest_access
10. Cognito Forms save and resume: https://www.cognitoforms.com/support/594/how-to-guides/let-customers-save-progress-and-complete-forms-later ; Jotform: https://www.jotform.com/answers/795710-Save-and-Continue-Problems ; MachForm: https://www.machform.com/forums/topic/save-for-later-1 ; Mandeep: https://www.mandeeps.com/community/ideas/save-a-multi-step-form-could-be-improved
11. Formester, form abandonment recovery: https://formester.com/features/form-abandonment-recovery/
12. OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

status: ok
