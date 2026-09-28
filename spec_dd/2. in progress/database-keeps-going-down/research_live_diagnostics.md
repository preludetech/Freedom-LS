# Research: live evidence from the dev database on this machine

Gathered 2026-09-28, 14:37–14:55 UTC (16:37–16:55 SAST, host local time is UTC+2). Everything was
read-only: no container, process or setting was touched, and only `SELECT`/`SHOW` SQL was run. Log
timestamps below are UTC unless marked SAST.

**Legend:** **[fact]** means read directly from a log, `docker inspect` or a query. **[inference]**
means my interpretation of those facts.

## Verdict

**The database is not what crashes. The Docker Desktop VM that hosts it crashes, and every time the
trigger is a file event from the Postgres data directory, which is bind-mounted from the host home
folder.** Confidence: high for the mechanism, medium-high for the "DROP DATABASE churn" trigger.

- **[fact]** 31 Docker Desktop VM crashes are on record between 2026-08-24 and 2026-09-28 (user
  journal back to 2026-08-17). 13 of them fell in the last ~55 hours: 5 on 09-26, 4 on 09-27 and
  4 on 09-28.
- **[fact]** Each crash has the same signature. Docker Desktop's host-to-VM filesystem-event
  injector (`com.docker.backend.grpcfuse.volume` / `init.fs`) gets stuck on **one event under
  `~/.lms_postges_dev_data`**. It logs `unable to inject 1 events for 10s … 1m0s`, then
  `init.fs [E] injecting event … blocked for 60s` and `Service fs failed`. dockerd is then
  `SIGKILL`ed, and after 1 s to 10 min `init [E] FATAL: running services: running fs: injecting
  event blocked for 60s` → `init.poweroff` kills postgres → `reboot: Power down`. The whole engine
  goes down, which matches the user's report.
- **[fact]** All 31 stalled events are paths inside the Postgres data dir. 29 of 31 are
  `Action:Removed` on `base/<db-oid>/<relfilenode>`, which is what `DROP DATABASE` does when it
  unlinks hundreds of files per database. One is `ChangeContents` on a 16 MB `pg_wal` segment
  (today, 13:58) and one is `Created`.
- **[inference]** The trigger is heavy file churn in the bind-mounted data dir: test databases
  being dropped and recreated (a bare `uv run pytest` drops and recreates them, and xdist makes
  up to 16 `_gwN` copies), plus WAL writes, all on a directory of 85,651 files that Docker
  Desktop mirrors file events for. Today's crash fits: the last Postgres line before it was
  `13:57:14 ERROR: database "test_db_educator_interface_5_permissions" already exists` (a pytest
  create/drop cycle). The stall began at ~13:57:15. Crash recovery at 14:35 reported
  `could not open directory "base/27624501"`, meaning a `DROP DATABASE` was half-done when the VM died.
- **[fact] None of the six Postgres failure modes shows up in the evidence available.** There are
  zero `too many clients`, `remaining connection slots`, `could not resize shared memory`, `No space
  left`, `out of memory`, `terminated by signal` or `PANIC` lines. The VM kernel console has no
  OOM-killer lines (the only `oom` hits are `oom-tracer started` at boot) and there is no host OOM
  kill of qemu. The host disk is 49% used and `/dev/shm` is 2% used. `being accessed by other
  users` (template/test-DB contention) appears 4 times. It is a nuisance for pytest, not what takes
  the server down.
- **[fact]** Recovery is manual, and the downtime per crash ran from ~4 min to ~7 h, typically
  about 1 h (VM power-down to next VM boot). Docker Desktop does not restart its VM after this
  FATAL, and even when it comes back the container's `RestartPolicy` is `"no"`.
- **Unknown:** why the injector wedges. It could be a Docker Desktop bug, host inotify/fanotify
  pressure, or the host being under memory pressure (13 GiB of 40 GiB swap in use). Also unknown:
  whether keeping the data dir off the host bind mount (a named Docker volume inside the VM)
  removes the problem entirely. Also unknown: why the postgres container was *recreated* at
  13:18:14 today. Its previous logs were lost with it, so Postgres-level evidence from before
  13:18 no longer exists.

