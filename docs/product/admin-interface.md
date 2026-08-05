# Admin Interface

_Last updated: 2026-08-05_

## Summary

- The Django admin is enhanced with the Unfold UI framework, preserving all standard Django admin behaviour.
- Administrators grant educators access to specific cohorts through per-object permissions.
- The admin path is configurable via `DJANGO_ADMIN_URL`, so production can move it off the default location.
- Legal consent records are fully read-only — they cannot be added, changed, or deleted.
- Webhook endpoints have a test-send action for verifying configuration without waiting for a real event.

## Unfold

The admin uses [Unfold](https://github.com/unfoldadmin/django-unfold) as a drop-in enhancement over Django's standard admin. It provides an improved layout while leaving standard admin behaviour intact.

Site-scoped admin pages are automatically filtered to the current site, consistent with [multi-tenancy and isolation](./multi-tenancy-and-isolation.md). Unfold's branding customisation (site title, header colour, logo) is present in settings but commented out, so admin branding is not configured in a default installation.

## Cohort Permissions

Each cohort's admin detail page carries a per-object permissions tab. Administrators use it to grant an individual educator view access to that specific cohort. The educator interface then filters its cohort and user listings by these grants — note the [known gap](./educator-interface.md#access-control) in how detail pages enforce them.

## Configurable Admin URL

The admin is mounted at the path given by the `DJANGO_ADMIN_URL` environment variable. Changing it in production moves the admin off its default location, reducing exposure to automated discovery. No code change is required.

## Read-Only Consent Records

Legal consent records are registered read-only: the admin disables add, change, and delete. This preserves the append-only integrity of the consent audit trail, described in [authentication](./authentication.md).

## Webhook Test-Send

A webhook endpoint's admin detail page exposes an action that sends a test payload to the configured URL, so an administrator can confirm the endpoint is reachable and its authentication headers are correct before a live event triggers delivery. The full control set is in [webhooks](./webhooks.md).
