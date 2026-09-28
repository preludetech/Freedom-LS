# Research: sizing and tuning the shared dev Postgres

Scope: direction item 2 ("the server has headroom sized for several worktrees... we set the
connection limit, shared memory and memory on purpose, and tune them together"). This file
answers *how* to size `max_connections`, `shared_buffers`, `work_mem`, `shm_size` and a container
memory limit together, and exactly what happens when memory runs out. It assumes
`research_postgres_failure_modes.md` and `research_isolation_options.md` for the failure-mode
catalogue and option comparison, and does not repeat them except where it corrects a specific
claim.

---

## 1. Per-backend memory: realistic cost, how the multipliers stack, worst-case formula

**Baseline per-connection cost is small and mostly *not real extra memory* — but you cannot see
that from `ps`/RSS.** Andres Freund's measurement of a fresh, idle backend (still the best
primary-source measurement available; done on PG13-era code, but the underlying mechanism —
`fork()` of a process that maps the same shared-memory segments as every other backend — is
unchanged through PG17):

- Naive `ps`/RSS reading: **~16 MiB per idle connection with `huge_pages=off`**, ~7 MiB with
  `huge_pages=on`.
- But summing RSS across backends **double-, triple-, N-times-counts** `shared_buffers` and other
  shared regions, because every backend's RSS includes every shared page it has ever touched. With
  1,030 idle connections open, the *actual marginal* memory (measured via `Pss` from
  `/proc/<pid>/smaps_rollup`, which divides shared pages proportionally) totalled only **~4 MiB**
  with huge pages off, ~1.2 MiB with huge pages on — i.e. a few KB of genuinely private memory per
  idle connection (`Pss_Anon`), plus per-process page-table overhead (`VmPTE`) that huge pages
  collapse from ~6.5 MiB to ~0.1 MiB per backend.
- **The trap this research flags explicitly:** don't provision a container's memory limit by
  multiplying "RSS per backend" (5–10 MB, as `research_postgres_failure_modes.md` estimates,
  reasonably) by `max_connections` and adding `shared_buffers` on top — that double-counts
  `shared_buffers` on top of itself. The cgroup memory controller that actually decides whether you
  get OOM-killed (§3) charges a shared physical page **once** to the container's cgroup, no matter
  how many backends map it — it behaves like `Pss`, not like summed `ps` RSS. So `shared_buffers`
  belongs in the formula once, not once per connection.
- **Huge pages in Docker, practically:** `huge_pages` defaults to `try`. Getting real huge pages
  requires the *host* to have `vm.nr_hugepages` reserved and the container to have access to
  `hugetlbfs` — neither happens by default in a plain `docker compose` dev setup, so `try` silently
  falls back to normal pages. **Assume `huge_pages` is effectively off** for this project's dev
  container unless someone deliberately wires up hugetlbfs (not recommended here — it's host-level
  configuration that would leak into "works on my machine"). That means the *worse* column of the
  numbers above is the one to plan around.

**How the configured multipliers stack (quoting PG17 docs, `runtime-config-resource.html`):**

- `work_mem` (default `4MB`): *"a complex query might perform several sort and hash operations at
  the same time, with each operation generally being allowed to use as much memory as this value
  specifies before it starts to write data into temporary files. Also, several running sessions
  could be doing such operations concurrently. Therefore, the total memory used could be many
  times the value of `work_mem`."*
- `hash_mem_multiplier` (default `2.0`): hash-based operations (hash join, hash aggregate) get
  `work_mem × hash_mem_multiplier`, not `work_mem` — so the real per-operation ceiling for a hash
  node is double the configured `work_mem` at defaults.
- `maintenance_work_mem` (default `64MB`): used by `VACUUM`, `CREATE INDEX`,
  `ALTER TABLE ADD FOREIGN KEY`. **When autovacuum runs, up to `autovacuum_max_workers` times this
  memory may be allocated** (default `autovacuum_max_workers` is 3, so up to 3×
  `maintenance_work_mem`/`autovacuum_work_mem` concurrently, independent of anything above).
