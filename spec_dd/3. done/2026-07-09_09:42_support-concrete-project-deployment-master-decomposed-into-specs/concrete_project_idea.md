# Deploy `ConcreteFlsImplementation` to Vultr (Docker Compose on a single VPS)

> **Terminology.** `ConcreteFlsImplementation` is the placeholder used throughout for the
> specific concrete production implementation of FLS this document deploys — a downstream repo
> that installs `freedom_ls` as a submodule. It is deliberately *not* named after any theme;
> earlier prototyping in the FLS repo produced a similarly-named theme, and the placeholder
> keeps the two from being confused. Wherever `ConcreteFlsImplementation` appears it always
> means that downstream implementation project, never a theme.

## Problem

We need to deploy **`ConcreteFlsImplementation`** (this concrete FLS project) to production. The
target architecture is already decided in FLS's own docs — a single **Vultr
Johannesburg** VPS running Docker Compose (Caddy + Gunicorn + Django + a
containerised PostgreSQL), provisioned with Ansible, deployed via GitHub Actions →
GHCR → SSH pull. See `submodules/Freedom-LS/docs/product/deployment.md` and the
`deployment-playbook.md` (in the product-documentation spec); these are the
**source of truth** and this idea does not re-litigate them.

The gap is on **our** side:

- `config/settings_prod.py` is already production-ready and fully env-driven (S3
  media via `AWS_*`, WhiteNoise compressed-manifest static, full security headers /
  HSTS / secure cookies, env-var DB + `SECRET_KEY` + email). Nothing is hardcoded.
- But **this repo has no deployment artifacts at all** — no Dockerfile, no
  production compose file, no Caddyfile, no Ansible, no CI/CD workflows (only
  `.github/dependabot.yml`). `dev_db/docker-compose.yaml` is dev-only.

We **cannot** reuse the Dockerfile / `docker-compose.yml` that FLS ships in the
submodule:

1. `CLAUDE.md` forbids editing anything under `submodules/` — it is a read-only
   dependency.
2. They are written for the FLS **standalone** repo: the build context assumes
   `./freedom_ls` exists at the root and copies a root `pyproject.toml`. In this
   project `freedom_ls` is installed from `submodules/Freedom-LS` via
   `[tool.uv.sources]`, so those `COPY` paths do not apply.
3. They use **nginx**, which FLS's `deployment.md` explicitly marks **superseded
   by Caddy**.

So `ConcreteFlsImplementation` must author its **own** deployment artifacts at the project root.

## How this differs from what FLS documents

We **deliberately do not diverge on architecture**: single Vultr VPS + Docker
Compose + Caddy is FLS's documented source of truth, and this idea adopts it
wholesale. The differences are implementation adaptations and additions layered on
top:

- **Same architecture, different repo shape.** FLS's Dockerfile/compose assume the
  **standalone** FLS repo (a root `./freedom_ls`, its own `pyproject.toml`). First
  Class installs `freedom_ls` from `submodules/Freedom-LS` via
  `[tool.uv.sources]`, and `CLAUDE.md` forbids editing anything under
  `submodules/`. So we author our **own** artifacts at the project root rather than
  reusing the submodule's. Related: a slim image may ship without `.git`, so
  `LEGAL_DOCS_MANIFEST_PATH` may be required (per FLS's deployment-security
  checklist).
- **Caddy, not nginx — aligned with FLS.** FLS marks its nginx-based
  `DOCKER_DEPLOY.md` **superseded by Caddy** (automatic HTTPS, no Certbot). We skip
  the legacy nginx path entirely, matching FLS's current stance.
- **Two stacks on one host (staging + prod) — a `ConcreteFlsImplementation` addition.** FLS's docs
  describe a single standalone deployment. We run staging + prod as two Compose
  stacks on one VPS (per-env `COMPOSE_PROJECT_NAME` + `--env-file`, one shared
  Caddy routing by host, staging basic-auth + `noindex`). FLS does not document
  this.
- **Deliberate divergence on background tasks.** FLS's docs assume the
  `django-tasks` **DatabaseBackend** + a separate `db_worker` container. `ConcreteFlsImplementation`
  keeps the built-in Django Tasks **`ImmediateBackend`** for V1 — Django 6 ships the
  Tasks framework natively, so there is no `django-tasks` package to install and no
  `worker` container to run, and tasks execute synchronously in-process — because no
  feature needs deferred/async work yet. The durable backend + worker is the
  documented upgrade path. This resolves the `# TODO @claude` in `settings_prod` as
  an explicit choice, not an oversight.
- **Logging fix, aligned with FLS.** FLS assumes **stdout** logging; our
  `config/settings_prod.py` uses a local-disk `RotatingFileHandler`. We switch to
  stdout (see "Shape of work" below), alongside adding `SECURE_PROXY_SSL_HEADER`
  (needed to sit behind Caddy).
