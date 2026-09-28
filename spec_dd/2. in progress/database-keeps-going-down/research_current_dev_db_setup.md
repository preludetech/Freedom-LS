# Research: how the dev database is set up today, and where the load comes from

Scope: read-only survey of this repo's config/scripts. No web research. All facts are cited to a
file path; anything not directly evidenced is explicitly flagged as inference.

## 1. How Postgres runs for dev

One shared Postgres 17 container, defined once, used by every worktree:

- `dev_db/docker-compose.yaml`: a single `postgres:17` service, `POSTGRES_USER=pguser`,
  `POSTGRES_PASSWORD=password`, `POSTGRES_DB=db`, bind-mounted to a single host path
  `${DB_DATA_PATH:-~/.lms_postges_dev_data}`, port `6543:5432` published to the host. There is a
  `mailpit` service alongside it.
- **No `max_connections`, `shared_buffers`, `work_mem` or any other `postgresql.conf` override.**
  Nothing in `dev_db/docker-compose.yaml` sets `command:` or mounts a custom config, so the
  container runs the stock image default, which is **`max_connections = 100`**. (Inference: the
  value 100 is the well-known `postgres:17` image default; the repo itself never states a number —
  the fact that no override exists at all is directly evidenced.)
- **No `shm_size`** override (stock default, small `/dev/shm` — relevant if queries ever spill to
  disk-based hash/sort operations, though not confirmed as a factor here).
- **No `restart:` policy** — a crashed container just stays down until someone runs
  `docker compose up` again, which matches the idea's "everything stalls" symptom.
- **No `healthcheck:`** on the dev compose file (contrast: `.github/workflows/tests.yml` *does* add
  a Postgres `healthcheck` with `pg_isready`, but that is CI-only, not dev).
- **No CPU/memory resource limits** (`deploy.resources`, `mem_limit`, etc.) on the dev `postgres`
  service.
- `dev_db/README.md` documents `docker compose up` to start it and `./cleanup_devdb.sh` +
  `docker-compose up` to reset it; `dev_db/cleanup_devdb.sh` does `docker kill dev_db_dbs_1`,
  `docker rm dev_db_dbs_1`, `sudo rm -r ./gitignore` — a manual, single-container reset with a
  hardcoded container name that does not match compose's actual naming for this project
  (`dev_db-postgres-1` under modern compose), so this script is likely stale/non-functional as
  written (inference from the mismatch, not confirmed by running it).
- `dev_db/docker-entrypoint-initdb.d/create-test-db.sql` creates one extra database, `test_db`,
  granted to `pguser` — a vestige of a pre-per-branch-DB convention (see §3); it runs once, at
  first container bring-up, and plays no role in the current per-branch scheme.

**One Postgres process, one fixed connection ceiling (default 100), shared by every worktree that
points at `127.0.0.1:6543`.** Nothing in the compose file scales that ceiling with the number of
worktrees.

## 2. How Django connects

- `config/settings_dev.py` (lines ~94-104): every worktree/branch builds its own `DATABASES["default"]`
  pointing at the same host/port (`127.0.0.1:6543`), same user/password (`pguser`/`password`), but a
  **branch-derived database name** — see §3. No `CONN_MAX_AGE`, no `CONN_HEALTH_CHECKS`, no `OPTIONS`
  are set here, so Django's defaults apply: `CONN_MAX_AGE = 0` (connection closed at the end of every
  request/command — dev does **not** hold long-lived pooled connections) and no psycopg connection
  pool is configured for dev.
- `config/settings_prod.py` (lines 80-83) explicitly sets `CONN_MAX_AGE` from
  `freedom_ls/deployment/settings_defaults.py:55` (`CONN_MAX_AGE: int = 60`) and
  `CONN_HEALTH_CHECKS = True` (line 56) — but this is production-only; dev never opts into
  connection reuse or a psycopg pool. `pyproject.toml` depends on `psycopg[binary]>=3.3.0` but no
  settings file wires up `django.db.backends.postgresql`'s `OPTIONS["pool"]` psycopg3 pooling
  anywhere in the repo (checked via grep for `pool`/`CONN_MAX_AGE`/`CONN_HEALTH`).
- Net effect for dev: **each request, each `manage.py` invocation, and (per §4) each pytest worker
  opens its own short-lived connection** rather than sharing a pool — so the connection count at any
  instant tracks concurrently-running requests/processes, not a fixed pool size, but a burst of
  concurrent activity (e.g. Playwright driving several sequential page loads while pytest workers are
  also mid-test) can still spike concurrent connections.

## 3. Per-worktree / per-branch database convention

