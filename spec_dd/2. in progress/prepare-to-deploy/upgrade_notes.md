---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/accounts/templates/accounts/lockout.html  # new page, extends allauth/layouts/entrance.html
requires_settings_change: true
changed_settings:
  - TRUSTED_PROXY_IP_HEADER  # hard: meaning changed from a request.META key to an HTTP header name
  - ALLAUTH_TRUSTED_CLIENT_IP_HEADER  # hard: new in settings_prod; without it allauth 403s every login behind an edge
  - CACHES  # hard: production is now DatabaseCache; freedom_ls_deployment.E005 enforces the table at check --deploy
  - AXES_LOCKOUT_PARAMETERS  # optional: now the nested [["ip_address", "username"]] form
  - AXES_CLIENT_IP_CALLABLE  # optional
  - AXES_LOCKOUT_TEMPLATE  # optional
  - AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT  # optional
  - ACCOUNT_RATE_LIMITS  # optional: gains a login_failed entry
  - WORKER_HEARTBEAT_PATH  # optional
  - WORKER_HEARTBEAT_MAX_AGE_SECONDS  # optional
  - HOUSEKEEPING_HEARTBEAT_PATH  # optional
  - HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS  # optional
  - HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS  # optional
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: prepare-to-deploy

## Breaking changes

**`TRUSTED_PROXY_IP_HEADER` changed meaning.** It used to hold a `request.META` key
(`"HTTP_X_FORWARDED_FOR"`); it now holds a plain HTTP header name (`"X-Real-IP"`).
`freedom_ls.accounts.utils.get_client_ip` reads `request.headers` rather than `request.META`, so a
project that still sets the old spelling gets no match and silently falls back to `REMOTE_ADDR` —
no error, just wrong client IPs in `LegalConsent` records and django-axes lockout keys. Rewrite the
value if you set it.

The header must be one your edge **sets** rather than appends, so it carries exactly one address.
The value is no longer comma-split, and a value that is not a single valid address (an appended
`X-Forwarded-For`, say) is distrusted entirely and falls back to `REMOTE_ADDR`.

**`manage.py create_site` and `manage.py create_site_superuser` are gone.** Any script, runbook or
CI step invoking either now fails with an unknown-command error. Use
`manage.py setup_initial_prod_data <admin_email> [--domain ...] [--site-name ...]` instead. It
creates the `Site` (keyed on domain, not name), the staff superuser bound to that `Site`, and a
verified primary allauth `EmailAddress`. It is safe to run twice, never resets an existing
password, and prints the generated password once to stdout and nowhere else.

**Do not define your own `setup_initial_prod_data` command.** Django's `get_commands()` resolves a
duplicate name silently in favour of the app earliest in `INSTALLED_APPS`, and FLS apps sit earlier
than yours, so FLS's would win without warning. Your own worker and housekeeping wrappers are safe:
FLS deliberately names its commands `fls_run_worker` and `fls_run_housekeeping`.

**Production now sets `CACHES`.** `config/settings_prod.py` sets
`CACHES = fls_defaults.DATABASE_CACHES` — a `DatabaseCache` on the table `django_cache_table`. No
migration creates that table. Miss `createcachetable` and nothing fails until the first request
that touches the cache (allauth's login and signup rate limiting does, on every attempt), which
then raises `ProgrammingError` from inside the auth flow. A new system check,
`freedom_ls_deployment.E005`, catches this at `manage.py check --deploy` time. If you set your own
`CACHES` in production, this does not apply to you.

**`AXES_LOCKOUT_PARAMETERS` takes the nested form** `[["ip_address", "username"]]`, so a lockout
now needs address *and* username together rather than locking on either alone. If you override this
setting, the flat form is a denial of service on a shared NAT — take the nested form too.
`ACCOUNT_RATE_LIMITS` gains `"login_failed": "10/m/ip,5/5m/key"` as the faster layer above the
lockout; it merges over allauth's defaults, so overriding the dict wholesale drops it.

## Manual steps

1. **Add `createcachetable` to your deploy sequence**, before the app starts serving:
   `manage.py createcachetable`. It is idempotent. Skip only if you set your own non-database
   `CACHES` in production.
2. **Run `manage.py check --deploy`** after deploying. It now includes
   `freedom_ls_deployment.E005` (database-backed cache alias whose table is missing). A build
   container with no database reachable returns no error rather than a false one.
3. **Set the edge header.** In production, `TRUSTED_PROXY_IP_HEADER` and
   `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` both default to `"X-Real-IP"`
   (`freedom_ls.deployment.settings_defaults.TRUSTED_CLIENT_IP_HEADER`). Naming a header removes
   allauth's own fallback to `REMOTE_ADDR`, so if your edge does not set `X-Real-IP`, every login,
   signup and password reset answers 403 — point both settings at whichever header your edge does
   set. Do **not** set `ALLAUTH_TRUSTED_PROXY_COUNT`; it selects the `X-Forwarded-For` path
   instead. Make sure no route reaches the origin without traversing the proxy, or a client sets
   the header itself and picks its own lockout key.
4. **Swap your process commands.** Replace bare `manage.py db_worker` with
   `manage.py fls_run_worker` (all queues, heartbeat file, watchdog that exits the process when the
   main thread wedges). Replace any scheduled `prune_db_task_results` with
   `manage.py fls_run_housekeeping`, which runs the task-result prune, `clearsessions`, a
   late-unpicked-task check and an orphaned-task reap in one pass and exits non-zero on failure.
   `db_worker` is still available if you need its full flag surface.
5. **Wire the heartbeats.** `fls_run_worker` touches `WORKER_HEARTBEAT_PATH` (default
   `/tmp/heartbeat`) once per poll; `fls_run_housekeeping` touches `HOUSEKEEPING_HEARTBEAT_PATH`
   (default `/tmp/housekeeping-heartbeat`) on a completed run. Point your container healthchecks at
   those files' mtimes. Keep the two paths distinct: on one shared file a daily sweep keeps a dead
   worker's heartbeat fresh and holds the probe green over it.
6. **Tune the windows if your tasks run long.** `WORKER_HEARTBEAT_MAX_AGE_SECONDS` (default 300) is
   the longest a task may run before the watchdog kills the worker holding it.
   `HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS` (default 3600) is how long a worker may hold a
   claimed task before housekeeping marks the row failed — set it below your longest legitimate
   task runtime and you close live work. Keep it at or above `WORKER_HEARTBEAT_MAX_AGE_SECONDS`.
   Reaped tasks are marked `FAILED` with `exception_class_path` naming `OrphanedTaskError` and are
   never requeued, so a task that is not idempotent is not silently run twice.
7. **Review the new lockout page.** `freedom_ls/accounts/templates/accounts/lockout.html` is new
   (`AXES_LOCKOUT_TEMPLATE`), served when django-axes refuses a locked-out sign-in. It extends
   `allauth/layouts/entrance.html`, so a project overriding that layout picks up its own chrome
   automatically — check it renders under your theme. It introduces no Tailwind utility class that
   FLS templates did not already use, so no CSS rebuild is needed.
8. **No migrations.** Nothing in this change adds or alters a model.
