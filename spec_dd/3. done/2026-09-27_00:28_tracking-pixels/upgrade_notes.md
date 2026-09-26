---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/google_tag/templates/partials/google_analytics.html
  - freedom_ls/google_tag/templates/partials/google_analytics_events.html
  - freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html
requires_settings_change: true
changed_settings:
  - TEMPLATES  # hard: add freedom_ls.base.context_processors.analytics_events; freedom_ls_base.E004 enforces it at boot
  - INSTALLED_APPS  # optional: freedom_ls.meta_pixel, freedom_ls.tiktok_pixel
  - VISITOR_COUNTRY_HEADER  # optional: needed for either ad pixel to load; freedom_ls_base.E003 rejects an HTTP_ value
  - META_PIXEL_ID  # optional: freedom_ls_meta_pixel.W001 warns when set without VISITOR_COUNTRY_HEADER
  - TIKTOK_PIXEL_ID  # optional: freedom_ls_tiktok_pixel.W001 warns when set without VISITOR_COUNTRY_HEADER
  - SECURE_CSP_REPORT_ONLY  # optional: Meta and TikTok hosts, only if you enable the pixels and keep your own CSP
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: tracking-pixels

Adds optional Meta and TikTok pixels (new apps `freedom_ls.meta_pixel` and
`freedom_ls.tiktok_pixel`) and moves the platform-neutral analytics event queue out of
`freedom_ls.google_tag` into `freedom_ls.base`.

## Breaking changes

**A new context processor is required.** If any of `freedom_ls.google_tag`,
`freedom_ls.meta_pixel` or `freedom_ls.tiktok_pixel` is in `INSTALLED_APPS`, then
`freedom_ls.base.context_processors.analytics_events` must be in
`TEMPLATES[...]['OPTIONS']['context_processors']`. A boot-time system check,
`freedom_ls_base.E004`, enforces this, so a project that already has `freedom_ls.google_tag`
installed fails `manage.py check` until it is added. Without it, recorded events are never sent.

**`freedom_ls.google_tag.events` is removed.** Its contents now live in
`freedom_ls.base.analytics_events`:

| Old (`freedom_ls.google_tag.events`) | New (`freedom_ls.base.analytics_events`) |
| --- | --- |
| `GoogleAnalyticsEvent` | `AnalyticsEvent` (same members and values) |
| `GoogleAnalyticsEventPayload` | `AnalyticsEventPayload` |
| `GOOGLE_ANALYTICS_EVENTS_SESSION_KEY` | `ANALYTICS_EVENTS_SESSION_KEY` (same value, so events queued at deploy time survive) |
| `record_google_analytics_event` | `record_analytics_event` |
| `record_sign_up` | `record_sign_up` |
| `pop_google_analytics_events` | `pop_analytics_events` |

**`freedom_ls.course_access.google_analytics` is renamed** to
`freedom_ls.course_access.analytics_events`. The function names are the same.

**`freedom_ls.google_tag.context_processors` changes:**

- `CONSENT_MODE_DENIED_REGIONS` is removed. Use
  `freedom_ls.base.analytics_events.EU_CONSENT_POLICY_COUNTRIES`.
- `PendingGoogleAnalyticsEvent` is removed.
- `google_tag_config` no longer puts `google_analytics_events` in the template context. Pending
  events are now the `analytics_events` context variable, which
  `freedom_ls.base.context_processors.analytics_events` provides. The Google Ads `send_to` for an
  event is now worked out in the template with the `google_ads_send_to` filter
  (`{% load google_tag_tags %}`).

**The events include point changed.** Templates now include `partials/analytics_events.html`, which
renders each configured platform's events partial. A template of yours that still includes
`partials/google_analytics_events.html` directly sends events to GA4 only and consumes them, so
Meta and TikTok never see them. Switch it to `partials/analytics_events.html`.

## Manual steps

1. Add `"freedom_ls.base.context_processors.analytics_events"` to your `TEMPLATES` context
   processors, then run `manage.py check` and confirm `freedom_ls_base.E004` is gone.
2. Update any imports of `freedom_ls.google_tag.events`, `freedom_ls.course_access.google_analytics`
   or `CONSENT_MODE_DENIED_REGIONS` using the tables above.
3. If you override any of these templates, re-apply your customisations against the new versions:
   - `freedom_ls/base/templates/_base.html`: the GA4 include inside `{% block google_analytics %}`
     is now wrapped in `{% if google_analytics_measurement_id %}`, the Meta and TikTok loader
     partials are included in `<head>`, and the closing include is now
     `partials/analytics_events.html`. If you override `{% block google_analytics %}` (for example
     on a landing page with `content_group`), wrap your include in the same `if`.
   - `freedom_ls/base/templates/_base_interface.html` and
     `freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html`:
     include `partials/analytics_events.html` instead of `partials/google_analytics_events.html`.
   - `freedom_ls/google_tag/templates/partials/google_analytics_events.html`: loops over
     `analytics_events` instead of `google_analytics_events`, and gets `send_to` from the
     `google_ads_send_to` filter.
   - `freedom_ls/google_tag/templates/partials/google_analytics.html`: comments only.
4. Optional, to turn on the Meta or TikTok pixel:
   - add `freedom_ls.meta_pixel` and/or `freedom_ls.tiktok_pixel` to `INSTALLED_APPS`, and
     `freedom_ls.meta_pixel.context_processors.meta_pixel_config` and/or
     `freedom_ls.tiktok_pixel.context_processors.tiktok_pixel_config` to your context processors;
   - set `META_PIXEL_ID` and/or `TIKTOK_PIXEL_ID`;
   - set `VISITOR_COUNTRY_HEADER` to the name of the header your proxy sets to the visitor's
     ISO 3166-1 alpha-2 country code (the header name, e.g. `X-Visitor-Country`, not an `HTTP_`
     key, or `freedom_ls_base.E003` fails). The pixels never load while it is unset, and never load
     for visitors in the EEA, the UK or Switzerland or on educator interface pages;
   - if you define your own `SECURE_CSP_REPORT_ONLY`, add the Meta and TikTok hosts that
     `config/settings_base.py` now lists;
   - if you ship your own privacy policy, name Meta and TikTok in it. The default
     `legal_docs/_default/privacy.md` now does, at version 1.3.

   `docs/how tos/meta-and-tiktok-pixels.md` covers the setup in full.

No migrations, Python or npm package changes, or Tailwind rebuild are needed.
