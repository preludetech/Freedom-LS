# Deployment Security Checklist

Use this checklist before every production deployment to ensure the system is properly secured.

Security controls only. The operational side of a deployment — the deploy sequence, background
worker and housekeeping processes, health probes, uptime and error monitoring, backups as an
operation — is in [product deployment documentation](./product/deployment.md). The complete,
annotated set of environment variables is in `.env.example`; only the security-relevant ones are
listed here.

---

## 1. Server Hardening

- [ ] Operating system is fully patched and on a supported version
- [ ] Only minimal required services are running
- [ ] SSH access uses key-based authentication only (password auth disabled)
- [ ] Root SSH login is disabled
- [ ] Unattended security updates are enabled
- [ ] Non-essential packages have been removed

## 2. Database Security

- [ ] Application uses a dedicated database user (not the superuser). Topology-dependent: for
      the same-host containerised Postgres this project ships with, the official image runs
      `initdb --username="$POSTGRES_USER"`, so the application role is the cluster superuser by
      construction, and the backup path authenticates as that role over the container's local
      socket, which is what keeps the password off a command line `ps` would show. A separate
      application role would break that backup. This item stands as written for an external or
      managed database
- [ ] Database user has only the minimum required privileges
- [ ] Database password is strong (32+ characters, randomly generated)
- [ ] Database is not publicly accessible (bound to private network only)
- [ ] Database connections use SSL/TLS encryption (external/managed databases only — for
      the same-host containerised Postgres this project ships with, the load-bearing
      control is not publishing port 5432 to the host, not `sslmode`; see Firewall Rules
      below)
- [ ] Database backups are encrypted

## 3. TLS Configuration

- [ ] TLS 1.2 or higher is enforced (TLS 1.0 and 1.1 disabled)
- [ ] Strong cipher suites only (disable weak ciphers like RC4, 3DES)
- [ ] HTTP requests are redirected to HTTPS (301 redirect)
- [ ] SSL certificate is valid and not near expiration
- [ ] Certificate expiration monitoring is active, so a lapse is caught before it drops traffic
- [ ] Certificate chain is complete
- [ ] OCSP stapling is enabled
- [ ] If behind a reverse proxy (Nginx, Cloudflare, ALB), set `SECURE_PROXY_SSL_HEADER` in Django settings to avoid redirect loops
- [ ] SMTP submission uses TLS (`EMAIL_USE_TLS=True`), so mail credentials and message bodies do not cross the network in the clear

## 4. HSTS Rollout

Deploy HSTS in stages to avoid locking users out if there are TLS issues:

### Stage 1: Initial deployment
```
HSTS_SECONDS=3600
HSTS_INCLUDE_SUBDOMAINS=False
HSTS_PRELOAD=False
```
Monitor for 1 week. Verify no TLS errors in logs.

### Stage 2: Increase to 1 week
```
HSTS_SECONDS=604800
HSTS_INCLUDE_SUBDOMAINS=False
HSTS_PRELOAD=False
```
Monitor for 1 week. Verify all traffic is HTTPS with no issues.

### Stage 3: Increase to 1 year
```
HSTS_SECONDS=31536000
HSTS_INCLUDE_SUBDOMAINS=False
HSTS_PRELOAD=False
```
Monitor for 1 month. Verify all traffic is HTTPS.