**Implication for the idea [inference]:** "server recovers on its own" through `restart:` cannot
help, because the engine itself dies. The highest-leverage change is to move `PGDATA` from the
host bind mount (`${DB_DATA_PATH:-~/.lms_postges_dev_data}`) to a Docker named volume, which lives
inside the VM, has no host file sharing and no event injection. Reducing `DROP/CREATE DATABASE`
churn (`--reuse-db`, capped `-n`, cleaning up the 92 stale DBs) comes second. The Postgres-side
hardening in the idea is still worth doing, but it is not what has been taking the database down.

## 1. Container state (`docker inspect dev_db-postgres-1`)

**[fact]**

```
docker context: desktop-linux (Docker Desktop), server 28.3.2, compose v2.38.2-desktop.1
container: dev_db-postgres-1 (id 8758e45e3d9d), image postgres:17 (PostgreSQL 17.11)
Created   = 2026-09-28T13:18:14Z      <- container recreated today, earlier logs gone
State     = running, OOMKilled=false, ExitCode=0, Error=""
StartedAt = 2026-09-28T14:35:05Z   FinishedAt = 2026-09-28T14:32:48Z
RestartCount = 0   RestartPolicy = {"Name":"no"}   Healthcheck = null
Memory = 0 (unlimited)   ShmSize = 67108864 (64 MiB)
LogConfig = json-file, no max-size/max-file (unrotated, but the log dies with the container)
Mounts: bind /home/sheena/.lms_postges_dev_data -> /var/lib/postgresql/data
        bind .../main/dev_db/docker-entrypoint-initdb.d -> /docker-entrypoint-initdb.d
compose project = dev_db, working_dir = /home/sheena/workspace/lms/freedom-ls-worktrees/main/dev_db
```

- **[fact]** `dev_db-mailpit-1` has the identical `FinishedAt 14:32:48.014Z` / `StartedAt
  14:35:05.12Z`. Both containers stopped together. **[inference]** The engine went down, not
  Postgres alone. `FinishedAt` is stamped when the restarted dockerd cleans up, and the real death
  was at 13:59:46 (see §3).
- **[inference]** Both containers started within milliseconds at 14:35:05 even though the restart
  policy is `no`. Someone ran `docker compose up` by hand after restarting Docker Desktop.
- **[fact]** `dev_db/cleanup_devdb.sh` targets `dev_db_dbs_1`. The real name is
  `dev_db-postgres-1` (Compose v2 uses hyphens and the service is `postgres`, not `dbs`). The
  script is broken as the idea says.
- **[fact]** A second, native Docker engine also runs on the host (`default` context,
  `/var/run/docker.sock`, `dockerd[4688]`). It holds an old `dev_db-postgres-1` (e8c52f0c596c)
  that has been `Exited (0) 5 months ago`. It is inactive, but it means which engine you get
  depends on the active context.

## 2. Postgres container log (`docker logs -t`)

**[fact]** 1,636 lines / 432 KB, covering 2026-09-28 13:18:21 → 14:35:21 only (container created
13:18).

| pattern | count |
|---|---|
| FATAL | 13 (2× `database "db_database_keeps_going_down" does not exist` at 13:22, 10× `the database system is starting up` 14:35:09–14:35:19, 1× `role "root" does not exist` 14:35:21) |
| PANIC | 0 |
| terminated by signal | 0 |
| too many clients / remaining connection slots | 0 / 0 |
| could not resize shared memory | 0 |
| No space left | 0 |
| out of memory | 0 |
| server process (… exited) | 0 |
| being accessed by other users | 4 (13:28:55, 13:30:04, 13:45:47 on `test_db_educator_interface_3_panel_framework_dialogs`, 13:48:00 on `test_db_educator_interface_5_permissions`) |
| database … already exists | 3 (13:29:17, 13:30:09, 13:57:14) |
| shutdown messages (smart/fast/immediate, "shut down") | 0 |
| database system was interrupted | 1 (14:35:09) |
| database system is ready | 2 (13:18:21, 14:35:20) |
| ERROR (total) | 508, almost all expected unique-violation errors from tests |

