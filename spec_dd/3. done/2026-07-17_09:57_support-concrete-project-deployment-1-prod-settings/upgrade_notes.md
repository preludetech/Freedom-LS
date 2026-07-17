---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - SECRET_KEY            # now mandatory — hard-fails at boot if missing/empty
  - SECURE_PROXY_SSL_HEADER
  - LOGGING
  - DATABASES.default.OPTIONS     # sslmode, from DB_SSLMODE env var
  - DATABASES.default.CONN_MAX_AGE
  - DATABASES.default.CONN_HEALTH_CHECKS
  - DB_SSLMODE            # new env var (default "prefer")
  - DB_CONN_MAX_AGE       # new env var (default 60)
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: P0 production settings defaults + importable `settings_defaults` module

This change adds `freedom_ls/deployment/settings_defaults.py` — a pure, Django-free module
of P0 deployment-settings primitives (flat constants + small functions) — and migrates this
repo's reference `config/settings_prod.py` to *import and assign* those primitives instead of
hard-coding literals. Downstream projects own their own `config/settings_prod.py`, so pulling
the submodule does **not** apply these fixes automatically: you must migrate your own
`settings_prod.py` to consume the new primitives (one time), and set two new env vars.

No models, migrations, templates, URLs, packages, or Tailwind sources changed.

## Breaking changes

- **`SECRET_KEY` is now mandatory.** The reference config replaced
  `SECRET_KEY = os.getenv("SECRET_KEY", "")` with `fls_defaults.require_secret_key()`, which
  raises at settings-import time (Gunicorn boot → visible crash-loop) when `SECRET_KEY` is
  missing, empty, or whitespace-only. Previously an unset key silently booted green and then
  broke session/CSRF signing on the first request. **Any deployment relying on the old empty
  default will fail to boot after adopting the import form.** Ensure a real non-empty
  `SECRET_KEY` is present in the environment before deploying.

- **`SECURE_PROXY_SSL_HEADER` is now set as a hard default**
  (`("HTTP_X_FORWARDED_PROTO", "https")`). This is correct only behind a TLS-terminating proxy
  that forwards `X-Forwarded-Proto` (the target Caddy + Cloudflare **Full (strict)** topology).
  The five trust preconditions are documented beside the primitive in `settings_defaults.py`.
  If your topology does not terminate TLS at a trusted proxy, review before adopting — a proxy
  that forwards an attacker-controllable `X-Forwarded-Proto` would let `request.is_secure()` be
  spoofed. This is distinct from `TRUSTED_PROXY_IP_HEADER` (the client-IP header), which is
  unchanged.

## Manual steps

1. **Migrate your project's `config/settings_prod.py` to the import-and-assign form** so future
   P0 settings fixes reach you on a submodule SHA bump rather than by copy-editing. Run
   `/fls:concrete:update_fls` against your project, or apply by hand:
   - `from freedom_ls.deployment import settings_defaults as fls_defaults`
   - `SECRET_KEY = fls_defaults.require_secret_key()`
   - `SECURE_PROXY_SSL_HEADER = fls_defaults.SECURE_PROXY_SSL_HEADER`
   - `LOGGING = fls_defaults.build_logging_config(log_dir=BASE_DIR / "logs")` (keep `log_dir`
     for now — stdout-only logging is deferred until the Docker `json-file` log caps land; see
     below)
   - `DATABASES["default"]["OPTIONS"] = fls_defaults.database_ssl_options(os.getenv("DB_SSLMODE", "prefer"))`
   - `DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", fls_defaults.CONN_MAX_AGE)`
   - `DATABASES["default"]["CONN_HEALTH_CHECKS"] = fls_defaults.CONN_HEALTH_CHECKS`
   - Delete any redundant `TASKS` block in your `settings_prod.py` — `ImmediateBackend` is
     already inherited from `settings_base.py` as the deliberate default.

2. **Set the new environment variables** (both have safe defaults, but document them for your
   deployment):
   - `DB_SSLMODE` — default `prefer`. Use `disable` for the shipped same-host containerised
     Postgres (no TLS listener); reserve `require`/`verify-full` for external/managed databases.
     For same-host Postgres the control that matters is not publishing port `5432`, not
     `sslmode`.
   - `DB_CONN_MAX_AGE` — default `60`. Persistent connection lifetime in seconds; recommended
     60–300s, never unlimited. `CONN_HEALTH_CHECKS` is on, so stale sockets after a `db`
     restart are recycled.
   - Confirm `SECRET_KEY` is set and non-empty (see Breaking changes).

3. **Do not flip logging to stdout-only yet.** `build_logging_config()` defaults to
   stdout/stderr with no file handlers, but the reference config still passes `log_dir` to keep
   today's rotating-file behaviour and the `logs/` bind mount. Dropping `log_dir` (and the bind
   mount) relocates the disk-fill risk onto uncapped Docker `json-file` logs — only safe once
   the per-service `max-size`/`max-file` caps ship (a later spec in this effort).

4. **No `migrate`, no Tailwind rebuild, no package/npm install** are required for this change.
