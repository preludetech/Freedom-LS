---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/callout.html
  - freedom_ls/base/templates/cotton/panel-callout.html
  - freedom_ls/panel_framework/templates/cotton/panel-callout.html
  - freedom_ls/panel_framework/templates/cotton/panel-notice.html
  - freedom_ls/base/templates/account/login.html
  - freedom_ls/base/templates/partials/form.html
  - freedom_ls/course_applications/templates/course_applications/applicant_details.html
  - freedom_ls/course_applications/templates/course_applications/check_your_answers.html
  - freedom_ls/course_applications/templates/course_applications/form_page.html
  - freedom_ls/educator_interface/templates/educator_interface/learner_import_upload.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/change_role.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_role_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_staff_member_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/modal/move_confirmation.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/course_content.html
  - freedom_ls/educator_interface/templates/educator_interface/panels/dashboard_region.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/import_error_block.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/staff_only_admin_callout.html
  - freedom_ls/form_engine/templates/form_engine/partials/answer_errors.html
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/confirm.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/delete_confirmation.html
  - freedom_ls/panel_framework/templates/panel_framework/modal/form.html
  - freedom_ls/panel_framework/templates/panel_framework/panels/_lazy_region.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/bulk_confirmation_message.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/inline_record_form.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: misure-of-admonitions

App pages, panels and dialogs now show status messages with one theme-fit callout,
`<c-callout tone=… title=…>`. Course content keeps `<c-admonition>`.

## Breaking changes

- `<c-callout level=…>` is now `<c-callout tone=…>`. Tones are `info` (default), `success`,
  `warning` and `error`. A leftover `level` attribute is ignored, so the callout renders as `info`
  without any error.
- `<c-panel-notice>` is removed (`freedom_ls/panel_framework/templates/cotton/panel-notice.html` is
  deleted). Replace `<c-panel-notice tone=… title=…>` with `<c-callout tone=… title=…>` in app
  templates, or `<c-panel-callout tone=… title=…>` in templates that must work without FLS's
  `base` app.
- A project that overrode `cotton/panel-notice.html` now overrides `cotton/panel-callout.html`.
  FLS ships one in `freedom_ls/base/templates/cotton/panel-callout.html` that renders
  `<c-callout>`.
- The callout looks different: no outer margin (the old one added `my-6` unless the caller passed
  a `my-` class), no left stripe, and the title is a bold first line (`<strong>`), not an `<h4>`.
  Add spacing in the parent where a callout now sits too close to its neighbours.
- The `.alert`, `.alert-info`, `.alert-success` and `.alert-error` classes in
  `tailwind.components.css` are renamed to `.callout`, `.callout-info`, `.callout-success` and
  `.callout-error`, with a new `.callout-warning` and `.callout-icon`. A theme that overrides the
  `.alert*` rules renames them to `.callout*` and adds `.callout-warning`; the `first_class` theme
  in `freedom_ls/themes/first_class/static/themes/first_class/theme.css` is the worked example.

## Manual steps

- Search the project's templates for `level=` on `<c-callout>`, `c-panel-notice` and the `alert`
  classes, and update each as above. The known downstream use is First Class
  `apps/landing_pages/templates/cotton/lp/step.html`.
- Review and re-apply customisations to any of the templates listed in `changed_template_paths`
  that the project overrides.
- Rebuild Tailwind (`npm run tailwind_build`): the callout classes changed.
