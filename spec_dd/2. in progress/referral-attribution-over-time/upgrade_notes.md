---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS  # optional: default 90
  - REFERRAL_TRACKING_MAX_COOKIE_TOUCHES  # optional: default 10
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral-attribution-over-time

## Breaking changes

- `freedom_ls.learner_management.learner_actions.self_register` now returns the new
  `LearnerCourseRegistration` when it created one, and `None` otherwise. It used to return `True` or
  `False`. A downstream caller that compares the result with `True` (`is True`, `== True`) must
  change to a truthiness or `is not None` check. A plain `if self_register(...):` keeps working.

Nothing else downstream code calls changes shape. The attribution cookie's first-touch keys
(`COOKIE_KEYS`) and the `dict[str, str]` that `read_attribution_cookie` returns are unchanged. The
later landings go under a separate key, `tl`, which `read_attribution_cookie` does not return.
`set_attribution_cookie(response, first_touch)` still works with its original two arguments.

## Manual steps

- Run `manage.py migrate`. It applies `referral_tracking` migrations
  `0005_attributiontouch`, `0006_conversion` and `0007_attributiontouch_verbose_name_plural`, which
  add the `AttributionTouch` and `Conversion` tables. Existing accounts start with an empty touch
  timeline. Nothing is backfilled from `SignupAttribution`.
- Optional: two new settings, both with defaults.
  `REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS` (default 90) sets how far back a conversion looks for
  the touches in play. `REFERRAL_TRACKING_MAX_COOKIE_TOUCHES` (default 10) sets how many later
  landings the cookie keeps beside the first touch. A new warning,
  `freedom_ls_referral_tracking.W001`, fires at `manage.py check` when the window is shorter than
  `REFERRAL_TRACKING_COOKIE_MAX_AGE_DAYS`.
- Optional: touches are kept until an operator prunes them. To limit how long they are kept, schedule
  `manage.py prune_attribution_touches --older-than-days <N>`. Conversions are never pruned.
