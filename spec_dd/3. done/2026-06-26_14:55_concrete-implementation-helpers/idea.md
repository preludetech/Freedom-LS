# Concrete Implementation Helpers

FLS is designed to be included in other Django projects. A "concrete implementation" is a fresh
Django project that includes FLS as a git submodule (read-only reference), installs it editably via
uv, wires up the FLS Claude plugin, and adds its own theme, config, and optionally its own Django
apps. We need to make creating and maintaining these implementations easy.

In the simplest case a concrete implementation is just FLS plus the concrete project's configuration
(its own theme, icons, password rules, settings). In more complicated cases it has its own set of
Django apps too. Either way, Claude must **never** edit the `freedom_ls` submodule — it is there as a
reference only.

> **Supersedes `make-concrete-implementation-easy`.** That sibling in-progress spec covers the same
> ground; it should be archived/dropped in favour of this one to avoid duplicate work.

## Scope

In scope for this spec:

1. **Define the separate template repo** — its structure and contents (the repo itself lives outside
   this repo, but this spec specifies what goes in it).
2. **FLS-side helpers** that the template repo and concrete implementations rely on — primarily the
   `fls:init` and `concrete/update_fls` plugin commands, plus the how-to docs.
3. **A safe, structured FLS-update flow**, including a new per-spec upgrade-notes artifact authored
   as part of FLS's own spec-completion workflow.
4. **Caprover / dead-deployment cleanup** (concrete list below).

Out of scope (explicitly future work — do **not** build now):

- Deployment / infrastructure helpers (CI/CD, Caddy, Ansible, media storage, etc.). See the
  `deployment-phase-1` spec as one example of where this is heading. The template repo should leave
  room for an `env/stage` and `env/prod` branch story later, but we are not building it here.
- **Do not** research, reference, or build on the current Caprover deployment setup — it is not in
  use and never will be. We only remove it (see cleanup section).

## The template repo (separate repo)

**Scaffolding mechanism: GitHub Template Repository.** "Use this template" generates a new repo with
the submodule included (GitHub has supported submodules in template generation since 2020). No
external tooling required; `fls:init` handles post-generation customisation. The chief downside —
the generated repo starts with whatever FLS commit the template pinned — is mitigated by an
auto-update workflow on the template repo (see below). cookiecutter was rejected (incomplete
submodule support, adds a tool dependency for a one-time op); clone+script was rejected as more
manual.

The template repo should ship:

- `submodules/Freedom-LS` as an initialised submodule pinned to a recent FLS commit, with the FLS
  Claude plugin available from inside it.
- `pyproject.toml` with `freedom_ls = { path = "submodules/Freedom-LS", editable = true }` and a
  committed `uv.lock`.
- A fresh Django `config/` project pre-wired with the FLS settings (the settings/urls wiring that is
  currently left as TODOs in `docs/how tos/incorperate into another project.md` must be completed
  and reflected here).
- Tailwind setup (`package.json`, `tailwind.input.css` template, themes dir).
- Wrapper-script stubs and `.claude/` setup (handled/finished by `fls:init`).
- A project-level `.claude/settings.json` with `Write(submodules/**)` / `Edit(submodules/**)` deny
  rules, plus a `CLAUDE.md` "do not edit the FLS submodule" instruction — belt-and-suspenders so the
  submodule is read-only even before `fls:init` runs.
- A README documenting the post-generation steps: `git clone --recurse-submodules`, `uv sync`,
  `npm i && npm run tailwind_build`, then `./claude.sh /fls:init`.
- An auto-update workflow (e.g. Dependabot `gitsubmodule` or a scheduled action) that keeps the
  template's FLS pointer current so new projects don't start badly stale.

Design principle from the research: **keep the template thin.** Anything reusable belongs in FLS
proper, not in the template — the more logic lives in the template, the harder downstream sync
becomes. Concrete implementations must also never need to *fork* FLS models/migrations; custom
models live in the concrete project's own apps so FLS owns its migrations entirely and the
downstream owns theirs (this is the migration-divergence trap that breaks django-oscar downstreams).

## Keeping concrete implementations up to date

We already have `concrete/update_fls` (spec-by-spec submodule advance, read spec.md/plan.md, test
gate, one commit per spec). That core design is correct and stays. Improvements:

- **Structured per-spec `upgrade_notes.md`.** Going forward, completing an FLS spec authors a small
  structured upgrade-notes file (flags: requires_migrations, requires_template_review,
  requires_settings_change, requires_package_upgrade, requires_tailwind_rebuild; plus breaking-change
  notes). `update_fls` reads this to decide what integration steps to run instead of inferring from
  prose. This adds a required step to FLS's own spec-completion workflow. Older specs without the
  file → command warns and falls back to inference.
- **Dry-run / preview step** listing all pending specs and their flags before any pointer moves.
- **Migration safety:** `manage.py migrate --check` before applying each spec, `makemigrations
  --check` after, to catch concrete-project migration state issues and avoid silent conflicts.
- **Template-drift detection:** for specs that touched FLS templates, diff the changed template
  paths against the concrete project's overrides and flag any override whose upstream source
  changed (a lightweight take on Symfony Flex's diff-based patching).
- **Documented rollback procedure** for when a spec fails mid-integration.
- Always run `uv sync` after a pointer move (catches new FLS dependencies); use `uv sync --locked`
  in concrete-project CI.

## Caprover / dead-deployment cleanup

Remove the dead Caprover artifacts (this is the only deployment work in scope):

- Delete `captain-definition`.
- Delete `docs/how tos/Caprover deploy.md`.
- Edit `README.md` (remove the "Caprover predeploy hook" mention; keep the rest).
- Fix the now-broken link to the deleted file in `docs/product/deployment.md`.

No Python/settings/CI code references Caprover, so nothing else breaks. Generic Docker assets
(`Dockerfile`, `docker-compose.yml`, `nginx.conf`, `docker-entrypoint.sh`, `.dockerignore`,
`DOCKER_DEPLOY.md`) are **not** Caprover-specific — leave them alone for now; they belong to the
future deployment-helpers work, not this spec.

## Research

See the research notes in this directory:

- `research_comparable_frameworks.md` — Wagtail / Saleor / django-oscar / cookiecutter+cruft; the
  template-vs-fork tension and the migration-divergence trap.
- `research_submodule_uv_mechanics.md` — submodule + uv-editable mechanics, GitHub-template behaviour,
  submodule read-only enforcement.
- `research_upgrade_sync_ux.md` — evaluation of `update_fls` and the structured upgrade-notes design.
- `research_caprover_cleanup.md` — exact cleanup inventory (delete vs review-later).
