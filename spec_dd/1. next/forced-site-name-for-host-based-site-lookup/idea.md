# Idea: make FORCE_SITE_NAME reach Django's own site lookup

## What

`FORCE_SITE_NAME` makes FLS's own site lookup serve one named Site on any host, which is how a dev
server or QA run on a random port sees the right site's data. Django's `get_current_site` and allauth
still match the request host against `Site.domain`, so on any port but the Site's own, the login,
signup and admin pages fail with `Site.DoesNotExist`.

Make the forced site reach that host-based lookup too, in development only.

## Why

Every project that uses `FORCE_SITE_NAME` for QA hits this the first time it starts a dev server on a
port other than the Site's domain. First-Class-LMS fixed it with a small middleware, and this run's
QA of First-Class-LMS depended on that middleware to log in at all.

## Reference implementation

First-Class-LMS, `apps/project_setup/middleware.py` (`ForcedSiteHostMiddleware`), added in
`config/settings_dev.py` ahead of FLS's `CurrentSiteMiddleware`. It seeds Django's `SITE_CACHE` under
the request host with the forced Site. That touches a private Django cache, which the spec has to
weigh. The project would delete its copy.

## Settled

- It belongs in `site_aware_models`, beside `FORCE_SITE_NAME` and the cached site lookup it consumes.
- It is development-only and must never be active in production settings.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-10-30).
