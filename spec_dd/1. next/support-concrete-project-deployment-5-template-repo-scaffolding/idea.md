# Idea: P3 deployment scaffolding (spec 5 of support-concrete-project-deployment)

This is **spec 5 of 5** in the `support-concrete-project-deployment` decomposition. The spec is
already written — see `1. spec.md` in this directory.

> **⚠️ Targets the SEPARATE `freedom-ls-concrete-template` repo**, not this repo — it is meant to be
> moved there and implemented there (synced via `/fls:sdd:update_template_repo`).

## Source idea & coordination (all in the parent directory)

- **Refined idea:** `spec_dd/2. in progress/support-concrete-project-deployment/idea.md`
  (and the earlier `concrete_project_idea.md`)
- **Ordering / dependencies across the 5 sibling specs:**
  `spec_dd/2. in progress/support-concrete-project-deployment/spec-order.md`
  (**runs last** — consumes the code primitives from specs 1, 2, and 3)
- **Third-party services & credentials** (Cloudflare, R2/S3, Sentry, GHCR, VPS, backups):
  `spec_dd/2. in progress/support-concrete-project-deployment/third-party-services.md`

## Associated research

- `spec_dd/2. in progress/support-concrete-project-deployment/research_deployment_scaffolding_references.md`
- `spec_dd/2. in progress/support-concrete-project-deployment/shared-scaffolding-home-research.md`
- Codebase verification: `.sdd-work/spec_research_codebase.md`
