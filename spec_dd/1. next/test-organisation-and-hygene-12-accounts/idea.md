# Accounts: cut the reach into seven apps' tests

Spec 12 of 15 in the Test organisation and hygiene effort. Read the "Test organisation and
hygiene" section of `spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec
depends on and may run beside, the decisions already taken and the assumptions every idea in the
effort makes.

## What

Bring `accounts`' tests in line with rule 2: an app's tests import only apps it depends on at
runtime. `accounts` runtime-depends on `base`, `google_tag`, `mail`, `markdown_rendering`,
`site_aware_models`, `webhooks`, yet its tests are the heaviest test-only importer of upstream apps
in the repo, reaching into `content_engine`, `course_applications`, `course_interest`, `icons`,
`learner_management`, `organisations` and `referral_tracking`. Four files carry all of it:

- `test_deferred_login.py` imports `content_engine.factories.CourseFactory`,
  `course_applications.factories.CourseApplicationFactory`, `course_interest.models.CourseInterest`
  and `learner_management.models.LearnerCourseRegistration`. It exercises a deferred-registration
  flow end to end, not `accounts` behaviour. It is an integration test wearing `accounts` clothing.
  Its right home is an app that depends on everything it touches, not `accounts`.
- `test_setup_initial_prod_data.py` imports `organisations.models.Organisation` to assert that
  bootstrapping a Site's default Organisation still fires.
- `test_legal_doc_view.py` imports `icons.loader._cache` to reset the icon loader's cache between
  tests, because the legal-doc 404 page it renders also carries icons.
- `test_admin.py` imports `referral_tracking.factories.SignupAttributionFactory` and
  `referral_tracking.models.SignupAttribution` to assert that deleting a `User` cascades to a
  `SignupAttribution` audit row.

## Why

`accounts` sits about as low in the runtime graph as an app gets. Its test suite reaching up into
seven others is the sharpest instance of the smell rule 2 exists to catch, and the biggest single
win available to this cleanup line. It is also the spec every other cleanup measures itself against
for the question "does a cross-app test move, or does it get a local fixture instead". One file
here is a wholesale integration test, three are single-import cases with a real behaviour behind
the import, not a borrowed convenience fixture.

## What is settled

- `accounts/tests/conftest.py` is already the good example the cut points to. It has fixtures plus
  underscore-private helpers, nothing needing a manual import. This spec adds to it, or to a new
  sibling module, on the same terms. It does not restructure it.
- A test that spans apps belongs in the lowest app that depends on every app it touches. This spec
  applies that rule to `test_deferred_login.py`.
- Spec 1's allowance runs one way: other apps' tests may use `accounts`' `UserFactory`. It does
  not let `accounts`' tests borrow other apps' factories and models, which is what the four files
  above do.
- Spec 3 owns the rule 1 and rule 2 baseline files. This spec deletes `accounts`' lines from both
  once its violations are fixed. It does not touch any other app's lines.
- This spec depends on spec 4 and otherwise runs in parallel with specs 5–11 and 13–15. The one
  exception: if it moves any part of `test_deferred_login.py` into `learner_interface`, it rebases
  against specs 13 and 14, which also edit `learner_interface`'s tests and share its one conftest.
- `form_engine -.-> accounts` is a separate, already-documented exception owned by spec 9, not this
  one. `accounts` is the depended-on app in that pair, not the one reaching out.

## Open until the spec

- Where `test_deferred_login.py` (or the behaviour it covers) moves. Applied literally, the "lowest
  app that depends on everything it touches" rule names `qa_helpers`. It is the only app in the
  dependency graph with a runtime edge to `accounts`, `content_engine`, `course_applications`,
  `course_interest` and `learner_management` all at once. `learner_interface` depends on
  `accounts`, `content_engine`, `course_interest` and `learner_management` at runtime but not
  `course_applications`. Its existing test-only edge into `course_applications` is itself a
  violation, not a runtime dependency the rule can lean on. `qa_helpers` exists as cross-app QA
  fixture glue, not as a home for behaviour tests. The spec decides between landing the test there,
  splitting its assertions by app (a `course_applications` case for the application-linked
  registration, a `learner_management` case for the plain one) so no single new home is needed, or
  another shape research didn't anticipate. Whichever way this goes, `course_interest`'s presence in
  the same file needs the same decision, not a separate one.
- Whether `test_setup_initial_prod_data.py`'s `Organisation` assertion moves to `organisations`' own
  suite (which already tests its receivers) or stays in `accounts` as a documented exception, since
  it verifies a Site-creation signal's side effect rather than borrowing a convenience fixture.
- Whether `test_legal_doc_view.py`'s cache reset gets a small public reset function on the icon
  loader instead of reaching for `icons.loader._cache` directly, or stays as is.
- Whether `test_admin.py`'s cascade assertion moves to `referral_tracking`'s own suite (which
  already tests the FK it owns on `accounts.User`) or stays in `accounts`, documented, since it is
  exercising a cascade FK'd to `accounts`, not borrowing an unrelated fixture.

## Out of scope

- `accounts`' other ~26 test files: already clean on both rules, per
  `research_test_layout_audit.md`.
- The `form_engine -.-> accounts` edge (spec 9's) and any other app's baseline lines.
- Landing all four files' fixes in one commit rather than one rebase-friendly commit per file where
  the fixes are independent.

## Resources

- `research_test_layout_audit.md` (parent directory, §1 and §5 "accounts" row): the per-app
  findings this idea verifies and narrows to `accounts`.
- `freedom_ls/accounts/tests/conftest.py`: the reference conftest layering to keep.
- `docs/app_structure.md`: the runtime-dependency source of truth rule 2 checks against.
- `claude_plugins/django-stack/skills/testing/SKILL.md` and
  `claude_plugins/fls-dev/skills/testing/SKILL.md`: where spec 1 documents rule 2 in full.
