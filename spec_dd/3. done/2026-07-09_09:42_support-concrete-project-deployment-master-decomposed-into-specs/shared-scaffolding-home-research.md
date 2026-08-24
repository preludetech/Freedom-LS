# Shared scaffolding home — research

Resolves the open **"Decisions needed → Shared scaffolding home"** item in
[`concrete_project_idea.md`](./concrete_project_idea.md): where the reusable,
multi-project deployment parts eventually live. The idea framed it as a binary —
**shared repo vs upstream into FLS**. Research shows that framing is incomplete:
the answer depends on *how each artifact is reused*, and there is already-built
org infrastructure that pre-decides most of it.

## What already exists (the facts that reframe the decision)

1. **FLS itself already ships deployment artifacts** at its repo root —
   `Dockerfile`, `docker-compose.yml`, `nginx.conf`, `docker-entrypoint.sh`,
   `.env.example`, `.dockerignore`. They are the **standalone / nginx /
   bind-mount** artifacts the idea explicitly supersedes (nginx not Caddy;
   `container_name:` set; bind mounts `./media` + `~/.fls_postges_prod_data`;
   build context assumes a root `./freedom_ls`). They are *reference-only* for a
   concrete project — they cannot be consumed in place.

2. **A concrete-project template repo already exists** —
   `git@github.com:preludetech/freedom-ls-concrete-template.git`, a GitHub
   **Template Repository** ("Use this template" → new repo, submodule pointer
   preserved). New concrete FLS projects are *born from it*. It already owns the
   root-level wiring a project needs (`config/`, `pyproject.toml`,
   `tailwind.input.css`, `CLAUDE.md`, `.claude/settings.json`, and
   `dev_db/docker-compose.yaml`) — but currently ships **no production deployment
   scaffolding** (only `dev_db/` + `.github/dependabot.yml`). That absence is the
   gap this decision fills.

3. **A keep-in-sync apparatus already exists** around that template:
   - `/update_template_repo` — propagate a completed FLS change into the
     **scaffold new projects are generated from**.
   - `/update_fls` — propagate a completed FLS change into an **existing**
     downstream project.
   - `notify-downstream.yml` in FLS — FLS already fans changes out to downstreams.
   - `resources/template_repo_manifest.md` — documents the template's layout and a
     `config/` content contract, with a written "keep the template in sync" process.
   The template's stated philosophy: **intentionally thin — wiring and nothing
   else; never fork FLS migrations/logic.** Deployment scaffolding is *infra
   wiring*, so it fits that remit (the template already carries `dev_db/` compose).

## The load-bearing distinction: two classes of "reusable"

The deployment artifacts do **not** all reuse the same way. Sorting them by
*reuse mechanism* is what dissolves the binary.

### Class A — Root boilerplate (must physically sit at each project root)

`Dockerfile`, `docker-compose.yml`, `Caddyfile`, `docker-entrypoint.sh`,
`.env.example`, `.dockerignore`.

- Docker build context and `docker compose` discovery **require** these at the
  consuming repo's root. They **cannot be consumed live** from a submodule or a
  package — every concrete project needs its *own copy at root*.
- Therefore reuse = "start new projects with a good copy" + "propagate
  improvements into existing copies." That is precisely a **template + sync**
  problem, not a shared-dependency problem.
- FLS *cannot* be the live home for these: `CLAUDE.md` forbids editing
  `submodules/**`, and a Dockerfile inside `submodules/Freedom-LS/` is the wrong
  build context anyway. FLS can at most hold a **reference** copy — which is
  strictly worse than a template that copies at birth.

### Class B — Live-referenceable, versioned logic (consumed by reference)

GitHub Actions **reusable workflows** (`on: workflow_call`) / composite actions,
and **Ansible roles** (a collection / `requirements.yml`).

- These *can* be centralized and referenced **by version**, so a fix propagates
  without copying. A reusable workflow is referenced as
  `preludetech/Freedom-LS/.github/workflows/deploy.yml@<sha>` — **no build-context
  problem** (it's referenced by repo path, never built from the submodule tree).
- FLS is already the org's shared-CI hub (it runs `notify-downstream.yml`), so
  upstreaming *reusable workflows* into FLS is a natural fit; each concrete
  project keeps only a thin **caller** workflow that pins a version + passes
  inputs/secrets.
- Ansible roles are also live-referenceable, but they are the *least* coupled to
  FLS and the *most* likely to want independent versioning — a candidate for a
  small dedicated repo/collection **if and when** a second project needs them.

## Why the binary as posed is the wrong question

- **"Upstream everything into FLS"** fails for Class A: the root files can't be
  consumed from a submodule, so FLS could only host duplicate *reference* copies —
  a second, worse copy-path competing with the template that already exists.
- **"One new shared deploy repo for everything"** fails for Class A too: for
  copy-at-birth files a shared repo is *also* just a source-to-copy — duplicating
  what the template already does, and now splitting the scaffold across two
  template-like sources with two sync paths, for no gain. It also adds a repo to
  own before a second project even exists (speculative).
- Both framings **ignore the template repo**, which already exists, already owns
  root wiring, and already has a sync command — the natural Class A home.

## Recommendation — split by reuse mechanism (not one home)

1. **Class A (root boilerplate) → the existing concrete-template repo**, kept
   current with the already-built `/update_template_repo` machinery.
   - New projects get correct deployment scaffolding at birth; existing projects
     receive improvements through the same `/update_fls` / notify-downstream path
     already used for `config/` changes.
   - Zero new infrastructure; extends the template's existing remit (it already
     ships `dev_db/` compose). Add the manifest rows for the new files and a
     "deployment scaffold" section to the `config/` contract's sibling.
   - **Caveat to design in now:** these files are parameterised by env
     (`COMPOSE_PROJECT_NAME`, `--env-file`, `HOST_DOMAIN`, `FLS_THEME` build-arg),
     so the template ships the *generic* Dockerfile/compose/Caddyfile and each
     project supplies only its `.env`/inventory. Keep project-specific values out
     of the templated files — the idea's "generic vs project-specific" separation
     is what makes this clean.

2. **Class B, CI/CD → upstream into FLS as `workflow_call` reusable workflows**,
   called by a thin per-project caller. FLS is already the org CI hub; this
   replaces the superseded standalone CI story with a versioned, shared one, and a
   bug fix reaches every project by bumping one ref.

3. **Class B, Ansible → keep in this project's repo for V1; extract to a shared
   `freedom-ls-deploy` collection (or FLS `deploy/`) only when the *second*
   concrete project actually needs it.** This matches the idea's "for now
   everything lives in this repo" and avoids speculative extraction; the trigger
   is a real second consumer, not a calendar.

### Sequencing (so this doesn't block V1)

- **This spec:** author every artifact **in the concrete project repo**, exactly
  as the idea already states — but *structure* it for the split above (generic
  files free of project-specific values; a thin CI caller shape even if V1's
  workflow is self-contained).
- **On the second concrete project:** promote Class A into the template repo via
  `/update_template_repo`, upstream Class B CI into FLS as reusable workflows, and
  reassess the Ansible collection. The "config change, not a rewrite" posture the
  idea takes everywhere else applies here too.

### Net

The eventual home is **not one place**: **template repo** for copy-at-birth root
files (the bulk), **FLS reusable workflows** for CI/CD, and a **deferred shared
Ansible collection** triggered by a real second consumer. "Shared repo vs upstream
into FLS" collapses into "both, by mechanism — and the template repo (a third
option the idea omitted) carries the largest part."
