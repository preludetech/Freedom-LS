---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/accounts/templates/accounts/lockout.html  # new page, extends allauth/layouts/entrance.html
requires_settings_change: true
changed_settings:
  - TRUSTED_PROXY_IP_HEADER  # hard: meaning changed from a request.META key to an HTTP header name
  - ALLAUTH_TRUSTED_CLIENT_IP_HEADER  # hard: new in settings_prod; naming a header your edge does not send 403s every login
  - CACHES  # hard: production is now DatabaseCache; freedom_ls_deployment.E005 enforces the table at check --deploy
  - AXES_LOCKOUT_PARAMETERS  # optional: now two rules, the nested pair plus username alone
  - AXES_CLIENT_IP_CALLABLE  # optional
  - AXES_LOCKOUT_TEMPLATE  # optional
  - AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT  # optional
  - ACCOUNT_RATE_LIMITS  # optional: gains a login_failed entry
  - WORKER_HEARTBEAT_PATH  # optional
  - WORKER_HEARTBEAT_MAX_AGE_SECONDS  # optional: narrowed, now bounds only the quiet poll loop and no longer a task's runtime
  - HOUSEKEEPING_HEARTBEAT_PATH  # optional
  - HOUSEKEEPING_UNPICKED_TASK_MAX_AGE_SECONDS  # optional
  - HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS  # optional
  - WORKER_MAX_TASK_SECONDS  # optional: new, caps how long the heartbeat is held up for one task
  - HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS  # optional: new, closes reports stranded in RUNNING
  - SILENCED_SYSTEM_CHECKS  # optional: three new ids, freedom_ls_deployment.E005 and E006 and freedom_ls_accounts.E003
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: prepare-to-deploy

## Breaking changes

**`TRUSTED_PROXY_IP_HEADER` changed meaning.** It used to hold a `request.META` key
(`"HTTP_X_FORWARDED_FOR"`); it now holds a plain HTTP header name (`"CF-Connecting-IP"`).
`freedom_ls.accounts.utils.get_client_ip` reads `request.headers` rather than `request.META`, so a
project that still sets the old spelling gets no match and silently falls back to `REMOTE_ADDR` —
no error, just wrong client IPs in `LegalConsent` records and django-axes lockout keys. Rewrite the
value if you set it. A system check, `freedom_ls_accounts.E003`, now catches the old spelling: any
value starting with `HTTP_` is an error, raised on `runserver` as well as under `check --deploy`.

The header must be one your edge **sets** rather than appends, so it carries exactly one address.
The value is no longer comma-split, and a value that is not a single valid address (an appended
`X-Forwarded-For`, say) is distrusted entirely and falls back to `REMOTE_ADDR`.

**`manage.py create_site` is gone.** Any script, runbook or CI step invoking it now fails with an
unknown-command error. The empty `create_site_superuser` stub next to it was removed at the same
time, but it was a zero-byte file and never a working command, so nothing can have called it. Use
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

**`AXES_LOCKOUT_PARAMETERS` takes two independent rules**,
`[["ip_address", "username"], "username"]`. The nested entry needs address *and* username together,
so one person's mistakes cannot lock out everyone behind a shared NAT. The flat `"username"` entry
locks on the account alone, which is what caps a spray that rotates source addresses — the only cap
on the Django admin login, which `ACCOUNT_RATE_LIMITS` does not wrap. If you override this setting,
keep both: the nested entry alone leaves `/admin/login/` uncapped, and a bare flat pair
(`["ip_address", "username"]`) is a denial of service on a shared NAT.
`ACCOUNT_RATE_LIMITS` gains `"login_failed": "10/m/ip,5/5m/key"` as the faster layer above the
lockout; it merges over allauth's defaults, so overriding the dict wholesale drops it.

## Manual steps

1. **Add `createcachetable` to your deploy sequence**, before the app starts serving:
   `manage.py createcachetable`. It is idempotent. Skip only if you set your own non-database
   `CACHES` in production.
2. **Run `manage.py check --deploy`** after deploying. It gains two ids:
   `freedom_ls_deployment.E005` (database-backed cache alias whose table is missing) and
   `freedom_ls_deployment.E006` (the two client-IP header settings name different headers). A build
   container with no database reachable returns no error from E005 rather than a false one. The
   third new id, `freedom_ls_accounts.E003`, is deliberately not deploy-gated: it fires on
   `runserver`, `migrate` and plain `check` as well, so a carried-over `HTTP_`-prefixed header value
   is caught in development rather than at deploy time.

   If you have never run `check --deploy` — FLS's own update command wrongly said a plain `check`
   covered everything — expect the four pre-existing media-alias checks
   (`freedom_ls_deployment.E001` through `E004`) to fire alongside the two new ones. Those are
   long-standing storage misconfigurations surfacing for the first time, not something this change
   broke. `docs/deployment-security-checklist.md` has a table of what each id reports.
