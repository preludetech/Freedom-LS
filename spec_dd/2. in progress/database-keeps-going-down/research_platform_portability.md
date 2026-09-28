# Research: will the dev database fixes work on every contributor's machine?

Scope: this repo's `dev_db/docker-compose.yaml` runs a single shared `postgres:17` container for
every worktree. The idea's planned fixes are compose-level: `restart:`, `healthcheck:`, `shm_size`,
a memory limit, `command: postgres -c ...` tuning flags, maybe non-durable settings, and a fixed
reset script (see `idea.md`, `research_isolation_options.md` Option 1). This asks: do those specific
knobs behave the same on every platform a contributor plausibly runs Docker on? Everything below is
web-sourced unless marked "(repo)"; anything I could not pin to a primary source is marked
**unverified**.

---

## 1. Per-knob support matrix

| Knob | Linux native (cgroup v2) | Docker Desktop macOS (Apple Silicon) | Docker Desktop Windows (WSL2) | OrbStack | Colima | Podman + podman-compose/`podman compose` | Rancher Desktop |
|---|---|---|---|---|---|---|---|
| `restart: unless-stopped` (survives daemon/app restart) | Works — daemon (`dockerd`) restarts containers with a restart policy when it starts, including on boot if `dockerd` is a systemd service enabled at boot. | Works only while "Start Docker Desktop when you log in" is enabled in Settings → General; if Desktop isn't running, nothing restarts. [Docker Desktop settings](https://forums.docker.com/t/docker-desktop-auto-start-upon-server-reboot/135332) | Same as macOS — depends on Desktop's "start on login"; the WSL2 backend itself doesn't independently relaunch containers. | OrbStack starts on login by default (menu-bar app) similarly to Desktop; **unverified** whether it restarts `unless-stopped` containers identically to Desktop — no primary doc found, treat as Desktop-equivalent but unconfirmed. | Colima VM must be started explicitly (`colima start`) or via a login item/launchd job you set up yourself; there's no menu-bar auto-start by default, so `unless-stopped` inside a VM that isn't running does nothing until `colima start` runs. **unverified** exact behavior of restart policies once the VM *is* up — inference from colima being a thin Lima wrapper around plain `dockerd`, which does honor restart policies once running. | **Gotcha:** Podman has no persistent daemon; at boot, `podman-restart.service` runs `podman start --all --filter restart-policy=always` — it only restarts containers with policy `always`, and explicitly **skips `unless-stopped`** containers on boot-time restart even though `unless-stopped` is meant to persist across restarts. Confirmed bug/behavior mismatch vs Docker semantics. [containers/podman#22451](https://github.com/containers/podman/issues/22451) | Rancher Desktop uses containerd or dockerd (moby) backend depending on config; **unverified** how its restart-policy/auto-start interacts — no primary doc found. |
| `healthcheck` (`test`, `interval`, `timeout`, `retries`) | Full support, all Compose/Engine versions in common use. | Full support (same Compose binary as Linux, runs inside the Desktop VM). | Full support. | Full support (OrbStack implements the Docker API). | Full support (runs real `dockerd`+Compose inside the Lima VM). | Supported by `podman compose`/`podman-compose`, but historically some healthcheck fields lagged Docker's; current `podman compose` (Podman ≥4) maps to native `HealthCheck` — **verify on the actual podman version in use**, older podman-compose (python, Docker-Compose-v1-compatible) had gaps. | Supported (same underlying engines). |
| `healthcheck.start_period` | Supported since Docker Engine 17.x / Compose file v2.3+. Universal today. | Same. | Same. | Same (API-compatible). | Same. | Supported in recent Podman; **unverified** exact minimum version. | Same. |
| `healthcheck.start_interval` | Requires **Compose ≥2.20.2 and Docker Engine ≥25.0** (needs Engine API supporting the field; older Engine silently ignores or errors). [docker/compose#10830](https://github.com/docker/compose/issues/10830), [docker-library/docker#473](https://github.com/docker-library/docker/issues/473) | Bundled Compose/Engine versions in current Desktop releases satisfy this, but a contributor on an old Desktop install (pre-2024) may not. | Same caveat as macOS. | **unverified** whether OrbStack's Docker API shim implements `start_interval`; treat as unconfirmed until tested. | Depends on the `dockerd`/Compose version colima installs — colima lets you pick the Docker version; an older pinned version could lack it. **unverified**, verify by running `docker compose version` and `docker version` inside the target machine before relying on it. | `podman compose`/`podman-compose` supported? **unverified** — not found in the podman documentation searched; do not rely on `start_interval` if podman is a supported contributor path, or gate it behind a version check. | **unverified**. |
| `shm_size` | Full, standard. | Full, standard (applies to the container inside the Desktop VM). | Full, standard. | Full, standard (API-compatible). | Full, standard. | **Gotcha:** rootless Podman containers default `/dev/shm` to **64 MB** (same stock default Postgres already has today), and there is a **known bug**: `shm_size` in a compose file is **ignored when using docker-compose with a Podman backend** (i.e. running `docker-compose`/`docker compose` pointed at the Podman socket rather than native `podman compose`). [podman#18461](https://github.com/containers/podman/issues/18461). Native `podman run --shm-size` works standalone but is rejected inside a **pod** with default IPC sharing (`podman pod create` shares one `/dev/shm` across the pod and has no `--shm-size` flag) — relevant if `podman compose` maps the compose "project" onto a single pod, which some podman-compose implementations do. [podman#1770](https://github.com/containers/podman/issues/1770) | Full, standard (containerd/moby backend). |
| `mem_limit` (legacy top-level Compose v2 field) | Full support outside Swarm mode; this is the field that actually works for a plain `docker compose up` (not `deploy.resources.limits.memory`, which **Compose ignores outside Swarm mode / `docker stack deploy`** and only warns "will be ignored"). [docker/docs#14185](https://github.com/docker/docs/issues/14185), [Docker forums](https://forums.docker.com/t/limit-resources-without-swarm/98524) | Same — `mem_limit` is honored as a cgroup limit inside the Desktop VM's Linux kernel. | Same. | Same (implements the same cgroup-backed limits). | Same (real Linux kernel cgroups inside the Lima VM). | `podman-compose`/`podman compose` maps `mem_limit` to `--memory`; broadly supported, but **rootless** Podman on a host where the current user's cgroup delegation isn't configured (no `systemd` user session, or cgroup v1 host) can silently fail to apply memory limits — a known rootless-cgroups caveat, not specific to this field but affects it. **unverified** exact failure mode; flag as a rootless-Podman risk. | Same as other Linux-kernel-backed engines. |
| `deploy.resources.limits.memory` | **Ignored** by plain `docker compose up` everywhere (Swarm-only field) — same on every platform. Do **not** use this field for the memory limit; use `mem_limit`. [docker/compose-cli#1523](https://github.com/docker/compose-cli/issues/1523) | Same. | Same. | Same. | Same. | **unverified** whether podman-compose even parses `deploy.resources` at all outside its own Kube-generation path; assume it's a no-op like elsewhere. | Same. |
| `oom_score_adj` | Supported top-level Compose field since `docker/compose#3590` merged; range **-1000..1000**, part of the Compose Specification. [compose-spec/spec.md](https://github.com/compose-spec/compose-spec/blob/main/spec.md) | Same (Compose Spec field, engine-version-independent once your Compose is new enough). | Same. | **unverified** whether OrbStack's engine shim applies the underlying `--oom-score-adj` flag identically. | Same as Linux (real kernel underneath). | **unverified** — not found in podman docs searched; Podman's own OOM handling differs (Podman doesn't run a long-lived daemon so "the daemon's own `oom_score_adj`" framing doesn't map 1:1) — treat as unconfirmed/likely unsupported until checked against the installed podman-compose version. | **unverified**. |
| `command: postgres -c ...` (postgres flag overrides) | Standard Compose `command:` override — works identically on every engine that runs the `postgres` entrypoint script unmodified; this is an application-level concern (Postgres itself), not a Docker-engine feature, so it is the **most portable** knob in this whole list. | Same. | Same. | Same. | Same. | Same — `command:` is basic Compose syntax, universally supported. | Same. |
| `stop_grace_period` | Standard, long-supported Compose field controlling SIGTERM→SIGKILL grace window on `down`/`stop`. Universal. | Same. | Same. | Same. | Same. | Supported by `podman compose`. | Same. |

**Minimum versions worth calling out explicitly in whatever the fix documents:** Compose ≥2.20.2 +
Engine ≥25.0 if `start_interval` is used; anything older silently drops or errors on that one field.
Everything else in the plan (`restart`, `healthcheck` core fields, `shm_size`, `mem_limit`,
`oom_score_adj`, `command`, `stop_grace_period`) works on Compose v2/Compose Spec generally, which
has been the default `docker compose` (space, not hyphen) for several years.

---

## 2. VM memory ceiling per platform (why a per-container `mem_limit` isn't the whole story)

Every non-Linux-native engine runs Postgres inside a VM with its **own** memory ceiling, independent
of whatever `mem_limit`/`shm_size` the compose file sets on the container. If the VM itself gets
OOM-pressured (by this Postgres container *plus* whatever else is running inside the same VM — other
projects' containers, other worktrees' containers, IDEs' language servers if run inside a devcontainer,
etc.), the VM's own OOM killer can kill Postgres regardless of a generous per-container limit.

| Platform | Default VM memory ceiling | Source |
|---|---|---|
| Docker Desktop (macOS, Windows non-WSL2 backend) | **50% of host RAM** on platforms that expose the setting (e.g. 8 GB VM on a 16 GB Mac). Configurable in Settings → Resources. | [OneUptime — Docker Desktop resource management](https://oneuptime.com/blog/post/2026-02-08-how-to-use-docker-desktop-resource-management-settings/view) |
| Docker Desktop on Windows using the **WSL2** backend | Not set by Desktop directly — delegated to WSL2's own limit (see next row); Desktop UI shows "Resource allocation is managed by WSL 2." | same |
| WSL2 (bare, or under Desktop) | **50% of total host RAM, or 8 GB, whichever is smaller** (build ≥20175); older builds could use up to 80%. Configurable via `%UserProfile%\.wslconfig` `[wsl2]` `memory=`. Swap defaults to 25% of total RAM or 2 GB, whichever is **larger**. | [microsoft/WSL#9636](https://github.com/microsoft/WSL/issues/9636), [Aleksandr Hovhannisyan — Limiting Memory Usage in WSL2](https://www.aleksandrhovhannisyan.com/blog/limiting-memory-usage-in-wsl-2/) |
| OrbStack | **8 GB by default**, but OrbStack allocates *dynamically* (usage starts low, grows on demand, unused memory returned to macOS) rather than reserving it up front — configurable in Preferences or `orb config`. | [OrbStack docs — Settings](https://docs.orbstack.dev/settings), [OrbStack — dynamic memory](https://orbstack.dev/blog/dynamic-memory) |
| Colima | **2 GiB by default** (`colima start` with no flags creates a 2-CPU, 2 GiB VM) — this is the smallest default of any platform surveyed and is plausibly *too small on its own* for a Postgres container that also gets a generous `mem_limit`/`shm_size` from the compose fix; a contributor on Colima defaults would need `colima start --memory 4` (or higher) before the compose-level fix can do anything. | [abiosoft/colima README](https://github.com/abiosoft/colima) |
| Podman machine (macOS/Windows, since Podman itself needs a VM there too) | **unverified** exact default (Podman machine's `podman machine init` default is commonly cited as 2 GiB in community writeups, matching Colima's Lima-based default, but no primary doc was confirmed in this pass) — flag as needing a direct check (`podman machine inspect`). | unverified |
| Rancher Desktop | **unverified** default VM memory (has a Preferences → Virtual Machine memory slider; no default value confirmed in this pass). | unverified |
| Linux native Docker Engine (no VM) | N/A — no VM layer; the container's `mem_limit` is enforced directly by the host kernel's cgroup, and the *host's* total RAM (and its own OOM killer) is the real ceiling. This is the one platform where "no VM ceiling" removes a whole failure class. | inference from architecture |

**How a contributor checks their own ceiling:** `docker info --format '{{.MemTotal}}'` reports what
the Docker **engine** (i.e., inside the VM, if there is one) sees as total memory — this is the
number to compare against the compose file's `mem_limit` + whatever else runs in the same VM, not the
host's own RAM. On WSL2, `wsl.exe --status` / `.wslconfig` and Task Manager's "Vmmem" process show
the WSL-level ceiling separately from Desktop's own setting when using the WSL2 backend.

**Implication for the plan:** a `mem_limit`/`shm_size` combination tuned assuming "plenty of host RAM
available" can be silently capped by Colima's 2 GiB default or WSL2's 8 GB-or-50%-whichever-is-smaller
rule before Postgres ever gets OOM-killed by its *own* limit — the fix's documentation should tell a
contributor to check their engine's visible `MemTotal` (or equivalent) once, not assume the host RAM
figure applies.

---

## 3. Bind-mounted data directory vs a named volume

Current state (repo): `dev_db/docker-compose.yaml` bind-mounts `${DB_DATA_PATH:-~/.lms_postges_dev_data}:/var/lib/postgresql/data`.

**Performance:**
- On Linux native, a bind mount is a normal filesystem path with native fsync cost — no penalty vs a
  named volume (both ultimately resolve to the same overlay/host filesystem).
- On Docker Desktop for Mac, file sharing for bind mounts goes through **VirtioFS** (default since
  Desktop 4.6, replacing the much slower gRPC-FUSE); this cut bind-mount filesystem-op latency by up
  to 98% for some workloads and closed most of the historic "Docker on Mac is slow" gap, but bind
  mounts are still cited as roughly **3x slower than native** even with VirtioFS, versus a **named
  volume**, which lives entirely inside the Linux VM's own filesystem and pays no cross-OS
  translation cost at all. There are also specific reports of VirtioFS **breaking Postgres on
  first start** (`could not open file pg_wal/...: No such file or directory`) and of VirtioFS being
  measurably worse than the old gRPC-FUSE specifically for Postgres data-seeding workloads — Postgres
  is one of the workloads called out as *not* benefiting cleanly from the VirtioFS migration.
  [docker/for-mac#6363](https://github.com/docker/for-mac/issues/6363), [docker/for-mac#6270](https://github.com/docker/for-mac/issues/6270), [Jeff Geerling — VirtioFS 4x faster](https://www.jeffgeerling.com/blog/2022/new-docker-mac-virtiofs-file-sync-4x-faster/)
- On Docker Desktop for Windows (WSL2 backend), a bind mount to a **Windows-side** path (e.g. a repo
  cloned under `C:\Users\...`) crosses the Windows/WSL2 9P-based file-sharing boundary and is
  meaningfully slower than a bind mount to a path already inside the WSL2 filesystem (e.g. under
  `/home/...`), which is itself close to native. `~/.lms_postges_dev_data` (repo default) expands to
  whatever `$HOME` is in the shell that runs `docker compose up` — on WSL2 that's the Linux-side
  home, so this default is already doing the *right* thing there; a contributor who instead sets
  `DB_DATA_PATH` to a Windows-side path (e.g. to inspect files from Explorer) would reintroduce the
  slow-path case. **This is a real portability trap specific to how `DB_DATA_PATH` is set, not to
  the compose file itself.**
- A **named Docker volume** sidesteps all of the above on every VM-backed platform (Desktop/Mac,
  Desktop/WSL2, OrbStack, Colima) because Docker manages the storage entirely inside the VM's own
  filesystem — no host/VM path translation, no VirtioFS/9P/gRPC-FUSE layer in the write path at all.

**Permissions/ownership:**
- The official `postgres` image runs as **uid 999** (`postgres` user) inside the container. On a
  Linux **bind mount**, the files on the host end up owned by uid 999 as seen from the host — if that
  uid doesn't match the contributor's own uid, later host-side operations (deleting the directory,
  inspecting files) need `sudo`. This is exactly why the existing `cleanup_devdb.sh` shells out to
  `sudo rm -r ./gitignore` (repo) — the bind-mounted data directory is owned by uid 999, not the
  invoking user, so a plain `rm -r` fails with permission denied.
  [Docker Hub — postgres official image](https://hub.docker.com/_/postgres), [Markaicode — PostgreSQL Docker permission denied](https://markaicode.com/errors/postgresql-docker-deployment-failed-fix/)
- On Docker Desktop for Mac/Windows, this uid mismatch is largely invisible day-to-day (the bind mount
  is translated through the VM boundary and the host OS doesn't see a literal uid-999-owned file the
  same way Linux does), but any contributor on **Linux** hits the `sudo rm` requirement every time,
  which is what the current script encodes.
- A **named volume** avoids the ownership question entirely: Docker creates and manages it, uid 999
  matches from creation, and `docker compose down -v` (or `docker volume rm`) removes it without
  needing `sudo`, on every platform, including Linux. This directly removes the reason the current
  reset script needs `sudo`.

**What breaks for existing contributors if the storage location/mechanism changes:**
- Anyone with an existing `~/.lms_postges_dev_data` directory from before the change would, on
  switching to a named volume, effectively start from an **empty database** (Docker won't
  auto-migrate bind-mount contents into a new named volume) — their existing worktree databases
  would need to be recreated via `dev_db_init.sh` + `migrate` again. This is low-cost here because
  dev/test data is meant to be disposable and rebuilt from migrations (per the idea's own framing:
  "Dev-only non-durable settings are fine, because the data is rebuilt from migrations"), but it is a
  one-time break worth calling out in whatever change note ships this.
- **Postgres major-version pinning of the data directory** applies identically to either storage
  mechanism: a `postgres:17` data directory (bind-mounted or named-volume-backed) cannot be read by a
  `postgres:18` container without `pg_upgrade`; this is unrelated to bind-mount-vs-volume and would
  only matter if the compose file's image tag is bumped later — not a portability risk introduced by
  this fix, just noting it's orthogonal.
- If the fix keeps the bind mount (rather than switching to a named volume) but changes `DB_DATA_PATH`'s
  default path, any contributor with data already at the old default path would silently get a
  **fresh, empty** database at the new path unless the change also migrates or documents moving the
  old directory.

**Recommendation surface (not a decision, just what the sources point at):** switching to a named
volume removes two of the three platform-specific bind-mount problems found above (Mac/Windows
file-sharing slowness, Linux uid-999 `sudo` requirement) and is what most of the tuning write-ups in
`research_isolation_options.md` implicitly assume; the tradeoff is that a named volume is less
directly inspectable from the host shell (no `ls ~/.lms_postges_dev_data`), which matters if any dev
workflow relies on poking at the raw data directory (grep for this before switching — none found in
this repo's scripts).

---

## 4. Container naming and a portable reset recipe

**Current state (repo):** `dev_db/cleanup_devdb.sh` hardcodes `docker kill dev_db_dbs_1` /
`docker rm dev_db_dbs_1` — this is **Compose v1's** underscore-joined naming
(`<project>_<service>_<index>`). Modern `docker compose` (the Go-based v2 CLI, the default for
several years) names containers `<project>-<service>-<index>` with **hyphens**, and the compose
file's service is named `postgres`, not `dbs` — so under a modern Compose CLI, the real container
name is `dev_db-postgres-1`, not `dev_db_dbs_1`. The script as written targets a name that doesn't
exist under today's tooling, confirming the idea's own note that "the documented reset path is
broken" (`idea.md`) — this is a **fact**, not new research, but is the concrete mechanism behind that
claim.

**Portable ways to address the container without hardcoding a name:**
- `docker compose -f dev_db/docker-compose.yaml exec postgres <cmd>` / `... down` / `... down -v` —
  addresses the service by its **compose-file-relative service name** (`postgres`), which is stable
  regardless of Compose v1-vs-v2 naming, project name, or container-id churn. This is the portable
  replacement for the current script's hardcoded container name.
- A top-level `name:` key in the compose file pins the **project name** explicitly (overriding the
  directory-basename default described below) if that's ever wanted; not strictly required here (see
  next point) but is the documented, portable way to fix a project name rather than relying on the
  implicit default.
- A `container_name:` field would pin the exact container name too, but is generally discouraged
  by Compose's own docs when a service might ever be scaled, and isn't needed if `exec`/`down` always
  address the service by name via `-f` instead of a raw `docker kill <name>`.

**Portable "reset the dev DB" recipe:** once storage is a named volume (§3), a full reset is simply
`docker compose -f dev_db/docker-compose.yaml down -v` (stops and removes the container **and** the
named volume) followed by `docker compose -f dev_db/docker-compose.yaml up -d` — no `sudo`, no
hardcoded container name, and it works identically on every platform in the matrix (Compose `down -v`
semantics are engine-version-independent Compose Spec behavior). If the bind mount is kept instead,
`down -v` won't remove host-side bind-mounted data (Compose only manages volumes it created), so the
reset recipe would still need an explicit `rm -rf "$DB_DATA_PATH"` (potentially `sudo` on Linux, per
§3) — another point in favor of the named-volume switch specifically *because* it simplifies the
reset script this idea also wants fixed.

**Project naming across worktrees — does every worktree reach the same container?**
Docker Compose's project-name resolution order is: `-p` flag → `COMPOSE_PROJECT_NAME` env var →
top-level `name:` in the compose file → **the basename of the directory containing the compose file**
(or the first `-f` file's directory) → basename of the current directory if no file is given.
[Docker docs — Specify a project name](https://docs.docker.com/compose/how-tos/project-name.md)

Because every worktree is a **full checkout** of the repo (git worktrees check out the whole tree,
not just the current branch's changed files), every worktree has its own `dev_db/docker-compose.yaml`
at `<worktree-path>/dev_db/docker-compose.yaml` — and the **directory basename is always `dev_db`**,
regardless of what the worktree's own top-level directory is named (`database-keeps-going-down`,
`user-communication-3-messaging-policy`, etc.) or where it lives on disk. So today, running
`docker compose up` from any worktree's `dev_db/` (or `docker compose -f <worktree>/dev_db/docker-compose.yaml up` from anywhere) resolves to the **same default project name, `dev_db`**, and therefore the
**same container** across every worktree — confirmed from Compose's documented resolution rule, not
just inference; this is *why* the current one-shared-container design already works as intended
without every worktree needing to coordinate a project name explicitly.

**Race / config-drift risk this creates:** because the project name is the same everywhere, Compose's
own change-detection (§ below) becomes a cross-worktree hazard once the compose file itself is edited
on some branches but not others. `docker compose up` recreates a container when the **service
configuration Compose computes changed** since the container was created (image, environment,
command, `shm_size`, `mem_limit`, `healthcheck`, etc. are all part of that hash) — `--force-recreate`
forces it unconditionally, but a *plain* `docker compose up` already recreates on a detected
config diff even without that flag.
[Docker docs — compose up](https://docs.docker.com/reference/cli/docker/compose/up/)

Concretely: once this fix lands on the `database-keeps-going-down` branch's `dev_db/docker-compose.yaml`
(with the new `restart:`/`healthcheck:`/`shm_size`/`mem_limit`/`command:` lines) but **before** it's
merged to `main`, any other worktree still on an unmerged branch has the **old** compose file. If that
worktree's contributor (or their agent) runs `docker compose up` against the same `dev_db` project
name, Compose computes the config hash from *that worktree's* file and will detect a mismatch against
whatever container is currently running (whichever worktree most recently started it) and **recreate**
the container using the old, unfixed config — silently reverting the other worktree's fix, and
potentially racing if two worktrees run `up` around the same time (last one to run `up` wins; Compose
doesn't merge or warn across worktrees, since from its perspective these are just two invocations of
the same project with two different file contents). This is a **new** portability finding, not
called out in `idea.md`/`research_isolation_options.md`: the shared-project-name property that makes
the *current* design work also means **any future edit to `dev_db/docker-compose.yaml` is only safe
once every active worktree has rebased past it**, or the compose file needs to be excluded from
per-worktree drift some other way (e.g. documenting "run `git pull`/rebase onto the fix before your
next `docker compose up`" as part of the rollout, or pinning `container_name:`+`name:` doesn't help
here since the *content* hash, not the name, drives recreation).

---

## 5. Other "works anywhere" risks

- **Port 6543 conflicts.** The compose file publishes `6543:5432` unconditionally. Any other project,
  tool, or a leftover container on the same host that already binds host port 6543 will make
  `docker compose up` fail with an address-already-in-use error on **every** platform identically
  (this is host-network-stack behavior, not engine-specific) — not a cross-platform *divergence*, but
  a real "works on my machine, not this one" risk if a contributor already runs something else on
  6543. Not something the planned compose-level fixes (`restart`/`healthcheck`/`shm_size`/`mem_limit`)
  touch either way.
- **arm64 image availability.** The official `postgres` image (used here, `postgres:17`) is
  multi-arch and includes `linux/arm64/v8` — Apple Silicon Macs (native or under Docker
  Desktop/OrbStack/Colima) pull the correct arch automatically with no Rosetta/QEMU emulation needed;
  this is **not** a risk for this specific image. [Docker Hub — postgres official image](https://hub.docker.com/_/postgres)
- **Rootless Docker + `shm_size`.** Separate from Podman (which is rootless by default): rootless
  **Docker** (the `dockerd-rootless` mode, distinct from Docker Desktop) has its own history of
  cgroup-delegation quirks affecting memory/cgroup-backed limits similarly to rootless Podman; if any
  contributor runs rootless Docker Engine on Linux rather than the default rootful daemon, the same
  class of "limit silently not applied without proper cgroup v2 delegation" caveat found for rootless
  Podman in §1 plausibly applies. **unverified** in this pass — flag for a direct test if rootless
  Docker is a supported contributor path (not confirmed either way whether any contributor actually
  uses it).
- **Podman as a genuinely different engine, not just "Docker with a different CLI."** Several items
  above (`shm_size` ignored via docker-compose+Podman backend, `unless-stopped` skipped by
  `podman-restart.service`, `oom_score_adj` unconfirmed) stack up specifically for Podman. If Podman
  is a contributor path the team actually wants to support (CLAUDE.md and `dev_db/README.md` only say
  "Install Docker" / "Install Docker-compose," so Podman support isn't explicitly promised today),
  the fix should either explicitly document Podman as unsupported, or budget separate verification
  time for it — treating "docker compose" and "podman compose" as interchangeable based on this
  research is **not safe** for at least the restart-policy and shm_size knobs.
- **`docker-compose` (hyphenated, Python v1) vs `docker compose` (space, Go v2).** `dev_db/README.md`
  itself mixes both spellings ("`docker compose up`" and "`docker-compose up`" in the same file) —
  the legacy hyphenated `docker-compose` v1 binary is deprecated/unmaintained upstream and may not be
  installed at all on a fresh machine that only has the modern `docker compose` plugin; this is a
  documentation portability gap independent of the compose-file changes themselves, and is the direct
  root cause of the container-naming mismatch in §4 (`dev_db_dbs_1` is v1-style naming).

---

## Bottom line

Most of the planned knobs (`healthcheck` core fields, `shm_size`, `mem_limit`, `command: -c ...`,
`stop_grace_period`) are Compose Spec basics that behave the same everywhere and are safe to ship as
proposed. Three things need explicit handling, not just "it'll work everywhere":

1. **`restart: unless-stopped` does not mean the same thing on Podman as on Docker** —
   `podman-restart.service` skips it on boot. If Podman is a supported path, either document it as
   unsupported there or note contributors must use `restart: always` + accept it ignoring manual stops.
2. **VM memory ceilings vary by 4x across platforms** (Colima's 2 GiB default vs Docker Desktop's
   50%-of-host) — any `mem_limit`/`shm_size` numbers chosen need a stated minimum VM memory
   requirement, and the fix's docs should tell a contributor how to check it (`docker info`'s
   `MemTotal`, `.wslconfig`, `colima start --memory`).
3. **The shared project-name property that makes "every worktree reaches the same container" work
   today also means an in-flight, not-yet-merged edit to `dev_db/docker-compose.yaml` can be silently
   reverted by any sibling worktree that still has the old file and happens to run `docker compose up`
   after this one does** — this needs a rollout note (rebase before next `up`), not a compose-file
   knob.

status: ok
