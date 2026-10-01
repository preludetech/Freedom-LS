# Research: why a single shared dev Postgres "dies" under multi-worktree load

## Confirmed setup in this repo

- `dev_db/docker-compose.yaml`: a single `postgres:17` container, no `shm_size:`, no
  `mem_limit`/`deploy.resources.limits`, no `POSTGRES_*` tuning flags. Data volume is a bind
  mount to `~/.lms_postges_dev_data` on the host (or `DB_DATA_PATH`), exposed on host port
  `6543`. Defaults therefore apply: `max_connections=100`, `/dev/shm` capped at Docker's
  default 64 MiB, and no container memory ceiling of its own (only whatever the host / Docker
  Desktop VM has).
- `config/settings_dev.py`: `DATABASES["default"]["NAME"]` is derived from the current git
  branch (`branch_to_db_name`), and `TEST.name` is `test_{branch_db_name}` — so **different
  worktrees on different branches already get different app DBs and different base test-DB
  names**, which avoids one class of cross-worktree collision. It does **not** set
  `CONN_MAX_AGE` (Django's connection-reuse setting), so dev likely runs on the Django default
  `CONN_MAX_AGE=0` (connection closed at the end of each request) unless the code path pulls in
  `freedom_ls/deployment/settings_defaults.py`'s `CONN_MAX_AGE=60` — worth confirming which
  value is actually active, since it changes which failure mode below is plausible.
- `pyproject.toml`: `pytest-xdist`, `pytest-django`, `pytest-playwright`, `pytest-randomly` are
  all installed; `addopts` has no `-n` flag, so parallelism is whatever `-n auto`/`-n N` a
  developer or agent passes on the command line. pytest-django auto-suffixes each xdist worker's
  test DB with `_gwN`, so **within one worktree** parallel workers get distinct test DBs; the
  risk is many worktrees × many xdist workers × Playwright's live server all opening
  connections/creating DBs against the *same* Postgres instance at once.

## 1. `max_connections` exhaustion

**Symptom developer sees:** the app (or `psql`, or pytest) suddenly can't connect; Postgres
itself is still running (container up, other already-open connections keep working). Error text
is one of:
- `FATAL: sorry, too many clients already`
- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
  (the last 3 slots, per `superuser_reserved_connections`)

This "looks like an outage" but the server process is alive — it's actively refusing new
sessions because every slot up to `max_connections` (default 100) is taken.

**Why it happens here:** every worktree's dev server, every pytest-xdist worker (each with its
own DB connection, potentially its own connection pool if using threaded test client / Playwright
live server), and every Playwright browser-driven request against the live server opens a
Postgres connection concurrently. With several worktrees active plus `-n auto` xdist fanning out
across CPU cores, it's easy to multiply past 100 real connections.

**How to diagnose:**
- Postgres logs show the FATAL line above at the moment a client tried to connect.
- `SELECT count(*) FROM pg_stat_activity;` vs `SHOW max_connections;` — if count is at/near the
  limit, this is the cause.
- `SELECT usename, application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3 ORDER BY 4 DESC;`
  shows which processes/worktrees own the connections (Django sets `application_name` in some
  configs; otherwise correlate by `client_port`/`backend_start`).

**Standard mitigation:** raise `max_connections` (with awareness of the memory cost, see below),
put a pooler such as PgBouncer in front in transaction-pooling mode so many client connections
share a small pool of real Postgres backends, and/or reduce concurrency at the source (cap
`-n` for xdist, ensure Django closes connections promptly, avoid one long-lived pooled connection
per xdist worker × per worktree).

