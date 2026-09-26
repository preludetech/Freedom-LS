A would-be learner clicked "Apply now" on a course, was sent to the login page, had no account, submitted the login form several times and gave up without signing up or applying. `more-prominent-signup-button` fixes the routing and the login page so fewer people end up there. This idea is about the people who still get stuck: staff should be able to find out who they were and what they were trying to do (the `next` destination, e.g. the course they were applying to), so they can get back to them.

Staff see these records in the Django admin. There is no educator interface page and no notification email.

## What is still open

How to capture the visitor. `research_capturing_failed_signin_intent.md` covers the privacy, security and product side. In short:

- **Silently storing the email typed into a failed login** is legally fragile under POPIA and GDPR, because the visitor does not expect it. Staff follow-up to that address counts as unsolicited direct marketing, which needs consent (POPIA s69, PECR). Typos mean some of those addresses belong to other people, and credential-stuffing bots would fill the table unless capture is gated behind a repeated-attempt threshold, deduplicated and rate-limited.
- **An opt-in "Having trouble? Tell us what you're trying to do" form** on the login page, shown after failed attempts, gives consent-clean records with the email, the `next` destination and a message.
- **Emailing the typed address** with a "no account with this email, here's how to sign up" message, following allauth's `unknown_account` pattern for password reset. This reaches only the mailbox owner and stores nothing, so it leaves staff nothing to follow up on.

Whichever option is chosen must leave the login response unchanged, so that it still does not reveal whether an email has an account (`ACCOUNT_PREVENT_ENUMERATION`), and must never store the password.

## Existing pieces

Nothing persists "an anonymous email that tried to log in, plus where it was going". django-axes logs the attempted email and IP for every failed login, but it records no destination and is a security log. `CourseInterest` and `CourseApplication` both require a `User`. The `next` URL is available on the login page and is the one existing signal for what the visitor was trying to do. `../more-prominent-signup-button/research_allauth_capabilities.md` covers where to hook in: `AccountAdapter.authentication_failed`, Django's `user_login_failed` signal, and what axes stores.