Startup and crash-recovery events:

```
13:18:21.525 [1] LOG: starting PostgreSQL 17.11 ...            (fresh container, existing PGDATA)
13:18:21.638 [1] LOG: database system is ready to accept connections
13:57:14.856 [2248] ERROR: database "test_db_educator_interface_5_permissions" already exists   <- last line before the crash
      -- no shutdown line of any kind: postgres was killed with the VM --
14:35:09.613 [1] LOG: starting PostgreSQL 17.11
14:35:09.715 [54] LOG: database system was interrupted; last known up at 2026-09-28 13:57:14 UTC
14:35:09.973 .. 14:35:19.931  10x FATAL: the database system is starting up   (a client polling ~1.1 s)
14:35:20.009 [54] LOG: database system was not properly shut down; automatic recovery in progress
14:35:20.121 [54] WARNING: could not open directory "base/27624501": No such file or directory
14:35:20.121 [54] WARNING: some useless files may be left behind in old database directory "base/27624501"
14:35:20.314 [1] LOG: database system is ready to accept connections
14:35:21.065 [133] FATAL: role "root" does not exist   (someone ran psql in the container without -U)
```

- **[inference]** The `base/27624501` warning means a `DROP DATABASE` was in progress when the VM
  died. That matches the file-removal events that stall the injector.
- **[fact]** Crash recovery took ~10 s (09.7 → 20.0), most of it before the "automatic recovery"
  line. **[inference]** That is the startup data-dir fsync over the file-shared mount.
- **[fact]** `log_connections`/`log_disconnections` are off and `logging_collector` is off.
  Postgres keeps no log of its own on the data volume, only container stdout, and that is lost
  whenever the container is recreated.

## 3. Docker Desktop

### 3a. Engine, VM and settings

**[fact]**

```
docker info: Operating System: Docker Desktop, Kernel 6.10.14-linuxkit, CPUs: 16, Total Memory: 7.52GiB,
             Storage Driver: overlayfs (containerd snapshotter), Cgroup v2, Logging Driver: json-file
qemu-system-x86_64 -accel kvm -m 7953 -smp 16 ...  (host RSS 1.4 GB)
/opt/docker-desktop/bin/virtiofsd --shared-dir=/home --cache=auto ...
inside container: MemTotal 7885088 kB; /dev/shm tmpfs 64M, 1.1M used
PGDATA mount inside container: /run/host_mark/home on /var/lib/postgresql/data type fakeowner
~/.docker/desktop/settings-store.json: AutoStart=False, UseContainerdSnapshotter=True,
    EnableDockerAI=False; no memory/CPU/swap/disk/resource-saver keys (all Docker Desktop defaults)
VM disk ~/.docker/desktop/vms/0/data/Docker.raw: apparent 915G, actual 20G on disk
```

- **[fact]** Host: 31 GiB RAM (17 GiB used, 13 GiB available), 16 cores, swap 40 GiB file with
  13.3 GiB used. Root filesystem 915G, 49% used. `~/.lms_postges_dev_data` is 2.0 GB and holds
  **85,651 files** (125 database directories under `base/`).
- **[inference]** `AutoStart=False` combined with no auto-recovery after the fs FATAL means every
  crash waits for a human.
- `docker system df` was not run separately. The DB data lives on the host bind mount, not in the
  VM disk, so the VM disk is not a factor (20G actual).

### 3b. The crash signature (today, 13:57–13:59 UTC)

**[fact]** Host `com.docker.backend.log` and VM `console.log.1`:

