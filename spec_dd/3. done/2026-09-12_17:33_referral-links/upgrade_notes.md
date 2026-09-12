---
requires_migrations: true
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - REFERRAL_TRACKING_INACTIVE_DESTINATION  # optional: defaults to "/", but any value set is enforced at boot by freedom_ls_referral_tracking.E001
  - REFERRAL_TRACKING_HIT_LOG_LIMIT  # optional
  - REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS  # optional
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral_links

A builder can now create a `ReferralCode` in the admin, hand out `/go/{code}` or `/d/{CODE}`, and
see the hits it draws. The code joins `SignupAttribution` and `FirstTouchCount` as a seventh
attribution key. See `docs/product/referral-codes.md`.

## Breaking changes

- **`/go/` and `/d/` become FLS routes at the site root.** Once the include below is added, any
  route your own project serves under those two prefixes is shadowed by whichever include comes
  first in your root URLconf. Check for a collision before adding the include.
- **`FirstTouchCount` rows split for the upgrade day.** `key_hash` is computed over
  `ATTRIBUTION_KEY_FIELDS`, which gains `referral_code`, so a campaign tallied both before and
  after the deploy lands on two rows for that one day. The tally is comparative; no rehash
  migration is provided.
- **Rolling back after the upgrade discards live attribution cookies.** The cookie payload gains an
  `rc` key, and the pre-upgrade reader rejects a payload holding a key it does not know. A visitor
  who landed after the upgrade would be re-minted, losing their original first touch.
- **`first_touch_from_request()` returns a `referral_code` key, not `ref`.** The `ref` query
  parameter is the one tracked parameter whose field name differs from the parameter that fills it.
  Only relevant if you call that function or read the payload dict directly.

## Manual steps

1. Add the redirect routes to your root URLconf, with the single-purpose mounts and ahead of any
   app mounted at `""`:

   ```python
   path("", include("freedom_ls.referral_tracking.urls")),
   ```

   Without it, `ReferralCode` still records and the admin still works, but every printed link 404s.

2. Run `manage.py migrate`. Three migrations land in `freedom_ls_referral_tracking`:
   `0002_firsttouchcount_referral_code_and_more`,
   `0003_referralcodehit_freedom_ls__hit_at_16a0f2_idx` and
   `0004_alter_referralcode_hit_count`.

3. Run `collectstatic`. The `ReferralCode` change form loads two new static files,
   `referral_tracking/css/copy_button.css` and `referral_tracking/js/copy_button.js`, for the copy
   buttons beside the Go URL and D URL.

4. Run `manage.py check`. If you set `REFERRAL_TRACKING_INACTIVE_DESTINATION`, it must be a path on
   your own site — one leading slash, no host, no whitespace, and not one of the redirect routes.
   A value that fails that test raises `freedom_ls_referral_tracking.E001` at boot. Leaving it
   unset keeps the default `/`.

5. Decide on hit-log retention and schedule the prune yourself. Nothing trims the log:

   ```
   manage.py prune_referral_code_hits --older-than-days 30
   ```

   It deletes hits across every site and leaves `hit_count` and `last_hit_at` untouched.

6. Optional: tune the hit-log cap. `REFERRAL_TRACKING_HIT_LOG_LIMIT` (default 30) is how many hits
   on one code one address may write per `REFERRAL_TRACKING_HIT_LOG_WINDOW_SECONDS` (default 3600);
   0 logs every hit. Throttled hits still redirect, and they move neither `hit_count` nor the log.
   The counter lives in Django's default cache, so on a per-process backend such as `LocMemCache`
   the cap applies per process. `freedom_ls.deployment.settings_defaults.DATABASE_CACHES` is the
   shared default FLS itself uses in production.
