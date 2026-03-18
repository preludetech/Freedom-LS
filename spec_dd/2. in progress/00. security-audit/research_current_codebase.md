# FLS Current Codebase Security Audit

Summary of personal data inventory, current security measures, and identified gaps in the Freedom Learning System codebase.

---

## Personal Data Inventory

### User Account Data (accounts.User model)
- **email** (unique, required) - used as username
- **first_name** (optional, max 200 chars)
- **last_name** (optional, max 200 chars)
- **password** (hashed via Django)
- **is_active, is_staff, is_superuser** (boolean flags)
- **site_id** (site awareness)
- **date_joined, last_login** (automatic timestamps)

### Student Management Data
- **CohortMembership** - tracks which cohort a user belongs to
- **UserCourseRegistration** - course enrollment with user_id, course_id, is_active, registered_at
- **CohortCourseRegistration** - cohort-level course assignments
- **Course/Student Deadlines** - deadline tracking per student and cohort
- **RecommendedCourse** - course recommendations with created_at timestamp

### Student Progress Data
- **TopicProgress** - per-user topic completion: start_time, last_accessed_time, complete_time
- **FormProgress** - per-user form/quiz progress: scores (JSONField), completion times
- **QuestionAnswer** - student answers: selected_options (M2M), text_answer (free-text)
- **CourseProgress** - aggregate: progress_percentage, completion timestamps

### External Data Transmission via Webhooks
Webhook events expose personal data to external endpoints:
- **user.registered**: user_id, user_email
- **course.registered**: user_id, user_email, course_id, course_title, registered_at
- **course.completed**: user_id, user_email, course_id, course_title, completed_time

### API Authentication Data
- **app_authentication.Client**: api_key (64-char urlsafe secret), name, is_active

### Webhook Infrastructure Data
- **WebhookEndpoint** - stores webhook secrets and event subscriptions
- **WebhookEvent** - full event payloads (JSONField)
- **WebhookDelivery** - delivery attempt logs including response bodies (500-char truncated)

---

## Current Security Measures in Place

### Authentication & Authorization
- Email-based authentication with custom User model
- `@login_required` decorators on student interface views
- Django allauth with mandatory email verification
- All four Django password validators configured
- Multiple auth backends: ModelBackend, ObjectPermissionBackend (django-guardian), AllAuth

### API & Webhook Security
- API key generation uses `secrets.token_urlsafe(48)` (cryptographically secure)
- Webhook HMAC-SHA256 signatures (Standard Webhooks format)
- HTTPS enforcement for webhook URLs in production
- Circuit breaker pattern (auto-disable after 5 consecutive failures)
- Retry logic with exponential backoff

### CSRF Protection
- Global CSRF via HTMX headers: `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'`
- CSRF middleware enabled

### Content Security
- CSP in **report-only mode** (default-src: self, script-src: self + unsafe-inline, style-src: self + unsafe-inline)
- X-Frame-Options: SAMEORIGIN

### Data Isolation
- Site-aware models with automatic site filtering
- Thread-local request storage for context-aware site selection

### Logging
- Production logging: django.log, django_errors.log, security.log
- Rotating file handlers (10MB, 5 backups)
- Separate loggers for django, django.request, django.security

---

## Identified Gaps & Concerns

### Critical

1. **No HTTPS enforcement in production settings** - SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SECURE_HSTS_SECONDS all not set
2. **CSP is report-only** - violations reported but not enforced; unsafe-inline allowed
3. **No Argon2 password hashing** - still using PBKDF2
4. **No brute-force protection** - no django-axes or rate limiting
5. **Missing security headers** - SECURE_CONTENT_TYPE_NOSNIFF, SECURE_REFERRER_POLICY, SECURE_CROSS_ORIGIN_OPENER_POLICY not set
6. **No data deletion/export capabilities** - no GDPR/POPIA compliance features
7. **Webhook payloads contain PII** - user_email sent to external URLs with no opt-out
8. **No rate limiting on sensitive endpoints** - registration, form submission, password reset

### High Impact

9. **No dependency scanning in CI** - no pip-audit, Bandit, or Semgrep in pipeline
10. **Template security concerns** - CSP allows unsafe-inline for scripts and styles
11. **No encryption at rest** - webhook secrets, API keys, question answers all stored plaintext
12. **API authentication weak** - no key rotation, no expiration, no audit trail
13. **No audit logging for sensitive operations** - no trail of who accessed what

### Medium Impact

14. **No CORS configuration found**
15. **Session security not hardened** - no SESSION_COOKIE_AGE override in prod
16. **S3/Object storage** - no documented access controls
17. **No input validation documentation**

---

## Summary Assessment

**Personal Data Scope:** FLS stores moderate PII including emails, names, course progress, form responses, and timestamps. Data is exposed externally via webhooks.

**Current Security Posture:** Demonstrates security awareness (site-aware isolation, webhook signatures, CSRF, login requirements) but has critical gaps in production hardening, cryptography, operational security, and privacy compliance.

**Readiness:**
- **Development:** Reasonable baseline
- **Production:** NOT ready - missing HTTPS/cookie settings, no brute-force protection, no audit logging
- **Compliance:** Does not yet meet ISO 27001 or GDPR/POPIA requirements
