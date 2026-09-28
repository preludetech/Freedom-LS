# Research: why Docker Desktop stops, and whether to use Docker Engine

Scope: the user's new fact is that on their machine "the database goes down" really means **the
entire Docker Desktop service stops** — every container, not just `postgres:17`, and they must
restart Docker Desktop itself and then bring containers back up by hand. They run **Docker Desktop
on Linux** (not Docker Engine directly) and are willing to switch to plain Docker Engine if that is
the better call. This unit covers Docker Desktop's own architecture and failure modes on Linux, and
compares it to Docker Engine. Postgres-internal tuning and cross-platform Compose portability are
other research units' turf; this file only touches them where the Desktop-vs-Engine choice changes
the picture (fsync path, bind-mount UID handling, OOM victim).

## 0. This changes a framing in the existing research files

`research_postgres_failure_modes.md` (§3, OOM) and `research_failure_evidence.md` (§1) both frame
"Docker Desktop" as a **macOS/Windows-only** concept whose hidden VM the host's own `dmesg`/
`journalctl` can't see, contrasted with "a native Linux Docker host" where the kernel doing the
OOM-killing is the one you can inspect directly. That framing is **wrong for this user**: Docker
Desktop for Linux *also* runs everything inside a QEMU/KVM virtual machine
([docs.docker.com — Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/)),
so the same caveat applies to them — the kernel that OOM-kills something inside the containers is
the **VM's** guest kernel, not the host's, and the host's own `dmesg`/`journalctl -k` will not show
a guest-side OOM kill. `docker inspect`'s `State.OOMKilled` flag (already the correct fallback per
`research_failure_evidence.md` §1) still works identically, because it comes from the Docker API,
not the host kernel — that part of the existing research holds up regardless of platform.

What the existing files don't cover at all is the failure this user actually described: **the VM
itself, or the Desktop backend process managing it, stopping** — which is not one of the six
Postgres-level failure modes catalogued in `research_postgres_failure_modes.md`. It is a layer
below Postgres: when it happens, Postgres, mailpit, and anything else running dies together,
indiscriminately, and nothing comes back until a human restarts Docker Desktop. See §2/§3.

`research_isolation_options.md` recommends adding `restart: unless-stopped` as part of "keep the
one shared server" (line 17). That is necessary but **not sufficient** on Docker Desktop: a
container restart policy is enforced by the `dockerd` running *inside* the Desktop VM. If the VM/
backend itself stops, there is no `dockerd` alive to apply any restart policy — see §3.

## 1. Architecture

