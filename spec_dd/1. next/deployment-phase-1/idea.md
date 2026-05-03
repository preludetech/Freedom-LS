# Deployment — Phase 1

## What

Deploy FreedomLS to staging + production, **on the same VPS**, with as much of the lifecycle automated as possible. Single Vultr Johannesburg High Performance instance (~$48/mo): handles 50–200 concurrent users, ~1,000 registered students, 6–12 months of bootstrapped runway.

This phase is also a **reusable template**: FLS will ship customised installs for multiple customers, so every site-specific value (domain, branding, secrets, DB names, R2 buckets, Sentry project) must be a substitutable placeholder, not a hardcoded constant. The Ansible inventory + GitHub Actions workflows + Caddy/Compose templates are the deliverable; "the freedomls.com deployment" is one instantiation of that template.

## Why

We have no production deployment yet. We need:
- A live staging environment for QA and demos.
- A production environment for paying tenants.
- A repeatable process for spinning up new customer installs.
- Enough operational hygiene (backups, monitoring, rollback) that one solo dev can sleep at night.

Scaling to a more elaborate topology (separate DB host, multiple app servers, Kubernetes) is explicitly out of scope until monitoring data shows we need it.

## High-level architecture

```
                    Cloudflare (DNS, free tier; grey cloud in Phase 1)
                                      |
            +-------------------------+-------------------------+
            |                                                   |
   app.<domain>            staging.<domain>            media.<domain>
   (prod web)               (staging web)              (R2 public bucket)
            \                       /                          |
             \                     /                           |
              [ Caddy on Vultr JNB ] <-- one Caddy, two vhosts | (free egress)
                          |                                    |
              +-----------+-----------+                +--------+--------+
              |                       |                |                 |
        [ prod_web ]           [ staging_web ]    [ R2 public ]   [ R2 private ]
        (gunicorn)              (gunicorn)        (custom dom.)   (signed URLs)
              \                       /
               \                     /
                [ Postgres 17 ]  <-- one container, two databases
                  fls_prod, fls_staging (separate roles)
```

Off-box:
- **Uptime Kuma** on a Hetzner CX22 in Falkenstein (~EUR 5/mo). Watching the Vultr box from a different vendor + continent is the whole point — a watchdog living on the thing it watches goes blind during the incidents that matter most.
- **Backblaze B2** for encrypted nightly Postgres dumps + GFS-rotated archives. Age-encrypted with a public key on the server; the private key lives offline (password manager + paper) so a compromised server cannot decrypt the backups it produced.
- **Cloudflare R2** for media (two buckets per env: public via `media.<domain>`, private via signed URLs).
- **Sentry SaaS free tier** for error tracking.
- **GHCR** for app images, **GitHub Actions** for CI/CD.

## Key decisions (made)

- **One Vultr High Performance VPS**, both envs co-located. Trigger to split is monitoring-driven, not calendar-driven.
- **One Postgres, two databases** (`fls_prod`, `fls_staging`) with separate roles. Saves ~600 MB RAM vs running two Postgres containers. Logical isolation is sufficient for Phase 1.
- **Two Compose projects** (`fls-prod`, `fls-staging`), four Docker networks, distinct env files, distinct `SECRET_KEY`/DB role/media bindings. Resource limits + `oom_score_adj` keep staging from starving prod.
- **One Caddy** with two virtual hosts. Wildcard cert for `*.<domain>` via Cloudflare DNS-01 (`caddybuilds/caddy-cloudflare` image). On-Demand TLS + Django `caddy_ask` endpoint wired from day one but only exercised when a custom-domain tenant arrives.
- **Multi-tenant via Django Sites** — the existing `site_aware_models` code already maps `request.get_host()` to a `Site` row. `ALLOWED_HOSTS = [".<domain>", ...]`, `CSRF_TRUSTED_ORIGINS = ["https://*.<domain>"]`. Subdomains are fully automatable; custom tenant domains are partly automatable (customer must update their DNS).
- **R2 from day one**, two buckets per env. `django-storages[s3]` with Django 6 `STORAGES`. Tenant-prefixed keys (`sites/<site_id>/...`). Versioning + 90-day non-current lifecycle.
- **Trunk-based git flow**: push `main` → staging deploy; tag `v*` → production deploy (gated by GitHub Environment with required-reviewer self-approval).
- **Image tag strategy**: immutable `:sha-<full>` always; `:vX.Y.Z` for prod releases; `:latest` never deployed to prod.
- **`docker-rollout`** for prod web container (zero-downtime swap), naive `docker compose up -d` for staging.
- **Migrations** in a one-shot ephemeral container before swap. Expand-contract for backwards-incompatible changes. Pre-deploy `pg_dump` snapshot kept locally for 7 days.
- **Static files** baked into the image at build time, served by WhiteNoise.
- **Secrets**: ansible-vault-encrypted files in the repo, vault passphrase in GitHub Secrets. Per-env vaults under `inventory/group_vars/{prod,staging}/vault.yml`.
- **SSH on port 2202**, key-only, root login disabled, `deploy` user with narrow sudoers whitelist.
- **fail2ban + UFW + unattended-upgrades + pam_exec login canary** day one.
- **Cloudflare grey-cloud** (DNS only) in Phase 1. Orange-cloud is a Phase 2 evaluation (it conflicts with on-demand TLS HTTP-01 and complicates `trusted_proxies`).
- **Alerts**: Telegram bot (vibrate channel) + email. No pager, no SMS.
- **Logs**: Docker `json-file` driver capped at 20MB×5. Structured JSON from Django to stdout. No Loki/Grafana in Phase 1.
- **Total recurring cost: ~$60/mo per install** (Vultr $48 + Hetzner Kuma ~$5.40 + B2 ~$0.50 + R2 <$5).

