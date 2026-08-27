# Security and Data Handling

_Last updated: 2026-08-26_

This is the cross-cutting reviewer document. Every claim is labelled by its actual state: **built** (in code and active), **operational** (requires correct deployment configuration), or **not yet built**.

## Summary

- **Built:** CSRF protection on all requests including HTMX partials; strict allowlist sanitisation of all authored content; clickjacking prevention; Argon2 password hashing; brute-force lockout; automatic multi-site data isolation; SSRF-checked outbound webhooks with encrypted per-site secrets.
- **Built:** Security gates run on every commit — secret and private-key detection, a Python security linter, linting, formatting, type checking, and shell linting. CI additionally runs dependency and static-analysis scans plus Django's own deployment checks.
- **Built:** Production trusts a TLS-terminating reverse proxy's forwarded scheme, so the HTTPS redirect and HSTS behave correctly behind it — and refuses to start at all if `SECRET_KEY` or `WEBHOOK_ENCRYPTION_SALT` is missing.
- **Built:** Media in object storage is private by default, served via time-limited signed links rather than permanently public URLs. Error tracking is wired but inactive until an operator supplies credentials, and omits learner personal data by default.
- **Built:** Cohort progress reports are downloaded only through a permission-checked view, never a public media URL. Generating and downloading one both require the requesting staff user to be authorised to see that cohort; staff status alone is not enough.
- **Operational:** Report PDFs are written to a private storage location, separate from the buckets that hold course media and public branding. There is no fallback: an unconfigured location fails at startup, and a deploy pipeline running Django's deployment check catches a location that resolves to the wrong bucket before anything is written to it.
- **Report-only:** Content Security Policy runs in report-only mode — violations are reported, not blocked. HSTS is configurable but needs a staged rollout at deployment time; it is not meaningfully on by default.
- **Defect narrowed:** cohort and user detail pages in the educator interface are now permission-checked and deny by default. What remains is the Courses section — any authenticated user on a site can still read the full course list, hidden courses included, and any course detail page. Writes are gated and site isolation is unaffected. See [educator interface authorisation](#educator-interface-authorisation-narrowed-defect).
- **Not yet built:** 2FA/MFA, automated data-deletion and data-subject-rights tooling, a formal incident-response runbook, centralised logging and alerting, per-request access-controlled media downloads, a retention or expiry policy for generated report files, and an access log for report downloads. All are covered honestly below and tracked in the [roadmap](./roadmap.md).
- **Infrastructure:** The target deployment uses Vultr Johannesburg (ISO 27001:2022 certified). Vultr's certification covers physical and hypervisor layers; the operator owns everything above. See [shared responsibility](#infrastructure-and-shared-responsibility).

---

## Development-time Controls

**Pre-commit gates (built).** Every commit runs secret detection against a maintained baseline, private-key detection, a Python security linter at medium-and-above severity, linting and formatting, project-wide static type checking, shell linting, and file-hygiene checks including a 1 MB limit on added files. The authoritative list is `.pre-commit-config.yaml`.

**CI (built).** Pull requests run the test suite plus a security workflow covering static security analysis, dependency vulnerability auditing, and pattern-based scanning — and a job that runs Django's own `check --deploy` against the production settings, failing on warnings. This catches a weak or misconfigured production setting before it ships.

**GitHub platform features (operational).** Branch protection, Dependabot alerts, secret scanning, and CodeQL are configuration, not code. See [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §12 — not duplicated here.

---

## Runtime Application Security

### Educator Interface Authorisation (narrowed defect)

The educator interface grants educators permission on specific cohorts, or on a whole organisation. Its Cohorts and Learners listings and their detail pages are now permission-checked and **deny by default**: a visitor without the right grant gets the same not-found response as a record that does not exist, so cohort, learner, and organisation identifiers cannot be enumerated by guessing URLs.

**What remains unfixed.** The Courses section is unchanged. Any authenticated user on a site still sees every course on it, including ones authored as hidden, and course detail pages are still not permission-checked.

Three things bound the remaining impact, and none of them excuse it:

- **Reads only.** Create, rename, and delete actions do check the object-level permission, so this is not a route to modifying another educator's data.
- **Within a tenant.** Every query is still site-scoped, so the gap never crosses a site boundary. An organisation is a scoping layer inside that boundary, not a security boundary of its own — see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations).
- **Authenticated only.** An anonymous visitor cannot reach any of it.

Detail-view authorisation across the educator panel now denies by default: a section that has not been given a real permission check cannot serve detail pages at all unless it explicitly opts out with a declared reason, and an automated test asserts every opt-out is declared. The Courses gap is therefore a tracked exception rather than an invisible one. Full detail is in [educator interface](./educator-interface.md#access-control); the remaining fix is tracked in the [roadmap](./roadmap.md).

**CSRF protection (built).** Active on all state-changing requests. HTMX requests carry the CSRF token via a global attribute on the page body, so every HTMX partial request is covered without per-view work.

**Content sanitisation (built).** All authored Markdown is sanitised against a strict allowlist before rendering, using a Rust-based, memory-safe sanitiser. Only explicitly permitted content-widget tags and their declared attributes survive; all other HTML is stripped. This is the control that prevents stored XSS from authored content.

**Organisation logo upload validation (built).** Administrator-uploaded organisation logos are restricted to an allowlist of raster formats — PNG, JPEG, and WebP. The uploaded bytes are decoded and the real format asserted rather than the file extension trusted, so a disguised file is caught. SVG is deliberately excluded: it is XML rather than image data and can carry a script, a risk raster formats do not share. File-size and pixel-dimension limits apply, along with decompression-bomb protection, and the uploaded filename is never used to build the storage path. EXIF metadata is deliberately not stripped — the uploader is always an administrator and the asset is a corporate logo, not a personal photo, so the usual location-metadata concern does not apply. Note the scope: this validation covers organisation logos only. Course file assets, which are loaded from the content repository by an operator rather than uploaded through a browser, carry no equivalent check.

**Content Security Policy (report-only — not enforcing).** A policy is configured and violations are reported, but nothing is blocked. The policy permits same-origin sources for most directives, allows inline scripts and styles (currently required by the HTMX and Alpine.js usage in templates), and restricts framing to same-origin plus YouTube. Enforcing mode has not been enabled — doing so requires refactoring the inline script and style usage first. Tracked in the [roadmap](./roadmap.md).

**Clickjacking (built in FLS's reference production settings).** FLS's own production settings send `X-Frame-Options: DENY`, so pages cannot be framed by any site, including themselves. The shared base default is `SAMEORIGIN`, so that locally-served PDF previews can be framed in development; in production those files are served from object storage on a separate origin.

Note the seam: `DENY` lives in FLS's production settings module, not in the defaults a downstream project imports. Because FLS is [never deployed standalone](./deployment.md), the deployed artifact is a concrete project, and that project must carry the production value forward — inheriting the base settings alone leaves it on `SAMEORIGIN`. The same applies to the other production-only headers and cookie flags. Verify with Django's `check --deploy` against the concrete project's own settings.

**Password hashing and strength (built).** Argon2 is the primary hasher, with older algorithms retained only so existing passwords can be migrated on next login. Passwords must be at least 10 characters and are rejected if they are numeric-only, on the common-password list, or too similar to the user's own details.

**Brute-force lockout (built).** Five failed login attempts trigger a one-hour lockout, which resets on a successful login. The lockout applies independently by IP address and by username — either reaching the limit locks. This is configured in the shared base settings, so it is active in every environment, development included.

**What development does relax.** Two things, and only these two: the password validators are emptied, and the signup/login rate limits are switched off. Both are active in production. The brute-force lockout above is not among them.

**Static file serving (built).** Compressed, cache-busted static files are served directly from the application, removing a class of misconfigured-file-server vulnerabilities.

**HTTPS behind a proxy (built).** Production runs behind a TLS-terminating reverse proxy and is configured to trust its forwarded scheme, so the application correctly recognises proxied requests as secure. Without this the HTTPS redirect could loop and HSTS would never take effect, because every request would look like plain HTTP. This is safe only under the proxy-hardening preconditions in [`../deployment-security-checklist.md`](../deployment-security-checklist.md).

**HSTS (operational — staged rollout required).** HSTS duration, subdomain inclusion, and preloading are configurable by environment variable, but are not set to meaningful values by default. A staged rollout must be followed at deployment time to avoid locking users out during certificate changes; the procedure is in [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §4.

**Required configuration fails fast (built).** Production refuses to start — a visible crash-loop rather than a silent misconfiguration — if `SECRET_KEY` is missing or empty, or if `WEBHOOK_ENCRYPTION_SALT` is unset. The latter previously fell back to a hardcoded development value, silently weakening webhook secret encryption; that fallback still applies in development and test but can no longer reach production. Both checks catch absence only; a present-but-weak key is caught separately by the deployment checks that run in CI.

**Multi-site data isolation (built).** A single installation can serve multiple sites with fully isolated users, content, and settings. Isolation is automatic — every database query made while serving a request is scoped to the site matching that request's host. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md) for the canonical guarantee.

**Webhook controls (built).** Outbound webhooks are HMAC-signed or authenticated via templated headers, with per-site secrets encrypted at rest. In production, target URLs must be HTTPS and must not resolve to private, loopback, or link-local addresses. See [webhooks](./webhooks.md) for the full control set and the known DNS-rebinding limitation.

### Media File Access Control (built, with a stated limitation)

Course pages are access-controlled: a learner must be authorised before FLS renders a link to a course's files. Historically the files themselves — PDFs, videos, images — were not, because links pointed straight at storage.

When object storage is configured, this is closed at the storage layer: files are private by default and every link is a time-limited signed URL, so files are neither publicly discoverable nor permanently reachable from a leaked link.

**Limitation:** this is storage-layer privacy, not per-request access control. FLS does not re-check whether a specific learner is still authorised at the moment a file is fetched — a signed link works for anyone holding it until it expires. Routing downloads through the same access check used for course pages is **not yet built**; see the [roadmap](./roadmap.md). Without object storage, media is served from local disk with no signing at all — that mode is for development only. See [deployment](./deployment.md) for configuration.

### Cohort Report Access Control (built)

A [cohort progress report](./reports.md) holds real learner names, completion history, and individual quiz answers, and is treated accordingly.

Unlike ordinary media, a report is never reachable through a storage URL. Both generating a report and downloading one require the requesting user to be authorised to see that cohort — through a per-cohort permission grant, or a staff role on the cohort's organisation, the two routes described under [educator interface access control](./educator-interface.md#access-control). Being staff is not sufficient on its own: a staff user holding neither is denied on both the generate action and the download. Unlike media, that check runs on every request, not only at the storage layer.

Downloads are served as an attachment with caching suppressed, so a PII-bearing PDF is not left sitting in a shared proxy cache or a browser's disk cache.

**Not yet built:** report downloads are not audit-logged. Beyond who requested a report's generation, there is no record of who downloaded it or when.

---

## Data Handling

### Personal Data Collected

FLS stores, in its PostgreSQL database:

- Email address, first name, and last name.
- Hashed password (Argon2).
- Legal consent records — which document and version was accepted, when, from what IP address, and by what method.
- Learning activity — course progress, quiz answers, and scores.
- Webhook delivery logs, which may contain user data inside the delivered payload.

Outside the database, FLS stores generated [cohort progress reports](./reports.md) as PDF files. Each holds real learner names, completion history, and individual quiz scores and answers, and is not anonymised — the audience is internal staff, by design. See [generated cohort reports](#generated-cohort-reports).

No payment data, government ID, or biometric data is stored by FLS.

### Encryption in Transit

TLS terminates at the reverse proxy (or the CDN edge) using Let's Encrypt certificates, and the application can enforce an HTTPS redirect. Database connection encryption is configurable and defaults to *preferred* — encrypted if the server offers it, plaintext otherwise — which suits the shipped same-host containerised PostgreSQL, since it does not run TLS. Strict modes that require or verify TLS are intended for external or managed databases and should be used there. For the shipped topology the control that actually matters is not publishing the database port to the host; see [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §3.

### Encryption at Rest

**Webhook secrets only.** Per-site webhook secrets are encrypted with Fernet symmetric encryption, keyed from `SECRET_KEY` plus a required production salt. This is the only application-level encryption at rest in FLS.

**Database-level.** FLS implements no transparent database encryption. Encryption of the PostgreSQL data volume is provider- or host-dependent. Do not overstate this.

**Backups.** Encrypting database dumps before offsite sync is an operational requirement covered in [`../deployment-security-checklist.md`](../deployment-security-checklist.md) §6. No backup scripts ship with FLS.

### Error Tracking and Personal Data

FLS can report application errors to Sentry once an operator supplies credentials; until then it does nothing. Because FLS holds learner personal data, an error report can incidentally include it — the email of the learner who triggered the error, or the contents of the offending request.

This is **off by default**: attaching personal data to error reports requires a deliberate opt-in. Left at its default, reports omit it. Automated redaction before events leave the application is **not yet built**, so a deployment that opts in should treat Sentry as a place that data now lives, with no scrubbing safety net. See [deployment](./deployment.md) for configuration.

### Consent Audit Trail

Every acceptance of a legal document is recorded as an append-only record tied to the exact committed version of the document accepted, which makes it tamper-evident. This is the closest thing FLS has to a personal-data processing record. Owned by [authentication](./authentication.md) — see it for detail.

### Generated Cohort Reports

A [cohort progress report](./reports.md) is a generated PDF, one per cohort, holding real learner names, completion status, and the individual answers behind each quiz score. It is not anonymised — the audience is internal educators and staff, and that is a deliberate product decision. Who can reach one is covered under [cohort report access control](#cohort-report-access-control-built).

**Storage (operational).** Report files are written to a storage location configured separately from ordinary media, through the `REPORTS_STORAGE_ALIAS` setting. This used to fall back to default media storage when unconfigured, which could mean publicly served, with only a startup warning naming the gap. That fallback is gone. An unconfigured location now fails at startup instead of writing anywhere, and a deployment check fails a deploy pipeline whose reports location is not a bucket of its own — whether it collides with the general-purpose default bucket, or reached no bucket at all and fell back to the server's local disk. See [deployment](./deployment.md).

**Deletion (built).** Deleting a report removes its stored PDF, not only the database row, and the same holds when a cohort is deleted and takes its reports with it. Neither path leaves an orphaned PII-bearing file behind.

**Gap — no retention or expiry (not yet built).** A generated report is kept indefinitely until deleted by hand. This is a deferred decision, not a statement that reports should be kept forever. See [retention, deletion, and data-subject rights](#retention-deletion-and-data-subject-rights-not-yet-built) and the [roadmap](./roadmap.md).

### Incident Response (not yet built)

No incident-response runbook, breach-notification templates, or automated alerting for data events exist in the codebase. POPIA requires prompt notification to the Information Regulator following a breach. A written plan is an operator responsibility, not something FLS ships. See the [roadmap](./roadmap.md).

### Retention, Deletion, and Data-Subject Rights (not yet built)

There is no retention policy, scheduled deletion, subject-access-request tooling, right-to-erasure workflow, or portability export. Deleting user data is a manual database or admin operation (hard delete), and the admin does not restrict delete permissions on user records beyond standard Django permission checks. All of this is operator responsibility today. The same gap applies to generated cohort report files — see [generated cohort reports](#generated-cohort-reports). See the [roadmap](./roadmap.md).

---

## Infrastructure and Shared Responsibility

The target deployment runs on **Vultr Johannesburg** (ISO/IEC 27001:2022 certified). ISO 27001 operates on a shared-responsibility model. **Freedom LS itself is not certified under ISO 27001 or any other framework.**

**Vultr's certification covers** the physical data centre (access control, CCTV, environmental), hardware maintenance and disposal, the network backbone and hypervisor layer, and Vultr's own staff and operational procedures.

**The operator owns everything above that.** Current state of each area:

| Responsibility area | Status |
|---|---|
| OS hardening (SSH key-only, fail2ban, firewall, unattended updates, no root login) | Operational — documented in the checklist; not automated |
| TLS encryption and HTTPS redirect | Built — reverse proxy in the deployment architecture; requires correct configuration |
| Encrypted backups before offsite sync | Planned — strategy defined; no automation ships with FLS |
| Database SSL connections | Operational — connection configuration required; see above |
| Access control (MFA on infrastructure, least privilege) | Operational — checklist item; not automated |
| Centralised logging and failed-login alerting | Not yet built — no logging pipeline is configured by FLS |
| Backup and disaster recovery (schedule, tested restores, RTO/RPO) | Planned — restore testing and formal RTO/RPO not yet documented |
| Incident response plan | Not yet built — no runbook ships with FLS |
| Change management | Operational — the Git/PR workflow provides an audit trail of code and config changes |
| Vulnerability management | Operational — dependency scanning and static analysis run in CI; container image scanning and periodic penetration testing are not automated |
| ISMS documentation (policy, risk assessment, statement of applicability) | Not yet built — operator responsibility |

See [deployment](./deployment.md) for the full V1 architecture.

## POPIA Data Residency

South Africa's Protection of Personal Information Act does not impose a blanket data-residency requirement; cross-border transfers are permitted where adequate protection exists. Hosting on Vultr Johannesburg keeps personal data in South Africa, which simplifies compliance argumentation and aligns with the June 2024 National Policy on Data and Cloud. This is a **practical advantage, not a legal mandate** — unless FLS is deployed by a financial institution or government entity with sector-specific local-hosting obligations.

---

## References

- [`../deployment-security-checklist.md`](../deployment-security-checklist.md) — pre-deployment checklist covering server hardening, TLS, HSTS rollout, firewall rules, backup encryption, log management, monitoring, GitHub security features, and environment variables. Referenced throughout; not duplicated here.
- [Deployment](./deployment.md) — the V1 architecture.