- **Project-specific choices FLS leaves open.** S3 media provider (Vultr Object
  Storage / Cloudflare R2 / Backblaze B2), the observability tool (**decided:
  Sentry**, covering errors + logs + uptime + crons), the **log shipping backend**
  (stdout is only *emission* — retention/aggregation off the box is a `ConcreteFlsImplementation`
  decision; V1 uses Sentry for app logs, keeps infra logs on-box), backup automation,
  and the forward-looking multi-project reuse goal are all decisions `ConcreteFlsImplementation`
  makes that FLS does not prescribe.

## Goal

**Staging and production** deployments of `ConcreteFlsImplementation` on Vultr that match the FLS
target architecture, with **all deployment code living in this repo**, structured
so the generic parts can later be shared across multiple FLS projects.

## Decision: deployment code lives in this repo (monorepo)

Deployment artifacts live alongside the application, not in a separate repo,
because:

- **Atomic versioning** — the Dockerfile pins the exact submodule SHA and
  `pyproject` dependency set; CI tests the exact code it builds and ships. A
  separate repo would have to track "which app commit am I deploying", adding
  coordination overhead with no real benefit at this scale.
- **FLS's deployment design assumes colocation** — the Dockerfile build context,
  the compose file, and the GHCR-build pipeline all expect app + deploy artifacts
  in one repo.
- **Operational simplicity** — one clone, one PR history, one CI pipeline.
- **ISO 27001 change management** — a single auditable git/PR trail covering both
  application and infrastructure changes is exactly the evidence auditors expect.

Secrets are **never** committed. On the VPS, `.env` is managed directly / via
Ansible Vault.

## Repo layout

```
Dockerfile               # repo root — multi-stage app image
docker-compose.yml       # repo root — caddy + web + worker + db
docker-entrypoint.sh     # repo root
Caddyfile                # repo root
.env.example             # repo root — documents every required env var
.dockerignore            # repo root — keeps build context small/correct
deploy/ansible/          # provisioning + OS hardening roles/playbooks
.github/workflows/       # ci.yml (test + build + push GHCR), deploy.yml (SSH pull)
```

## Target architecture (per FLS `deployment.md`)

```
[Cloudflare CDN/WAF — free tier, orange-cloud proxy]  # CDN + unmetered DDoS + origin-IP hiding + baseline WAF, $0. See "Cloudflare front (edge CDN/WAF)".
    → [Vultr JNB VPS] # scale UP = in-place resize (reboot + grow filesystem); scale DOWN = rebuild onto a new VPS. See "Scaling this VPS" and "Why not Kubernetes (yet)?"
        → Caddy (reverse proxy + automatic HTTPS via Let's Encrypt)
        → Gunicorn + Django 6 (WSGI application, gthread workers)  # ASGI/Channels deferred — see "Async / ASGI / Channels (deferred)"
        → PostgreSQL (containerised, named Docker volume)
        # No db_worker in V1 — ImmediateBackend runs tasks in-process. See "TASKS backend".
```

## Environments: staging + prod on one VPS

Both environments run on the **same Vultr VPS** for now, to save cost. If compute
capacity becomes a constraint, staging moves to its own VPS — the stack is authored
so that is a config change (new inventory host + env file), not a rewrite.

- **Two compose stacks, one host.** The same `docker-compose.yml` is launched twice
  with different `COMPOSE_PROJECT_NAME` + `--env-file` (`prod.env` / `staging.env`),
  so each gets its own containers, network, and named volumes (separate `db`,
  separate everything). The two stacks never share state.
- **One shared Caddy** fronts both, routing by hostname: `HOST_DOMAIN` → prod
  `web`, `staging.HOST_DOMAIN` → staging `web`, with automatic HTTPS for both.
- **Same settings module.** Both stacks run `config.settings_prod`; they differ
  only by env values (`HOST_DOMAIN`, `DB_*`, `SECRET_KEY`, S3 bucket, deploy key).
- **Staging is not public-facing.** Caddy protects the `staging.` host with HTTP
  basic auth and sends `X-Robots-Tag: noindex`, so it is never crawled or indexed.
- **Staging data is seeded** (management command / fixtures), not copied from prod.

## Shape of work (artifacts to create)

Described here; the actual build happens in the resulting spec(s).

- **Dockerfile** — multi-stage: Node stage builds Tailwind (`FLS_THEME` passed as
  a **build-arg**, since it is baked in at build time), then a Python/uv stage
  installs production deps, runs `collectstatic`, and runs Gunicorn against
  `config.wsgi` with `config.settings_prod`. Adapted for this repo's
  submodule-sourced `freedom_ls`.
- **docker-compose.yml** — services: `web` (Gunicorn) and `db` (PostgreSQL 17,
  **named volume — never a bind mount**), plus a shared `caddy` fronting both
  stacks. **No `worker` container in V1** — `ImmediateBackend` runs tasks in-process
  (add a `worker` service later only if we adopt the durable task backend).
  Parameterised by `COMPOSE_PROJECT_NAME` + `--env-file` so the **same file runs as
  both the staging and prod stack on one host**, each with isolated containers,
  network, and volumes. Healthchecks on each; config via the per-environment `.env`.
