---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/_base.html                                                                               # changed
  - freedom_ls/base/templates/_base_interface.html                                                                     # changed
  - freedom_ls/base/templates/cotton/button.html                                                                       # changed
  - freedom_ls/base/templates/cotton/data-table-cells/boolean.html                                                     # deleted
  - freedom_ls/base/templates/cotton/data-table-cells/link.html                                                        # deleted
  - freedom_ls/base/templates/cotton/data-table.html                                                                   # deleted
  - freedom_ls/base/templates/cotton/dropdown-menu.html                                                                # changed
  - freedom_ls/base/templates/cotton/modal.html                                                                        # deleted
  - freedom_ls/base/templates/cotton/pagination.html                                                                   # changed
  - freedom_ls/base/templates/cotton/scroll-table-labels.html                                                          # deleted
  - freedom_ls/base/templates/partials/form.html                                                                       # changed
  - freedom_ls/base/templates/partials/header_bar.html                                                                 # changed
  - freedom_ls/base/templates/partials/header_bar_user_menu.html                                                       # changed
  - freedom_ls/comms/templates/comms/partials/messages_button.html                                                     # new
  - freedom_ls/comms/templates/comms/partials/notification_bell.html                                                   # new
  - freedom_ls/content_engine/templates/cotton/picture.html                                                            # changed
  - freedom_ls/course_applications/templates/course_applications/partials/applicant_details_field.html                 # new
  - freedom_ls/course_applications/templates/course_applications/partials/claim_link_notice.html                       # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/_link_to_cohort.html                   # deleted
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_courses.html                    # changed
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html                      # changed
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_member_actions.html             # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html                   # changed
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member.html                            # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/member_roles.html                      # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/membership_actions.html                # new
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/progress_check.html                    # deleted
  - freedom_ls/educator_interface/templates/educator_interface/interface.html                                          # changed
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_preview.html                             # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_member.html                                   # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/change_cohorts.html                               # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/cohort_inactive.html                              # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_cohort_registration_confirmation.html  # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_confirmation.html                      # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_learner_confirmation.html              # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_member_confirmation.html               # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_registration_confirmation.html         # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_role_confirmation.html                 # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/delete_cohort_confirmation.html                   # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/move_confirmation.html                            # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_confirmation.html                      # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_learner_confirmation.html              # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_member_confirmation.html               # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/reactivate_registration_confirmation.html         # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/add_learner_result.html                          # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/cohort_name_form.html                         # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/remove_from_cohort_confirmation.html              # new
  - freedom_ls/educator_interface/templates/educator_interface/modal/resend_setup_email_confirmation.html              # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/_lazy_region.html                                # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_needs_attention_region.html               # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_body_region.html                   # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard.html                                   # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html                            # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html                             # new
  - freedom_ls/educator_interface/templates/educator_interface/panels/learner_registrations.html                       # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html                     # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/instance_details_panel.html                    # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/learner_import_result_body.html                # new
  - freedom_ls/educator_interface/templates/educator_interface/partials/list_view.html                                 # deleted
  - freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html                     # changed
  - freedom_ls/educator_interface/templates/educator_interface/partials/panel_container.html                           # deleted
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/cohort.html                                 # new
  - freedom_ls/educator_interface/templates/educator_interface/quick_views/learner.html                                # new
  - freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html                                                  # changed
  - freedom_ls/form_engine/templates/form_engine/inputs/long_text.html                                                 # changed
  - freedom_ls/form_engine/templates/form_engine/inputs/text_input.html                                                # changed
  - freedom_ls/panel_framework/templates/cotton/data-table-card.html                                                   # new
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/link.html                                             # new
  - freedom_ls/panel_framework/templates/cotton/data-table-cells/text.html                                             # new
  - freedom_ls/panel_framework/templates/cotton/data-table.html                                                        # new
  - freedom_ls/panel_framework/templates/cotton/modal-header.html                                                      # new
  - freedom_ls/panel_framework/templates/cotton/panel-attention-row.html                                               # new
  - freedom_ls/panel_framework/templates/cotton/panel-avatar-chip.html                                                 # new
  - freedom_ls/panel_framework/templates/cotton/panel-card.html                                                        # new
  - freedom_ls/panel_framework/templates/cotton/panel-definition-list.html                                             # new
  - freedom_ls/panel_framework/templates/cotton/panel-definition-row.html                                              # new
  - freedom_ls/panel_framework/templates/cotton/panel-page-header.html                                                 # new
  - freedom_ls/panel_framework/templates/cotton/panel-search-field.html                                                # new
  - freedom_ls/panel_framework/templates/cotton/panel-stat-tile.html                                                   # new
  - freedom_ls/panel_framework/templates/cotton/panel-status-badge.html                                                # new
  - freedom_ls/panel_framework/templates/panel_framework/modal/delete_confirmation.html                                # new
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html                                               # new
  - freedom_ls/panel_framework/templates/panel_framework/modal/read_only.html                                          # new
  - freedom_ls/panel_framework/templates/panel_framework/navigation_response.html                                      # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_base.html                                  # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_data_table_region_base.html                           # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_instance_details_base.html                            # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_panel_base.html                                       # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_nav.html                                          # new
  - freedom_ls/panel_framework/templates/panel_framework/panels/_tab_set_base.html                                     # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_denied.html                                   # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_unavailable.html                              # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html                                     # changed
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation.html                               # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_form.html                          # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_message.html                       # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result.html                                     # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_result_body.html                                # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html                             # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/instance_actions.html                                # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/instance_details_panel.html                          # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_refresh.html                                    # changed
  - freedom_ls/panel_framework/templates/panel_framework/partials/list_view.html                                       # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/main_content.html                                    # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_form.html                                      # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/modal_host.html                                      # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/panel_container.html                                 # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/panel_toggle.html                                    # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/quick_view_host.html                                 # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html                                     # changed
  - freedom_ls/panel_framework/templates/panel_framework/partials/tab_container.html                                   # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/tab_panels.html                                      # deleted
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_selection_bar.html                             # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_sheet.html                                     # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_toolbar.html                                   # new
  - freedom_ls/panel_framework/templates/panel_framework/partials/table_footer.html                                    # new
  - freedom_ls/panel_framework/templates/panel_framework/quick_view/frame.html                                         # new
  - freedom_ls/panel_framework/templates/panel_framework/views/_base_view_base.html                                    # new
  - freedom_ls/panel_framework/templates/panel_framework/views/_bulk_confirmation_base.html                            # new
  - freedom_ls/panel_framework/templates/panel_framework/views/_instance_view_base.html                                # new
  - freedom_ls/panel_framework/templates/panel_framework/views/_list_view_base.html                                    # new
  - freedom_ls/panel_framework/templates/panel_framework/views/_main_base.html                                         # new
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS               # hard: add "freedom_ls.audit_log" or the project fails to boot
  - WEBHOOK_EVENT_TYPES          # hard only for a project that sets its own list: use the final event codes below
  - SETUP_EMAIL_RESEND_SECONDS   # optional: default 900
  - REPORTS_SCREEN_CACHE_SECONDS # optional: default 300
  - BULK_BACKGROUND_THRESHOLD    # optional: default 250
  - LEARNER_IMPORT_MAX_ROWS      # optional: default 2000
  - BULK_RECORD_RETENTION_DAYS   # optional: default 30
  - AUDIT_LOG_EXTRA_ACTIONS      # optional: default {}
  - AUDIT_LOG_RETENTION_DAYS     # optional: default None (keep forever)
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator interface rebuild (specs 1 to 12)

