# Upgrade the dev database setup

## Problem

The shared dev PostgreSQL container stops serving partway through a working day, and the only thing
that brings it back is quitting and restarting Docker Desktop. It happens often enough to be a tax
on every worktree.

Nothing is killing the container. The PostgreSQL data directory is a **host bind mount**, so Docker
Desktop's file-sharing layer serves every read and write, and that layer falls behind within a
minute or two of every start and never catches up. Database I/O degrades while Docker itself stays
up. Two smaller problems ride alongside. `dev_db_delete.sh` never drops the per-worker databases
pytest-xdist creates, so they accumulate forever, and the one container carries 37 databases at rest
against the default `max_connections=100`, a ceiling a few worktrees testing at once will exhaust.

## Chosen approach

Three changes, in that order of value.

**Move the data directory onto a named Docker volume.** `dev_db/docker-compose.yaml` currently
mounts `${DB_DATA_PATH:-~/.lms_postges_dev_data}` from the host. A named volume lives inside the
Docker VM's own disk and never crosses the file-sharing boundary. That takes the database out of
the failing path instead of making it fail less often.

Nothing is migrated. The existing 645 MB is disposable, including the `ticketville_*` and `fcweb_*`
databases belonging to other projects, so the cutover is a clean break: bring the stack down, point
the compose file at the volume, bring it up, and let each worktree rebuild its own database with
`db_recreate.sh`. No dump and restore step.

**Teach `dev_db_delete.sh` about the worker databases.** It drops `db_<branch>` and
`test_db_<branch>` today. It also needs the `test_db_<branch>_gw*` set, plus a way to sweep
databases whose branch no longer exists. The leaked ones are already there and no command removes
them.

**Put a ceiling under concurrent test runs.** Either raise `max_connections` on the container, bound
the xdist worker count, or both, so a test run in one worktree cannot starve another.

## What we want (high level)

- **A dev database that survives a full working day** across many worktrees without a Docker
  restart.
- **Per-branch isolation unchanged.** `branch_to_db_name` and the `db_<branch>` / `test_db_<branch>`
  scheme stay exactly as they are. This is about where the bytes live, not how they are named.
- **Test runs that cannot starve each other.** Concurrent pytest across worktrees stays inside the
  connection ceiling.
- **No orphaned databases.** Tearing down a worktree removes everything that worktree created, and
  there is a way to clear what has already leaked.
- **A reset path that still works.** "Wipe my dev database and start again" must stay a single
  documented command once the directory it used to delete no longer exists.

## Design considerations to resolve in the spec

- **The `db_clear.sh` contract breaks.** It wipes the data directory by deleting `${DB_DATA_PATH}`
  outright. Against a named volume that becomes `docker volume rm`, which behaves differently: the
  volume must not be in use, so the container has to come down first. The script belongs to the
  **ds** plugin, is generic rather than FLS-specific, and has a generated wrapper in
  `.claude/ds/scripts/` and a template in `django-stack/templates/wrapper_scripts/`. The change
  reaches all three.
- **Keeping the sanitisation in sync.** `dev_db_delete.sh` already carries a note that its
  branch-name sanitisation mirrors `branch_to_db_name` in `freedom_ls.base.git_utils`. A
  pattern-matched drop of `test_db_<branch>_gw*` must not drift from it, and a sweep of dead-branch
  databases needs a rule for what counts as dead.
- **Where the connection ceiling is enforced.** A `command:` override on the compose service is
  visible and applies to everyone. Capping pytest's `-n` sits closer to the cause but is easy to
  bypass. They are not exclusive.
- **Downstream propagation.** `dev_db/docker-compose.yaml` and the `dev_db_*` scripts ship in the
  concrete-project template, so the spec must budget for `fls-dev:update_template_repo` and
  `fls-dev:update_upgrade_notes`. Existing downstream projects have a live bind mount, and the
  upgrade notes have to say plainly that switching drops whatever is in it.
- **Whichever worktree brings the stack up owns the mount paths.** The initdb directory is currently
  bind-mounted from the `main` worktree, because that is where `docker compose up` was run. Decide
  whether that is fine or should be made explicit.

## Out of scope

- **Per-worktree database containers.** One shared PostgreSQL on `:6543` stays.
- **Production database configuration.** `config/settings_prod.py` is untouched.
- **Docker Desktop and host-machine tuning.** Real, and half the fix, but not repo work. The
  recommendations are recorded at the end of the research file instead.

## Research

See `research_dev_db_failure_diagnosis.md` in this directory for the evidence: the log trail showing
the file-sharing layer falling behind, the container state ruling out a kill, and the full database
and connection inventory.