Sources: [Netdata guide](https://www.netdata.cloud/guides/postgres/postgres-too-many-connections/), [oneuptime guide](https://oneuptime.com/blog/post/2026-01-21-postgresql-too-many-connections/view), [Baeldung](https://www.baeldung.com/sql/psqlexception-fatal-sorry-too-many-clients-already-solution)

## 2. Docker `/dev/shm` 64 MB default + parallel query shared-memory resize failure

**Symptom developer sees:** a specific query fails (not the whole server): `ERROR: could not
resize shared memory segment "/PostgreSQL.<hash>" to <N> bytes: No space left on device`. Often
triggered by a parallel sequential scan, parallel hash join, or parallel index build — i.e. more
likely to bite when the test suite's larger fixtures run under load with `max_parallel_workers_per_gather > 0`.

**Why it happens here:** Docker containers get 64 MiB of `/dev/shm` unless `shm_size:` is set in
compose; Postgres uses dynamic shared memory (backed by `/dev/shm` on Linux) for parallel-query
work areas separate from `shared_buffers`. This repo's `dev_db/docker-compose.yaml` has no
`shm_size:`, so it is on the 64 MiB default.

**How to diagnose:** the error text names shared memory explicitly and is scoped to one query/
connection rather than the whole instance; `docker exec <container> df -h /dev/shm` shows the
64 MiB cap; correlate with `pg_stat_activity` to see which query triggered it.

**Standard mitigation:** add `shm_size: 256m` (or similar) to the `postgres` service in
`docker-compose.yaml`, or disable/limit parallel query on the dev instance
(`max_parallel_workers_per_gather = 0`) if shared memory can't be grown.

Sources: [SQLpassion](https://www.sqlpassion.at/archive/2024/12/09/how-to-fix-the-postgresql-could-not-resize-shared-memory-segment-error-in-docker/), [SigNoz](https://signoz.io/guides/pq-could-not-resize-shared-memory-segment-no-space-left-on-device/), [Instaclustr](https://www.instaclustr.com/blog/postgresql-docker-and-shared-memory/), [osprey issue](https://github.com/als-apg/osprey/issues/1026)

## 3. OOM killer / container memory limits killing the postmaster

**Symptom developer sees:** this is the one that genuinely looks like "the database died" — the
whole container exits/restarts, every connection drops simultaneously (`server closed the
connection unexpectedly`, `SSL connection has been closed unexpectedly`, `could not connect to
server: Connection refused` right after). Postgres log's last line is often abrupt with no
graceful shutdown message, or shows `server process (PID N) was terminated by signal 9: Killed`.

**Why it happens here:** with no `mem_limit`/`deploy.resources.limits.memory` set on the
`postgres` service, the container isn't individually capped, but the whole Docker/Docker Desktop
VM has a memory ceiling; if the combined footprint of N worktrees' Django dev servers, N ×
xdist-workers' Python processes, Playwright's bundled Chromium instances, and Postgres's own
per-backend memory (each backend ~5–10 MB baseline, more with `work_mem` for sorts/hashes)
exceeds the VM's memory, the Linux (or Docker Desktop VM's Linux) OOM killer picks a victim —
often postgres, since it can be one of the larger resident processes.

**How to diagnose:**
- `docker inspect <container> --format '{{.State.OOMKilled}}'` returns `true` if the OOM killer
  hit that specific container.
- Host-level: `dmesg | grep -i "out of memory\|oom_kill"` or `journalctl -k | grep -i oom` shows
  which process was killed and why (look for `postgres` / `postmaster` in the victim list).
- `docker stats` while the failure is reproduced shows memory climbing toward the limit
  beforehand.

**Standard mitigation:** raise the Docker Desktop VM's memory allocation (Settings → Resources),
and/or set an explicit `mem_limit`/`deploy.resources.limits.memory` on the postgres service so it
fails predictably rather than being an OOM-killer lottery victim alongside everything else. Since
cgroup v2 `memory.max` delivers an immediate SIGKILL with no graceful degradation, an explicit,
sized limit plus lowering `shared_buffers`/`work_mem` per connection reduces the chance Postgres
itself is the trigger.

Sources: [Crunchy Data — The Linux Assassin](https://www.crunchydata.com/blog/deep-postgresql-thoughts-the-linux-assassin), [Netdata OOM guide](https://www.netdata.cloud/guides/postgres/postgres-out-of-memory/), [ADHDecode Docker Compose OOM](https://adhdecode.com/debugging/docker-compose/memory-limit-exceeded-oom-killed/)

## 4. Disk full: accumulated test databases, WAL, docker volume growth

**Symptom developer sees:** writes start failing across the board — `PANIC` in the Postgres log,
or ORM errors like `could not extend file`, `No space left on device`; the container may refuse
to (re)start at all if the bind-mounted data dir has zero free bytes. This can look identical to
"the database died" from the app's point of view because writes and new connections both fail.

**Why it happens here:** the data directory is a bind mount to the host
(`~/.lms_postges_dev_data`), shared by every worktree since they all point at the same Postgres
instance. Many git-branch-named app DBs plus many `test_<branch>` / `test_<branch>_gwN` databases
accumulate over time if not dropped (especially if `--reuse-db`/`--keepdb` is used, or a run is
killed mid-teardown), each with its own on-disk footprint; WAL also grows if checkpoints can't
keep up with write-heavy parallel test runs.

**How to diagnose:**
- `df -h` on the host path backing `~/.lms_postges_dev_data` (or `docker exec <container> df -h
  /var/lib/postgresql/data`).
- `SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY 2 DESC;`
  to find which of the many `test_*`/branch DBs are largest — a long tail of stale worktree
  branches' leftover test DBs is a common culprit.
- Postgres log around the failure shows `PANIC: could not write to file ... No space left on
  device` or similar.

**Standard mitigation:** periodically drop stale `test_*` and branch DBs for worktrees that no
longer exist (a cleanup script keyed off `git worktree list`), avoid `--keepdb`/`--reuse-db`
accumulating indefinitely, and monitor/alert on the bind-mount's free space.

Sources: [oneuptime disk-full guide](https://oneuptime.com/blog/post/2026-01-25-fix-disk-full-postgresql/view), [Medium — mysterious no space left](https://medium.com/@komalbagwe31797/postgresql-in-docker-the-mysterious-no-space-left-on-device-error-and-how-to-fix-it-on-macos-ee7371d4eae8), [Docker forums](https://forums.docker.com/t/postgre-no-space-left-on-device/136085)

## 5. Lock contention / `CREATE DATABASE` races on `template1`

**Symptom developer sees:** pytest fails to create/drop its test database with:
`django.db.utils.OperationalError: source database "template1" is being accessed by other
users`, or the inverse `... is being accessed by other users` on the *target* test DB during
teardown/`--create-db`. This is a pytest-django/Django-level error, not a whole-server outage —
other connections keep working.

**Why it happens here:** `CREATE DATABASE`/`DROP DATABASE` in Postgres require exclusive access
to the template (`template1` by default) and to the target DB respectively; if any other backend
(another worktree's xdist worker, a leftover connection, Django's own next test run) has an open
connection to that same template or target DB at that instant, the command is rejected outright
rather than waiting. With several worktrees running pytest concurrently and pytest-django
creating/tearing down test DBs on every fresh run (or on `--create-db`), the odds of two
`CREATE DATABASE FROM template1` calls overlapping goes up. Django ticket #25406 notes
`_create_test_db` can hide/mis-report this error under `--keepdb`, making it confusing to debug.

**How to diagnose:** the error text names `template1` (or the specific test DB) and "being
accessed by other users"; `pg_stat_activity` filtered to `datname = 'template1'` at the time of
failure shows the interloping backend(s) and which worktree/PID owns them.

**Standard mitigation:** avoid connecting anything to `template1` directly; use `--reuse-db`
where safe to skip repeated create/drop cycles; ensure each worktree/branch truly has a unique
test-DB name (this repo already does, via `branch_to_db_name`) so at least different *worktrees*
don't race on the same target DB — the remaining race is multiple worktrees' `CREATE DATABASE ...
TEMPLATE template1` calls overlapping on the shared template itself, which is inherent to sharing
one Postgres instance and is mitigated by serializing test-DB creation (e.g. a lock/mutex around
the `manage.py test`/pytest invocation) or using `template0`/a lighter creation flow.

Sources: [Django ticket #25406](https://code.djangoproject.com/ticket/25406), [pytest-django docs — database access](https://pytest-django.readthedocs.io/en/latest/database.html), [pytest-django issue #696](https://github.com/pytest-dev/pytest-django/issues/696), [Django ticket #22420](https://code.djangoproject.com/ticket/22420)

## 6. Idle connections left open by killed test runs / `CONN_MAX_AGE` / idle-in-transaction

**Symptom developer sees:** connection count creeps up over a working session even though no one
is actively running tests right now; eventually tips into failure mode #1 (`too many clients
already`). `pg_stat_activity` shows many rows in `state = 'idle'` or, worse, `idle in
transaction`, some with `backend_start` hours old.

**Why it happens here:** when a pytest run (especially under xdist, or a Ctrl-C'd Playwright
run) is killed abruptly (SIGKILL, VS Code/agent process torn down, terminal closed), Python never
gets to run connection-close teardown, so the Postgres backend the client held stays registered
until TCP eventually notices the peer is gone (which can be a long time, or never, on a local
Docker network) — this is a well-known pytest-django/Django issue (ticket #17887, #22420). If
Django's `CONN_MAX_AGE` is non-zero anywhere in the stack (the shared `settings_defaults.py`
default is `60`; worth confirming this isn't picked up in dev), persistent connections held open
across requests compound the same effect for the live dev server itself, not just tests.
"Idle in transaction" specifically is worse than plain idle because it can hold row/table locks
and block other sessions (including `CREATE DATABASE`/DDL from #5).

**How to diagnose:**
```sql
SELECT pid, usename, application_name, state, now() - state_change AS idle_for, query
FROM pg_stat_activity
WHERE state IN ('idle', 'idle in transaction')
ORDER BY idle_for DESC;
```
Long `idle_for` values with no corresponding active developer session point at leaked
connections from a killed run rather than current load.

**Standard mitigation:** set `idle_in_transaction_session_timeout` (and optionally
`idle_session_timeout`, Postgres 14+) on the dev instance so Postgres itself reaps stale sessions
instead of relying on clients to close cleanly; keep Django's `CONN_MAX_AGE` low/zero for the dev
settings (trading a little per-request connection-setup cost for not accumulating zombies);
periodically `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE ...` as a manual
escape hatch.

Sources: [Django ticket #17887](https://code.djangoproject.com/ticket/17887), [Django ticket #22420](https://code.djangoproject.com/ticket/22420), [SquadStack — statement_timeout from Django](https://medium.com/squad-engineering/configure-postgres-statement-timeouts-from-within-django-6ce4cd33678a)

## Dev-only tuning commonly recommended for test/dev databases

These are durability-for-speed trades that are explicitly endorsed by the Postgres docs *only*
for throwaway data (`Non-Durable Settings` in the Postgres manual):

- `fsync = off`, `synchronous_commit = off`, `full_page_writes = off` — skip forcing writes to
  durable storage / WAL page images; reported ~30% speedup on disk-backed test runs. **Caveat:**
  a crash (OOM kill, `docker kill`, host power loss) can corrupt the data directory beyond
  recovery — acceptable only because dev/test DBs are recreated from migrations/fixtures anyway,
  never for anything with data worth keeping.
- Mounting the Postgres data directory on `tmpfs` (RAM-backed) instead of the bind-mounted disk —
  reported as the single biggest speedup (more than the fsync/sync flags combined) in independent
  benchmarks. **Caveat:** data vanishes on container restart (fine for test DBs, not for the
  persistent dev app DB people expect to survive `docker compose restart`), and it consumes host
  RAM directly, which competes with the OOM-killer risk in #3 above — sizing it too large can
  itself cause OOM kills.
- `shm_size` raised from Docker's 64 MiB default (see #2) — no durability trade-off, just fixes
  parallel-query shared memory; cheap to do unconditionally for a dev Postgres.
- Raising `max_connections` (see #1) — **not free**: each connection has a baseline memory cost
  (rough estimates in surveyed sources: ~2–3 MB shared + ~5–10 MB total per idle backend, before
  any `work_mem` for active sorts/hashes/joins, which multiplies per connection per concurrent
  operation). Raising `max_connections` from 100 to, say, 300 to absorb multiple worktrees'
  worth of xdist workers directly raises the instance's peak memory need and makes OOM (#3) more
  likely unless matched with lower `work_mem`/`shared_buffers` or more VM memory. A pooler
  (PgBouncer in transaction mode) is the standard alternative that avoids this trade-off by
  capping *real* backend count while allowing many logical client connections.
- `max_parallel_workers_per_gather = 0` (or similar) as a blunt way to avoid #2 entirely if
  shared memory can't be grown, at the cost of slower large queries.

Sources: [Postgres docs — Non-Durable Settings](https://www.postgresql.org/docs/current/non-durable-settings.html) *(not directly fetched this session but referenced by multiple secondary sources below; recommend confirming exact wording before citing in the spec)*, [pythonspeed.com — Realistic, easy, fast enough DB tests with Docker](https://pythonspeed.com/articles/faster-db-tests/), [dev.to — Speed up PostgreSQL unit tests](https://dev.to/thejessleigh/speed-up-your-postgresql-unit-tests-with-one-weird-trick-364p), [dev.to — Speeding Up PostgreSQL in Containers](https://dev.to/miry/speeding-up-postgresql-in-containers-1eeg), [Postgres wiki — Tuning Your PostgreSQL Server](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server), [Postgres docs — Resource Consumption](https://www.postgresql.org/docs/current/runtime-config-resource.html)

## Quick triage checklist (symptom → likely cause)

| What you see | Most likely cause | First diagnostic |
|---|---|---|
| New connections rejected, server otherwise responsive | #1 max_connections | `pg_stat_activity` count vs `max_connections` |
| One query fails mid-run, others fine | #2 `/dev/shm` | error text mentions "shared memory segment" |
| Whole container restarts, all connections drop at once | #3 OOM killer | `docker inspect --format '{{.State.OOMKilled}}'`, `dmesg \| grep -i oom` |
| Writes fail everywhere, container won't (re)start | #4 disk full | `df -h` on the bind-mounted data path |
| pytest fails to create/drop its test DB specifically | #5 template1 lock contention | error text mentions "template1 ... being accessed" |
| Connection count creeps up between runs with no active work | #6 leaked idle connections | `pg_stat_activity` filtered to `idle`/`idle in transaction`, check `state_change` age |

status: ok
