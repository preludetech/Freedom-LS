---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/partials/form.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html
  - freedom_ls/panel_framework/templates/cotton/panel-page-header.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html
  - freedom_ls/panel_framework/templates/panel_framework/views/_instance_view_base.html
requires_settings_change: true
changed_settings:
  - SETUP_EMAIL_RESEND_SECONDS  # optional: new accounts setting, default 900
  - WEBHOOK_EVENT_TYPES  # hard only for a project that sets its own list: add the eight new types
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-7-learner-administration

## Breaking changes

None that stop a project booting. Three behaviour changes may matter to integrators:

- **Webhooks.** Eight new event types were added to `FLS_WEBHOOK_EVENT_TYPES` in
  `freedom_ls/base/webhook_event_types.py`: `course.unregistered`, `cohort.course_registered`,
  `cohort.course_unregistered`, `learner.added`, `learner.deactivated`, `learner.reactivated`,
  `cohort.member_added` and `cohort.member_removed`. A project that sets the
  `WEBHOOK_EVENT_TYPES` setting to its own list, rather than to `FLS_WEBHOOK_EVENT_TYPES` or a list
  built from it, must add them: `fire_webhook_event` raises `ValueError` on an unknown type, so the
  new learner actions would fail.
  `course.registered` now also fires when an inactive registration is reactivated. A move between
  cohorts fires `cohort.member_removed` then `cohort.member_added`, sharing a `move_id`.
- **Staff-created accounts do not fire `user.registered`.** They fire `learner.added` with
  `account_created: true`. A CRM listening only to `user.registered` will miss them.
- **Permissions.** `freedom_ls_accounts.change_user` is now in the permission registry and granted
  to the `site_admin` base role, so site admins can edit a learner's name. A project with its own
  roles config that should keep this ability must add the permission to its own role.

## Manual steps

1. Run `uv run manage.py migrate`. Migration
   `freedom_ls_learner_progress.0002_course_progress_cohort_constraint_deferrable` makes the
   `one_course_progress_per_cohort_registration` constraint on `CourseProgress` deferrable.
2. Run `uv run manage.py sync_role_permissions` so existing `site_admin` grants pick up
   `freedom_ls_accounts.change_user`.
3. Rebuild Tailwind (`npm run tailwind_build`): the new educator-interface templates use utility
   classes a downstream bundle must include. Run `collectstatic` as usual; the panel framework's
   `alpine-components.js` changed.
4. If you override any template in `changed_template_paths`, diff it against the new FLS version
   and re-apply your changes. `partials/form.html` no longer renders a label for hidden fields.
5. Optional: set `SETUP_EMAIL_RESEND_SECONDS` (default `900`) to change how soon staff may resend
   the account setup email to the same person. The guard lives in the Django cache, so it is only
   as strong as the cache: with `LocMemCache` it is per process.
6. Optional: the new account setup email uses
   `freedom_ls/accounts/templates/account/email/account_setup_subject.txt`,
   `account_setup_message.txt` and `account_setup_message.html`. There is no subject setting;
   override `account_setup_subject.txt` to change it.
