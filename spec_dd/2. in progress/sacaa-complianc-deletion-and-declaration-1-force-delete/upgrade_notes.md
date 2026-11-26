---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
requires_settings_change: true
changed_settings:
  - MIDDLEWARE  # hard: freedom_ls_accounts.E004 fails boot without LastActiveMiddleware
  - LAST_ACTIVE_WRITE_SECONDS  # optional: defaults to 300
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-complianc-deletion-and-declaration-1-force-delete

## Breaking changes

- **Ordinary user delete is gone.** `freedom_ls.accounts.admin.UserAdmin.has_delete_permission`
  now returns `False`, so the user admin has no Delete button, no "Delete selected users" action,
  and `/admin/freedom_ls_accounts/user/<pk>/delete/` answers 403. A superuser erases a user with
  **Force delete**, which asks for a reason and writes a `user.deleted` audit entry.
- **The User admin is re-registered by `freedom_ls.learner_progress.admin`.** That module
  unregisters `User` and registers `freedom_ls.learner_progress.admin.UserAdmin` (the accounts
  admin plus `ForceDeleteAdminMixin`). A project that re-registers its own User admin should
  subclass `freedom_ls.learner_progress.admin.UserAdmin`, not `freedom_ls.accounts.admin.UserAdmin`,
  or it loses force delete.
- **`Learner` now has an admin.** `freedom_ls.learner_progress.admin.LearnerAdmin` is registered.
  It is read-only and carries learner force delete (`learner.removed` audit entry). A project that
  registers its own `Learner` admin now gets `AlreadyRegistered`; unregister FLS's first.
- **`acting_user` moved.** `freedom_ls.api_admin.audit.acting_user` is now
  `freedom_ls.audit_log.writer.acting_user`. Update any import of the old path.
- **Educator "Last active" changed source.** The educator learner table and quick view read
  `User.last_active` instead of the latest `CourseProgress.last_accessed_time`. The quick view
  template now prints `{{ last_active }}` as given; the panel supplies the "Never" text.
- **Protected admin models and force delete.** A model whose admin refuses delete blocks a user
  force delete unless its app adds it to `freedom_ls.accounts.admin.USER_ERASURE_CASCADE_MODELS`.
  A downstream model with such an admin and a foreign key to `User` or `Learner` must add itself
  there from its admin module. Records a receiver erases with no foreign key to the user go in
  `freedom_ls.accounts.admin.USER_ERASURE_UNLINKED_RECORDS` so the confirmation page counts them.

## Manual steps

- Add `"freedom_ls.accounts.middleware.LastActiveMiddleware"` to `MIDDLEWARE`, after
  `django.contrib.auth.middleware.AuthenticationMiddleware`. The system check
  `freedom_ls_accounts.E004` fails `manage.py check` and boot until it is there.
- Optionally set `LAST_ACTIVE_WRITE_SECONDS` (default 300): the minimum gap between two writes of
  one user's `last_active`.
- Run `manage.py migrate`. `freedom_ls_accounts.0006_user_last_active` adds `User.last_active`, and
  `freedom_ls_learner_progress.0004_backfill_user_last_active` fills it for existing users with
  the later of `last_login` and their latest course activity.
- If you override `educator_interface/quick_views/learner.html`, re-apply your changes against the
  new "Last active" row.
