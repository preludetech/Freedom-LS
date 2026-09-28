# The dev database keeps going down

## Problem

We usually have 4–6 worktrees in progress at once, many of them driven by parallel Claude Code
agents. They all share one dev Postgres, and it keeps going down. When it does, every worktree
stalls until someone notices and brings it back by hand.

The dev setup has to work anywhere, for anyone who clones the repo, however many worktrees they run.

## What we know

All worktrees share one `postgres:17` container defined in `dev_db/docker-compose.yaml`. Each
worktree gets its own `db_<branch>` and `test_db_<branch>` on it, named by `branch_to_db_name`. The
container runs on stock defaults: 100 connections, a 64 MB `/dev/shm`, no memory limit, no
healthcheck and **no restart policy**. That last gap is why a crash turns into "everything stalls".

We don't know *which* failure takes it down. Nobody has captured a log line or a `pg_stat_activity`
snapshot at the moment it fails. `research_postgres_failure_modes.md` lists the six candidates, how
each one looks to a developer and how to confirm it. The strongest are connection exhaustion and
the OOM killer. `research_current_dev_db_setup.md` traces where the load comes from:

- pytest-xdist is opt-in with no worker cap, so `-n auto` opens one connection and one test
  database per CPU core.
- Every bare `uv run pytest` drops, recreates and re-migrates its test database. Several worktrees
  doing that at once contend on `template1`.
- Playwright live-server tests hold two connections each.
- The rebase hook and `qa-bugfixer` run the full suite repeatedly, and QA can fan several bugfixers
  out inside one worktree.
- Branch databases are only dropped by `/sdd:finish_worktree`. Abandoned worktrees leave theirs
  behind, and 13 sibling worktrees exist today.
- `dev_db/cleanup_devdb.sh` targets a container name modern Compose no longer uses, so the
  documented reset path is broken.

## Direction

Keep the one shared server and fix it on both sides: make the server resilient and reap
what it leaks, and stop the clients from overloading it. `research_isolation_options.md` compares
all the alternatives.

1. **The server recovers on its own.** A crashed Postgres comes back without anyone touching it,
   and a healthcheck says when it is ready.
2. **The server has headroom sized for several worktrees.** We set the connection limit, shared
   memory and memory on purpose, and tune them together. Raising `max_connections` on its own
   raises memory use and makes an OOM kill more likely. Dev-only non-durable settings are
   fine, because the data is rebuilt from migrations.
3. **The server reaps leaked sessions.** Connections left behind by killed test runs and idle
   transactions time out instead of piling up.
4. **Test runs are bounded.** Parallel pytest uses a capped worker count, not one worker per core,
   everywhere the project tells people or agents to run the suite.
5. **Stale databases get cleaned up.** A developer can find and drop every database whose worktree
   no longer exists. The broken reset script gets fixed or replaced.
6. **The next failure explains itself.** When the database does go down, the developer can tell
   which of the six failure modes it was without having to reproduce it.

This must not burden downstream projects that install FLS. It changes this repo's dev
infrastructure and conventions only. A developer running a single worktree should notice nothing
except that the database stays up.

## Not doing

- **A Postgres container per worktree.** The worktree tools built for parallel agents do this, and
  it removes shared fate. We are not doing it because it doesn't reduce the total load on the host,
  and it adds per-worktree ports and container lifecycle to every setup. Every gap we know about can
  be fixed on the shared server. If the shared server still falls over once the fixes are in, this
  is the next step.
- **PgBouncer.** It needs a second, direct connection for migrations and brings prepared-statement
  caveats, all to solve a connection problem that capping workers and raising the limit also solve.
- **Ephemeral per-run test databases** such as testcontainers or pytest-postgresql. Every test run
  would pay container start-up time, and they do nothing for the dev database.
