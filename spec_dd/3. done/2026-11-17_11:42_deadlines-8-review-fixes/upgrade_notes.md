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

# Upgrade notes: deadlines-8-review-fixes

## Breaking changes

None.

The `freedom_ls.content_engine.signals.collection_items_synced` signal now also sends a `moved`
keyword argument: a list of `freedom_ls.content_engine.moved_children.MovedChild`, one for each
child the load moved off a row it left behind. A receiver that accepts `**kwargs`, as Django
requires, keeps working unchanged. A project with its own receiver that reconciles moved
children can read `moved` instead of working the moves out from `created` and `written`.

## Manual steps

None. No migrations, settings, templates or packages changed.