```
13:57:25 [com.docker.backend.grpcfuse.volume][W] unable to inject 1 events for 10.000007765s
13:57:35 ... for 20s   13:57:45 ... 30s   13:57:55 ... 40s   13:58:05 ... 50s
13:58:15 ... unable to inject 1 events for 1m0.00000805s
13:58:15 [init.fs][E] injecting event ... On:File Action:ChangeContents Path:"home" Path:"sheena"
         Path:".lms_postges_dev_data" Path:"pg_wal" Path:"000000010000000F000000ED" Size:16777216 blocked for 60s
13:58:15 [init.control] reporting error to /services/error: service fs failed: injecting event blocked for 60s
13:58:16 [init.services] Service fs failed with: injecting event blocked for 60s
13:58:16 [init.dockerd][W] root context was cancelled, sending SIGKILL
13:58:16 [init.procd] unpausing ... "pause resumed: Docker Desktop is running"
13:58:16 [init.dockerd] exited: signal: killed
13:59:46 [init][E] FATAL: running services: running fs: injecting event blocked for 60s
13:59:46 [init.poweroff] preparing to power the VM off...
13:59:46 [init.poweroff] killing /usr/lib/postgresql/17/bin/postgres (pid 10667)
13:59:47 [init.poweroff] power the vm off        [ 7764.047476] reboot: Power down
13:59:47 host virtiofsd: Client disconnected, shutting down
14:32:44 next VM boot (Linux version 6.10.14-linuxkit)
14:34:00 VM powered off again cleanly (dockerd "waitid: no child processes", no fs error)
         -> [inference] a manual Docker Desktop restart
14:34:01 VM boot; 14:35:05 containers started by hand
```

- **[fact]** The stall starts at ~13:57:15, one second after Postgres's last log line
  (13:57:14.856) and matching `last known up at 13:57:14` in the recovery log.
- **[fact]** Host `electron-2026-09-28.log` shows the Docker Desktop UI reconnecting to the
  engine at 05:06, 07:19, 09:43, 11:50, 13:58, 14:32 and 14:34 UTC. That is one reconnect per VM
  (re)boot or engine loss.

### 3c. Every crash in the VM console logs (2026-09-26 02:33 → now)

**[fact]** `~/.docker/desktop/log/vm/console.log*`. "Stall" is when the injector reported
60 s blocked (the stall began 60 s earlier). "Next boot" is the next `Linux version` line.

| # | fs stall reported (UTC) | stalled event | VM power-down | next VM boot | down for |
|---|---|---|---|---|---|
| 1 | 09-26 06:45:36 | Removed `base/18432838/18471068` | 06:46:54 | 07:38:45 | ~52 min |
| 2 | 09-26 08:17:26 | Removed `base/18681824/18823491` | 08:17:35 | 09:12:42 | ~55 min |
| 3 | 09-26 13:11:22 | Removed `base/19399981/19466633` | 13:13:09 | 13:17:46 | ~5 min |
| 4 | 09-26 16:54:17 | Removed `base/20378227/4144` | 16:55:03 | 18:20:16 | ~1 h 25 |
| 5 | 09-26 18:59:44 | Removed `base/20931240/20951509` | 18:59:46 | 19:07:33 | ~8 min |
| 6 | 09-27 00:45:01 | Removed `base/22602168/22660085` | 00:47:43 | 04:44:41 | ~4 h |
| 7 | 09-27 05:36:40 | Removed `base/22960066/23011452` | 05:38:49 | 06:30:15 | ~51 min |
| 8 | 09-27 19:30:19 | Removed `base/25136645/25201389` | 19:36:06 | 20:56:29 | ~1 h 20 |
| 9 | 09-27 21:55:07 | Removed `base/25378923/25464574` | 21:58:58 | 09-28 05:06:05 | ~7 h |
| 10 | 09-28 06:27:31 | Removed `base/26083274/4144` | 06:37:58 | 07:19:00 | ~41 min |
| 11 | 09-28 09:31:29 | Removed `base/26935334/26985821` | 09:34:08 | 09:43:40 | ~10 min |
| 12 | 09-28 10:25:37 | Removed `base/27189031/4144` | 10:30:12 | 11:50:22 | ~1 h 20 |
| 13 | 09-28 13:58:15 | ChangeContents `pg_wal/…0F000000ED` | 13:59:46 | 14:32:44 | ~33 min |

- **[fact]** During #8 the host backend kept logging `unable to inject 1 events` from 19:29 up to
  `15m39s`, so the injector never unblocked.
