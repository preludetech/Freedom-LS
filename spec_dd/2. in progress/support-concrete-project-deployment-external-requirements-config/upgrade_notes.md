---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - "freedom_ls/base/templates/_base.html"
requires_settings_change: true
changed_settings:
  - "INSTALLED_APPS: add \"freedom_ls.deployment\""
  - "TEMPLATES context_processors: add \"freedom_ls.deployment.context_processors.posthog_config\" (the old freedom_ls.base.context_processors.posthog_config path was removed)"
  - "New env->settings: POSTHOG_API_HOST (default https://us.i.posthog.com), POSTHOG_UI_HOST (optional)"
  - "New env->settings: SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_RELEASE, SENTRY_TRACES_SAMPLE_RATE (default 0.1), SENTRY_SEND_DEFAULT_PII (default False)"
  - "R2/S3 media is now private-by-default: new AWS_QUERYSTRING_AUTH (default True), AWS_QUERYSTRING_EXPIRE (default 3600), AWS_S3_CUSTOM_DOMAIN (opt-in public serving)"
  - "AWS_DEFAULT_ACL removed (R2 has no ACLs) — drop it from your environment"
  - "AWS_S3_REGION_NAME now defaults to \"auto\" (R2 convention) when unset"
requires_package_upgrade: true
changed_packages:
  - "sentry-sdk[django]>=2.64.0"
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: external requirements config (PostHog / Sentry / R2)

## Breaking changes

**Media is now private-by-default.** When `AWS_STORAGE_BUCKET_NAME` is set, FLS
serves media through **signed, time-limited URLs** (`querystring_auth=True`,
`AWS_QUERYSTRING_EXPIRE=3600` seconds) instead of plain public URLs. Deployments
that previously relied on publicly-readable media (hotlinked object URLs, a public
bucket, or a CDN pointed at the bucket without signing) will find those URLs stop
working after upgrade — every media link is now short-lived and signed. Opt back
out explicitly if you need public serving (see Manual steps).

**`AWS_DEFAULT_ACL` is no longer read** (Cloudflare R2 has no ACLs). If your
environment sets it, remove it; it has no effect.

**The PostHog context processor moved.** It is now
`freedom_ls.deployment.context_processors.posthog_config` (previously
`freedom_ls.base.context_processors.posthog_config`, which no longer exists). If
your project registers this processor in its own `TEMPLATES` config by that old
dotted path, Django will fail to import it at startup until you update the path.

No models, migrations, or URL **names** changed. A new URL `/sentry-debug/` is
added (staff/superuser-gated). PostHog and Sentry stay inert unless you set
`POSTHOG_API_KEY` / `SENTRY_DSN`, so enabling them is opt-in.

## Manual steps

1. **If your project maintains its own Django settings** (rather than importing
   FLS's `config/settings_base.py`):
   - Add `"freedom_ls.deployment"` to `INSTALLED_APPS`. Its `AppConfig.ready()`
     hook initialises Sentry (a no-op until `SENTRY_DSN` is set).
   - Add `"freedom_ls.deployment.context_processors.posthog_config"` to your
     `TEMPLATES[0]["OPTIONS"]["context_processors"]` so the PostHog snippet
     renders.
   - Include the deployment URLs so `/sentry-debug/` resolves:
     `path("", include("freedom_ls.deployment.urls"))`.
   - Surface the PostHog/Sentry env vars onto Django settings (see
     `config/settings_base.py` for the `env_bool`/`env_float` pattern) so
     `deployment.config` can resolve them.

2. **Review your `_base.html` override, if you have one.** FLS's
   `freedom_ls/base/templates/_base.html` changed: the PostHog snippet now reads
   `api_host: '{{ posthog_api_host }}'` (and an optional `{{ posthog_ui_host }}`)
   from context instead of a hardcoded `https://eu.i.posthog.com`. If you override
   this template, re-apply that change or your PostHog host stays hardcoded.

3. **To keep serving media publicly** (opt back out of signed URLs), set both:

   ```
   AWS_S3_CUSTOM_DOMAIN=cdn.your-domain.example
   AWS_QUERYSTRING_AUTH=False
   ```

   `AWS_QUERYSTRING_AUTH` accepts `false`/`0`/`no`/`off` (case-insensitive) to
   disable signing. Without a custom domain, leave it at its default `True` so
   media stays private.

4. **Adjust the signed-URL lifetime** if the 1-hour default is too short or long
   for your embeds: `AWS_QUERYSTRING_EXPIRE=3600` (seconds).

5. **Remove `AWS_DEFAULT_ACL`** from your environment / secrets — it is no longer
   used.

6. **Configure Sentry (optional).** Set `SENTRY_DSN` to enable it. When you do,
   also set `SENTRY_ENVIRONMENT` per environment — otherwise the SDK silently tags
   every event `production`, making staging indistinguishable from prod. Other
   optional vars: `SENTRY_RELEASE`, `SENTRY_TRACES_SAMPLE_RATE` (default `0.1`),
   `SENTRY_SEND_DEFAULT_PII` (default `False`). Verify wiring by hitting
   `/sentry-debug/` as a staff/superuser — it raises a deliberate 500 that should
   land in Sentry.

7. **Configure PostHog region (optional).** `POSTHOG_API_HOST` now defaults to
   `https://us.i.posthog.com`; override it (e.g. `https://eu.i.posthog.com`) if
   your PostHog project is in another region. `POSTHOG_UI_HOST` is only needed for
   a reverse-proxied ingestion host.

The `sentry-sdk[django]` dependency ships with FLS — run your normal dependency
sync (`uv sync`) after upgrading; there is no separate install step. No
migrations, Tailwind rebuild, or npm installs are required for this upgrade.
