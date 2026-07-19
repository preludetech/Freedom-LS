---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - WEBHOOK_ENCRYPTION_SALT   # NEW required secret in production — app fails fast on boot if unset
  - DJANGO_ADMIN_URL          # .env.example parity — config, default "admin/"
  - HSTS_SECONDS              # .env.example parity — config, default 3600
  - HSTS_INCLUDE_SUBDOMAINS   # .env.example parity — config, default False
  - HSTS_PRELOAD              # .env.example parity — config, default False
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: more deploy preparation

## Breaking changes

**`WEBHOOK_ENCRYPTION_SALT` is now required in production.** `config/settings_prod.py`
reassigns `SALT_KEY = fls_defaults.require_webhook_encryption_salt()`, which raises
`ImproperlyConfigured` at settings-import time when the `WEBHOOK_ENCRYPTION_SALT`
environment variable is unset, empty, or whitespace-only. Any production environment (or
any downstream prod-settings module that inherits from `config.settings_prod`) that boots
without this variable set will **crash-loop until it is supplied**.

This is intentional. Before this change, an unset salt silently fell back to a hardcoded
deterministic dev salt, which weakens the Fernet encryption of webhook secrets. The
fail-fast closes the "insecure dev salt silently reaches prod" path. Dev and test are
unaffected — they keep the deterministic fallback in `settings_base.py`.

There is no data migration concern: this ships ahead of the first real deployment, so no
existing production data is encrypted under the old dev-fallback salt.

If your CI or tests load `config.settings_prod` (e.g. a `check --deploy` job, or a test that
`importlib.reload`s the prod settings), you must add a dummy `WEBHOOK_ENCRYPTION_SALT` to
that environment the same way you already supply a dummy `SECRET_KEY`, or the load will
raise.

## Manual steps

1. **Set `WEBHOOK_ENCRYPTION_SALT`** to a non-empty secret value in every production
   environment before deploying this change. Treat it like `SECRET_KEY` (a real secret,
   sourced from your vault / secret store, not committed). Without it the app will not boot.

2. **Review the new `.env.example` keys** and add any you don't already have to your
   environment / vault key list:
   - `WEBHOOK_ENCRYPTION_SALT` (secret — see above; required in production)
   - `DJANGO_ADMIN_URL` (config; default `admin/`)
   - `HSTS_SECONDS` / `HSTS_INCLUDE_SUBDOMAINS` / `HSTS_PRELOAD` (config; defaults
     `3600` / `False` / `False` — already the code defaults, added for parity only)

   The last four are documentation/parity additions with safe defaults — no behaviour change
   if you leave them at their defaults.

3. **(Optional) Set `SENTRY_RELEASE`** if you use Sentry. A new Django system check
   (`freedom_ls_deployment.W001`) now emits a `Warning` on every `manage.py check` /
   `migrate` / `runserver` when `SENTRY_DSN` is set but `SENTRY_RELEASE` is blank, so your
   Sentry events stay untagged and regressions can't be tied to a deploy. Set
   `SENTRY_RELEASE` (e.g. the git SHA) to clear it. If you deliberately don't track releases,
   silence it via `SILENCED_SYSTEM_CHECKS = ["freedom_ls_deployment.W001"]`. This is only a
   Warning — it never blocks `migrate` or `runserver`.

No `migrate` step is required — this feature adds no models or migrations. No Tailwind
rebuild, package upgrade, or template review is needed.
