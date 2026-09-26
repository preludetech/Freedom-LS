# Course access and applications test dependencies

Spec 7 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `course_access`'s and `course_applications`' tests into line with both testing rules from
spec 1, and fix `course_applications`' conftest hygiene.

`course_access/tests/test_visibility_enforcing_backend.py` imports
`course_applications.factories.CourseApplicationFactory` to build an application and call
`get_dashboard_contributions`. `course_applications` runs on top of `course_access` at runtime, not
the other way round, so this is a rule-2 violation that runs backwards against a real edge between
the same two apps.

`course_applications/tests/test_views.py` imports `learner_progress.models.CourseFormAttempt`.
`course_applications` does not depend on `learner_progress` at runtime, so this is a second,
independent rule-2 violation on the same app.

`course_applications/tests/conftest.py` defines `gated_course_with_form`, a plain function callers
import manually (`from freedom_ls.course_applications.tests.conftest import gated_course_with_form`)
rather than a pytest fixture or a helper in its own module.

## Why

The `course_access` ↔ `course_applications` edge is one of only three circular-shaped test-only
edges in the repo. The test-only dependency points opposite the real runtime dependency between the
same two apps. That makes it the sharpest form of a misleading dependency graph this effort finds.

## What is settled

- Rules 1 and 2 from spec 1 (`ds:testing`) apply to both apps: the test file hierarchy mirrors the
  app's file hierarchy, and an app's tests import only apps the app itself depends on.
- The runtime graph (`docs/app_structure.md`) is unchanged by this spec: `course_access` depends on
  `accounts`, `base`, `content_engine`, `google_tag`, `learner_management`; `course_applications`
  depends on `accounts`, `content_engine`, `course_access`, `form_engine`, `learner_management`,
  `site_aware_models`. `course_applications` depending on `course_access` is the only real edge
  between the two. The reverse does not exist; this spec does not create it.
- A test that spans apps lives in the lowest app that depends on every app it touches. This decides
  where the spec fixes each of the two violations above, once it has looked at what each test
  actually asserts.
- Spec 4 (shared test infrastructure) has already landed before this spec starts, so the root
  conftest, optional-app collection guards and dead test directories are not this spec's concern.
- Spec 3 owns the rule 1 and rule 2 baseline files; this spec deletes `course_access`'s and
  `course_applications`' lines from both once the apps are clean, and touches no other app's lines.
- This spec touches only `course_access/tests/` and `course_applications/tests/` (plus its own
  baseline lines), so it runs in parallel with every other cleanup spec in the effort.

## Open until the spec

- Whether `test_visibility_enforcing_backend.py`'s need for an application fixture is met by a
  local stub owned by `course_access`, or by moving that assertion into `course_applications` (which
  already tests application gating and depends on `course_access`). The "lowest app that depends on
  everything it touches" rule decides this once the spec reads what the test actually checks.
- Whether `test_views.py`'s need for `CourseFormAttempt` is intrinsic to the behaviour under test, or
  replaceable with a narrower check that doesn't reach into `learner_progress`. The spec decides
  from the test's actual assertions.
- Whether `gated_course_with_form` becomes a proper fixture or moves to a plain `helpers.py` module
  beside `conftest.py`. Spec 1 sets the general conftest-vs-plain-module rule; this spec applies it
  here.

## Out of scope

- General test quality for either app: assertions, redundancy, coverage.
- Any change to `course_access`'s or `course_applications`' production code or runtime dependency
  graph. This spec only touches tests.
- Other apps' rule violations, including `learner_management` ↔ `learner_progress`'s own circular
  edge (spec 8).
- Regenerating the rule 2 baseline mechanism. Spec 3 owns it; this spec only removes its own two
  apps' lines from it.

## Resources

- `research_test_layout_audit.md` (`spec_dd/1. next/test-organisation-and-hygene/`). §1 names this
  pair as one of the repo's two circular test-only edges; §3 and §5 cover
  `course_applications/tests/conftest.py`'s un-prefixed helper.
- `docs/app_structure.md`, the runtime dependency graph both rules check against.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`, `factory_boy.md`)
  and `claude_plugins/fls-dev/skills/testing/SKILL.md`, the rules and the conftest/fixture layering
  guidance this spec applies.