- Parallel workers: *"parallel queries may consume very substantially more resources than
  non-parallel queries, because each worker process is a completely separate process which has
  roughly the same impact on the system as an additional user session... Resource limits such as
  `work_mem` are applied individually to each worker... a parallel query using 4 workers may use up
  to 5 times as much CPU time, memory, I/O bandwidth, and so forth as a query which uses no workers
  at all."* (`max_parallel_workers_per_gather` default `2`, `max_parallel_workers` default `8`,
  `max_worker_processes` default `8`.) Parallel workers are full backend processes but are **not**
  counted against `max_connections` — they draw from `max_worker_processes`/`max_parallel_workers`
  — so they are an *addition* to the connection-count-based part of the formula, not covered by it.

**Worst-case memory formula (container budget, not naive RSS-sum):**

```
container_memory_needed  ≈
    shared_buffers                                            (once — shared, not ×connections)
  + max_connections × per_backend_private_baseline            (huge_pages off: plan ~8–10 MB/backend
                                                                 to be safely pessimistic; true
                                                                 marginal cost is lower per Pss, but
                                                                 cgroup accounting + page-table
                                                                 overhead + Django/psycopg client-side
                                                                 buffering on the backend justify the
                                                                 pessimistic number)
  + expected_concurrent_active_backends
        × work_mem × hash_mem_multiplier
        × avg_concurrent_sort_or_hash_nodes_per_query          (assume 2 if unmeasured)
  + autovacuum_max_workers × maintenance_work_mem              (or autovacuum_work_mem if set)
  + max_parallel_workers × work_mem × hash_mem_multiplier      (each parallel worker gets its own
                                                                 work_mem budget; bounded by
                                                                 max_worker_processes)
  + headroom (20–30%)                                          (OS, connection-count spikes, the
                                                                 dynamic-shared-memory usage in §2)
```

