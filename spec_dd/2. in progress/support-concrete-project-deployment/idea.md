# FLS support for concrete-project production deployment

> **Audience: the FLS (Freedom Learning System) team.** This is a handoff idea raised
> by a concrete downstream project. The deployment spec/idea for that downstream project can be seen in `concrete_project_idea.md` in this directory

## Problem

> **Terminology.** `ConcreteFlsImplementation` is the placeholder used throughout this idea
> for the specific concrete production implementation of FLS that raised this handoff — a
> separate downstream repo that installs `freedom_ls` as a submodule. It is deliberately *not*
> named after any theme; earlier prototyping in this repo produced a similarly-named theme, and
> the placeholder keeps the two from being confused. Wherever `ConcreteFlsImplementation`
> appears it always means that downstream implementation project, never a theme. (Generic
> phrases like "every concrete project" still refer to concrete FLS projects *in general*.)

A concrete FLS project (`ConcreteFlsImplementation`) installs `freedom_ls` as a **read-only git
submodule** (`submodules/Freedom-LS`, sourced via `[tool.uv.sources]`) and owns its own
`config/`, apps, and `tailwind.input.css`. It is authoring its own production deployment
— single Vultr JNB VPS, Docker Compose, Caddy + Gunicorn + PostgreSQL (see the downstream
`spec_dd/next/deployment/idea.md`). While scoping that work we found that most of the
friction is **not `ConcreteFlsImplementation`-specific**: it lives in FLS's reference config, in the
shared **concrete-project template repo**, in FLS's shipped deployment artifacts, and in
FLS's deployment docs. Every FLS-based concrete project inherits these gaps, more such
projects are planned, so fixing them **once upstream** is far cheaper than each project
working around them **N times**. Several are **silent production-breakers**, not cosmetic.

**Framing premise: FLS is never deployed standalone — only concretely, as a submodule of a
downstream project.** The standalone repo exists to be *consumed*, not *deployed*. Every
deployment artifact and doc that targets a standalone FLS deploy therefore describes a mode
no one runs; the concrete (submodule) path is the *only* real deployment target. This premise
drives items 7 and 8: standalone deployment artifacts and docs are **legacy to remove**, not a
parallel path to maintain alongside the concrete one.

### Propagation surfaces (same maintainers)

FLS has **no importable base-settings module**: each concrete project owns a full copy of
`config/settings_base.py` + `settings_prod.py`, so a fix in one project does not
propagate. There is **no automated sync** — every propagation is a human/agent running an
`/fls:sdd:*` command. Most settings-level fixes below must therefore land in **all three**
surfaces below, or they drift:

1. **The concrete-project template repo** (`freedom-ls-concrete-template`) — the scaffold
   new projects are generated from
   (`fls-claude-plugin/resources/template_repo_manifest.md`, synced via
   `/fls:sdd:update_template_repo`). This is the *source* of the prod-settings defaults for
   **future** projects.
2. **FLS's own reference `config/`** (`submodules/Freedom-LS/config/settings_*.py`) — a
   near-verbatim twin and the documented *authority*, so the same bug exists in both.
3. **Existing downstream projects, via `/fls:sdd:update_fls`.** `ConcreteFlsImplementation` **already exists**,
   generated from an older template — so a fix landed only in (1) reaches *new* projects and
   **silently misses `ConcreteFlsImplementation` itself**. The P0 settings fixes only reach the flagship consumer
   that motivated this idea when `/update_fls` is run against it. Any triage that stops at (1)+(2)
   leaves the project that raised the idea unpatched.

The core ask of this idea is to deliver reusable deployment scaffolding **shaped for the
submodule consumer** — a concrete project with its own apps that installs `freedom_ls`
from a read-only submodule — delivered through the concrete template repo, with the
code-level primitives made importable from `freedom_ls` rather than copy-pasted per
project.

## Proposed changes (prioritised)

### P0 — production settings defaults that bite every project

Small template + reference `config/` edits; each removes a silent production failure that
every concrete project inherits unchanged.

