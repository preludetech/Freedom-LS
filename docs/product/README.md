# Freedom LS — Product Documentation

_Last updated: 2026-08-05_

High-level product documentation for evaluators, operators, and downstream integrators: what Freedom LS does and what can be configured. It is not developer or API reference.

Each document labels its claims by actual state — built, operational (needs deployment configuration), or not yet built. Anything incomplete is collected in the [roadmap](./roadmap.md).

**Three things worth knowing up front:**

- **There is an open authorisation defect.** The educator interface does not permission-check reads: any authenticated user on a site can read any cohort's progress data, any user's detail page, and the full course list, by URL. Writes are gated and site isolation is unaffected. Not fixed. See [educator interface](./educator-interface.md#access-control).
- **FLS is not certified** under ISO 27001 or any other framework. The target host (Vultr Johannesburg) is ISO/IEC 27001:2022 certified, which covers the physical and hypervisor layers only — the operator owns everything above. See [security and data handling](./security-and-data-handling.md).
- **FLS is never deployed standalone.** A production deployment is a downstream project that installs FLS as a submodule. See [deployment](./deployment.md).

## Product Features

| Doc | Description |
|---|---|
| [Content Editing Workflow](./content-editing-workflow.md) | Git-backed Markdown/YAML authoring, validated and loaded by a CLI command; a sanitising render pipeline; content widgets; and version-tracked legal documents. No browser-based editor. |
| [Authentication](./authentication.md) | Email-only login with mandatory verification, per-site signup policy with optional extra registration forms, hardened password and lockout policy, and an append-only legal-consent audit trail. No MFA. |
| [Learner Experience](./learner-experience.md) | Public catalogue and course pages, personalised dashboard, self-enrolment or application, coming-soon and hidden course visibility with an express-interest waitlist, sequential unlock with resume, multi-page forms, quiz feedback, and deadlines. |
| [Learner Tracking](./learner-tracking.md) | Per-item completion, quiz attempts and scores, course progress percentage, and a resume pointer. No time-on-task and no score export. |
| [Educator Interface](./educator-interface.md) | Single-page panel with cohort, user, and course views, plus a course-progress matrix. Read and monitoring only — and with a known authorisation gap: reads are not permission-checked. |
| [Admin Interface](./admin-interface.md) | Django admin enhanced with Unfold, a configurable admin path, per-cohort educator permission grants, read-only consent records, and a webhook test-send action. |
| [Webhooks](./webhooks.md) | Outbound events for registration, course registration, and course completion, with HMAC signing, encrypted per-site secrets, templated payloads, SSRF protection, retries, and a circuit breaker. |

## Security & Data

| Doc | Description |
|---|---|
| [Multi-Tenancy and Isolation](./multi-tenancy-and-isolation.md) | One installation, many sites. Every request's database queries are scoped automatically to the site matching its host; users, content, progress, cohorts, and webhooks are isolated between tenants. |
| [Security and Data Handling](./security-and-data-handling.md) | The reviewer document: development and runtime controls, personal data collected, encryption in transit and at rest, the gaps in incident response and data deletion, and the ISO 27001 shared-responsibility split. |

## Configuration and Deployment

| Doc | Description |
|---|---|
| [Configuration and Extension](./configuration-and-extension.md) | Branding, three-tier theming, two bundled themes and four icon sets, pluggable course-access backends, the host-project override model, and an opt-in conformance suite for verifying a downstream's wiring. |
| [Deployment](./deployment.md) | V1 architecture — Vultr Johannesburg VPS, Docker Compose with Caddy, Gunicorn, and PostgreSQL. Database-backed background tasks requiring a worker process, object storage for media, health probes, and a partially automated backup strategy. |

## Roadmap

| Doc | Description |
|---|---|
| [Roadmap](./roadmap.md) | Everything not yet complete: the educator interface authorisation gap, application review, notifications, MFA, RBAC wiring, per-request media access control, data-retention tooling, xAPI, and enforcing CSP. |