Sources: [PostgreSQL 17 docs — Resource Consumption](https://www.postgresql.org/docs/17/runtime-config-resource.html), [PostgreSQL 17 docs — Connections and Authentication](https://www.postgresql.org/docs/17/runtime-config-connection.html), [Andres Freund — Measuring the Memory Overhead of a Postgres Connection](https://blog.anarazel.de/2020/10/07/measuring-the-memory-overhead-of-a-postgres-connection/) *(PG13-era measurement; mechanism unchanged in PG17 but not independently re-measured on PG17 for this research — flagged as not directly re-verified)*.

---

## 2. `shared_buffers` vs `/dev/shm` — what actually needs the Docker shm limit

This corrects/sharpens a point `research_postgres_failure_modes.md` §2 gets right in outcome but
imprecise in mechanism ("Postgres uses dynamic shared memory (backed by `/dev/shm`... for
parallel-query work areas **separate from `shared_buffers`**" — that "separate from" is the load-
bearing part, and it's worth being exact about why):

- `shared_memory_type` (default on Linux: `mmap`) controls the server's **main** shared memory
  region — this is where `shared_buffers` lives. Per PG17 docs: *"By default, PostgreSQL allocates
  a very small amount of System V shared memory, as well as a much larger amount of anonymous
  `mmap` shared memory."* **Anonymous `mmap` shared memory is not backed by `/dev/shm` at all** —
  it's an anonymous memory mapping shared via `fork()`, counted as ordinary process/cgroup memory,
  with no dependence on Docker's `shm_size`. **You can run `shared_buffers=2GB` in a container with
  the stock 64 MiB `/dev/shm` and it works fine** — the two are unrelated for this part.
  `shared_memory_type=sysv` is the alternative and is "generally discouraged as it typically
  requires non-default kernel settings" (i.e. host `kernel.shmmax`/`shmall` tuning) — no reason to
  use it here.
- `dynamic_shared_memory_type` (default on Linux: `posix`) is what actually uses `/dev/shm`: POSIX
  shared memory is implemented via `shm_open()`, which creates a file-backed mapping on the
  `/dev/shm` tmpfs. This is used for **parallel query** work areas — parallel hash joins, parallel
  bitmap heap scans, parallel sort/tuplestores — allocated per parallel worker, on top of (not
  instead of) that worker's `work_mem`/`hash_mem_multiplier` budget from §1.
- **Practical conclusion:** Docker's default 64 MiB `/dev/shm` only bites when parallel-query
  workers are active and their combined DSM segments exceed 64 MiB — exactly the "one query fails,
  server otherwise fine" symptom `research_postgres_failure_modes.md` §2 documents. It does **not**
  constrain `shared_buffers` sizing. The `docker-library/postgres` image's own compose example
  recommends `shm_size: 128mb` as a starting point; given several worktrees may run parallel test
  queries concurrently, **256 MiB is a safer floor** for this setup, and it's cheap because the
  segments are only actually used (and only actually charged, see next point) while a parallel
  query is running.
- **Does `/dev/shm` count against the container's memory limit? Yes.** tmpfs pages (which is what
  `/dev/shm` is) are charged to the same cgroup as everything else in the container: "shmem: shared
  memory segments and tmpfs mounts are included in what counts toward the memory limit." So
  `shm_size` is not a separate budget bolted on beside `mem_limit` — it is a **ceiling carved out of
  the same container memory budget**. Setting `shm_size` generously does not itself reserve or
  cost memory (tmpfs is populated lazily, only charged when pages are actually written), but if
  parallel queries fill it, that usage competes with `shared_buffers`/backends/etc. for the same
  `mem_limit`. Treat `shm_size` as "how much of the container's total memory parallel-query DSM is
  allowed to consume," not as extra headroom.

Sources: [PostgreSQL 17 docs — Resource Consumption (`shared_memory_type`, `dynamic_shared_memory_type`)](https://www.postgresql.org/docs/17/runtime-config-resource.html), [PostgreSQL 17 docs — Managing Kernel Resources](https://www.postgresql.org/docs/17/kernel-resources.html), [docker-library/postgres — Docker Hub README (shm_size example)](https://hub.docker.com/_/postgres), [docker-library/postgres issue #416 — `/dev/shm` sizing question (open, no official formula given)](https://github.com/docker-library/postgres/issues/416), community write-ups on cgroup v2 tmpfs accounting (search-derived, not a single canonical doc page — flagged as not a primary source): [GoLinuxCloud — Linux memory limits in containers](https://www.golinuxcloud.com/linux-container-memory-limits-cgroups/).

---

## 3. What happens under a container memory limit vs host-wide OOM

**Container PID 1 is Postgres itself — verified.** `docker-library/postgres`'s
`docker-entrypoint.sh`, after any root-only setup, does `exec gosu postgres "$BASH_SOURCE" "$@"`
and ultimately `exec "$@"`, i.e. `exec`, not a forked subprocess — postgres replaces the shell and
becomes PID 1 in the container's PID namespace. This matters for both signal delivery and for the
"does the container exit" question below.

**Killing one backend (e.g. the OOM killer picks a single large query's backend, not the
postmaster):**

- Postgres's own crash-handling: when any backend dies abnormally (SIGKILL/SIGSEGV), the postmaster
  logs `server process (PID N) was terminated by signal 9: Killed`, then forcibly disconnects
  **every other backend** ("terminating any other active server processes" / clients see
  `WARNING: terminating connection because of crash of another server process` /
  `FATAL: the database system is in recovery mode`), and performs crash recovery (WAL replay since
  the last checkpoint). Once recovery completes it starts accepting connections again.
- **The postmaster (PID 1) itself is not killed in this scenario and stays running throughout** —
  so the *container* stays up the whole time, `docker ps` never shows a restart, but every client,
  in every worktree, sees its connection drop simultaneously and has to reconnect. This is the
  "everything drops, then recovers on its own" failure mode the topic asked to verify — **confirmed
  as accurate**, and it's a materially different failure shape from a full container exit:
  `restart: unless-stopped` does **nothing** here (nothing exited), because the *supervisor*
  process never died — only a *backend* died. The fix for this failure shape is entirely on the
  client side (reconnect-on-error) plus not causing OOM kills in the first place (§1/§6), not the
  restart policy.

**Killing the postmaster itself, or the whole cgroup:**

- If cgroup v2's OOM killer instead selects the postmaster process (or `memory.oom.group` is set to
  `1` for the container, which forces the kernel to kill **every** process in the cgroup together
  rather than a single victim), the container's PID 1 dies and **the container exits**. This is the
  scenario where `restart: unless-stopped` (or `on-failure`) actually earns its keep, and where a
  `healthcheck` matters (so nothing routes traffic at a container mid-restart-and-recovering).
- **Which of these two shapes you get is not fully within your control by default.** cgroup v2's
  `memory.oom.group` defaults to `0` — *"the default value of 0 results in only some tasks being
  OOM killed"* — meaning a plain Docker container, absent extra configuration, is exposed to the
  *single-backend-killed, container-survives* shape more often than the *whole-container-exits*
  shape. (Some higher-level orchestrators, e.g. recent Kubernetes releases, opt into
  `memory.oom.group=1` per-pod; plain `docker compose` does not do this for you as far as this
  research could verify — **flagged as not independently confirmed against a specific
  `runc`/Docker Engine version**; if this matters in practice, `docker inspect
  <container> --format '{{.State.OOMKilled}}'` plus `dmesg | grep -i oom` after a real incident is
  the way to tell which shape actually occurred here.)

**Linux memory overcommit and `oom_score_adj` — what's feasible in Docker:**

- PG17 docs on the host-level fix: *"The default virtual memory behavior on Linux is not optimal
  for PostgreSQL... the kernel might terminate the PostgreSQL postmaster... if the memory demands
  of either PostgreSQL or another process cause the system to run out of virtual memory."* The
  documented mitigation is `sysctl -w vm.overcommit_memory=2` (strict overcommit) — but this is a
  **system-wide, not per-namespace, kernel setting**; it is not something a `docker-compose.yaml`
  can scope to one container, and setting it would affect the whole host (or Docker Desktop VM),
  which is out of scope for "changes this repo's dev infrastructure only." **Not recommended here**
  — flag as infeasible within the stated constraints, not as a per-container knob.
- PG17 docs' `PG_OOM_ADJUST_FILE`/`PG_OOM_ADJUST_VALUE` mechanism (protect the postmaster at
  `oom_score_adj=-1000`, let ordinary backends stay killable at `0`) requires **root**, writing to
  `/proc/self/oom_score_adj` **before** `exec`ing postgres. The stock `docker-library/postgres`
  entrypoint does not appear to set this (it drops from root to the `postgres` user via `gosu`
  precisely at the point this would need to happen) — doing it would require a custom entrypoint
  wrapper. **Not verified against the current image's entrypoint source beyond reading it once —
  flag as something to confirm before relying on it**, and Docker's own docs explicitly discourage
  hand-tuning OOM scores: *"You shouldn't try to circumvent these safeguards by manually setting
  `--oom-score-adj` to an extreme negative number on the daemon or a container."* Docker Compose
  does expose a per-service `oom_score_adj: <-1000..1000>` key (mirrors `docker run
  --oom-score-adj`) if this is ever revisited, but per Docker's own guidance it's a knob to use
  cautiously, not a first move — and it only affects *which process inside the cgroup* gets picked
  when `memory.oom.group=0`, not whether the cgroup limit is hit at all.