3. **Set the edge header.** In production, `TRUSTED_PROXY_IP_HEADER` and
   `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` are both read from the `TRUSTED_CLIENT_IP_HEADER`
   environment variable, defaulting to `"CF-Connecting-IP"`
   (`freedom_ls.deployment.settings_defaults.TRUSTED_CLIENT_IP_HEADER`) — the header a Cloudflare
   tunnel sets. Naming a header removes allauth's own fallback to `REMOTE_ADDR`, so if your edge
   sets a different one, every login, signup and password reset answers 403. Set the environment
   variable to whichever header your edge sets; no code change is needed. `freedom_ls_deployment.E006`
   fails `check --deploy` if the two settings ever name different headers, but no check can tell
   whether your edge actually sends the one you named — verify that with a real login. Do **not**
   set `ALLAUTH_TRUSTED_PROXY_COUNT`; it selects the `X-Forwarded-For` path instead. Make sure no
   route reaches the origin without traversing the proxy, or a client sets the header itself and
   picks its own lockout key.
4. **Swap your process commands.** Replace bare `manage.py db_worker` with
   `manage.py fls_run_worker` (all queues, heartbeat file, watchdog that exits the process when the
   main thread wedges). Note the queue change: `db_worker` defaults to the `default` queue alone,
   while `fls_run_worker` consumes every queue. Replace any scheduled `prune_db_task_results` with
   `manage.py fls_run_housekeeping`, which runs five sweeps in one pass: the task-result prune,
   `clearsessions`, a late-unpicked-task check, an orphaned-task reap and an orphaned cohort-report
   reap. `db_worker` is still available if you need its full flag surface.

   `fls_run_worker` reuses django-tasks-db's own work loop line for line, so the `==0.12.0` pin in
   FLS's `pyproject.toml` is now load-bearing and a test asserts it. Bumping that package fails the
   FLS suite on purpose, to force someone to re-check the copied loop against the new upstream.

   Watch what you alert on. The command exits non-zero for two different reasons: a sweep of its
   own failed, or a sweep found something wrong elsewhere. A queue full of unpicked tasks is the
   second kind, so a missing *worker* turns the *housekeeping* cron red. That is deliberate, since
   nothing else is watching the queue, but an alert that reads "housekeeping failed" will point at
   the wrong container. Only the first kind withholds the heartbeat file.
5. **Wire the heartbeats.** `fls_run_worker` touches `WORKER_HEARTBEAT_PATH` (default
   `/tmp/heartbeat`) once per poll between tasks, and every 30 seconds while a task is running, up
   to the cap in step 6; `fls_run_housekeeping` touches `HOUSEKEEPING_HEARTBEAT_PATH`
   (default `/tmp/housekeeping-heartbeat`) on a completed run. Point your container healthchecks at
   those files' mtimes. Keep the two paths distinct: on one shared file a daily sweep keeps a dead
   worker's heartbeat fresh and holds the probe green over it.
6. **Tune the windows if your tasks run long.** Two settings bound a task, and they mean different
   things. `WORKER_HEARTBEAT_MAX_AGE_SECONDS` (default 300) is how long the *poll loop* may go
   quiet before the watchdog decides the worker has wedged. `WORKER_MAX_TASK_SECONDS` (default
   1800) is how long a *single task* may run: the worker holds its heartbeat up for the whole of a
   task it is genuinely working on, up to that cap, and past it lets the heartbeat go stale on
   purpose so the watchdog kills a hung task. Raise `WORKER_MAX_TASK_SECONDS` if your longest
   legitimate job needs more than half an hour; leave the heartbeat window alone.

   A task's true maximum life is the sum of the two plus one 30-second watchdog poll, so 2130
   seconds at the defaults. Both orphan windows have to clear that sum, or housekeeping closes rows
   a live worker is still inside. `HOUSEKEEPING_ORPHANED_TASK_MAX_AGE_SECONDS` (default 3600) is
   how long a worker may hold a claimed task before housekeeping marks the row failed, and
   `HOUSEKEEPING_ORPHANED_REPORT_MAX_AGE_SECONDS` (default 3600) does the same for a cohort report
   left rendering. That second one matters more than its default suggests: only one report per
   cohort may be pending or running at a time, so a report stranded by a dead worker blocks that
   cohort from requesting another until the sweep closes it.

   Reaped tasks are marked `FAILED` with `exception_class_path` naming `OrphanedTaskError` and are
   never requeued, so a task that is not idempotent is not silently run twice. A reaped report is
   marked failed with an explanatory `error_message` and is not re-rendered; the educator asks for
   it again.
7. **Review the new lockout page.** `freedom_ls/accounts/templates/accounts/lockout.html` is new
   (`AXES_LOCKOUT_TEMPLATE`), served when django-axes refuses a locked-out sign-in. It extends
   `allauth/layouts/entrance.html`, so a project overriding that layout picks up its own chrome
   automatically — check it renders under your theme. It introduces no Tailwind utility class that
   FLS templates did not already use, so no CSS rebuild is needed. The page is served with HTTP
   429, which is django-axes' default and what your monitoring will see for a locked-out sign-in.
8. **No migrations.** Nothing in this change adds or alters a model.