- **Caddyfile** — one Caddy fronting both stacks with automatic HTTPS, routing by
  host: `HOST_DOMAIN` → prod `web`, `staging.HOST_DOMAIN` → staging `web`. It sets
  `X-Forwarded-Proto` (Django trusts it via `SECURE_PROXY_SSL_HEADER`) and
  reverse-proxies app traffic to `web`. **Static** is served by WhiteNoise from the
  app (so Caddy just proxies — no separate `/static/` mount), and **media is on
  S3**, so Caddy does **not** serve `/media/`. The `staging.` host additionally
  gets HTTP **basic auth** and an `X-Robots-Tag: noindex` header.
- **docker-entrypoint.sh** — exec the service command; site bootstrap per the FLS
  Docker deploy notes. **Migrations are NOT run here** — running `migrate` from
  container start is fragile (it races if a service restarts or is scaled, and
  couples schema changes to boot), so migrations run as a single one-off step in
  `deploy.yml` before the services start.
- **.env.example** — documents every variable `settings_prod` reads: `SECRET_KEY`,
  `HOST_DOMAIN`, `DB_*`, `EMAIL_*`, `AWS_*` (S3 media), `HSTS_*`,
  `DJANGO_ADMIN_URL`, `FLS_THEME`, and **`SENTRY_DSN`** (+ per-env `SENTRY_ENVIRONMENT`
  so staging and prod errors/logs stay separated). TODO: when do we set up the site
  name/domain mapping?
- **TASKS backend** — keep the built-in Django Tasks **`ImmediateBackend`** for V1
  (tasks run synchronously in-process). Django 6 ships the Tasks framework natively,
  so nothing is installed and **no `worker` container runs**. Resolve the
  `# TODO @claude` in `settings_prod.TASKS` by making this an explicit, documented
  V1 choice. The upgrade path — the external `django-tasks` package's
  `DatabaseBackend` (PostgreSQL as broker — no Celery/Redis) plus a `worker`/
  `db_worker` container — is deferred until a feature needs deferred/async work.
- **GitHub Actions** — `ci.yml`: run `pytest` against a PostgreSQL service
  container, then build the multi-stage image **once** and push to GHCR **tagged by
  commit SHA** (plus `latest` for convenience). `deploy.yml`: merge to `main`
  auto-deploys that SHA to **staging**; a **gated step** (a GitHub Environment
  requiring manual approval, or a release tag) promotes the *same, already-tested*
  SHA to **prod** — prod never rebuilds. Each deploy uses a dedicated ed25519 deploy
  key (GitHub Secrets) to SSH in, runs `migrate` as a one-off step, brings up the
  target stack with `docker compose up -d`, then polls the health endpoint and
  **rolls back to the previous SHA** if it does not come up healthy.
- **Ansible** (`deploy/ansible/`) — OS hardening (SSH key-only access, UFW,
  fail2ban, unattended security updates, disabled root login, a `deploy` user with
  limited sudo), Docker installation, **`docker login ghcr.io` with a read-only
  registry token** so the host can pull the private image (the SSH deploy key only
  gets the workflow onto the box), per-environment `.env` provisioning via Ansible
  Vault, and a `pg_dump` cron job (per stack) with encrypted offsite sync to
  Backblaze B2.
- **settings_prod fixes** (inherited by both environments):
  `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` so Django detects
  HTTPS behind Caddy (without it, `SECURE_SSL_REDIRECT` causes a redirect loop);
  and log to **stdout/stderr** instead of `RotatingFileHandler` under
  `BASE_DIR/logs/` (container file logs are ephemeral and invisible to
  `docker logs`). Note this is only the *emission* change — where logs go next is
  the **log handling** item below, not "solved" by stdout alone.
- **Log handling (emission ≠ retention).** Switching Django to stdout does **not**
  take logs off disk: Docker's default `json-file` driver still writes them to
  `/var/lib/docker/containers/**/*-json.log` on the VPS, **unbounded**. Two parts:
  - **Bound the on-disk buffer — required in V1.** Configure the Docker log driver
    with `max-size` + `max-file` (e.g. `10m` × `5`) per service in
    `docker-compose.yml` (or daemon-wide via Ansible) so container logs can never
    fill the host disk. This is a hard requirement, not optional — the current plan
    silently relies on an unbounded default.
  - **Ship logs off-box — via Sentry (application logs), infra logs on-box for V1.**
    We use **Sentry** as the single observability tool (see "Monitoring" below), and
    its structured-Logs product captures **Django's application logs** off-box
    (SDK/Python `logging` integration, trace-linked to errors, 30-day retention) —
    the logs that matter most for debugging and app-level audit. Sentry is
    SDK/app-centric, so **non-app container logs** (Caddy, PostgreSQL, entrypoint
    stdout, OS) are **not** shipped in V1; they stay **on-box**, bounded
    by the committed `json-file` size cap and read via `docker logs`. A central,
    retained store for those *infra* logs (Vector → Grafana Loki or Axiom) is
    **deferred on-signal** — reopen only if an incident can't be debugged from
    `docker logs` or an ISO auditor explicitly asks. Full comparison (Grafana Loki /
    Axiom / Better Stack / Sentry) in
    [`log-shipping-backend-research.md`](./log-shipping-backend-research.md).
