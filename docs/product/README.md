# Freedom LS — Product Documentation

_Last updated: 2026-07-01_

## Security Posture

Freedom LS applies security hardening at multiple layers: Argon2 password hashing, django-axes brute-force lockout (5 failures → 1-hour cooldown), SSRF-protected outbound webhooks with Fernet-encrypted per-site secrets, automatic site isolation on every ORM query via `SiteAwareManager`, and pre-commit security gates (detect-secrets, detect-private-key, bandit, ruff, mypy) that run on every commit. Content Security Policy is currently configured in report-only mode, not enforcing. There is no 2FA/MFA at this time; see the [roadmap](./roadmap.md).

## Infrastructure and Certification

The target deployment runs on **Vultr Johannesburg**, which holds **ISO/IEC 27001:2022** certification (plus SOC 2+ Type II, PCI-DSS, ISO 27017/27018). The Johannesburg point of presence keeps data in South Africa, which simplifies POPIA compliance argumentation — a practical advantage, not a legal mandate. **Freedom LS itself is not ISO 27001 certified** (or certified under any other framework). ISO 27001 operates on a shared-responsibility model: Vultr's certification covers physical data centre, hardware, network backbone, and hypervisor; the FLS operator owns OS hardening, access control, TLS configuration, encrypted backups, logging, incident response, and ISMS documentation. Details are in [security and data handling](./security-and-data-handling.md) and [deployment](./deployment.md).

---

## Product Features

| Doc | Description |
|---|---|
| [Content Editing Workflow](./content-editing-workflow.md) | Git-backed Markdown/YAML authoring with Pydantic validation, idempotent upsert by UUID, a four-stage render pipeline (python-markdown → nh3 → cotton → Django), and a tamper-evident legal-document consent audit trail. |
| [Authentication](./authentication.md) | Email-only login with mandatory verification, per-site signup policy, Argon2 hashing, django-axes lockout, email-enumeration prevention, append-only `LegalConsent` records, and a separate API-client token system. |
| [Learner Experience](./learner-experience.md) | Personalised dashboard, course detail with outcomes and difficulty, self-registration, coming-soon/hidden course visibility with an express-interest waitlist, sequential item unlock with resume, multi-page forms, quiz feedback, and hard/soft deadline enforcement. |
| [Learner Tracking](./learner-tracking.md) | Per-item completion records (`TopicProgress`, `FormProgress`, `QuestionAnswer`), course progress percentage with auto-recalculation, and a resume pointer; no time-on-task or score export. |
| [Educator Interface](./educator-interface.md) | Single-page HTMX panel with cohort, user, and course views; course-progress matrix (completion, quiz scores, deadlines); course visibility and coming-soon interest counts with drill-down to interested students; access restricted to permissioned cohorts via django-guardian. Membership and deadline management are admin-only. |
| [Admin Interface](./admin-interface.md) | Django admin enhanced with Unfold; configurable admin URL; django-guardian object-level permissions for cohort grants; read-only `LegalConsent`; webhook test-send action. |
| [Webhooks](./webhooks.md) | Outbound events (`user.registered`, `course.completed`, `course.registered`) with HMAC-SHA256 signing, Fernet-encrypted per-site secrets, Jinja2 body/header templates, SSRF protection, retry with exponential back-off, and circuit breaker. |

## Security & Data

| Doc | Description |
|---|---|
| [Multi-Tenancy and Isolation](./multi-tenancy-and-isolation.md) | One installation, multiple sites: `SiteAwareModel` and `SiteAwareManager` automatically scope every ORM query to the current site; users, content, progress, cohorts, webhooks, and secrets are fully isolated between tenants. |
| [Security and Data Handling](./security-and-data-handling.md) | Cross-cutting reviewer doc covering dev-time controls, runtime application security, personal data collected, encryption in transit and at rest, incident response and data-deletion gaps, and the ISO 27001 shared-responsibility split. |

## Configuration

| Doc | Description |
|---|---|
| [Configuration and Extension](./configuration-and-extension.md) | Branding settings, three-tier theming (CSS tokens → cotton slots → whole-file shadowing), two bundled themes, pluggable icon set, and a host-project extension model with full template and component override capability. |

## Deployment

| Doc | Description |
|---|---|
| [Deployment](./deployment.md) | V1 architecture: Vultr Johannesburg VPS, Docker Compose (Caddy + Gunicorn + PostgreSQL), Cloudflare free tier, Ansible provisioning, GitHub Actions CI/CD, `django-tasks` DatabaseBackend (no Celery/Redis at launch), and `pg_dump` + Backblaze B2 backup strategy (partially automated). |

## Roadmap

| Doc | Description |
|---|---|
| [Roadmap](./roadmap.md) | Features not yet complete: 2FA/MFA (not built), RBAC role system (infrastructure exists, not wired into access control), xAPI (placeholder stub only), `SiteGroup` (commented out), and educator-interface management gaps. |