1. **Redirect-loop landmine: `SECURE_PROXY_SSL_HEADER` is never set while
   `SECURE_SSL_REDIRECT = True`.**
   - `config/settings_prod.py:16` (FLS) / `:15` (concrete twin) sets `SECURE_SSL_REDIRECT
     = True`, but `SECURE_PROXY_SSL_HEADER` is absent from all four settings files. Behind
     any TLS-terminating proxy (Caddy, Cloudflare, ALB) the app never sees `https`, so it
     redirects forever. Today this exists only as checklist prose
     (`docs/deployment-security-checklist.md:33`), not code.
   - **Fix:** set `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` in the
     template's `settings_prod.py` (env-guardable if FLS wants it optional) and add it to
     the manifest contract. Any FLS-recommended reverse proxy terminates TLS, so this is a
     default, not a footnote.
   - **Trust caveat:** this header is only safe if the **trusted proxy overwrites**
     `X-Forwarded-Proto` on every request (Caddy does). If a client can reach the origin
     directly and set the header itself, the app can be tricked into treating plain HTTP as
     secure. This pairs with the downstream Cloudflare setup (`spec_dd/next/deployment/cloudflare-front-research.md`):
     SSL mode **Full (strict)** (never Flexible — Flexible + `SECURE_SSL_REDIRECT` is itself a
     redirect loop), origin firewalled to Cloudflare ranges, and Caddy `trusted_proxies` restoring
     the real client IP from `CF-Connecting-IP`.

2. **Container-hostile logging: prod logs to `RotatingFileHandler` on local disk.**
   - `config/settings_prod.py:65-146` fans `django`, `django.request`, `django.security`,
     `freedom_ls`, and `root` out to `RotatingFileHandler`s under `BASE_DIR/logs/`
     (`:91,:99,:107`); the shipped compose even bind-mounts `./logs:/app/logs`
     (`docker-compose.yml:26`). In a container these files are ephemeral and invisible to
     `docker logs` / the platform log driver. (A `console` `StreamHandler` is attached at
     `:86`, so stdout isn't empty — but the file handlers are the documented default and
     the manifest bakes them in.)
   - **Fix:** default prod logging to **stdout/stderr only**; drop the file handlers (or
     make them opt-in via an env flag) and stop bind-mounting `logs/`.
   - **Ship it with the log cap — not alone.** Moving to stdout only relocates the disk-fill
     risk: un-capped Docker `json-file` logs then grow unbounded under `/var/lib/docker` and
     fill the host disk on a single small VPS. This settings change is therefore only safe when
     shipped **alongside** the P3 compose `json-file` `max-size`/`max-file` caps per service. The
     downstream idea treats that cap as **required**, not optional (`spec_dd/next/deployment/idea.md`,
     observability/Sentry section) — so P0(2) and the P3 caps land together.

