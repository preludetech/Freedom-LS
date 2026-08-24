# Third-party services & credentials — concrete FLS deployment

This catalogues every **externally-hosted service** a concrete (submodule-based) FLS production
deployment depends on: what to **sign up for**, what to **configure**, what **credentials/env vars**
result, and which spec consumes them. It is a setup reference for whoever stands up a
`ConcreteFlsImplementation` deployment from the Spec 5 template scaffolding — the scaffolding assumes
these accounts exist and reads their credentials from `.env`.

> **Scope.** These are the *external* dependencies. The shipped stack itself (Gunicorn, WhiteNoise,
> containerised `postgres:17`, Caddy) needs no external account. Consumed mostly by **Spec 5** (the
> template scaffolding); a few values are also read by **Spec 1** settings and **Spec 2** health.
> **Host provisioning (Ansible) and database backups are owned by a separate fleet ops repo**, not
> Spec 5 — that repo manages the shared host (prod + staging on one VPS) and the off-box backups; the
> VPS (§5) and off-box backup target (§6) accounts below are still required, just consumed there.

> **Env-var contract.** For the PostHog / Sentry / R2 vars specifically, this repo's `.env.example`
> is the authoritative, in-sync list — the two documents together form one contract.

## 1. Cloudflare (DNS + front proxy) — required

- **Sign up for:** a Cloudflare account, and add the deployment's **domain as a zone**.
- **Configure:**
  - Point the zone's DNS at the VPS; proxy the app hostname through Cloudflare (orange-cloud).
  - **SSL/TLS mode = Full (strict)** — **never Flexible** (Flexible breaks the
    `SECURE_PROXY_SSL_HEADER` trust chain and can cause redirect loops).
  - **Firewall the origin to Cloudflare's IP ranges** so the proxy header can be trusted.
  - Scope Caddy's `trusted_proxies` to **Cloudflare's published IP ranges** — never `0.0.0.0/0`.
- **Credentials / config produced:**
  - `HOST_DOMAIN` (Caddy `{$HOST_DOMAIN}` substitution) — Spec 5 Caddyfile + Spec 1 host settings.
    This is the **single** domain var both the prod settings and the Caddyfile read (Spec 5 §5.3);
    there is no separate Caddy `DOMAIN`.
  - Cloudflare IP ranges → Caddy `trusted_proxies`; `CF-Connecting-IP` handling — Spec 5.
  - (Optional, if DNS is automated) a Cloudflare API token scoped to the zone.
- **Consumed by:** Spec 1 (§5.1-A proxy-header preconditions), Spec 5 (§5.3 Caddyfile).

## 2. Object storage — Cloudflare R2 / S3-compatible (media) — required

- **Sign up for:** an S3-compatible object-storage provider (Cloudflare R2, or AWS S3 / compatible).
- **Configure:** create the media bucket(s); create an access key/secret scoped to them; note the
  endpoint and region.
- **Credentials produced (env vars, wired by `freedom_ls/deployment` — see this repo's
  `.env.example`):**
  - `AWS_STORAGE_BUCKET_NAME` — config; also the on/off gate (unset ⇒ local `FileSystemStorage`).
  - `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` — **secret**.
  - `AWS_S3_ENDPOINT_URL` — config, e.g. `https://<account-id>.r2.cloudflarestorage.com`.
  - `AWS_S3_REGION_NAME` — config, default `auto` (R2's region convention).
  - `AWS_S3_CUSTOM_DOMAIN` — config, optional; opt-in to public serving only (set together with
    `AWS_QUERYSTRING_AUTH=False`).
  - `AWS_QUERYSTRING_AUTH` — config, default `True` (private, time-limited signed URLs).
  - `AWS_QUERYSTRING_EXPIRE` — config, default `3600` (signed-URL lifetime, seconds).
  - No `AWS_DEFAULT_ACL` — R2 has no ACLs; the var was removed.
- **Consumed by:** Spec 5 (media storage config + `.env.example`); Spec 2 (the **opt-in** readiness
  storage check, off by default).
- **Note:** media is on object storage; static is served by WhiteNoise from the image — Caddy proxies
  only (no `/static`/`/media` file serving).

## 3. Sentry (error tracking / observability) — required for prod

- **Sign up for:** a Sentry account and a **project** for this deployment.
- **Configure:** create the project, grab its **DSN**; set environment/release tagging per
  environment.
- **Credentials produced (env vars, wired by `freedom_ls/deployment` — see this repo's
  `.env.example`):**
  - `SENTRY_DSN` — **secret**; unset ⇒ Sentry off.
  - `SENTRY_ENVIRONMENT` — config; set explicitly whenever `SENTRY_DSN` is set — the SDK otherwise
    silently tags events `"production"`.
  - `SENTRY_RELEASE` — config, optional; CI-injected git SHA; unset ⇒ no release tag.
  - `SENTRY_TRACES_SAMPLE_RATE` — config, default `0.1`.
  - `SENTRY_SEND_DEFAULT_PII` — config, default `False`.
- **Consumed by:** Spec 5 (§5.6 Sentry observability wiring, parameterised template).

## 3a. PostHog (analytics) — optional

- **Sign up for:** a PostHog account and a **project** per environment (staging and prod each get
  their own project token).
- **Configure:** grab the project's API key; pick the region host (US or EU).
- **Credentials produced (env vars, wired by `freedom_ls/deployment` — see this repo's
  `.env.example`):**
  - `POSTHOG_API_KEY` — public project token (safe in client-side HTML); unset ⇒ PostHog disabled.
  - `POSTHOG_API_HOST` — config, default `https://us.i.posthog.com` (override for EU).
  - `POSTHOG_UI_HOST` — config, optional; only needed for a reverse-proxied ingestion host.
- **Consumed by:** `freedom_ls.base.context_processors.posthog_config` (in-repo, every render) —
  no Spec 5 template wiring needed beyond setting the env vars.

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
  §1) pointing at the VPS. Both the prod and staging FLS instances run on this **same host**.
