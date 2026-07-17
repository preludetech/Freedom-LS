---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - "INSTALLED_APPS += ['health_check', 'freedom_ls.health']"
  - "SECURE_REDIRECT_EXEMPT (settings_prod, from freedom_ls.deployment.settings_defaults)"
  - "HEALTH_READINESS_CHECKS (optional override; default ['health_check.checks.Database'])"
requires_package_upgrade: true
changed_packages:
  - "django-health-check==4.4.3"
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: P1 importable health module

FLS now ships an importable `freedom_ls.health` package giving two probes out of the box:
`GET /health/liveness/` (always 200, touches no dependency) and `GET /health/readiness/`
(DB-connectivity check by default). The engine is `django-health-check` v4, pinned in the
submodule — nothing for you to `pip`/`uv install` separately, but you do need to wire the apps and
settings into your own project.

## Breaking changes

- **The old static `health_check` view is gone.** The reference `config/urls.py` previously mounted
  a static `{"status":"healthy"}` view named `health_check` at `/health/`. That view and its URL
  name (`health_check`) no longer exist. If your project references the URL name `health_check`
  (e.g. in a middleware exempt-list, a `reverse("health_check")` call, or a monitor pointed at bare
  `/health/`), update it:
  - The path `/health/` no longer resolves on its own — the live paths are now
    `/health/liveness/` and `/health/readiness/`.
  - The resolved view names are now namespaced: `health:liveness` and `health:readiness`.

## Manual steps

1. **Add the apps to `INSTALLED_APPS`** (in your project's settings): add both
   `"health_check"` (the engine — check classes + dashboard templates) and `"freedom_ls.health"`
   (the FLS wrapper). No `HEALTH_CHECK` settings block is needed.

2. **Include the URLconf.** Mount the importable module in your root URLconf, e.g.
   `path("health/", include("freedom_ls.health.urls"))`. This gives you
   `/health/liveness/` and `/health/readiness/`.

3. **Assign `SECURE_REDIRECT_EXEMPT` in your production settings** so internal plain-HTTP probes to
   `/health/…` aren't 301'd to https (which a naive `healthcheck:` reads as unhealthy). Mirror the
   reference `config/settings_prod.py`, importing the shipped default:

   ```python
   from freedom_ls.deployment import settings_defaults as fls_defaults
   SECURE_REDIRECT_EXEMPT = fls_defaults.SECURE_REDIRECT_EXEMPT  # [r"^health/"]
   ```

   This pairs with the proxy-header change (`SECURE_PROXY_SSL_HEADER`) from the earlier deployment
   spec. If your policy forbids a redirect-exempt path, the fallback is to have every prober forge
   `X-Forwarded-Proto: https`.

4. **Update any stale `health_check` references** in your own code — see Breaking changes above.
   If you maintain your own registration-completion middleware exempt-list, use the namespaced names
   `health:liveness` / `health:readiness`.

5. **(Optional) Add cache/storage checks to readiness.** Readiness defaults to DB-only. To opt into
   more, set `HEALTH_READINESS_CHECKS` in your own settings, e.g.
   `["health_check.checks.Database", "health_check.checks.Cache", "health_check.checks.Storage"]`.
   Liveness stays check-free regardless — it's a separate view.

6. **Keep `/health/*` off any public/edge vhost.** Readiness reveals dependency state (recon
   surface); every legitimate consumer reaches it container-to-container or over localhost. Do not
   route `/health/*` on a public reverse proxy.

Not required: no migrations (the health package has no models), no Tailwind rebuild, no npm install.
For deploy smoke-testing that migrations are applied, use `manage.py migrate --check` as a
pre-cutover gate — it is deliberately **not** a polled readiness check.
