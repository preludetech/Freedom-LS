# Educator interface test cleanup

Spec 15 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and
hygiene" section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec
depends on and may run beside, the decisions already taken and the assumptions every idea in the
effort makes.

## What

Bring `educator_interface`'s tests to rule 2 once the "Educator interface code layout" effort has
finished: a test imports only apps the app depends on at runtime. Clear whatever
`educator_interface` and `panel_framework` lines remain in the rule 1 and rule 2 baselines that
`test-organisation-and-hygene-3-enforcement-checks` wrote, for the lines this spec's cleanup
resolves.

Rule 1 (file layout mirrors the app) is no longer this spec's job. The "Educator interface code
layout" effort moves every `educator_interface` test into the mirrored `tests/panels/<area>/`
layout, alongside the code it moves, and clears the mirroring baseline lines as it goes. This spec
only checks that nothing in rule 1 is left over.

## Why

The "Educator interface code layout" effort (`educator-interface-refactor-1-scaffolding-and-common`
through `educator-interface-refactor-7-cleanup`, see that section of `spec_dd/1. next/roadmap.md`)
splits `views.py` and `actions.py` into `panels/<area>/` packages and moves nearly every test file.
Fixing imports in tests that are about to move would be done twice. `educator_interface` is cleaned
up after the move, not before.

## What is settled

- Depends on `test-organisation-and-hygene-4-shared-test-infrastructure` (root conftest and
  baseline scaffolding) and on `educator-interface-refactor-7-cleanup` (the layout effort's last
  spec). Both must be in `spec_dd/3. done/` before this spec starts.
- This spec re-audits `educator_interface` and `panel_framework` against the tree as the layout
  effort leaves it, rather than trusting today's violations. The file names below are today's;
  after the move they live under `educator_interface/tests/panels/<area>/`. Its job is to find
  what is left, not to replay a stale list.
- Today's violations, confirmed against the current tree, are the starting point for that
  re-audit. None of them is a runtime dependency of `educator_interface` today (its runtime deps
  are `content_engine`, `form_engine`, `learner_management`, `learner_progress`, `organisations`,
  `panel_framework`, `site_aware_models`):
  - `freedom_ls.role_based_permissions.utils.assign_object_role`, imported by
    `educator_interface/tests/test_organisation_switcher.py`,
    `test_config_authorisation.py`, `test_document_title.py`, `test_organisation_isolation.py`,
    `test_learner_section.py`, `test_interface_urls.py`, and both
    `educator_interface/tests/playwright/test_organisation_switcher.py` and
    `test_organisation_switcher_mobile.py`. This is the widest single violation in the app.
  - `freedom_ls.accounts`: `UserFactory` and `User` throughout, which spec 1 allows in any app's
    tests, and `SiteFactory` in `test_course_visibility_and_interest.py`, which spec 4 moves to
    `site_aware_models`. Neither is left to fix unless the move adds other `accounts` imports.
  - `freedom_ls.course_interest.factories.CourseInterestFactory`, imported by
    `test_course_visibility_and_interest.py` only.
  - `panel_framework` itself has no test-only violations today. It is the cleanest app in the
    repo, so this spec only has baseline lines for it if new ones have appeared.
- The effort's baseline rule applies unchanged here: spec 3 owns the baseline files; this spec
  deletes its two apps' lines once their violations are gone, and does not touch any other app's
  lines.

## Open until the spec

- Whether `educator_interface` calls `role_based_permissions` from its own runtime code. If it
  does, `docs/app_structure.md` gains it and the test
  imports stop being violations. If not, the tests follow spec 1's rule for granting a role.
- Whether the `accounts` and `course_interest` edges above still exist in the moved tests, in the
  same shape, a different shape, or not at all.

## Out of scope

- Any cleanup work before `educator-interface-refactor-7-cleanup` lands.
- Moving test files to mirror the app. The "Educator interface code layout" effort does that.
- Any other app's tests or baseline lines.
- General test quality (assertions, redundancy, coverage). This effort's decision 1 already
  limits "hygiene" to placement and layering.
- A big-bang rewrite of the whole app's tests in one PR.

## Resources

- `research_test_layout_audit.md` (parent directory `spec_dd/1. next/test-organisation-and-hygene/`),
  §1 and the `educator_interface` row of §5: the runtime/test-only dependency split this idea's
  "What is settled" section confirms against the current tree.
- The "Educator interface code layout" section of `spec_dd/1. next/roadmap.md`: the specs this one
  waits on, and the test layout they leave.
- `ds:testing`, `fls-dev:testing` (test-organisation-and-hygene-1-testing-standards owns these
  skills): the rules this spec applies.
- `freedom_ls/panel_framework/tests/conftest.py`: the stub-model technique, if the role edge
  resolves to "use a local fixture."