- **Health endpoint** — a lightweight, dependency-checking health URL used by both
  the compose healthchecks and the post-deploy smoke test.
- **Monitoring, error tracking & alerting — Sentry (decided, not GlitchTip).** One
  hosted Sentry account is the single observability tool, covering **error tracking**,
  **application-log aggregation** (Sentry Logs — 5 GB/mo free, 30-day retention,
  trace-linked; see "Log handling" above), **uptime monitoring** (1-min URL check
  with alerting), and **cron/check-in monitoring** (alert if the nightly `pg_dump`
  backup doesn't run). GlitchTip was rejected because it is error-tracking only (no
  Logs product), so it can't consolidate observability the way Sentry now does. The
  free Developer plan is too tight for a live product (1 user, 5k errors/mo, hard
  caps), so budget for the **Team plan (~$26/mo)**. The deferred "scale when
  monitoring says so" plan depends on this existing. Caveat carried in "Log handling":
  Sentry sees the *app*, not the *box*, so infra/container logs stay on-box in V1.
- **.dockerignore** — keep the build context small and correct (exclude `.git`,
  `dev_db/`, `node_modules`, local `.env*`); the submodule tree is large.

## Multi-project consideration

More FLS-based concrete projects are planned, so the deployment scaffolding should
be designed for reuse from the start:

- Keep the **generic, reusable** parts (Dockerfile pattern, compose file, Caddyfile,
  Ansible roles, CI workflow templates) cleanly separable from the
  **project-specific** config (domain, `.env` values, server inventory, secrets).
- The **eventual home is decided (see "Shared scaffolding home" under Decisions
  resolved): split by reuse mechanism** — root boilerplate → the existing
  concrete-project **template repo** (copy-at-birth via `/update_template_repo`);
  CI/CD → **FLS reusable `workflow_call` workflows**; Ansible → a **deferred** shared
  collection, extracted only when a second project needs it. Full analysis in
  [`shared-scaffolding-home-research.md`](./shared-scaffolding-home-research.md).

This is a forward-looking design constraint only — for now everything lives in
this repo; the generic-vs-project-specific separation above is what keeps later
promotion a copy, not a rewrite. (Upstreaming CI into FLS or extracting the Ansible
collection are separate efforts, not part of this work, since the submodule is
read-only here.)

## Suggested spec split

This idea is large; it likely lands as several reviewable specs / PRs rather than
one:

1. **App-build artifacts** — Dockerfile, two-stack compose, multi-domain Caddyfile
   (staging basic-auth + noindex), entrypoint, `.env.example`, `.dockerignore`, the
   `settings_prod` fixes (proxy SSL header + stdout logging), the **Docker
   `json-file` log size cap** (`max-size`/`max-file` per service), the health
   endpoint, the TASKS backend kept on `ImmediateBackend` (no `worker` container),
   and the `CACHES` DatabaseCache backend (+ `createcachetable`).
2. **CI/CD pipeline** — SHA-tagged GHCR build, auto-deploy to staging on merge,
   gated promotion of the same image to prod, one-off migration step, and
   post-deploy health smoke test with rollback.
3. **Ansible provisioning + hardening** (incl. GHCR pull auth on the host).
4. **Backups** — `pg_dump` cron + encrypted B2 sync, with a tested restore drill.
5. **Observability** — **Sentry** (decided, not GlitchTip): error tracking +
   application-log aggregation (Sentry Logs) + uptime/health alerting + cron
   monitoring, in one tool. The V1 Docker `json-file` size cap (spec #1) is separate
   and required regardless; an off-box *infra*-log shipper (Vector → Loki/Axiom) is
   deferred on-signal, not part of this spec.

## Decisions resolved

- **PostgreSQL:** **containerised** (PostgreSQL 17 in a container with a named
  Docker volume), per FLS playbook Phase 1 — not Vultr Managed Database. Moving to a
  managed DB later is a monitoring-triggered config/`.env` change (FLS Phase 2), not
  a rewrite.
- **Backups:** **fully automated in V1**, not documented-strategy-only. A `pg_dump`
  cron (per stack) with encrypted off-box sync to **Cloudflare R2** (the off-box DB
  backup target from the S3-media decision; **B2** on retention growth), plus a
  **tested restore drill** so the backup is proven recoverable rather than assumed.
  Cron/check-in monitoring (Sentry) alerts if the nightly `pg_dump` doesn't run. This
  is spec scope item #4. Full automation is cheap here (a cron + a sync + one drill)
  and a DB you can't restore is the one failure a small VPS can't walk back, so the
  documented-strategy-only option was rejected.
- **Background tasks:** keep the built-in Django Tasks **`ImmediateBackend`** for
  V1. Django 6 ships the Tasks framework natively, so there is **no `django-tasks`
  package to install and no `worker`/`db_worker` container to run** — tasks execute
  synchronously in-process. No feature needs deferred/async work yet, so this is the
  right V1 default. Adopt the durable `DatabaseBackend` + a `worker` container (the
  external `django-tasks` package; PostgreSQL as broker — no Celery/Redis) only when
  a feature actually needs background work; that is an additive config change. See
  "TASKS backend".
- **Environments:** staging + prod share **one VPS** for now; split staging to its
  own VPS only if compute becomes a constraint.
- **Config:** both environments run `config.settings_prod`, differing only by env
  values.
- **App server:** stays **WSGI/Gunicorn** (`gthread`) for V1; async/ASGI/Channels
  is deferred and feature-gated (see "Async / ASGI / Channels (deferred)").
- **Cache backend:** Django's **database cache** (`DatabaseCache` +
  `createcachetable`) for V1 — a worker-shared cache with **no new service**,
  mirroring the "PostgreSQL as broker" choice for background tasks. This closes the
  current gap where no `CACHES` is configured (so allauth's rate limits fall back to
  per-process `LocMemCache` and reset per worker). Redis/Valkey is deferred to a
  real trigger; see "Cache backend (database cache for V1)" and
  [`valkey-cache-idea.md`](./valkey-cache-idea.md).
