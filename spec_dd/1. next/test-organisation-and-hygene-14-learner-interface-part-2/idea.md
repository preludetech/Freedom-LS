# Learner interface test cleanup, part 2: forms and quiz runner

Spec 14 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring the form-runner and quiz-runner half of `learner_interface/tests/` up to the two testing
rules. This spec's file set is every file matching `test_form_*.py`, `test_quiz_*.py`,
`test_required_question_*.py`, `playwright/test_form_*.py`, or `playwright/form_ui_tests.py`:

- Form runner: `test_form_start_page_buttons.py`, `test_form_complete_results.py`,
  `test_form_page_navigation.py`, `test_form_runner_views.py`.
- Quiz runner: `test_quiz_runner_option_affordances.py`, `test_quiz_without_pass_mark.py`.
- Required-question UI, shared by both runners: `test_required_question_validation.py`,
  `test_required_question_legend.py`.
- `playwright/test_form_required_validation.py`, `playwright/test_form_option_layout.py`,
  `playwright/test_form_submit_navigation_guard.py`, `playwright/test_form_submit_dialog_focus.py`,
  `playwright/test_form_exit_submits_page_answers.py`, `playwright/test_form_answered_count.py`,
  and their shared support module `playwright/form_ui_tests.py`.

No file in this set carries a `course_applications` or `role_based_permissions` import. Both of
`learner_interface`'s rule-2 edges live entirely in spec 13's files, and grep confirms it. This
spec's own rule-2 scope is therefore checking that stays true as it edits these files, not fixing
an edge of its own.

## Why

`learner_interface` has 62 test files, too many to clean in one spec. This half is the form-runner
and quiz-runner surface. It is a distinct subject from the dashboard, listing and course-player
tests spec 13 owns, and small enough (14 test files plus one shared Playwright helper) to review on
its own once spec 13 has landed.

## What is settled

- This spec runs after `-13-learner-interface-part-1`, not beside it, because both halves share one
  `conftest.py`; spec 13 moves its eight plain helper functions out first, and this spec imports
  them from wherever spec 13 leaves them rather than from `conftest.py`.
- This spec does not touch `conftest.py`. Any fixture or helper this file set needs that still
  lives in `conftest.py` when spec 13 finishes is spec 13's to have moved, not something this spec
  re-opens.
- This spec does not own either of `learner_interface`'s rule-2 edges (`course_applications`,
  `role_based_permissions`). Both sit in spec 13's files. This spec's grep check confirms neither
  edge is present in its own file set before it starts.
- Spec 4 decides the root conftest's Playwright wildcard re-export scope and where
  `course_with_scored_quiz`/`sit_quiz` live. This spec follows that decision as given. Today this
  spec's files use neither fixture; only spec 13's course-player tests use them. So spec 4's
  decision affects this spec only if it changes the fixtures' import path in a way every consumer
  must follow.
- Spec 12 may move `accounts`' integration tests into `learner_interface`. Those tests
  (`test_deferred_login.py` and similar) are registration/listing concerns, not form-runner or
  quiz-runner ones, so they are expected to land in spec 13's scope, not this spec's; this spec
  rebases only if that expectation turns out wrong once spec 12 runs.
- This spec removes its files' lines from spec 3's rule-1 and rule-2 baselines once those baselines
  exist, verifying with a grep over its own file set that no import the baseline ignored is still
  present before deleting the line.

## Open until the spec

- Whether the `test_required_question_*.py` pair needs any change beyond what a conftest-import
  update forces. They carry no rule-2 violation, only a dependency on helpers spec 13 relocates.
- Whether `playwright/form_ui_tests.py`, as a shared support module rather than a test file itself,
  needs anything beyond following the same conftest-import update as its callers.

## Out of scope

- Spec 13's files: dashboard, listing, course detail, course player and the app's `conftest.py`.
- General test quality (assertions, redundancy, coverage). This spec covers placement and layering
  only.
- Deciding the root conftest's Playwright re-export or `course_with_scored_quiz`/`sit_quiz`
  placement. That is spec 4's.

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`), §3 and
  §5: the conftest plain-function violation (fixed by spec 13, consumed here) and the per-app
  summary row this spec's scope is drawn from.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`,
  `resources/factory_boy.md`), `claude_plugins/fls-dev/skills/testing/SKILL.md`, and
  `claude_plugins/fls-dev/skills/playwright-tests/SKILL.md`: the rules and Playwright-specific
  conventions this spec's browser tests follow.
- `freedom_ls/accounts/tests/conftest.py` and `freedom_ls/panel_framework/tests/conftest.py`: the
  reference conftest shapes this spec's imports should end up matching.
