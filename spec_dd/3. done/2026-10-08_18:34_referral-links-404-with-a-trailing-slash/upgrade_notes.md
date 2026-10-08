---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - MIDDLEWARE  # optional: add RemoveSlashMiddleware after CommonMiddleware
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral-links-404-with-a-trailing-slash

## Breaking changes

None.

Referral links now accept a trailing slash. `/go/<code>/` and `/d/<code>/` (any letter case)
are served directly by `follow_referral_code`, the same as `/go/<code>` and `/d/<code>`: same
door, one hit recorded, same redirect target, query string kept, no extra hop. This comes from
the route patterns in `freedom_ls/referral_tracking/urls.py`, so it needs no settings change.
`reverse("referral_tracking:follow_go", ...)` and `reverse("referral_tracking:follow_d", ...)`
still return the slashless URL.

## Manual steps

1. **Remove any trailing-slash shim for referral links.** If your project added its own
   `re_path` entries in its root URLconf to catch `/go/<code>/` or `/d/<code>/` and call
   `follow_referral_code`, delete them along with their tests. FLS's own routes now cover both
   doors.

2. **Optional: add `RemoveSlashMiddleware` to your `MIDDLEWARE`.** FLS's settings now include
   `freedom_ls.base.middleware.RemoveSlashMiddleware`, placed directly after
   `django.middleware.common.CommonMiddleware`. It is `APPEND_SLASH` in reverse. When a
   request 404s, its path ends in exactly one `/`, the path doesn't resolve and the path
   without the slash does, it answers a 301 to the slashless path with the query string kept.
   Without it, any route whose pattern has no trailing slash 404s when a slash is added. That
   covers the learner form routes in `freedom_ls/learner_interface/urls.py` (`.../start_form/`,
   `.../complete/`, `.../submit-and-exit/`, `.../fill_form/<n>/`) and any slashless routes in
   your own URLconf, such as a `robots.txt` route. Downstream projects keep their own `MIDDLEWARE` list, so add the
   entry yourself:

   ```python
   MIDDLEWARE = [
       ...
       "django.middleware.common.CommonMiddleware",
       "freedom_ls.base.middleware.RemoveSlashMiddleware",
       ...
   ]
   ```

   It leaves every other response alone: a 404 raised by a view whose route matched, the root
   `/`, a path ending in `//`, and a path whose slashless form doesn't resolve either. No
   system check requires it.