- **Promotion:** build once (SHA-tagged), auto-deploy to staging on merge to
  `main`, gated manual promotion of the *same image* to prod.
- **Staging data:** seeded, not copied from prod.
- **Observability + logging: Sentry** (hosted, **not GlitchTip**). One tool for error
  tracking + application-log aggregation (Sentry Logs, 30-day retention) + uptime +
  cron monitoring. Budget the ~$26/mo Team plan. Infra/container logs (Caddy/Postgres/
  OS) stay **on-box** in V1 bounded by the `json-file` cap; an off-box infra-log
  shipper (Vector → Grafana Loki / Axiom) is deferred on-signal. See "Monitoring",
  "Log handling", and [`log-shipping-backend-research.md`](./log-shipping-backend-research.md).
- **Vertical scaling:** grow **up** via in-place Vultr resize (reboot +
  filesystem-grow step); scaling **down** is a rebuild onto a new VPS, so size
  conservatively and grow upward. See "Scaling this VPS (up vs down)".
- **Cloudflare front:** **in scope for V1**, on the **free tier** (orange-cloud
  proxy), fronting **both** prod and staging. We control the domain's DNS, so
  authoritative DNS moves to Cloudflare. **Not** buying Vultr's DDoS add-on
  ($10/mo/instance does less than Cloudflare free). Pro/Business is a later,
  on-signal upgrade (a billing toggle, not a rearchitecture). See "Cloudflare
  front (edge CDN/WAF)" and [`cloudflare-front-research.md`](./cloudflare-front-research.md).
- **Reserved IPs:** adopt **Vultr Reserved IPs** for staging + prod from V1, so a
  VPS rebuild/downgrade is an IP re-attach, not a DNS change. Low cost, and it
  preserves the "config change, not a rewrite" posture. The filesystem-grow step is
  in the Ansible/runbook regardless.
- **S3 media provider: Cloudflare R2.** Native to the Cloudflare edge we already
  run (custom-domain binding on the existing zone, served from the JNB PoP with the
  WAF in front), **unconditional $0 egress**, a real free tier (~$0 at V1 image
  scale), S3-compatible via `django-storages`, and **no new vendor**. **Not** Vultr
  Object Storage — an **$18/mo floor** (bills a full 1 TB) and no Johannesburg
  object-storage region kill both its cost and co-location rationale. R2 also holds
  **off-box DB backups** for V1 (one namespace, ~free), giving provider-level DR
  separation from the Vultr host. **Backblaze B2** is the documented fallback, to
  adopt only when stored media reaches the low-TB range (or scope broadens to
  video/large files) or backup retention accumulates into many GB/TB — the point
  where B2's $0.006/GB beats R2's $0.015/GB; migration is a `django-storages` config
  change + one-time copy. Media spec bakes in presigned direct-to-S3 uploads (also
  the workaround for Cloudflare's 100 MB proxied-upload cap), a `media.HOST_DOMAIN`
  custom-domain binding with edge caching, public bucket for images / presigned GET
  for protected media, CORS, and a POPIA note for if media later holds PII. See
  [`s3-media-provider-research.md`](./s3-media-provider-research.md).
- **Shared scaffolding home: split by reuse mechanism — not one home.** The
  eventual multi-project home is decided per *how each artifact reuses*, because the
  artifacts don't reuse the same way (full analysis in
  [`shared-scaffolding-home-research.md`](./shared-scaffolding-home-research.md)):
  - **Root boilerplate** (Dockerfile, compose, Caddyfile, entrypoint,
    `.env.example`, `.dockerignore`) → the **existing concrete-project template
    repo** (`preludetech/freedom-ls-concrete-template`), propagated with the
    already-built `/update_template_repo` machinery. These files *must* sit at each
    project's root (build context + `docker compose` discovery), so they can't be
    consumed live from FLS's read-only submodule — copy-at-birth via the template is
    the right mechanism, and the template already owns root wiring (incl. `dev_db/`
    compose). This is the third option the earlier "shared repo vs upstream" framing
    omitted, and it carries the largest part.
  - **CI/CD** → **upstream into FLS as `workflow_call` reusable workflows**, called
    by a thin per-project caller pinned to a version. Workflows are referenced by
    repo path (no build-context problem), and FLS is already the org CI hub (it runs
    `notify-downstream.yml`), so a fix reaches every project by bumping one ref.
  - **Ansible** → **stay in this repo for V1; extract to a shared
    `freedom-ls-deploy` collection (or FLS `deploy/`) only when the *second*
    concrete project actually needs it** — a real-consumer trigger, not speculative
    extraction.
  This does **not** change V1: every artifact is still authored **in this project
  repo** now (per "Multi-project consideration"), just *structured* generic-vs-
  project-specific so promotion later is a copy, not a rewrite. "Upstream everything
  into FLS" was rejected (root files can't be consumed from a submodule, so FLS
  could only hold duplicate reference copies); "one new shared repo for everything"
  was rejected (for copy-at-birth files it's also just a source-to-copy, duplicating
  the template and adding a second sync path before a second project even exists).