- **Net recommendation for this project:** don't fight the OOM killer with `oom_score_adj` or host
  sysctls. Size the container so hitting the limit is rare (§6), add `restart: unless-stopped` +
  `healthcheck` so the *container-exits* shape self-heals, and treat the *single-backend-killed*
  shape as a client-reconnect problem, not a server-config problem.

Sources: [docker-library/postgres — `docker-entrypoint.sh`](https://github.com/docker-library/postgres/blob/master/17/bookworm/docker-entrypoint.sh), [PostgreSQL 17 docs — Managing Kernel Resources (Linux Memory Overcommit)](https://www.postgresql.org/docs/17/kernel-resources.html), [Docker docs — Resource constraints (OOM behavior, `--oom-kill-disable` warning)](https://docs.docker.com/engine/containers/resource_constraints/), [Giuseppe Scrivano — Cgroup v2 OOM group](https://scrivano.org/posts/2020-08-14-oom-group/), [opencontainers/runc issue #3387](https://github.com/opencontainers/runc/issues/3387), [Docker Compose file reference — `oom_score_adj`](https://docs.docker.com/reference/compose-file/services/), general Postgres crash-recovery behavior corroborated via [PostgreSQL 17 docs — Shutting Down the Server](https://www.postgresql.org/docs/17/server-shutdown.html) and community threads *(the exact "terminating any other active server processes" log-line behavior is well-documented Postgres behavior but this research did not locate one single canonical doc paragraph stating it verbatim — flagged as corroborated, not verbatim-quoted, from primary docs)*.

---

## 4. Docker Compose knobs — exact syntax and what's honoured without Swarm

All of the following are honoured by plain `docker compose up` (Compose v2, non-Swarm) on the
`postgres` service in `dev_db/docker-compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:17
    mem_limit: "3g"                 # hard memory ceiling → cgroup memory.max
    shm_size: "256m"                # /dev/shm size (see §2 — shares the mem_limit budget)
    command: >
      postgres
        -c max_connections=120
        -c shared_buffers=768MB
        -c work_mem=16MB
        -c maintenance_work_mem=128MB
        -c max_parallel_workers_per_gather=2
        -c idle_in_transaction_session_timeout=60000
    restart: unless-stopped          # "no" | "always" | "on-failure[:N]" | "unless-stopped"
    stop_grace_period: 30s           # wait before SIGKILL after SIGTERM; default 10s
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 15s              # grace period before failures count against `retries`
      start_interval: 1s             # poll faster during start_period (Compose ≥2.20.2 / needs a
                                      # recent-enough Docker Engine — verify locally before relying
                                      # on it; older Compose silently ignores unknown keys)
```

- `mem_limit` — **honoured directly, no Swarm needed.** This is the field to use here.
- `deploy.resources.limits.memory` — the Compose Specification's "canonical" way to express memory
  limits, but historically **only applied under Swarm, or under plain `docker compose` when passed
  `--compatibility`**; without either, it is silently ignored by `docker compose up`. **Correction
  to keep in mind if the eventual spec/plan references `deploy:` syntax:** for this repo's plain,
  non-Swarm `docker compose up` workflow, `mem_limit:` is the reliable choice; `deploy:` limits
  should not be assumed to take effect without independently confirming the installed Compose
  version's behavior.
- `command: postgres -c key=value ...` vs mounting `postgresql.conf` — both work. `command:` flags
  are simplest for a docker-compose-only setup (no extra bind mount, shows up in
  `pg_settings.source = 'command line'`, highest precedence), and is what the `docker-library`
  image's own docs demonstrate. Mounting a custom `postgresql.conf` (with `-c config_file=...`) is
  preferable only if the settings list grows long enough that inlining it in YAML gets unwieldy, or
  if non-Compose tooling (`psql` scripts, `pg_ctl`) also needs the same config outside Compose.
- `restart:` — `unless-stopped` is the right choice per the idea's direction item 1: restarts after
  a crash or Docker daemon restart, but respects an explicit `docker compose stop`. This only fires
  on the *container-exits* failure shape from §3, not the *single-backend-killed* shape.
- `healthcheck` + `start_period`/`start_interval` — `pg_isready` is the standard check; `start_period`
  avoids counting normal startup/crash-recovery time as failures (important here, since crash
  recovery after an OOM-killed backend, §3, can take a few seconds and would otherwise flap the
  health status); `start_interval` (newer field) lets the check poll faster than the steady-state
  `interval` while still inside `start_period`, so a quick recovery is detected sooner than a full
  `interval` would allow. Confirm the installed Docker Compose version supports `start_interval`
  before depending on it — flagged as version-gated, not verified against a specific version pin in
  this repo.
- `stop_grace_period` — matters even for a disposable dev DB, because an unclean shutdown
  (`SIGKILL` after grace period expires) is itself a "crash" from Postgres's point of view and
  interacts with §5's durability trade-offs; keeping the default smart-shutdown path (checkpoint on
  `SIGTERM`) working within the grace period avoids adding *routine* crash-recovery cycles on top of
  whatever accidental ones already happen.

