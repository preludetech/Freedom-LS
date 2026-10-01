# Research: making the next failure explain itself

Scope: idea direction item 6 — after a crash, a developer should be able to tell which of the six
failure modes (connection exhaustion, `/dev/shm` exhaustion, OOM kill, disk full, `template1`
contention, leaked idle sessions — plus orphaned test processes) happened, without reproducing it.
This is about *evidence that already exists when the failure happens*, not new monitoring.

Repo facts used below, confirmed by reading the files directly:
- `dev_db/docker-compose.yaml`: single `postgres:17` service, bind-mounted data dir
  (`${DB_DATA_PATH:-~/.lms_postges_dev_data}:/var/lib/postgresql/data`), no `shm_size`, no
  `mem_limit`, **no `restart:` policy**, no `healthcheck:`, published on host port `6543`.
- `config/settings_dev.py`: no `OPTIONS`, no `CONN_MAX_AGE` → Django default `CONN_MAX_AGE = 0`
  (every request/command opens and closes its own connection); driver is `psycopg[binary]>=3.3.0`
  via `django.db.backends.postgresql` (confirmed in `pyproject.toml`); the app/test DB name is
  branch-derived (`branch_to_db_name` in `freedom_ls/base/git_utils.py`).
- `pyproject.toml` package config: `include = ["freedom_ls*"]`,
  `exclude = ["media*", "config*", "static*", "dev_db*", ...]` — `config/` and `dev_db/` are
  explicitly excluded from what ships. Anything added only to `config/settings_dev.py` or
  `dev_db/docker-compose.yaml` is this repo's own dev convenience and reaches no downstream
  project.

## 1. Where evidence lives, and when it's lost

Two independent log stores exist for the same container, and they have very different lifetimes:

