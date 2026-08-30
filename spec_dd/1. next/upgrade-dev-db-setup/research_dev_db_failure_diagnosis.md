# Why the dev database stack keeps going unusable

Diagnosis of the recurring failure where the shared dev PostgreSQL container stops serving and only
a Docker Desktop restart brings it back. Taken from the live machine on 2026-08-30.

The suspected culprit was the pile of concurrent Claude Code worktree sessions. It provably is not.

## What it is not

**No script in the repo kills the stack.** Nothing under `freedom_ls/`, `claude_plugins/`,
`.claude/` or `dev_db/` runs `docker kill`, `docker stop`, `docker compose down` or
`docker system prune` against it. The one script that could, `dev_db/cleanup_devdb.sh`, targets a
container named `dev_db_dbs_1`. The live containers are `dev_db-postgres-1` and `dev_db-mailpit-1`,
so it has been a no-op for a long time.

**The containers are never killed.**

```
RestartCount=0  ExitCode=0  OOMKilled=false
```

**Both recorded shutdowns were clean GUI quits.** The retained Docker Desktop logs cover
2026-08-29 14:00 onward and hold two shutdowns, at 14:25 and 06:54. Both look like this:

```
POST /app/quit   Docker-Desktop/4.43.2 (Linux; x64; GUI)
main.tracker: sending event: actionMenuQuit
```

That is the Quit item in Docker Desktop's own menu. It is the fix being applied, not the fault. The
`electron shutdown by signal: killed` line two seconds later belongs to the normal teardown
sequence. So the stack goes unusable *while Docker is still running*, and the restart is what the
operator does about it.

## Root cause: the file-sharing layer stalls

`com.docker.backend.log` repeats this every ten seconds. The duration only climbs, and it resets
only when Docker restarts.

```
14:00:28  grpcfuse.volume [W] unable to inject 50 events for 10s
14:25:38  grpcfuse.volume [W] unable to inject 50 events for 24m20s
00:34:15  grpcfuse.volume [W] unable to inject 50 events for 9h38m30s
04:54:25  grpcfuse.volume [W] unable to inject 50 events for 13h58m40s
```

The volume watcher falls behind within a minute or two of every start and never catches up. Across
the three retained log files it fired 5,195 times.

Docker Desktop serves the PostgreSQL data directory over that same layer, as a host bind mount:

```
bind /home/sheena/.lms_postges_dev_data -> /var/lib/postgresql/data          (645 MB)
```

`dev_db/docker-compose.yaml` sets it as `${DB_DATA_PATH:-~/.lms_postges_dev_data}`. Once the
file-sharing layer is backed up, database I/O degrades, and a Docker restart is the only thing that
clears it.

The event load feeding the backlog comes from the working setup around it. Fifteen git worktrees sit
under one shared host folder, each with `node_modules`, Tailwind watchers, pytest runs, and editor
and agent file watchers.

## Database and connection sprawl

The container sits at **37 databases** when nothing is running, against the PostgreSQL default of
`max_connections=100`. Sampled again a few minutes later while other worktrees were testing, it was
at **52 databases and 23 connections**. Fifteen databases appeared and vanished inside that window,
which is the churn of xdist workers creating and dropping their own.

`claude_plugins/fls-dev/scripts/dev_db_delete.sh` drops `db_<branch>` and `test_db_<branch>`, but
not the per-worker databases pytest-xdist creates. Nine have leaked so far, and five of them belong
to branches that no longer have a worktree:

```
test_db_final_pre_deploy_db_structure_cleanup_gw11
test_db_final_pre_deploy_db_structure_cleanup_gw15
test_db_prepare_to_deploy_gw0
test_db_prepare_to_deploy_gw5
test_db_better_course_progress_tracking_gw8
test_db_better_course_progress_tracking_gw12
test_db_extract_forms_into_seperate_app_gw13
test_db_learners_associated_with_organisations_gw1
test_db_prod_bucket_setup_gw9
```

The `_gw15` suffix shows xdist running up to 16 workers in a single run. A handful of worktrees
testing at once will exhaust the 100-connection ceiling, and from inside a test run that reads as
the database having died.

The container is also shared with unrelated projects. `ticketville_*` and `fcweb_*` databases sit
alongside the FLS ones.

## Contributing host pressure

| | |
|---|---|
| RAM | 26 GB used of 31 GB, ~5 GB available |
| Swap | 15 GB in use of 39 GB |
| Docker VM | `-m 7953 -smp 16` (8 GB, 16 vCPUs) |
| Running at once | 15 worktrees, ~10 `claude` processes, several VS Code windows, Chrome |

## Machine-level recommendations

None of this lives in the repo, so none of it belongs in the spec. It is recorded here because it is
half the fix.

- Narrow Docker Desktop's shared-folder list so `~/workspace` is not mirrored wholesale.
- Try switching between VirtioFS and gRPC-FUSE in Settings, Resources, File sharing.
- Shrink the VM. 8 GB and 16 vCPUs is the wrong split on a host already 15 GB into swap.
- Keep fewer worktrees hot at once.