- **Credentials produced:** SSH private key / host access for the Ansible control machine.
- **Consumed by:** the **separate fleet ops repo** (Ansible provisioning/hardening) — out of scope for
  Spec 5.

## 6. Off-box backup destination — required for prod

- **Sign up for:** an **off-box storage target** for encrypted database backups (object storage, a
  second host, or a managed backup service).
- **Configure:** credentials for the sync target; a **backup encryption key** (backups are
  `pg_dump` + encrypted off-box sync of **both** the prod and staging DBs on the shared host).
- **Credentials produced:** backup-target credentials + backup encryption key/passphrase.
- **Consumed by:** the **separate fleet ops repo** (backup scheduling + off-box sync) — out of scope
  for Spec 5.

## 7. PostgreSQL — usually **no** external account

- The shipped topology is **same-host containerised `postgres:17`** — no external provider, and
  `DB_SSLMODE=disable` is correct (the real DB-security control is **not publishing `5432`**, Spec 5).
- **Only** if a project uses an **external/managed** Postgres does it need a provider account and
  `DB_SSLMODE=require` / `verify-full` (Spec 1 §5.1-D reserves those modes for that case).

## Consolidated credentials / env-var checklist

| Var / secret | Type | Source service | Consumed by |
|---|---|---|---|
| `SECRET_KEY` | per-deploy secret | generated (not a service) | Spec 1 (hard-fail if missing) |
| `HOST_DOMAIN` | config | Cloudflare zone (§1) | Spec 1, Spec 5 (Caddy) |
| `trusted_proxies` (CF ranges) | config | Cloudflare (§1) | Spec 5 (Caddy) |
| `DB_SSLMODE` | config (`disable` default) | Postgres topology (§7) | Spec 1 |
| `AWS_STORAGE_BUCKET_NAME` | config (on/off gate) | R2 / S3 (§2) | Spec 5, Spec 2 (opt-in) |
| `AWS_S3_ACCESS_KEY_ID` / `AWS_S3_SECRET_ACCESS_KEY` | per-deploy secret | R2 / S3 (§2) | Spec 5, Spec 2 (opt-in) |
| `AWS_S3_ENDPOINT_URL` / `AWS_S3_REGION_NAME` (`auto` default) | config | R2 / S3 (§2) | Spec 5, Spec 2 (opt-in) |
| `AWS_S3_CUSTOM_DOMAIN` (opt-in) / `AWS_QUERYSTRING_AUTH` (`True` default) / `AWS_QUERYSTRING_EXPIRE` (`3600` default) | config | R2 / S3 (§2) | Spec 5, Spec 2 (opt-in) |
| `SENTRY_DSN` | per-deploy secret | Sentry (§3) | Spec 5 |
| `SENTRY_ENVIRONMENT` / `SENTRY_RELEASE` | config | Sentry (§3) | Spec 5 |
| `SENTRY_TRACES_SAMPLE_RATE` (`0.1` default) / `SENTRY_SEND_DEFAULT_PII` (`False` default) | config | Sentry (§3) | Spec 5 |
| `POSTHOG_API_KEY` | public token | PostHog (§3a) | in-repo (`base.context_processors`) |
| `POSTHOG_API_HOST` (`https://us.i.posthog.com` default) / `POSTHOG_UI_HOST` (optional) | config | PostHog (§3a) | in-repo (`base.context_processors`) |
| `GITHUB_TOKEN` (`packages: write`) / GHCR pull cred | CI secret | GitHub/GHCR (§4) | Spec 5 |
| VPS SSH key | operator secret | VPS (§5) | fleet ops repo (Ansible) |
| Backup target creds + backup encryption key | per-deploy secret | off-box target (§6) | fleet ops repo (backups) |

**Legend:** *per-deploy secret* = unique per environment, never committed (lives in `.env` / CI
secrets); *config* = non-secret value documented in `.env.example`; *operator/CI secret* = held by
the person/pipeline running the deploy.
