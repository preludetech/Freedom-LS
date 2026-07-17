# Security and Data Handling

_Last updated: 2026-07-17_

## Summary

- **Built:** All HTTP traffic is protected at the application layer: CSRF middleware, nh3 markdown sanitisation (Rust-based allowlist), clickjacking prevention (`X_FRAME_OPTIONS=SAMEORIGIN`), Argon2 password hashing, django-axes brute-force lockout, multi-site data isolation via `SiteAwareManager`, and SSRF-protected webhook delivery with Fernet-encrypted secrets.
- **Built:** Dev-time security gates run on every commit via pre-commit hooks: detect-secrets, detect-private-key, bandit (medium+ severity), ruff, mypy, shellcheck, and merge-conflict/large-file/AST checks.
- **Built:** Production settings trust the reverse proxy's forwarded HTTPS scheme, so the HTTPS redirect and HSTS header behave correctly behind a TLS-terminating proxy, and refuse to start if `SECRET_KEY` is missing or empty rather than booting with broken session/CSRF signing.
- **Built:** Media files in object storage are private by default — served via time-limited signed URLs rather than public links, so application-gated course files do not leak from a guessed or shared link. Error tracking (Sentry) is wired but inactive until an operator supplies credentials, and defaults to **not** sending learner personal data with error events.
- **Report-only:** Content Security Policy is currently in report-only mode (`SECURE_CSP_REPORT_ONLY`), not enforcing. HSTS is configurable but requires a staged rollout during deployment; it is not active by default.
- **Not yet built:** 2FA/MFA, automated data-deletion tooling, data-subject-rights tooling, and a formal incident-response runbook do not exist in code. These are documented honestly in §4 and tracked in the [roadmap](./roadmap.md).
- **Not yet built:** A per-request access-controlled media gate (re-checking course access on every file download) — signed URLs are time-limited but not access-checked per request, so anyone holding a live URL can fetch the file until it expires. Automated scrubbing of personal data from error-tracking events is likewise absent — opting into sending personal data to Sentry sends it unredacted.
- **Infrastructure:** The target deployment uses Vultr Johannesburg (ISO 27001:2022 certified). Vultr's certification covers physical and hypervisor layers; the FLS operator owns OS hardening, access control, logging, backups, and ISMS documentation. See §5 for the shared-responsibility split.

---

## Development-time controls

### Pre-commit hooks (built)

Every commit triggers the following checks, sourced directly from `.pre-commit-config.yaml`:

