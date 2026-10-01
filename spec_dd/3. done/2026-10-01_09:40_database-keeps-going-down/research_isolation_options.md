# Research: options for a dev/test Postgres setup that survives many concurrent worktrees

## Current state (from the repo)

- `dev_db/docker-compose.yaml` runs **one** `postgres:17` container for the whole machine, published on host port 6543, with a single bind-mounted volume (`~/.lms_postges_dev_data`). No `shm_size`, no memory/CPU limits, no `restart:`, no `healthcheck`, no tuned `command:` flags — it's the stock image with defaults (`max_connections=100`, default `shared_buffers`, default 64 MB `/dev/shm`).
- Per the `fls-dev:git-worktree-setup` skill, every worktree gets its **own database** on that one server (`db_<sanitized_branch>`), derived in `config/settings_dev.py` from `get_current_branch()`. `install_dev.sh` → `dev_db_init.sh` creates it. Test runs use Django's own `test_<db_name>` convention (`TEST: {"name": f"test_{_db_name}"}`).
- No connection pooling anywhere in dev (`settings_dev.py` sets no `OPTIONS`, `CONN_MAX_AGE`, or `pool`). `settings_prod.py` does set `CONN_MAX_AGE`/`CONN_HEALTH_CHECKS` from `freedom_ls.deployment.settings_defaults`, so there's already a documented "downstream project configures via env" pattern to follow if pooling knobs get added.
- `pytest-xdist>=3.8.0` is already a dependency and `addopts` in `pyproject.toml` doesn't cap workers (`-n` is presumably passed ad hoc or defaults to serial). No `--reuse-db` in `addopts`.
- FLS is installed into downstream Django projects (it's a library, not just this monorepo), so anything that changes downstream projects' required infrastructure (e.g. "you must run PgBouncer", "you must run one Postgres per branch") is a bigger ask than something that only affects this repo's own `dev_db/docker-compose.yaml` and CLAUDE-Code-driven worktree workflow.

With the isolation-by-database convention already in place, the actual failure mode described in the idea ("gets overloaded and dies") is most plausibly: (a) `max_connections` (100 default) exhausted by N worktrees × (runserver + pytest-xdist workers + Playwright) each holding open connections, and/or (b) the single container's default memory/shared-buffers/`/dev/shm` getting starved when several `pytest-xdist` workers run `CREATE DATABASE`/heavy test suites concurrently, and/or (c) no `restart:` policy so a single OOM-killed or crashed Postgres process takes every worktree down with it until someone notices and runs `docker compose up` again.

---

## Option 1 — Harden the one shared Postgres container

**What it is:** Keep the current one-container, many-databases model, but raise `max_connections`, tune `shared_buffers`/`work_mem`, raise `shm_size`, add memory/CPU limits (so Postgres itself doesn't get OOM-killed by something else on the box), add `restart: unless-stopped` + a `healthcheck`, and optionally apply dev-only durability trade-offs (`fsync=off`, `synchronous_commit=off`, `full_page_writes=off`) since a throwaway dev DB doesn't need crash durability.

**Fixes:** connection exhaustion (raising `max_connections`), the container not coming back after a crash (`restart:` + healthcheck), shared-memory errors under parallel query/VACUUM load (`shm_size`), and general dev-loop speed (durability flags — one project reported dropping a suite from ~1300–1700s to ~41s with `fsync=off`/`synchronous_commit=off`/`full_page_writes=off`, and 30–37% more from adding tmpfs on top). Docker's docs and the `postgres` image caveats note `shared_buffers` should roughly align with `shm_size` or you get shared-memory failures under parallel workers.

**Doesn't fix:** it's still a *single point of failure and a single resource pool* — one worktree's runaway migration, `pytest-xdist` storm, or a `VACUUM FULL` can still starve every other worktree even with generous limits; it just raises the ceiling rather than removing the shared-fate problem. Raising `max_connections` also raises Postgres's own per-connection memory overhead, so it interacts with `shared_buffers`/`work_mem` sizing — tuning has to be done together, not as one isolated knob.

**Cost:** low — it's a docker-compose edit plus documenting the new `dev_db/docker-compose.yaml`; no new services, no code changes, no downstream impact since it's purely this repo's local dev infra file. No ongoing maintenance beyond periodically revisiting the numbers as worktree count grows.

**Effect on single-worktree devs:** none negative; a healthcheck + `restart:` is a pure improvement, and generous connection/memory headroom for a single worktree changes nothing they notice.

**How common:** very common as the entry-level fix; multiple recent write-ups (Medium/dev.to "Running PostgreSQL Correctly with Docker Compose", Econumo's "Mastering PostgreSQL Docker Compose") converge on this same tuning surface (`shm_size`, `max_connections`, `shared_buffers`, `effective_cache_size`, healthcheck, restart policy) as the baseline for any shared dev Postgres container.

Sources: [Running PostgreSQL Correctly with Docker Compose](https://medium.com/@hartwig.bertrand/running-postgresql-correctly-with-docker-compose-bcf3e2273221), [How to Configure Docker's Shared Memory Size](https://last9.io/blog/how-to-configure-dockers-shared-memory-size-dev-shm/), [Mastering PostgreSQL Docker Compose for Dev & Prod](https://econumo.com/posts/postgresql-docker-compose/), [PostgreSQL Docker Compose: A Production-Shaped Setup](https://chat2db.ai/resources/blog/postgres-docker-compose-production-setup), [H3: Postgres speed flags on throwaway test databases](https://github.com/CDRO/Inventory/issues/302), [Realistic, easy, and fast enough: database tests with Docker](https://pythonspeed.com/articles/faster-db-tests/), [Optimize Postgres Containers for Testing](https://babakks.github.io/article/2024/01/26/re-015-optimize-postgres-containers-for-testing.html)

---

## Option 2 — Connection pooling in front of the shared server

**What it is:** Either (a) PgBouncer as a separate proxy process/container between Django and Postgres, or (b) Django 5.1+'s native psycopg3 pool via `DATABASES["default"]["OPTIONS"]["pool"] = {...}` (min_size/max_size/timeout), which uses `psycopg_pool` in-process per Django process rather than a shared external pooler.

**Fixes:** caps the number of *actual* backend connections Postgres has to hold regardless of how many worktree processes/xdist workers try to connect — this is the more principled fix for connection exhaustion than just raising `max_connections`, and it survives a runaway client better (bounded queue instead of a hard connection-refused wall).

**Doesn't fix:** it doesn't fix shared *resource* contention (CPU, disk IO, memory, VACUUM/lock contention) between worktrees' schemas — that's still one server. It also introduces real caveats specific to this stack:
- **PgBouncer transaction-pooling mode** breaks anything that needs session affinity: prepared statements (Django's ORM/psycopg can hit "prepared statement already exists"/mismatch errors unless PgBouncer ≥1.21 with `max_prepared_statements>0` and protocol-level prepare, or Django's `DISABLE_SERVER_SIDE_CURSORS`-style workaround), `CREATE INDEX CONCURRENTLY`/session-scoped DDL used by some migrations, and server-side cursors. Django admin/migrations often need a *direct* (non-pooled) connection for exactly this reason, so a PgBouncer setup commonly needs two connection strings (pooled for the app, direct for `migrate`).
- **Native Django pool + pytest-django:** each pytest-django/xdist worker process gets its own in-process pool (not shared across workers), so it caps per-worker connections but N workers × pool `max_size` is still the real total — this is the same "pool_size × workers" trap called out for other pooled test setups, so it must be sized as a budget across expected worktree/worker counts, not a fire-and-forget default.
- Django's docs (5.1–5.2) recommend *against* the native pool under ASGI/long-running async processes — only relevant if the project moves to ASGI; Django 6.0 adds an async-aware pool.
- `CONN_MAX_AGE` should be set to `0` when the native pool is active, since the pool — not Django's per-request connection reuse — now owns connection lifecycle; leaving both on fights each other.

**Cost:** PgBouncer: new service to run, own config file, own health/restart story, and a second (direct) connection string for migrations/admin — non-trivial to introduce into a **dev** workflow where every worktree also needs `manage.py migrate` to keep working. Native Django pool: much lower cost (a settings dict + `psycopg[pool]`), but only available from Django 5.1+ and only mitigates the *Django-process* side, not `psql`/scripts connecting directly.

**Effect on single-worktree devs:** if added at the settings-default level (e.g. via `freedom_ls.deployment.settings_defaults`, mirroring how `CONN_MAX_AGE`/`CONN_HEALTH_CHECKS` are already wired for prod), a single-worktree dev sees no behavior change other than possibly needing `psycopg[pool]` installed. If PgBouncer is introduced, every dev — single-worktree or not — now depends on an extra running service, which is a bigger ask, and it changes what downstream FLS-installing projects must run too unless carefully scoped as dev-only infra.

**How common:** PgBouncer is the long-standing, extremely common answer to "too many Postgres connections" in production Django (Heroku's docs and multiple dev.to/Medium posts treat it as the default recommendation), but its use as a *local dev* pooler in front of a shared multi-worktree Postgres is less documented — most write-ups target production. Django's native psycopg3 pool (added in 5.1, mid-2024) is newer and increasingly recommended as the lower-friction alternative when PgBouncer's operational overhead isn't wanted.

Sources: [Django docs — Databases (pool)](https://docs.djangoproject.com/en/5.2/ref/databases/), [Cut Django Database Latency With Native Connection Pooling](https://saurabh-kumar.com/articles/2025/06/cut-django-database-latency-by-50-70ms-with-native-connection-pooling/), [PostgreSQL Connection Pooling in Django: Native Pools & PgBouncer Guide](https://medium.com/@anas-issath/postgresql-connection-pooling-django-native-pools-and-pgbouncer-871dd11c632f), [Understanding Django DB Connection Pooling: Native vs PgBouncer](https://iifx.dev/en/articles/457704134), [Prepared Statements in Transaction Mode for PgBouncer — Crunchy Data](https://www.crunchydata.com/blog/prepared-statements-in-transaction-mode-for-pgbouncer), [PgBouncer 1.21 adds prepared statement support](https://pganalyze.com/blog/5mins-postgres-pgbouncer-prepared-statements-transaction-mode), [PgBouncer Configuration and Best Practices — Heroku](https://devcenter.heroku.com/articles/best-practices-pgbouncer-configuration), [Django PgBouncer in Production: Pitfalls, Fixes, and Survival Tricks](https://dev.to/artemooon/django-pgbouncer-in-production-pitfalls-fixes-and-survival-tricks-3jib), [Bound the connection pre-warm across pytest-xdist workers](https://github.com/exasol/dbt-exasol/issues/240)

---

## Option 3 — One Postgres container per worktree

**What it is:** Give each worktree its own `docker compose` project (`COMPOSE_PROJECT_NAME` derived from the worktree/branch), its own Postgres container, its own port (allocated per worktree), and its own data volume; start/stop it as part of worktree create/remove lifecycle.

**Fixes:** true resource isolation — one worktree's runaway test suite or crashed Postgres cannot affect any other worktree's database at all. This directly removes the "shared fate" problem the idea describes, not just raises its ceiling.

**Doesn't fix:** doesn't fix anything about a *single* worktree's own load (its own runserver + pytest-xdist + Playwright still share one small container's resources), and shifts the failure mode from "the shared DB dies" to "the host runs N Postgres containers simultaneously and *that* saturates host memory/CPU/disk" if worktree count grows unchecked — trading one bottleneck for another that scales with worktree count instead of with load.

**Cost:** meaningfully higher than options 1/2: needs a per-worktree compose file or project-name templating, a port-allocation scheme (`PG_PORT` derived from worktree path/branch and written to a gitignored `.env.local`, per the pattern seen in third-party tools), and explicit lifecycle hooks tied into worktree create/remove (the existing `fls-dev:git-worktree-setup` skill's per-worktree `install_dev.sh` step is a natural hook for "create the container," but *removal* — stopping/cleaning up the container and its volume when a worktree is deleted — needs its own explicit step, which doesn't currently exist for the single-container-many-databases model). Resource cost is N × (one Postgres process + its own `shared_buffers`/connections) instead of one process serving all worktrees, which is heavier at idle.

**Effect on single-worktree devs:** neutral-to-positive if the tooling is transparent (docker compose plus a small wrapper script) — one worktree still gets one Postgres, same as today, just addressed via a different generated port. It does add one more moving part (a per-worktree `.env.local` with a port number) that doesn't exist today.

**How common:** this is an active, fairly recent (2025-era) pattern specifically for "AI coding agents running many worktrees in parallel" — several purpose-built tools exist for exactly this (worktree-compose, Docktree, worktree-manager, workz), all converging on the same shape: derive `COMPOSE_PROJECT_NAME` + ports per worktree, isolate containers/networks/volumes per branch. This suggests the underlying problem (shared dev infra dying under parallel-agent load) is a recognized, fairly new pain point rather than a long-solved one — which fits this project's situation (multiple Claude Code agents running worktrees concurrently) closely.

Sources: [worktree-compose](https://github.com/mostafasudo/worktree-compose), [worktree-manager](https://github.com/Hy0sh/worktree-manager), [Docktree](https://docktree.dev/), [workz](https://github.com/rohansx/workz), [Git Worktrees Need Runtime Isolation for Parallel AI Agent Development](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/), [Using Git Worktrees to Automate Development Environments](https://fsck.sh/en/blog/git-worktree/), [Make docker-compose host ports configurable for parallel worktrees](https://github.com/danjac/django-studio/issues/421)

---

## Option 4 — Separate the test Postgres from the dev Postgres

**What it is:** Run test databases against a different Postgres instance than the one `runserver` and manual QA use — e.g. an ephemeral, tmpfs-backed Postgres spun up just for a `pytest` run (per-machine or per-worktree), so a test storm (many `pytest-xdist` workers creating/dropping `test_db_<branch>`) can't take down the dev DB that a running `runserver`/Playwright session depends on.

**Fixes:** the specific interaction called out in the idea — dev work stalling because *tests* (which are bursty, connection-heavy, and disposable) overloaded the *same* server that interactive dev/demo work depends on. Splitting them means a test-run crash only affects test runs, not `runserver`.

**Doesn't fix:** doesn't reduce total resource usage — it's still N worktrees' worth of test load, just redirected to different infrastructure. Doesn't help if the dev DB itself is what's overloaded by concurrent `runserver`+Playwright sessions across worktrees (only isolates *test* load from *dev* load, not worktree from worktree on either side unless combined with option 3).

**Cost:** moderate — needs a second Postgres target (a tmpfs-backed container, or a `pytest` fixture that spins one up per session) and a settings split so `TEST: {...}` (or a `PYTEST_...` env-driven `HOST`/`PORT`) points somewhere different from the interactive `DATABASES["default"]` dev DB. `config/settings_dev.py` already computes `TEST: {"name": f"test_{_db_name}"}` on the *same* server, so this would need extending, not introducing from scratch.

**Effect on single-worktree devs:** an extra container/process runs alongside the dev one, which is overhead a single-worktree dev pays even though they weren't the problem — worth weighing against just capping xdist workers (option 5), which fixes the same interaction without a second server.

**How common:** less common as a named pattern by itself; it's usually achieved implicitly by combining option 6 (ephemeral per-test-run Postgres via testcontainers/pytest-postgresql) with a dev-only persistent Postgres, rather than being hand-rolled as its own thing.

---

## Option 5 — Limit concurrency client-side

**What it is:** Cap `pytest-xdist` worker count (`-n <N>` or xdist's `--maxprocesses`, rather than unconstrained `-n auto`) so worker count × per-worker connections stays under `max_connections`; use `--reuse-db` so test DB schema isn't dropped/recreated on every run; set `CONN_MAX_AGE=0` in tests so connections don't linger across the suite; optionally add a machine-wide semaphore/lock (e.g. a lockfile under `~/.cache` or a `flock`-based wrapper) so only one worktree at a time runs a heavy migrate/test-create step against the shared server.

**Fixes:** directly addresses the "pool_size × workers" connection-exhaustion trap documented for other pooled/xdist setups — e.g. `-n8` with a pool size of 32 pre-warming 256 connections against a ~248-session cap. Capping workers (or adding `--maxprocesses`) bounds this without touching infra at all. `--reuse-db` avoids the DDL-heavy `CREATE DATABASE`/migrate churn that's expensive under concurrent load from multiple worktrees. A cross-worktree lock prevents the specific pile-up of N worktrees all running `migrate`/test-db-create at the same instant.

**Doesn't fix:** doesn't fix a genuinely undersized server (`max_connections`, memory) — it only prevents *pytest* from being the thing that tips it over; `runserver`+Playwright across worktrees can still do so. A global lock also serializes what could otherwise be legitimate parallel work (defeats some of the point of parallel Claude Code agents across worktrees), and `--reuse-db` requires discipline (`--create-db` after schema changes) that agents/devs can forget, silently running stale-schema tests.

**Cost:** very low — `addopts`/CI config changes and possibly one small wrapper script for the lock; no new infra, no downstream impact (it's a `pyproject.toml`/local dev convention, not something FLS imposes on installing projects).

**Effect on single-worktree devs:** a worker cap or `--reuse-db` is neutral-to-positive (faster reruns) for a single worktree; a *global* cross-worktree lock has no effect on a dev running only one worktree (nothing to contend with) but does add friction if that dev ever opens a second terminal/second worktree — worth scoping the lock so it's only engaged when it can detect siblings.

**How common:** very common and low-effort — `--reuse-db`/`--create-db` are documented, standard pytest-django flags; capping xdist workers below `-n auto` is a widely-used pragmatic fix (seen in the dbt-exasol and vinga examples) for exactly the "N workers × connections-per-worker exceeds the server's cap" failure mode. A cross-worktree filesystem lock is a more bespoke, less-documented pattern specific to the multi-worktree-agent situation.

Sources: [pytest-django — Database access](https://pytest-django.readthedocs.io/en/latest/database.html), [Bound the connection pre-warm across pytest-xdist workers](https://github.com/exasol/dbt-exasol/issues/240), [Bound how many workers -n auto resolves to](https://github.com/rafacm/vinga/pull/538), [concurrent pytest runs on one machine destroy each other's databases](https://github.com/lahavrud/rs-recruiting/issues/1073), [Stop the test suite from exhausting the PostgreSQL connection limit](https://github.com/privacyidea/privacyidea/pull/5956), [Speeding up Django unit tests with SQLite, reuse-db and RAMDisk](https://flowfx.de/blog/speeding-up-django-unit-tests-with-sqlite-reuse-db-and-ramdisk/)

---

## Option 6 — Testcontainers-python / pytest-postgresql style ephemeral databases

**What it is:** Instead of a long-lived dev Postgres shared across worktrees, spin up a fresh, throwaway Postgres (container via `testcontainers-python`, or a managed local process via `pytest-postgresql`) per test session (or per worker), configured via a `django_db_setup` pytest fixture that overrides `DATABASES` before Django's test-db machinery runs.

**Fixes:** removes shared-server contention for *tests* entirely — each test session/worker gets its own isolated Postgres, so no worktree's test run can be starved or crashed by another's. `pytest-postgresql`'s `postgresql` fixture explicitly drops the test DB and cleans up connections after each use, so there's no accumulation.

**Doesn't fix:** doesn't touch interactive dev (`runserver`) load at all — this is purely a testing-side pattern. Starting a fresh Postgres per session/worker has real startup-time cost (container boot, migrations) unless carefully scoped (module/session-scoped fixtures, or a `--reuse-db`-equivalent for the ephemeral instance), which can make it *slower* than a reused shared DB unless combined with tmpfs/durability-flag tricks (option 4's optimizations). Also means the dev/test environment now has a Docker-in-Docker or nested-container dependency if used inside CI or inside a devcontainer, which adds moving parts.

**Cost:** moderate-to-high to introduce well (fixture design, container lifecycle, migration/seed strategy) but is a "just add a pytest plugin and a fixture" change with no new persistent infra to run/monitor — unlike option 3, nothing needs to be started/stopped as part of worktree lifecycle, since it's spun up and torn down by the test run itself.

**Effect on single-worktree devs:** no different in kind from any-worktree devs — everyone gets their own ephemeral test DB regardless of how many worktrees are open, so this option's benefit doesn't scale with worktree count the way options 3/4/5 do; it's really solving "test isolation" rather than "worktree isolation," though it incidentally helps the worktree problem since ephemeral per-run DBs by definition can't collide/contend across worktrees.

**How common:** an established, well-documented pattern for test isolation in general (`testcontainers-python`, `pytest-postgresql` are both mature, widely used projects), but it's aimed at *general* test isolation rather than specifically the multi-worktree/multi-agent contention problem — pairing it with the worktree situation described here is not something the research surfaced as an existing documented combination.

Sources: [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/), [pytest-postgresql troubleshooting — DeepWiki](https://deepwiki.com/dbfixtures/pytest-postgresql/9-troubleshooting-and-faq), [Setup a Testing Environment with Docker and Pytest-Django](https://dev.to/koladev/setup-a-testing-environment-with-docker-and-pytest-django-postresql-schema-issue-2ffo), [Enhancing Your Testing Workflow with Testcontainers](https://gelopfalcon.medium.com/enhancing-your-testing-workflow-with-docker-testcontainers-3b69faa5fa28)

---

## Option 7 — Cleanup of accumulated databases from removed worktrees

**What it is:** A script (run periodically, or as part of worktree-removal) that lists databases on the shared Postgres matching the `db_<branch>`/`test_db_<branch>` naming convention and drops the ones whose worktree no longer exists.

**Fixes:** a slow-burn contributor to overload that's easy to miss — every worktree ever created (even ones later merged and removed) leaves its `db_<branch>` and `test_db_<branch>` behind on the shared server forever, since nothing in the current `install_dev.sh`/`dev_db_init.sh` flow appears to deprovision on worktree removal. Over months of Claude-Code-driven worktree churn this is pure accumulation: more catalog entries, more autovacuum workers potentially touching more databases, more clutter making it harder to reason about what's using the server. This doesn't cause a sudden overload by itself but compounds whichever other option is chosen.

**Doesn't fix:** does nothing about *concurrent, live* worktrees overloading each other — a stale-DB sweep only helps with debris from worktrees that are already gone, not the active contention the idea describes.

**Cost:** low — a single script comparing `psql -l`-style output against the current `git worktree list`, callable manually or wired into the worktree-removal path (`sdd:git-worktree-setup`'s teardown, if one exists) or a cron/manual "spring cleaning" step.

**Effect on single-worktree devs:** none — this only matters once worktree churn has happened, and cleanup is not something a single-worktree dev needs to think about.

**How common:** this is a generic "reap orphaned resources" pattern rather than something web research surfaced as a named tool/technique — it's the kind of housekeeping most teams eventually script for themselves once they notice `psql -l` listing dozens of stale per-branch databases; it wasn't the focus of the dedicated worktree-container tools found for option 3 (which mostly assume a container per worktree gets torn down structurally rather than a shared server accumulating rows in its catalog).

---

## Common combinations

Across the sources, a few pairings recur:

- **Option 1 (harden shared container) + Option 5 (client-side concurrency limits)** is the lowest-cost, most-cited combination: tune `max_connections`/`shm_size`/restart policy on the server side, and cap `pytest-xdist` workers / use `--reuse-db` on the client side, so neither side alone has to absorb all the headroom. This is the pattern implicit in most of the "shared Postgres for dev" tuning write-ups plus the xdist-connection-cap issues.
- **Option 3 (container per worktree) + Option 1's tuning ideas applied per-container** is the shape of the purpose-built worktree tools (worktree-compose, Docktree, worktree-manager): isolate first, then still apply reasonable per-container resource limits so N containers don't collectively starve the host.
- **Option 2 (PgBouncer) is commonly paired with a direct/unpooled connection string for migrations** — every write-up on PgBouncer + Django's schema-changing operations recommends keeping a second, non-pooled route for `migrate`/DDL, i.e. PgBouncer is never used alone for a Django app that runs migrations.
- **Option 4 (separate test server) is typically implemented via Option 6 (ephemeral testcontainers/pytest-postgresql) rather than as a second persistent long-lived server** — i.e. "test DB is separate from dev DB" in practice usually means "test DB doesn't persist at all," combined with tmpfs/durability-flag speedups from Option 1's test-tuning ideas.
- **Option 7 (cleanup) pairs with whichever shared-server option (1, 2, 4) is chosen** — it's irrelevant once every worktree has its own throwaway/ephemeral database (options 3/6 make stale-DB accumulation moot by construction), but is necessary hygiene for any design that keeps one long-lived server with per-worktree databases on it.

status: ok