- **Zero-downtime deploys: deferred.** Ship V1 on the `docker compose up -d` blip
  (~1–2s per deploy, absorbed by Cloudflare + Caddy retries on idempotent requests);
  **not** adopting `docker-rollout` now. At a single small VPS with gated prod deploys
  we schedule, the blip is acceptable and keeps the deploy path dependency-free. We
  build V1 so later adoption is a config change, not a rewrite, by taking on the
  prerequisites that are good hygiene anyway: **backward-compatible (expand/contract)
  migrations** as a written rule, a real dependency-checking healthcheck (already in
  scope), and **no `container_name:` / no published ports on `web`** (already true —
  it's proxied by Caddy). Switching on zero-downtime later is then: install the plugin
  (Ansible), swap `docker compose up -d web` → `docker rollout web` in `deploy.yml`,
  add a Caddy dynamic-upstream note, and validate draining. Reopen if prod deploys
  become frequent during active hours or any blip becomes unacceptable. See
  [`docker-rollout-research.md`](./docker-rollout-research.md).

## Decisions needed

_(none open)_

## Cloudflare front (edge CDN/WAF)

We put **Cloudflare free** in front of the VPS from V1 (orange-cloud proxy),
fronting **both** prod and `staging.HOST_DOMAIN` on one free zone. Full research
and the tier comparison are in
[`cloudflare-front-research.md`](./cloudflare-front-research.md).

- **Why an edge at all.** It hides the Vultr origin IP (public DNS resolves to
  Cloudflare, not the VPS), absorbs volumetric L3/4 DDoS before it reaches a single
  small VPS, offloads/caches static via a JNB PoP, and adds a WAF layer in front of
  Django — useful defence-in-depth and ISO-27001 perimeter evidence.
- **Free tier is enough for V1.** Every Cloudflare tier gives the *same* CDN +
  unmetered DDoS + Universal SSL + origin-IP hiding; you pay Pro/Business almost
  entirely for **WAF depth, edge rate limiting, and SLA/support**. Free's real
  gaps: a fixed "Free Managed Ruleset" (no tunable OWASP Core Ruleset), only 5
  custom rules (no regex), and **no edge rate limiting**.
- **Cover the rate-limiting gap at the origin.** Because free has no edge rate
  limiting, throttle auth brute-force/scraping at the origin — Caddy `rate_limit`
  and/or `django-axes` on login, plus the `fail2ban` the Ansible hardening already
  installs.
- **Not using Vultr's DDoS add-on.** Vultr DDoS Protection ($10/mo/instance, L3/4
  only, JNB-available) does strictly **less** than Cloudflare free (no CDN, no WAF,
  no origin hiding) for money. Skipped.
- **Upgrade to Pro/Business on a security signal, not a calendar** — a billing
  toggle on the same zone (no DNS change, no cutover). Triggers: auth-attack
  pressure that origin throttling can't absorb, a targeted L7 attack the free
  ruleset misses, a compliance need for a tunable OWASP WAF, an SLA requirement, or
  proxied uploads >100 MB. (This depends on the observability work below existing so
  we *notice* the trigger.)
- **Setup specifics for the spec.** SSL mode **Full (strict)** (Caddy already holds
  a valid Let's Encrypt cert — never "Flexible", which would loop against
  `SECURE_SSL_REDIRECT`); restore the real client IP via **`CF-Connecting-IP`** and
  set Caddy `trusted_proxies` to Cloudflare's ranges (so logging, `django-axes`, and
  `fail2ban` act on the true visitor); **firewall the origin (UFW) to Cloudflare's
  IP ranges** so the box can't be hit directly by IP; `SECURE_PROXY_SSL_HEADER`
  stays as already planned. Cloudflare free/Pro enforce a **100 MB proxied
  request-body limit** — large media must go **presigned direct-to-S3** (bypassing
  the proxy), which also offloads the VPS; confirm against the media-upload flow.

## Scaling this VPS (up vs down)

Vertical scaling on Vultr is **asymmetric**, and the deployment posture has to
account for both directions:

