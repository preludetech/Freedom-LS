# Research: capturing "failed sign-in intent" to help lost applicants

**Question**: Should FreedomLS silently record the email address a visitor types into the login form
when it doesn't match any account (plus what they were trying to reach), so staff can follow up?
FreedomLS deliberately does not reveal to the visitor whether an email is registered
(anti-enumeration), and operates in GDPR and POPIA jurisdictions.

---

## 1. Privacy/legal basis

**Lawful basis for storing the typed email (GDPR Art. 6(1)(f) / POPIA processing conditions).**
Legitimate interest can, in principle, cover a business purpose like "help a would-be learner who
got stuck," but the ICO's three-part legitimate-interests test requires the interest to be genuine,
the processing necessary, and — critically — that it doesn't override the person's own rights, and
that the person could **reasonably expect** this use ([ICO — when can we rely on legitimate
interests](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/when-can-we-rely-on-legitimate-interests/)). A visitor typing an email into a login box expects it to be used to *authenticate them*, not
retained and used to contact them later — "any purpose the user wouldn't expect... does not fall
under a legitimate interest basis" ([CookieYes — Legitimate Interest Under
GDPR](https://www.cookieyes.com/blog/legitimate-interest/)). That expectation gap is the central
legal risk: silent capture is unlikely to survive a balancing test unless it is clearly disclosed
and narrowly scoped (see minimisation below). Genuine anti-fraud/security processing (e.g., logging
failed attempts to rate-limit or detect brute force) *is* recognised as a legitimate interest
([Auth0 — GDPR: Protect and Secure User
Data](https://auth0.com/docs/secure/data-privacy-and-compliance/gdpr/gdpr-protect-and-secure-user-data)),
but that only justifies short-lived security logging, not indefinite lead-capture for outreach.

Under POPIA, the same "reasonable expectation" logic applies via the processing-limitation and
purpose-specification conditions, and it also matters because of what happens *next* (see below).

**Emailing the captured address (direct marketing vs. service message).** This is the sharper legal
problem: an unsolicited "we noticed you tried to log in, need help enrolling?" email sent to an
address someone merely typed (who may not even be the address's owner) is direct electronic
marketing, not a transactional/service message, because the recipient never asked for it and has no
account or relationship with the site.
- **POPIA s69** prohibits unsolicited direct marketing by electronic communication unless the data
  subject has given consent, or (narrowly) is an *existing customer* contacted about similar
  products with an opt-out — a failed, non-account visitor is neither
  ([popia.co.za — Section 69](https://popia.co.za/section-69-direct-marketing-by-means-of-unsolicited-electronic-communications/); [Michalsons — Guidance note on direct marketing](https://www.michalsons.com/blog/guidance-note-on-direct-marketing-in-south-africa/51168); [DLA Piper Africa — Direct Marketing Guidance
  Note](https://www.dlapiperafrica.com/en/south-africa/insights/2025/Data-Protection-Guidance-Note-on-Direct-Marketing)).
- **UK/EU PECR/ePrivacy**: legitimate interest cannot be used to bypass PECR's consent requirement
  for unsolicited electronic mail marketing — "legitimate interests does not override PECR... If
  PECR requires consent, you must not use legitimate interests as your lawful basis" ([ICO — When can we
  rely on legitimate interests](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/when-can-we-rely-on-legitimate-interests/); [Data Protection Network — When is direct marketing a legitimate
  interest?](https://dpnetwork.org.uk/direct-marketing-legitimate-interests/)). A "soft opt-in" exists only for existing customers who were given a chance to opt out at
  the point of sale — again not applicable to a stranger who typed an email into a login box.
- Sending mail *to the address the visitor typed* also risks emailing an uninvolved third party
  (typo) — see Security section.

**Retention limits.** Neither law sets a numeric retention period; both require retention no longer
than necessary for the stated purpose (POPIA's storage limitation condition; GDPR Art. 5(1)(e)).
For a "help someone who got stuck" purpose, that implies a short, defined window (e.g., days, not
months) after which the record must be deleted or anonymised, plus a documented retention schedule.

**Disclosure.** Whatever is captured must be named in the site's privacy notice: what's stored (a
typed email + the destination URL/course), the purpose, the legal basis, retention period, and how
to object/request erasure. Undisclosed capture of failed-login input is the kind of "invisible
processing" GDPR/POPIA transparency obligations exist to prevent.

**Minimisation.** Never store the password (see Security). If technically capturing "what they were
trying to do," store only the destination context needed (course/page identifier), not full request
logs, form field dumps, or headers/user-agent beyond what security monitoring already needs. Do not
retain entries that turn out to belong to an existing account (that's just a forgotten-password
event, already served by the "forgot password" flow) or that are indistinguishable from typos of an
existing user's real address.

**Takeaway:** Silently capturing and later emailing a typed, non-account email is legally fragile on
both instruments (unexpected use under GDPR/POPIA, and POPIA s69/PECR treat unsolicited outreach as
marketing requiring consent) — an opt-in, explicit-ask design (Section 4) is the only version that
sits comfortably within legitimate interest / consent and avoids s69/PECR entirely.

---

## 2. Security

**The typed email is not verified — it may belong to someone else.** A classic risk with any
"capture what was typed" feature: fat-fingered or wrong-recollection emails belong to real,
unrelated third parties, who would then receive unsolicited contact ("we saw your application") for
something they never did — a data-accuracy problem under POPIA/GDPR and a bad user experience for an
innocent bystander.

**Credential-stuffing / scraping will flood the table.** Automated credential-stuffing operates at
huge scale — Akamai tracked **26 billion** credential-stuffing attempts per month in 2024, and
because ~half of users reuse passwords, stuffing succeeds often enough to be economically viable for
attackers ([Breachsense / cited via search — credential stuffing
scale](https://www.breachsense.com/blog/what-is-credential-stuffing/); [OWASP — Credential
stuffing](https://owasp.org/www-community/attacks/Credential_stuffing)). If "email + no account"
is logged unconditionally, an attacker running a combo-list (email:password pairs from breach dumps)
against the login form will populate the table with thousands of unrelated, often stolen, real email
addresses — turning a "help our learners" feature into a fresh honeypot of PII and a compliance
liability, and potentially triggering a breach-notification-worthy incident if that table leaks.
Mitigations if this is pursued at all:
- Only log after **N repeated attempts** with the same email (matching the actual "gave up after
  several tries" scenario, not every single miss).
- Rate-limit and IP/device fingerprint the logging path itself, separately from the login endpoint's
  own throttling.
- De-duplicate by email — don't accumulate multiple rows for the same repeated attempts.
- Cap total volume (e.g., per hour/day) and alert on spikes indicative of automated scanning.
- Never combine this with password logging — the password field must never be persisted anywhere
  (not in this table, not in general logs); this is a basic, non-negotiable secure-logging rule
  reflected throughout OWASP's authentication guidance ([OWASP — Authentication Cheat
  Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)).

**Don't let this feature change the anti-enumeration response.** OWASP is explicit that
login/registration/reset flows must return **the same generic message regardless of whether the
account exists** ("Invalid username or password") to prevent enumeration
([OWASP — Authentication Cheat
Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html); [OWASP —
Testing for Account Enumeration](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/03-Identity_Management_Testing/04-Testing_for_Account_Enumeration_and_Guessable_User_Account)). django-allauth's own `ACCOUNT_PREVENT_ENUMERATION` setting exists precisely to close this
hole by always sending an email and never varying the on-screen response ([allauth
docs — Configuration](https://docs.allauth.org/en/latest/account/configuration.html); [GitHub
allauth #1401 — enumeration issue](https://github.com/pennersr/django-allauth/issues/1401)).
Any capture logic must sit entirely server-side, behind the identical response the visitor already
sees — timing, status code, and copy must not differ based on whether logging occurred.

**Takeaway:** If built, gate capture behind a repeated-attempt threshold + strict rate limiting +
de-duplication, never store the password, and never let the capture path leak into the
visitor-facing response (which must stay enumeration-safe).

---

## 3. Product patterns: does silent capture actually work?

**Abandoned-signup/cart recovery is a well-established pattern, but it's built on captured, willing
data, with fast timing.** In e-commerce/SaaS, 10–25% of abandoned signups can be recovered with a
tight follow-up sequence, and the best-converting window is the first 30–60 minutes; waiting a full
day roughly halves the conversion rate ([Dodo Payments — Abandoned Cart Recovery for
SaaS](https://dodopayments.com/blogs/abandoned-cart-recovery-saas); [Kelviq — How abandoned cart
emails actually recover revenue](https://www.kelviq.com/blog/abandoned-cart-emails-saas/)).
Recommended practice is to **capture the email early in a flow the user is already
progressing through** (e.g., "email before card details" in checkout) — i.e. the person has
volunteered the address as part of *their own* action, not had it inferred from a failed login.
That is materially different from FreedomLS's scenario, where the "abandonment" point is a failed
*authentication* attempt, not a stalled signup form the visitor was filling in.

**No direct evidence found for "silently capture failed-login emails and cold-email them."** Search
did not surface case studies or vendor patterns for capturing emails typed into a *login* (not
signup) form and treating failed authentication as a marketing-lead signal — the abandoned-cart/
abandoned-signup literature is uniformly about people who started providing data voluntarily in a
conversion flow, not people who got an "invalid credentials" wall. This absence is itself a signal:
it's not an established, de-risked pattern the way cart-recovery is.

**Explicit-ask ("leave your email, we'll help") is the pattern actually used for this exact
situation** and is consistent with general login-UX guidance to give struggling users a clear,
low-friction escape hatch rather than trapping them — e.g., clear messaging like "no account found
for that email" (in enumeration-tolerant contexts) that helps the user self-diagnose, and offering
account recovery/help affordances directly in the flow ([Loop11 — 15 tips to improve UX of
registration/login forms](https://www.loop11.com/15-tips-to-improve-the-ux-of-registration-and-login-forms/)).

**Takeaway:** The evidence base supports fast follow-up on data people *chose* to give during a
flow they were completing — not on inferring intent from failed logins; an explicit "need help?"
ask fits the evidence better than silent capture.

---

## 4. Lower-risk alternatives

1. **Explicit "Need help signing in?" contact affordance on the login page.** A visible link/small
   form ("Can't get in, or don't have an account? Tell us what you're trying to do and we'll help")
   that the visitor voluntarily submits. This converts the whole thing into **consent-based, expected
   processing** — solving the GDPR/POPIA legitimate-expectation problem in Section 1 outright,
   because the person chose to hand over their email for exactly this purpose. It doesn't touch the
   login form's response at all, so it has zero interaction with anti-enumeration protections.

2. **Capture the email only once the visitor starts a signup flow**, not at login. If someone hits
   "Sign up" and gets partway (e.g., enters email, doesn't finish), that's a genuine abandoned-signup
   event with the same legal footing as the cart-recovery pattern in Section 3 — it's their own
   in-progress transaction, matching what they'd reasonably expect follow-up on.

3. **Send a "no account with this email — sign up here" email to the typed address itself**, rather
   than storing it centrally for staff outreach. This is the **allauth "unknown account" pattern**:
   when `ACCOUNT_PREVENT_ENUMERATION` is enabled, allauth always sends an email on password reset
   regardless of whether the account exists, and the message body differs depending on the actual
   result — a real user gets a reset link, a non-user gets a "no account found, want to sign up?"
   notice — while the **on-screen response to the visitor is identical either way** ([allauth
   docs — Configuration, `ACCOUNT_PREVENT_ENUMERATION`](https://docs.allauth.org/en/latest/account/configuration.html)). This preserves enumeration protection perfectly (the *screen* never
   reveals anything) while still getting a helpful message to the mailbox owner — and only the actual
   owner of that mailbox can act on it, which also solves the "typo belongs to someone else" risk in
   Section 2: an unrelated third party just gets an ignorable email instead of being added to a staff
   follow-up list. It requires no new PII store, no retention question, and no direct-marketing
   analysis under POPIA s69/PECR because it's arguably a one-off transactional response to the
   person's own action (attempting to sign in), not an unsolicited marketing communication — though
   the content of that email should stick to "how to get an account" and not upsell/marketing copy to
   stay clearly transactional.

**Comparative takeaway:** Options 1–3 all get a struggling applicant help without creating a
liability-laden database of unverified, non-consenting third-party emails; of the three, option 3
(allauth-style "no account" email to the typed address) most directly targets FreedomLS's actual
reported scenario (repeated failed logins, no account) while option 1 is the simplest to build and
most legally clean, and both can reasonably be combined (help link on the page + automatic
"no account, here's how to sign up" email).

---

## Overall recommendation for FreedomLS

Do **not** silently persist failed-login emails into a staff-facing outreach table. The combination
of (a) unexpected processing under GDPR/POPIA, (b) POPIA s69 / PECR treating unsolicited follow-up
as direct marketing requiring consent, and (c) the credential-stuffing/typo risk of accumulating
unverified third-party emails, makes that design hard to justify. Prefer the allauth-style "no
account found — here's how to sign up" email sent to the typed address (Section 4.3), optionally
paired with a visible, opt-in "need help?" contact affordance on the login page (Section 4.1). Both
preserve the enumeration protection already in place, avoid storing anything beyond what's needed,
and only reach the actual owner of the mailbox.

---

status: ok
