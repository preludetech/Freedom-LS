---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: support-concrete-project-deployment-5-template-repo-scaffolding

This spec delivers reusable **deployment scaffolding** (Dockerfile, `docker-compose.yml`,
`Caddyfile`, `docker-entrypoint.sh`, `.env.example`, `.dockerignore`, GHCR CI, Sentry/settings
wiring). Those artifacts are authored in the **separate `freedom-ls-concrete-template` repo**, not in
`freedom_ls`. They reach *new* projects via "Use this template", not by pulling `freedom_ls` — so
there is nothing in the shared library for an existing downstream project to import here.

The only change this branch makes to `freedom_ls` itself is a fix to a vendored static asset:
`freedom_ls/content_engine/static/content_engine/vendor/katex/katex.min.css` no longer references the
`.woff`/`.ttf` KaTeX fonts that were never vendored (only `.woff2` ships, which serves every current
browser).

## Breaking changes

None. The dropped `.woff`/`.ttf` `url()` entries pointed at files that were never present on disk;
removing them changes no rendered output.

## Manual steps

- **Nothing new is required.** Run `collectstatic` as part of your normal deploy — this fix is what
  now lets it *succeed*: under `ManifestStaticFilesStorage` strict mode, `collectstatic` previously
  hard-failed on the 40 missing KaTeX font files referenced by `katex.min.css`. After pulling, that
  failure is gone.
- **Existing projects wanting the new deployment stack** (Caddy-fronted Compose, GHCR image build,
  worker + prune services) must adopt the artifacts from the `freedom-ls-concrete-template` repo
  manually — they are not distributed through `freedom_ls`. New projects get them by scaffolding from
  that template.