### Stage 4: Enable subdomains and preload
```
HSTS_SECONDS=31536000
HSTS_INCLUDE_SUBDOMAINS=True
HSTS_PRELOAD=True
```
Submit domain to the [HSTS preload list](https://hstspreload.org/).

## 5. Firewall Rules

- [ ] Only ports 80 (HTTP) and 443 (HTTPS) are publicly accessible
- [ ] Database port (5432) is restricted to application servers only
- [ ] SSH port (22) is restricted to known admin IPs or VPN. Topology-dependent: a fleet whose
      operators have no fixed address instead relies on key-based authentication (already
      required above, with password auth disabled) plus `fail2ban` to block brute-force
      attempts. Answer with whichever control applies
- [ ] All other ports are blocked by default (deny-all policy)
- [ ] Outbound traffic is restricted to required destinations only

## 6. Backup Encryption

- [ ] Database backups are encrypted at rest
- [ ] Backup encryption keys are stored separately from backups
- [ ] Backup restore process has been tested and documented
- [ ] Backups are stored in a geographically separate location
- [ ] Backup retention policy is defined and enforced
- [ ] Regular restore drills are scheduled (at least quarterly)

## 7. Log Management

- [ ] Centralized logging is configured (e.g., ELK, CloudWatch, Datadog). Topology-dependent:
      production logs to stdout only, capped at the container log driver, and errors also go to
      Sentry, so a two-box fleet with no aggregator satisfies this differently
- [ ] Security events are logged (failed logins, permission denials, admin actions)
- [ ] Logs do not contain sensitive data (passwords, tokens, PII)
- [ ] Log retention policy complies with regulatory requirements
- [ ] Alerts are configured for suspicious activity patterns

## 8. Django Deployment Check

Run the built-in Django deployment check before every release:

```bash
uv run manage.py check --deploy
```

Review and resolve all warnings. Common issues include:

- `SECURE_HSTS_SECONDS` not set
- `SECURE_SSL_REDIRECT` not enabled
- `SESSION_COOKIE_SECURE` not set
- `CSRF_COOKIE_SECURE` not set
- `DEBUG` set to True

`freedom_ls_deployment.W001` (`SENTRY_DSN` set but `SENTRY_RELEASE` blank) can be silenced via
`SILENCED_SYSTEM_CHECKS` if release tracking is intentionally disabled for an environment.

FLS's own checks are split across the two runs, so run both:

- [ ] `uv run manage.py check` — covers `freedom_ls_accounts.E003`, which catches a
      `TRUSTED_PROXY_IP_HEADER` still holding the old `request.META` spelling (`HTTP_`-prefixed).
      That value never matches, so the client IP silently falls back to the connecting address.
- [ ] `uv run manage.py check --deploy` — the only run that executes
      `freedom_ls_deployment.E001` through `E006`. See §9 for what each reports.

## 9. Environment Variables

The security-relevant variables only. `.env.example` carries the complete annotated set, including
the connection, mail and analytics settings that are configuration rather than controls. Never
hardcode credentials.

### Core Django Settings

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key. Must be unique, random, and at least 50 characters. |
| `WEBHOOK_ENCRYPTION_SALT` | Salt for webhook-secret Fernet encryption. Required in production — startup raises `ImproperlyConfigured` (crash-loops) when unset. |
| `HOST_DOMAIN` | The production domain name (e.g., `example.com`). Used for `ALLOWED_HOSTS`. |
| `TRUSTED_CLIENT_IP_HEADER` | The header your edge sets to the visitor's own address. Defaults to `CF-Connecting-IP`, which a Cloudflare tunnel sets. Sets both `TRUSTED_PROXY_IP_HEADER` and `ALLAUTH_TRUSTED_CLIENT_IP_HEADER`. Naming a header the edge does not send answers 403 to every login, and no check can detect that — verify with a real sign-in. Must be one the edge *sets* rather than appends, so it carries exactly one address. |

### Database

| Variable | Description |
|---|---|
| `DB_PASSWORD` | PostgreSQL database password. Must be strong and randomly generated. |
| `DB_SSLMODE` | libpq `sslmode` (default: `prefer`). Use `require`/`verify-full` for external/managed databases. |

### HSTS

| Variable | Description |
|---|---|
| `HSTS_SECONDS` | HSTS max-age in seconds. See HSTS Rollout section above. |
| `HSTS_INCLUDE_SUBDOMAINS` | Whether to include subdomains in HSTS policy (`True`/`False`). |
| `HSTS_PRELOAD` | Whether to enable HSTS preload (`True`/`False`). |

### Admin

| Variable | Description |
|---|---|
| `DJANGO_ADMIN_URL` | Custom admin URL path (e.g., `my-secret-admin/`). Defaults to `admin/`. |

### Legal Documents

| Variable | Description |
|---|---|
| `LEGAL_DOCS_MANIFEST_PATH` | Absolute path to the pre-built legal-docs manifest JSON. Required in deployments where `.git` is absent. Must point to a **read-only** location in the image filesystem. If set, the file MUST exist or startup raises `ImproperlyConfigured`. See §10. |

### AWS / S3 Storage

FLS resolves storage per bucket purpose, not per project. `PURPOSE` is one of `PUBLIC`,
`COURSE_MEDIA`, `USER_UPLOADS`, `GENERATED`, `CERTIFICATES`, `DEFAULT`, one per `STORAGES` alias.
Every variable below is optional. An unset per-bucket variable falls through to the shared column,
and an unset bucket name falls through to local filesystem storage — which `check --deploy` reports
as an error outside `DEBUG`, so it is a development convenience rather than a production mode.

| Property | Shared variable | Per-bucket override |
|---|---|---|
| Bucket name | `AWS_STORAGE_BUCKET_NAME` | `AWS_S3_<PURPOSE>_BUCKET_NAME` |
| Access key | `AWS_S3_ACCESS_KEY_ID` | `AWS_S3_<PURPOSE>_ACCESS_KEY_ID` |
| Secret key | `AWS_S3_SECRET_ACCESS_KEY` | `AWS_S3_<PURPOSE>_SECRET_ACCESS_KEY` |
| Endpoint URL | `AWS_S3_ENDPOINT_URL` | `AWS_S3_<PURPOSE>_ENDPOINT_URL` |
| Region | `AWS_S3_REGION_NAME` (default `auto` for R2) | `AWS_S3_<PURPOSE>_REGION_NAME` |
| Custom domain | `AWS_S3_CUSTOM_DOMAIN` | `AWS_S3_<PURPOSE>_CUSTOM_DOMAIN` |
| Querystring auth | `AWS_QUERYSTRING_AUTH` | `AWS_S3_<PURPOSE>_QUERYSTRING_AUTH` |
| Querystring expire | `AWS_QUERYSTRING_EXPIRE` | `AWS_S3_<PURPOSE>_QUERYSTRING_EXPIRE` |

An access key and its secret must be set together or not at all. A per-bucket key id paired with
the shared secret signs every request with a key the secret does not match, and nothing downstream
can see that; a half-set pair therefore raises `ImproperlyConfigured` at startup rather than
falling back.

Which alias each kind of file writes to is configurable; see
[configuration and extension](./product/configuration-and-extension.md).

Four checks between them require every media alias to reach a bucket of its own and to serve its
files the way its contents need.

| Check | Reports |
|---|---|
| `freedom_ls_deployment.E001` | An alias that resolves to the same bucket as `default`. |
| `freedom_ls_deployment.E002` | An alias that reached no bucket at all and fell back to local disk while `DEBUG` is off — what a misspelled per-bucket variable produces once the shared `AWS_STORAGE_BUCKET_NAME` is left unset. |
| `freedom_ls_deployment.E003` | An alias that took its bucket from the shared `AWS_STORAGE_BUCKET_NAME` because its own variable is unset. E001 cannot see this one: with `AWS_S3_DEFAULT_BUCKET_NAME` naming a bucket of its own, an alias that fell through matches nothing it compares against. |
| `freedom_ls_deployment.E004` | An alias holding private files — course media, user uploads, cohort reports — resolving with querystring auth off, so its URLs are unsigned and never expire. The shared `AWS_QUERYSTRING_AUTH` reaches every media alias, which is how a project upgrading from the single-bucket layout carries public serving forward onto learner data. |

They carry separate ids so that a deployment serving media from local disk deliberately can silence
E002 through `SILENCED_SYSTEM_CHECKS` without also giving up the other three.

Two further deploy checks cover the production cache and the edge:

| Check | Reports |
|---|---|
| `freedom_ls_deployment.E005` | A database-backed cache alias whose table does not exist, because `createcachetable` was not run before the application started serving. No migration creates it; it belongs in the deploy sequence, described in [product deployment documentation](./product/deployment.md). A database this check cannot reach reports nothing rather than a false error, so a build container with no database still passes. |
| `freedom_ls_deployment.E006` | `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` and `TRUSTED_PROXY_IP_HEADER` naming different headers, which would have allauth's rate limiting and django-axes' lockout keying their counters on two different addresses for the same visitor. |

All six run only under `manage.py check --deploy`, not under plain `check`, `runserver` or
`migrate`, so a deploy pipeline has to actually run `check --deploy` for any of them to catch a
misconfigured bucket, a missing cache table or a mismatched edge header.

One FLS check is deliberately **not** deploy-gated. `freedom_ls_accounts.E003` errors when
`TRUSTED_PROXY_IP_HEADER` holds an `HTTP_`-prefixed value, the `request.META` key form the setting
used to take. Both readers now go through `request.headers`, where that value never matches, so the
client IP falls back to the proxy's own address and lands in consent evidence and lockout keys with
nothing to say it happened. It runs on `runserver` and `migrate` too, so a downstream carrying the
old spelling meets it in development rather than at deploy time.

No check can tell whether your edge actually sends the header you named. Naming one it does not send
removes allauth's fallback to `REMOTE_ADDR` and answers 403 to every login, signup and password
reset, so verify it with a real sign-in after deploying.

## 10. Legal Documents

The `accounts` app reads Terms / Privacy from the git blob at HEAD so a tampered
working tree cannot affect what users see at signup or what is recorded as
consent evidence. **The git-checkout mode is the more tamper-resistant of the
two — use the manifest only when `.git` is genuinely unavailable at runtime**
(e.g. slim Docker images that ship without a `.git` directory). In that case,
build a manifest at image-build time:

- [ ] At image build time, BEFORE the `.git` directory is dropped, run:
  ```bash
  uv run manage.py build_legal_docs_manifest -o /app/legal_docs.manifest.json
  ```
- [ ] Bake the resulting manifest into a **read-only** layer of the image
- [ ] Set `LEGAL_DOCS_MANIFEST_PATH` to the absolute path of that file in
      production settings, e.g.:
      ```python
      LEGAL_DOCS_MANIFEST_PATH = "/app/legal_docs.manifest.json"
      ```
      If the setting is set but the file is missing, startup raises
      `ImproperlyConfigured` — fail-loud is intentional.
- [ ] Never regenerate the manifest at runtime — once built, the manifest IS
      the source of truth in this mode, and an attacker with write access to
      the manifest controls both the displayed content AND the recorded
      `git_hash`
- [ ] Rebuild the manifest as part of every build whenever a legal doc has
      been edited and committed
- [ ] Run `uv run manage.py check` and confirm no legal-doc system-check
      warnings before promoting the image

## 11. GitHub Security Features

- [ ] Dependabot is enabled for dependency vulnerability alerts
- [ ] Dependabot security updates are configured for automatic PRs
- [ ] GitHub secret scanning is enabled on the repository
- [ ] Branch protection is enabled on `main`:
  - [ ] Require pull request reviews before merging
  - [ ] Require status checks to pass before merging
  - [ ] Require branches to be up to date before merging
  - [ ] Do not allow force pushes
  - [ ] Do not allow deletions
- [ ] Code scanning (CodeQL or equivalent) is enabled
