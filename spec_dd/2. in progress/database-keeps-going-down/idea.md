# The dev database keeps going down

## Problem

We usually have 4–6 worktrees in progress at once, many of them driven by parallel Claude Code
agents. They all share one dev Postgres, and it keeps going down. When it does, the whole Docker
engine stops with it. Every worktree stalls until someone restarts Docker Desktop and brings the
containers back up by hand.

The dev setup has to work anywhere, for anyone who clones the repo, however many worktrees they run.

## What we know

**Docker Desktop's file sharing is what crashes, not Postgres.** `research_live_diagnostics.md`
holds the evidence from this machine. There were 31 crashes between 24 August and 28 September,
rising to 4–5 a day, and every one has the same signature. Docker Desktop relays file events from
the host into its VM. The relay stalls for 60 s on a single event under the bind-mounted Postgres
data dir, `~/.lms_postges_dev_data`. Docker Desktop's file service then fails and it powers off the
VM, killing every container. 29 of the 31 stalled events were file deletions under `base/`, which is
what `DROP DATABASE` produces. None of the Postgres failure modes in
`research_postgres_failure_modes.md` shows up: no connection exhaustion, OOM kill, shared-memory
error or full disk. Outages usually lasted about an hour and up to 7 h, because nothing comes
back on its own. Docker Desktop is not set to start at login and does not recover from this failure,
and the container has no restart policy.

Docker Desktop on Linux also runs a VM, and that VM has 7.5 GiB of memory here. Native Docker Engine
has neither the VM nor the file-event relay. A Docker named volume lives inside the VM on every
platform, so file sharing never sees it. `research_docker_desktop_on_linux.md` and
`research_platform_portability.md` cover the platforms.

**The container also gets recreated, which is a second way it goes down.** The Compose project is
`dev_db` in every worktree. However, the `docker-entrypoint-initdb.d` bind mount resolves to a
different absolute path in each one. So running `docker compose up` from another worktree's `dev_db/`
sees a changed config and recreates the container. That drops every connection and deletes the
container log. It happened at 13:18 on 28 September. A worktree still on an older compose file would
do the same thing to a newer one.

**Load and leaks make it worse:**

- Agents do run `-n auto`, which gives 16 workers on this 16-core machine. Each worker creates its
  own test database from scratch and migrates it, so one run creates and drops 16 databases.
  `research_pytest_database_lifecycle.md` has the detail.
- A Claude Code Bash command that hits its timeout moves to the background and keeps running, so
  full-suite runs overlap. See `research_agent_process_lifecycle.md`.
- The server holds 124 databases. 22 belong to live worktrees and 87 are stale FLS databases. The
  rest belong to other projects that also point at port 6543. Only `/sdd:finish_worktree` drops
  branch databases.
- The host had 13 GiB of swap in use. 85 leaked Playwright MCP server processes held 3.1 GB, some
  of them more than a day old, and one agent wait loop had been stuck for almost 9 hours.
  `research_leaked_agent_processes.md` traces them to `claude_plugins/django-stack/.mcp.json`
  launching `@playwright/mcp@latest` through `npx`, and to open upstream bugs.
- `dev_db/cleanup_devdb.sh` targets a container name that Compose v2 does not use.

**Evidence doesn't survive.** Postgres logs only to the container's stdout, and that log is deleted
whenever the container is recreated. Docker Desktop's own logs rotate within one to three days.

Killing a client process on the same host does not leak its session. The backend sees the socket
close and exits. Leaked sessions come from processes that are still alive but stuck. Every
connection also uses `pguser`, the image's superuser, so connection limits and reserved slots don't
apply to anyone. `research_session_reaping.md` covers both.

## Direction

Keep the one shared server. First remove the crash, then the other ways the server goes down, then
the load and the leaks.

1. **Postgres data stays out of host file sharing.** The data dir moves from the host bind mount to
   a Docker named volume. This starts a fresh cluster. Nothing carries over from the old one,
   including other projects' databases. On Linux, the dev setup docs recommend Docker Engine over
   Docker Desktop.
2. **Starting the server from any worktree never recreates it.** `docker compose up` gives the
   same container config whichever worktree runs it. The rollout also accounts for worktrees still
   on the old compose file.
3. **The server recovers on its own.** If Postgres or its container dies while the engine stays up,
   it comes back without anyone touching it, and a healthcheck reports when it is ready. The docs
   explain that on Docker Desktop this also depends on Desktop starting at login.
4. **The server has headroom, sized on purpose.** We set the connection limit, shared memory and
   memory limit together, using the formulas in `research_server_sizing.md`. The memory limit sits
   well below the VM's, so an OOM stays inside the container instead of taking the VM down. We accept
   non-durable settings, `fsync=off` included. If a crash corrupts the cluster, recovery means
   recreating the volume and migrating again.
5. **Stuck sessions get reaped, and a human can always get in.** Idle-in-transaction sessions time
   out. App and test traffic connects as a role that is not a superuser, so connection limits and
   reserved slots actually hold.
6. **Test runs are bounded.** In this repo, `-n auto` resolves to a capped worker count rather than
   one worker per core, and test databases come from `template0`. A full-suite run started by
   an agent does not outlive that agent.
7. **Leaked agent processes stop piling up.** Playwright MCP servers and their browsers stop leaking
   where the launch config can prevent it. A developer can find and reap the ones that still leak.
8. **Stale databases get cleaned up.** A developer can find and drop every FLS database whose
   worktree no longer exists, without touching other projects' databases on the same server. The
   broken reset script gets fixed or replaced.
9. **The next failure explains itself.** Postgres keeps its logs on the data volume, so they survive
   the container being recreated. Each connection names its worktree and whether it comes from
   runserver or pytest. One command tells the developer which failure happened, including Docker
   Desktop's file-service failure. `research_failure_evidence.md` maps each failure to its proof.

This must not burden downstream projects that install FLS. `dev_db/`, the root `conftest.py` and the
pytest config are not in the package. Other projects share the `ds` and `sdd` plugins, so any
change to them has to be driven by config with today's behaviour as the default, or be a fix every
project benefits from. `research_test_run_sites.md` lists which files are shared. A developer running
a single worktree notices one fresh, empty dev database after the switch, and after that nothing
except that the database stays up.

## Not doing

- **A Postgres container per worktree.** The crash came from file sharing, not from sharing a
  server, and per-worktree containers add ports and container lifecycle to every setup without
  reducing load on the host. If the shared server still falls over once these fixes are in, this is
  the next step.
- **PgBouncer.** There is no evidence that connections ever ran out. It would also need a second,
  direct connection for migrations and brings caveats around prepared statements.
- **Ephemeral per-run test databases** such as testcontainers or pytest-postgresql. Every test run
  would pay the container start-up time, and they do nothing for the dev database.
- **`--reuse-db` by default.** pytest-django doesn't notice new migrations, and rebases bring them
  in. Once the data is out of file sharing, dropping and recreating databases no longer crashes
  anything.
- **Tuning the OOM killer** with `oom_score_adj` or host sysctls. Both need root on the host.
