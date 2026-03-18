# ISO 27001:2022 Requirements for Web Application Source Code

Research into ISO 27001 Annex A controls that are directly relevant to application-level code security, with a focus on Django web applications.

---

## 1. Relevant Annex A Controls

The following ISO 27001:2022 Annex A controls have direct implications for application source code. Controls that are purely organisational or infrastructure-level (physical security, HR screening, etc.) are excluded.

### Primary Code-Level Controls

| Control | Title | Relevance |
|---------|-------|-----------|
| **A.8.4** | Access to Source Code | Restrict read/write access to source code, dev tools, and libraries. Prevent unauthorised introduction of backdoors. |
| **A.8.24** | Use of Cryptography | Define rules for encryption of data at rest and in transit. Manage cryptographic key lifecycle. |
| **A.8.25** | Secure Development Life Cycle | Integrate security into every stage of the SDLC. Separate dev/test/prod environments. |
| **A.8.26** | Application Security Requirements | Identify and document security requirements before development. Covers input validation, authentication, session management, error handling. |
| **A.8.27** | Secure System Architecture and Engineering Principles | Design security into all architecture layers. Define coding standards (e.g. "all inputs must be validated", "all passwords must be salted"). |
| **A.8.28** | Secure Coding | Prevent vulnerabilities through secure coding standards. Covers OWASP Top 10, secret management, dependency management. **New in 2022 edition.** |
| **A.8.29** | Security Testing in Development and Acceptance | Define and implement security testing during development and before go-live. Includes code reviews, SAST, DAST, and acceptance testing. |

### Supporting Controls With Code Implications

| Control | Title | Code Relevance |
|---------|-------|----------------|
| **A.5.17** | Authentication Information | Secure handling of credentials in code. Password policies, hashing, MFA support. |
| **A.8.3** | Information Access Restriction | Enforce authorisation checks in application code. Role-based access control. |
| **A.8.5** | Secure Authentication | Application must implement secure authentication mechanisms. |
| **A.8.10** | Information Deletion | Application must support secure data deletion per retention policies. |
| **A.8.11** | Data Masking | Mask PII in application outputs where appropriate (logs, exports, displays). |
| **A.8.12** | Data Leakage Prevention | Prevent sensitive data exposure through application outputs, error messages, logs, APIs. |
| **A.8.15** | Logging | Application must log security-relevant events with required fields. |
| **A.8.16** | Monitoring Activities | Support anomaly detection through structured, analysable log output. |

---

## 2. Code-Level Security Requirements

### 2.1 Input Validation (A.8.26, A.8.28)

**Requirement:** All input from external sources must be validated server-side before processing.

**What auditors look for:**
- Server-side validation of length, type, format, and allowed characters on all user inputs
- Protection against injection attacks: SQL injection, command injection, LDAP injection, XSS
- Output encoding/escaping to prevent XSS
- File upload validation (type, size, content)
- Whitelisting over blacklisting approach

**Django-specific implementation:**
- Use Django forms and model validation (never trust `request.POST` directly)
- Use the ORM exclusively -- avoid `raw()`, `extra()`, `RawSQL` (already in project conventions)
- Use Django's template auto-escaping (enabled by default); never use `|safe` or `mark_safe()` on user-supplied data
- Validate file uploads with `FileExtensionValidator` and content-type checking
- Use `django.core.validators` for email, URL, and other standard formats