Sources: [Docker Compose file reference — full field list](https://docs.docker.com/reference/compose-file/services/), [docker/compose issue #5803 — `mem_limit` vs Swarm-only `deploy` limits](https://github.com/docker/compose/issues/5803), [docker/docs issue #14185 — memory limits in Compose v3 vs `docker-compose`](https://github.com/docker/docs/issues/14185), [docker-library/postgres — Docker Hub README](https://hub.docker.com/_/postgres).

---

## 5. The "Non-Durable Settings" page — exact wording, and the corruption risk weighed honestly

Fetched directly from `https://www.postgresql.org/docs/17/non-durability.html`. Exact wording:

- **fsync:** *"Turn off fsync; there is no need to flush data to disk."*
- **synchronous_commit:** *"Turn off synchronous_commit; there might be no need to force WAL
  writes to disk on every commit. **This setting does risk transaction loss (though not data
  corruption) in case of a crash of the database.**"*
- **full_page_writes:** *"Turn off full_page_writes; there is no need to guard against partial
  page writes."*
- **The page's overall framing:** *"Except as noted below, durability is still guaranteed in case
  of a crash of the database software; only an abrupt operating system crash creates a risk of
  data loss or corruption when these settings are used."*
- **`wal_level=minimal` and `max_wal_senders=0` are not on this page at all.** They come from
  `runtime-config-wal.html` instead: `wal_level=minimal` strips WAL down to the bare minimum needed
  for crash recovery (no logical decoding, no replication), and requires `max_wal_senders=0` because
  replication needs at least `wal_level=replica`. This is a legitimate additional dev-only WAL-volume
  reduction, but it is **not one of the settings the Postgres project itself groups under "Non-
  Durable Settings"** — worth being precise about that distinction if citing "the docs say this is
  fine" in the spec.

**Reading the wording precisely, `fsync` and `synchronous_commit` carry different risk classes,
and the page says so explicitly**: `synchronous_commit=off` alone risks losing the *last few
commits*, not corruption. `fsync=off` has no such carve-out — the page's general framing
("...creates a risk of data loss **or corruption**...") applies to it directly, and `fsync` is what
guarantees writes actually reach durable storage in the order Postgres expects. **A further
interaction worth calling out (not stated as a single sentence on the docs page, but following
directly from what each setting protects against):** `full_page_writes` exists to let recovery
repair a *torn page* — a page write interrupted mid-flush by a crash. That protection is only
meaningful if `fsync` is actually forcing writes to reach disk in the first place; turning
`full_page_writes` off *while `fsync` is also off* removes both the mechanism that detects/repairs
torn pages and the guarantee that flushes even happen in order, so the two settings' risks compound
rather than sitting side by side.

**Weighed against this repo's actual architecture, honestly:** the topic prompt is right to single
this out. `dev_db/docker-compose.yaml` bind-mounts **one** persistent data directory
(`~/.lms_postges_dev_data`, or `DB_DATA_PATH`) that holds **every worktree's** `db_<branch>` and
`test_db_<branch>` databases in the **same** cluster. `fsync=off` doesn't corrupt "a database" — if
the cluster is corrupted, `initdb`/WAL recovery may not be able to bring the *instance* back up at
all, which means every worktree's dev database goes down together, not just the one that happened
to trigger the crash. That is precisely the "shared fate" problem the idea's direction is trying to
reduce, reintroduced via a different mechanism: an OOM kill (the failure mode this whole document
is about reducing the odds of) is exactly the kind of "abrupt operating system crash" the docs warn
about, and with `fsync=off` it's the trigger for the worst-case outcome instead of the
recover-automatically outcome verified in §3.

**Recommendation:** `synchronous_commit=off` is close to free — bounded risk (lose the last
uncommitted-to-disk transactions, no corruption), no interaction with crash recovery's ability to
bring the cluster back up, and Postgres explicitly frames it as safe against "a crash of the
database" (only OS-level crashes, e.g. `docker kill -9`/host power loss, threaten more, and even
then the docs don't extend "corruption" to this setting specifically). `full_page_writes=off` is
reasonable **only if `fsync` stays on** — turning it off relies on `fsync` still being active to
avoid torn-page corruption. **`fsync=off` should not be the default here** given the shared,
persistent, multi-worktree data directory: the blast radius of getting it wrong is exactly the
outage this whole spec is trying to prevent, just moved from "connections drop and recover" to
"nobody's dev database comes back until the volume is wiped and every worktree re-migrates."
`wal_level=minimal`+`max_wal_senders=0` is comparatively low-risk (it changes what's *logged*, not
whether writes are *durable*) and is a reasonable "free" addition once replication is confirmed
unneeded in dev. If `fsync=off` is wanted anyway for the speed gain, it should be paired with (a) the
memory sizing in §6 actually making OOM kills rare, and (b) making sure the "stale database cleanup"
tooling (direction item 5) doubles as a "rebuild the whole cluster from scratch" runbook, since that
becomes the actual recovery path if `fsync=off` ever does bite.

Sources: [PostgreSQL 17 docs — Non-Durable Settings (fetched directly, quoted verbatim above)](https://www.postgresql.org/docs/17/non-durability.html), [PostgreSQL 17 docs — Write Ahead Log (`wal_level`, `max_wal_senders`)](https://www.postgresql.org/docs/17/runtime-config-wal.html).

---

## 6. Recommended starting configuration — formulas and worked examples

**Assumptions (stated explicitly — these are illustrative, not measured against this repo's real
load; direction item 6, "the next failure explains itself," should be used to correct these numbers
against real `pg_stat_activity` data once the healthcheck/logging groundwork lands):**

- Per-worktree peak connection count = `runserver (2) + xdist_workers × 2 + playwright (2)`.
  `xdist_workers` is the **capped** worker count from direction item 4, not `-n auto`; this
  research assumes that cap is enforced project-wide (a documented `-n` value or `pytest-xdist`
  config), since without it these numbers don't hold — an uncapped `-n auto` on an 8–16 core box
  defeats any connection-limit sizing.
- `huge_pages` effectively off (§1) — plan around the pessimistic per-backend number.
- The Postgres container is **not** the only thing consuming host RAM: N worktrees' Django
  `runserver` processes, xdist worker Python processes, and Playwright's bundled Chromium
  instances (each meaningfully larger than a Postgres backend) also compete for host memory. The
  container `mem_limit` figures below are deliberately a **minority** of host RAM — sizing Postgres
  to consume most of the box would just relocate the OOM risk onto the container that's supposed to
  survive.
- `autovacuum_max_workers` left at its default of 3.
- Headroom target: keep steady-state connection usage under ~65–70% of `max_connections`, and
  reserve enough superuser/reserved slots that a developer can always open a diagnostic `psql`
  session even at the cap.

**Worked examples:**

| | 16 GB / 8-core | 32 GB / 12-core | 64 GB / 16-core |
|---|---|---|---|
| Assumed concurrent worktrees | 4 (this box is genuinely tight for 6 — see note) | 6 | 6–8 |
| Capped xdist workers per worktree | 4 | 4 | 6 |
| Per-worktree peak connections | 2+4×2+2 = 12 | 2+4×2+2 = 12 | 2+6×2+2 = 16 |
| Raw peak connections | 48 | 72 | ~128 |
| `superuser_reserved_connections` | 3 (default) | 3 (default) | 5 |
| `reserved_connections` (PG17, headroom for a non-superuser diagnostic role) | 0 | 3 | 5 |
| **`max_connections`** | **80** | **120** | **200** |
| `mem_limit` (container) | **3g** (~19% of host RAM) | **6g** (~19%) | **12g** (~19%) |
| **`shared_buffers`** (25% of `mem_limit`, per PG docs guidance) | **768MB** | **1536MB** | **3072MB** |
| `maintenance_work_mem` × `autovacuum_max_workers(3)` | 128MB × 3 = 384MB | 192MB × 3 = 576MB | 256MB × 3 = 768MB |
| Per-backend baseline (`max_connections` × ~8MB) | 640MB | 960MB | 1600MB |
| Headroom (~20% of `mem_limit`) | ~614MB | ~1229MB | ~2458MB |
| Remaining for `work_mem` budget | ~1050MB | ~1843MB | ~4390MB |
| **`work_mem`** (remaining ÷ ~20–40 concurrently-*active* backends ÷ `hash_mem_multiplier`) | **16MB** | **32MB** | **48MB** |
| **`max_parallel_workers_per_gather`** | 2 (or 0 if `/dev/shm` pressure shows up — see §2) | 2 | 4 |
| `max_worker_processes` | 8 (default) | 12 (align with cores) | 16 |
| **`shm_size`** | **256m** | **512m** | **1g** |

Notes on the table:

- **16 GB is genuinely tight for "6 worktrees."** The idea states 4–6, "sometimes more"; this
  research's honest read is that a 16 GB box supporting 6 fully-loaded worktrees (each running
  Playwright/Chromium) at once is optimistic once Postgres, Django, xdist, and browsers are all
  counted — the table above assumes **4** concurrent worktrees for the 16 GB case specifically to
  keep the non-Postgres headroom (~13 GB across everything else) plausible. If 6 worktrees must be
  supported on 16 GB, the more realistic fix is capping xdist workers harder (2, not 4) and/or
  accepting a smaller `max_connections`/`work_mem`, not shrinking `mem_limit` further — Postgres is
  already a minority consumer here.
- `reserved_connections` (a PG17 addition, default `0`) is a good fit for "a developer can always
  get in to diagnose": grant `pg_use_reserved_connections` to a diagnostic role distinct from
  `pguser`-the-superuser, so even a compromised/runaway app connection storm can't also exhaust the
  slots a human needs to run `pg_stat_activity` queries. If that's more machinery than wanted,
  simply keeping `superuser_reserved_connections` at its default (3) and connecting as the existing
  `POSTGRES_USER=pguser` superuser role achieves the same practical outcome with zero extra config,
  since `pguser` is already a superuser in this image by virtue of `POSTGRES_USER`.
- These numbers are a **starting point for direction item 2**, sized from formulas and PG17 docs
  guidance, not from measured load on this repo's actual Postgres instance. Direction item 6 ("the
  next failure explains itself") should feed real `pg_stat_activity`/`docker stats` numbers back
  into this table once the healthcheck and any added logging exist — particularly the "per-backend
  baseline" and "concurrently-active backends" inputs, which are the two most speculative numbers
  in the formula (§1 flags exactly why: true marginal memory is far lower than naive RSS, but the
  pessimistic planning number is deliberately chosen to avoid re-creating the OOM problem this
  research is trying to solve).

Sources: same as §1/§2/§6 above — [PostgreSQL 17 docs — Resource Consumption](https://www.postgresql.org/docs/17/runtime-config-resource.html), [PostgreSQL 17 docs — Connections and Authentication](https://www.postgresql.org/docs/17/runtime-config-connection.html).

---

## Summary of corrections to the existing research files

- `research_postgres_failure_modes.md` §2's framing ("dynamic shared memory... separate from
  `shared_buffers`") is directionally correct but this file makes the mechanism precise:
  `shared_buffers` uses anonymous `mmap` (unrelated to `/dev/shm`); only *parallel-query* dynamic
  shared memory segments use `/dev/shm`, via `dynamic_shared_memory_type=posix` (§2).
- `research_postgres_failure_modes.md` §3's claim that "the whole container exits/restarts, every
  connection drops simultaneously" on OOM is **only one of two possible shapes**. This research
  confirms a second, more likely-by-default shape exists: a single backend gets OOM-killed, the
  postmaster (container PID 1) survives and does crash recovery, every connection still drops, but
  the **container itself never exits or restarts** — `restart: unless-stopped` does nothing in that
  case (§3). Both shapes should be accounted for, not just the exits-and-restarts one.
- `research_isolation_options.md` §Option 1 mentions "`mem_limit`/`deploy.resources.limits.memory`"
  as if roughly interchangeable. §4 of this file corrects that: only `mem_limit` is reliably honoured
  by this repo's plain (non-Swarm) `docker compose up`; `deploy.resources.limits.memory` needs
  Swarm or `--compatibility` and should not be assumed to work otherwise.
- `research_postgres_failure_modes.md`'s "Dev-only tuning" section flags `fsync=off` as a caveat but
  frames it evenhandedly against `synchronous_commit=off`/`full_page_writes=off`. §5 of this file
  sharpens that: the Postgres docs draw an explicit line between `synchronous_commit=off` (no
  corruption risk, only transaction loss) and `fsync=off`/`full_page_writes=off` (corruption risk on
  an abrupt OS crash), and given this repo's single shared, persistent, multi-worktree data
  directory, that corruption risk is a **cluster-wide** outage, not a per-worktree one — the same
  shared-fate problem direction item 2 exists to reduce, reappearing through a different door.

## Unverified / flagged items

- The exact per-backend "~8–10 MB baseline" used in §1/§6's formula is a deliberately pessimistic
  planning number, not a PG17-specific re-measurement; the only primary measurement found
  (Andres Freund's) is from PG13-era code and reports lower *marginal* (PSS-based) memory.
- Whether the stock `docker-library/postgres:17` entrypoint sets `PG_OOM_ADJUST_FILE`/
  `oom_score_adj` for the postmaster was not confirmed beyond one reading of the entrypoint script.
- Whether Docker/`runc`'s default cgroup v2 configuration sets `memory.oom.group=1` (kill-the-whole-
  container) for ordinary `docker compose` containers, vs leaving it at the kernel default `0`
  (kill a single process), was not confirmed against a specific Docker Engine/`runc` version — this
  determines which of the two OOM shapes in §3 is more likely in practice on a given developer's
  machine.
- `start_interval` in `healthcheck` is version-gated (Compose ≥2.20.2-era) and was not checked
  against whatever Docker/Compose version this project's developers actually run.
- The claim that `POSTGRES_USER` becomes a Postgres superuser by default in this image (relied on
  in §6's reserved-connections note) is standard `docker-library/postgres` behavior but was not
  re-confirmed by fetching that specific paragraph of the image README in this session.

status: ok
