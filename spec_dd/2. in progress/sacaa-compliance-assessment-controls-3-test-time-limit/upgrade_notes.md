---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/course_form.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
  - freedom_ls/form_engine/templates/form_engine/partials/form_facts.html
  - freedom_ls/reports/templates/reports/partials/learner_detail.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: sacaa-compliance-assessment-controls-3-test-time-limit

## Breaking changes

None. A quiz has no time limit unless its content sets `time_limit_minutes` in the form's
frontmatter, so existing quizzes behave as before.

## Manual steps

- Run `manage.py migrate`. `freedom_ls_form_engine.0019_form_time_limit_minutes_and_more` adds
  `Form.time_limit_minutes`, `FormProgress.completion_reason` (existing sittings default to
  `learner_submitted`) and `FormProgress.time_limit_minutes`.
- If you override any of these templates, re-apply your changes against the new versions:
  - `learner_interface/course_form.html`: the time limit notice above the Start button.
  - `learner_interface/course_form_page.html`: the top bar now carries
    `x-data="examCountdown"` with `data-remaining-seconds`, `data-time-up-url` and
    `data-warnings`, the `role="timer"` countdown beside the answered count, and the 5-minute and
    1-minute warning callouts with their live regions. An override that drops these attributes
    loses the countdown and the submit at 0:00; the server still completes the sitting when the
    learner next loads a quiz page.
  - `learner_interface/course_form_complete.html`: the "Time ran out" line, driven by the
    `time_expired` context variable.
  - `form_engine/partials/form_facts.html`: the time limit chip. It now reads `form` from the
    context as well as `question_count` and `page_count`.
  - `reports/partials/learner_detail.html`: the "Completion reason" column in the attempts table.
    If you override `reports/print.css`, add a `.col-attempt-reason` width and narrow
    `.col-attempt-quiz` to match.
- If you set `FREEDOM_LS_ICON_OVERRIDES`, the new semantic icon `time_limit` (a clock in every
  built-in set) can be overridden like any other.
- No action needed for housekeeping: `fls_run_housekeeping` now also completes timed sittings whose
  limit ran out while nobody was on the page, so keep running it on its existing schedule.