## Reusable-template requirement

Every value listed below must be parameterised so a new FLS install is "fill in the variables, run the bootstrap playbook":

- **Domain**: `<domain>`, `app.<domain>`, `staging.<domain>`, `media.<domain>`
- **Branding**: site name, logo, theme colours (defer to FLS brand system; the deploy template just passes them as env vars / template inputs)
- **Cloudflare**: zone ID, scoped API token (DNS:Edit on that zone)
- **Vultr**: VPS IP, SSH port, region (default JNB)
- **R2**: account ID, bucket names, scoped tokens
- **B2**: bucket names, application key
- **Sentry**: DSN, project name, environment names
- **Hetzner (monitoring box)**: IP, Cloudflare Tunnel hostname
- **GHCR**: image name, pull token
- **Postgres**: role names, passwords, database names
- **App secrets**: `SECRET_KEY`, email backend creds, etc.
- **Tenant seed**: list of `Site` rows to create on bootstrap

The "FreedomLS deployment template" repo (or directory) layout should make adding a new install a matter of creating one new `inventory/<install>/` directory with a new vault file. The Ansible roles, GitHub Actions workflows, Caddy templates, Compose templates, Dockerfile are all shared.

## Out of scope for Phase 1

- Horizontal scaling, separate DB host, managed Postgres, Redis, Celery — all Phase 2+.
- WAL archiving / PITR — daily logical backups are correct for an LMS at this scale.
- Cloudflare orange-cloud, WAF tuning, rate limiting beyond Caddy defaults.
- Self-service tenant signup; new tenants go through manual DNS step + admin command.
- Cloudflare for SaaS custom-hostname API.
- Self-hosted Sentry, Loki, Grafana, Prometheus.
- Wazuh / OSSEC / heavy IDS.
- Direct browser-to-R2 presigned PUTs (large file uploads); Phase 1 ships through-Django uploads with a TODO at the 5 MB threshold.

## Open questions for the spec phase

- **Healthcheck design**: what exactly does `/healthz` exercise — DB ping only, or also R2 reachability? (Probably DB only; R2 outages should not take staging/prod containers out of the load balancer.)
- **First-deploy bootstrap**: how is the initial superuser created? One-shot Ansible task, environment-driven Django command, or out-of-band `manage.py createsuperuser` over SSH?
- **Restore drill cadence**: monthly automated smoke restore plus quarterly full drill is the recommendation; how do we surface drill failures (push to healthchecks.io? Telegram?).
- **Branding/customisation interface**: where does customer-specific config (colours, logo, copy) live in the deploy template? Env vars rendered by Ansible? A separate `customer_config.yml` overlay? This intersects with the FLS brand system and the existing `markdown_content` setup.
- **Image build per customer or shared**: do all customer installs run the same FLS image, or do we build per-customer images with branding baked in? If shared, how do per-customer assets reach the running container?
- **Secrets bootstrap for new install**: who generates the initial vault passphrase, R2 token, etc., and how do they enter the system without leaving plaintext on disk?
- **Hetzner Kuma sharing**: does one Hetzner CX22 Kuma instance monitor all FLS installs (cheaper, single dashboard) or one per install (cleaner ownership, more cost)? Probably one shared, with installs as separate tags/groups inside Kuma.

## Research

Detailed findings live alongside this idea file:

- `research-on-scaling-stratergy.md` — hosting provider analysis, why Vultr JNB, ISO 27001 considerations, scaling phases.
- `research-staging-prod-coexistence.md` — single-VPS topology, Postgres-sharing tradeoff, resource budgeting, isolation patterns.
- `research-multi-tenant-caddy-cloudflare.md` — TLS strategy, Caddy `ask` endpoint, Django Sites integration, per-tenant workflows.
- `research-ansible-github-actions.md` — playbook structure, bootstrap order, deploy workflow, migration strategy, rollback.
- `research-r2-media-storage.md` — R2 vs alternatives, two-bucket pattern, signed URLs, Django 6 `STORAGES` config.
- `research-backups-monitoring.md` — pg_dump + age + B2, restore drills, off-box Uptime Kuma, Sentry, alerting routes, log management.
