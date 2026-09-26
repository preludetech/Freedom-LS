# Learner management and progress test dependencies

Spec 8 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `learner_management`'s and `learner_progress`'s tests into line with both testing rules from
spec 1.

`learner_management/tests/test_learner_admin.py` imports `learner_progress.admin.learner_progress_links`,
`learner_progress.factories`, and `learner_progress.models.CourseProgress`.
`learner_management/tests/test_registration_webhook_events.py` imports
`learner_progress.models.CourseProgress`. `learner_progress` runs on top of `learner_management` at
runtime, not the other way round, so both are rule-2 violations that run backwards against a real
edge between the same two apps.

`learner_management/tests/test_context_processors.py` and `learner_management/tests/test_queries.py`
import `role_based_permissions.utils.assign_object_role`. `learner_management` has no runtime
dependency on `role_based_permissions` in either direction, so this is a second, independent rule-2
violation on `learner_management`.

`learner_progress/tests/test_course_progress_for.py`, `test_ensure_course_progress_record.py`, and
`test_course_progress_by_course_for.py` import `organisations.factories.OrganisationFactory`.
`learner_progress` has no runtime dependency on `organisations`.

## Why

The `learner_management` ↔ `learner_progress` edge is one of only three circular-shaped test-only
edges in the repo. The test-only dependency points opposite the real runtime dependency between the
same two apps. This is the sharpest form of a misleading dependency graph this effort finds.

## What is settled

- Rules 1 and 2 from spec 1 (`ds:testing`) apply to both apps: the test file hierarchy mirrors the
  app's file hierarchy, and an app's tests import only apps the app itself depends on.
- The runtime graph (`docs/app_structure.md`) is unchanged by this spec: `learner_management` depends
  on `accounts`, `base`, `content_engine`, `form_engine`, `organisations`, `site_aware_models`.
  `learner_progress` depends on `accounts`, `content_engine`, `form_engine`, `learner_management`,
  `site_aware_models`, `webhooks`. `learner_progress` depending on `learner_management` is the only
  real edge between the two. The reverse does not exist and is not created by this spec.
- A test that spans apps lives in the lowest app that depends on every app it touches. This decides
  where each violation above is fixed, once the spec has looked at what each test actually asserts.
- `role_based_permissions`'s own reverse test-only edge into `learner_management`
  (`role_based_permissions/tests/test_utils.py`, `test_models.py`,
  `test_management_commands.py` borrowing `CohortFactory` as "some object with an assignable role")
  belongs to spec 5's stub-model group, not this spec. This spec owns only the direction pointing
  out of `learner_management`.
- Spec 4 (shared test infrastructure) has already landed before this spec starts, so the root
  conftest, optional-app collection guards and dead test directories are not this spec's concern.
- Spec 3 owns the rule 1 and rule 2 baseline files. This spec deletes `learner_management`'s and
  `learner_progress`'s lines from both once the apps are clean, and touches no other app's lines.
- This spec touches only `learner_management/tests/` and `learner_progress/tests/` (plus its own
  baseline lines), so it runs in parallel with every other cleanup spec in the effort, with one
  caution. `educator-interface-7-learner-administration` rebuilds `learner_management`'s learner,
  membership and registration views and their tests (including `test_learner_admin.py` and the
  registration webhook events this spec also touches). Whichever of the two lands second rebases
  against the other's changes to those files.
- The `assign_object_role` imports in `test_context_processors.py` and `test_queries.py` follow
  spec 1's rule for granting a role in an app that does not depend on `role_based_permissions`.

## Open until the spec

- Where the two circular-edge assertions in `test_learner_admin.py` and
  `test_registration_webhook_events.py` land: a local stub owned by `learner_management`, or moving
  the assertion into `learner_progress` (which already tests progress records and depends on
  `learner_management`). The "lowest app that depends on everything it touches" rule decides this
  once the spec reads what each test actually checks.
- Whether `learner_progress`'s `organisations` edge is fixed with a local stub, or documented as an
  accepted exception the way spec 1 lets an intrinsic edge be documented rather than removed, the
  spec decides from whether `learner_progress`'s behaviour under test genuinely needs an org-scoped
  learner or can be built without a real `Organisation` row.

## Out of scope

- General test quality for either app: assertions, redundancy, coverage.
- Any change to `learner_management`'s or `learner_progress`'s production code or runtime dependency
  graph. This spec only touches tests.
- `role_based_permissions`'s reverse edge into `learner_management` (spec 5), the `course_access` ↔
  `course_applications` circular pair (spec 7).
- The educator interface rebuild itself. This spec only rebases against it where the same files
  overlap.
- Regenerating the rule 2 baseline mechanism. Spec 3 owns it. This spec only removes its own two
  apps' lines from it.

## Resources

- `research_test_layout_audit.md` (`spec_dd/1. next/test-organisation-and-hygene/`). §1 names this
  pair as one of the repo's three circular test-only edges and covers the `role_based_permissions`
  and `organisations` edges and the `form_engine` exception precedent. §5 has the per-app rows for
  `learner_management` and `learner_progress`.
- `docs/app_structure.md` is the runtime dependency graph both rules check against.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`, `factory_boy.md`)
  and `claude_plugins/fls-dev/skills/testing/SKILL.md` have the rules and the conftest/fixture
  layering guidance this spec applies.
- `spec_dd/1. next/educator-interface-7-learner-administration/idea.md` is the rebuild this spec
  rebases against where it touches the same `learner_management` test files.
