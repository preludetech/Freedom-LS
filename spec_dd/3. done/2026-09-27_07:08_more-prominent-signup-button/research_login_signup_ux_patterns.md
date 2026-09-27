# Research: login-vs-signup confusion and where to send a first-time user

Context: a would-be learner clicked "apply"/"enrol", was sent to the login page, had no account, kept
resubmitting the login form, and gave up. FreedomLS uses django-allauth, email-based login, and
`ACCOUNT_PREVENT_ENUMERATION=True` (must not reveal whether an email has an account).

Every finding below ends with a one-line **FreedomLS takeaway**.

---

## 1. Best practice and evidence on login-vs-signup confusion

- **Baymard Institute** — sign-in/sign-up forms are visually near-identical (a couple of fields, some
  text, a button), so users routinely fill in the wrong one and only discover the mistake after
  submitting, causing wasted effort and abandonment. Baymard's fallback fix (when you can't show both
  clearly) is to use a cookie/history signal to detect a first-time visitor and default the highlighted
  action accordingly; sign-in is conventionally placed top-right where returning users expect it.
  [baymard.com/blog/simplifying-sign-in](https://baymard.com/blog/simplifying-sign-in)
  **Takeaway:** FreedomLS should not rely on identical-looking login/signup forms; a first-time
  visitor (no session, arriving via an "apply" link) should be defaulted toward signup, not login.

- **UX Movement** — reiterates that near-identical sign-up/log-in forms are a primary cause of users
  submitting the wrong form.
  [uxmovement.substack.com/p/how-to-stop-users-from-confusing](https://uxmovement.substack.com/p/how-to-stop-users-from-confusing)
  **Takeaway:** Make the login and signup screens visually distinguishable (heading, colour/illustration,
  copy), not just distinguishable by a small label.

- **GOV.UK Design System** ("Help users to create accounts") — explicitly warns that presenting
  sign-in and create-account "side by side is not enough because users might miss one of them or not
  understand the difference"; recommends the unambiguous label "Create an account" (never "Register"/
  "Sign up") and keeping the create-account screen free of distracting content/links so users are not
  pulled into the wrong flow.
  [design-system.service.gov.uk/patterns/create-accounts](https://design-system.service.gov.uk/patterns/create-accounts)
  **Takeaway:** Don't trust a side-by-side toggle alone to fix the "apply → login wall" problem; the
  page a first-time user lands on must actively route them, not just offer an equal-weight link.

- **learnui.design (Wes O'Haire, "15 tips for better signup/login UX")** — avoid label pairs that
  require users to "think for half a second" (his example: "Sign in" vs "Sign up" is too similar);
  use visually/semantically distinct terms (e.g. "Register" vs "Sign in"). Also: never make a user
  re-enter their email after switching screens or after a failed attempt.
  [learnui.design/blog/tips-signup-login-ux.html](https://www.learnui.design/blog/tips-signup-login-ux.html)
  **Takeaway:** Consider replacing FreedomLS's "Log in"/"Sign up" pair with more distinct wording, and
  guarantee the email typed on the login page survives a switch to signup.

- **Baymard on forced account creation in checkout** — ~24% of checkout abandonment is attributed to
  "site wanted me to create an account"; 62% of sites don't make the alternative path prominent enough;
  moving account creation later (or removing it as a hard gate) measurably improves conversion (ASOS:
  +50% after moving account creation post-purchase).
  [baymard.com/blog/checkout-flow-ux-optimization](https://baymard.com/blog/checkout-flow-ux-optimization),
  [corbado.com/blog/guest-checkout-vs-forced-login](https://www.corbado.com/blog/guest-checkout-vs-forced-login)
  **Takeaway (guest-checkout analogy, see §2):** the "apply for a course" intent is an acquisition
  moment — treat the auth wall the same way ecommerce treats a login wall at checkout: minimize it,
  or make the "I'm new" path at least as prominent as "I already have an account."

---

## 2. Patterns for handling the fork

| Pattern | Description | Source |
|---|---|---|
| **Default-to-signup for acquisition CTAs** | When the triggering action implies a new relationship ("apply", "enrol", "join", "get started"), route unauthenticated users to signup by default, with a small "already have an account? Log in" link — not the reverse. | General best practice, corroborated by GOV.UK's insistence on distinct create-account flows; Coursera/Udemy CTA conventions (§3). |
| **Combined/tabbed login+signup** | One screen, two tabs; switching tabs must **preserve** any email already typed and the `next`/intent parameter. GOV.UK explicitly says tabs/side-by-side alone don't solve the confusion — the tab labels and framing still need to be unambiguous. | [design-system.service.gov.uk/patterns/create-accounts](https://design-system.service.gov.uk/patterns/create-accounts) |
| **Identifier-first ("enter your email, we'll figure it out")** | User types only an email first; the backend decides the next step (password, SSO, "no account — want to create one?"). Okta's Identity Engine and Auth0 use this as the default for adaptive sign-in (also enables passkeys/passwordless later). | [developer.okta.com/docs/concepts/oie-idfirst-signin](https://developer.okta.com/docs/concepts/oie-idfirst-signin/), [community.auth0.com – identifier-first](https://community.auth0.com/t/setup-identifier-first-authentication-only-on-login-and-not-signup/122353) |
| **"Continue with email" unified flow** | Single form (email [+ optional name]) that transparently creates-or-logs-in; Stripe's own guidance says: if someone who signed up with password later chooses "Sign in with Google", sign them into the *existing* account rather than erroring — never create a dead end for changed sign-in method. | [stripe.com/guides/atlas – sign-up/sign-in](https://stripe.com/guides/atlas/optimize-your-customer-sign-up-and-sign-in-experience) |
| **Passwordless / magic link** | Removes the login-vs-signup distinction entirely: same "enter your email" action works whether the account exists or not (Notion uses this for every login, first-time or returning). Notion's onboarding completion rose 64%→87% after removing the password requirement; one B2B SaaS saw 70% of logins go passwordless once it was the default (with an escape hatch "use a password instead"). | [blog.logrocket.com/ux-design/how-to-use-magic-links](https://blog.logrocket.com/ux-design/how-to-use-magic-links/), [okta.com/blog/product-innovation/magic-links](https://www.okta.com/blog/product-innovation/magic-links/) |
| **2-page (email-then-password) login critique** | Splitting login into "email" then "password" pages breaks autofill/password managers and is slower for most returning users. Recommended alternative: single page, but conditionally reveal (e.g. show SSO options) once the email is typed, rather than a hard page break. | [smart-interface-design-patterns.com – 2-page login pattern](https://smart-interface-design-patterns.com/articles/2-page-login-pattern/) |
| **Guest-checkout analogy** | E-commerce's fix for "forced account creation kills conversion" is to let the user proceed first and create the account afterward/optionally. For FreedomLS, the analogous move is: let the "apply" intent survive past authentication (via `next`) and offer signup as the default completion of that intent, rather than treating login as a precondition with signup as an afterthought. | [corbado.com/blog/guest-checkout-vs-forced-login](https://www.corbado.com/blog/guest-checkout-vs-forced-login) |

**Takeaway:** Of these, the two most realistic near-term fixes for FreedomLS (allauth-based, not
rebuilding auth) are (a) **default acquisition CTAs to signup, not login**, and (b) **make the
login↔signup toggle preserve email + `next` intent** and be visually unambiguous. Identifier-first and
magic-link are bigger architecture changes worth a future spec, not this one.

---

## 3. How reference products handle it

- **Coursera** — separate `/login` and `/signup` pages, but the modal/page explicitly frames itself as
  "I'm a new Coursera user" vs "I'm an existing Coursera user", i.e. it never assumes; course/enroll
  CTAs ("Join for Free") route to signup by default for anonymous visitors.
  [coursera.org/signup](https://www.coursera.org/signup), [coursera.org/login](https://www.coursera.org/login)
- **edX** — enrolling requires registration (email, username, password) for first-time users; the
  "Enroll Now" action is what triggers the registration prompt, i.e. the enrol CTA — not a generic
  login page — is the entry point for new users.
  [classcentral.com/help/sign-up-edx](https://www.classcentral.com/help/sign-up-edx)
- **Khan Academy** — Sign-up flow branches by role (Learner/Teacher/Parent) up front and offers
  Google/Facebook/Apple/Microsoft/email; under-13 learners get a username+password path with no email.
  The point: the *first* screen after clicking "get started" is signup-oriented, not a bare login form.
  [support.khanacademy.org – account setup](https://support.khanacademy.org/hc/en-us/articles/202487450-How-do-I-set-up-a-new-user-account)
- **Stripe** (as a general-SaaS reference, not LMS) — single-form signup (email, name, password), and
  explicit guidance to never dead-end a user whose chosen sign-in method doesn't match their original
  signup method — always resolve to the existing account rather than an error.
  [stripe.com/guides/atlas](https://stripe.com/guides/atlas/optimize-your-customer-sign-up-and-sign-in-experience)
- **Notion / Slack-style magic-link products** — treat "enter your email" as the single entry point for
  both new and returning users; the system, not the user, decides create-vs-authenticate.
  [blog.logrocket.com/ux-design/how-to-use-magic-links](https://blog.logrocket.com/ux-design/how-to-use-magic-links/)
- General pattern across these products for **acquisition-intent CTAs** ("Join", "Enroll", "Get
  Started", "Apply"): they land the anonymous user on **signup**, not login. Login is reserved for
  CTAs that presuppose an existing relationship ("Log in", account-icon in the header).

**Takeaway:** FreedomLS's "apply to a course" is squarely an acquisition-intent CTA in this taxonomy —
by the pattern every reference product follows, it should route unauthenticated users to **signup
first** (with an obvious "already have an account? Log in" escape hatch), not to a bare login form.

---

## 4. Error messaging compatible with `ACCOUNT_PREVENT_ENUMERATION=True`

- **OWASP / security guidance** — the standard mitigation for enumeration is a single generic message
  for both "wrong password" and "no such account" (e.g. "Invalid credentials" / "email or password is
  incorrect"), plus constant-time responses so timing doesn't leak existence.
  [owasp.org – Testing for Account Enumeration](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/03-Identity_Management_Testing/04-Testing_for_Account_Enumeration_and_Guessable_User_Account),
  [stytch.com/blog/prevent-enumeration-attacks](https://stytch.com/blog/prevent-enumeration-attacks/),
  [controlgap.com – protect against username enumeration](https://www.controlgap.com/blog/how-to-protect-against-username-enumeration-from-forms)
- Security commentary itself notes this is "most problematic ... from a usability perspective" —
  i.e. the security requirement and the UX goal are acknowledged to be in tension, which is exactly
  FreedomLS's situation.
  [davecallan.com – account enumeration prevention](https://davecallan.com/web-security-account-enumeration-prevention/)
- The way products square this: keep the generic **security-relevant** message strictly generic (never
  say "that email isn't registered"), but pair it with a **non-committal, always-shown** nudge that
  doesn't depend on whether the account exists — e.g. *"Email or password incorrect. New here?
  [Create an account]"* — the nudge is shown to everyone who fails, not conditionally, so it discloses
  nothing.
- **Progressive nudges after repeated failures**: since the exact-match generic message can't escalate
  without leaking info (escalating differently for "exists" vs "doesn't exist" would itself be a leak),
  the safe pattern is to escalate the **same** nudge in prominence/wording after N failures for *any*
  email — e.g. after 1 failure: small inline link; after 2–3 failures: a highlighted callout above the
  form ("Trouble signing in? If you're new, create an account instead") — content and trigger threshold
  identical regardless of whether the email exists, so it stays enumeration-safe. (Synthesis from the
  enumeration-prevention sources above combined with Baymard/learnui error-messaging guidance — no
  single source states this exact escalation pattern; flagged as a design recommendation, not a
  documented industry pattern.)

**Takeaway:** FreedomLS can keep `ACCOUNT_PREVENT_ENUMERATION=True` and still fix the reported failure
by (a) always showing an unconditional "New here? Create an account" link/button next to the generic
error, and (b) escalating that link's visual prominence after repeated failures — the escalation logic
must trigger identically whether or not the email exists, to avoid re-introducing an enumeration oracle.

---

## 5. Common UX complaints and anti-patterns

- **Tiny/low-contrast "sign up" link** buried below a login form — users miss it entirely, especially
  on mobile. (Baymard/UX Movement pattern above.)
- **Ambiguous "Sign in" vs "Sign up" labels** that differ by two letters — learnui.design specifically
  calls this out as forcing users to "think for half a second"; recommends visually/lexically distinct
  labels (e.g. "Log in" vs "Create account").
  [learnui.design/blog/tips-signup-login-ux.html](https://www.learnui.design/blog/tips-signup-login-ux.html)
- **Losing the `next`/intent parameter** when a user switches between login and signup, or when 2FA/
  password-reset is interposed — documented as a real, repeated bug class (e.g. django-allauth-2fa
  losing `next` through the 2FA step; Drupal issue queue for the same problem in password reset/login).
  The consequence is exactly what was reported: user completes auth but lands somewhere generic instead
  of back at "apply for this course".
  [github.com/valohai/django-allauth-2fa/issues/51](https://github.com/valohai/django-allauth-2fa/issues/51),
  [drupal.org/project/drupal/issues/3362664](https://www.drupal.org/project/drupal/issues/3362664)
- **Forcing re-entry of email** after switching screens or after a failed attempt — explicitly called
  out as a failure mode to avoid.
  [learnui.design/blog/tips-signup-login-ux.html](https://www.learnui.design/blog/tips-signup-login-ux.html)
- **Redirecting to a generic login/401 page with no context** instead of preserving what the user was
  trying to do — a commonly cited anti-pattern in web-app auth flows generally.
  [dev.to/aragossa – please stop redirecting to login on 401](https://dev.to/aragossa/please-stop-redirecting-to-login-on-401-errors-3c0l)

**Takeaway:** This maps almost exactly to the reported bug: the user's "apply" intent likely needs to
survive as a `next` param through whichever auth path is chosen, and the current login page's route to
"I'm new" is probably too small/ambiguous — both are named anti-patterns, not edge cases.

---

## 6. Accessibility considerations

- **Tabs for combined login/signup**: use proper `role="tablist"`/`role="tab"` with `aria-selected`
  (or, better, native controls) so switching between "Log in" and "Sign up" is announced and operable
  by keyboard and screen reader, not just a visual toggle.
  [a11y-collective.com – Building Accessible Tab Interfaces](https://www.a11y-collective.com/blog/accessibility-tab/)
- **Every toggle/segmented control needs an accessible name** (`aria-label`/`aria-labelledby`) — a bare
  icon or colour-only distinction between "log in" and "sign up" states fails WCAG.
  [accessibilitychecker.org – ARIA toggle fields](https://www.accessibilitychecker.org/wcag-guides/ensure-every-aria-toggle-field-has-an-accessible-name/)
- **Labels outside fields, not placeholder-only** — placeholder text as the only label disappears on
  focus/input and commonly fails WCAG 2.1 contrast; this applies equally to email fields shared between
  login and signup forms.
- **Full keyboard operability**: users must be able to switch login↔signup, submit, and follow the
  "create an account" nudge without a mouse; focus should move sensibly (e.g. to the email field) when
  the form/tab changes.
  [a11y-collective.com – ARIA button](https://www.a11y-collective.com/blog/aria-button/)
- **Error messages must be programmatically associated** with the form (e.g. `aria-describedby`, a live
  region) so screen-reader users hear the generic "incorrect email or password" message and the
  "create an account" nudge, not just sighted users via colour/positioning.
  [uxdesign.cc – Building better logins: a UX and accessibility guide](https://uxdesign.cc/building-better-logins-a-ux-and-accessibility-guide-for-developers-9bb356f0a132)

**Takeaway:** Whatever fix is chosen (redirect-to-signup, tabbed toggle, or inline nudge), it must be
implemented with real focus management, `aria-live` error announcement, and a properly-labelled toggle
— not just a CSS-visible link — or the accessibility gap will mirror the discoverability gap that
caused the original complaint.

---

## Summary of recommendations for the spec

1. Route unauthenticated users hitting an **acquisition-intent CTA** ("apply", "enrol") to **signup**
   by default, with an unmissable "already have an account? Log in" link — matches Coursera/edX/Khan
   Academy convention (§3) and Baymard's guest-checkout-style guidance (§2).
2. Whatever screen they land on, preserve the **`next` param / course-application intent** through
   login, signup, and any interposed step (2FA/verification) — this is a named, recurring bug class
   in django-based auth stacks (§5).
3. Make the login↔signup switch **visually unambiguous** and **carry over the typed email** — don't
   force retyping (§1, §5).
4. Keep the enumeration-safe generic error message, but pair it with an **always-shown** "New here?
   Create an account" nudge, and consider escalating its prominence after repeated failures using
   logic that doesn't depend on whether the account exists (§4).
5. Build the toggle/nudge with proper ARIA roles, labels, and live-region error announcements (§6).
6. Identifier-first or magic-link auth would structurally remove this whole class of bug, but is a
   bigger change — worth flagging as a future direction, not this spec (§2).

---

status: ok
