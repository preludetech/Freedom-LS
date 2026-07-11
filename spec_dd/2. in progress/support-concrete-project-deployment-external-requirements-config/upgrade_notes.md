---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - "AWS media is now private-by-default: new AWS_QUERYSTRING_AUTH (default True), AWS_QUERYSTRING_EXPIRE (default 3600), AWS_S3_CUSTOM_DOMAIN"
  - "AWS_DEFAULT_ACL removed (R2 has no ACLs) — drop it from your environment"
  - "AWS_S3_REGION_NAME now defaults to \"auto\" (R2 convention) when unset"
  - "New Sentry vars: SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_RELEASE, SENTRY_TRACES_SAMPLE_RATE (default 0.1), SENTRY_SEND_DEFAULT_PII (default False)"
  - "New PostHog vars: POSTHOG_API_HOST (default https://us.i.posthog.com), POSTHOG_UI_HOST (optional)"
requires_package_upgrade: true
changed_packages:
  - "sentry-sdk[django]"
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: external requirements config (PostHog / Sentry / R2)

## Breaking changes

**Media is now private-by-default.** When `AWS_STORAGE_BUCKET_NAME` is set, FLS
serves media through **signed, time-limited URLs** (`querystring_auth=True`,
`AWS_QUERYSTRING_EXPIRE=3600` seconds) instead of plain public URLs. Deployments
that previously relied on publicly-readable media (e.g. hotlinked object URLs, a
public bucket, or a CDN pointed at the bucket without signing) will find those
URLs stop working after upgrade — every media link is now short-lived and signed.

`AWS_DEFAULT_ACL` is no longer read (Cloudflare R2 has no ACLs). If your
environment sets it, remove it; it has no effect.

No models, migrations, URL names, or template context keys changed. PostHog and
Sentry are inert unless you set `POSTHOG_API_KEY` / `SENTRY_DSN` respectively, so
they are not breaking for existing deployments.

## Manual steps

1. **To keep serving media publicly** (opt back out of signed URLs), set both:

   ```
   AWS_S3_CUSTOM_DOMAIN=cdn.your-domain.example
   AWS_QUERYSTRING_AUTH=False
   ```

   `AWS_QUERYSTRING_AUTH` accepts any falsy value (`false`/`0`/`no`/`off`,
   case-insensitive). Without a custom domain, leave it at its default `True` so
   media stays private.

2. **Adjust the signed-URL lifetime** if the 1-hour default is too short or long
   for your embeds:

   ```
   AWS_QUERYSTRING_EXPIRE=3600
   ```

3. **Remove `AWS_DEFAULT_ACL`** from your environment / secrets — it is no longer
   used.

4. **Configure Sentry (optional).** Set `SENTRY_DSN` to enable it. When you do,
   also set `SENTRY_ENVIRONMENT` per environment — otherwise the SDK silently tags
   every event `production`, making staging indistinguishable from prod. Other
   optional vars: `SENTRY_RELEASE`, `SENTRY_TRACES_SAMPLE_RATE` (default `0.1`),
   `SENTRY_SEND_DEFAULT_PII` (default `False`).

5. **Configure PostHog region (optional).** `POSTHOG_API_HOST` now defaults to
   `https://us.i.posthog.com`; override it (e.g. `https://eu.i.posthog.com`) if
   your PostHog project is in another region. `POSTHOG_UI_HOST` is only needed for
   a reverse-proxied ingestion host.

The `sentry-sdk[django]` dependency is pulled in transitively via FLS — no
separate install step beyond upgrading FLS. No migrations, Tailwind rebuild, or
npm installs are required for this upgrade.
