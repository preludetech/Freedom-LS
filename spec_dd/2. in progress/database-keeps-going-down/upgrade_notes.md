---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: the dev database stays up

This change is about the shared dev Postgres server and the dev tooling around it. It adds no models,
templates, settings keys, Python or npm packages, or Tailwind sources to the installed `freedom_ls`
package. The changes a downstream project picks up come through the FLS checkout it uses for
`dev_db/` and `claude_plugins/` (the `fls-dev` and `ds` plugins):

- `dev_db/docker-compose.yaml` now runs as compose project `fls_dev_db`, with its data in the named
  volume `fls_dev_db_pgdata` instead of the `~/.lms_postges_dev_data` bind mount (`DB_DATA_PATH` no
  longer applies). It restarts itself, has a healthcheck, and is sized for a 4 GiB engine. It runs
  with `fsync`, `synchronous_commit` and `full_page_writes` off, so dev data can be lost if the
  container crashes. `cleanup_devdb.sh` is now a full reset: it asks you to confirm, then destroys
  the volume and starts a fresh server.
- `dev_db_init.sh` creates a non-superuser role `fls_dev` (password `password`, `CREATEDB`, with
  `idle_in_transaction_session_timeout = '15min'`) if it doesn't exist yet. It creates or re-owns
  the per-branch dev and test databases as `fls_dev`, and writes a worktree stamp
  (`COMMENT ON DATABASE`) on `db_<branch>`.
- `rebuild_after_rebase.sh` now runs `dev_db_init.sh`, and `install_dev.sh` no longer calls it
  separately. Every rebase therefore makes sure the role and the databases exist.
- `dev_db_delete.sh` also drops the `test_db_<branch>_gwN` databases that xdist workers leave
  behind.
- The `ds` plugin's `.mcp.json` pins `@playwright/mcp@0.0.83` and adds `--idle-timeout 600000`.
  There is a new reaper for leaked Playwright MCP processes:
  `claude_plugins/django-stack/scripts/reap_playwright_mcp.sh`. Run it with no argument to list
  them, or with `--kill` to end them.
- `freedom_ls/tests/playwright_fixtures.py` overrides pytest-playwright's session `playwright`
  fixture so that it closes Django's DB connections before Playwright stops. A project that
  re-exports `freedom_ls.conftest` gets this automatically.

## Breaking changes

- **The old dev server can't run next to the new one.** Both bind port 6543. Once the new server is
  up, `docker compose up` from an older `dev_db/` fails with a port conflict. Nothing carries over
  from the bind-mounted data directory, and that includes other projects' databases on the same
  server.
- **New portable test.**
  `freedom_ls/base/tests/test_dev_tooling_disabled_in_tests.py` has no marker, so it runs in a
  downstream's `-m "not playwright and not fls_internal and not ci_only and not weasyprint"` run.
  It fails if `django_browser_reload` is in `INSTALLED_APPS`, or
  `django_browser_reload.middleware.BrowserReloadMiddleware` is in `MIDDLEWARE`, while tests run.
  If your dev settings add them for tests too, add them only when not testing, as
  `config/settings_dev.py` now does. Its `/__reload__/events/` stream holds a DB connection open,
  and in Playwright tests that connection can make the test database's `DROP DATABASE` fail.

## Manual steps

1. **Switch to the new server** once per machine, after updating your FLS checkout:
   1. `docker compose -p dev_db down` stops the old server.
   2. `docker compose up -d` from the updated `dev_db/` starts the new one.
   3. In each worktree, rebase onto the updated FLS (the rebase runs `dev_db_init.sh`), or run
      `.claude/fls-dev/scripts/install_dev.sh`, to recreate its databases.
   4. Optional: delete `~/.lms_postges_dev_data`. Its files belong to uid 999, so this needs `sudo`.
2. **No settings change is required.** Your dev settings keep working as `pguser`, which is still
   the superuser. Optional: switch `DATABASES["default"]["USER"]` to `"fls_dev"` to get the
   connection-slot reservation and the idle-in-transaction timeout. If you switch, any tables
   already in your per-branch databases belong to `pguser`. Run
   `.claude/fls-dev/scripts/dev_db_delete.sh` and then `.claude/fls-dev/scripts/install_dev.sh` in
   each worktree to recreate them.
3. **Optional, to install the reaper wrapper:** re-run `/ds:init`. It adds
   `.claude/ds/scripts/reap_playwright_mcp.sh` and leaves your existing files alone.
4. **Optional test-run settings** that FLS adopted in its own repo and a downstream can copy:
   - `"TEST": {"NAME": ..., "TEMPLATE": "template0"}`.
   - An `application_name` in `OPTIONS` (see `build_application_name` in `config/settings_dev.py`).
   - A `pytest_xdist_auto_num_workers` hook in the root `conftest.py` that caps `-n auto` at 4.
   - `pytest-timeout` with `timeout = 300`.

   The FLS-repo tools `uv run python -m dev_db.diagnose` and `uv run python -m dev_db.stale_dbs`
   run from an FLS checkout, not from a downstream project root.