3. **Tasks backend: `ImmediateBackend` in production + a `db_worker` that doesn't exist.**
   - Django 6 ships the Tasks framework **built in** (`django.tasks`, already in
     `INSTALLED_APPS`) — no external dependency is needed for the framework itself. But the
     builtin ships only `ImmediateBackend`: prod re-declares `TASKS = {"default":
     {"BACKEND": "...immediate.ImmediateBackend"}}` with a live `# TODO @claude`
     (`config/settings_prod.py:208-215` FLS / `:191-197` concrete), so background work runs
     **synchronously in the request/worker process** in production. Meanwhile
     `docs/product/deployment.md:52` tells operators to run a separate `python manage.py
     db_worker` container against a `DatabaseBackend` — but the builtin framework provides
     **no durable database-backed backend and no `db_worker` command**, and FLS adds none.
     So the documented deferred/out-of-process path does not exist; the one real consumer
     today, webhook dispatch (`freedom_ls/webhooks/events.py`), ships as a synchronous
     in-request side effect in prod.
   - **Fix (opt-in upgrade, not a forced default).** The downstream `ConcreteFlsImplementation` idea has
     **explicitly decided** that V1 keeps `ImmediateBackend`, runs **no worker container**, and
     defers async "until a feature needs it" — treating this as the *resolution* of the
     `# TODO @claude`, not an outstanding gap (`spec_dd/next/deployment/idea.md`,
     background-tasks section). So FLS must **not** make `DatabaseBackend` + a worker the shipped
     production default; that would force a worker onto the one consumer that decided against it.
     Instead, FLS owns the **primitive** and the **upgrade path**, and leaves the default alone:
     - **Keep `ImmediateBackend` as the shipped settings default.** Delete the misleading
       re-declaration + `# TODO @claude` (prod already inherits base's `ImmediateBackend`); make
       the default a *deliberate* choice, not a stray TODO.
     - **Ship the durable backend as an importable, opt-in primitive** — Postgres as broker,
       **no Redis/Celery** (per [this Django-6 production write-up](https://www.better-simple.com/django/2026/05/06/using-django-tasks-in-production/)):
       the small **`django-tasks-db`** package + `django_tasks_db` in `INSTALLED_APPS` +
       `TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}`. A project turns
       this on with a settings flip, not a code port against the read-only submodule. Bonus for a
       single small VPS: tasks are visible in the **Django admin** (scheduled / completed / errored),
       so no separate queue dashboard.
     - **Ship the `worker` container in the P3 template present-but-disabled** (commented, or
       gated behind an env flag that defaults OFF), so enabling out-of-process work is one edit,
       not a from-scratch build.
     - **Fix the docs** (`deployment.md` / `deployment-playbook.md`) to describe this **upgrade**
       ("install `django-tasks-db`, flip `TASKS`, enable the worker service") instead of promising a
       `db_worker` that the shipped stack does not run. Killing that doc-vs-reality lie is the real
       ask here — not changing anyone's default. See P1(6).

4. **DB connections are not SSL-enforced despite the security checklist requiring it.**
   - `docs/deployment-security-checklist.md:22` requires encrypted DB connections, but the
     prod `DATABASES` block has **no `OPTIONS`** at all (`config/settings_prod.py:48-57`
     FLS / `:47-56` concrete) — no `sslmode`.
   - **Fix:** support a `DB_SSLMODE` env var → `OPTIONS = {"sslmode": ...}`. **Default to
     `prefer`, not `require`** — and ship `DB_SSLMODE=disable` in the template `.env.example`.
     The topology FLS actually ships and the downstream idea plans is **same-host containerised
     Postgres** (`postgres:17`), which does **not** enable TLS by default; a `require` default
     makes the client demand TLS the server can't offer and the app **fails to connect on first
     boot** — a silent breaker, ironic for the item about safe defaults. Reserve `require` /
     `verify-full` for an **external or managed** DB, and say so in `.env.example`.

   **Two more P0-class settings landmines to fix in the same pass (same twins):**

   - **Empty `SECRET_KEY` default.** FLS reference uses `os.getenv("SECRET_KEY", "")` — an empty
     key silently boots a misconfigured prod instead of failing loudly (downstream already
     hardened this to `os.environ["SECRET_KEY"]`). **Fix:** hard-fail on a missing/empty
     `SECRET_KEY` in prod. Exactly the "silent default that bites every project" class this P0
     section targets.
   - **No `CONN_MAX_AGE`.** Prod `DATABASES` has no persistent connections, so on a small VPS with
     Gunicorn `gthread` workers a fresh DB connection is opened per request. **Fix:** add an
     env-guarded `CONN_MAX_AGE` to the same `DATABASES` edit.

### P1 — missing / weak reusable primitives

5. **Ship a dependency-checking, importable health endpoint.**
   - Today the health view is a per-project copy returning `{"status": "healthy"}` with
     **no DB/cache check** (`config/urls.py:35-37,52` FLS / `:23-25,34` concrete; manifest
     `template_repo_manifest.md:213`). It cannot distinguish "process up" from "DB
     reachable," so it is weak as a readiness probe or post-deploy smoke test, and every
     project re-declares the same function.
   - **Fix:** provide an **importable** FLS health module (e.g. views + a
     `freedom_ls.health.urls` that projects `include(...)`) exposing **two endpoints**:
     - **liveness** — a shallow "process is up" check that touches no dependencies and
       always returns 200 if the process can serve a request. Used by the container/orchestrator
       to decide whether to restart the process.
     - **readiness** — a deep check of DB connectivity (optionally cache and
       applied migrations), returning non-200 when a dependency is down. Used by compose
       `healthcheck:` directives and post-deploy rollback smoke tests to decide whether the
       app is ready to serve traffic.

     This gives projects both probes without copy-paste, and lets liveness and readiness
     fail independently (process up but DB unreachable → live but not ready).
   - **Gotcha to design for: `SECURE_SSL_REDIRECT` 301s the probe.** With P0(1)'s
     `SECURE_SSL_REDIRECT = True`, an **internal plain-HTTP** request to `/health/` (the normal
     container-healthcheck path, hitting the app over localhost with no TLS) is answered with a
     **301 → https**. A naive `healthcheck:` or smoke test that expects 200 then sees 301 and marks
     the container **unhealthy**, blocking every deploy. The health endpoints must therefore either
     be **exempt from SSL redirect**, or the probe must send `X-Forwarded-Proto: https` (so
     P0(1)'s `SECURE_PROXY_SSL_HEADER` treats it as secure) / speak HTTPS directly. Ship the P3
     compose `healthcheck:` examples doing this correctly — this is also the "dependency-checking
     healthcheck" prerequisite the downstream docker-rollout research already wants
     (`spec_dd/next/deployment/docker-rollout-research.md`).

6. **Reconcile the background-tasks story end-to-end** — the code-side counterpart to
   P0(3). The **shipped default** (`ImmediateBackend`, no worker), the **opt-in** importable
   `DatabaseBackend` + `db_worker`, the **present-but-disabled** `worker` container, and
   `deployment.md` / `deployment-playbook.md` must all agree: the docs describe how to *enable*
   the worker, not a worker the default stack runs. No more docs promising a `db_worker` the
   shipped code doesn't start.

### P2 — shipped artifacts & docs hygiene

7. **Resolve the nginx-vs-Caddy contradiction and the broken standalone Dockerfile.**
   - Docs declare Caddy the current architecture and nginx **superseded**
     (`docs/product/deployment.md:28,:111,:113`), but the **shipped**
     `docker-compose.yml:45-51` runs `nginx:1.25-alpine` against `nginx.conf`, and **no
     Caddyfile exists anywhere**. So the "current" architecture is documentation-only while
     the shipped stack is the superseded one. The compose DB volume also defaults to a
     **bind mount** (`docker-compose.yml:10`), contradicting the "named volume, never a
     bind mount" rule for prod. The standalone `Dockerfile` frontend stage is additionally
     **broken**: the `node` stage runs `npm run tailwind_build` (which invokes `uv run …`)
     but has no `uv`/Python, copies `tailwind.input.css` but not the `tailwind.*.css` files
     it `@import`s, and has **no `ARG FLS_THEME`** despite docs mandating a build-time theme
     (`docs/product/deployment.md:62`). `docs/how tos/DOCKER_DEPLOY.md` is stale.
   - **Fix:** **remove** the superseded standalone artifacts — the nginx compose stack, the
     broken standalone `Dockerfile`, and the stale `DOCKER_DEPLOY.md` — rather than repairing
     them. Since FLS is never deployed standalone (see item 8), there is no build for these to
     serve; repairing a standalone Dockerfile to the Caddy architecture would only produce a
     second, unused deployment path. The working Caddy-based stack ships instead through the
     P3 concrete template repo. Docs and shipped code must stop disagreeing — by deleting the
     artifacts that describe a deployment mode no one runs.

8. **Make the concrete (submodule) deployment path the *only* documented path.**
   - **FLS is never deployed standalone — only concretely, as a submodule of a downstream
     project.** Yet all current deployment guidance and every shipped deployment artifact
     targets the **standalone** FLS repo, and nothing explains how a submodule-based project
     (host `config`, `[tool.uv.sources]`, project-owned `tailwind.input.css`) builds an
     image, wires compose, chooses a proxy, or runs Gunicorn. So today FLS documents a
     deployment mode that no one uses and omits the only one that ships.
   - **Fix:** treat the standalone deployment docs and artifacts as **legacy to remove**, not
     a parallel path to maintain. The "scope the existing docs as standalone-only" option is a
     non-option — there is no standalone deployment for those docs to serve. Replace them with
     a single "Deploying a concrete (submodule-based) project" guide that points at the P3
     template-repo scaffolding as the canonical, and only, deployment path.

### P3 — ship the reusable deployment scaffolding to the concrete template repo

This is the "scaffold as much as possible" core. Ship, into the
`freedom-ls-concrete-template` repo (synced via `/fls:sdd:update_template_repo`), a working
Caddy-based, submodule-correct baseline so every new concrete project starts
deployment-ready:

- **Submodule-aware Dockerfile** — multi-stage, `ARG FLS_THEME`, builds project-owned
  Tailwind, installs `freedom_ls` **from the submodule**, and uses `uv.lock` (reproducible
  builds — the shipped standalone image installs straight from `pyproject.toml`).
- **Parameterised `docker-compose.yml`** — **named volume, never a bind mount**;
  **`json-file` log driver with `max-size`/`max-file` caps per service (required — this is what
  makes P0(2)'s stdout logging safe on a small VPS)**; healthchecks that speak to the P1(5)
  endpoints **without tripping SSL redirect** (send `X-Forwarded-Proto: https` or target HTTPS);
  `COMPOSE_PROJECT_NAME` + `--env-file` so the same file runs staging **and** prod on one
  host with isolated containers/networks/volumes; and a **`worker` container present but
  disabled by default** (commented / env-flagged OFF) running `db_worker` against the P0(3)
  opt-in `DatabaseBackend` — enabling async is a one-line change, and V1 ships without it to
  match the downstream decision.
- **Caddyfile** — one Caddy, automatic HTTPS, host-based routing, sets `X-Forwarded-Proto`
  (paired with P0(1)); WhiteNoise serves static and media is on S3, so Caddy only proxies.
- **`docker-entrypoint.sh`**, **`.env.example`** (documents every var settings reads),
  **`.dockerignore`**.
- **GHCR build-and-push CI** — FLS's `.github/workflows/` builds/tests but ships **no**
  image-build or deploy workflow today; provide the SHA-tagged build+push template.
- **Ansible** provisioning/hardening, **backups** (`pg_dump` + encrypted off-box sync),
  and **Sentry** observability wiring — all as parameterised templates.

**Reusable-template requirement:** every site-specific value (domain, branding, secrets,
DB names, R2 buckets, Sentry project) is a substitutable placeholder, so a new install is
"fill in the variables, run the bootstrap" — never an edit to shared logic.

## Scaffolding-home decision (resolved)

The reuse boundary is **artifact-vs-code**, and this idea resolves it decisively (closing
the downstream master idea's open "Shared scaffolding home" item,
`spec_dd/next/deployment/idea.md:373`):

- **Reusable deploy *artifacts*** (Dockerfile, compose, Caddyfile, entrypoint,
  `.env.example`, CI, Ansible, backup scripts) live in the **`freedom-ls-concrete-template`
  repo** and reach projects via `/fls:sdd:update_template_repo`. This is the home that
  serves the submodule consumer directly.
- **Reusable *code* primitives** (the health module, the P0 prod-settings defaults, the
  P0(3) opt-in `DatabaseBackend` tasks primitive) live in **`freedom_ls` itself** so they are
  **imported, not copy-pasted** — the durable fix for "no importable base-settings module." The
  tasks backend is shipped as an importable primitive projects *may* enable; the shipped default
  stays `ImmediateBackend`.

Not "shared repo *vs* upstream into FLS" left open — **both**, split cleanly by whether the
thing is an artifact or code.

## Suggested triage

- **Land first (P0, items 1–4):** small, self-contained template + reference `config/`
  edits that remove silent production failures for every project.
- **Then (P1):** the importable health endpoint (5) and the background-tasks reconciliation
  (3/6), which unblock real compose healthchecks and any async work.
- **Then (P2/P3):** artifact/doc hygiene and the template-repo scaffolding.
- **Every P0 landing has a fourth step: run `/fls:sdd:update_fls` against `ConcreteFlsImplementation`** (and any
  other existing project). Landing in the template + reference config only patches *future*
  projects; the flagship consumer that raised this idea stays vulnerable until `/update_fls` runs.

Items 1–5 are each independently shippable and independently valuable.

## Out of scope

- **`ConcreteFlsImplementation`'s own downstream deploy artifacts and CI/CD** — those live in the
  downstream repo (`spec_dd/next/deployment/idea.md`); this document only covers FLS-side
  changes.
- **Kubernetes / horizontal scaling** — deferred per the downstream deployment idea and
  FLS's own Phase-4 stance.
- **ISO 27001 certification process** itself.

## References (verified against `submodules/Freedom-LS` at the current SHA)

- Prod settings twins — FLS `config/settings_prod.py` and downstream `config/settings_prod.py`:
  `SECURE_SSL_REDIRECT` (:16 / :15); LOGGING with `RotatingFileHandler` (:65-146, handlers
  at :86/:91/:99/:107); `TASKS` `ImmediateBackend` + `# TODO @claude` (:208-215 / :191-197);
  `DATABASES` with no `OPTIONS` (:48-57 / :47-56).
- Template repo contract: `fls-claude-plugin/resources/template_repo_manifest.md` (:128
  TASKS, :193 `settings_prod.py`, :213 health) and
  `fls-claude-plugin/commands/sdd/update_template_repo.md`.
- Health view: FLS `config/urls.py:35-37,52`; downstream `config/urls.py:23-25,34`.
- Only real task consumer: `freedom_ls/webhooks/events.py`.
- Shipped artifacts: `Dockerfile`, `docker-compose.yml` (nginx :45-51, logs bind-mount :26,
  DB bind-mount :10), `nginx.conf`, `package.json`, `tailwind.input.css`.
- Docs: `docs/product/deployment.md` (:28, :52, :62, :111, :113),
  `docs/how tos/DOCKER_DEPLOY.md`, `docs/deployment-security-checklist.md` (:22, :33).
- Downstream decisions this idea must not contradict — `spec_dd/next/deployment/idea.md`
  (V1 keeps `ImmediateBackend`, no worker container; `json-file` log cap treated as required) and
  `spec_dd/next/deployment/cloudflare-front-research.md` (Cloudflare SSL **Full (strict)**,
  `trusted_proxies`, `CF-Connecting-IP`).
