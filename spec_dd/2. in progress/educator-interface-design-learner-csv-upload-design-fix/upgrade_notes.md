---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_upload.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_preview.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_result.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/import_stepper.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/learner_import_result_body.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: educator-interface-design-learner-csv-upload-design-fix

## Breaking changes

- The learner import upload page's context no longer has `headers` (the comma-joined column
  list). It has `format_rows` (one entry per CSV column, for the "File format" table),
  `max_rows` and `max_file_size` instead. A downstream override of
  `educator_interface/learner_import_upload.html` that reads `headers` renders it empty and must
  switch to `format_rows`.

## Manual steps

- Rebuild Tailwind: the restyled import templates use utility classes the old bundle may lack.
- If your project shadows any of the five templates listed in `changed_template_paths` by path,
  it keeps the old look until you merge the new markup into your copy. The preview page and the
  result body now include a new partial, `educator_interface/partials/import_error_block.html`,
  for their error rows.
- No action needed for `{% local_time %}`: the tag now lives in `base`'s `time_tags` library
  (`{% load time_tags %}`), and `deadline_tags` still registers it, so templates that
  `{% load deadline_tags %}` keep working.