**References:**
- [OWASP Django Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html)
- [Django Security Documentation](https://docs.djangoproject.com/en/6.0/topics/security/)

### 2.2 Authentication (A.5.17, A.8.5, A.8.26)

**Requirement:** Applications must implement secure authentication with support for MFA. Credentials must be stored using industry-standard hashing.

**What auditors look for:**
- Password hashing with strong algorithms (Argon2, bcrypt, PBKDF2)
- Multi-factor authentication support
- Account lockout or rate limiting after failed attempts
- Secure password reset flows
- No credentials in source code or configuration files
- Session invalidation on password change

**Django-specific implementation:**
- Use Django's `PASSWORD_HASHERS` with Argon2 as the preferred hasher (`django.contrib.auth.hashers.Argon2PasswordHasher`)
- Configure `AUTH_PASSWORD_VALIDATORS` for minimum length, complexity, and common password checking
- Implement rate limiting on login views (e.g. `django-axes` or `django-ratelimit`)
- Use `django-otp` or `django-two-factor-auth` for MFA
- Store all secrets in environment variables, never in code (already in project conventions)
- Call `django.contrib.auth.update_session_auth_hash()` on password change

**References:**
- [Django Authentication System](https://docs.djangoproject.com/en/6.0/topics/auth/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)

### 2.3 Session Management (A.8.26)

**Requirement:** Sessions must use secure cookies, enforce timeouts, and rotate tokens to prevent fixation and hijacking.

**What auditors look for:**
- Secure cookie flags (`HttpOnly`, `Secure`, `SameSite`)
- Session timeout (both idle and absolute)
- Session token rotation on authentication
- Session invalidation on logout
- Protection against session fixation

**Django-specific implementation:**
- `SESSION_COOKIE_SECURE = True` (HTTPS only)
- `SESSION_COOKIE_HTTPONLY = True` (no JavaScript access)
- `SESSION_COOKIE_SAMESITE = "Lax"` or `"Strict"`
- `SESSION_COOKIE_AGE` set to an appropriate timeout (e.g. 3600 for 1 hour)
- `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` for sensitive applications
- Django rotates session keys on login by default via `django.contrib.auth.login()`
- Ensure `django.contrib.auth.logout()` is called to flush session data

### 2.4 Access Control / Authorisation (A.8.3, A.8.26)

**Requirement:** Applications must enforce role-based access control. Every request to a protected resource must verify the user's permissions.

**What auditors look for:**
- Authorisation checks on every view/endpoint (not just hiding UI elements)
- Principle of least privilege
- Separation of duties where applicable
- Vertical and horizontal access control (users cannot access other users' data)
- Admin interfaces properly protected

**Django-specific implementation:**
- Use `@login_required` and `@permission_required` decorators or `LoginRequiredMixin`/`PermissionRequiredMixin`
- Implement object-level permissions for multi-tenant/multi-user data isolation
- Filter querysets by the current user/site to prevent horizontal privilege escalation
- Restrict Django admin access (`ADMIN_ENABLED`, IP whitelisting, strong authentication)
- Use `get_object_or_404` with ownership checks, not just PK lookups

### 2.5 Cryptography (A.8.24)

**Requirement:** Define and enforce encryption for data at rest and in transit. Manage cryptographic keys securely throughout their lifecycle.

**What auditors look for:**
- TLS 1.2+ enforced for all connections
- Sensitive data encrypted at rest (database fields, file storage)
- Strong, approved algorithms (no MD5, SHA1 for security purposes, no DES/3DES)
- Cryptographic keys not hardcoded in source
- Key rotation procedures

**Django-specific implementation:**
- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS` set to a large value (e.g. 31536000)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- Use `django-encrypted-model-fields` or similar for sensitive database fields
- `SECRET_KEY` loaded from environment variable, rotated periodically
- Database connections over SSL (`OPTIONS: {'sslmode': 'require'}` in `DATABASES`)

### 2.6 CSRF Protection (A.8.26, A.8.28)

**Requirement:** Applications must protect against Cross-Site Request Forgery.

**Django-specific implementation:**
- `django.middleware.csrf.CsrfViewMiddleware` must be enabled (Django default)
- CSRF token included in all POST forms (`{% csrf_token %}`)
- For HTMX: set `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on body (already in project conventions)
- `CSRF_COOKIE_SECURE = True`
- `CSRF_COOKIE_HTTPONLY = True`
- Never use `@csrf_exempt` without security review and documentation

### 2.7 Security Headers (A.8.26, A.8.27)

**Requirement:** Applications must set appropriate HTTP security headers.

**Django-specific implementation:**
- `SECURE_CONTENT_TYPE_NOSNIFF = True` (X-Content-Type-Options: nosniff)
- `X_FRAME_OPTIONS = "DENY"` or `"SAMEORIGIN"` (clickjacking protection)
- Content-Security-Policy header via `django-csp` middleware
- `SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"`
- `SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"`
- Remove `Server` header where possible

### 2.8 Error Handling and Information Disclosure (A.8.12, A.8.26)

**Requirement:** Error messages must not expose system details, stack traces, or sensitive data to end users.

**What auditors look for:**
- Generic error pages for users (400, 403, 404, 500)
- No stack traces, SQL queries, or configuration details in production error responses
- Detailed errors logged server-side only
- No sensitive data in URL parameters
- API error responses do not leak internal structure

**Django-specific implementation:**
- `DEBUG = False` in production (critical)
- Custom error templates: `400.html`, `403.html`, `404.html`, `500.html`
- Use Django's `ADMINS` setting for error notification
- Structured error logging to server-side logs
- Ensure API views return sanitised error responses

### 2.9 Audit Logging (A.8.15, A.8.16)

**Requirement:** Applications must log security-relevant events with sufficient detail for incident investigation. Logs must be protected from tampering.

**Required log fields per event (A.8.15):**
- User ID
- Description of the activity/event
- Date and time (UTC)
- Device/system identity
- IP address

**Events that must be logged:**
- Authentication attempts (successful and failed)
- Privilege escalation and administrative actions
- Access to sensitive data
- Data modifications (create, update, delete) on critical records
- System and application errors
- Session creation and destruction
- Permission changes

**Django-specific implementation:**
- Configure Django's `LOGGING` setting with structured output (JSON format preferred)
- Use `django.contrib.admin.models.LogEntry` for admin audit trail
- Implement middleware or signals to log authentication events
- Use `django-auditlog` or `django-simple-history` for model change tracking
- Log to a centralised, tamper-resistant store (not just local files)
- Include request metadata (user, IP, user-agent) in log records
- Protect log files from modification (append-only, separate permissions)

### 2.10 Data Protection (A.8.10, A.8.11, A.8.12)

**Requirement:** Applications must support secure data deletion, masking of PII, and prevention of data leakage.

**What auditors look for:**
- PII not exposed in logs, error messages, or debug output
- Data masking in non-production environments
- Secure deletion capability (not just soft-delete)
- API responses do not over-expose data (return only required fields)
- No sensitive data in browser caches or local storage

**Django-specific implementation:**
- Use serializers or explicit field lists to control API output (never serialise entire model objects)
- Scrub PII from log output
- Implement data retention and deletion management commands
- Use `Cache-Control: no-store` headers for sensitive pages
- Mask sensitive fields in admin views where appropriate

---

## 3. Secure Coding Practices (A.8.28)

A.8.28 is a **new control** in the 2022 edition, specifically requiring secure coding standards. Key requirements:

### 3.1 Coding Standards
- Define and enforce secure coding rules for all developers
- Align with OWASP Top 10 and OWASP ASVS (Application Security Verification Standard)
- Code review for security on all changes (not just functionality)

### 3.2 Secret Management
- No API keys, passwords, or tokens in source code
- Use environment variables or a secret management system (e.g. HashiCorp Vault, AWS Secrets Manager)
- Scan for secrets in CI pipeline (e.g. `trufflehog`, `gitleaks`, `detect-secrets`)

### 3.3 Dependency Management
- Maintain an inventory of all third-party libraries
- Monitor for known vulnerabilities (e.g. `pip-audit`, `safety`, Dependabot, Snyk)
- Define SLAs for patching: critical vulnerabilities within 24-48 hours, high within 1 week
- Pin dependency versions, review updates before applying

### 3.4 Static Analysis (SAST)
- Run SAST tools in CI on every pull request
- Block merges on high/critical findings
- Tools for Django/Python: `bandit`, `semgrep`, `SonarQube`

### 3.5 Framework Hardening
- Disable debug mode in production
- Remove default/example pages and endpoints
- Set all security-related Django settings explicitly
- Review Django's deployment checklist: `python manage.py check --deploy`

---

## 4. Security Testing Requirements (A.8.29)

### During Development
- Peer code review with security focus
- SAST on every commit/PR
- Unit tests for security controls (authentication, authorisation, input validation)

### In Staging/Pre-Production
- DAST scanning against running application (e.g. OWASP ZAP, Burp Suite)
- Penetration testing (at least annually, or before major releases)
- Dependency vulnerability scanning

### Acceptance Criteria
- No high or critical vulnerabilities
- All OWASP Top 10 categories addressed
- Security requirements from A.8.26 verified

---

## 5. Common Gaps That Fail ISO 27001 Audits

Based on research into common audit failures for web applications:

### 5.1 Authentication and Session Weaknesses
- No MFA support
- No account lockout or rate limiting
- Session tokens not rotated on login
- Missing session timeouts
- Passwords stored with weak hashing (MD5, SHA1 without salt)

### 5.2 Missing or Inadequate Logging
- Authentication events not logged
- Logs missing required fields (user ID, timestamp, IP)
- No log protection (logs can be modified or deleted)
- No monitoring or alerting on suspicious patterns
- PII exposed in log output

### 5.3 Input Validation Failures
- Client-side-only validation without server-side checks
- SQL injection via raw queries or string interpolation
- XSS via unescaped user content
- Missing file upload validation

### 5.4 Insufficient Access Control
- Broken object-level authorisation (IDOR -- users accessing other users' data via predictable IDs)
- Missing authorisation checks on API endpoints
- Admin interface exposed without additional protection
- No separation between user roles

### 5.5 Cryptography Issues
- HTTP allowed (no TLS enforcement)
- Missing HSTS headers
- Sensitive data stored unencrypted
- Hardcoded secrets in source code or configuration files
- Weak algorithms in use

### 5.6 Error Handling and Information Disclosure
- Debug mode enabled in production
- Stack traces exposed to users
- Detailed error messages revealing database structure or internal paths
- Version numbers exposed in HTTP headers

### 5.7 Missing Security Headers
- No Content-Security-Policy
- No X-Frame-Options (clickjacking)
- No X-Content-Type-Options
- Missing Referrer-Policy

### 5.8 Dependency Management
- Outdated libraries with known CVEs
- No process for monitoring or updating dependencies
- No software bill of materials (SBOM)

### 5.9 Documentation Gaps
- Security requirements not documented before development
- No evidence of security testing
- No risk assessment mapping controls to application features
- Missing secure coding guidelines

---

## 6. Django Deployment Security Checklist

Django provides a built-in deployment check that covers many ISO 27001-relevant settings:

```bash
python manage.py check --deploy
```

**Critical settings that must be configured for compliance:**

```python
# Production security settings
DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]  # From environment, never hardcoded
ALLOWED_HOSTS = ["your-domain.com"]

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Session timeout
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
```

---

## 7. References

### ISO 27001 Annex A Control Guides
- [ISO 27001:2022 Annex A Controls Overview (DataGuard)](https://www.dataguard.com/iso-27001/annex-a/)
- [A.8.4 Access to Source Code (ISMS.online)](https://www.isms.online/iso-27001/annex-a-2022/8-4-access-to-source-code-2022/)
- [A.8.24 Use of Cryptography (HighTable)](https://hightable.io/iso27001-annex-a-8-24-use-of-cryptography/)
- [A.8.25 Secure Development Life Cycle (HighTable)](https://hightable.io/iso27001-annex-a-8-25-secure-development-life-cycle/)
- [A.8.26 Application Security Requirements (HighTable)](https://hightable.io/iso27001-annex-a-8-26-application-security-requirements/)
- [A.8.27 Secure System Architecture (HighTable)](https://hightable.io/iso27001-annex-a-8-27-secure-systems-architecture-and-engineering-principles/)
- [A.8.28 Secure Coding (ISMS.online)](https://www.isms.online/iso-27001/annex-a-2022/8-28-secure-coding-2022/)
- [A.8.28 Secure Coding (HighTable)](https://hightable.io/iso27001-annex-a-8-28-secure-coding/)
- [A.8.29 Security Testing (HighTable)](https://hightable.io/iso27001-annex-a-8-29-security-testing-in-development-and-acceptance/)
- [A.8.12 Data Leakage Prevention (ISMS.online)](https://www.isms.online/iso-27001/annex-a-2022/8-12-data-leakage-prevention-2022/)
- [A.8.15 Logging (HighTable)](https://hightable.io/iso-27001-annex-a-8-15-logging/)
- [A.8.16 Monitoring Activities (HighTable)](https://hightable.io/iso-27001-annex-a-8-16-monitoring-activities/)

### Django Security
- [Django Security Documentation](https://docs.djangoproject.com/en/6.0/topics/security/)
- [OWASP Django Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html)
- [OWASP Django REST Framework Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Django_REST_Framework_Cheat_Sheet.html)

### ISO 27001 Application Security
- [ISO 27001 Application Security Compliance (StackHawk)](https://www.stackhawk.com/blog/iso-27001-application-security-compliance)
- [Application Security According to ISO 27001 (Invicti)](https://www.invicti.com/white-papers/application-security-according-to-iso-27001-invicti-ebook)
- [Web Application Security Testing for ISO 27001 (Neumetric)](https://www.neumetric.com/web-application-security-testing-for-iso-27001-certification-1861/)

### Standards
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Application Security Verification Standard (ASVS)](https://owasp.org/www-project-application-security-verification-standard/)
- [ISO/IEC 27001:2022 Official](https://www.iso.org/standard/27001)
