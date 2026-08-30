# Deployment

_Last updated: 2026-08-30_

## Summary

- The target production architecture is a single Vultr Johannesburg VPS running Docker Compose: a reverse proxy with automatic HTTPS, Gunicorn, Django 6, and containerised PostgreSQL.
- FLS is never deployed standalone — a production deployment is a **concrete project** built from the template repo, which owns the Compose and reverse-proxy scaffolding.
- The build step is built: the template repo ships CI that builds and pushes a per-commit, SHA-tagged image. VPS provisioning and the deploy step are **not yet built**.
- Backups are a defined strategy, not an automated system.
- Scale figures are estimates from typical Gunicorn configurations. They have **not** been load-tested.

## Target Architecture

The V1 production architecture, shipped by the template repo's scaffolding:

```
[Cloudflare CDN/WAF — free tier]        (planned)
    → [Vultr JNB VPS]
        → Caddy (reverse proxy + automatic HTTPS via Let's Encrypt)
        → Gunicorn + Django 6 (WSGI application)
        → PostgreSQL (containerised, named Docker volume)
```

- **Vultr Johannesburg VPS** — Regular Performance (4 vCPU, 8 GB RAM, 160 GB SSD, ~$40/month) or High Performance NVMe (~$48/month). Vultr holds ISO/IEC 27001:2022, SOC 2+ Type II, PCI-DSS, and ISO 27017/27018 certifications.
- **Caddy** — reverse proxy, acquiring and renewing TLS certificates automatically, eliminating manual certificate management.
- **Gunicorn** — recommended for a 4-core VPS: 5 workers, threaded worker class, 2 threads, preloaded app.
- **PostgreSQL** — containerised, data in a named Docker volume (never a bind mount).
- **Cloudflare free tier** — CDN, WAF, and DDoS mitigation in front of the VPS. Planned, not yet in place.

## Provisioning and CI/CD

**Built:** the template repo ships a GitHub Actions workflow that builds the application image and pushes a per-commit, SHA-tagged image to GHCR — that image is the deploy and rollback unit. This FLS repo itself ships only test and security CI; the build-and-push workflow lives in the template repo alongside the rest of the deploy scaffolding.

**Not yet built:** Ansible provisioning and OS hardening (SSH key-only access, firewall, fail2ban, unattended security updates, disabled root login), and the step that pulls a tagged image onto the VPS. No playbooks exist in this repository — this is specced work, not shipped work.

**Deferred:** Terraform, until Phase 2 brings multiple servers into play. Vultr has an official provider ready when needed.

The intent is that all infrastructure configuration is version-controlled, giving a git-auditable change history — every infrastructure change tracked via PR, consistent with ISO 27001 change-management expectations.

## Background Tasks

Django 6's built-in task framework is wired in. Production uses a durable, database-backed backend that stores tasks as rows in PostgreSQL — no Celery, Redis, or separate broker — and enqueued tasks are inspectable in the Django admin. Dev and test instead run tasks synchronously inside the request cycle, so the whole test suite runs without a worker process.

**`python manage.py db_worker` is a required production process.** An enqueued task sits in the database until a worker picks it up; without one running, background work — webhook delivery and [cohort report](./reports.md) generation — is accepted but never executes, and a requested report stays pending indefinitely. Run it as its own long-lived process or container.

Delivery is at-least-once, so a task can be redelivered. Task producers are idempotent under redelivery: a webhook is not sent twice for the same event and endpoint. See [webhooks](./webhooks.md).

The task-results table grows without bound if left alone, which eventually becomes a disk problem on a small VPS. Schedule the `prune_db_task_results` retention job rather than leaving it as a manual chore.

## Application-Level Capabilities

Built into the application and present regardless of deployment configuration:

- **Static files** — served compressed and cache-busted directly from the application. No separate static file server needed.
- **Object storage for media** — media is served from S3-compatible object storage (Cloudflare R2), split across three buckets by sensitivity: one for anonymously readable branding, one for course content, one for private data. Course content is private but holds no personal data and can be rebuilt from the content repository, so the private-data bucket is the one a leaked credential should reach the least. Each of the five named locations resolves independently, optionally with its own credentials, so an operator can scope a token to the private-data bucket alone. Locations share the three buckets above rather than each getting one of their own. Leaving one unset falls back to local filesystem storage, which the deployment check reports as an error — that fallback is a development convenience, not a way to run in production. Media is **private by default**, with time-limited signed links rather than permanently public URLs. See [security and data handling](./security-and-data-handling.md).
- **Health probes** — `/health/liveness/` and `/health/readiness/`, available with no configuration. Liveness only confirms the process can serve a request and checks no dependency, so a transient database problem cannot trigger a restart loop. Readiness checks database connectivity and returns a non-200 when it is unreachable, making it the probe that container health checks and load balancers should poll to gate traffic; a setting lets an operator add further checks. Applied migrations are deliberately excluded — that belongs in a deploy-time smoke test, not a polled probe. Health paths are exempt from the HTTPS redirect, so a plain-HTTP internal probe behind a TLS-terminating proxy is served rather than mistaken for unhealthy.
- **Error tracking (Sentry)** — configured by supplying a DSN, and a complete no-op until one is set, so development and unconfigured deployments send nothing. Once configured it tags events with the deployment's environment and release. Attaching learner personal data is an explicit opt-in, off by default. A staff-only endpoint lets an operator confirm a running deployment is actually reaching Sentry. If a DSN is set but the release identifier is left blank, a non-blocking deployment warning surfaces at boot and in CI, so untagged events are caught rather than quietly degrading release tracking.
- **Analytics (PostHog)** — a client-side snippet configured by project token and region host. With no token set the snippet does not render, so development deployments send nothing.
- **Environment-variable configuration** — all secrets and deployment-specific settings are supplied by environment variable, with sensible in-repo defaults where one makes sense, so a deployment configures these services without copy-pasting settings code. No credentials are hardcoded. Database connection SSL mode is configurable and defaults to *preferred*, which suits the shipped same-host containerised PostgreSQL; stricter modes are for external or managed databases. Persistent database connections are enabled with health checking, so a connection left stale by a database restart is recycled rather than failing the next request. A missing `SECRET_KEY` — or a missing `WEBHOOK_ENCRYPTION_SALT` — fails the application at startup as a visible crash-loop rather than booting into a silently broken state. See [security and data handling](./security-and-data-handling.md).
- **HTTPS detection behind a reverse proxy** — production trusts the proxy's forwarded scheme, so requests that reached the proxy over HTTPS are correctly recognised as secure. This is what makes the HTTPS redirect and HSTS work behind a proxy instead of looping. See [security and data handling](./security-and-data-handling.md) for the trust preconditions.
- **Shared production defaults** — the production settings FLS recommends are increasingly delivered as values a downstream project imports directly from FLS rather than copies. A fix to one of these lands once in FLS and reaches downstream projects on their next routine version update, instead of needing to be re-applied project by project.
- **Tailwind build at image-build time** — `npm run tailwind_build` must run during image construction, and `FLS_THEME` must be set at build time. It cannot be changed at runtime without a rebuild. The [cohort report](./reports.md) takes its colours from this compiled stylesheet rather than carrying any of its own, so a deployment that ships without running the build gets an explicit failure when generating a report rather than a colourless PDF.

