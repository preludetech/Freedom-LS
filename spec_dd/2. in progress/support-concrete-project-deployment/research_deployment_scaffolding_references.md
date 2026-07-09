# Research: reference implementations for FLS's P3 deployment scaffolding

> Scope: one research topic feeding the `support-concrete-project-deployment` idea's **P3**
> (reusable, parameterised deployment scaffolding shipped to the `freedom-ls-concrete-template`
> repo). This surveys reference implementations and extracts concrete patterns + pitfalls; it
> does not design FLS's actual artifacts.

## Top recommendations (read this first)

1. **Copy cookiecutter-django's two-stage `uv sync` caching pattern and its "no migrate in
   entrypoint" discipline — both validated by primary source.** Its production `Dockerfile`
   installs deps in a `python-build-stage` before copying source, and its `start` script runs
   `collectstatic` then `exec gunicorn` — **no `migrate` call anywhere in `entrypoint` or
   `start`**. Migrations are documented as a separate one-off command
   (`docker compose -f docker-compose.production.yml run --rm django python manage.py migrate`).
   This directly validates the downstream idea's decision to run migrations as a one-off deploy
   step, not in the entrypoint (see "One-off migrations vs migrate-on-entrypoint" below).
2. **Don't copy cookiecutter-django's reverse proxy choice.** It defaults to **Traefik**
   (`compose/production/traefik/`), with an `nginx` service kept only to serve media files when
   no cloud storage is configured. Traefik's value proposition (dynamic service discovery,
   multi-app routing, Let's Encrypt DNS challenges at scale) doesn't pay for itself on a
   single-app single-VPS deploy; a plain Caddyfile is simpler to read, audit, and hand to an
   ops-inexperienced maintainer. FLS's Caddy choice is the right one for this topology —
   just don't expect a cookiecutter-django Caddy reference to copy verbatim; it doesn't ship one
   (a "switch to Caddy" issue against cookiecutter-django has been open since 2018 and is
   unresolved as of this research).