- **[fact]** Across all VM console logs there are zero `oom-kill`, `Out of memory` or
  `Killed process` lines.

### 3d. Longer history (host user journal, `journalctl --user`, back to 2026-08-17)

**[fact]** `Service fs failed with: injecting event blocked for 60s`, count per day (SAST dates):

```
08-24: 1   08-29: 2   09-04: 1   09-07: 1   09-08: 1   09-12: 4   09-15: 1
09-17: 3   09-18: 2   09-23: 2   09-26: 5   09-27: 4   09-28: 4        total 31
```

**[fact]** The stalled path for each pre-09-26 event was also under `.lms_postges_dev_data/base/…`:
16 × `Removed`, 1 × `ChangeContents` (`base/…/1259`), 1 × `Created`. **31 of 31 crashes hit the
Postgres data dir.** None happened 08-17 → 08-23. **[inference]** The rising frequency (1–2 a week
in August, 4–5 a day now) tracks the growth in parallel worktrees, xdist runs and databases.

### 3e. Host kernel and journal

**[fact]**
- `dmesg`: `Operation not permitted` (no sudo).
- `journalctl -k`: no OOM kill. The only hits are `OOM killer disabled./enabled.` pairs at 09-27
  10:47 and 18:57 SAST, which are the kernel freezing tasks around a suspend/resume. Neither lines
  up with a crash. Also AppArmor denials from the Discord snap (irrelevant).
- `journalctl --user` around 15:56–16:01 SAST: nothing from qemu or the host kernel. The
  `com.docker.backend` entries mirror the backend log above.
- `journalctl -u docker` shows only the native (non-Desktop) dockerd. Nothing relevant.

## 4. Postgres settings and activity (live, 14:42 UTC)

**[fact]** Stock defaults:

```
max_connections 100 | superuser_reserved_connections 3 | shared_buffers 128MB (16384 x 8kB)
work_mem 4MB | maintenance_work_mem 64MB | max_parallel_workers_per_gather 2
idle_session_timeout 0 | idle_in_transaction_session_timeout 0
fsync on | synchronous_commit on | full_page_writes on | max_wal_size 1GB | checkpoint_timeout 300s
log_min_messages warning | logging_collector off | log_connections off | log_disconnections off
dynamic_shared_memory_type posix | /dev/shm 64M (1.1M used)
```

`pg_stat_activity` (7.5 min after restart, so it says nothing about the load before the crash):

```
db_educator_interface_3_panel_framework_dialogs | client backend | idle   | 2 | age 00:02:30  (172.18.0.1, the runserver on :8561)
postgres                                        | psql           | active | 1 | (this query)
+ checkpointer, background writer, walwriter, autovacuum launcher, logical replication launcher
```

- **[inference]** `fsync=on` plus a 16 MB WAL segment per ~16 MB of writes means every write goes
  through the virtiofs share and generates host file events. Dev-only `fsync=off` /
  `synchronous_commit=off` / `full_page_writes=off` would cut the writes. They would not remove
  the `DROP DATABASE` unlink storms.

## 5. Databases vs worktrees

**[fact]** 124 databases, 1,494 MB total (each 7–17 MB). 16 branches are checked out in worktrees
(the bare repo root has none). The 64 `_gwN` xdist databases go up to `_gw15`, which means
`-n auto` → 16 workers on this 16-core machine.

Classification, reproducing `branch_to_db_name` (lowercase, `[^a-z0-9]`→`_`, truncate to 50,
prefix `db_`):

| class | count | size | notes |
|---|---|---|---|
| live worktree | 22 | 292 MB | 10 `db_*` + 12 `test_db_*` (incl. `…components_gw15`, `…enforcement_checks_gw4/_gw6`) |
| stale (no worktree) | 87 FLS + 5 `db_fcweb_*` | 1,182 MB | e.g. 16× `test_db_footer_area_gw0..15`, 16× `test_db_more_prominent_signup_button_gw0..15`, `test_db_a690daf` (detached-HEAD short SHA) |
| other | 10 | 92 MB | `db`, `test_db`, `postgres`, `template0`, `template1`, and **another project**: `ticketville_main`, `ticketville_main_copy`, `ticketville_crud_events`, `test_ticketville_*` |

