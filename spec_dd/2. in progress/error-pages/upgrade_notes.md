---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/400.html                # new
  - freedom_ls/base/templates/403.html                # new
  - freedom_ls/base/templates/403_csrf.html           # new
  - freedom_ls/base/templates/404.html                # new
  - freedom_ls/base/templates/429.html                # new
  - freedom_ls/base/templates/500.html                # new
  - freedom_ls/base/templates/503.html                # new
  - freedom_ls/base/templates/cotton/error-page.html  # new
  - freedom_ls/accounts/templates/accounts/lockout.html  # rewritten
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: error-pages

FLS now ships branded pages for 400, 403, 403 (CSRF), 404, 429, 500 and 503, built on a
new `<c-error-page>` cotton component, and restyles `accounts/lockout.html` onto the same
panel.

No new views, URLs, settings, models or migrations. Django and allauth already look for
these bare template names, so shipping the templates is the whole wiring job — do **not**
add `handler400`/`handler403`/`handler404`/`handler500` to your URLconf or set
`CSRF_FAILURE_VIEW` to pick them up.

## Breaking changes

- **A project-level error template now shadows the FLS one.** Django's app-directories
  loader is searched after `TEMPLATES["DIRS"]`, so if your project already has its own
  `400.html`, `403.html`, `403_csrf.html`, `404.html`, `429.html`, `500.html` or
  `503.html` in a project templates directory, yours keeps winning and you will not see
  the new pages. Nothing breaks — but the change is invisible until you remove or rebase
  your copy.

- **`freedom_ls.site_aware_models.models.get_cached_site` no longer raises
  `DisallowedHost`.** For a request whose `Host` header Django has already rejected it
  now returns a new `UnknownSite` (a `django.contrib.sites.requests.RequestSite` subclass
  with empty `domain` and `name`), so that the 400 page — which renders with a full
  `RequestContext` and therefore runs every context processor — does not degrade into a
  500. `UnknownSite` is deliberately *not* a `Site` row. Downstream code that calls
  `get_cached_site` and then queries against the result must guard with
  `isinstance(site, Site)` and fall back to its own default, as FLS's own callers do; code
  that relied on the exception propagating will no longer see it. `SiteAwareManager` and
  `SiteAwareModelBase` carry that guard themselves, so under a rejected host a site-aware
  queryset comes back unfiltered and `save()` leaves `site` unset, rather than either
  raising from inside the ORM.

- **Rendered icon SVGs now carry `width` and `height` attributes.**
  `freedom_ls.icons.backend.build_svg` emits the icon set's intrinsic dimensions alongside
  the existing `viewBox`, so an icon stays small when the stylesheet has not loaded. CSS
  still beats the attributes, so any `size-*` class or explicit width/height rule keeps
  winning. Downstream CSS that relied on a `viewBox`-only SVG stretching to fill its
  container with no sizing rule of its own must now set that size explicitly.

## Manual steps

1. **Rebuild Tailwind** — `npm run tailwind_build` (or your project's equivalent). The new
   templates use class combinations your bundle has not seen: `bg-error-light` /
   `text-on-error-light`, `bg-warning-light` / `text-on-warning-light`, `bg-info-light` /
   `text-on-info-light`, `ring-8`, `min-h-[70vh]` and `tracking-[0.14em]`. Without a
   rebuild the status mark on every error page renders unstyled.

2. **Re-apply your customisations to `accounts/lockout.html`** if you override it. The
   template was rewritten: it now extends `_base.html` instead of
   `allauth/layouts/entrance.html`, renders through `<c-error-page>`, and names the
   configured cool-off period using the new `duration` filter from
   `freedom_ls.base.templatetags.fls_base_filters` (`{% load fls_base_filters %}`,
   `{{ cooloff_timedelta|duration }}`). An override that still extends the allauth
   entrance layout keeps working but will not pick up the new styling.

3. **Review any project-level error templates** you already ship (see Breaking changes
   above) and decide whether to keep yours or adopt the FLS pages.

4. **If you set `FREEDOM_LS_ICON_BACKEND` to a custom backend**, add the two new semantic
   icon names `rate_limit` and `maintenance` to it. The four built-in mappings
   (heroicons, lucide, tabler, phosphor) already have them, so projects using the default
   backend need do nothing — `manage.py check` will report `icons.E007` if a mapping is
   missing a semantic name.

5. **Nothing to serve for 503.** FLS ships `503.html` but never renders it — there is no
   maintenance mode, middleware or switch. If you want it, point your proxy or maintenance
   middleware at the template yourself. It is a standalone `<!DOCTYPE html>` document that
   links only the compiled stylesheet, so it renders with the app down.
