# Authentication

_Last updated: 2026-08-30_

## Summary

- Email is the sole login identifier — there are no usernames. Email verification is mandatory before login is permitted.
- Accounts are hardened with Argon2 hashing, brute-force lockout, login and signup rate limiting, email-enumeration prevention, and a 10-character minimum password.
- Each site has its own signup policy controlling whether self-registration is open and what is collected, including additional registration forms shown after verification.
- Every consent to a legal document is recorded in an append-only audit trail tied to the exact document version accepted.
- A separate token-based system exists for machine-to-machine API access, but is not enabled in a default installation.
- Multi-factor authentication is **not implemented**; see [roadmap](./roadmap.md).

## User Accounts

Users are scoped to a site, so the same email address can exist as two separate accounts on two different sites. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

Email is the login identifier; there are no username fields, and addresses are stored normalised. First and last name are editable by the user from their profile page and are optional unless the site's signup policy requires them.

## Registration

**Email verification is mandatory.** A user cannot log in until they follow the verification link sent to their address. Following it logs them in immediately.

**Per-site signup policy.** Each site can define its own policy controlling whether self-registration is open at all, whether a name is required at signup, whether terms must be accepted before registration completes, and which additional registration forms to present after email verification. A site without its own policy falls back to the installation-wide defaults `ALLOW_SIGN_UPS`, `REQUIRE_NAME`, and `REQUIRE_TERMS_ACCEPTANCE`.

**Additional registration forms.** A deployment can insert its own form steps into the registration flow — for example to collect information specific to its programme. Until a user has completed every required form, they are redirected to the completion step before they can reach any other page.

**Intended destination is preserved.** A destination requested before login survives the whole signup flow, including the additional-form steps, so the user lands where they meant to go. Every such destination is validated as a same-host path before use, and off-host values are discarded in favour of the default post-login redirect. This is what makes the browse-first, log-in-at-commitment flow in [learner experience](./learner-experience.md) work.

## Legal Consent Audit Trail

Consent to a legal document is recorded as an **append-only** record. Each record ties a user to a specific document type (terms or privacy), the version string from the document, and the exact git blob hash of the committed document version they accepted — plus the timestamp, the client IP address at the time, and how consent was given. Recording the git hash is what makes the trail tamper-evident: the record points at one immutable version of the text, not at "the terms" in general.

Append-only is enforced in two layers: updating an existing record raises an error, and the admin registers these records as fully read-only — no add, change, or delete. Direct bulk database updates bypass the first layer, which is why the read-only admin is the second.

This is the canonical description of the consent trail; other docs link here. How legal documents are authored and versioned is covered in [content editing workflow](./content-editing-workflow.md).

## Security Hardening

**Password hashing.** Argon2 is the primary hasher; older algorithms are retained only so existing passwords can be migrated on next login.

**Password strength.** At registration and password change, passwords must be at least 10 characters and are rejected if numeric-only, on the common-password list, or too similar to the user's own details.

**Brute-force lockout.** Five failed login attempts against the same account from the same address trigger a one-hour lockout, which resets on a successful login. The address and the account are not independent lockout keys — both must fail together — so one person's mistakes cannot lock out a shared office address or a NAT gateway, and an attacker guessing from many addresses cannot lock a chosen learner out. Someone who does hit the lockout sees a branded page explaining the pause and pointing them to password reset, rather than a bare error.

**Login failure rate limiting.** A shorter-lived limit sits above the lockout on the login form, capping failed attempts to about ten a minute from one address and about five within a few minutes against one account — enough to blunt both password spraying and a distributed attack on a single account, without shutting anyone out for the hour the lockout does. Like the lockout, it guards the ordinary login form only; the Django admin login has the lockout and nothing above it.

**Signup rate limiting.** Signups are capped per minute, per IP address and per key.

**Email-enumeration prevention.** Responses do not distinguish "email not registered" from "password incorrect", so the login and reset flows cannot be used to discover which addresses have accounts.

Development settings deliberately relax exactly two of these: the password validators are emptied and the signup/login rate limits are switched off. Both are active in production. The brute-force lockout is not relaxed — it applies in development too. See [security and data handling](./security-and-data-handling.md).

## Sessions

Users authenticate with standard session cookies. A successful password reset logs the user in immediately.

## Registration Webhook

A successful new registration fires a `user.registered` webhook carrying the user's id, email, and name. See [webhooks](./webhooks.md).

## API Client Authentication

FLS includes a separate token-based authentication system for machine-to-machine API access, where a client authenticates with an API key rather than an email/password session. **It is not enabled in a default installation** — the code exists but the app is commented out of the installed apps.

## Multi-Factor Authentication

**Not implemented.** There is no TOTP, OTP, or hardware-key support in the codebase in any form, and it should not be presented as available. See [roadmap](./roadmap.md).
