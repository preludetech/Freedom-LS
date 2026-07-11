# Deployment

_Last updated: 2026-07-11_

## Summary

- The target production architecture is a single Vultr Johannesburg VPS running Docker Compose: Caddy (reverse proxy + automatic HTTPS) + Gunicorn + Django 6 + containerised PostgreSQL.
- Vultr's Johannesburg data centre is ISO/IEC 27001:2022 certified and provides a South African point of presence — a practical advantage for POPIA data-residency arguments, not a legal mandate.
- Infrastructure is provisioned and hardened via Ansible; CI/CD uses GitHub Actions → GHCR → SSH pull to the VPS.
- Backup strategy is `pg_dump` cron + encrypted offsite sync to Backblaze B2. Parts of this strategy are not yet automated — see below.
- Scale estimates for Phase 1 are approximately 50–200 concurrent users and up to ~1,000 registered students. These are estimates based on typical Gunicorn configurations; they have not been load-tested.

## Target Architecture

The V1 production architecture as documented in the deployment playbook:

```
[Cloudflare CDN/WAF — free tier]
    → [Vultr JNB VPS]
        → Caddy (reverse proxy + automatic HTTPS via Let's Encrypt)
        → Gunicorn + Django 6 (WSGI application)
        → PostgreSQL (containerised, named Docker volume)
```

**Components:**

- **Vultr Johannesburg VPS** — Regular Performance (4 vCPU, 8 GB RAM, 160 GB SSD, ~$40/month) or High Performance NVMe (~$48/month). Vultr holds ISO/IEC 27001:2022, SOC 2+ Type II, PCI-DSS, and ISO 27017/27018 certifications.
- **Caddy** — reverse proxy handling TLS certificate acquisition and renewal automatically via Let's Encrypt. Replaces nginx for this role; eliminates manual Certbot management.
- **Gunicorn** — WSGI server running the Django application. Recommended configuration for a 4-core VPS: 5 workers (`gthread` class, 2 threads, `preload_app=True`).
- **PostgreSQL** — containerised in Docker Compose, data persisted in a named Docker volume (never a bind mount).
- **Cloudflare free tier** — CDN, WAF, and DDoS mitigation in front of the VPS.

## Provisioning and Configuration Management

- **Ansible** is used to provision the VPS: OS hardening (SSH key-only access, UFW firewall, fail2ban, unattended security updates, disabled root login), Docker installation, and initial service setup.
- **Terraform** is deferred to Phase 2 when managing multiple servers. Vultr has an official Terraform provider ready when needed.
- All infrastructure configuration is version-controlled. The Ansible + Docker Compose approach provides a git-auditable change history — every infrastructure change is tracked via PR, consistent with ISO 27001 change-management requirements.

## CI/CD Pipeline

GitHub Actions → GHCR → SSH pull:

1. Push to `main` triggers the workflow.
2. Django tests run against a PostgreSQL service container in CI.
3. A multi-stage Docker image is built and pushed to GitHub Container Registry (GHCR).
4. The workflow SSH-connects to the VPS and runs `docker compose pull && docker compose up -d --no-deps web worker`.

A dedicated ed25519 SSH deploy key (stored in GitHub Secrets) is used for the deploy step. The VPS has a `deploy` user with limited sudo permissions. Secrets are never committed to git; `.env` files on the VPS are managed via Ansible Vault.

## Background Tasks

Django 6's built-in task framework (`django-tasks` with `DatabaseBackend`) is used for background work. PostgreSQL serves as the task broker — no Celery, Redis, or separate message broker is required at launch. The worker runs as a separate container: `python manage.py db_worker`.

## Application-Level Facts

The following are built into the application code and are always present regardless of deployment configuration:

- **Whitenoise** — serves compressed, cache-busted static files directly from Django/Gunicorn. No separate static file server is required.
- **S3-compatible media storage (Cloudflare R2)** — media files are served from S3-compatible object storage (Cloudflare R2), enabled by setting the storage bucket environment variable; without it, media falls back to local filesystem storage. Media is **private by default** — links are time-limited signed URLs rather than permanently public, so application-gated course files aren't exposed to anyone who obtains a link. See [security and data handling](./security-and-data-handling.md) for the rationale behind private-by-default media.
- **`/health/` endpoint** — used by Docker health checks and uptime monitoring tools.
- **Sentry error tracking** — wired into the application and configured via the Sentry DSN environment variable. It is a no-op until that variable is supplied, so local/development and unconfigured deployments send nothing. Once configured it reports the deployment's environment name, release identifier, and a low default trace-sampling rate for cost control; attaching learner personal data to error reports is an explicit opt-in, off by default (see [security and data handling](./security-and-data-handling.md)). A staff-only verification endpoint lets an operator confirm a running deployment is actually reaching Sentry; it is inaccessible to anonymous or non-staff users.
- **PostHog analytics** — a client-side analytics snippet is wired into the application and configured via environment variables (a project token and a region host, defaulting to the US region and overridable for the EU). If the project token is unset, the snippet does not render, so local/development deployments send no analytics by default.
- **Environment-variable configuration** — all secrets and deployment-specific settings (SECRET_KEY, HOST_DOMAIN, DB credentials, email credentials, DJANGO_ADMIN_URL, LEGAL_DOCS_MANIFEST_PATH, object storage/R2, Sentry, PostHog) are provided via environment variables, each with a sensible in-repo default where one makes sense, so a deployment configures these services without copy-pasting settings code. No credentials are hardcoded.
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

- OS hardening (handled by Ansible)
- TLS encryption (handled by Caddy)
- Encrypted backups (GPG before B2 sync — not yet automated)
- PostgreSQL SSL connections
- Access control (deploy key, limited sudo)
- Logging and monitoring (Uptime Kuma; Sentry error tracking is built in and activates once a DSN is configured — a free-tier Sentry account is sufficient)
- Incident response (documented plan required; not yet written)
- Change management (git/PR workflow provides this)
- Vulnerability management (Trivy for container image scanning, Dependabot for Python dependencies)
- ISMS documentation (required for ISO 27001 certification; not yet produced)

For the full shared-responsibility breakdown and security hardening details, see [security and data handling](./security-and-data-handling.md).

## POPIA Data Residency

Hosting on Vultr Johannesburg keeps data in South Africa. South Africa's Protection of Personal Information Act (POPIA) does not impose a blanket data-residency requirement, so this is a practical advantage for compliance argumentation, not a legal mandate. It does simplify the cross-border transfer analysis and aligns with the June 2024 National Policy on Data and Cloud.

Sector-specific requirements (financial institutions, government entities) may impose stricter local hosting obligations — verify with legal counsel for those deployments.

## Superseded Deployment Guides

The following guides in this repository document earlier deployment approaches that are **superseded** by the Ansible + Docker Compose + Caddy architecture described in this document and in the deployment playbook. They are retained for historical reference but should not be followed for new deployments:

- [DOCKER_DEPLOY.md](../how%20tos/DOCKER_DEPLOY.md) — Docker Compose deployment using nginx as the reverse proxy. **Superseded.** The current architecture uses Caddy.
