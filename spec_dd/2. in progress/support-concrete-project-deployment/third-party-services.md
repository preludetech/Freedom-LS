# Third-party services & credentials — concrete FLS deployment

This catalogues every **externally-hosted service** a concrete (submodule-based) FLS production
deployment depends on: what to **sign up for**, what to **configure**, what **credentials/env vars**
result, and which spec consumes them. It is a setup reference for whoever stands up a
`ConcreteFlsImplementation` deployment from the Spec 5 template scaffolding — the scaffolding assumes
these accounts exist and reads their credentials from `.env`.

> **Scope.** These are the *external* dependencies. The shipped stack itself (Gunicorn, WhiteNoise,
> containerised `postgres:17`, Caddy) needs no external account. Consumed mostly by **Spec 5** (the
> template scaffolding); a few values are also read by **Spec 1** settings and **Spec 2** health.

## 1. Cloudflare (DNS + front proxy) — required

- **Sign up for:** a Cloudflare account, and add the deployment's **domain as a zone**.
- **Configure:**
  - Point the zone's DNS at the VPS; proxy the app hostname through Cloudflare (orange-cloud).
  - **SSL/TLS mode = Full (strict)** — **never Flexible** (Flexible breaks the
    `SECURE_PROXY_SSL_HEADER` trust chain and can cause redirect loops).
  - **Firewall the origin to Cloudflare's IP ranges** so the proxy header can be trusted.
  - Scope Caddy's `trusted_proxies` to **Cloudflare's published IP ranges** — never `0.0.0.0/0`.
- **Credentials / config produced:**
  - `DOMAIN` (Caddy `{$DOMAIN}` substitution) — Spec 5 Caddyfile + Spec 1 host settings.
  - Cloudflare IP ranges → Caddy `trusted_proxies`; `CF-Connecting-IP` handling — Spec 5.
  - (Optional, if DNS is automated) a Cloudflare API token scoped to the zone.
- **Consumed by:** Spec 1 (§5.1-A proxy-header preconditions), Spec 5 (§5.3 Caddyfile).

## 2. Object storage — Cloudflare R2 / S3-compatible (media) — required

- **Sign up for:** an S3-compatible object-storage provider (Cloudflare R2, or AWS S3 / compatible).
- **Configure:** create the media bucket(s); create an access key/secret scoped to them; note the
  endpoint and region.
- **Credentials produced (env vars, exact names per the storage backend the project wires):**
  access key ID, secret access key, bucket name(s), endpoint URL, region.
- **Consumed by:** Spec 5 (media storage config + `.env.example`); Spec 2 (the **opt-in** readiness
  storage check, off by default).
- **Note:** media is on object storage; static is served by WhiteNoise from the image — Caddy proxies
  only (no `/static`/`/media` file serving).

## 3. Sentry (error tracking / observability) — required for prod

- **Sign up for:** a Sentry account and a **project** for this deployment.
- **Configure:** create the project, grab its **DSN**; optionally set environment/release tagging.
- **Credentials produced:** `SENTRY_DSN` (+ any environment/release env vars).
- **Consumed by:** Spec 5 (§5.6 Sentry observability wiring, parameterised template).

## 4. GitHub Container Registry (GHCR) — required (CI/CD)

- **Sign up for:** a GitHub account/org hosting the concrete project repo (GHCR is part of GitHub).
- **Configure:** enable GitHub Actions; the build workflow pushes a SHA-tagged image to GHCR using
  the Actions-provided `GITHUB_TOKEN` with `packages: write` permission (or a PAT for cross-repo
  pushes). The VPS needs read access to pull the image.
- **Credentials produced:** `GITHUB_TOKEN` (in-Actions, `packages: write`); a pull credential on the
  VPS if the package is private.
- **Consumed by:** Spec 5 (§5.5 GHCR build-and-push CI).

## 5. VPS host + DNS — required

- **Sign up for:** a single **VPS** from any provider (the shipped topology is single-host Docker
  Compose).
- **Configure:** an **SSH key** for Ansible provisioning/hardening; DNS records at Cloudflare (see
  §1) pointing at the VPS.
- **Credentials produced:** SSH private key / host access for the Ansible control machine.
- **Consumed by:** Spec 5 (§5.6 Ansible provisioning/hardening).

## 6. Off-box backup destination — required for prod

- **Sign up for:** an **off-box storage target** for encrypted database backups (object storage, a
  second host, or a managed backup service).
- **Configure:** credentials for the sync target; a **backup encryption key** (backups are
  `pg_dump` + encrypted off-box sync).
- **Credentials produced:** backup-target credentials + backup encryption key/passphrase.
- **Consumed by:** Spec 5 (§5.6 backups template).

## 7. PostgreSQL — usually **no** external account

- The shipped topology is **same-host containerised `postgres:17`** — no external provider, and
  `DB_SSLMODE=disable` is correct (the real DB-security control is **not publishing `5432`**, Spec 5).
- **Only** if a project uses an **external/managed** Postgres does it need a provider account and
  `DB_SSLMODE=require` / `verify-full` (Spec 1 §5.1-D reserves those modes for that case).

## Consolidated credentials / env-var checklist

| Var / secret | Type | Source service | Consumed by |
|---|---|---|---|
| `SECRET_KEY` | per-deploy secret | generated (not a service) | Spec 1 (hard-fail if missing) |
| `DOMAIN` | config | Cloudflare zone (§1) | Spec 1, Spec 5 (Caddy) |
| `trusted_proxies` (CF ranges) | config | Cloudflare (§1) | Spec 5 (Caddy) |
| `DB_SSLMODE` | config (`disable` default) | Postgres topology (§7) | Spec 1 |
| Object-storage access key / secret / bucket / endpoint | per-deploy secret + config | R2 / S3 (§2) | Spec 5, Spec 2 (opt-in) |
| `SENTRY_DSN` | per-deploy secret | Sentry (§3) | Spec 5 |
| `GITHUB_TOKEN` (`packages: write`) / GHCR pull cred | CI secret | GitHub/GHCR (§4) | Spec 5 |
| VPS SSH key | operator secret | VPS (§5) | Spec 5 (Ansible) |
| Backup target creds + backup encryption key | per-deploy secret | off-box target (§6) | Spec 5 (backups) |

**Legend:** *per-deploy secret* = unique per environment, never committed (lives in `.env` / CI
secrets); *config* = non-secret value documented in `.env.example`; *operator/CI secret* = held by
the person/pipeline running the deploy.
