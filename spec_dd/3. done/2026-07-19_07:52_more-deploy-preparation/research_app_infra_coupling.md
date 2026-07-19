# Research: app-repo obligations from the Infrastructure (Ansible) repo plan

> Source plan: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/spec_dd/next/deployment/infra-repo/2. plan.md`
> Scope: check the four app-repo obligations that plan states against what this FLS repo
> and its `.env.example` currently ship. Goal is a short, high-signal gap list — not an
> exhaustive audit. Maintainer wants efficiency, not scope creep.

## 1. `.env.example` completeness

Read: `.env.example:1-84`, `config/settings_base.py`, `config/settings_prod.py`,
`docs/deployment-security-checklist.md:129-179`.

**Already covered in `.env.example`** (verified against `settings_prod.py` reads): `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE`, `DB_CONN_MAX_AGE`, `SECRET_KEY`,
`EMAIL_BACKEND`/`EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_USE_TLS`/`EMAIL_HOST_USER`/
`EMAIL_HOST_PASSWORD`/`DEFAULT_FROM_EMAIL`, `HOST_DOMAIN`, `POSTHOG_*`, `SENTRY_*`, `AWS_*`
(R2 media). These were the subject of an earlier round of gap-fixing (see
`spec_dd/3. done/2026-07-11_16:01_support-concrete-project-deployment-external-requirements-config/`
and `.../2026-07-17_09:57_support-concrete-project-deployment-1-prod-settings/`) and are in
good shape.

**Genuine gaps — settings reads with no `.env.example` entry:**

- **`WEBHOOK_ENCRYPTION_SALT` — highest-signal gap.** Read at `config/settings_base.py:443`
  (`_webhook_salt = os.environ.get("WEBHOOK_ENCRYPTION_SALT", "")`), assigned to `SALT_KEY`
  at `config/settings_base.py:450`. `settings_prod.py` does `from .settings_base import *`
  (line 6) and never re-derives `SALT_KEY`, so **an unset var in production silently falls
  back to the hardcoded dev salt** (`config/settings_base.py:444-449`) rather than failing
  loud — unlike `SECRET_KEY`, which does hard-fail via `fls_defaults.require_secret_key()`
  (`settings_prod.py:55`). This directly weakens the webhook-secret Fernet encryption
  described in `docs/product/webhooks.md:44` and is exactly the kind of key the infra
  `app_env` role needs to know about to fill from vault per stack. Not in `.env.example` today.
- **`DJANGO_ADMIN_URL`** — read at `config/urls.py:31`, documented in
  `docs/deployment-security-checklist.md:160` and `docs/product/admin-interface.md:9`, but
  absent from `.env.example`. Low risk (has a safe default, `admin/`) but it's exactly the
  kind of per-stack config value `app_env` renders, so it belongs in the key list.
- **`HSTS_SECONDS` / `HSTS_INCLUDE_SUBDOMAINS` / `HSTS_PRELOAD`** — read at
  `config/settings_prod.py:28-32`, fully documented with a rollout plan in
  `docs/deployment-security-checklist.md:38-72`, but absent from `.env.example`. Safe
  defaults exist (`3600`/`False`/`False`), so this isn't a functional break — but per obligation
  #2 (`.env.example` is the app repo's canonical "which keys does prod need" list for the
  infra `app_env` role), the shape file and the checklist doc have drifted apart.

**Not a gap (noted for completeness, no action needed):**
- `LEGAL_DOCS_MANIFEST_PATH` (`config/settings_base.py:296`) — an in-image filesystem path
  baked at build time (`manage.py build_legal_docs_manifest`), not a per-stack secret/config
  value `app_env` would render from vault. Correctly out of scope for `.env.example`.
- `FLS_THEME` (`config/settings_base.py:33`) — explicitly documented
  (`docs/product/deployment.md:64`) as a Docker **build-time** ARG, "cannot be changed at
  runtime without a rebuild." Not a `.env`/vault-fill concern.

## 2. Postgres `container_name` convention

No `docker-compose.yml` exists anywhere in this repo (only `dev_db/docker-compose.yaml`, a
local Postgres-only dev fixture, unrelated to the prod stack). This confirms the infra plan's
own framing: production Compose (and therefore `container_name`) is owned entirely by the
**template repo** (`freedom-ls-concrete-template`), not this FLS repo — see
`docs/product/deployment.md:7,15,111-117` ("A concrete project deploys from the template
repo's Caddy/Docker Compose scaffolding").

**Template-repo action item (not this repo's work):** pin a stable, per-stack
`container_name` in the template's Compose file — e.g. `lms-staging-db` / `lms-prod-db` —
matching the `pg_container_name` value the infra plan's `group_vars/{staging,prod}/vars.yml`
records (`Task 1.2` of the infra plan, `2. plan.md:126-129`). This is purely a naming
handshake between two files neither of which lives in this repo; nothing to design here.

## 3. Backup restore verification (`SELECT count(*) FROM django_migrations;`)

Valid as a smoke check. `django_migrations` is a Django-core bookkeeping table created by the
migration executor (`MigrationRecorder`) the first time `manage.py migrate` runs against any
Django project with migrations enabled — it exists regardless of which apps are installed, so
the query works unmodified for this app. It proves the restored database round-trips through
`pg_dump`/`pg_restore` correctly and has *some* schema state; it deliberately does not (and per
the infra plan is not meant to) prove application health — that's a separate deploy-time smoke
test concern, consistent with `docs/product/deployment.md:57` ("Applied-migrations are
deliberately not part of readiness — that check belongs in a deploy-time smoke test, not a
polled probe"). **No app-side change needed.**

## 4. Health probes + required processes

Already shipped and already documented — confirmed in code, not just docs:
- `/health/liveness/` and `/health/readiness/`: `freedom_ls.health` is installed
  (`config/settings_base.py:103`) and mounted at `config/urls.py:46`
  (`path("health/", include("freedom_ls.health.urls"))`).
- `db_worker` + `prune_db_task_results`: `TASKS = fls_defaults.DATABASE_TASKS` is the
  production default (`config/settings_prod.py:81`), and both processes are documented as
  required in `docs/product/deployment.md:41-49`. The upgrade notes for the durable-backend
  change explicitly record "The worker container ships enabled by default in the deployment
  template repo" (`spec_dd/3. done/2026-07-17_22:28_support-concrete-project-deployment-3-background-tasks/upgrade_notes.md:51`) —
  i.e. wiring these into the Compose stack/systemd is already a template-repo concern, already done there.

**No new app-code work here** — this obligation is fully satisfied by what already exists;
running the processes is a template-repo/infra deployment-scaffolding concern, not a gap.

## 5. Net list

**(a) FLS-repo actions (small, concrete — this repo):**
- Add `WEBHOOK_ENCRYPTION_SALT` to `.env.example`, marked secret, with a one-line comment
  that an unset value in production silently falls back to an insecure hardcoded salt (this
  is the one gap with real security bite — worth a short comment, not just a bare var).
- Add `DJANGO_ADMIN_URL` to `.env.example` (config, optional, default `admin/`).
- Add `HSTS_SECONDS` / `HSTS_INCLUDE_SUBDOMAINS` / `HSTS_PRELOAD` to `.env.example` (config,
  safe defaults already exist in code — this is a shape/documentation-parity fix, not a
  functional bug).

**(b) Template-repo actions (not this repo, recorded for the handoff):**
- Pin a stable per-stack Postgres `container_name` in the template's Compose file
  (`lms-staging-db` / `lms-prod-db` convention) matching the infra inventory's
  `pg_container_name` var.
- Mirror the same `.env.example` additions from (a) into the template repo's copy once they
  land here, via the existing `/fls:sdd:update_template_repo` propagation path — not new
  mechanism, just the standard sync this project already uses for settings drift
  (see `spec_dd/2. in progress/support-concrete-project-deployment/idea.md:34-53`).

**(c) Infra-repo/inventory actions (not this repo, FYI only):**
- Record the agreed `pg_container_name` per stack in `group_vars/{staging,prod}/vars.yml`
  once the template repo's Compose names are settled (already planned in the infra plan's
  Task 1.2 — no new ask, just needs the template-repo name to exist first).
- Once `WEBHOOK_ENCRYPTION_SALT`/`DJANGO_ADMIN_URL`/`HSTS_*` are added to `.env.example`
  (item a), the infra `app_env` role's key list should include them — this falls out
  automatically from `.env.example` being the source of truth per the infra plan's own
  design ("the app repo owns which keys its settings expect"); no separate infra-side
  discovery step needed.

**(d) Already done / no action (the majority of the surface area):**
- `DB_*`, `SECRET_KEY`, `HOST_DOMAIN`, `EMAIL_*`, `SENTRY_*`, `POSTHOG_*`, `AWS_*` (R2) are
  all already correctly declared in `.env.example`.
- Backup restore verification query is valid as-is — no app change needed.
- Health liveness/readiness endpoints are shipped and wired.
- `db_worker` + `prune_db_task_results` are documented required processes and already run by
  default in the template repo's Compose stack (per existing upgrade notes) — running them is
  not new work for either repo.
- No `docker-compose.yml` exists in this repo, confirming `container_name` genuinely belongs
  to the template repo — nothing to build or decide here.
- `LEGAL_DOCS_MANIFEST_PATH` and `FLS_THEME` are correctly *not* `.env.example`/vault-fill
  concerns (build-time / image-baked, not per-stack secrets).

---

status: ok