- **Scale UP — in place, same VPS, same IP, no data migration.** Console →
  instance → **Change Plan** (or API/CLI/Terraform) to a larger plan. Vultr powers
  the instance off, grows the virtual disk, and reboots it on the new plan — a short
  reboot window (a few minutes); there is **no** zero-downtime resize. The named
  Postgres volume and all data survive untouched. **Caveat:** Vultr enlarges the
  *virtual disk* but the root partition/filesystem usually does **not** auto-expand
  — a `growpart` + `resize2fs`/XFS-grow step is required afterwards to actually use
  the new space. This should be a documented runbook step (or an Ansible task), as
  it is easy to forget and silently leaves paid-for disk unused. Note also that an
  upgrade is **permanent and cannot be undone** (precisely because the disk grew).
  This is the intended Phase 1→2 growth lever — cheaper and simpler than any
  horizontal/k8s move (see below).
- **Scale DOWN — NOT in place; it is a rebuild.** Vultr does **not** support
  downgrading a resized instance (shrinking a disk risks data loss across their
  OS/ISO matrix), so going smaller means spinning up a **new, smaller VPS**,
  migrating configs + data across, and cutting over. This is the "new VPS + move
  everything" path.

**Implications for this design:**

- **Size the VPS conservatively and grow upward** rather than provisioning large
  and planning to trim later — trimming is a rebuild, not a resize.
- **Adopt Vultr Reserved IPs from day one** (for both staging and prod). A reserved
  IP detaches the public address from any single instance, so a downgrade — or *any*
  rebuild onto a fresh VPS — becomes an IP re-attach rather than a DNS scramble.
  This is what keeps "move to a new VPS" a **config change, not a rewrite**, matching
  the same posture the staging-split and multi-project sections already take.

## Why not Kubernetes (yet)?

Vultr Kubernetes Engine (VKE) offers a **free control plane**, which invites the
question: why not run `ConcreteFlsImplementation` on k8s and scale up/down on demand? For V1 the
answer is **no** — and this is not a fresh opinion, it is exactly what FLS's own
`deployment-playbook.md` already prescribes. k8s remains the right *deferred*
option, not the right *now* option.

- **"Free control plane" ≠ free (or cheap) cluster.** VKE waives the control-plane
  fee, but a real cluster still costs **more** than the current plan: you pay for
  worker nodes (2 GB+ RAM each, at normal compute rates — and you want ≥2 for the
  HA that is k8s's whole point), a **load balancer** (~$10/mo, billed as a compute
  instance), and **block storage** for persistent volumes; an HA control plane adds
  another **$40–50/mo per cluster**. That exceeds the **one** $40–48/mo VPS that
  today runs **both** staging and prod (FLS Phase 1).
- **FLS already defers this on trigger, not calendar.** The playbook scales on
  monitoring data (CPU consistently >70% at peak, or DB >50 GB), and places
  container orchestration at **Phase 4 — "unlikely to be needed before 5,000+
  concurrent users."** Even then it recommends **Docker Swarm first** (near-
  identical Compose syntax, adds replication + rolling updates + self-healing),
  moving to k8s only for CRDs, operators, GitOps/ArgoCD, or genuinely complex
  multi-service architectures. Playbook conclusion: *"managed databases,
  horizontal scaling, Kubernetes — follow naturally from monitoring data, not from
  architecture anxiety."*
- **The app isn't stateless enough to scale horizontally yet** — which is the thing
  k8s actually buys. `settings_prod` logs to a local-disk `RotatingFileHandler` and
  only uses S3 media when `AWS_*` is set; this idea fixes logging (stdout) and sets
  the S3 env. Background tasks stay on `ImmediateBackend` (in-process, no worker),
  which is horizontal-safe on its own, and the deferred durable backend is
  Postgres-backed, so likewise horizontal-safe when adopted. So the remaining V1
  statelessness fix is logging — until it lands, horizontal replicas would misbehave
  regardless of orchestrator.
- **Postgres on k8s is a known operational cost.** StatefulSets, PVCs, failover and
  backups are all fiddlier than a named Docker volume — and the database is the
  real LMS bottleneck, which k8s does **not** relieve. Most teams end up on a
  managed DB anyway (FLS Phase 2), at which point k8s bought the data tier nothing.
- **It sacrifices operational simplicity.** Caddy's zero-config automatic HTTPS
  gives way to an ingress controller + cert-manager; and you take on
  kubectl/Helm/RBAC/node-upgrade overhead — against this idea's "one clone, one PR
  history, one CI pipeline" goal and FLS's "match the team's size, not the
  product's ambitions."

**Before k8s, the cheaper scaling lever is vertical.** On Vultr, "bigger CPU/RAM"
is a VPS resize (a reboot), not a re-architecture — that is the intended Phase 1→2
growth step, ahead of any horizontal move.

**Revisit k8s when** *any* of these hold — and evaluate **Docker Swarm first** at
that point:

- a sustained need for **multi-VPS horizontal scaling** that vertical resizing and
  a separate managed DB (FLS Phase 2/3) no longer cover, backed by monitoring data;