| Hook | Purpose |
|---|---|
| `detect-secrets` (Yelp v1.5.0, baseline-checked) | Blocks accidental credential commits |
| `detect-private-key` | Blocks private key file commits |
| `bandit` (`-ll`, excludes `./tests`) | Python security linter, medium-and-above severity |
| `ruff-check --fix` + `ruff-format` | Linting and formatting |
| `mypy` (full project, `--config-file=pyproject.toml`) | Static type checking |
| `shellcheck` | Shell script linting |
| `check-merge-conflict` | Blocks unresolved merge markers |
| `check-added-large-files` (max 1024 KB) | Prevents large binary blobs |
| `check-ast` | Validates Python syntax |
| `debug-statements` | Blocks accidental `pdb`/`breakpoint()` |
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml` | File hygiene |

### GitHub security features (operational — requires configuration)

Branch protection, Dependabot vulnerability alerts, secret scanning, and CodeQL are covered by the deployment security checklist. See [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §12 — this document does not duplicate that checklist.

---

## Runtime application security

All controls below are **built** unless labelled otherwise.

### CSRF protection

`CsrfViewMiddleware` is active in the middleware stack. HTMX requests include the CSRF token via a global `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` attribute on the `<body>` element, so all HTMX partial requests are covered without per-view decoration.

### Content Security Policy (report-only — not enforcing)

`django.middleware.csp.ContentSecurityPolicyMiddleware` is in the middleware stack. The policy is configured via `SECURE_CSP_REPORT_ONLY`, which means violations are reported but not blocked. The current policy permits `self` for most directives, `unsafe-inline` for scripts and styles (required by HTMX/Alpine.js inline usage), and restricts `frame-src` to `self`, `youtube.com`, and `youtube-nocookie.com`.

Enforcing mode (`SECURE_CSP`) has not been enabled. Removing `unsafe-inline` requires a refactor of inline script/style usage; this is tracked in the [roadmap](./roadmap.md).

### Markdown XSS sanitisation

All markdown content is passed through the `nh3` sanitiser (Rust-based, memory-safe) before rendering. nh3 applies a strict allowlist defined in `MARKDOWN_ALLOWED_TAGS` — only explicitly permitted cotton component tags and their declared attributes pass through. All other HTML is stripped. This prevents stored XSS from authored content.

### Clickjacking

`XFrameOptionsMiddleware` sets `X-Frame-Options: SAMEORIGIN` on every response. This value is deliberate: PDF embed widgets require same-origin framing, so `DENY` is not used.

### HSTS (operational — staged rollout required)

`SecurityMiddleware` supports HSTS via the `HSTS_SECONDS`, `HSTS_INCLUDE_SUBDOMAINS`, and `HSTS_PRELOAD` environment variables. These are not set to meaningful values by default; a staged rollout must be followed at deployment time to avoid locking users out during TLS certificate changes. The four-stage rollout procedure (1 hour → 1 week → 1 year → preload submission) is documented in [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §4. HSTS also depends on the application correctly recognising proxied requests as HTTPS, as described above under [Security middleware](#security-middleware) — without that, the header is inert behind a TLS-terminating proxy regardless of these values.

### Brute-force lockout

django-axes is configured with `AXES_FAILURE_LIMIT = 5` and `AXES_COOLOFF_TIME = 1` (1 hour). After five failed login attempts from the same IP address or username, the account is locked for one hour. Lockout state resets on successful login (`AXES_RESET_ON_SUCCESS = True`). `AxesStandaloneBackend` is registered in `AUTHENTICATION_BACKENDS`.

### Password hashing

Argon2 is the primary password hasher (`PASSWORD_HASHERS` first entry: `Argon2PasswordHasher`). PBKDF2, PBKDF2SHA1, and BCryptSHA256 are retained as fallback hashers for password migration. Minimum password length is 10 characters; common-password and numeric-only checks are enforced via `AUTH_PASSWORD_VALIDATORS`.

### Static file serving

WhiteNoise middleware serves compressed, cache-busted static files directly from Django without a separate file server. This removes a class of misconfigured file-server vulnerabilities.

### Security middleware

`django.middleware.security.SecurityMiddleware` is the first middleware in the stack. It handles SSL redirects (when `SECURE_SSL_REDIRECT` is set), secure cookie flags, and the HSTS header based on environment variable configuration.

Because production runs behind a reverse proxy that terminates TLS, FLS is configured to trust the proxy-forwarded HTTPS scheme, so the application correctly recognises proxied requests as secure. Without this, the HTTPS redirect could loop indefinitely and the HSTS header would never take effect, because Django would see every request — even ones that reached the proxy over HTTPS — as plain HTTP. This is safe because production terminates TLS at a trusted proxy under the hardening preconditions in the deployment security checklist; see [`../deployment-security-checklist.md`](../deployment-security-checklist.md) for those preconditions.

**`SECRET_KEY` is required at boot.** Production refuses to start if `SECRET_KEY` is missing or empty — the application fails immediately at startup (a visible crash-loop) rather than booting and silently running with a broken signing key, which would compromise session and CSRF signing. This check only catches an absent or empty key; a present-but-weak key is separately flagged by Django's deployment checks, which already run in CI.

### Multi-site data isolation

A single FLS installation can serve multiple sites (domains), each with fully isolated users, content, and settings. Isolation is automatic: `SiteAwareManager` filters every ORM query to the current site derived from the request thread-local. No cross-site data leakage is possible through the ORM. This is the canonical statement of the isolation guarantee; see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md) for full detail.

### Webhook controls

Outbound webhooks use HMAC signing or custom auth headers. Per-site secrets are encrypted at rest using Fernet (`django-fernet-encrypted-fields`). In production mode, webhook target URLs are validated against an SSRF allowlist — only HTTPS URLs resolving to public IP addresses are permitted; private/loopback addresses are blocked. See [webhooks](./webhooks.md) for the full control set.

### Media file access control (built, with a stated limitation)

Course pages are access-controlled: a learner must be authorised to view a course before FLS renders a link to its content. Historically the files themselves — PDFs, videos, images — were not: once a file's URL was known it could be fetched directly regardless of course access, because file links pointed straight at storage rather than passing through a permission check on every download.

When object storage is configured for a deployment, this gap is closed at the storage layer: files are private by default and every file link is a signed URL valid for a limited time (one hour, by default). This prevents files from being publicly discoverable or permanently accessible from a leaked link. Public, edge-cacheable serving remains available for deployments that deliberately opt into it (for example, to put large media behind a CDN), but that is an explicit choice, not the default.

**Stated limitation:** this is storage-layer privacy, not per-request access control. FLS does not re-check whether a specific learner is still authorised for a specific file at the moment it is downloaded — a signed link, once issued, works for anyone who has it until it expires. The stronger control (routing every file download through the same access check used for course pages) is not yet built; see the [roadmap](./roadmap.md). When object storage is not configured, media is served from local disk without this signing — that mode is intended for development only. See [deployment](./deployment.md) for how object storage is configured.

---

## Data handling (current-state, honest)

### Personal data collected

The following personal data is stored in the PostgreSQL database:

| Data | Model | Location |
|---|---|---|
| Email address | `User` | `freedom_ls_accounts_user` |
| First name, last name | `User` | `freedom_ls_accounts_user` |
| Hashed password (Argon2) | `User` | `freedom_ls_accounts_user` |
| IP address at consent time | `LegalConsent` | `freedom_ls_accounts_legalconsent` |
| Legal consent record (document type, version, git hash, timestamp, IP, consent method) | `LegalConsent` | `freedom_ls_accounts_legalconsent` |
| Course progress, quiz answers | `CourseProgress`, `FormProgress`, `QuestionAnswer`, `TopicProgress` | `freedom_ls_student_progress_*` |
| Webhook delivery logs (may contain user data in payload) | `WebhookDelivery`, `WebhookEvent` | `freedom_ls_webhooks_*` |

No payment data, government ID, or biometric data is stored by FLS itself.

### Encryption in transit

TLS is termination at the Caddy reverse proxy (or Cloudflare edge) using certificates from Let's Encrypt. `SecurityMiddleware` can enforce HTTPS redirect via `SECURE_SSL_REDIRECT`. Database connection encryption is configurable via an environment variable and defaults to **disabled** for the shipped same-host containerised PostgreSQL, which does not run TLS; the modes that turn on database TLS (`require`/`verify-full`) are reserved for external or managed databases, where they should be used. For the shipped same-host topology, the control that actually matters is not publishing the database port to the host — not the SSL mode — see [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §3 for that control and for external/managed-database guidance. All of this requires correct deployment configuration.

### Error tracking and personal data (Sentry)

FLS can report application errors to Sentry, an external error-tracking service, once an operator supplies credentials; it does nothing until then. Because FLS holds learner personal data (name, email, course activity), an error report can incidentally include that data — for example the email of the learner who triggered the error, or the contents of the request that caused it.

This is **off by default**: an operator must consciously opt in via a configuration flag before personal data is attached to error reports. Left at its default, error reports omit personal data. Automated redaction of personal data from error events before they reach Sentry is **not yet built** — so a deployment that opts into sending it should treat Sentry as a place where that data now lives, with no scrubbing safety net. See [deployment](./deployment.md) for how Sentry is configured.

### Encryption at rest

**Webhook secrets only:** Per-site webhook secrets are encrypted at rest using Fernet symmetric encryption via `django-fernet-encrypted-fields`. The encryption key is derived from `SECRET_KEY` plus a configurable `WEBHOOK_ENCRYPTION_SALT` environment variable.

**Database-level encryption:** FLS does not implement application-level encryption of database rows beyond webhook secrets. Encryption of the PostgreSQL data volume is provider-dependent (the host's disk encryption, or a containerised volume with host-level encryption). Do not overstate this: there is no transparent database encryption built into FLS.

**Backup encryption:** Encrypting `pg_dump` backups before offsite sync is an operational requirement covered in [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §6. No backup scripts are shipped with FLS.

### Consent audit trail

Every terms/privacy acceptance is recorded as an append-only `LegalConsent` row tying the consent to the exact git blob hash of the document version accepted, which makes the record tamper-evident. This is the closest thing FLS has to a personal-data processing record. The full field list and append-only guarantees are owned by [authentication](./authentication.md) — see it for detail.

### Incident response (not yet built)

No formal incident-response runbook, breach notification templates, or automated alerting for data events exists in the codebase. POPIA requires prompt notification to the Information Regulator in the event of a breach. Implementing a written incident-response plan is an operator responsibility, not something FLS ships. This is tracked in the [roadmap](./roadmap.md).

### Data retention and deletion (not yet built)

There is no automated data-retention policy or scheduled deletion tooling in FLS. Deletion of user data is a manual database or Django admin operation (hard delete). The Django admin does not restrict delete permissions on user records beyond standard Django permission checks. Building automated retention/deletion tooling is tracked in the [roadmap](./roadmap.md).

### Data-subject rights tooling (not yet built)

FLS provides no built-in tooling for subject-access requests, right-to-erasure workflows, or data-portability exports. These are operational responsibilities for the FLS operator. Roadmap item: see [roadmap](./roadmap.md).

---

## Infrastructure and shared responsibility

The target deployment runs on **Vultr Johannesburg** (ISO/IEC 27001:2022 certified). ISO 27001 operates on a shared-responsibility model.

### What Vultr's certification covers

Vultr's ISO 27001:2022 certification covers the physical and infrastructure layers:

- Physical data centre security (access controls, CCTV, environmental)
- Hardware maintenance and disposal
- Network backbone and hypervisor/virtualisation layer
- Vultr's own operational procedures and staff controls

### What the FLS operator owns

The operator (the organisation deploying FLS) owns security in the cloud. Each area is labelled by current state:

| Responsibility area | Status |
|---|---|
| OS hardening (SSH key-only, fail2ban, UFW, unattended updates, root login disabled) | Operational — documented in checklist; not automated |
| TLS encryption (Caddy, Let's Encrypt, HTTPS redirect) | Built — Caddy in deployment architecture; requires correct env configuration |
| Encrypted backups (GPG before offsite sync to Backblaze B2) | Planned — strategy in playbook; no automation scripts ship with FLS |
| PostgreSQL SSL connections | Operational — documented in checklist; connection string configuration required |
| Access control (MFA on admin access, least privilege) | Operational — checklist item; MFA on infrastructure access is not automated |
| Centralised logging and failed-login alerting | Not yet built — no logging pipeline is configured by FLS |
| Backup and disaster recovery (documented schedule, tested restores, defined RTO/RPO) | Planned — strategy defined; restore testing and formal RTO/RPO are not yet documented |
| Incident response plan | Not yet built — operator responsibility; no runbook ships with FLS |
| Change management | Operational — Git-based PR workflow provides a documented audit trail of all code and config changes |
| Vulnerability management (Trivy container scanning, Dependabot, periodic OWASP ZAP) | Operational — Dependabot and secret scanning documented in checklist; Trivy and ZAP are not automated |
| ISMS documentation (Information Security Policy, Risk Assessment, Statement of Applicability) | Not yet built — operator responsibility |

See [deployment](./deployment.md) for the full V1 architecture.

### POPIA data residency

South Africa's Protection of Personal Information Act (POPIA) does not impose a blanket data residency requirement. Cross-border transfers are permitted where adequate protection exists. Hosting on Vultr Johannesburg keeps personal data in South Africa, which simplifies compliance argumentation and aligns with the June 2024 National Policy on Data and Cloud. This is a **practical advantage**, not a legal mandate — unless FLS is deployed by a financial institution or government entity with sector-specific local-hosting requirements.

---

## References

- [`../deployment-security-checklist.md`](../deployment-security-checklist.md) — pre-deployment checklist covering server hardening, TLS, HSTS rollout, firewall rules, backup encryption, log management, monitoring, GitHub security features, and environment variables. Referenced throughout this document; not duplicated here.
- [Deployment](./deployment.md) — V1 architecture (Vultr JNB, Docker Compose, Caddy, Gunicorn, PostgreSQL, Cloudflare, Ansible, GitHub Actions).