**Docker's own capture of container stdout/stderr** — the default logging driver is `json-file`,
which by default has *no rotation* (`max-size` defaults to `-1`/unlimited, `max-file` to `1`), so
it grows forever unless `max-size`/`max-file` are set in the service's `logging:` block; Docker's
alternative `local` driver rotates by default (`max-size: 20m`, `max-file: 5`, ~100 MB total,
compressed) and is still readable through `docker logs`/`docker compose logs`. Either way, this
log lives at `/var/lib/docker/containers/<container-id>/<container-id>-json.log` on the host,
**keyed to the container ID, not the service name**. `docker rm` (which `docker compose down`
performs) deletes that whole per-container directory, so **the crash's own stdout evidence is
gone the moment someone runs `docker compose down`** — a very likely first move once "the
database is down" (rebuilding a hunch: it should be the *last* move, only after capturing the
[Docker docs — json-file](https://docs.docker.com/engine/logging/drivers/json-file/),
[Docker docs — local](https://docs.docker.com/engine/logging/drivers/local/),
[SigNoz — where Docker logs are stored](https://signoz.io/guides/docker-logs-location/).

If instead the container is left in place and only **restarts** (a restart policy, or `docker
compose up` again without `down`), the container ID is unchanged, so the same `-json.log` file is
retained and simply appended to — `docker logs` after an auto-restart still shows the crash's last
lines. `docker inspect` on that same container also updates `State.OOMKilled`, `State.ExitCode`
and increments `State.RestartCount` to describe the most recent stop
([Netdata — Docker OOMKilled](https://www.netdata.cloud/guides/docker/docker-oomkilled/),
[Netdata — container keeps restarting](https://www.netdata.cloud/guides/docker/docker-container-keeps-restarting/)).
**Unverified nuance:** whether `State.OOMKilled` is cleared back to `false` once the container has
since run cleanly for a while, or whether it keeps describing the *last* stop event until the next
one — the sources above describe it only as "the most recent" state, not its exact reset timing.
Treat a `true` here as "OOM happened at some point since last checked," and re-check freshness via
`State.FinishedAt`/`StartedAt` rather than trusting the boolean alone.

The repo's compose file today has **no restart policy at all**, which is exactly what the idea
calls out as "that last gap." Adding one trades the current "stalls until someone notices" problem
for a narrower forensic window: once auto-restart happens, `docker inspect` state is still readable
(container ID unchanged), but only until the *next* restart overwrites it — so the diagnostic
script in §4 should run automatically, or the developer should run it, before touching the
container a second time.

**Postgres's own `logging_collector`** writes into files inside `PGDATA` (`$PGDATA/log/` by
default) rather than to the process's stdout. Because this repo bind-mounts `PGDATA` to a host
path (`~/.lms_postges_dev_data` or `$DB_DATA_PATH`), **those log files live on the host and survive
both `docker compose down` and container recreation** — they are tied to the data directory, not
the container ID. This is the one piece of evidence that outlives the most destructive recovery
action a developer is likely to take. It requires `logging_collector = on` and (the default)
`log_destination = 'stderr'`, since the collector's job is to capture what would otherwise go to
stderr — see [Postgres 17 docs — Error Reporting and Logging](https://www.postgresql.org/docs/17/runtime-config-logging.html).
**Unverified:** the docs page did not state `logging_collector`'s literal default value; it varies
by packaging (off on most Linux/Docker images, on for the Windows-service installer), so it should
be set explicitly rather than relied on.

**Kernel OOM evidence** (`dmesg`, `journalctl -k`) is the odd one out: on a native Linux Docker
host it can name the OOM-killed process directly, but it typically needs root/`sudo` to read, and
on **Docker Desktop** (macOS/Windows) the kernel doing the killing is inside Docker Desktop's own
hidden Linux VM — the host's own `dmesg`/`journalctl` won't show it at all. `docker inspect`'s
`OOMKilled` flag is the portable substitute that works identically on both, since it comes from
Docker's own API rather than the host kernel — treat host kernel logs as a nice-to-have on native
Linux only, not something the diagnostic script should depend on.
[Crunchy Data — the Linux assassin](https://www.crunchydata.com/blog/deep-postgresql-thoughts-the-linux-assassin)
(already cited in `research_postgres_failure_modes.md`) covers the OOM-killer mechanics themselves.

## 2. Which Postgres log settings, at low noise, in dev

Recommended set for `dev_db/docker-compose.yaml`'s `postgres` service `command:`/a mounted
`postgresql.conf`, with current PG17 defaults from
[Postgres 17 docs — Error Reporting and Logging](https://www.postgresql.org/docs/17/runtime-config-logging.html)
noted for each:

| Setting | PG17 default | Recommendation | Why |
|---|---|---|---|
| `logging_collector` | platform-dependent, effectively off in the stock image | `on` | Without it, everything below only ever reaches the container's stdout log, which §1 shows is disposable. |
| `log_line_prefix` | `'%m [%p] '` | `'%m [%p] %q%u@%d app=%a client=%h '` | Adds user (`%u`), database (`%d`), `application_name` (`%a`) and client address (`%h`) — the fields needed to attribute a line to a worktree/role/xdist worker once §3's `application_name` is set. `%q` suppresses the session fields on background-process lines (checkpointer, autovacuum) where they'd be empty. |
| `log_min_messages` | `WARNING` | leave at default | Already excludes routine `LOG`/`DEBUG` noise; nothing in the six failure modes needs a lower floor. |
| `log_connections` / `log_disconnections` | `off` / `off` | turn **on** | This is the direct evidence for #6 (leaked idle sessions) and corroborates #1 (exhaustion) — pairs of lines showing who connected and for how long. |
| `log_lock_waits` | `off` | turn **on** | Zero cost when there's no contention; when there is, it's the direct signal for idle-in-transaction sessions blocking `CREATE DATABASE`/DDL (feeds #5 and #6). |
| `log_temp_files` | `-1` (disabled) | `0` | Cheap; a spike of temp-file lines right before a `/dev/shm` failure corroborates #2 even though the shared-memory error itself (§5) is the primary signal. |
| `log_checkpoints` | **`on`** (default since PG15) | leave as-is | Already low-volume; useful background context for disk-full (#4), not a primary signal. |
| `log_autovacuum_min_duration` | `10min` | leave, or `0` if disk-full debugging needs it | Not one of the six modes directly; low priority. |
| `log_min_duration_statement` | `-1` (disabled) | leave off | Out of scope for these six modes and would be by far the loudest setting here — a full pytest run logs every statement. Don't turn this on for this purpose. |

**Noise judgement on `log_connections`/`log_disconnections`:** with `CONN_MAX_AGE = 0` (confirmed
in `config/settings_dev.py`) every request and every pytest process opens a fresh connection, so
each one produces a connect + disconnect line pair. A `pytest -n auto` run across several
worktrees can plausibly generate hundreds of such pairs in a session. That is a *volume* problem
for a human reading the file live, not a *value* problem — the lines are short, cheap to write, and
exactly what makes leaked-session and exhaustion post-mortems possible; grep/tail (§4) rather than
disabling the setting is the right way to manage the volume. Postgres's own log rotation
(`log_rotation_age`/`log_rotation_size`, or `logrotate` on the bind-mounted directory) bounds disk
use the same way Docker's `max-size`/`max-file` would for the container log.

Sources: [Postgres 17 docs — Error Reporting and Logging](https://www.postgresql.org/docs/17/runtime-config-logging.html),
[pganalyze — tuning log config settings](https://pganalyze.com/docs/log-insights/setup/tuning-log-config-settings).

## 3. Making connections attributable: `application_name`

Django's Postgres backend passes everything in `DATABASES["default"]["OPTIONS"]` straight through
as keyword arguments to the driver's `connect()` call, and documents `application_name` explicitly
as one of the standard [libpq connection parameters](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS)
that can be set this way
([Django docs — connecting to the database](https://docs.djangoproject.com/en/5.2/ref/databases/#connecting-to-the-database)).
`application_name` is a plain libpq keyword, not one of the psycopg3-only options Django calls out
separately (`pool`, `server_side_binding`, both explicitly "ignored with psycopg2") — so it works
the same way under psycopg3, which is what this repo already depends on
(`psycopg[binary]>=3.3.0` in `pyproject.toml`). Concretely:

```python
DATABASES["default"]["OPTIONS"] = {
    "application_name": f"{_db_name}:{_role}:{_worker}",
}
```

where `_role` is derived from `sys.argv`/`os.environ` (`"pytest" if TESTING else "runserver"` —
`settings_dev.py` already computes `TESTING` this way) and `_worker` is
`os.environ.get("PYTEST_XDIST_WORKER", "-")`, so `pg_stat_activity.application_name` (and now
`log_line_prefix`'s `%a`) directly says *which worktree, which role, which xdist worker* a
connection belongs to — exactly the grouping `research_postgres_failure_modes.md` already
recommends for diagnosing #1 and #6 (`SELECT ... application_name, count(*) FROM pg_stat_activity
GROUP BY ...`). One existing real-world writeup of the same pattern (Django + Postgres, not
FLS-specific):
[Arthur Pemberton — setting application_name when using Postgres with Django](https://arthurpemberton.com/2019/03/setting-application_name-when-using-postgres-with-django).

**Downstream impact:** none. `config/settings_dev.py` is this repo's own dev settings; the
`pyproject.toml` package build config explicitly excludes `config*` (and `dev_db*`) from what is
distributed (`include = ["freedom_ls*"]`, `exclude = [..., "config*", "dev_db*", ...]`, confirmed
by reading `pyproject.toml`), so nothing here reaches a project that installs FLS as a dependency.

## 4. A proportionate "what happened?" diagnostic

Prior art surveyed: `pg_isready` is a plain up/down probe with no diagnostic detail
([Postgres docs — pg_isready](https://www.postgresql.org/docs/current/app-pg-isready.html));
`check_postgres.pl` (Nagios-style, [bucardo.org](https://bucardo.org/check_postgres/)) checks over
20 metrics and is built for ongoing production monitoring with alerting thresholds — more
machinery than a one-shot dev post-mortem needs. The right shape here is a single ordered script
(or a `manage.py` command under `freedom_ls/dev_tools`, matching that app's existing
dev-convenience commands) that runs cheap checks first and stops printing a verdict as soon as one
matches, not a monitoring daemon:

1. **Container state** — `docker inspect <container> --format '{{json .State}}'`: `Running`,
   `OOMKilled`, `ExitCode`, `RestartCount`, `StartedAt`/`FinishedAt`. Classifies "never started",
   "OOM-killed", "exited cleanly", or "still running" before touching Postgres at all. Works
   identically on native Linux and Docker Desktop (goes through the Docker API, not the host
   kernel); no `sudo` needed.
2. **Recent log lines** — `docker compose logs postgres --tail=200` (falls back to
   `$PGDATA/log/*.log` if `logging_collector` evidence is needed after `down`, per §1) grepped for
   the signature strings this research already collected in `research_postgres_failure_modes.md`'s
   triage table (`"too many clients already"`, `"could not resize shared memory segment"`,
   `"terminated by signal 9"`, `"No space left on device"`, `"template1" ... "being accessed by
   other users"`). Cheapest and most direct check; no `sudo` needed either way.
3. **If Postgres answers** — `pg_isready`, then the SQL already specified in
   `research_postgres_failure_modes.md`: connection count vs `max_connections` grouped by
   `application_name` (now meaningful per §3), `idle`/`idle in transaction` ages from
   `pg_stat_activity`, and `pg_database_size` per database to catch a long tail of stale
   branch/test DBs.
4. **Disk and shared memory** — `df -h` on the bind-mounted data path (host-side, no `sudo`) or
   `docker exec <container> df -h /var/lib/postgresql/data /dev/shm` (container-side, no `sudo`
   either — both are ordinary filesystem stats, not privileged operations).
5. **Host kernel OOM log** — `dmesg | grep -i oom` / `journalctl -k | grep -i oom` as a
   *corroborating*, not required, step: needs root on many Linux distros and is unreachable at all
   from a Docker Desktop host (§1) — the script should treat step 1's `OOMKilled` as sufficient and
   only attempt this on native Linux, best-effort.
6. **Orphaned test/agent processes** — `pgrep -af pytest` / `ps` filtered to the repo path, cross-
   referenced against `git worktree list` for worktrees that no longer exist on disk, the same
   principle idea.md's item 5 already applies to stale databases, applied to processes instead.

Sources: [Postgres docs — pg_isready](https://www.postgresql.org/docs/current/app-pg-isready.html),
[check_postgres](https://bucardo.org/check_postgres/).

## 5. Failure mode → the one line/field that proves it

Given the settings in §2 and the `application_name` in §3:

| Failure mode | Proof (with recommended settings) |
|---|---|
| Connection exhaustion | Postgres log: `FATAL: sorry, too many clients already` (or `... remaining connection slots are reserved ...`); confirm with `pg_stat_activity` count vs `SHOW max_connections`, grouped by `application_name`. |
| `/dev/shm` exhaustion | Postgres log: `ERROR: could not resize shared memory segment "/PostgreSQL.<hash>" to <N> bytes: No space left on device` — scoped to one query/connection, not the whole instance. |
| OOM kill | `docker inspect <container> --format '{{.State.OOMKilled}}'` → `true`; Postgres log's last line (if it got one out before the collector process itself died) may show `server process (PID N) was terminated by signal 9: Killed`; every other session drops simultaneously with `server closed the connection unexpectedly`. |
| Disk full | Postgres log: `PANIC: could not write to file ... No space left on device` (or `could not extend file`); confirm with `df -h` on the bind-mounted data path. |
| `template1`/`CREATE DATABASE` contention | Django/pytest error text: `source database "template1" is being accessed by other users` (or the target DB, on drop); `pg_stat_activity` filtered to `datname = 'template1'` at that moment shows the interloping backend's `application_name`. |
| Leaked idle sessions | No single log line — the signal is a **shape** in `pg_stat_activity`: rows with `state IN ('idle','idle in transaction')` and old `state_change`, `application_name` from §3 pinning them to a specific worktree/role/worker that finished long ago. `log_disconnections` lines that never arrive for a connection whose `log_connections` line is old is the log-only equivalent. |
| Orphaned test processes (not in original six) | Not a Postgres-side signal at all: `pgrep -af pytest`/`ps` showing PIDs for a worktree path that `git worktree list` no longer knows about; corroborated by that same `application_name`/worktree still holding `pg_stat_activity` rows above. |

status: ok