- **~5,000+ concurrent users** (FLS's Phase 4 threshold); or
- the **multi-project fleet** grows enough that one shared VKE cluster
  (namespace-per-project) is genuinely cheaper/simpler than N single VPSes — the
  one place the free control plane could eventually pay off.

## Async / ASGI / Channels (deferred)

The app server is **Gunicorn + Django 6 (WSGI)** for V1, matching FLS's documented
architecture. A future move to async (native async views, SSE, or Django Channels /
WebSockets) is a **deferred, feature-gated** decision — not something we build
infrastructure for now. Full research is in
[`async-asgi-channels-research.md`](./async-asgi-channels-research.md).

- **WSGI now, per FLS V1.** FLS's `deployment.md` specifies Gunicorn WSGI with the
  `gthread` worker class and "no Celery/Redis at launch." There is **no** async,
  WebSocket, or SSE usage anywhere in the code today, so ASGI would buy nothing yet
  (and adds a marginal threadpool cost for a purely-sync workload).
- **The swap is cheap and comes in three tiers.** (1) **Async views** — change the
  Gunicorn target to `config.asgi:application -k uvicorn.workers.UvicornWorker` and
  add the `uvicorn` deps; sync views keep working unchanged, **no Redis**. (2)
  **Server-Sent Events** (one-way live updates) — a native async streaming view;
  needs ASGI but **still no Channels/Redis**. (3) **Django Channels / WebSockets**
  (bidirectional realtime) — the only tier that adds infrastructure: `channels` +
  `channels-redis` + a **Redis** channel layer (the in-memory layer can't span
  worker processes), which is **already deferred** below.
- **Door already open at ~zero cost.** `config/asgi.py` exists (stock Django ASGI
  entrypoint), and Caddy proxies WebSocket/streaming connections transparently — so
  the reverse proxy needs no redesign. The swap is a runbook checklist, not a
  re-architecture.
- **Revisit trigger.** The first feature needing live/bidirectional updates —
  concretely the already-scoped FLS `student-communication` real-time layer (live
  unread counts, incoming messages, typing/presence). That feature itself mandates
  **graceful degradation to HTMX polling**, so it can ship on WSGI first and turn
  on ASGI/Channels as an enhancement.

## Cache backend (database cache for V1)

There is currently **no `CACHES` setting**, so Django falls back to per-process
`LocMemCache`. That is invisible for most of the app but matters in one place:
`allauth`'s rate limits are cache-backed, so under multiple Gunicorn workers their
counters are **per-worker and reset on restart** — softer than they look. (The
security-critical control, `django-axes` account lockout, is DB-backed and already
cross-worker/durable, so this is a hardening gap, not a hole.)

- **Decision: use Django's database cache for V1.** Set `CACHES` to
  `django.core.cache.backends.db.DatabaseCache` and create the table with
  `manage.py createcachetable` (a one-off step alongside the migration step in
  `deploy.yml`). This gives allauth a cache **shared across Gunicorn workers and
  restart-durable** with **no new service** — the same "PostgreSQL is already there,
  use it" reasoning that would back a Postgres task broker if/when we adopt one.
- **Why not Redis/Valkey now.** It would be the first always-on stateful service
  the architecture is deliberately avoiding at V1, for a payoff (firming up
  secondary auth counters) that the DB cache already delivers. The cache is
  low-volume and off the hot path, so DB-backed latency is a non-issue at this
  scale.
- **Spec touchpoints.** Add `CACHES` to `settings_prod`, add `createcachetable` to
  the deploy one-off steps (next to `migrate`), and confirm allauth's
  `ACCOUNT_RATE_LIMITS` are active in prod (they are: `settings_dev` disables them,
  `settings_base` keeps the defaults + `signup` override).
- **Upgrade trigger → Valkey.** When a real Redis-shaped need appears (Tier-3
  Channels channel layer, a queue that outgrows the Postgres broker, or multi-node
  scaling where DB-cache contention bites), adopt **Valkey** — not Redis — as the
  one service covering channel layer + cache + broker. Full reasoning and the
  cutover in [`valkey-cache-idea.md`](./valkey-cache-idea.md).

## Out of scope / deferred

- **Terraform** — deferred to playbook Phase 2 (multiple servers).
- **ASGI / Django Channels / WebSockets** — V1 runs WSGI/Gunicorn; the async swap
  is feature-gated and cheap when needed. See **"Async / ASGI / Channels
  (deferred)"** above.
- **Horizontal scaling, Redis/Valkey, Kubernetes** — later phases, triggered by
  monitoring data; see **"Why not Kubernetes (yet)?"** above for the reasoning and
  the concrete triggers that would reopen the k8s question. V1 caching uses the
  **database cache** (see "Cache backend (database cache for V1)"); the eventual
  in-memory service is **Valkey**, scoped in [`valkey-cache-idea.md`](./valkey-cache-idea.md).
- **ISO 27001 certification process** itself (ISMS documentation, audits) — a
  separate effort; this idea only covers the deployment that supports it.

## References (source of truth)

- `submodules/Freedom-LS/docs/product/deployment.md`
- `submodules/Freedom-LS/spec_dd/3. done/2026-06-10_12:07_product-documentation/deployment-playbook.md`
- `submodules/Freedom-LS/docs/deployment-security-checklist.md`
- `config/settings_prod.py`
