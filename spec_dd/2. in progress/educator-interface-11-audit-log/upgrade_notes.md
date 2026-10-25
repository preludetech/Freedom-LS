---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_learner_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/remove_from_cohort_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/remove_role_confirmation.html          # renamed to deactivate_role_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/suspend_member_confirmation.html       # renamed to deactivate_member_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/unregister_confirmation.html           # renamed to deactivate_cohort_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/unregister_from_course_confirmation.html  # renamed to deactivate_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_history.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/reregister_confirmation.html           # renamed to reactivate_registration_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_member.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/change_cohorts.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/unregister.html            # renamed to deactivate_registration.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member_actions.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member_roles.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS            # hard: add "freedom_ls.audit_log" or the project fails to boot
  - AUDIT_LOG_EXTRA_ACTIONS   # optional: defaults to {}
  - AUDIT_LOG_RETENTION_DAYS  # optional: defaults to None (keep forever)
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-11-audit-log

FLS now keeps an append-only audit log of administrative changes: learner state, cohort
membership, course registrations, cohort lifecycle, learner renames, setup emails, and role and
member changes. Educators read it on a learner's and a cohort's History tab and in a new
organisation "Audit log" section with filters. Several confirm dialogs gain an optional reason
field. The Django admin shows the log read-only. History starts at the upgrade; past actions are
not backfilled.

## Breaking changes

- **New required app.** `freedom_ls.learner_management`, `freedom_ls.role_based_permissions` and
  `freedom_ls.educator_interface` now import `freedom_ls.audit_log` at runtime, so
  `"freedom_ls.audit_log"` must be in your `INSTALLED_APPS`. No system check covers this; leaving
  it out makes Django fail at startup with an error that the `AuditLogEntry` model is not in an
  installed app. FLS puts it straight after `"freedom_ls.organisations"`.
- **New permission on the admin roles.** `freedom_ls_audit_log.view_auditlogentry` is part of
  `site_admin` and `organisation_admin` in `BASE_ROLES`
  (`freedom_ls/role_based_permissions/roles.py`). A role config named in
  `FREEDOMLS_PERMISSIONS_MODULES` that extends `BASE_ROLES` picks it up. One that writes its own
  permission sets must add the permission to its site and organisation admin roles, or those
  users won't see the History tabs or the Audit log section.
- **Organisations with audit entries can't be deleted.** `AuditLogEntry.organisation` uses
  `on_delete=PROTECT`, so deleting an organisation that has entries raises `ProtectedError`.
  Entries can't be edited or deleted from application code either: `save()` on an existing entry,
  `delete()`, and queryset `update()` and `delete()` raise
  `freedom_ls.audit_log.exceptions.AppendOnlyError`. The only supported way to remove entries is
  the `prune_audit_log` command.
- **Template removed.** `educator_interface/panels/learner_history.html` (the old empty History
  placeholder) is gone. The learner History tab is now a data table. An override of the old path is
  no longer used.
- **Confirm dialogs restructured.** The modal templates in `changed_template_paths` used to hold the
  `<form>` around the confirm button only. The form now wraps the whole dialog body, so the optional
  reason (`educator_interface/partials/reason_field.html`) posts with it. An override built on the
  old markup has no reason field.
- **One vocabulary for changes.** The domain glossary now has a "Changes" section: a change is
  named once as `noun.verb`, setting an `is_active` flag to False is *deactivating* and the state is
  *Inactive*, and a webhook event type that is also an audit action is the same string. Everything
  below follows from it.
- **Webhook event types renamed.** The codes below are gone; the new ones are the audit action codes.
  Migration `freedom_ls_webhooks.0002_rename_event_types` rewrites every `WebhookEndpoint.event_types`
  list, subscribing an endpoint to both new codes where one split. Past `WebhookEvent` rows keep the
  code that was sent, so the admin's history and filters still show old codes for old events. A
  receiver that branches on the envelope's `type`, a body template that reads `event.type`, and a
  downstream `WEBHOOK_EVENT_TYPES` setting that lists codes all need the new names; `fire_webhook_event`
  raises `ValueError` for a code the setting no longer lists. The payloads are unchanged.

  | Old | New |
  | --- | --- |
  | `user.registered` | `user.signed_up` |
  | `course.registered` | `registration.added` for a new registration, `registration.reactivated` for a reactivated one |
  | `course.unregistered` | `registration.deactivated` |
  | `cohort.course_registered` | `cohort_registration.added`, `cohort_registration.reactivated` |
  | `cohort.course_unregistered` | `cohort_registration.deactivated` |
  | `cohort.member_added` | `cohort_membership.added` |
  | `cohort.member_removed` | `cohort_membership.removed` |

  The notification category `course.registered` is a different registry and is unchanged.
