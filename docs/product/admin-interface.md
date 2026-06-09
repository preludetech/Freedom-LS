# Admin Interface

_Last updated: 2026-06-09_

## Summary

- Django admin is enhanced with the Unfold UI framework for an improved administrative experience.
- Object-level permissions via django-guardian allow cohort access to be granted per educator.
- The admin URL is configurable via the `DJANGO_ADMIN_URL` environment variable, enabling obscured or custom paths in production.
- `LegalConsent` records are fully read-only in the admin — they cannot be added, changed, or deleted through the interface.
- Webhook endpoints include a test-send action for verifying configuration without triggering a real event.

## Unfold Admin Framework

The admin uses [Unfold](https://github.com/unfoldadmin/django-unfold) as a drop-in enhancement over Django's standard admin. Unfold must be listed before `django.contrib.admin` in `INSTALLED_APPS`. It provides an enhanced layout while preserving all standard Django admin behaviour.

All site-scoped admin classes extend `SiteAwareModelAdmin` (which itself re-exports Unfold's `ModelAdmin`). This ensures admin querysets are automatically filtered to the current site, consistent with the isolation model described in [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

Note: the `UNFOLD` settings block for branding customisation (site title, header colour, logo) is present in `config/settings_base.py` but is commented out. Admin branding is not configured in a default installation.

## Object-Level Permissions (django-guardian)

`django-guardian` is integrated via `unfold.contrib.guardian`. The `Cohort` admin class uses `GuardedModelAdmin`, which adds a per-object permissions tab to each cohort's admin detail page. Administrators use this tab to grant individual educators `view_cohort` permission on specific cohorts. The educator interface then enforces these permissions via `get_objects_for_user`.

## Configurable Admin URL

The admin is mounted at the path defined by the `DJANGO_ADMIN_URL` environment variable. Changing this value in production moves the admin to a non-default URL, reducing exposure to automated discovery. No code change is required.

## LegalConsent (Read-Only)

The `LegalConsent` model is registered in the admin as fully read-only. The admin class disables the add, change, and delete actions. This preserves the append-only integrity of the consent audit trail. The full description of `LegalConsent` and its fields is in [authentication](./authentication.md).

## Webhook Test-Send

The `WebhookEndpoint` admin detail page exposes a custom action that sends a test payload to the configured endpoint URL. This allows administrators to verify that an endpoint is reachable and that authentication headers are correct before a live event triggers delivery. Webhook controls (HMAC signing, encrypted secrets, SSRF protection) are described in [webhooks](./webhooks.md).
