# Learner interface test cleanup, part 1: dashboard, listing and course player

Spec 13 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene"
section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on
and may run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `learner_interface/tests/` up to the two testing rules and the conftest-layering rule, for
every file except the form-runner and quiz-runner tests (spec 14's half). Concretely, this spec
owns every file in `freedom_ls/learner_interface/tests/` not matched by `test_form_*.py`,
`test_quiz_*.py`, `test_required_question_*.py`, `playwright/test_form_*.py`, or
`playwright/form_ui_tests.py`. That leaves it:

- Dashboard: `test_dashboard_cost.py`, `test_dashboard_accessibility.py`,
  `test_dashboard_ordering.py`, `test_dashboard_section_slugs.py`, `test_dashboard_grouping.py`,
  `test_dashboard_view.py`, `test_dashboard_pagination.py`.
- Listing: `test_all_courses_public.py`, `test_all_courses_view.py`, `test_all_courses_rows.py`,
  `test_course_listing.py`, `test_listing_visibility.py`, `test_course_cards.py`.
- Course detail: `test_course_detail_public.py`, `test_course_detail_visibility.py`,
  `test_course_detail_category_chip.py`, `test_course_detail_toc_in_development.py`,
  `test_course_price_placement.py`, `test_course_price_component.py`, `test_course_icon.py`.
- Course player: `test_player_organisation.py`, `test_player_breadcrumbs.py`,
  `test_player_progress_scoping.py`, `test_course_item_navigation.py`, `test_view_course_item.py`,
  `test_sequential_item_unlock.py`, `test_outline_agrees_with_progress.py`,
  `test_read_path_record_scoping.py`, `test_resume_and_redirect.py`, `test_course_part_children.py`.
  (Several of these build a course with a `Form` as one content item alongside `Topic`s to exercise
  player mechanics, such as sequential unlock, outline and progress agreement, and resume
  bookkeeping, that apply to any content type. They are not form-runner or quiz-runner tests, so
  they stay here.)
- Course-level and cross-cutting: `test_course_finish_requires_passing.py`,
  `test_course_completion_webhook_events.py`, `test_deadline_integration.py`,
  `test_course_access_integration.py`, `test_self_registration_learner.py`,
  `test_anonymous_home_page.py`, `test_seo_discoverability.py`, `test_page_title_tags.py`,
  `test_checks.py`.
- `playwright/test_flashcard_overflow.py`, `playwright/test_course_toc.py`,
  `playwright/test_picture_spotlight.py`, `playwright/test_course_detail_layout.py`,
  `playwright/test_course_detail_price_stat.py`.
- `conftest.py` and `no_sitemap_urls.py`.

Fix, for this file set:

1. **Rule 1.** `conftest.py`'s eight plain functions are `course_with_single_question_form`,
   `course_with_form`, `register_user_for_course`, `course_progress_record`, `form_attempt`,
   `topic_completion`, `learner_with_two_grants`, and `collection_item_for`. Move them out of
   `conftest.py` into a sibling plain module (`accounts/tests/conftest.py` and
   `panel_framework/tests/conftest.py` are the reference examples for what stays a fixture versus
   what becomes a private helper or a plain import). Update every manual
   `from freedom_ls.learner_interface.tests.conftest import ...` in this spec's own files to the
   new location.
2. **Rule 2.** `course_applications` and `role_based_permissions` are `learner_interface`'s only
   test-only dependencies, and both sit entirely in this spec's files, not spec 14's:
   `course_applications` in `test_course_access_integration.py`, `test_course_detail_public.py`,
   `test_anonymous_home_page.py`, `test_all_courses_public.py` (`CourseApplicationFactory`, the
   `course_applications:apply`/`:status` URL names, the `ApplicationCourseAccessBackend` setting);
   `role_based_permissions` in `test_resume_and_redirect.py`
   (`freedom_ls.role_based_permissions.loader.clear_caches`). Fix each per whatever spec 7
   (`course_access`/`course_applications`) and spec 1's rule on `role_based_permissions` settle, or
   document why the edge is intrinsic if it turns out not to be.

## Why

`learner_interface` has 62 test files, two to three times any other app, so cleaning it in one
spec would be unreviewable. This half, everything except the form runner and quiz runner, is a
coherent unit: dashboard, listing, course detail and the course player are all read paths over a
learner's registration and progress records, distinct in subject from the form-engine-backed
runner UI that spec 14 owns.

## What is settled

- This spec runs after `-4-shared-test-infrastructure` and before `-14-learner-interface-part-2`,
  because both halves share one `conftest.py`; landing this spec's conftest move first is what lets
  spec 14 land cleanly.
- The file split above is final: any file matching `test_form_*.py`, `test_quiz_*.py`,
  `test_required_question_*.py`, `playwright/test_form_*.py`, or `playwright/form_ui_tests.py`
  belongs to spec 14, not here, even where its fixtures come from this spec's cleaned-up helper
  module.
- This spec owns the `conftest.py` cleanup for the whole app; spec 14 only edits its own files and
  imports whatever this spec leaves behind. It does not touch `conftest.py` itself.
- This spec owns both of the app's rule-2 edges (`course_applications`, `role_based_permissions`),
  because both happen to live in files this spec owns. A grep in this idea's research pass confirmed
  that spec 14's files carry neither edge.
- Spec 4 decides the root conftest's Playwright wildcard re-export scope and where
  `course_with_scored_quiz`/`sit_quiz` live; this spec follows that decision as given, not revisits
  it. Today those two fixtures are used only by this spec's files
  (`test_outline_agrees_with_progress.py`, `test_player_progress_scoping.py`,
  `test_sequential_item_unlock.py`, `test_course_finish_requires_passing.py`), not spec 14's.
- Spec 12 may move `accounts`' integration tests (e.g. `test_deferred_login.py`) into
  `learner_interface`. If that lands first, this spec rebases to place the moved file correctly
  against the split above (almost certainly here, since deferred registration is a
  listing/registration concern, not a form-runner one) rather than silently keeping it wherever the
  rebase leaves it.
- This spec removes its files' lines from spec 3's rule-1 and rule-2 baselines once those baselines
  exist, verifying with a grep over `freedom_ls/learner_interface/` that no import the baseline
  ignored is still present before deleting the line.

## Open until the spec

- Whether the `course_applications` and `role_based_permissions` edges get a stub-model/local-
  fixture fix or a documented exception, following spec 7's fix and spec 1's rule.
- Where the eight conftest helpers land (a `helpers.py` sibling, or split by the section of the app
  they serve) and their new names, if any change.
- Whether `test_course_detail_toc_in_development.py` needs any change at all, given it carries no
  rule 1 or rule 2 violation today, only a conftest dependency on fixtures this spec is moving.

## Out of scope

- Spec 14's files: the form-runner and quiz-runner tests.
- General test quality (assertions, redundancy, coverage). This is placement and layering only.
- Deciding the root conftest's Playwright re-export or `course_with_scored_quiz`/`sit_quiz`
  placement. That is spec 4's.

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`), §3 and
  §5: the conftest plain-function violation and the per-app summary row this spec's scope is drawn
  from.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`,
  `resources/factory_boy.md`) and `claude_plugins/fls-dev/skills/testing/SKILL.md`: the rules and
  the stub-model/conftest-layering pattern to apply here.
- `freedom_ls/accounts/tests/conftest.py` and `freedom_ls/panel_framework/tests/conftest.py`: the
  reference conftest shapes (fixtures plus private helpers; stub models).
- `docs/app_structure.md`: the dependency graph the rule-2 fix has to respect.