- **Educator interface wording.** Unregister becomes Deactivate on a course registration, Re-register
  becomes Reactivate, Suspend becomes Deactivate on a member, and Remove becomes Deactivate on a role.
  The member badge and the learner status read "Inactive" (the learner status filter value `removed`
  is now `inactive`). Dialog headers and loading text change to match. An override of these templates,
  or a test that looks for the old labels, needs the same change.
- **Identifiers renamed to match.** Template files: see the `# renamed to` notes in
  `changed_template_paths`. Action classes and `action_name` slugs (the `/__actions/<slug>` URL and the
  `row_action_urls` key): `UnregisterCohortFromCourseAction`/`unregister` →
  `DeactivateCohortRegistrationAction`/`deactivate_cohort_registration`;
  `UnregisterLearnerFromCourseAction`/`unregister_from_course` → `DeactivateRegistrationAction`/
  `deactivate_registration`; `ReregisterLearnerForCourseAction`/`reregister_for_course` →
  `ReactivateRegistrationAction`/`reactivate_registration`; `RemoveRoleAction`/`remove_role` →
  `DeactivateRoleAction`/`deactivate_role`; `SuspendMemberAction`/`suspend` →
  `DeactivateMemberAction`/`deactivate`. Service functions: `unregister_from_course` →
  `deactivate_registration`, `unregister_cohort_from_course` → `deactivate_cohort_registration`
  (`learner_management`); `remove_role` → `deactivate_role` (`learner_management.role_assignment`);
  `remove_object_role`, `remove_site_role`, `remove_system_role` → `deactivate_object_role`,
  `deactivate_site_role`, `deactivate_system_role`, with `removed_by` → `deactivated_by`
  (`role_based_permissions.utils`; `delete_role_rows_for` keeps `removed_by`, since it deletes).
  `learners_visible_to(include_removed=...)` → `include_inactive`; `LearnerStatus.REMOVED` →
  `LearnerStatus.INACTIVE`. Member rows expose `is_inactive` instead of `is_suspended`.
- **Audit action codes.** A role row deleted along with its cohort is now `role.removed` ("Role
  removed") rather than `role.deactivated`; adding a learner by email who was inactive here writes
  `learner.reactivated` rather than `learner.added` with a `reactivated` outcome.

## Additions

- `freedom_ls.audit_log.writer.record_entry` and `record_run_summary` let downstream code write its
  own entries. `record_entry` opens no transaction, so call it inside the transaction of the change
  it records; a rollback then leaves no entry. Unknown action codes raise `ValueError`.
- `AUDIT_LOG_EXTRA_ACTIONS` (default `{}`) is a `{code: label}` dict that registers downstream
  action codes. System check `freedom_ls_audit_log.E001` fails at boot when a code is already an
  FLS action code or isn't a lower-case `noun.verb` string.
- `AUDIT_LOG_RETENTION_DAYS` (default `None`) is the age in days that
  `manage.py prune_audit_log` deletes past when you run it without `--older-than`. The log is kept
  forever unless you schedule the command. `--dry-run` reports the count without deleting.

## Manual steps

1. Add `"freedom_ls.audit_log"` to `INSTALLED_APPS`.
2. Run `uv run manage.py migrate` to create the `freedom_ls_audit_log` tables (migrations `0001_initial`
   and `0002_alter_auditlogentry_options`) and to rewrite webhook subscriptions
   (`freedom_ls_webhooks.0002_rename_event_types`).
3. Run `uv run manage.py check`. It confirms the app loads and flags any bad
   `AUDIT_LOG_EXTRA_ACTIONS` code as `freedom_ls_audit_log.E001`.
4. If your role config writes its own permission sets, add
   `freedom_ls_audit_log.view_auditlogentry` to your site and organisation admin roles.
5. If you override any template listed in `changed_template_paths`, apply your changes again on top of
   the new version. Remove an override of `panels/learner_history.html`.
6. Rebuild Tailwind, because the new audit log templates use utility classes your bundle may not
   contain yet.
7. Optionally set `AUDIT_LOG_RETENTION_DAYS` and schedule `manage.py prune_audit_log` if you don't
   want to keep entries forever.
8. Tell every webhook receiver about the renamed event types, and update any `WEBHOOK_EVENT_TYPES`
   setting, body template or test of your own that names an old code.
