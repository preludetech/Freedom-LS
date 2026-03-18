# Multi-Factor Authentication (MFA)

Add MFA support for educator and admin accounts to protect against credential compromise.

## Why this matters

FLS currently relies solely on email/password authentication. If an educator's or admin's password is compromised (phishing, credential stuffing, password reuse), the attacker gets full access to student data and course management.

MFA is the single most effective control against account takeover. Microsoft reports that MFA blocks 99.9% of automated credential attacks.

ISO 27001 requires MFA in multiple controls:
- **A.5.17** (Authentication Information): "multi-factor authentication should be implemented"
- **A.8.5** (Secure Authentication): applications must support strong authentication mechanisms
- **A.8.26** (Application Security Requirements): authentication requirements must be defined

POPIA and GDPR don't mandate MFA specifically, but both require "appropriate technical measures" to protect personal data - MFA is the standard expectation for any system handling PII.

## When to do this

**Before production with real student data, after the security audit hardening.** MFA for admin/educator accounts is high priority. Student MFA can be optional/later since students have limited access and the risk profile is lower.

Priority order:
1. Django admin accounts (superusers) - highest privilege, highest risk
2. Educator accounts - access to student data
3. Student accounts - optional, lower risk

## In scope

### TOTP-based MFA
- Time-based One-Time Password support (Google Authenticator, Authy, etc.)
- Use `django-otp` + `django-two-factor-auth` or `django-allauth[mfa]` (allauth has built-in MFA since v0.56)
- QR code setup flow for registering authenticator apps
- Recovery codes for account recovery if authenticator is lost

### Enforcement policies
- MFA required for all admin/superuser accounts
- MFA required for educator accounts
- MFA optional for student accounts (configurable per deployment)
- Grace period for existing accounts to set up MFA after policy is enabled

### Admin integration
- MFA enforcement on Django admin login
- Admin view showing which accounts have MFA enabled

## Out of scope
- SMS-based MFA (insecure, vulnerable to SIM swapping)
- Hardware security keys/WebAuthn (nice to have later, not essential)
- Biometric authentication
