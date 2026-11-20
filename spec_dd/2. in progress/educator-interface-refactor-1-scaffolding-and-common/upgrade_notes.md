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

# Upgrade notes: educator-interface-refactor-1-scaffolding-and-common

## Breaking changes

Shared educator interface helpers moved out of the flat modules into the new package
`freedom_ls.educator_interface.panels.common`. Behaviour, URLs, templates and app labels are
unchanged, and no re-export is left behind. The old module no longer defines these names. Some
still resolve there only because the old module imports them for its own use; don't rely on that.
Repoint any downstream import or `mock.patch` string to the new path.

All paths below are under `freedom_ls.educator_interface`.

| Name | Old module | New module |
| --- | --- | --- |
| `LAST_ORGANISATION_SESSION_KEY` | `views` | `panels.common.request` |
| `OrganisationScopedRequest` | `views` | `panels.common.request` |
| `OrganisationSectionConfig` | `views` | `panels.common.request` |
| `active_status_badge` | `views` | `panels.common.badges` |
| `inactive_badge` | `views` | `panels.common.badges` |
| `_interface_link` | `views` | `panels.common.tables` |
| `_learner_column` | `views` | `panels.common.tables` |
| `_active_status_column` | `views` | `panels.common.tables` |
| `_registration_columns` | `views` | `panels.common.tables` |
| `uuid_or_404` | `views` | `panels.common.ids` |
| `VisibleCourseFilter` | `filters` | `panels.common.filters` |
| `EducatorReasonMixin` | `actions` | `panels.common.actions` |
| `_uuid_from` | `actions` | `panels.common.actions` |
| `_action_params` | `actions` | `panels.common.actions` |
| `_empty_message` | `actions` | `panels.common.actions` |
| `_picker_title` | `actions` | `panels.common.actions` |
| `_register_title` | `actions` | `panels.common.actions` |
| `EducatorBulkAction` | `actions` | `panels.common.bulk_actions` |
| `CoursePickerMixin` | `actions` | `panels.common.bulk_actions` |
| `PROGRESS_STATUS_TONES` | `reporting` | `panels.common.report` |
| `progress_status_badge` | `reporting` | `panels.common.report` |
| `flag_badge` | `reporting` | `panels.common.report` |
| `report_over_limit_message` | `reporting` | `panels.common.report` |

`quick_views._active_status_badge`, a private lazy wrapper, is gone; use
`panels.common.badges.active_status_badge`.

No registered bulk action moved, so stored `BulkActionRun.action_path` values are unaffected.

## Manual steps

None beyond repointing imports, if your project uses any of the names above. Otherwise no action
needed.