**Logging.** The application's logging helper defaults to stdout/stderr only, which suits container log collection. This repo's own production settings currently opt out of that default and additionally write rotating log files to disk — an in-code comment marks that as temporary, pending container-level log size caps. The template repo's reference configuration pairs stdout logging with per-service capped container logging, so the disk-fill risk is handled at the log-driver level rather than relocated.

## Backups

**Strategy (partially automated).** `pg_dump` on a cron schedule, with dumps encrypted and synced offsite to Backblaze B2 (~$0.005/GB).

**Current state.** The strategy is defined; automated scheduling and tested restore procedures are not. No backup scripts ship with FLS. Until automated runs and restore drills are confirmed, treat backup as a documented strategy, not an operational system. RTO and RPO have not been formally defined or tested.

## Scale Estimates

Estimates from the Gunicorn configuration above and typical Django/PostgreSQL characteristics. **Not validated by load testing.**

| Phase | Estimated capacity | Rough cost |
|---|---|---|
| Phase 1 — single VPS | ~50–200 concurrent users, ~1,000 registered learners | ~$45–48/month |
| Phase 2 — separate DB | ~500+ concurrent, ~5,000–10,000 learners | ~$60–108/month |
| Phase 3 — horizontal scaling | ~1,000+ concurrent, multiple tenants | ~$150–250/month |

Moving to Phase 2 is triggered by monitoring data — CPU consistently above 70% at peak, or database size past 50 GB — not by a calendar date.

## Operator Responsibilities

Vultr's ISO 27001:2022 certification covers the physical data centre, hardware, network backbone, hypervisor, and Vultr's own procedures. It does not cover the OS or the application. The operator owns:

- OS hardening — planned via Ansible, not yet built.
- PDF rendering system packages — [cohort reports](./reports.md) render using WeasyPrint, which needs Pango, cairo, gdk-pixbuf, and HarfBuzz present at runtime, so a production image must install them. The report bundles its own fonts, so rendering does not depend on what the base image carries. FLS does not load WeasyPrint at startup: a deployment missing those libraries still boots, and report generation fails at generation time with a clear error rather than a crash loop.
- TLS encryption — terminates at the reverse proxy in the template-repo stack.
- Encrypted backups — not yet automated.
- Database SSL configuration.
- Access control — deploy key, limited sudo.
- Logging and monitoring — Sentry error tracking is built in and activates once a DSN is configured (a free-tier account suffices). External uptime and availability monitoring is not set up and no monitoring tool is wired into the application or infrastructure.
- Incident response — a documented plan is required and not yet written.
- Change management — the git/PR workflow provides this.
- Vulnerability management — dependency updates via Dependabot, plus CI security scanning and Django deployment checks. Container image scanning is not set up.
- ISMS documentation — required for certification; not yet produced.

The full breakdown is in [security and data handling](./security-and-data-handling.md).

## POPIA Data Residency

Hosting on Vultr Johannesburg keeps data in South Africa. POPIA imposes no blanket data-residency requirement, so this is a practical advantage for compliance argumentation, not a legal mandate — though it does simplify the cross-border transfer analysis and aligns with the June 2024 National Policy on Data and Cloud.

Sector-specific requirements (financial institutions, government entities) may impose stricter local-hosting obligations; verify with legal counsel for those deployments.

## Deploying a Concrete Project

FLS is never deployed standalone. A production deployment is a **concrete project** — a downstream repository that installs `freedom_ls` as a git submodule and supplies its own settings, content, and deployment scaffolding.

The starting point is the template repo, `git@github.com:preludetech/freedom-ls-concrete-template.git`, a GitHub template repository you clone to begin a new project. It carries the Caddy and Docker Compose scaffolding and its own README for the step-by-step.

Before deploying, run the FLS conformance suite against the concrete project's own settings as a pre-launch check. Many FLS wiring mistakes are also reported when the application starts, rather than surfacing later as an error for a learner. See [configuration and extension](./configuration-and-extension.md) for both.