These notes cover the whole educator interface rebuild in one pass, for a downstream project that
upgrades across it at once: specs 1 to 12 and `educator-interface-looks-good`. They name every
template, class, event and setting by its final name. A project that has already applied some of
the per-spec notes should follow those instead (see [Per-spec notes](#per-spec-notes)), because
`update_fls` reads them one spec at a time and this file repeats their steps.

## Do you need to act?

Every project:

- [ ] Add `"freedom_ls.audit_log"` to `INSTALLED_APPS` ([Settings](#settings)).
- [ ] Run `uv run manage.py migrate`, then create `OrganisationMember` rows for existing role
      holders ([Migrations and data](#migrations-and-data)). Until then, every organisation
      admin, cohort admin and cohort viewer loses access.
- [ ] Run `uv run manage.py sync_role_permissions` and `uv run manage.py check`.
- [ ] Rebuild Tailwind (`npm run tailwind_build`) and run `collectstatic`.
- [ ] Re-select the event types on every webhook endpoint ([Webhook events](#webhook-events)).
- [ ] Make sure the `db_worker` process runs and `fls_run_housekeeping` is scheduled
      ([Background work](#background-work)).

Only if your project does this:

- [ ] Names a role key, or lists modules in `FREEDOMLS_PERMISSIONS_MODULES`: see [Roles and permissions](#roles-and-permissions).
- [ ] Grants educator access with guardian `assign_perm`: see [Roles and permissions](#roles-and-permissions).
- [ ] Sets `WEBHOOK_EVENT_TYPES` to its own list, or has a webhook receiver: see [Webhook events](#webhook-events).
- [ ] Builds its own interface on `freedom_ls.panel_framework`: see [Panel framework API](#panel-framework-api).
- [ ] Shadows any template in `changed_template_paths`: see [Templates](#templates).
- [ ] Subclasses or imports educator interface classes: see [Educator interface code](#educator-interface-code).
- [ ] Listens for htmx events or replaced `alpine-components.js`: see [Front end](#front-end).
- [ ] Uses `FREEDOM_LS_ICON_OVERRIDES` or a custom `FREEDOM_LS_ICON_BACKEND`: see [Icons](#icons).
- [ ] Runs PgBouncer in transaction mode or sync Gunicorn workers: see [Background work](#background-work).

## Settings

- **`INSTALLED_APPS`** (hard). Add `"freedom_ls.audit_log"`; FLS puts it straight after
  `"freedom_ls.organisations"`. `freedom_ls.learner_management`, `freedom_ls.role_based_permissions`
  and `freedom_ls.educator_interface` import it at runtime. No system check covers this: without it
  Django fails at startup because the `AuditLogEntry` model is not in an installed app.
- **`WEBHOOK_EVENT_TYPES`** (hard only if you set your own list). `fire_webhook_event` raises
  `ValueError` on a code the setting does not list. Build the list from `FLS_WEBHOOK_EVENT_TYPES`
  in `freedom_ls/base/webhook_event_types.py`, or add every code in
  [Webhook events](#webhook-events).
- Optional, set only to change the default:
  - `SETUP_EMAIL_RESEND_SECONDS` (default `900`): how soon staff may resend the account setup
    email to the same person. The guard lives in the Django cache, so with `LocMemCache` it is per
    process.
  - `REPORTS_SCREEN_CACHE_SECONDS` (default `300`): how long the on-screen report and dashboard
    figures are cached in the `default` cache. Use a cache shared across workers in production.
  - `BULK_BACKGROUND_THRESHOLD` (default `250`): bulk runs and learner imports above this many
    rows run as background tasks.
  - `LEARNER_IMPORT_MAX_ROWS` (default `2000`): the largest learner import file accepted.
  - `BULK_RECORD_RETENTION_DAYS` (default `30`): how long `fls_run_housekeeping` keeps finished
    bulk runs and imports.
  - `AUDIT_LOG_EXTRA_ACTIONS` (default `{}`): a `{code: label}` dict of your own audit action
    codes. System check `freedom_ls_audit_log.E001` fails at boot for a code that is already an FLS
    code or is not a lower-case `noun.verb` string.
  - `AUDIT_LOG_RETENTION_DAYS` (default `None`, keep forever): the age `manage.py prune_audit_log`
    deletes past when run without `--older-than`. Schedule the command to use it.

## Migrations and data

1. Run `uv run manage.py migrate`. The rebuild adds:
   - `freedom_ls_role_based_permissions`: `0002_rename_educator_roles` (data: rewrites the old
     role keys on existing assignments) and `0003_alter_objectroleassignment_options_and_more`.
   - `freedom_ls_learner_management`: `0003_organisationmember`,
     `0004_alter_cohort_options_alter_learner_options`, `0005_cohort_is_active` (every existing
     cohort becomes active), `0006_delete_orphan_cohort_role_rows` (data: deletes role assignments
     and guardian rows whose cohort no longer exists) and `0009_learnerimport_learnerimportrow`.
   - `freedom_ls_learner_progress`: `0002_course_progress_cohort_constraint_deferrable`.
   - `freedom_ls_panel_framework`: `0001_initial` (the bulk run record).
   - `freedom_ls_audit_log`: `0001_initial` to `0004_actor_index_and_delete_handler`.
2. **Create `OrganisationMember` rows for existing role holders.** An organisation admin, cohort
   admin or cohort viewer role counts only while the person is an active `OrganisationMember` of
   that organisation. New grants create the row, but no migration backfills existing ones. Run
   this once in `uv run manage.py shell`. It is idempotent and never reactivates a row someone
   deactivated:

   ```python
   from freedom_ls.learner_management.models import Cohort
   from freedom_ls.learner_management.utils import ensure_organisation_member
   from freedom_ls.organisations.models import Organisation
   from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

   for assignment in ObjectRoleAssignment._base_manager.filter(is_active=True).select_related("user"):
       target = assignment.target
       if isinstance(target, Organisation):
           ensure_organisation_member(assignment.user, target)
       elif isinstance(target, Cohort):
           ensure_organisation_member(assignment.user, target.organisation)
   ```

3. Run `uv run manage.py sync_role_permissions` so existing grants pick up the new permission
   sets, then `uv run manage.py validate_role_permissions` and `uv run manage.py check`.

Audit history starts at the upgrade; past actions are not backfilled. An organisation with audit
entries cannot be deleted (`AuditLogEntry.organisation` is `PROTECT`), and entries can be removed
only with `prune_audit_log`.

## Roles and permissions

- **Role keys renamed, no alias.** In `freedom_ls.role_based_permissions.roles.BASE_ROLES`:
  `organisation_staff` is `organisation_admin`, `instructor` is `cohort_admin`, `ta` is
  `cohort_viewer`. `site_admin` keeps its key. A module in `FREEDOMLS_PERMISSIONS_MODULES` that
  inherits from or overrides an old key fails at import. Code, fixtures and tests that pass an old
  key to `assign_object_role` or `assign_site_role` fail too.
- **Every role's permission set changed**, and the role descriptions were rewritten. New
  permissions include `freedom_ls_learner_management.download_cohort_report` (needed to generate
  and download a cohort report), `freedom_ls_accounts.change_user` (site admin; edits a learner's
  name) and `freedom_ls_audit_log.view_auditlogentry` (site and organisation admin; the History
  tabs and the Audit log). A role config that writes its own permission sets must add these.
- **Guardian rows no longer decide educator visibility.**
  `freedom_ls.learner_management.capabilities.can(user, capability, scope)` reads role
  assignments only. Replace `assign_perm` grants for educator access with `assign_object_role` or
  `assign_site_role` from `freedom_ls.role_based_permissions.utils`.
- **Role removal is deactivation.** `deactivate_object_role`, `deactivate_site_role` and
  `deactivate_system_role` in `freedom_ls.role_based_permissions.utils` take `deactivated_by`.
  `deactivate_site_role` raises `RoleChangeRefused` (`freedom_ls/role_based_permissions/exceptions.py`)
  for the last active site admin. `assign_object_role` and `assign_site_role` move `assigned_at`
  when they reactivate an assignment or change its grantor.
- **An inactive cohort grants no course access.** Check access through
  `freedom_ls.learner_management.queries.access_granting_cohort_registrations()`, not a direct
  `CohortCourseRegistration.objects.filter(is_active=True)`. The messaging policy ignores inactive
  cohorts when it looks for peers.

## Webhook events

Final event codes, as listed in `FLS_WEBHOOK_EVENT_TYPES`:

| Code | Fires when |
|---|---|
| `user.signed_up` | Someone signs up themselves (was `user.registered`). Staff-created accounts fire `learner.added` instead. |
| `course.completed` | Unchanged. |
| `registration.added` | A learner is registered for a course (was `course.registered`). |
| `registration.reactivated` | An inactive registration is reactivated (was `course.registered`). |
| `registration.deactivated` | A registration is deactivated. |
| `cohort_registration.added` | A cohort is registered for a course. |
| `cohort_registration.reactivated` | A cohort's inactive registration is reactivated. |
| `cohort_registration.deactivated` | A cohort's registration is deactivated. |
| `learner.added` | A learner is added to an organisation; `account_created` says whether an account was made. |
| `learner.deactivated` | A learner is deactivated. |
| `learner.reactivated` | A learner is reactivated. |
| `cohort_membership.added` | A learner joins a cohort. |
| `cohort_membership.removed` | A learner leaves a cohort. A move fires `cohort_membership.removed` then `cohort_membership.added`, sharing a `move_id`. |

Existing `WebhookEndpoint.event_types` subscriptions are not migrated: an endpoint subscribed to
`user.registered` or `course.registered` receives nothing until its event types are selected
again. Past `WebhookEvent` rows keep the code that was sent. Update receivers that branch on the
envelope's `type`, and body templates that read `event.type`. The notification category
`course.registered` is a separate registry and is unchanged.

## Panel framework API

Only for projects that build their own interface on `freedom_ls.panel_framework`. The URL shape
(`__panels/`, `__tabs/`, `__actions/`) is unchanged.

- **Panels** (`freedom_ls/panel_framework/panels.py`) are bound per request as `PanelClass(ctx)`
  with a `freedom_ls.panel_framework.context.PanelContext`. They render through `template_name` and
  `get_context_data()`. Tabs are the `children` of a `TabSet`; `PanelStack` shows panels one after
  another; `InstanceView.panel` is a single root. `InstanceDetailsPanel.fields` use `__` paths.
  `Panel.refresh_events` lists the events a panel refetches on (default none).
- **`PanelContext`** needs `config` (the section config class) and takes `scope`.
- **Section configs.** `panel_framework_view(config, ...)` takes a `list[NavGroup]`.
  `SectionConfigBase.has_capability(request, capability, scope)` returns `False` by default, so a
  section config that does not override it denies every built-in create, edit and delete action.
  Override `get_scope` and `has_capability`, and optionally `get_denied_context`,
  `get_instance_label` and `view_capability`.
- **Actions** (`freedom_ls/panel_framework/actions.py`). `has_permission(self, ctx)` replaces
  `has_permission(self, request, instance=None)`. `handle_submit(ctx)` takes the context; a
  subclass of `EditAction` that overrides it calls `super().handle_submit(ctx)`. The trigger
  renders from `trigger_template_name` and `get_trigger_context(ctx)`; `template_name` builds only
  the dialog fragment. Declare `success_events` instead of `get_created_event_name()`.
  `is_offered(ctx)` and `renders_in_footer` decide where an action shows. Use the module-level
  `count_noun` and `join_prose`.
- **Tables** (`freedom_ls/panel_framework/tables.py`). `get_columns()` returns `Column` instances.
  Every `DataTablePanel` and every `ListViewConfig` with a `list_view` sets `table_key`, and query
  parameters are prefixed with it (`<table_key>-q`, `-sort`, `-page`, `-export`, `-<filter key>`).
  Searching, filtering and sorting live in `filter_queryset`. `page_size` defaults to `10`.
  `empty_state_template` defaults to `panel_framework/partials/table_empty.html`, with text from
  `empty_message` and `empty_no_results`; set both on each table. `default_sort` and `noun` are
  optional.
- **Bulk actions** (`freedom_ls/panel_framework/bulk_actions.py`). `execute(request, queryset,
  cleaned_data)` returns a `BulkResult` or `BackgroundRun`; per-row work goes in
  `apply(user, obj, cleaned_data)`. `classify_all` takes the request. A selection in
  `all_matching` mode covers every row the table's search and filters match. Result templates read
  `result_lines`. Extend `RecordedBulkAction` to record and poll background runs. Optional:
  `confirm_variant`, `loading_text`, `confirmation_title(count, cleaned_data)`.
- **Responses.** No action sends `HX-Redirect`: a create, or a delete with a `success_url`, answers
  204 with `HX-Trigger` (including `closeModal`) and `HX-Location`. A denied action answers htmx
  with `panel_framework/partials/action_denied.html` (403); an object that no longer resolves
  answers with `panel_framework/partials/action_unavailable.html` (404).
- **System checks** `freedom_ls_panel_framework.E001` to `E008` validate panel `fields`,
  `children`, `table_key`, filter keys and `default_sort` at boot.
- `escape_csv_formula` and `FORMULA_TRIGGERS` are imported from `freedom_ls.base.csv_safety`.
- The CSV export streams with `QuerySet.iterator()`. See [Background work](#background-work) for
  PgBouncer and Gunicorn.

## Educator interface code

- Section config, panel and action classes in `freedom_ls/educator_interface/` were rebuilt. Check
  any subclass or import against `views.py`, `actions.py`, `reporting.py` and `quick_views.py`.
  Notable: `CohortDetailsStack` and `CourseRegistrationsPanel` are gone (`CohortOverviewStack`,
  `CohortCoursesPanel`); `DashboardPanel`, `CohortNeedsAttentionPanel` and `LearnerCoursesPanel`
  live in `reporting.py`.
- Action classes and slugs (the `/__actions/<slug>` URL and the `row_action_urls` key) follow the
  glossary: `DeactivateRegistrationAction` (`deactivate_registration`),
  `ReactivateRegistrationAction` (`reactivate_registration`), `DeactivateCohortRegistrationAction`
  (`deactivate_cohort_registration`), `DeactivateRoleAction` (`deactivate_role`) and
  `DeactivateMemberAction` (`deactivate`). Bulk: `DeactivateRegistrationBulkAction`
  (`deactivate_registration`) and `DeactivateCohortRegistrationBulkAction`
  (`deactivate_cohort_registration`).
- Service functions: `deactivate_registration` and `deactivate_cohort_registration` in
  `freedom_ls.learner_management`, `deactivate_role` in
  `freedom_ls.learner_management.role_assignment`.
- `learners_visible_to(include_inactive=...)` and `LearnerStatus.INACTIVE`; the learner status
  filter value is `inactive`. Member rows expose `is_inactive`.
- `inactive_cohort_response(request, cohort, blocked_phrase)` takes a required third argument, and
  a subclass of `RequiresActiveCohortMixin` sets `blocked_phrase`.
- The cohort page's tabs are `overview`, `learners`, `courses`, `report`, `settings` and
  `history`. Links to `cohorts/<pk>/__tabs/details` answer 404.
- The cohort report's roster keeps only active learners.
- `LearnerRegistrationProgress` (`freedom_ls/learner_progress/queries.py`) needs `registration`;
  `QuizResult` (`freedom_ls/reports/report_data.py`) needs `pass_percentage`.
- `freedom_ls.audit_log.writer.record_entry` and `record_run_summary` write your own audit entries;
  call `record_entry` inside the transaction of the change it records.
- The QA commands `qa_create_cohort_progress`, `qa_create_paginated_progress_matrix`,
  `qa_create_column_pagination_scenario`, `qa_add_course_items_for_pagination`,
  `qa_create_educator_modal_target` and `qa_create_educator_progress_targets` are deleted.

## Front end

- **htmx events.** `panelChanged` and `educatorChanged` are gone. Panels refresh on the domain
  events in `freedom_ls/educator_interface/events.py`: `learnerChanged`, `cohortChanged`,
  `registrationChanged` and `memberChanged`, each carrying `{"ids": [...]}` (build the header with
  `freedom_ls.panel_framework.events.build_hx_trigger`). An edit sends `instanceTitleChanged`, a
  dialog closes on `closeModal`, and a background bulk run starts with `bulkRunStarted`.
- **Error swaps.** The `htmx:beforeSwap` listener in
  `freedom_ls/base/static/base/js/alpine-components.js` swaps a 403 or 404 whose body contains
  `data-htmx-swap-error`. An unmarked 403 or 404 from a user-triggered request reloads the page,
  except inside `#interface-main` or an element marked `data-htmx-owns-errors`. A project that
  replaced this script needs the same rules.
- **htmx history cache is off** site-wide: `_base.html` sets `historyCacheSize: 0`.
- **Alpine components.** `modal`, `scrollTableLabels` and `sidebarMenuItem` are removed. The
  registered set is listed in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`.
- **CSS.** The `.modal-backdrop` class is removed (`.modal-backdrop-host` stays). New component
  classes `.panel-canvas` and `.panel-surface`, utilities `bottom-sheet` and `bottom-sheet-bare`,
  and the `--color-border-input` token (default `#6B7280`). A theme that changes `--color-surface`
  or `--color-surface-2` sets `--color-border-input` to keep 3:1 (`docs/how tos/theme-fls.md`).
  Default-theme `.chip-*` colours changed; `first_class`'s `--color-muted` is `#5F6B7F`.
- **New cotton components**, whose names may collide with your own: the `panel-*` components under
  `freedom_ls/panel_framework/templates/cotton/`, `<c-modal-header>`, `<c-modal-trigger>` and
  `<c-active-status-badge>`.
- **Component reference page (optional).** Include `freedom_ls.panel_framework.urls` inside your
  `if settings.DEBUG:` block to get the staff-only `components/` page.

## Icons

New semantic names: `cohort`, `add`, `search`, `filter`, `trend_up`, `trend_down`, `menu`,
`quick_view` and `open_page`. The four built-in sets map them all. With
`FREEDOM_LS_ICON_OVERRIDES` or a custom `FREEDOM_LS_ICON_BACKEND`, make sure each resolves, then
run `uv run manage.py check`.

## Background work

- Bulk runs and learner imports above `BULK_BACKGROUND_THRESHOLD` rows need the `db_worker`
  process the production `TASKS` setting already requires. Without it they stay queued until
  `fls_run_housekeeping` marks them failed.
- Keep `fls_run_housekeeping` scheduled: it also deletes unconfirmed import previews after 24
  hours and finished runs after `BULK_RECORD_RETENTION_DAYS`.
- CSV exports use a server-side cursor. Behind PgBouncer in transaction-pooling mode set
  `DISABLE_SERVER_SIDE_CURSORS: True` on that database. Under sync Gunicorn workers raise
  `--timeout` or use async or threaded workers.

## Templates

The account setup email uses `freedom_ls/accounts/templates/account/email/account_setup_subject.txt`,
`account_setup_message.txt` and `account_setup_message.html`; override the subject file to change
the subject.

Leaf templates are the ones meant to be overridden: `panel_framework/panels/{panel,panel_stack,tab_set,instance_details,data_table,data_table_region}.html`
and `panel_framework/views/{instance_view,list_view,base_view}.html`, each extending its `_base`
partner. A host template that extends `_base_interface.html` for panel-framework pages fills the
`quick_view_host` and `modal_host` blocks with `panel_framework/partials/quick_view_host.html` and
`panel_framework/partials/modal_host.html`. A dialog fragment opens with `<c-modal-header>` and pads
its own body. `educator_interface/interface.html` only extends `educator_interface/_shell.html`,
which holds the sidebar, content header and breadcrumbs blocks.

Existing templates changed, renamed or deleted since `6edcc4375`, from
`git diff --name-status 6edcc4375..HEAD` over template paths. Templates the rebuild added are not
listed, since nothing can already override them; `changed_template_paths` lists them as `# new`.

### Changed by the rebuild

- `freedom_ls/base/templates/_base.html`: changed
- `freedom_ls/base/templates/_base_interface.html`: changed
- `freedom_ls/base/templates/cotton/button.html`: changed
- `freedom_ls/base/templates/cotton/data-table-cells/boolean.html`: deleted (moved to `freedom_ls/panel_framework/templates/cotton/data-table-cells/boolean.html`, since deleted too)
- `freedom_ls/base/templates/cotton/data-table-cells/link.html`: deleted; now `freedom_ls/panel_framework/templates/cotton/data-table-cells/link.html`
- `freedom_ls/base/templates/cotton/data-table.html`: deleted; now `freedom_ls/panel_framework/templates/cotton/data-table.html`, rewritten
- `freedom_ls/base/templates/cotton/dropdown-menu.html`: changed
- `freedom_ls/base/templates/cotton/modal.html`: deleted; dialogs load into `panel_framework/partials/modal_host.html`
- `freedom_ls/base/templates/cotton/pagination.html`: changed
- `freedom_ls/base/templates/cotton/scroll-table-labels.html`: deleted; tables render as cards below `md`
- `freedom_ls/base/templates/partials/form.html`: changed
- `freedom_ls/base/templates/partials/header_bar.html`: changed
- `freedom_ls/base/templates/partials/header_bar_user_menu.html`: changed
- `freedom_ls/content_engine/templates/cotton/picture.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/_link_to_cohort.html`: deleted
- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_courses.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_links.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/data-table-cells/progress_check.html`: deleted
- `freedom_ls/educator_interface/templates/educator_interface/interface.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html`: deleted
- `freedom_ls/educator_interface/templates/educator_interface/partials/instance_details_panel.html`: deleted
- `freedom_ls/educator_interface/templates/educator_interface/partials/list_view.html`: deleted; use `panel_framework/views/list_view.html`
- `freedom_ls/educator_interface/templates/educator_interface/partials/organisation_switcher.html`: changed
- `freedom_ls/educator_interface/templates/educator_interface/partials/panel_container.html`: deleted
- `freedom_ls/form_engine/templates/form_engine/inputs/dropdown.html`: changed
- `freedom_ls/form_engine/templates/form_engine/inputs/long_text.html`: changed
- `freedom_ls/form_engine/templates/form_engine/inputs/text_input.html`: changed
- `freedom_ls/base/templates/cotton/data-table-cells/text.html`: renamed to `freedom_ls/panel_framework/templates/cotton/data-table-cells/text.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/breadcrumbs.html`: changed
- `freedom_ls/panel_framework/templates/panel_framework/partials/delete_confirmation.html`: deleted; now `panel_framework/modal/delete_confirmation.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/instance_actions.html`: deleted; actions render in `<c-panel-page-header>`
- `freedom_ls/panel_framework/templates/panel_framework/partials/instance_details_panel.html`: deleted; use `panel_framework/panels/instance_details.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/list_refresh.html`: changed
- `freedom_ls/panel_framework/templates/panel_framework/partials/list_view.html`: deleted; use `panel_framework/views/list_view.html` and `panel_framework/panels/data_table_region.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/main_content.html`: deleted; include `main_template_name` instead
- `freedom_ls/panel_framework/templates/panel_framework/partials/modal_form.html`: deleted; now `panel_framework/modal/form.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/panel_container.html`: deleted; use `panel_framework/panels/panel.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/sidebar_nav.html`: changed
- `freedom_ls/panel_framework/templates/panel_framework/partials/tab_container.html`: deleted; use `panel_framework/panels/tab_set.html`
- `freedom_ls/panel_framework/templates/panel_framework/partials/tab_panels.html`: deleted; use `panel_framework/panels/tab_set.html`

### Changed in the same range by other work

These changed between `6edcc4375` and this spec through work outside the rebuild, merged to `main`
in the same period. Their own specs' notes describe them; they are listed so a project upgrading
across the whole range sees every template it may shadow.

- `freedom_ls/accounts/templates/accounts/legal_doc.html`: changed
- `freedom_ls/base/templates/429.html`: changed
- `freedom_ls/base/templates/503.html`: changed
- `freedom_ls/base/templates/account/signup.html`: changed
- `freedom_ls/base/templates/allauth/layouts/entrance.html`: changed
- `freedom_ls/base/templates/allauth/layouts/manage.html`: changed
- `freedom_ls/base/templates/cotton/callout.html`: changed
- `freedom_ls/base/templates/cotton/markdown-container.html`: changed
- `freedom_ls/learner_interface/templates/cotton/course-section-pagination.html`: renamed to `freedom_ls/base/templates/cotton/section-pagination.html`
- `freedom_ls/base/templates/partials/page_title.html`: changed
- `freedom_ls/content_engine/templates/cotton/image-grid.html`: changed
- `freedom_ls/content_engine/templates/cotton/table.html`: changed
- `freedom_ls/course_applications/templates/course_applications/application_status.html`: changed
- `freedom_ls/course_applications/templates/course_applications/apply.html`: changed
- `freedom_ls/course_applications/templates/course_applications/check_your_answers.html`: changed
- `freedom_ls/course_applications/templates/course_applications/form_page.html`: changed
- `freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html`: changed
- `freedom_ls/course_interest/templates/course_interest/partials/express_interest_cta.html`: changed
- `freedom_ls/form_engine/templates/form_engine/partials/page_children.html`: changed
- `freedom_ls/google_tag/templates/partials/google_analytics.html`: changed
- `freedom_ls/google_tag/templates/partials/google_analytics_events.html`: changed
- `freedom_ls/icons/templates/cotton/icon.html`: changed
- `freedom_ls/learner_interface/templates/cotton/course-card-shell.html`: changed
- `freedom_ls/learner_interface/templates/cotton/course-row-shell.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/_course_base.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/course_detail.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/course_finish.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/course_form.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/course_topic.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/dashboard.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/card_title_link.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_details_link.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_listing_price.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_organisation_chip.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_row_list.html`: changed
- `freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html`: changed

## Per-spec notes

Each spec's own notes, under `spec_dd/3. done/`:

1. `spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/upgrade_notes.md`
2. `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/upgrade_notes.md`
3. `spec_dd/3. done/2026-10-04_09:07_educator-interface-3-panel-framework-dialogs/upgrade_notes.md`
4. `spec_dd/3. done/2026-09-29_14:19_educator-interface-4-panel-framework-components/upgrade_notes.md`
5. `spec_dd/3. done/2026-10-01_22:00_educator-interface-5-permissions/upgrade_notes.md`
6. `spec_dd/3. done/2026-10-11_06:57_educator-interface-6-cohort-administration/upgrade_notes.md`
7. `spec_dd/3. done/2026-10-20_13:37_educator-interface-7-learner-administration/upgrade_notes.md`
8. `spec_dd/3. done/2026-11-01_14:50_educator-interface-8-bulk-operations/upgrade_notes.md`
9. `spec_dd/3. done/2026-10-22_11:25_educator-interface-9-educator-administration/upgrade_notes.md`
10. `spec_dd/3. done/2026-10-24_08:10_educator-interface-10-reporting-dashboards/upgrade_notes.md`
11. `spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/upgrade_notes.md`
12. `upgrade_notes.md` beside this file (this spec's own changes).

`educator-interface-looks-good`: `spec_dd/3. done/2026-10-08_06:54_educator-interface-looks-good/upgrade_notes.md`

Some per-spec notes use names a later spec changed, such as `course.unregistered`,
`EDUCATOR_CHANGED`, `remove_site_role` or `UnregisterFromCourseBulkAction`. This file gives the
final name for each.
