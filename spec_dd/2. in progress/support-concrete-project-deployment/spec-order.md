# Spec order & parallelism — `support-concrete-project-deployment`

This effort was split from a single monolith into **5 numbered specs** plus this index and a
`third-party-services.md` setup reference. The number on each spec file is its **execution order**.
Specs 1–4 target **this repo** (`freedom_ls`); Spec 5 targets the **separate
`freedom-ls-concrete-template` repo** and is meant to be moved there and implemented there.

## The specs

| # | Spec | Repo | Scope (one line) | Depends on |
|---|------|------|------------------|------------|
| 1 | P0 prod settings + importable defaults | this repo | §5.1 A–F prod-settings fixes, delivered as importable `freedom_ls/deployment/settings_defaults.py` primitives | — (foundational) |
| 2 | P1 importable health module | this repo | `freedom_ls/health/` with liveness (no deps) + readiness (DB); `django-health-check`; pre-wired `SECURE_REDIRECT_EXEMPT` | Spec 1 (§5.1-A) |
| 3 | Background-tasks reconciliation | this repo | opt-in `django-tasks-db` primitive + doc fix; shipped default stays `ImmediateBackend` | Spec 1 (§5.1-C removes the TODO) |
| 4 | Remove standalone path, document concrete-only | this repo | delete nginx/standalone artifacts; concrete-only deployment docs | Spec 1 (loose); doc-rewrite pairs with Spec 5 |
| 5 | P3 deployment scaffolding | **template repo** | Dockerfile, compose, Caddyfile, entrypoint, `.env.example`, GHCR CI, Ansible/backups/Sentry, worker profile, template `settings_prod.py` migration | Specs 1, 2, 3 |

## Ordering & parallelism

```
        ┌── Spec 2 (health) ──┐
Spec 1 ─┼── Spec 3 (tasks) ───┼── Spec 5 (template scaffolding, template repo)
        └── Spec 4 (cleanup) ─┘        ▲ runs last — consumes Specs 1–3
```

- **Spec 1 first — foundational.** Everything either imports its primitives (`settings_defaults`) or
  pairs with its `SECURE_PROXY_SSL_HEADER` change. Landing the P0 values and the §6 importable module
  together is required: doing the values now and the module later re-touches `settings_prod.py`
  twice.
- **After Spec 1, run Specs 2, 3, 4 in parallel** — distinct new modules / dependencies / deletions.
  - **Doc coupling (Specs 3 & 4):** both edit `docs/product/deployment.md`. Land Spec 3's tasks-doc
    fix before, or together with, Spec 4's rewrite to avoid clobbering.
  - **Spec 4's concrete-only guide** points at Spec 5's shipped scaffolding, so its *doc rewrite* is
    best written **alongside/after Spec 5**, even though the *artifact removals* can happen right
    after Spec 1.
- **Spec 5 last.** It consumes Spec 1 (`settings_defaults`, proxy header, `DB_SSLMODE`, log-cap
  pairing), Spec 2 (readiness endpoint; keeps `/health/*` off the public vhost), and Spec 3 (opt-in
  `django-tasks-db` for the `worker` profile).

## Pairing constraints (do not land one half without the other)

- **Spec 1 §5.1-B (stdout logging) ⇄ Spec 5 §5.2 log caps.** Moving to stdout relocates the disk-fill
  risk to uncapped Docker `json-file` logs — only safe with the per-service `max-size`/`max-file`
  caps. Do **not** ship stdout logging ahead of the caps.
- **Spec 1 §5.1-A (proxy header) ⇄ HSTS verification.** HSTS and `SECURE_SSL_REDIRECT` are inert
  until the proxy header lands; verify them in the same pass.
- **Spec 2 `SECURE_REDIRECT_EXEMPT` ⇄ Spec 1 §5.1-A.** The redirect-exempt health path only matters
  once the proxy header makes internal HTTP probes get a `301 → https`.

## Cross-cutting context

### The propagation problem (structural root cause)
FLS has no importable base-settings module, so each concrete project owns a full copy of
`settings_base.py` + `settings_prod.py`; a fix in one project does not propagate and must land in
**three** surfaces (template repo, FLS reference `config/`, existing projects via `/update_fls`).
Spec 1 §6 collapses this to "one surface (`freedom_ls`) + a submodule SHA bump" by making the P0
defaults importable.

### Artifact-vs-code home split (idea §7)
- **Reusable deploy *artifacts*** → `freedom-ls-concrete-template` (Spec 5), synced via
  `/fls:sdd:update_template_repo`.
- **Reusable *code* primitives** → `freedom_ls` itself (Specs 1–3), so they are imported, not
  copy-pasted. The tasks backend is an importable primitive projects *may* enable; the shipped
  default stays `ImmediateBackend`.

### Propagation step on every P0 landing (idea §8)
Landing a P0 fix in the reference `config/` + template only patches *future* projects. **Every P0
landing has a further step: run `/fls:sdd:update_fls` against `ConcreteFlsImplementation`** (and any
other existing project) so the flagship consumer is actually patched. Primarily a Spec 1 concern.

## Shared references

- Idea & research live in this directory: `idea.md`, `concrete_project_idea.md`,
  `research_prod_settings_security_defaults.md`, `research_health_liveness_readiness_endpoints.md`,
  `research_importable_base_settings.md`, `research_django_tasks_durable_backend.md`,
  `research_deployment_scaffolding_references.md`, `shared-scaffolding-home-research.md`.
- Codebase verification: `.sdd-work/spec_research_codebase.md`.
- External accounts/credentials each deployment needs: `third-party-services.md`.