- **[inference]** `db_fcweb_*` (deploy, full_prod_demo, home_hero_text_responsive, main, sitemap)
  follows the FLS naming but matches no FLS branch. It is most likely a downstream project on the
  same server using the same convention, so treat it as another project's data, not FLS stale
  data. Ticketville is definitely another project. **This server is shared across projects**, so
  a cleanup tool must only drop names that match FLS's own convention *and* no longer map to a
  worktree, and even that would catch `db_fcweb_*`.
- **[fact]** Truncation: one live branch is truncated,
  `test-organisation-and-hygene-2-sdd-review-and-boy-scout` → `db_test_organisation_and_hygene_2_sdd_review_and_boy_`.
  The stale `db_upgrade_notes_name_a_storage_class_that_does_not_e` is truncated too. There are no
  collisions among the current 16 branches. `test_` + 53 chars + `_gwNN` stays under Postgres's
  63-byte limit.
- **[fact]** 6 live worktrees have no dev DB yet: auto-run-tailwind-watch,
  compliance-form-randomization, content_snapshots, in-app-feedback, qa-boy-scout-throwaway,
  xapi_implementation.
- **[inference]** 125 database directories = 85,651 files on the bind mount. Each dropped test DB
  unlinks ~300+ files, and one 16-worker run that uses `--create-db` or runs without `--reuse-db`
  drops and recreates 16 of them. That is the "Removed base/<oid>/<file>" storm seen in §3c.

## 6. Client processes (host, 14:43 UTC)

**[fact]**
- **pytest: none running**, so no orphan pytest processes (no python/pytest process has PPID 1
  apart from Ubuntu's `unattended-upgrade-shutdown`). The orphan-pytest hypothesis could not be
  confirmed or ruled out, because the crash had already killed every connection.
- One leftover agent shell (pid 3219981, running 8 h 45 min) loops
  `until ! ps aux | grep -q "[p]ytest"; do sleep 5; done; echo "pytest finished"`. **[inference]**
  It matches its own command line (which contains `pytest finished`) and can never exit. It holds
  no DB connection, but it shows that agent wait loops leak.
- 2× `manage.py runserver 8561` in `educator-interface-3-panel-framework-dialogs` (started 9 and
  7.7 min earlier, each with an autoreloader child). Only one can own the port.
- **Leaked Playwright MCP servers:** 85 `playwright-mcp`/`npm exec @playwright/mcp` processes
  (3.1 GB RSS). 9 of them are more than a day old. 36 Chrome processes (4.1 GB RSS), including a
  headless Playwright profile. Python total 1.3 GB, qemu 1.4 GB.
- **[inference]** Host memory pressure (13 GiB swapped) comes mostly from browsers and leaked MCP
  servers, not from Postgres. It could make the host-side event injector slow, but nothing links
  the two directly.

## 7. Other relevant observations

- **Evidence survival [fact]:** the container log is `json-file` with no rotation, but it is
  deleted whenever the container is recreated (it was today at 13:18). The Docker Desktop logs
  hold the real evidence. `vm/console.log*` covers only ~2.5 days (19 rotated files, 1 MB each)
  and `host/com.docker.backend.log*` covers ~1 day. The host `journalctl --user` keeps
  `com.docker.backend` output back to 2026-08-17 and is the best long-term record.
- **[fact]** Container recreated at 13:18:14 while the VM had been up since 11:50, so this was not
  a crash. The cause is unknown. **[inference]** A likely cause is `docker compose up` run from a
  different worktree's `dev_db/`. The project name is `dev_db` in every worktree, but the relative
  `./docker-entrypoint-initdb.d` mount path differs, so Compose sees a changed config and recreates
  the container. That kills live connections and throws away the log, and it is a second,
  independent way the DB "goes down".
- **[fact]** The `FATAL: the database system is starting up` burst at ~1.1 s intervals shows some
  client polling during startup. After the restart there was a `psql` without `-U` (role "root").

status: ok
