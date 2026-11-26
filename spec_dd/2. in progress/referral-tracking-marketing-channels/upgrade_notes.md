---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: referral-tracking-marketing-channels

## Breaking changes

None. The change adds one new pure module, `freedom_ls/referral_tracking/channels.py`, and its
tests. No model, migration, setting, template, URL or dependency changes.

## Manual steps

None. No action needed.

Optional: a project that classifies `SignupAttribution` rows into marketing channels with its own
code can switch to `freedom_ls.referral_tracking.channels.classify`, which takes a `FirstTouch`
(or `None`) and returns a `ChannelResult` holding a `Channel`, a `ChannelBasis` and a source
platform. `has_signal` reports whether a first touch carried any attribution signal. The channel
tables are module constants; a project that needs extra rules wraps `classify` rather than
editing them.