- `freedom_ls/base/git_utils.py:151-159` (`branch_to_db_name`) derives a Postgres-safe DB name from
  the current git branch: lower-case, non-`[a-z0-9]` → `_`, truncated to 50 chars, prefixed
  `db_<branch>`. `config/settings_dev.py:91-92` calls this via `get_current_branch()` /
  `branch_to_db_name()` to set `DATABASES["default"]["NAME"]`, and sets
  `DATABASES["default"]["TEST"]["name"] = f"test_{db_name}"` (line 102).
- `SESSION_COOKIE_NAME` is also branch-scoped (`settings_dev.py:107`) "so branches don't invalidate
  each other's sessions" — confirming the multi-worktree-at-once design is deliberate and expected,
  not incidental.
- **Every worktree therefore gets two databases in the one shared Postgres instance: `db_<branch>`
  (dev) and `test_db_<branch>` (pytest) — never one shared database.** This is the direct cause of
  database-count growth (§6), separate from the connection-count issue.
- Creation: `claude_plugins/sdd/skills/git-worktree-setup/SKILL.md` (generic bare-repo/worktree
  mechanics) is overlaid by `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md`, which
  points at the **Setup script** configured in `.claude/sdd/config.md:10-11`:
  `Setup script: .claude/fls-dev/scripts/install_dev.sh`, `Teardown script:
  .claude/fls-dev/scripts/dev_db_delete.sh`.
  - `.claude/fls-dev/scripts/install_dev.sh` delegates to
    `claude_plugins/fls-dev/scripts/install_dev.sh`, which runs `git submodule update`,
    `rebuild_after_rebase.sh` (uv sync / npm i / tailwind build), then
    `dev_db_init.sh`, then `uv run manage.py migrate`.
  - `claude_plugins/fls-dev/scripts/dev_db_init.sh` independently re-derives the same
    branch→db-name mapping in shell (its own comment flags the duplication: "NOTE: … mirrors
    `freedom_ls.base.git_utils.branch_to_db_name` — keep them in sync") and does an idempotent
    `CREATE DATABASE IF NOT EXISTS` for both `db_<branch>` and `test_db_<branch>` against the shared
    container on `127.0.0.1:6543`.
  - **Teardown is opt-in, not automatic.** `claude_plugins/fls-dev/scripts/dev_db_delete.sh`
    correctly does `pg_terminate_backend` + `DROP DATABASE IF EXISTS` for both databases, but it
    **only runs when `/sdd:finish_worktree` Step 2 is executed** (`claude_plugins/sdd/commands/
    finish_worktree.md:75-82`, which reads the Teardown script path from `.claude/sdd/config.md`
    and runs it). A worktree that is abandoned, or whose branch is deleted manually, or that is
    still "in progress" (the common case per the idea) never has this script invoked, so its two
    databases persist in the shared Postgres instance indefinitely (see §6).

## 4. How tests use the DB

- `pyproject.toml` `[tool.pytest.ini_options]`: `DJANGO_SETTINGS_MODULE = "config.settings_dev"`,
  `addopts = "--strict-markers -m 'not ci_only and not weasyprint' --disable-socket
  --allow-hosts=127.0.0.1,::1 --cov …"`. **No `-n`/xdist flag and no `--reuse-db`/`--create-db` flag
  are baked into `addopts`.** `pytest-xdist` is a dev dependency (`pyproject.toml` dev group /
  `[dependency-groups].dev`) but is opt-in: `claude_plugins/django-stack/skills/testing/SKILL.md:45`
  states "Run the full suite in parallel locally with `uv run pytest -n auto` (xdist is opt-in, not
  baked into `addopts`)" — i.e. a developer or agent *can* fan out pytest workers against the one
  `test_db_<branch>` database, each xdist worker getting pytest-django's own per-worker DB clone
  (pytest-django's xdist support appends a worker suffix to the test DB name), multiplying the
  number of live test databases and connections for that single worktree while such a run is in
  flight. No file in this repo demonstrates this actually being invoked in an automated flow, so the
  extent of real-world `-n` usage is unconfirmed — flagged as inference.
- Because `--reuse-db` is never passed, pytest-django's default behaviour applies: **each bare
  `uv run pytest` invocation drops and recreates `test_db_<branch>` and re-runs every migration**
  before running any test (pytest-django default, not overridden anywhere in this repo — confirmed
  by absence, not by an explicit setting). This is itself a spike of DDL + connection activity at
  the start of every test run, on top of steady per-test connections.
- Playwright/live-server tests: `freedom_ls/tests/playwright_fixtures.py` — `logged_in_page` depends
  on `live_server` (pytest-django's threaded live server) plus `@pytest.mark.django_db
  (transaction=True)` (per the fixture's own docstring, lines 34-47), which "flush[es] the entire
  database at the end of every test". `transaction=True` tests do **not** run inside a single rolled-
  back transaction like ordinary `django_db` tests; the live server thread holds its own DB
  connection separate from the test thread's connection, so each Playwright test that touches the DB
  is at least two concurrent connections for its duration, plus a full-table flush per test.
- Who runs the suite, how often, how parallel:
  - `claude_plugins/django-stack/commands/rebase_main.md` Step 9 runs `uv run pytest -x -q` then a
    second full `uv run pytest -q` (sequential, no `-n`) — invoked by `/sdd:finish_worktree` Step 0
    and by the "Rebase command" hook run before every feature-branch SDD step
    (`.claude/sdd/config.md:19`), i.e. potentially several times per spec, once per worktree, each
    against that worktree's own `test_db_<branch>`.
  - `claude_plugins/fls-dev/agents/qa-bugfixer.md` Step 2/4 runs a single targeted test
    (`uv run pytest <path>::<test> -x`), then Step 5 runs the **whole suite**
    (`uv run pytest`, no `-x`, no `-n`) once per bug fixed — and `do_qa`-style flows fan out multiple
    `qa-bugfixer` agents (this file's own framing: "One bug, TDD … non-interactive; never spawns
    subagents" — the *orchestrator*, not this agent, is what fans bugs out in parallel, per the
    fan-out convention referenced in `claude_plugins/sdd/skills/claude-code-authoring/SKILL.md:67`
    and `claude_plugins/sdd/commands/*` "One worker per unit, in parallel" pattern). If a QA run
    fans out several `qa-bugfixer` agents concurrently *within one worktree*, each runs its own full
    `uv run pytest` sequentially against the same `test_db_<branch>` — a source of DB contention
    even without xdist, evidenced by the pattern but not by a file that names a concurrency count
    (inference on the actual fan-out width).
  - CI (`.github/workflows/tests.yml`) runs its own **ephemeral** Postgres service container per job
    (`unit-tests` and `playwright-tests` jobs each get a fresh `postgres:17` container with a
    health check), entirely separate from the shared dev container — CI is not a contributor to the
    "dev database keeps going down" symptom described in the idea.
- `conftest.py` (root) and `freedom_ls/conftest.py` set up fixtures (`mock_site_context`,
  `_isolate_media_root`, etc.) but do nothing that affects connection count directly.

## 5. Other connection sources

- `uv run manage.py runserver` (dev server) — `config/settings_base.py` includes
  `django_browser_reload` and (per `settings_dev.py`) `debug_toolbar`; Django's autoreloader runs
  **two processes** (a watcher + the actual server) when `runserver` is used without
  `--noreload`, each capable of opening its own DB connection during startup checks. With
  `CONN_MAX_AGE = 0` (§2) each process closes its connection after each request rather than holding
  one open, so a single idle `runserver` is not a large steady connection consumer — but a worktree
  actively being clicked through in a browser adds one short-lived connection per request.
- `TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}`
  (`config/settings_base.py:583-587`, confirmed for dev since `settings_dev.py` does not override
  `TASKS`) — dev runs background tasks **inline in the request**, so there is no separate worker
  process holding its own pool of connections in dev (unlike prod's `fls_run_worker`, per
  `freedom_ls/deployment/settings_defaults.py` `DATABASE_TASKS`). This rules out a dev task-worker
  process as a connection source.
- `django_watchfiles` is present in `pyproject.toml`'s dev deps but commented out in
  `INSTALLED_APPS` (`config/settings_dev.py:48`, `# "django_watchfiles",`) — not currently active.
- Every worktree runs its own copy of all of the above **independently and concurrently** — there is
  nothing in this repo that coordinates or caps the total number of `runserver`/`pytest` processes
  running across worktrees at once; the shared resource is only the one Postgres container.

## 6. Estimate: connections and accumulated databases at peak

**Connections per worktree at peak** (approximate, built from §2-§5; flagged as estimate/inference,
not measured):

- Idle `runserver` (autoreload, 2 processes, `CONN_MAX_AGE=0`): ~0 held connections when idle, 1-2
  transient connections per request while in use.
- `uv run pytest` without `-n`: effectively 1 connection for the main test run, briefly 2+ during a
  Playwright/`live_server` test (test thread + live-server thread).
- `uv run pytest -n auto` (opt-in per §4): up to `N` = CPU core count workers, each pytest-django
  xdist worker with its own cloned test DB and its own connection(s) — on an 8-16 core dev machine
  that is potentially **8-16 simultaneous connections from one worktree alone**, all against
  Postgres's default `max_connections = 100` (§1).
- A `do_qa`-style fan-out of several `qa-bugfixer` agents *within* one worktree, each running a full
  `uv run pytest` (§4), stacks additional concurrent connections on top of the above, bounded only by
  how many agents the orchestrator spawns at once (not established by any file read here).

**Multiplied across worktrees:** this workspace currently has **13 sibling worktree directories
under `/home/sheena/workspace/lms/freedom-ls-worktrees/`** (in addition to `main`) — e.g.
`xapi_implementation`, `content_snapshots`, `compliance-form-randomization`,
`auto-run-tailwind-watch`, `test-organisation-and-hygene-3-enforcement-checks`,
`educator-interface-4-panel-framework-components`, `in-app-feedback`,
`educator-interface-2-panel-framework-tables`, `educator-interface-3-panel-framework-dialogs`,
`better-looking-notifications`, `educator-interface-5-permissions`,
`user-communication-3-messaging-policy`,
`test-organisation-and-hygene-2-sdd-review-and-boy-scout` — directly observed via directory listing,
each with its own `.venv`, hence plausibly each a live or recently-live worktree with its own
`db_<branch>` / `test_db_<branch>` pair. **If even a handful of these are mid-QA at once (each
running `uv run pytest`, one possibly with `-n auto`, plus a `runserver` being clicked through),
the shared container's default 100-connection ceiling is easily within reach** — this is the
mechanism-level explanation for the idea's "gets overloaded and dies" symptom, though the exact
trigger has not been captured in a log or error message in anything read here (inference).

**Number of accumulated databases:** with 14 possible worktrees (13 + `main`) each holding
`db_<branch>` + `test_db_<branch>`, that is up to **~28 databases** in the one Postgres data
directory today, growing by 2 every time a new worktree is set up (§3) and shrinking only when
`/sdd:finish_worktree` actually runs its teardown step for that branch. Since teardown is opt-in and
easy to skip (abandoned branches, manually deleted worktrees, worktrees still "in progress"), the
database count is a one-way ratchet in practice unless someone runs the teardown script by hand
(inference: no file read here confirms any of the 13 sibling worktrees are actually stale rather
than active, but the mechanism for accumulation is directly evidenced in §3).

## 7. Likely failure modes (flagged as inference vs. fact)

- **Fact (directly evidenced):** the dev Postgres container has no `max_connections` override
  (stock default, commonly 100), no resource limits, and no `restart:` policy — so if it is
  overwhelmed or OOM-killed, it does not come back on its own; someone has to notice and run
  `docker compose up` again. This matches "gets overloaded and dies then everything stalls" in the
  idea almost exactly.
- **Inference (plausible mechanism, not captured in a log):** connection exhaustion. Many worktrees
  each running `pytest` (optionally `-n auto`), `runserver`, and/or Playwright's live-server tests
  concurrently against one 100-connection Postgres instance is a straightforward way to hit
  `FATAL: sorry, too many clients already` or similar, which — depending on how the application and
  test harness handle a refused connection — can look like "the database died."
  - Compare and contrast: Playwright's `transaction=True` tests holding two connections per test for
    the duration of a browser-driven test (slower, by wall clock, than a normal transactional test)
    increases the odds of an overlap window where many such tests are mid-flight across worktrees at
    once (inference, stacking on the fact in §4).
- **Inference:** memory/CPU contention on the host, rather than the connection cap itself. With no
  `shared_buffers` tuning and no memory limit on the container, a `pytest` xdist run's DDL-heavy
  startup (drop/recreate + migrate the test DB every bare `uv run pytest`, §4) run in parallel by
  several worktrees at once could be enough I/O and CPU pressure to make Postgres unresponsive or
  get OOM-killed by the host, independent of the connection count. Not confirmed by any resource
  metrics or logs read here.
- **Inference:** database-count bloat (§6) is a secondary, slower-burning contributor — each stale
  `db_<branch>`/`test_db_<branch>` pair costs disk and a small amount of catalog/connection-pool
  overhead, but is unlikely by itself to be the proximate cause of a crash; it is more likely a
  housekeeping problem that compounds the connection-pressure mechanism above (more worktrees
  plausibly correlates with more stale databases, but the two are not the same mechanism).
- **Not evidenced either way:** whether the container has actually been OOM-killed, hit
  `max_connections`, or failed for some other reason (disk full under `~/.lms_postges_dev_data`,
  a crashed migration, etc.) — no log file, crash report, or incident note for this specific
  recurring failure was found in the repo. Any implementation plan should include capturing the
  actual failure signature (`docker logs`, `pg_stat_activity` at time of failure) before committing
  to one fix, since §1 and §4 each point at a different plausible root cause.

status: ok
