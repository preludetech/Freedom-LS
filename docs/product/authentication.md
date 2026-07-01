# Authentication

_Last updated: 2026-07-01_

## Summary

- Email is the sole login identifier; there are no usernames. Email verification is mandatory before login is permitted.
- Account security is hardened with Argon2 password hashing, brute-force lockout (5 failures → 1-hour cooldown), signup rate limiting, email-enumeration prevention, and a minimum 10-character password policy.
- Per-site signup policy controls whether self-registration is open, and what information is collected; additional registration forms and a post-registration completion step are supported. When a `?next=` destination is in flight, it is preserved through the completion step and validated against the current host before use.
- Every user consent to a legal document is recorded in an append-only `LegalConsent` table with the git hash of the accepted document, the IP address, a timestamp, and the consent method — this is the canonical consent audit trail.
- A separate token-based API authentication system (`app_authentication`) handles machine-to-machine access. Multi-factor authentication (2FA/MFA) is not yet implemented; see [roadmap](./roadmap.md).

## User Accounts

**Custom site-aware user model.** `freedom_ls/accounts/models.py` defines `User` as a subclass of `SiteAwareModelBase`, `AbstractBaseUser`, and `PermissionsMixin`. Users are scoped to a site; the same email address can exist on two different sites as separate accounts. Site isolation is described fully in [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

**Email as login identifier.** `USERNAME_FIELD = "email"`. There are no username fields. `ACCOUNT_LOGIN_METHODS = {"email"}`. Email addresses are stored normalised.

**Profile fields.** `first_name` and `last_name` are editable via the `accounts:account_profile` view. Both are optional by default; the per-site `SiteSignupPolicy` can require them at registration.

## Registration

**Mandatory email verification.** `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`. A user cannot log in until they click the verification link sent to their email. `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` — the user is logged in immediately on confirmation.

**Per-site signup policy (`SiteSignupPolicy`).** Each site can have one `SiteSignupPolicy` row controlling:

| Field | Effect |
|---|---|
| `allow_signups` | Whether self-registration is open on this site |
| `require_name` | Whether first/last name is required at signup |
| `require_terms_acceptance` | Whether the user must accept terms before completing registration |
| `additional_registration_forms` | JSON list of dotted-path form class strings to present after email verification |

If no `SiteSignupPolicy` row exists for a site, the global settings defaults apply (`ALLOW_SIGN_UPS`, `REQUIRE_NAME`, `REQUIRE_TERMS_ACCEPTANCE`).

**Additional registration forms and post-registration completion.** The `additional_registration_forms` list on `SiteSignupPolicy` allows additional form steps to be inserted into the registration flow. `RegistrationCompletionMiddleware` intercepts authenticated users who have not yet completed all required forms and redirects them to the `complete_registration` view before allowing access to any other page.

**`next` preservation and open-redirect safety.** A `?next=` destination requested before login is preserved through the entire signup flow — including the additional-forms and `complete_registration` steps — so the user lands where they intended. Every `next` value is validated with Django's `url_has_allowed_host_and_scheme` (same-host paths only); off-host values are discarded in favour of the default post-login redirect. See [learner experience](./learner-experience.md) for the browse-first, login-at-commitment flow this supports.

## Legal Consent Audit Trail

`LegalConsent` is the canonical record of a user's consent to a legal document. It is append-only by design: the model's `save()` method raises `ValueError` if an update is attempted on an existing row, and the admin registers the model as fully read-only (no add, change, or delete). `QuerySet.update()` and `bulk_update()` bypass the model-level guard; the read-only admin is the second layer of protection.

Each `LegalConsent` row records:

| Field | Content |
|---|---|
| `user` | Foreign key to the consenting user |
| `document_type` | `terms` or `privacy` |
| `document_version` | Version string from the legal document frontmatter |
| `git_hash` | Git blob hash of the exact document version the user accepted |
| `timestamp` | Auto-set at creation (UTC) |
| `ip_address` | Client IP at the time of consent |
| `consent_method` | How consent was given; currently `signup_checkbox` |

The `git_hash` field ties each consent record to the specific committed version of the document. Legal document loading is described in [content-editing-workflow](./content-editing-workflow.md).

## Security Hardening

**Password hashing.** Argon2 is the primary password hasher (`django.contrib.auth.hashers.Argon2PasswordHasher`). PBKDF2, PBKDF2SHA1, and BCryptSHA256 are listed as fallback hashers for legacy password migration.

**Password strength rules** (enforced at registration and password change):

- Minimum 10 characters (`MinimumLengthValidator`, `min_length=10`)
- Common password check (`CommonPasswordValidator`)
- Numeric-only password rejected (`NumericPasswordValidator`)
- User attribute similarity check (`UserAttributeSimilarityValidator`, max similarity 0.7)

**Brute-force protection (django-axes).** After 5 consecutive failed login attempts on a given IP address and username combination, the account is locked for 1 hour (`AXES_FAILURE_LIMIT = 5`, `AXES_COOLOFF_TIME = 1`). The lockout resets on successful login (`AXES_RESET_ON_SUCCESS = True`). `AxesStandaloneBackend` is registered in `AUTHENTICATION_BACKENDS`.

**Signup rate limiting.** `ACCOUNT_RATE_LIMITS = {"signup": "5/m/ip,3/m/key"}` — maximum 5 signups per minute per IP and 3 per minute per key.

**Email enumeration prevention.** `ACCOUNT_PREVENT_ENUMERATION = True`. The system does not differentiate between "email not registered" and "password incorrect" in any response.

## API Client Authentication

`freedom_ls/app_authentication/` provides a separate token-based authentication system for machine-to-machine API access. The `Client` model holds an auto-generated `api_key`. This is distinct from human user sessions: API clients authenticate with the token, not with email/password or session cookies.

Note: the `app_authentication` app is currently commented out of `INSTALLED_APPS` in settings. It exists as code but is not active in a default installation.

## Session Management

Human users authenticate via allauth session-based authentication. Django's standard session middleware manages session cookies. `ACCOUNT_LOGIN_ON_PASSWORD_RESET = True` — users are logged in immediately after a successful password reset.

## Webhook on Registration

When a new user registers successfully, the allauth adapter (`AccountAdapter`) fires a `user.registered` webhook event. The event payload includes `user_id`, `user_email`, `first_name`, and `last_name`. Webhook controls are described in [webhooks](./webhooks.md).

## Multi-Factor Authentication

**2FA / MFA is not currently implemented.** No TOTP, OTP, or hardware-key support exists in the codebase. This is a planned capability; see [roadmap](./roadmap.md).
