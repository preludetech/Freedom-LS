# Deployment

_Last updated: 2026-07-17_

## Summary

- The target production architecture is a single Vultr Johannesburg VPS running Docker Compose: a reverse proxy with automatic HTTPS + Gunicorn + Django 6 + containerised PostgreSQL. Caddy is the planned reverse proxy; the Docker Compose configuration currently in this repository uses nginx (see [Target Architecture](#target-architecture)).
- Vultr's Johannesburg data centre is ISO/IEC 27001:2022 certified and provides a South African point of presence — a practical advantage for POPIA data-residency arguments, not a legal mandate.
- The planned provisioning and deploy approach is Ansible for VPS hardening and a GitHub Actions → GHCR → SSH-pull pipeline. Neither is built yet — no Ansible playbooks or deploy workflow exist in this repository (CI itself does run: tests and security scanning).
- Backup strategy is `pg_dump` cron + encrypted offsite sync to Backblaze B2. Parts of this strategy are not yet automated — see below.
- Scale estimates for Phase 1 are approximately 50–200 concurrent users and up to ~1,000 registered students. These are estimates based on typical Gunicorn configurations; they have not been load-tested.

## Target Architecture

The V1 production architecture as documented in the deployment playbook. This is the **planned target**, not the current state: the Docker Compose configuration in this repository today uses nginx as the reverse proxy, and the Cloudflare/Caddy front described below is not yet built.

```
[Cloudflare CDN/WAF — free tier]        (planned)
    → [Vultr JNB VPS]
        → Caddy (reverse proxy + automatic HTTPS via Let's Encrypt)   (planned; nginx today)
        → Gunicorn + Django 6 (WSGI application)
        → PostgreSQL (containerised, named Docker volume)
```

**Components:**

- **Vultr Johannesburg VPS** — Regular Performance (4 vCPU, 8 GB RAM, 160 GB SSD, ~$40/month) or High Performance NVMe (~$48/month). Vultr holds ISO/IEC 27001:2022, SOC 2+ Type II, PCI-DSS, and ISO 27017/27018 certifications.
- **Caddy** (planned) — the intended reverse proxy, handling TLS certificate acquisition and renewal automatically via Let's Encrypt to eliminate manual Certbot management. The Compose configuration in this repository currently uses **nginx** for this role; the switch to Caddy is planned deployment work and is not built yet.
- **Gunicorn** — WSGI server running the Django application. Recommended configuration for a 4-core VPS: 5 workers (`gthread` class, 2 threads, `preload_app=True`).
- **PostgreSQL** — containerised in Docker Compose, data persisted in a named Docker volume (never a bind mount).
- **Cloudflare free tier** — CDN, WAF, and DDoS mitigation in front of the VPS.

## Provisioning and Configuration Management

- **Ansible** is the planned provisioning approach for the VPS: OS hardening (SSH key-only access, UFW firewall, fail2ban, unattended security updates, disabled root login), Docker installation, and initial service setup. No Ansible playbooks exist in this repository yet — this is specced deployment work, not built.
- **Terraform** is deferred to Phase 2 when managing multiple servers. Vultr has an official Terraform provider ready when needed.
- The intent is for all infrastructure configuration to be version-controlled, so the Ansible + Docker Compose approach gives a git-auditable change history — every infrastructure change tracked via PR, consistent with ISO 27001 change-management requirements.

## CI/CD Pipeline

**What exists today:** GitHub Actions runs CI on push — Django tests against a PostgreSQL service container (`tests.yml`) and security scanning (`security.yml`). There is no image-build-and-deploy workflow yet.

**Planned deploy pipeline** (GitHub Actions → GHCR → SSH pull, not yet built):

1. Push to `main` triggers the workflow.
2. Django tests run against a PostgreSQL service container in CI.
3. A multi-stage Docker image is built and pushed to GitHub Container Registry (GHCR).
4. The workflow SSH-connects to the VPS and runs `docker compose pull && docker compose up -d --no-deps web`.

The planned pipeline uses a dedicated ed25519 SSH deploy key (stored in GitHub Secrets) for the deploy step, a `deploy` user with limited sudo permissions on the VPS, and Ansible Vault for the VPS `.env` files. Secrets are never committed to git.

## Background Tasks

Django 6's built-in task framework (`django.tasks`) is wired into the application. It is currently configured with `ImmediateBackend`, which runs tasks synchronously in the request/response cycle. This is now the deliberate, documented default shipped in production settings, not a placeholder awaiting a decision.

The planned production setup uses a durable, database-backed backend, with PostgreSQL as the task broker (no Celery, Redis, or separate message broker) and the worker running as a separate container (`python manage.py db_worker`). Neither the durable backend nor the worker container is configured yet.

## Application-Level Facts

The following are built into the application code and are always present regardless of deployment configuration:

- **Whitenoise** — serves compressed, cache-busted static files directly from Django/Gunicorn. No separate static file server is required.
- **S3-compatible media storage (Cloudflare R2)** — media files are served from S3-compatible object storage (Cloudflare R2), enabled by setting the storage bucket environment variable; without it, media falls back to local filesystem storage. Media is **private by default** — links are time-limited signed URLs rather than permanently public, so application-gated course files aren't exposed to anyone who obtains a link. See [security and data handling](./security-and-data-handling.md) for the rationale behind private-by-default media.
- **`/health/` endpoint** — used by Docker health checks and uptime monitoring tools.
- **Sentry error tracking** — wired into the application and configured via the Sentry DSN environment variable. It is a no-op until that variable is supplied, so local/development and unconfigured deployments send nothing. Once configured it reports the deployment's environment name, release identifier, and a low default trace-sampling rate for cost control; attaching learner personal data to error reports is an explicit opt-in, off by default (see [security and data handling](./security-and-data-handling.md)). A staff-only verification endpoint lets an operator confirm a running deployment is actually reaching Sentry; it is inaccessible to anonymous or non-staff users.
- **PostHog analytics** — a client-side analytics snippet is wired into the application and configured via environment variables (a project token and a region host, defaulting to the US region and overridable for the EU). If the project token is unset, the snippet does not render, so local/development deployments send no analytics by default.
- **Environment-variable configuration** — all secrets and deployment-specific settings (SECRET_KEY, HOST_DOMAIN, DB credentials, `DB_SSLMODE`, `DB_CONN_MAX_AGE`, email credentials, DJANGO_ADMIN_URL, object storage/R2, Sentry, PostHog) are provided via environment variables, each with a sensible in-repo default where one makes sense, so a deployment configures these services without copy-pasting settings code. No credentials are hardcoded. `DB_SSLMODE` controls the database connection's SSL mode; it defaults to disabled for the shipped same-host containerised PostgreSQL (which has no TLS), with stricter modes reserved for external or managed databases — see [security and data handling](./security-and-data-handling.md) for the security posture. `DB_CONN_MAX_AGE` enables persistent database connections (recommended 60–300 seconds); connection health checks are on, so a stale connection left over from a database restart is recycled automatically rather than causing the next request to fail. A missing or empty `SECRET_KEY` fails the application at startup — a visible crash-loop — rather than booting successfully and only erroring on the first request that needs it.
- **HTTPS detection behind a reverse proxy** — FLS's production settings trust the reverse proxy's forwarded HTTPS scheme, so when deployed behind a TLS-terminating reverse proxy the application correctly detects that an incoming request is secure. This is what makes the existing HTTPS redirect and HSTS settings behave correctly behind the proxy, rather than risking a redirect loop. See [security and data handling](./security-and-data-handling.md) for the trust preconditions this relies on.
- **Container-friendly logging (capability; not yet the default in this repo)** — FLS's logging configuration is able to emit logs to stdout/stderr only, which is friendlier to container-based log collection than writing to files on disk. The reference production configuration shipped in this repository does not yet use that stdout-only mode: it still writes rotating log files under `logs/`, and the existing `logs/` bind mount is unchanged. Switching this repo's reference configuration to stdout-only is deferred until container-level log-size caps are added in later deployment work, so that moving to stdout doesn't just relocate the disk-fill risk onto uncapped container logs.
- **Shared production-settings defaults, propagated by version bump** — the production-settings defaults FLS recommends (including the items above, such as the proxy HTTPS detection, the database connection options, and the required-`SECRET_KEY` check) are increasingly delivered as values a downstream project imports directly from FLS, rather than settings each downstream project has to copy and hand-edit into its own configuration. This means a future fix to one of these shared defaults lands once in FLS and reaches a downstream project on its next routine version update, instead of needing to be found and re-applied project by project.
- **Tailwind build required at image-build time** — `npm run tailwind_build` must run during Docker image construction. `FLS_THEME` must be set at build time; it cannot be changed at runtime without a rebuild.

## Backups

**Strategy (partially automated):** `pg_dump` runs on a cron schedule to produce database dumps. Dumps are encrypted and synced offsite to Backblaze B2 (approximately $0.005/GB).

**Current state:** The backup strategy is defined. Automated scheduling and tested restore procedures are not yet fully implemented. Until automated backup runs and restore drills are confirmed, treat backup as a documented strategy, not a fully operational automated system.

A recovery time objective (RTO) and recovery point objective (RPO) have not been formally defined or tested.

## Scale Estimates

These are estimates based on the Gunicorn configuration described above and typical Django/PostgreSQL performance characteristics. They have **not been validated by load testing**.

| Phase | Estimated capacity | Rough cost |
|---|---|---|
| Phase 1 — single VPS | ~50–200 concurrent users, ~1,000 registered students | ~$45–48/month |
| Phase 2 — separate DB | ~500+ concurrent, ~5,000–10,000 students | ~$60–108/month |
| Phase 3 — horizontal scaling | ~1,000+ concurrent, multiple tenants | ~$150–250/month |

Scaling to Phase 2 is triggered by monitoring data (CPU consistently above 70% at peak, or DB data exceeding 50 GB), not by a fixed calendar date.

## ISO 27001 Shared Responsibility

Vultr's ISO 27001:2022 certification covers the physical data centre, hardware, network backbone, hypervisor, and Vultr's own operational procedures. It does not cover the application or OS layer.

The FLS operator (you) owns:

- OS hardening (planned via Ansible)
- TLS encryption (planned via Caddy; the current Compose config terminates TLS at nginx)
- Encrypted backups (GPG before B2 sync — not yet automated)
- PostgreSQL SSL connections
- Access control (deploy key, limited sudo)
- Logging and monitoring (Sentry error tracking is built in and activates once a DSN is configured — a free-tier Sentry account is sufficient. External uptime/availability monitoring is an operator responsibility and is not yet set up; no monitoring tool is wired into the application or infrastructure.)
- Incident response (documented plan required; not yet written)
- Change management (git/PR workflow provides this)
- Vulnerability management (Dependabot for dependency updates via `.github/dependabot.yml`, plus CI security scanning with Bandit, pip-audit, and Semgrep in `.github/workflows/security.yml`). Container image scanning is not yet set up.
- ISMS documentation (required for ISO 27001 certification; not yet produced)

For the full shared-responsibility breakdown and security hardening details, see [security and data handling](./security-and-data-handling.md).

## POPIA Data Residency

Hosting on Vultr Johannesburg keeps data in South Africa. South Africa's Protection of Personal Information Act (POPIA) does not impose a blanket data-residency requirement, so this is a practical advantage for compliance argumentation, not a legal mandate. It does simplify the cross-border transfer analysis and aligns with the June 2024 National Policy on Data and Cloud.

Sector-specific requirements (financial institutions, government entities) may impose stricter local hosting obligations — verify with legal counsel for those deployments.

## Deployment Guides

The Ansible + Docker Compose + Caddy architecture described in this document (and in the deployment playbook) is the **planned target**. It is not fully built — the Caddy/Ansible/CI-deploy pieces are specced deployment work that has not shipped.

- [DOCKER_DEPLOY.md](../how%20tos/DOCKER_DEPLOY.md) — Docker Compose deployment using nginx as the reverse proxy. This matches the Compose configuration currently in the repository. It will be superseded once the Caddy-based target architecture is built; until then it describes the working setup.
