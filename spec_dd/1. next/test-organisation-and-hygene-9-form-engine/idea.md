# Test organisation and hygiene: form_engine

Spec 9 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and hygiene" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

Bring `freedom_ls/form_engine/tests/` up to the two rules and the conftest/fixture/factory layering
standard, and delete `form_engine`'s lines from the baseline files spec 3 creates.

## Why

`form_engine` had the largest single-cause rule-2 violation: `accounts.factories.UserFactory`
in a dozen-plus test files. Spec 1 makes `UserFactory` usable in any app's tests, so that edge is not
a violation. What remains is small: the tests for the `templatetags` subpackage move into a mirrored
`tests/templatetags/` directory, one grab-bag file is documented, and the app's baseline lines go.
It stays its own spec because `form_engine` is under active change elsewhere (see below).

## What is settled

- `UserFactory` imports in `form_engine`'s tests are allowed (spec 1). Spec 3 decides how the check
  accepts them; this spec changes no `UserFactory` import.
- Tests for `freedom_ls/form_engine/templatetags/` modules move to `tests/templatetags/`, per spec 1's
  subpackage mirroring.
- The `docs/app_structure.md` runtime deps for `form_engine` (`base`, `content_base`,
  `markdown_rendering`, `site_aware_models`) are unaffected by this spec.
- `freedom_ls/form_engine/tests/` has no `conftest.py`. There is nothing to split into fixtures vs.
  plain helpers, and no manual-import anti-pattern to fix.
- `freedom_ls/form_engine/tests/test_import_independence.py` is a rule-1 grab-bag. It does not mirror
  a single production module. It parametrises over `scoring`, `signals`, `submissions` and
  `typed_answers` to prove none of them import `form_engine.models` at import time (guarding against
  an `INSTALLED_APPS`-order-dependent circular import). It passes today and is a deliberate,
  documented design, the same shape as `mail/tests/conftest.py`'s justified conftest exception. This
  spec documents why it doesn't mirror a module rather than moving or splitting it.
- Spec 3 owns the baseline files (the rule-2 `ignore_imports` list and the rule-1 mirroring
  exemption list); this spec's only edit to them is deleting `form_engine`'s own lines once its
  tests comply.
- `compliance-form-randomization` (in progress) and `form-engine-branch-logic` (next) both change
  `form_engine` and its tests. Whichever lands later rebases; a test file this spec moves is a likely
  conflict, so move files in their own commit.

## Open until the spec

- Whether `test_import_independence.py` needs a docstring addition explaining its non-mirroring shape,
  or whether its existing module docstring already suffices, is left to the spec to judge once spec
  3's mirroring check is in hand and can be run against it.

## Out of scope

- General test quality in `form_engine` (weak assertions, redundant tests, coverage) is on the effort's
  "Out of scope for all fifteen" list.

## Resources

- `research_test_layout_audit.md` (parent `spec_dd/1. next/test-organisation-and-hygene/`), §1 and
  §5 (per-app table row for `form_engine`): the `UserFactory` volume finding and the file-count/size
  summary this idea is built from.
- `claude_plugins/django-stack/skills/testing/SKILL.md` (+ `resources/testing.md`, `factory_boy.md`)
  and `claude_plugins/fls-dev/skills/testing/SKILL.md`: the rules this spec applies.
- `freedom_ls/mail/tests/conftest.py`: the reference example of documenting a deliberate deviation
  rather than forcing a fix.