Docker Desktop for Linux runs a QEMU/KVM virtual machine on the host and puts the real Docker
daemon inside it; the CLI on the host talks to that daemon over a socket. Docker's own stated
reasons: consistent behaviour across macOS/Windows/Linux, letting Docker ship newer kernel features
to all users regardless of host kernel, and an extra security boundary between containers and the
host — plus an isolated on-disk storage area "to prevent it from interfering with a Docker Engine
installation on the same machine" if one is also present.
([docs.docker.com — Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/),
[Docker blog — The magic behind the scenes of Docker Desktop](https://www.docker.com/blog/the-magic-behind-the-scenes-of-docker-desktop/))
System requirements confirm the mechanism explicitly: a 64-bit kernel with **KVM** virtualization
enabled and **QEMU ≥ 5.2**, `systemd`, and a supported desktop environment (GNOME/KDE/MATE) —
i.e. Desktop on Linux targets a GUI workstation session, not a headless box.
([docs.docker.com — Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/))

**Default VM resource ceilings** (Settings → Resources), per the official settings reference, apply
identically to Mac, Linux and Windows-Hyper-V backends:
- Memory: **defaults to 50% of the host's memory**.
- Swap: **1 GB default**.
- CPU: the docs confirm a CPU limit exists and is configurable but do not state the numeric
  default in the page fetched this session; third-party guides (not primary docs) commonly say
  "half of the host's CPUs" — **treat as unverified** against the primary source and check
  Settings → Resources → Advanced on the actual host instead of trusting a hardcoded number.
- Disk image size: the settings docs confirm you can cap "the maximum amount of disk space the
  engine can use" but no default figure was found in the pages fetched this session —
  **unverified**, check Settings → Resources → Advanced directly.
([docs.docker.com — Settings and maintenance / Settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/))
One third-party search result claimed a 25%-of-host-memory default rather than 50% — that
contradicts the primary docs page above; the 50% figure from docs.docker.com is the one to trust,
but given the discrepancy across sources/versions, the actual number should be read off
Settings → Resources on the machine in question, not assumed from any doc.

**virtiofs** is "the default (and currently only) mechanism to enable file sharing between the
host and Docker Desktop VM" on Linux.
([docs.docker.com — FAQs for Docker Desktop for Linux](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/linuxfaqs/))
A bind mount therefore crosses two boundaries, not one: host directory → VM filesystem (via
virtiofs) → container filesystem — "Docker Desktop will mount some of your folders into the
virtual machine and containers will actually mount the folders from inside the virtual machine"
([Docker Community Forums — Seeking clarity on Docker Desktop for Linux and its virtual machine(s)](https://forums.docker.com/t/seeking-clarity-on-docker-desktop-for-linux-and-its-virtual-machine-s/141570)).
For this repo's `dev_db/docker-compose.yaml`, which bind-mounts `PGDATA` straight to a host path
(`${DB_DATA_PATH:-~/.lms_postges_dev_data}:/var/lib/postgresql/data`), every Postgres `fsync` on
Docker Desktop for Linux therefore makes an extra hop through virtiofs that a native Docker Engine
bind mount (plain host filesystem, no VM) does not make. I did not find a Docker-published
benchmark quantifying virtiofs fsync latency specifically for Postgres workloads this session —
flagging the *existence* of the extra hop as verified, its magnitude as **unverified**, and leaving
quantification to the Postgres-tuning research unit.

## 2. Failure modes where the whole Desktop backend/VM stops

**Guest OOM inside the VM vs. the VM/host dying.** The VM has its own Linux kernel and its own
memory ceiling (§1). When something inside a *container* exceeds its own cgroup limit, the
container's cgroup OOM-kills that one process and (with a restart policy) Docker restarts just that
container — this is the same mechanism `research_postgres_failure_modes.md` §3 already describes,
just happening inside the VM's kernel instead of the host's. That is a **contained** failure. The
failure the user is describing is different in kind: the **VM process itself** (or the Desktop
backend managing it) stops running, taking every container down with it regardless of any
per-container cgroup limit.

**Host OOM killer killing the VM's own process.** The VM is, from the host's point of view, one
large process (traditionally `qemu-system-*`, managed by Docker's backend). On this user's
machine the host is simultaneously running several worktrees' Django dev servers, several
xdist-worker Python processes per worktree, Playwright's bundled Chromium instances, IDEs, and AI
coding agents — a large single-process VM allocated to hold, by default, half the host's memory
(§1) is a natural, large-resident-set target for the **host's** OOM killer when real host memory
runs low, independent of anything happening to Postgres inside the VM. I could not find a
Docker-published account of the host OOM killer specifically picking the Desktop VM process on
Linux this session; the mechanism is inferred from documented Desktop architecture (§1) plus the
general, well-documented behaviour of Linux's OOM killer favouring large resident-set processes —
**mark this specific causal chain as a plausible, undocumented-by-Docker hypothesis**, consistent
with (not proven by) the crash reports below, which show whole-VM failures without the reporters
being able to pin down a cause.

**Known Docker Desktop for Linux crash/hang reports (docker/desktop-linux issues):**
- **#282 — "Ubuntu - Docker Desktop Random Crashes"**: Docker Desktop 4.39.0 on Ubuntu 24.04.2,
  all running containers stop simultaneously and the whole app becomes unresponsive; requires a
  manual restart from the menu. Docker's own `com.docker.diagnose gather` tool reported no
  problems — i.e. the built-in diagnostics did not surface a root cause. No fix or workaround is
  recorded in the issue.
  ([docker/desktop-linux#282](https://github.com/docker/desktop-linux/issues/282))
- **#286 — "Docker Engine Crashing"**: Docker Desktop 4.40.0 (build 187762), Docker Engine
  28.0.4/28.1.1, Kubuntu, kernel `6.10.14-linuxkit` (the VM's own kernel, note the `-linuxkit`
  suffix confirming it's the guest kernel, not the host's). Error text:
  `running engine: engine linux/qemu failed to run: running virtiofsd for /home: signal: bad
  system call (core dumped)`. Reported after an overnight idle period with 10 containers running;
  the whole engine/VM fails, not one container. No root cause identified; issue marked
  needs-triage. This is a **virtiofsd crash under file-sharing load** taking the whole backend
  down — directly relevant given this repo's bind-mounted `PGDATA` and heavy Playwright/pytest I/O.
  ([docker/desktop-linux#286](https://github.com/docker/desktop-linux/issues/286))
- **moby/moby#40298 — "dockerd crash because of OOM kill"**: general evidence that `dockerd`
  itself is a documented OOM-kill victim, not just the workloads it runs; filed against `moby`
  (the daemon underlying both Engine and the daemon inside Desktop's VM), so the mechanism applies
  to both, though the memory ceiling that has to be exceeded differs (host RAM for Engine, the
  VM's allocated slice for Desktop).
  ([moby/moby#40298](https://github.com/moby/moby/issues/40298))
- **docker/for-linux#1001 — "Hitting Container Kernel Memory Limit causes OOM on Docker Host"**:
  this is about the deprecated per-container `--kernel-memory` flag specifically causing a
  **host-wide** OOM even with ample free host RAM, reproduced across Ubuntu 16.04–20.04, Debian,
  CentOS 8.1 on plain Docker Engine (not Desktop). It does **not** apply to ordinary
  `mem_limit`/`deploy.resources.limits.memory` (plain cgroup memory limits, which this project
  would use) — flagging it only as a reminder not to reach for `--kernel-memory` on either Engine
  or inside a Desktop VM's containers.
  ([docker/for-linux#1001](https://github.com/docker/for-linux/issues/1001))
- Component crash pattern, cross-platform: `com.docker.backend` (the Desktop backend process
  managing the VM/daemon connection) has multiple documented high-memory/high-CPU/crash reports on
  Windows and Mac (`docker/for-win#14367`, `#13589`, `docker/for-mac#6852`, `#7605`, `#7646`,
  `docker/desktop-feedback#152`/`#15036`). I found comparatively fewer indexed Linux-specific
  reports naming `com.docker.backend` directly this session, but the same backend architecture
  underlies all three platforms — **treat the Linux evidence as thinner but not absent**, and
  check the current `docker/desktop-linux` issue tracker for the installed version before ruling
  it out.
  ([docker/for-win#14367](https://github.com/docker/for-win/issues/14367), [docker/for-mac#6852](https://github.com/docker/for-mac/issues/6852))

**VM disk image full.** Separate from this repo's bind-mounted `PGDATA` (which lives on the real
host filesystem): Desktop's own VM stores its image/layer cache and any non-bind-mounted volumes in
a single growable disk image file, capped by the Settings → Resources disk-image-size setting
(§1). If that fills, Desktop can become unresponsive independent of anything Postgres is doing.
This repo's compose file bind-mounts `PGDATA` directly, so Postgres's own data growth does not
count against this cap — but Docker's own image cache (`postgres:17`, `mailpit`, plus whatever
else the worktrees' agents `docker pull`/`docker build`) does. I did not find a documented default
size this session (§1) — unverified, check the setting directly.

**Resource Saver mode.** "Significantly reduces CPU and memory utilization on the host by
automatically turning off the Linux VM when Docker Desktop is idle," restarting automatically
within "3–10 seconds" once a container needs to run; available on Mac, Linux and Windows-Hyper-V.
([docs.docker.com — Settings and maintenance / Settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/))
This is a documented, intentional VM shutdown, not a crash — but on a box running healthchecks and
several worktrees' dev servers expecting an always-available Postgres on port 6543, a 3–10 second
VM cold-start could plausibly look like a transient outage or trip a healthcheck timeout. I did not
find evidence either way of Resource Saver specifically causing the crash-like symptoms this user
described — **flag as worth disabling on this host as a precaution, not as a confirmed cause**.

**Where the logs are.** The officially documented, version-proof way to gather Desktop's own logs
is `docker desktop diagnose` (CLI) or Troubleshoot → "Get support" in the Dashboard, which bundles
logs and issues a Diagnostic ID.
([docs.docker.com — Troubleshoot Docker Desktop](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/))
Docker documents per-platform host-side log directories for macOS
(`~/Library/Containers/com.docker.docker/Data/log/host`) and Windows
(`%LOCALAPPDATA%/Docker/log/host/`) in its logging blog post, by direct analogy the Linux
equivalent is commonly assumed to be `~/.docker/desktop/log/host/` (and a `vm/` subdirectory for
VM-side logs) — **I could not find an official doc or forum post in this session that states that
literal Linux path**, so treat it as unverified and either confirm with `ls ~/.docker/desktop/log/`
on the actual machine, or just use `docker desktop diagnose`, which is documented and doesn't
depend on guessing a path.
([Docker blog — Capturing logs in Docker Desktop](https://www.docker.com/blog/capturing-logs-in-docker-desktop/),
[Docker Community Forums — Where are the log files located?](https://forums.docker.com/t/where-are-the-log-files-located/80400))
Inside the VM itself, on-boot action output goes to `/var/log/onboot/*` and service output to
`/var/log/*`, reachable via the diagnose bundle or a privileged `nsenter` container against the
VM's log socket (`/run/guest-services/memlogdq.sock`) — not something a developer would reach for
mid-incident.
([Docker blog — Capturing logs in Docker Desktop](https://www.docker.com/blog/capturing-logs-in-docker-desktop/))
The host's own `journalctl -k`/`dmesg` is still useful on Docker Desktop for Linux, but only for
catching the **host** OOM killer picking off the VM's own process (§0) — it will show nothing about
an OOM kill that happened to a process *inside* the VM's guest kernel.

## 3. What `restart:` policies do, and don't do, when the whole backend/VM stops

`restart: unless-stopped`/`always` is enforced by the `dockerd` that the policy's container is
registered with. On Docker Desktop, that `dockerd` runs **inside the VM**. So:
- While the VM/backend is up, restart policies work exactly as documented — a container that
  exits unexpectedly (including a cgroup OOM kill scoped to that one container, §2) comes back
  without anyone touching Desktop.
- If the **VM/backend itself** stops (crash, forced quit, host reboot), there is no `dockerd`
  alive to evaluate any restart policy for any container. Nothing comes back until Desktop (and
  its VM) is running again — which matches this user's own description exactly ("restart Docker
  Desktop and then bring the containers back up").
- **General → "Start Docker Desktop when you sign in"** is the setting that would make Desktop
  (and therefore its VM and `dockerd`, and therefore anything with `restart: unless-stopped`) come
  back automatically after a host reboot. On Linux specifically, this exact toggle has several
  open, unresolved reliability reports: not honoured when unchecked
  ([docker/desktop-linux#214](https://github.com/docker/desktop-linux/issues/214),
  [#215](https://github.com/docker/desktop-linux/issues/215)), autostart not disable-able on
  Ubuntu ([#182](https://github.com/docker/desktop-linux/issues/182)), and Desktop failing to
  start on login on Linux Mint ([#136](https://github.com/docker/desktop-linux/issues/136)). Treat
  this setting as unreliable on Linux until verified on the actual distro/version in use, not as a
  guaranteed unattended-recovery mechanism.
- **Whether Desktop auto-restarts its VM after a mid-session crash** (as opposed to after a full
  reboot/re-login): not documented, and the crash reports in §2 show the opposite in practice —
  `#282` explicitly required "a manual restart from the menu," and `#286` reports the system
  "becomes unusable until manual restart." No evidence of automatic mid-session recovery was found.
  This directly matches the user's own report and is the strongest evidence available that Desktop
  does **not** self-heal from a backend/VM crash today.
- Even once Desktop *is* manually restarted, whether previously-running containers with
  `restart: unless-stopped` actually come back is version-dependent: a cross-platform regression
  (`docker/desktop-feedback#516`, macOS 4.81.0) reports exactly this policy failing to restart
  containers after a Desktop restart/host reboot, working again once rolled back to 4.80.0 — i.e.
  this specific mechanism has shipped broken before. `restart: unless-stopped` is necessary; do
  not treat it as a guaranteed fix without checking behaviour on the installed version.
  ([docker/desktop-feedback#516](https://github.com/docker/desktop-feedback/issues/516))

## 4. Docker Engine (docker-ce) as the alternative

**No VM.** `dockerd` runs directly on the host, containers share the host kernel. There is no
separate VM memory ceiling to run out of — memory pressure is host memory pressure, directly and
visibly (`free`, `docker stats`, host cgroup accounting), with no extra "VM might also be starving"
variable. The host OOM killer can, however, still pick `postgres` itself if its container has no
explicit memory limit — this is the same mechanism already covered in
`research_postgres_failure_modes.md` §3 (Crunchy Data — "the Linux Assassin"), and is unchanged by
which Docker distribution is running; Engine removes the VM-wide single point of failure, it does
not remove Postgres's exposure to the host OOM killer on an unconstrained container.

**systemd lifecycle.** `sudo systemctl enable docker containerd` starts the daemon on boot; systemd
manages restarts of the daemon itself per its unit file. This is the standard, most-documented path
for unattended Linux dev/CI boxes.
([docs.docker.com — Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[docs.docker.com — Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/))
`restart: unless-stopped` on the `postgres` service then works across reboots as long as
`docker.service` is enabled — no GUI, no "start on sign-in" toggle, no login session required at
all, which sidesteps the exact reliability bugs found in §3 for Desktop's login-triggered autostart.

**Native bind mounts, no virtiofs hop.** The bind-mounted `PGDATA` directory is ordinary host
filesystem I/O with no VM/virtiofs boundary in the path (§1) — every `fsync` Postgres issues is a
direct host filesystem call.

**cgroup v2 limits.** `mem_limit`/`deploy.resources.limits.memory` on the `postgres` service apply
against the host's real cgroup v2 hierarchy directly — sizing this deliberately (idea.md's own
direction #2) lets the *container's own cgroup* OOM-kill Postgres and (with a restart policy)
recover it, rather than leaving Postgres exposed to the host-wide OOM killer's victim-selection
alongside Chromium/Python/agents.

**Downsides:**
- No Desktop GUI/Dashboard/Extensions/Resource Saver — pure CLI/Compose workflow.
- **Root-owned bind-mount files.** The official `postgres` image runs as uid `999` inside the
  container. On plain Engine, a bind mount is a literal host path with no UID remapping by
  default, so files Postgres writes land on the host filesystem owned by uid `999` as-is, which can
  make `~/.lms_postges_dev_data` unreadable/unwritable to the logged-in host user without
  `sudo`/`chown` (unless `userns-remap` or rootless mode is configured).
  ([Dash0 — How to Manage Permissions for Docker Shared Volumes](https://www.dash0.com/faq/how-to-manage-permissions-for-docker-shared-volumes))
  Whether Docker Desktop's VM-mediated bind mount actually presents files under the logged-in
  host user instead of the raw container uid is **not guaranteed either** — Desktop's own Linux
  FAQ requires `/etc/subuid`/`/etc/subgid` for user-namespace support and separately documents a
  known limitation that "files modified in a container and chowned to specific UIDs can become
  difficult to access on the host, requiring group creation or recursive ACL configuration."
  ([docs.docker.com — FAQs for Docker Desktop for Linux](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/linuxfaqs/))
  So this is a real caveat on **both** sides, not a Desktop-only advantage — verify the actual
  ownership on this host's existing `~/.lms_postges_dev_data` directory before assuming either way.
- **`docker` group is root-equivalent.** Membership grants effective root on the host via the
  daemon socket — a documented, well-known caveat, independent of this project.
  ([Ken Muse — Rootless Docker and Its Hidden Security Trade-Offs](https://www.kenmuse.com/blog/rootless-docker-and-its-hidden-security-trade-offs/),
  [mvysny — The docker group is root](https://mvysny.github.io/docker-rootless/))
- **Rootless mode** mitigates that (daemon and containers run as an unprivileged user, root inside
  a container maps to your own uid, not real root), at the cost of no privileged-port binding below
  1024 without extra setup, some storage-driver/network-mode restrictions, and slightly more
  overhead.
  ([docs.docker.com — Rootless mode](https://docs.docker.com/engine/security/rootless/))

**Desktop and Engine can coexist.** Desktop for Linux creates and uses its own Docker context,
`desktop-linux`, and stores its images/containers "in an isolated storage location within a VM"
specifically "to prevent it from interfering with a Docker Engine installation on the same
machine" — i.e. Docker's own docs assume both may be installed side by side, switchable via
`docker context use default` / `docker context use desktop-linux`.
([docs.docker.com — Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/))
They are two separate daemons with separate storage: a container/volume/image that exists under one
context does not exist under the other.

**Migration, high level, for this repo's setup specifically:**
1. `docker compose down` (no `-v`) under Desktop's `desktop-linux` context to stop the current
   `postgres`/`mailpit` containers.
2. The bind-mounted data directory (`${DB_DATA_PATH:-~/.lms_postges_dev_data}`) is an ordinary host
   path, not something living inside Desktop's VM disk image — it is untouched by switching
   daemons. `mailpit` in this compose file has no persistent volume, so there is nothing to
   migrate for it.
3. Install `docker-ce`/`docker-ce-cli`/`containerd.io` via Docker's apt repo, removing conflicting
   distro packages first.
   ([docs.docker.com — Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/))
4. `sudo systemctl enable --now docker`.
5. Add the user to the `docker` group (or configure rootless mode) and re-login.
   ([docs.docker.com — Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/),
   [docs.docker.com — Rootless mode](https://docs.docker.com/engine/security/rootless/))
6. Confirm the CLI is talking to `default` (Engine), not `desktop-linux`.
7. `cd dev_db && docker compose up -d` — this recreates the `postgres` container fresh against the
   **same** bind-mounted host directory; Postgres just sees its existing `PGDATA` on next start, so
   existing databases are picked up unchanged, modulo ownership (below). Image layers are re-pulled
   since Engine's image cache is separate from Desktop's VM-internal one.
8. **Expect a permissions step.** If the existing data directory's ownership doesn't match what
   Engine's uid-999 bind mount expects, the first symptom is a permission-denied error on startup;
   fix with a one-time `chown -R 999:999 <data dir>` (or matching subuid range for rootless), or —
   since this project's dev/test data is explicitly rebuildable from migrations per idea.md —
   simply point `DB_DATA_PATH` at a fresh directory and let the app rebuild.
9. Only uninstall Desktop after Engine is confirmed working; Desktop's own VM disk image and any
   images/volumes that were never bind-mounted are separate storage and are lost on uninstall if
   not otherwise needed.

## 5. What Docker's own docs recommend for Linux developers

No page fetched this session states a blanket "on Linux, prefer Engine" or "prefer Desktop"
recommendation. The framing throughout the install/Linux and Linux-FAQ pages is that Desktop exists
to give Linux users the **same GUI/Dashboard/Extensions/Resource-Saver experience** Mac and Windows
users get, deliberately isolated from any existing Engine install "on the same machine" — which
reads as Docker expecting Engine to be the baseline on Linux and Desktop to be an optional layer on
top for people who want the GUI, not as Docker steering people away from Engine.
([docs.docker.com — Install Docker Desktop on Linux](https://docs.docker.com/desktop/setup/install/linux/),
[docs.docker.com — FAQs for Docker Desktop for Linux](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/linuxfaqs/))
Desktop's own Linux system requirements (KVM, QEMU, a GUI desktop environment) implicitly rule it
out for headless dev/CI boxes — that's an inference from the requirements list, not a quoted
recommendation, but a reasonable one, since Docker does not offer a headless Desktop-for-Linux mode
at all. **Net: this project's recommendation below is derived from the architecture facts above,
not lifted from an explicit Docker recommendation** — Docker's docs leave the choice to the user.

## 6. What this project should recommend

**On Linux: prefer Docker Engine over Docker Desktop for this repo's dev-db workload.** Reasoning,
directly tied to the failure the user described:
- No VM means no VM-wide single point of failure that takes Postgres, mailpit, and every worktree
  down together — the exact symptom reported ("the entire Docker Desktop service stops").
- `systemctl enable docker` gives boot-time recovery with no dependency on a GUI login session or
  the Linux-specific "start on sign-in" toggle, which has multiple open reliability bugs today
  (§3).
- Real cgroup v2 limits let a deliberately-sized `mem_limit` on the `postgres` service (idea.md's
  own direction #2) make memory exhaustion a **contained, self-healing, diagnosable** container
  restart (already covered by `research_failure_evidence.md`'s `docker inspect --format
  '{{.State.OOMKilled}}'` check) instead of an opaque whole-VM stop.
- The one migration caveat to call out explicitly: sort out bind-mount ownership on the existing
  `~/.lms_postges_dev_data` (or `DB_DATA_PATH`) directory once during the switch (§4 step 8) — or
  just accept a rebuild, since this project's dev data is disposable by design.

**On macOS/Windows: Desktop's VM is not optional there**, so give concrete sizing guidance instead
of a platform switch:
- Check the actual current Memory/CPU/Swap/Disk allocation under Settings → Resources → Advanced
  on the machine in question rather than trusting any hardcoded default figure — §1 shows even the
  primary docs and secondary sources disagree on some of these numbers, and they are also
  version-dependent.
- Size the VM's memory comfortably above the sum of: this repo's own `postgres` `mem_limit` (once
  set, per below) + each active worktree's Django dev server + each worktree's xdist workers'
  Python processes + Playwright's Chromium instances + normal OS/IDE/AI-agent overhead. With 4–6
  worktrees each potentially running several xdist workers and a Chromium instance concurrently,
  that total can exceed a default 50%-of-host allocation on a modest laptop; there is no shortcut
  around measuring this on the actual hardware in use.
- Consider disabling Resource Saver mode on this specific setup, since a VM that turns itself off
  when Desktop is "idle" and takes 3–10 seconds to wake could interact awkwardly with healthchecks
  or a `restart:` policy's own retry timing — flagged as a precaution in §2, not a confirmed fix
  for anything already observed.

**Repo-level change that helps every platform, VM-based or not:** set an explicit `mem_limit` (or
`deploy.resources.limits.memory`) on the `postgres` service in `dev_db/docker-compose.yaml`, sized
well below whatever the VM/host actually provides. This makes the **known, diagnosable** path fire
first — Postgres's own container gets OOM-killed by its own cgroup and (with a restart policy)
comes back — instead of the VM's or host's overall memory running out first, which is what actually
stops the whole Desktop backend and everything in it. This is the direct link between "why Docker
Desktop stops entirely" (this file) and idea.md's existing direction #2 ("the server has headroom
sized for several worktrees") — on a VM-based host (Mac/Windows/Desktop-on-Linux) the sizing has to
happen at *two* layers that this repo doesn't fully control together: the container's own
`mem_limit`, and the VM's overall ceiling, which is a per-developer Desktop setting outside the
repo.

**Directly answering the user's closing question** — "If Docker Desktop is not the right choice,
then I can uninstall it and install just regular Docker" — yes: on Linux, Engine is the more
failure-resistant choice for this exact workload (no VM-wide single point of failure, real systemd
lifecycle, real cgroup limits, no reliance on a login-session-triggered autostart that is
unreliable on Linux today), Docker's own docs support Desktop and Engine coexisting via separate
contexts so the switch is low-risk and reversible, and the one thing worth doing carefully during
the migration is checking bind-mount file ownership on the existing Postgres data directory.

status: ok
