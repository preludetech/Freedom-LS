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

# Upgrade notes: referral-tracking-referer-host-normalisation

## Breaking changes

None. This change adds the module `freedom_ls/referral_tracking/referers.py` with two pure
functions, `normalised_host` and `referer_host`. Capture, `SignupAttribution`, the API and the CSV
export are unchanged, and the stored referer stays raw.

## Manual steps

None. A project that keeps its own copy of these helpers can import them from
`freedom_ls.referral_tracking.referers` and delete its copy. Two behaviours may differ from a
local copy: an `android-app://` referer returns the bare package name, and an IPv6 literal keeps
its address (`http://[::1]:8080/` returns `::1`, not `""`).
