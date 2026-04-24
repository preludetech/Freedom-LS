# Deployment Security Checklist

Use this checklist before every production deployment to ensure the system is properly secured.

---

## 1. Server Hardening

- [ ] Operating system is fully patched and on a supported version
- [ ] Only minimal required services are running
- [ ] SSH access uses key-based authentication only (password auth disabled)
- [ ] Root SSH login is disabled
- [ ] Unattended security updates are enabled
- [ ] Non-essential packages have been removed

## 2. Database Security

- [ ] Application uses a dedicated database user (not the superuser). **Required** — `experience_api` migration 0002 issues `REVOKE UPDATE, DELETE ON experience_api_event` against the application role to make the audit log immutable. Superusers bypass all grants, so running the app as a superuser silently defeats this protection and leaves the event log mutable in production. Local pytest and CI both exercise this by running against the non-superuser `fls_app` role (`pyproject.toml` → `[tool.pytest.ini_options].env`); run `fls-claude-plugin/scripts/dev_db_init.sh` once after cloning to provision the role.
- [ ] Database user has only the minimum required privileges
- [ ] A separate `fls_erasure_role` exists (created by `experience_api` migration 0002) and is held **only** by the dedicated erasure login user configured via `FLS_ERASURE_DB_USER` / `FLS_ERASURE_DB_PASSWORD`. The application user must not be a member of `fls_erasure_role`.
- [ ] Database password is strong (32+ characters, randomly generated)
- [ ] Database is not publicly accessible (bound to private network only)
- [ ] Database connections use SSL/TLS encryption
- [ ] Database backups are encrypted

## 3. TLS Configuration

- [ ] TLS 1.2 or higher is enforced (TLS 1.0 and 1.1 disabled)
- [ ] Strong cipher suites only (disable weak ciphers like RC4, 3DES)
- [ ] HTTP requests are redirected to HTTPS (301 redirect)
- [ ] SSL certificate is valid and not near expiration
- [ ] Certificate chain is complete
- [ ] OCSP stapling is enabled
- [ ] If behind a reverse proxy (Nginx, Cloudflare, ALB), set `SECURE_PROXY_SSL_HEADER` in Django settings to avoid redirect loops

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
- [ ] SSH port (22) is restricted to known admin IPs or VPN
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

- [ ] Centralized logging is configured (e.g., ELK, CloudWatch, Datadog)
- [ ] Log rotation is enabled to prevent disk exhaustion
- [ ] Security events are logged (failed logins, permission denials, admin actions)
- [ ] Logs do not contain sensitive data (passwords, tokens, PII)
- [ ] Log retention policy complies with regulatory requirements
- [ ] Alerts are configured for suspicious activity patterns

## 8. Monitoring

- [ ] Uptime checks are configured for the application URL
- [ ] Error tracking is enabled (e.g., Sentry, Rollbar)
- [ ] Performance monitoring is active (response times, throughput)
- [ ] Disk, CPU, and memory alerts are configured
- [ ] Database connection pool monitoring is in place
- [ ] SSL certificate expiration monitoring is active

## 9. Django Deployment Check

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

## 10. Environment Variables

All required environment variables must be set in production. Never hardcode credentials.

### Core Django Settings

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key. Must be unique, random, and at least 50 characters. |
| `HOST_DOMAIN` | The production domain name (e.g., `example.com`). Used for `ALLOWED_HOSTS`. |

### Database

| Variable | Description |
|---|---|
| `DB_NAME` | PostgreSQL database name. |
| `DB_USER` | PostgreSQL database user. |
| `DB_PASSWORD` | PostgreSQL database password. Must be strong and randomly generated. |
| `DB_HOST` | PostgreSQL host address. |
| `DB_PORT` | PostgreSQL port (default: `5432`). |
| `FLS_ERASURE_DB_USER` | PostgreSQL login user for the `experience_api` erasure command. Must be a member of `fls_erasure_role`. Not the application user. |
| `FLS_ERASURE_DB_PASSWORD` | Password for `FLS_ERASURE_DB_USER`. Must be strong and randomly generated. Rotate independently of `DB_PASSWORD`. |

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

### Email

| Variable | Description |
|---|---|
| `EMAIL_BACKEND` | Django email backend class path. |
| `EMAIL_HOST` | SMTP server hostname. |
| `EMAIL_PORT` | SMTP server port. |
| `EMAIL_USE_TLS` | Whether to use TLS for email (`True`/`False`). |
| `EMAIL_HOST_USER` | SMTP authentication username. |
| `EMAIL_HOST_PASSWORD` | SMTP authentication password. |
| `DEFAULT_FROM_EMAIL` | Default sender email address. |

### AWS / S3 Storage

| Variable | Description |
|---|---|
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name for media storage. |
| `AWS_S3_ACCESS_KEY_ID` | AWS access key ID. |
| `AWS_S3_SECRET_ACCESS_KEY` | AWS secret access key. |
| `AWS_S3_ENDPOINT_URL` | Custom S3 endpoint URL (for S3-compatible services). |
| `AWS_DEFAULT_ACL` | Default ACL for uploaded files (e.g., `private`). |
| `AWS_S3_REGION_NAME` | AWS region for the S3 bucket. |

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
