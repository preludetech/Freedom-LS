---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html
  - freedom_ls/base/templates/_base_interface.html
  - freedom_ls/base/templates/partials/posthog.html
  - freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: add "freedom_ls.google_tag" or _base.html raises TemplateDoesNotExist
  - TEMPLATES  # hard: two new context processors, or the tag renders nothing
  - GOOGLE_ANALYTICS_MEASUREMENT_ID  # optional: unset disables GA4 entirely
  - GOOGLE_ADS_CONVERSION_ID  # optional: unset disables Google Ads
  - GOOGLE_ADS_CONVERSION_LABELS  # optional: malformed value raises at boot
  - SECURE_CSP_REPORT_ONLY  # optional: report-only, violations are logged not blocked
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: google-analytics-setup

## Breaking changes

**`CourseAccessBackend.get_access_type()` is a new required method.** A project with its own
backend subclassing `freedom_ls.course_access.backends.CourseAccessBackend` directly must
implement it, or every course-funnel event raises `NotImplementedError` from
`freedom_ls.course_access.google_analytics.course_event_params` — a 500 on the course player,
the finish page, the apply view and the express-interest view, whether or not GA4 is
configured. It returns a stable lowercase snake_case machine name for how the course is
entered ("free"), never the badge label, which is display copy.

A backend subclassing `FreeOnlyCourseAccessBackend` inherits an implementation returning
`"free"` and needs no change unless it has more than one access type.

Nothing else in this branch changes an existing setting's meaning, a URL, a model field or a
template block, and no system check id was renumbered or repurposed.

## Manual steps

1. **Add the app.** Put `"freedom_ls.google_tag"` in `INSTALLED_APPS`. This is not optional for
   a project using FLS's `_base.html`: the two partials it includes ship inside the app and are
   found by the app-directories loader, so without it every page raises `TemplateDoesNotExist`,
   in production as well as under `DEBUG`. To run with no Google tag, install the app and leave
   `GOOGLE_ANALYTICS_MEASUREMENT_ID` unset — both partials then render nothing, and
   `record_google_analytics_event` is a no-op when the app is absent, so a project that
   overrides `_base.html` wholesale can still leave it out.

2. **Register two context processors**, in `TEMPLATES["OPTIONS"]["context_processors"]`:

   - `freedom_ls.deployment.context_processors.analytics_enabled`
   - `freedom_ls.google_tag.context_processors.google_tag_config`

   The first also gates PostHog: the snippet moved to
   `freedom_ls/base/templates/partials/posthog.html` and is now behind
   `{% if analytics_enabled and posthog_api_key %}`. Without it registered, **PostHog stops
   rendering too**. It suppresses analytics on the email-confirmation and password-reset pages,
   whose URLs carry a one-time token. A project that needs consent gating substitutes its own
   context processor returning `analytics_enabled` from its consent state.

3. **Set the environment variables you want** (all optional, all public IDs, all per
   environment) and read them into settings. `config/settings_base.py` and `.env.example` show
   the FLS wiring:

   - `GOOGLE_ANALYTICS_MEASUREMENT_ID` — unset means no GA4 and no Ads.
   - `GOOGLE_ADS_CONVERSION_ID` — needs the measurement ID above; the Ads tag rides on the GA4
     loader.
   - `GOOGLE_ADS_CONVERSION_LABELS` — comma-separated `event_name=label` pairs, parsed by
     `freedom_ls.google_tag.google_ads.parse_conversion_labels`. A malformed entry raises
     `ImproperlyConfigured` while settings are being built, so a typo fails the boot.

   Run `manage.py check` after setting them. Two new warnings exist, both silenceable via
   `SILENCED_SYSTEM_CHECKS`, neither blocking: `freedom_ls_google_tag.W001` (an Ads ID with no
   measurement ID) and `freedom_ls_google_tag.W002` (labels with no Ads ID).

4. **Extend your CSP** if you set a measurement ID. `SECURE_CSP_REPORT_ONLY` in
   `config/settings_base.py` gains the Google tag-manager, analytics and advertising hosts
   across `script-src`, `img-src`, `connect-src` and `frame-src`. Google calls
   `www.google.<country TLD>` for the visitor's country and CSP cannot wildcard a host's
   right-hand side, so FLS lists `www.google.co.za` by hand — **add the TLD for each country
   you serve**. The policy is report-only, so a gap shows up as reported violations rather
   than a broken tag.

5. **Review the four changed templates** if you override any of them:

   - `_base.html` — PostHog moved into `partials/posthog.html`; a new `{% block google_analytics %}`
     includes `partials/google_analytics.html` in the `<head>`; `partials/google_analytics_events.html`
     is included before `</body>`.
   - `_base_interface.html` — includes `partials/google_analytics_events.html` as the first
     thing inside `#interface-main`, so a boosted course-player navigation still emits events.
   - `express_interest_cta.html` — includes the events partial inside the swapped wrapper, so
     the event fires at the click rather than on the next full page.

   A page of yours that does not extend `_base.html` includes both partials itself to get the
   tag and its events.

6. **Update your privacy policy.** `legal_docs/_default/privacy.md` moved to version 1.2 with
   an analytics-and-advertising section. That file is the FLS placeholder — your own legal copy
   needs the equivalent disclosure, and bumping the version re-prompts learners for consent.

7. **Read the how-to before expecting reports.** `docs/how tos/google-analytics-and-ads.md`
   covers the one-off GA4 property and Google Ads account setup this code does not do.

No migrations, no new Python or npm packages, and no Tailwind rebuild: nothing in this branch
touches a model, a dependency manifest, or a template's utility classes.

Two notes on behaviour, not actions. **No consent banner ships.** For visitors in the EEA, the
UK and Switzerland the tag defaults Google Consent Mode to denied
(`CONSENT_MODE_DENIED_REGIONS` in `freedom_ls/google_tag/context_processors.py`); a deployment
serving those visitors adds its own banner and grants consent with
`gtag('consent', 'update', ...)`. And a downstream view records its own events through
`freedom_ls.google_tag.events.record_google_analytics_event`, which accepts any GA4-valid event
name — never pass anything a visitor typed.
