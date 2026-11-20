---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/panel_framework/templates/cotton/panel-attention-row.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_needs_attention_region.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/cohort_report_body_region.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_person.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/audit_row_detail.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_who.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/audit_target.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: profile-picture-on-id-rows

Educator attention rows (dashboard and cohort), the on-screen cohort report and the audit log now
show a person's profile picture where they used to show initials only. Attention and report rows
now key the avatar colour on the user pk, so a learner has the same colour there as in the
learners table. The cohort report PDF is unchanged.

## Breaking changes

None.

## Manual steps

No migration, setting or package change.

If your project overrides any of the templates listed in `changed_template_paths`, re-apply your
customisations on top of the new versions:

- `cotton/panel-attention-row.html` takes a new `picture_url` attribute (default empty, which shows
  initials) and forwards it to `c-panel-person-link`.
- The three panel region templates now read an `avatars` context value (filled by the panels in
  `freedom_ls/educator_interface/reporting.py`) through the new `lookup` filter in
  `educator_tags`, and pass `:user_id` and `:picture_url` from it. An override that keeps the old
  markup still renders, with initials and the old avatar colour.
- `partials/audit_person.html` takes a `picture_url`; the audit `who`, `target` and run-entry
  detail templates pass `actor_picture_url` / `target_picture_url`, which the audit log tables now
  set on each `AuditLogEntry` they render.
