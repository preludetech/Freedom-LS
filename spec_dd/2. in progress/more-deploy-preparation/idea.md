# Idea: more deploy preparation

Small, high-leverage deploy-readiness fixes on the FLS side, discovered while wiring up
the concrete-project deployment. Two threads: make a misconfigured Sentry **release** loud
and bake it into the image at build time, and close the app↔infra `.env` gaps the separate
Ansible Infrastructure repo depends on. Framing throughout: **efficiency and ease, no scope
creep** — prefer the smallest change that removes a real footgun.

Research backing: [`research_sentry_release.md`](./research_sentry_release.md),
[`research_app_infra_coupling.md`](./research_app_infra_coupling.md).

## Problem

1. **A blank `SENTRY_RELEASE` while `SENTRY_DSN` is set is invisible.** `init_sentry()`
   passes `release=None` and Sentry keeps working, but every event is untagged — regressions
   can't be tied to a deploy and "resolved in next release" silently degrades. We want to
   see that misconfiguration quickly.
2. **The release identifier is a runtime env var, not part of the image.** It belongs to the
   image: baked at build time it is guaranteed identical across `web` and `db_worker` (same
   image), whereas a per-service runtime env var is free to drift and split one deploy's
   events across two release tags.
3. **The app↔infra coupling has `.env` gaps.** The Ansible Infrastructure repo's `app_env`
   role fills each stack's `.env` from vault using **`.env.example` as the canonical key
   list**. Three prod settings are read by FLS but missing from `.env.example` — most
   importantly `WEBHOOK_ENCRYPTION_SALT`, which in production **silently falls back to a
   hardcoded insecure dev salt** (unlike `SECRET_KEY`, which hard-fails).

## Scope (this FLS repo)

- **Sentry release warning (decided: Warning system check).** Add a Django system check
  (`Warning`, not `deploy=True`, not fail-fast) in a new `freedom_ls/deployment/checks.py`,
  registered in `deployment/apps.py`'s `ready()`, that fires when `SENTRY_DSN` is set **and**
  `SENTRY_RELEASE` is blank. Modelled on the existing `course_access` W001 conditional-warning
  precedent. Fires automatically on the deploy pipeline's `manage.py check`/`migrate` step and
  in CI; never blocks a deploy; silenceable per-deployment via `SILENCED_SYSTEM_CHECKS`.
  `AppSettings` already normalises blank→`None`, so the check just tests falsiness.
- **`.env.example` gap closures (for the infra `app_env` key list):**
  - `WEBHOOK_ENCRYPTION_SALT` — add it (marked secret) **and make production fail-fast when
    unset** (decided), matching the `SECRET_KEY` treatment via the `settings_defaults` pattern,
    so the insecure-dev-salt fallback can never silently reach prod. This is the one gap with
    real security bite.
  - `DJANGO_ADMIN_URL` — add (config, safe default `admin/`); documentation-parity fix.
  - `HSTS_SECONDS` / `HSTS_INCLUDE_SUBDOMAINS` / `HSTS_PRELOAD` — add (config, safe defaults
    already in code); documentation-parity fix so `.env.example` and the security checklist
    stop drifting.

## Handoff to the template repo (via `/update_template_repo`, not this repo's code)

These land in `freedom-ls-concrete-template`, delivered through the existing SDD template-repo
sync step — recorded here so nothing is lost:

- **Bake `SENTRY_RELEASE` at build time.** `ARG SENTRY_RELEASE` / `ENV SENTRY_RELEASE=…` in
  the Dockerfile's final runtime stage, sourced from `github.sha` (full SHA) via
  `docker/build-push-action` `build-args:`. Value convention: **raw full git SHA** for V1 (no
  new semver scheme). Open sub-decision deferred to spec/plan: whether to make the GHCR image
  tag byte-identical to the release string (`docker/metadata-action`'s default `type=sha` is
  `sha-<short>`, not the full SHA) or accept loose same-commit correspondence — both fine.
- **Pin a stable per-stack Postgres `container_name`** in the template's Compose file
  (`lms-staging-db` / `lms-prod-db`) matching the infra inventory's `pg_container_name` var,
  which the `backups` role `docker exec`s.
- **Mirror the `.env.example` additions** above into the template's copy once they land here.

## Out of scope / already handled (no action)

- **`sentry-cli` release finalize / commit-association / deploy markers** — a documented
  *future* step only. Commit association needs a new `SENTRY_AUTH_TOKEN` secret + a Sentry↔GitHub
  integration; source maps are irrelevant to a server-rendered Django/HTMX app. Just passing the
  `release` string already solves the stated problem for V1.
- **`SENTRY_ENVIRONMENT`** has an analogous "set-it-whenever-DSN-is-set" note but is **not** part
  of this idea — don't let the check quietly grow to cover it.
- **Health probes, `db_worker` + `prune_db_task_results`, backup restore-drill query
  (`SELECT count(*) FROM django_migrations`)** — all already shipped/valid; template-repo/infra
  concerns, not new app code.

## Notes

- Keep this deliberately small. The only behavioural change to running code is the fail-fast on
  a missing `WEBHOOK_ENCRYPTION_SALT` in production; everything else is a check, a doc/`.env`
  parity fix, or a template-repo handoff.