3. **The FLS Caddyfile needs almost no directives** beyond `reverse_proxy` to the Gunicorn
   upstream — Caddy sets `X-Forwarded-Proto`, `X-Forwarded-For`, and `X-Forwarded-Host`
   automatically on `reverse_proxy` and (by default) **strips/ignores those headers from
   incoming client requests**, so spoofing isn't possible unless `trusted_proxies` is configured
   to trust an upstream (which the downstream Cloudflare setup needs, for `CF-Connecting-IP`).
   Since WhiteNoise serves static and media is on S3/R2 (per the idea's stack decision), the
   Caddyfile does **not** need `file_server`/`handle_path` blocks for `/static/*` or `/media/*`
   — every third-party Caddy+Django reference found serves static from Caddy directly, which is
   the wrong pattern for FLS given the WhiteNoise decision. Don't copy that part.
4. **Use `docker compose` `profiles:` for the "worker container present-but-disabled" P3
   requirement, not a commented-out block.** This is a first-class Compose feature (stable since
   Compose v2.20.2, incl. `depends_on.required: false` for optional cross-profile deps) built
   exactly for "ship it in the file, off by default, one flag turns it on" — cleaner than asking
   template consumers to uncomment YAML.
5. **Structure the Tailwind/Node stage so it never calls `uv run`.** FLS's current broken
   standalone Dockerfile fails because its `node` build stage runs `npm run tailwind_build`,
   and that npm script itself shells out to `uv run …` — but the `node` stage has no `uv`/Python
   installed. The fix is architectural, not a missing binary: **the Tailwind build must be a
   pure Node-stage command** (call the `tailwindcss` CLI / whatever `npm run tailwind_build`
   ultimately invokes directly, with no `uv run` indirection) so the node stage's only inputs are
   `package.json`, `tailwind.input.css`, the theme's `tailwind.*.css` partials it `@import`s, and
   `ARG FLS_THEME`, and its only output is compiled CSS copied into the Python stage before
   `collectstatic`. This also fixes the second bug the idea calls out: the node stage must
   `COPY` the `tailwind.*.css` partials the entry file imports, not just `tailwind.input.css`.
6. **Ship the `json-file` cap as a per-service Compose block (or a YAML anchor shared across
   services), not a daemon-wide `daemon.json` edit.** A template repo controls the compose file,
   not the host's Docker daemon config — Ansible provisioning a VPS shouldn't need to touch
   `/etc/docker/daemon.json` just to cap logs when the compose file can do it per-service and
   travels with the repo. Confirmed idiomatic syntax below.
7. **Prefer `.env`-only substitution over cookiecutter-style templating for the parameterisation
   layer**, since the FLS template is a plain GitHub "Use this template" repo, not a cookiecutter
   package — there's no templating engine to render `{{ cookiecutter.* }}` placeholders at
   generation time. Site-specific values (domain, DB name, bucket, Sentry DSN) belong in
   `.env`/`.env.example` substitution and Compose interpolation (`${VAR}`, `COMPOSE_PROJECT_NAME`),
   never in `{{ }}`-style template markers baked into committed files — those would be permanently
   broken syntax in a repo nobody renders. See "Parameterisation patterns" below.

## Evidence by area

### cookiecutter-django's production Docker setup

Repo: `cookiecutter/cookiecutter-django`, files under
`{{cookiecutter.project_slug}}/compose/production/`.

- **Stages** (`compose/production/django/Dockerfile`, current `master`):
  1. `client-builder` (conditional, `node:*-bookworm-slim`) — only present when the project
     enables Webpack/Gulp; builds frontend assets, passes cloud-storage env vars to the `npm`
     build so asset URLs can point at the CDN/bucket at build time.
  2. `python-build-stage` (`ghcr.io/astral-sh/uv:python3.14-bookworm-slim`) — installs build
     deps + DB client libs, runs `uv sync` with cache mounts and `UV_COMPILE_BYTECODE=1`, copies
     in the compiled frontend assets from stage 1 if present.
  3. `python-run-stage` (`python:3.14-slim-bookworm`) — final runtime image; creates a
     non-root `django` system user/group, installs only runtime packages (`libpq-dev`,
     `gettext`, `wait-for-it`), copies the venv from stage 2, copies `/entrypoint` and `/start`
     (and Celery variants when enabled) with `chown django`, strips CRLF, `chmod +x`, compiles
     `.mo` translation files, sets `ENTRYPOINT ["/entrypoint"]`.
  - **What to copy:** the three-stage split (frontend → python-build → python-run), the
    non-root user, `uv`'s cache-mount + bytecode-compile flags, `entrypoint` vs `start` split
    (entrypoint = wait for dependencies + `exec "$@"`; start = app-specific startup command).
  - **What's overkill for FLS's single small VPS:** Celery worker/beat/flower conditional
    scripts (the idea's own P0(3) deliberately defers async beyond `ImmediateBackend`), the
    `aws`/cloud-storage build-time asset URL wiring baked into the frontend stage (FLS's
    media-on-R2 story is a runtime `django-storages` setting, not a build-time asset-URL
    rewrite), Traefik's dynamic-routing labels (see recommendation 2).
- **`entrypoint` (verbatim, `compose/production/django/entrypoint`):**
  ```bash
  #!/bin/bash
  set -o errexit
  set -o pipefail
  set -o nounset

  if [ -z "${POSTGRES_USER}" ]; then
      base_postgres_image_default_user='postgres'
      export POSTGRES_USER="${base_postgres_image_default_user}"
  fi
  export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

  wait-for-it "${POSTGRES_HOST}:${POSTGRES_PORT}" -t 30

  >&2 echo 'PostgreSQL is available'

  exec "$@"
  ```
  Pattern: entrypoint only waits for the DB to accept TCP connections, then `exec`s whatever
  `command:`/`CMD` the compose service defines. **It does not run migrations.**
- **`start` behavior:** runs `python manage.py collectstatic --noinput`, optionally a static
  compression pass, then `exec gunicorn …`. **No `migrate` call.** Migrations are documented
  as a separate one-off invocation:
  `docker compose -f docker-compose.production.yml run --rm django python manage.py migrate`
  (cookiecutter-django docs, "Deployment with Docker").
- **Reverse proxy:** Traefik by default (`compose/production/traefik/`), with a `nginx`
  service present only to serve the `production_django_media` volume when no cloud storage
  backend is configured. Media is otherwise served by the configured cloud storage
  (S3/GCS/Azure) directly, not proxied through the app-tier reverse proxy — architecturally the
  same shape as FLS's "WhiteNoise for static, S3/R2 for media" decision.
- **Parameterisation:** `.envs/.production/.django`, `.envs/.production/.postgres`, etc. — env
  files consumed by Compose's `env_file:`, not baked into the Dockerfile. Cookiecutter's own
  `{{ cookiecutter.* }}` variables are resolved once, at `cookiecutter` generation time, to
  produce a plain repo; they are **not** a runtime parameterisation mechanism and don't survive
  into the generated project. This is the load-bearing distinction for FLS (see
  "Parameterisation patterns" below): cookiecutter variables answer "what shape of project do I
  want," `.env` answers "what are this deployment's secrets/domain/bucket."
- **Healthchecks:** not part of the shipped compose file by default; community discussion
  (`cookiecutter-django` GitHub discussions/issues) shows people bolting on either a raw TCP
  probe (`timeout 1 bash -c '</dev/tcp/localhost/5000'`) or `django-health-check` +
  `HEALTHCHECK CMD python manage.py health_check`. FLS's own P1(5) importable liveness/readiness
  endpoints are a **better** pattern than either — cookiecutter-django doesn't ship a
  reference worth copying here; treat this as validation that FLS should ship its own rather
  than search for an upstream one.

### Caddy + Django reference setups

- Caddy's `reverse_proxy` directive sets `X-Forwarded-For`, `X-Forwarded-Proto`, and
  `X-Forwarded-Host` **automatically** — no explicit `header_up` needed for the common case,
  unlike the nginx idiom of hand-setting all three. This is exactly the header P0(1)
  (`SECURE_PROXY_SSL_HEADER`) depends on.
- Caddy **ignores/overwrites** those headers from the incoming client connection by default —
  it will not blindly trust a client-supplied `X-Forwarded-Proto: https`. Only when
  `trusted_proxies` is configured (needed for FLS's Cloudflare-in-front topology, to trust
  `CF-Connecting-IP` from Cloudflare's IP ranges) does Caddy start trusting upstream-supplied
  values. This is the mechanism note the downstream idea's P0(1) "trust caveat" depends on —
  confirmed from Caddy's own docs, not just the idea's prose.
- Two idiomatic minimal Caddyfiles found (Chris Adams' TIL; Filip Stříbný's "Caddy 2 config for
  serving Django… apps"), both of the shape:
  ```
  example.com {
      handle_path /static/* { root * ./staticfiles/; file_server }
      handle_path /media/*  { root * ./media/;       file_server }
      reverse_proxy 127.0.0.1:8000
  }
  ```
  **This is not FLS's shape** — both examples serve static/media from Caddy because neither
  reference project uses WhiteNoise or S3. FLS's Caddyfile should be simpler: essentially just
  `reverse_proxy <gunicorn-upstream>` for the app, since WhiteNoise already serves `/static/*`
  from within the Django/Gunicorn process and media is on R2 (no local media directory to
  `file_server` at all). Don't let a copy-pasted reference Caddyfile reintroduce a static-file
  code path FLS deliberately doesn't need.
- **Common Caddyfile mistakes** surfaced across these references:
  - Forgetting `encode gzip`/`zstd` (Caddy doesn't compress by default the way nginx configs
    often do out of habit) — minor, worth a line in FLS's template.
  - Logging the raw `Authorization` header to `access.log` by default — Stříbný's example
    explicitly filters it out (`fields { request>headers>Authorization delete }`); FLS's
    Caddyfile should scrub auth/session-cookie headers from access logs if it logs to file at
    all (in tension with P0(2)'s "stdout only" logging default — worth flagging as an open
    question, see below).
  - Setting `auto_https off` only makes sense for a plain-HTTP internal/staging path; leaving
    it on (default) is what gives FLS automatic Let's Encrypt HTTPS for free — no manual
    certbot/ACME wiring needed, which is Caddy's whole value proposition over nginx here.

### Multi-stage Dockerfile for uv + Django

Primary sources: `docs.astral.sh/uv/guides/integration/docker/`, `astral-sh/uv-docker-example`
(GitHub), plus the community write-up "Optimizing Django Docker Builds with Astral's `uv`."

- **Canonical two-phase `uv sync` pattern** (this is the load-bearing caching trick):
  ```dockerfile
  FROM python:3.13-slim AS builder
  COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
  WORKDIR /app

  # Phase 1: install deps only — cache-friendly, invalidated only by lockfile/pyproject changes
  RUN --mount=type=cache,target=/root/.cache/uv \
      --mount=type=bind,source=uv.lock,target=uv.lock \
      --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
      uv sync --frozen --no-install-project --no-editable

  # Phase 2: copy source, install the project itself
  COPY . /app
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --no-editable

  FROM python:3.13-slim
  RUN useradd --system --create-home appuser
  COPY --from=builder --chown=appuser:appuser /app /app
  ENV PATH="/app/.venv/bin:$PATH"
  USER appuser
  ```
  - `--frozen` (not `--locked`): use the committed `uv.lock` exactly as-is without re-resolving
    or erroring on drift — appropriate for a Docker build where you want deterministic, fast
    installs from a lockfile the CI/dev workflow already validated, and *required* in
    submodule/workspace layouts where `uv` can't fully verify lock freshness without every
    workspace member's `pyproject.toml` present (FLS's submodule consumption is exactly this
    shape: `[tool.uv.sources]` pointing at a git submodule).
  - `--no-install-project` on the deps-only pass, then a full `uv sync --frozen` after `COPY .`,
    is what makes the dependency layer cacheable independent of source changes — changing
    application code doesn't bust the (slow) dependency-install layer.
  - `--no-editable` on the final install removes the source-code dependency from the synced
    venv, so stage 2 can copy **only** `/app/.venv` into the runtime stage without carrying
    build tooling — keeps the final image slim.
  - Cache mounts (`--mount=type=cache,target=...uv...`) persist uv's download/wheel cache across
    builds on the same builder without baking it into any image layer.
  - Non-root user in the runtime stage, `chown` on copy — matches cookiecutter-django's `django`
    system user pattern.
- **`.dockerignore` essentials** (from the uv Docker guide): exclude `.venv` — a locally-built
  venv is platform-specific and must never leak into the image (the image's own `uv sync` builds
  its own). Standard additions for FLS: `.git`, `__pycache__`, `*.pyc`, `node_modules`,
  `staticfiles/` (if collected locally), `.env*` (never bake secrets into an image layer),
  `spec_dd/`, test artifacts, `*.sqlite3`.
- **`collectstatic` at build vs run:** the community write-up runs `collectstatic` **at build
  time**, inside the builder stage, with `DEBUG=False ./manage.py collectstatic --noinput`.
  cookiecutter-django instead runs it in the `start` script at **container start**. Trade-off:
  build-time collectstatic means the compiled static bundle for a given image tag is fixed and
  reproducible (good for GHCR SHA-tagged images — the artifact is fully baked), but it requires
  all `STATIC_URL`/storage settings resolvable at build time (no secrets needed for WhiteNoise,
  since it just writes to local disk — this is fine for FLS). Run-time collectstatic (cookiecutter-django's
  choice) is simpler to reason about (one code path, same as local `runserver` prep) but adds a
  few seconds to every container start and means two containers built from the same image could
  theoretically diverge if `collectstatic` behavior is non-deterministic (it shouldn't be).
  **Given FLS uses WhiteNoise (bundles static into the image/served-from-disk, not uploaded to a
  CDN at build time), build-time `collectstatic` is the better fit** — it keeps the runtime
  container simpler and makes the pushed GHCR image fully self-contained and reproducible for
  the "SHA-tagged image is the deploy unit" CI story. Run collectstatic at build time.
- **Node/Tailwind stage feeding the Python stage — the gotcha FLS must fix.** None of the primary
  uv-Docker sources address a mixed Node+Python multi-stage build directly (the uv guide is
  Python-only), but the general Docker multi-stage principle applies cleanly: **each stage's
  `FROM` image only has what that stage's tooling needs; nothing crosses stages except explicit
  `COPY --from=`.** FLS's current standalone Dockerfile breaks this because its `node` stage's
  `npm run tailwind_build` script is written to shell out to `uv run …` — an assumption that only
  holds when run on a dev machine with `uv` on `PATH`, not inside a `node:*-slim` build stage.
  Two structurally sound fixes (either works; second is closer to cookiecutter-django's shape):
  1. **Rewrite `tailwind_build` to be pure-Node** (call the Tailwind CLI binary directly, no
     `uv run` wrapper) so the `node` stage is self-sufficient — matches cookiecutter-django's
     `client-builder` stage, which never touches Python.
  2. If the build genuinely needs a Python step (e.g. a management command that generates
     Tailwind class lists from Django templates/content), split it into its own **python-build**
     stage that runs *before* the node stage, `COPY --from=python-build` its output artifact into
     the `node` stage as an input file, and let `node` do only `npm`/`tailwindcss` work.
  Either way, the node stage must also `COPY` every `tailwind.*.css` partial the theme's
  `tailwind.input.css` `@import`s (not just the entry file) and take `ARG FLS_THEME` so the
  theme is selectable at build time — both already identified as missing in the idea's P2(7).

### Docker Compose logging caps

Primary source: Docker Engine docs, `json-file` logging driver page.

- **Per-service (what FLS's compose should use):**
  ```yaml
  services:
    django:
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "3"
  ```
  `max-size` accepts `k`/`m`/`g` suffixes; default is `-1` (unbounded) if unset — confirming the
  idea's framing that this is a **required**, not cosmetic, addition once P0(2) moves logging to
  stdout (unbounded stdout capture under `/var/lib/docker/containers/*/*-json.log` is exactly
  the "fills the host disk" failure mode being guarded against). `max-file` **only takes effect
  when `max-size` is also set** — both must be present together, not either alone.
  - Use a Compose **YAML anchor** (`x-logging: &default-logging`) to define the cap once and
    apply it to every service (`django`, `caddy`, `postgres`, `worker`) rather than repeating the
    block per service — keeps the "required per service" rule enforceable without copy-paste
    drift when a new service is added later.
- **Daemon-wide alternative:** `/etc/docker/daemon.json` → `{"log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}}`, applied host-wide, requires a Docker daemon
  restart, and only affects **newly created** containers. **Not the right mechanism for a
  template repo** — it lives outside the repo's version control, requires an Ansible task (or
  manual step) on every VPS the template is deployed to, and silently stops applying if someone
  reprovisions a host without also running that Ansible task. The per-service Compose block is
  self-contained in the artifact FLS ships and travels with the repo — confirms recommendation 6
  above.

### Parameterisation patterns for templates

- **Cookiecutter's variable-substitution model** (`{{ cookiecutter.project_slug }}` etc.) is
  resolved **once, at generation time**, by the `cookiecutter` CLI reading `cookiecutter.json`
  and rendering every `{{ }}` token in every file/filename before the new repo is ever created —
  the tokens do not exist in the generated repo at all. This requires a templating engine
  (Jinja2 under the hood) in the loop between "template" and "concrete project."
- **FLS's template repo is a plain GitHub "Use this template" repo** (confirmed from the idea:
  synced via `/fls:sdd:update_template_repo`, not a `cookiecutter generate` step) — there is no
  render step, so any `{{ cookiecutter.* }}`-style token left in a committed file would be
  **permanently broken syntax** in every generated project (nothing ever resolves it). This
  makes cookiecutter's variable-templating model a poor fit for FLS's artifacts, confirming
  recommendation 7: FLS must use **runtime substitution**, not generation-time templating:
  - `.env.example` → copied to `.env` and hand-edited (domain, `SECRET_KEY`, DB name, R2 bucket,
    Sentry DSN, etc.) — values are read at container start via `env_file:`/`environment:` in
    Compose, exactly like cookiecutter-django's `.envs/.production/.django` (same runtime
    mechanism cookiecutter-django *also* uses for secrets — cookiecutter's templating only
    handles structural/project-shape choices like "which cloud provider," never live secrets).
  - Compose `${VAR}` interpolation + `COMPOSE_PROJECT_NAME` + `--env-file` for anything Compose
    itself needs to see (container/network/volume naming, so the same compose file can run
    staging and prod on one host with isolated resources — already in the idea's P3 list).
  - The **Caddyfile's domain** is naturally an env-driven value too (`{$DOMAIN}` Caddyfile
    placeholder syntax, populated from the environment Caddy's own process sees) — Caddy
    natively supports `{$ENV_VAR}` substitution in Caddyfiles, so the domain doesn't need to be
    hand-edited in the file itself; confirm this is the same `.env` the compose file already
    populates so there's exactly one place to fill in per deployment, not two.
  - Anywhere the template needs **structural** choices (not secrets) that genuinely differ across
    concrete projects — e.g. "does this project enable the worker container" — a Compose
    `profiles:`/commented-block + a short bootstrap doc step is the right tool, not a templating
    engine (see recommendation 4).

### GHCR SHA-tagged build-and-push CI (brief)

- Canonical shape: `docker/login-action` (auth to `ghcr.io` using `github.actor` +
  `GITHUB_TOKEN`, no separate PAT needed for same-repo GHCR pushes) → `docker/metadata-action`
  (derive tags, typically `type=sha` for an immutable per-commit tag plus `type=ref,event=branch`
  or a `latest`/environment tag for convenience) → `docker/build-push-action` (build using
  Buildx, `push: true`, tags from the metadata step, `cache-from`/`cache-to` against the GHCR
  registry cache to speed up repeat builds). This is the standard, low-risk shape referenced
  across every current tutorial found; FLS's P3 CI template should follow it directly rather
  than inventing a bespoke workflow.
- SHA-tagging matters for FLS specifically because it makes "the deployed image" a durable,
  addressable artifact independent of a mutable `latest`/branch tag — which is what makes a
  rollback ("redeploy the previous SHA-tagged image") a real, safe operation instead of "hope the
  registry still has yesterday's `latest`."

### One-off migrations vs migrate-on-entrypoint — validated

The downstream idea's decision to run migrations as a **one-off deploy step**, not inside
`entrypoint`/`start`, matches cookiecutter-django's actual (verified from source, not just docs)
behavior: neither its `entrypoint` nor its `start` script calls `manage.py migrate` anywhere;
the docs prescribe a separate `docker compose run --rm django python manage.py migrate` command.
Reasons this is the safer default, consistent with what both the primary source and general
container-deploy practice support:

- **Concurrency safety.** If a compose `up`/rolling-restart ever starts more than one
  app-container replica (even transiently, e.g. `docker compose up --scale django=2` during a
  manual debug session, or a future move to N replicas), migrate-on-entrypoint means every
  replica races to run migrations concurrently against the same DB — Django's migration
  framework doesn't guard against concurrent runners the way some frameworks' migration locks
  do. A one-off step runs exactly once, explicitly, before any replica starts.
- **Failure isolation.** A failed migration inside `entrypoint` kills the app container's boot
  (or worse, crash-loops it under a restart policy) with the failure interleaved into the same
  logs/exit code as "app failed to start" — harder to triage than a distinct, previous pipeline
  step that fails loudly on its own with `run --rm` and doesn't touch the running (old) app
  container at all if it fails.
- **Rollback-compatible.** A one-off migration step composes cleanly with the SHA-tagged-image
  rollback story above: "deploy = migrate (one-off) → swap image tag → healthcheck → (rollback:
  swap image tag back)" is a clean linear pipeline; migrate-on-entrypoint entangles "did the new
  code start" with "did the new schema apply," which is exactly the ambiguity a rollback
  procedure needs to avoid.
- This validates — it does not just repeat — the downstream idea's decision; no reference
  reviewed here runs migrate-on-entrypoint as the default. Treat it as confirmed practice, not
  merely FLS's preference.

## Checklist of concrete recommendations + footguns for FLS's P3 artifacts

**Dockerfile**
- [ ] Three (or more) explicit stages: `node`/frontend → `python-build` → `python-run`, each
  `FROM` only what that stage's tooling needs.
- [ ] `node` stage's `tailwind_build` script must not invoke `uv run` or any Python tool; make it
  pure-Node, or split a genuinely-needed Python step into its own earlier stage and feed its
  output into the `node` stage via `COPY --from=`.
- [ ] `node` stage takes `ARG FLS_THEME` and `COPY`s every `tailwind.*.css` partial the theme's
  `tailwind.input.css` `@import`s, not just the entry file.
- [ ] `python-build` stage: two-phase `uv sync --frozen` (`--no-install-project` before `COPY .`,
  full sync after) with `--mount=type=cache,target=...uv...`, and `--no-editable` on the final
  sync so the runtime stage only needs `/app/.venv`.
- [ ] Install `freedom_ls` from the submodule path via `[tool.uv.sources]`, and require
  `uv.lock` (reproducible builds) rather than resolving from `pyproject.toml` at build time —
  the idea explicitly flags the current standalone image's `pyproject.toml`-only install as a
  gap to fix.
- [ ] Run `collectstatic` at **build time** (matches WhiteNoise's local-disk serving model, keeps
  the GHCR image self-contained/reproducible per SHA tag) — not in the entrypoint.
- [ ] Non-root runtime user, `chown` on the final `COPY --from=`.
- [ ] `.dockerignore`: `.venv`, `.git`, `__pycache__`/`*.pyc`, `node_modules`, `staticfiles/`,
  any `.env*`, `spec_dd/`, test/coverage artifacts.

**docker-compose.yml**
- [ ] Named volume for Postgres data — never a bind mount (already flagged elsewhere in the
  idea as a P2 fix for the current shipped compose).
- [ ] `x-logging: &default-logging` anchor with `driver: json-file`, `max-size` **and**
  `max-file` both set (max-file alone is a no-op), applied to every service — required, not
  optional, and lives in the compose file itself (not `daemon.json`) so it travels with the repo.
- [ ] `worker` service (P0(3)'s opt-in `db_worker`) gated behind Compose `profiles:` (or
  `depends_on: { ..., required: false }` if it has an optional dependency), not commented-out
  YAML — one env/flag flips it on.
- [ ] Healthchecks target the P1(5) readiness endpoint via HTTPS or with
  `X-Forwarded-Proto: https` set explicitly, so `SECURE_SSL_REDIRECT` doesn't 301 the probe and
  falsely mark the container unhealthy (idea's own P1(5) gotcha — restated here as a compose-file
  checklist item, since this is where it actually gets implemented).
- [ ] `COMPOSE_PROJECT_NAME` + `--env-file` support so the same file runs staging and prod with
  isolated containers/networks/volumes on one host.
- [ ] No `migrate` in any entrypoint/start/command path — migrations are a separate
  `docker compose run --rm django python manage.py migrate` step in the deploy pipeline/docs.

**Caddyfile**
- [ ] `reverse_proxy` only — no `file_server`/`handle_path` for `/static/*` or `/media/*`
  (WhiteNoise + R2 already cover both; copying a reference Caddyfile that serves them from Caddy
  reintroduces a code path FLS doesn't need).
- [ ] Rely on Caddy's automatic `X-Forwarded-Proto`/`-For`/`-Host` on `reverse_proxy` — don't
  hand-set headers nginx-style.
- [ ] `trusted_proxies` configured for the Cloudflare-in-front topology (per the downstream
  Cloudflare research this idea must not contradict), so `CF-Connecting-IP` is trusted and
  client IP isn't lost.
- [ ] Domain parameterised via Caddy's native `{$DOMAIN}` env-substitution syntax, reading the
  same `.env` the compose file populates — one place to edit per deployment.
- [ ] Leave `auto_https` at its default (on) — that's the entire reason to use Caddy over nginx
  here; don't let a "local/staging" variant of the Caddyfile accidentally ship with
  `auto_https off` in prod.
- [ ] If Caddy logs to a file at all, scrub `Authorization`/session-cookie headers from the log
  format — flagged as an open question below given P0(2)'s stdout-only logging default.

**CI (GHCR)**
- [ ] `docker/login-action` + `docker/metadata-action` (SHA tag) + `docker/build-push-action`
  against Buildx, with registry-backed layer caching — standard shape, no need to invent one.
- [ ] SHA tag is the actual deploy/rollback unit — the deploy pipeline should reference the
  built image by SHA, not `latest`.

## Open questions for the human

- **Caddy access-log destination vs P0(2)'s "stdout only" logging default.** P0(2) moves
  *Django's* logs to stdout to be container-native; does the same rule apply to *Caddy's* access
  log, or is a scrubbed file log (as in the Stříbný reference, with `Authorization` redacted)
  acceptable for Caddy specifically since it's a separate container/log stream from the app?
  Worth a one-line decision in the P3 spec so the Caddyfile template doesn't silently pick one.
- **Build-time vs run-time `collectstatic`.** This research recommends build-time (matches
  WhiteNoise + reproducible-SHA-image goals), diverging from cookiecutter-django's run-time
  default. Confirm this is acceptable before it's baked into the P3 Dockerfile template — the
  main cost is that changing a theme's static assets requires a rebuild+redeploy rather than a
  container restart, which the idea's `ARG FLS_THEME` build-time model already implies anyway.
- **Compose `profiles:` vs a documented env-flag pattern for the worker container.** `profiles:`
  is the more idiomatic Compose primitive, but if FLS's existing tooling
  (`/fls:sdd:update_template_repo`, bootstrap docs) already has conventions for "flip this on"
  via `.env` flags elsewhere, confirm `profiles:` composes with that convention rather than
  introducing a second on/off mechanism style in the same template.

## References

- cookiecutter-django (GitHub, primary source): `compose/production/django/Dockerfile`,
  `compose/production/django/entrypoint`, `compose/production/django/start` —
  https://github.com/cookiecutter/cookiecutter-django/tree/master/%7B%7Bcookiecutter.project_slug%7D%7D/compose/production
- cookiecutter-django docs, "Deployment with Docker" (migrate-as-one-off-command, `.envs/`
  parameterisation, media-serving fallback) —
  https://cookiecutter-django.readthedocs.io/en/latest/deployment-with-docker.html
- cookiecutter-django "Switch to Caddy on Docker" issue (open, unresolved — confirms no shipped
  Caddy reference) — https://github.com/cookiecutter/cookiecutter-django/issues/1132
- Caddy docs, `reverse_proxy` directive (automatic `X-Forwarded-*` headers, `trusted_proxies`) —
  https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy docs, reverse proxy quick-start —
  https://caddyserver.com/docs/quick-starts/reverse-proxy
- Filip Stříbný, "Caddy 2 config for serving Django, FastAPI and other web apps" (example
  Caddyfile, log filtering, HSTS) — https://stribny.name/posts/caddy-config/
- Chris Adams, "TIL: Using Caddy with Django apps instead of Nginx" (minimal Caddyfile,
  static/media handling) —
  https://rtl.chrisadams.me.uk/2023/01/til-using-caddy-with-django-apps-instead-of-nginx/
- Astral, "Using uv in Docker" (multi-stage pattern, `--frozen`, cache mounts, `.dockerignore`) —
  https://docs.astral.sh/uv/guides/integration/docker/
- `astral-sh/uv-docker-example` (GitHub) — Dockerfile / multistage.Dockerfile / standalone.Dockerfile —
  https://github.com/astral-sh/uv-docker-example
- Rob (cogit8.org), "Optimizing Django Docker Builds with Astral's `uv`" (build-time
  `collectstatic`, two-stage `uv sync`) —
  https://rob.cogit8.org/posts/optimizing-django-docker-builds-with-astrals-uv/
- Docker Engine docs, JSON File logging driver (`max-size`/`max-file` per-container and
  daemon-wide syntax, defaults, `max-file` requiring `max-size`) —
  https://docs.docker.com/engine/logging/drivers/json-file/
- Docker Compose docs, "Using profiles with Compose" —
  https://docs.docker.com/compose/how-tos/profiles/
- Nick Janetakis, "Optional depends_on with Docker Compose v2.20.2+" (`depends_on.required:
  false` alongside `profiles:`) —
  https://nickjanetakis.com/blog/optional-depends-on-with-docker-compose-v2-20-2
- GitHub Docs, "Publishing Docker images" (GHCR login-action/metadata-action/build-push-action
  shape) — https://docs.github.com/en/actions/use-cases-and-examples/publishing-packages/publishing-docker-images
- Idea context (this worktree):
  `spec_dd/2. in progress/support-concrete-project-deployment/idea.md` (P3 section, "Reusable-template
  requirement", P0(1)/(2)/(3) settings context, P1(5) health endpoint gotcha, P2(7) broken
  standalone Dockerfile description).

---
status: ok
