# Admin Interface

_Last updated: 2026-08-11_

## Summary

- The Django admin is enhanced with the Unfold UI framework, preserving all standard Django admin behaviour.
- Administrators grant educators access to specific cohorts through per-object permissions.
- Organisations are created, renamed, and given a logo entirely through the admin, with no delete and no merge. Assigning someone a staff role on an organisation grants access to every cohort inside it, including ones added later.
- The admin path is configurable via `DJANGO_ADMIN_URL`, so production can move it off the default location.
- Legal consent records are fully read-only — they cannot be added, changed, or deleted.
- Webhook endpoints have a test-send action for verifying configuration without waiting for a real event.
- Two site-aware base admin classes are available: one for ordinary models, one for models that also need guardian's per-object permission UI.

## Unfold

The admin uses [Unfold](https://github.com/unfoldadmin/django-unfold) as a drop-in enhancement over Django's standard admin. It provides an improved layout while leaving standard admin behaviour intact.

Site-scoped admin pages are automatically filtered to the current site, consistent with [multi-tenancy and isolation](./multi-tenancy-and-isolation.md). Unfold's branding customisation (site title, header colour, logo) is present in settings but commented out, so admin branding is not configured in a default installation.

## Site-Aware Admin Base Classes

`freedom_ls/site_aware_models/admin.py` provides two base classes for site-aware models. Both exclude the `site` field from the admin form, since it is set automatically rather than chosen by the administrator.

- **`SiteAwareModelAdmin`** — the default. Use this for any site-aware model that does not need per-object permissions.
- **`GuardedSiteAwareModelAdmin`** — combines Unfold's `ModelAdmin` with guardian's `GuardedModelAdmin` (in that MRO order) to add the object-permissions tab on top of the usual site-aware admin behaviour. Use this only where per-object permissions are actually needed — Unfold and guardian override overlapping admin templates and hooks, and the pairing is not guaranteed by either package, so a model adopting it should have its object-permissions page checked by hand in the browser.

## Cohort Permissions

Each cohort's admin detail page carries a per-object permissions tab, provided by `GuardedSiteAwareModelAdmin`. Administrators use it to grant an individual educator view access to that specific cohort. The educator interface filters its cohort and user listings, and their detail pages, by these grants — the [known gap](./educator-interface.md#access-control) has narrowed to the Courses section, which remains unguarded. Per-cohort grants and [organisation staff roles](#organisation-management) are two independent routes to the same access, at different granularity.

## Organisation Management

Organisations are managed entirely through the Django admin: an administrator creates an organisation, renames it, uploads a logo, and assigns staff to it. What an organisation is, and where it sits relative to a site, is described in [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations).

There is no delete and no merge — both are refused outright. This is a deliberate limit for this release, not an oversight. There is also no bulk import, and no way to manage organisations outside the admin.

Assigning someone a staff role on an organisation, through the same per-object permissions tab used for cohorts, grants them access to every cohort in that organisation in the educator interface, including cohorts added later. It is the alternative to granting per-cohort permissions one at a time. See [educator interface](./educator-interface.md#organisation-scope) for how educators move between the organisations they can reach.

Logo uploads accept PNG, JPEG, and WebP; SVG is rejected deliberately. A maximum file size and minimum and maximum pixel dimensions apply, and each upload is validated against its actual image bytes rather than trusted by filename — see [security and data handling](./security-and-data-handling.md).

## Configurable Admin URL

The admin is mounted at the path given by the `DJANGO_ADMIN_URL` environment variable. Changing it in production moves the admin off its default location, reducing exposure to automated discovery. No code change is required.

## Read-Only Consent Records

Legal consent records are registered read-only: the admin disables add, change, and delete. This preserves the append-only integrity of the consent audit trail, described in [authentication](./authentication.md).

## Webhook Test-Send

A webhook endpoint's admin detail page exposes an action that sends a test payload to the configured URL, so an administrator can confirm the endpoint is reachable and its authentication headers are correct before a live event triggers delivery. The full control set is in [webhooks](./webhooks.md).
