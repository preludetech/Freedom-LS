---
requires_migrations: false
requires_template_review: true
changed_template_paths:
  - freedom_ls/form_engine/templates/form_engine/question.html
  - freedom_ls/form_engine/templates/form_engine/inputs/phone_input.html
  - freedom_ls/learner_interface/templates/learner_interface/_exam_runner_base.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: true
changed_packages:
  - phonenumberslite==9.0.43
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: phone-number-form-field

## Breaking changes

None for code. Behaviour changes for learners: a `phone` question now has a country picker and
refuses a number that is not valid for the chosen country. New answers are stored in E.164 form
(`+27821234567`) and shown in international form.

Phone answers stored before this change are not converted. They display and export as typed, and
are validated only if the learner submits that question again.

## Manual steps

- Run `uv sync` to install `phonenumberslite` (new dependency, `>=9.0.43`). Keeping it current keeps
  phone validation current: a newly allocated number range is refused until the library is upgraded.
- Rebuild Tailwind: `freedom_ls/form_engine/templates/form_engine/inputs/phone_input.html` is a new
  template with responsive layout classes.
- If you override `form_engine/question.html`, change the `phone` branch to
  `{% include "form_engine/inputs/phone_input.html" %}`.
- If you override `learner_interface/_exam_runner_base.html` and replace its
  `extra_alpine_components` block without `{{ block.super }}`, add
  `<script defer src="{% static 'form_engine/js/alpine-components.js' %}"></script>`. Any other page
  you render a form question on needs the same script, or the phone question's example hint will not
  follow the country picker.
