# Research: Test organisation — conftest, factories, fixtures

Topic feed for the testing skill update. Two parts: external best practice (cited), then
current-FLS-state-and-gaps found by reading the actual repo.

## PART A — External best practices

### conftest.py placement and discovery

- pytest walks **upward** through the directory tree from the test file being collected,
  collecting every `conftest.py` on the way; fixtures defined closer to the test **override**
  same-named fixtures defined higher up. A test can never reach a fixture defined in a sibling
  or child directory — only ancestors.
  [pytest fixture reference](https://docs.pytest.org/en/stable/reference/fixtures.html)
- Practical layering rule that falls out of this: put a fixture at the **shallowest directory
  that still contains every consumer**, no shallower. A fixture used by one app's tests belongs
  in that app's `tests/conftest.py`, not the project root — putting it at the root just to save an
  import bloats every other app's fixture namespace and risks accidental name collisions.
  [Pytest with Eric — conftest best practices](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/)
- Root/project `conftest.py` is the right place for **cross-cutting, always-on** fixtures —
  autouse settings resets, global `django_db_setup` customisation, or a DB-blocker unblock
  wrapper — not for feature-specific test data helpers.
  [pytest-django database docs](https://pytest-django.readthedocs.io/en/latest/database.html)
- `conftest.py` files are **not test files** in the "must be imported" sense — pytest
  auto-discovers and auto-injects their fixtures; plain helper functions dropped into a
  `conftest.py` (not decorated `@pytest.fixture`) get no such auto-discovery and still require
  an explicit import at the call site, which defeats the reason to put them in `conftest.py` in
  the first place. [pytest fixture reference](https://docs.pytest.org/en/stable/reference/fixtures.html)
- Custom `django_db_setup` / `django_db_blocker` overrides must **chain** the original fixture
  as an argument (`def django_db_setup(django_db_setup, django_db_blocker):`) so Django's own
  setup still runs, and any raw DB access outside the standard transaction-rollback fixtures
  must be wrapped in `with django_db_blocker.unblock():`.
  [pytest-django database docs](https://pytest-django.readthedocs.io/en/latest/database.html)

### factory_boy organisation

- Two viable layouts exist in the wild: factories colocated under each app's `tests/` package,
  or a single `factories.py` per app at the app root (or a `factories/` package for very large
  apps). Both are legitimate; pick one and apply it project-wide.
  [factory_boy best practices (camilamaia)](https://github.com/camilamaia/factory-boy-best-practices),
  [factory_boy docs](https://factoryboy.readthedocs.io/)
- **SubFactory** wires a required FK; pass the **Factory class** directly for the normal case.
  For a genuine circular dependency between two factories (A needs B, B needs A), pass the
  **absolute dotted-string import path** instead of the class object — `factory.SubFactory(
  "app.factories.OtherFactory")` — so neither module needs to import the other at load time,
  breaking the import cycle. Watch for infinite recursion when both sides eagerly build the
  other; break the loop by constructing one side with the FK explicitly `None` first.
  [factory_boy reference docs](https://factoryboy.readthedocs.io/en/stable/reference.html)
- Nullable/optional fields should not be defaulted to a value in the base factory — model them
  as an opt-in **Trait** so the base factory stays minimal and every test that doesn't care
  about the field isn't paying for it (extra rows, extra queries, extra coupling).
  [factory_boy best practices (camilamaia)](https://github.com/camilamaia/factory-boy-best-practices)
- Factory vs fixture: a **factory** is for "build me a model instance with sensible defaults,
  overridable per test." A **fixture** is for "wire up something environmental" (a mocked
  boundary, a client, a temp file, DB setup). When a fixture's entire body is `return
  SomeFactory(**fixed_kwargs)` with no other setup, it isn't earning its keep — call the factory
  directly in the test instead. Fixtures that return a **callable** ("factory-fixtures") are the
  right middle ground when the caller needs to parametrise something a plain factory call can't
  express cleanly (e.g. because it depends on other fixtures like a mocked site context).
  [factory_boy docs](https://factoryboy.readthedocs.io/), [pytest fixture reference](https://docs.pytest.org/en/stable/reference/fixtures.html)
- General Django app-boundary guidance: don't let one app's model/factory module import
  directly from another app's `models.py` in a way that creates a cycle; prefer one-directional
  dependency flow (optional/feature apps depend on core apps, never the reverse), and use
  `apps.get_model()` or string `"app_label.Model"` references where Django itself needs to defer
  resolution.
  [Django Forum — avoiding circular imports across apps](https://forum.djangoproject.com/t/best-practices-for-avoiding-circular-imports-and-maintaining-app-independence-in-django/37946)

### Fixture scope and shared-mutable-state (critical under pytest-randomly)

- Default to **function scope**. Only widen to `module`/`session` when profiling shows the setup
  is genuinely expensive (schema creation, a session-scoped external process) — not "it would
  save a bit of typing."
  [QASkills — pytest fixture scope guide](https://qaskills.sh/blog/pytest-fixtures-scope-complete-guide)
- A session/module-scoped fixture that hands back a **mutable object** (dict, list, model
  instance later `.save()`d by a test) is a live isolation bug: one test's mutation leaks into
  every later test that shares the fixture. This is exactly the failure mode `pytest-randomly`
  is designed to surface — a suite that only fails in a *shuffled* order has an order dependency
  hiding in a fixture (or in test-level global state) that file-order execution was masking.
  [TheCodeForge — pytest mutable fixture trap](https://thecodeforge.io/python/unit-testing-pytest/),
  [Qualflare — pytest flaky tests](https://qualflare.com/blog/pytest-flaky-tests/)
- The safe pattern for "I need something session-scoped for cost reasons but each test needs a
  clean view of it": build the expensive read-only part at session scope, then reset/verify the
  per-test-mutable part at function scope, and make that reset **idempotent**
  (`get_or_create`, explicit cache-clear) so it's correct regardless of what ran before it.
  [TheCodeForge — pytest mutable fixture trap](https://thecodeforge.io/python/unit-testing-pytest/)
- pytest resolves fixtures by a dependency graph, not by definition order or by name proximity
  in the file — higher-scoped fixtures instantiate before lower-scoped ones inside a single
  test's chain, regardless of where they're written. Don't rely on "it happens to run first."
  [pytest fixture reference](https://docs.pytest.org/en/stable/reference/fixtures.html)

### File/dir layout and pitfalls

- Conventional Django/pytest layout: `app/tests/test_<module>.py`, one test file roughly per
  production module, tests **grouped by behaviour** inside the file (one test = one behaviour),
  not by mirroring internal function structure.
  [Pytest with Eric — organizing tests](https://pytest-with-eric.com/pytest-best-practices/pytest-organize-tests/)
- Common pitfalls called out across the sources above:
  - A fixture defined too deep (in a leaf conftest) when multiple sibling dirs need it — causes
    duplicate near-identical fixtures instead of one shared one.
  - A fixture defined too shallow (root conftest) when only one app needs it — pollutes the
    global fixture namespace and invites accidental shadowing.
  - Session-scoped fixtures holding **mutable** state, invisible until `pytest-randomly`/`xdist`
    reorders or parallelises the run.
  - **Import-time DB/model access**: importing a model or a factory that touches the Django app
    registry at **module scope** in a test file fails at **collection**, not at test-run time —
    and since collection happens before any test executes, a single bad import aborts the whole
    session, not just that file.
  - Forgetting `django_db_blocker.unblock()` around raw DB access inside a customised
    `django_db_setup`.

## PART B — Current FLS state and gaps

### Root conftest (`freedom_ls/conftest.py`)

Read in full. Holds:
- Three **autouse** cross-cutting fixtures — `_disable_force_site_name`,
  `_disable_preview_overrides`, `_clear_course_access_backend_cache` — correctly placed at root
  since they affect every test regardless of app. Good example of "root conftest = project-wide
  invariants."
- Several **factory-fixtures** (fixtures returning callables): `logged_in_client`,
  `make_temp_file`, `course_with_topic`. Legitimate use of the pattern — each composes more than
  a single factory call or wires a fixture dependency (`mock_site_context`) a bare factory call
  can't express.
- A **wildcard re-export** of Playwright fixtures: `from freedom_ls.tests.playwright_fixtures
  import *  # noqa: F403` (line 16), justified in a comment as "so tests can consume them without
  importing the fixtures module directly." This makes Playwright-only fixtures
  (`logged_in_page`, `reset_local_storage`) globally available to every non-Playwright test in
  the project, not just the `tests/e2e/` dirs that actually use them — worth a second look: is
  the cost (global namespace pollution, `noqa: F403` bypassing the "no wildcard import" lint
  rule) worth the convenience versus scoping the re-export to a conftest under `tests/e2e/`
  directories instead?
- `mock_site_context` (not shown above but defined here) is the load-bearing fixture almost
  every other fixture/test depends on — correctly rooted since virtually all site-aware tests
  need it.

### App-level conftests (4 found, matches the 4 named in the brief)

- `freedom_ls/accounts/tests/conftest.py` — clean example of the pattern: two fixtures
  (`mock_legal_blobs`, `legal_repo_mock`) plus one private module-level helper function
  (`_seed_default_legal_docs`, underscore-prefixed, never a fixture) that only the fixtures in
  the same file call. This is the shape to point to as the reference pattern: fixtures are
  fixtures, plain helpers are private and underscore-named so nothing mistakes them for
  auto-discovered fixtures.

- `freedom_ls/panel_framework/tests/conftest.py` — the most sophisticated conftest in the repo,
  and a good worked example of the "expensive session setup + idempotent function-scope reset"
  pattern from Part A:
  - `_panel_test_tables` (autouse, `scope="session"`) creates three test-only stub DB tables once
    via `schema_editor()`, wrapped in `django_db_blocker.unblock()` — correct use of the
    blocker-unblock pattern.
  - `_panel_test_permissions` (autouse, function-scoped) is **explicitly commented** as
    function-scoped *because* other tests elsewhere in the suite run
    `@pytest.mark.django_db(transaction=True)` and truncate tables, which would silently wipe a
    session-scoped permissions fixture — and it clears the `ContentType` cache and uses
    `get_or_create` to stay idempotent regardless of run order. This is exactly the
    isolation-under-pytest-randomly discipline Part A recommends, already practised here — worth
    citing verbatim as the skill's worked example rather than inventing a new one.
  - Comment banner states "no cross-app imports" and a docstring on the stub-model block warns
    these test-only models must never get real factory_boy factories — a second concern
    (cross-app import boundary discipline) folded into the same file, worth calling out
    explicitly as a rule rather than leaving it implicit in a comment.
  - `_use_panel_test_urls` (autouse) swaps `ROOT_URLCONF` per test — another example of an
    app-isolation fixture that belongs at this level, not root, because only `panel_framework`
    tests need an isolated URLconf.

- `freedom_ls/course_applications/tests/conftest.py` — contains **only** the collection-safety
  guard (`collect_ignore_glob` gated on `app_not_installed(...)`), no fixtures. This is the
  documented "belt" half of the optional-app pattern already in the skill (see below) — good,
  consistent with the skill's own guidance.

- `freedom_ls/student_interface/tests/conftest.py` — mixes two different things in one file:
  1. A real pytest fixture (`courses`).
  2. Three **plain functions** that are not fixtures at all
     (`course_with_single_question_form`, `course_with_form`, `register_user_for_course`) —
     these require an explicit `from freedom_ls.student_interface.tests.conftest import
     course_with_form` in consuming test files, which is exactly the "helper function in
     conftest.py needs manual import, defeating the auto-discovery reason to put it there"
     pitfall from Part A. There's also a re-export of `reverse_url` from the root conftest with a
     comment explaining that this conftest "shadows" the root one for a specific import path —
     a fragile, easy-to-miss reason for behaviour that a reader wouldn't expect from a
     `conftest.py`.
  - Worth codifying a rule: conftest.py holds `@pytest.fixture`-decorated fixtures (plus
    private, underscore-prefixed helpers those fixtures call); anything meant for **manual**
    import by test files belongs in a plain module (e.g. `helpers.py` or alongside `factories.py`),
    not `conftest.py`, so the file's contents match what a reader expects auto-discovery to
    provide.

### Factories (10 `factories.py` files found)

`app_authentication`, `student_progress`, `content_engine`, `site_aware_models`,
`role_based_permissions`, `webhooks`, `student_management`, `accounts`, `course_applications`,
`course_interest` — every one lives at the **app root** (`freedom_ls/<app>/factories.py`), not
under `tests/`. This is a deliberate, already-documented FLS convention (`factory_boy.md`
line 5: "Every Django app that has models should have a `factories.py` file at
`freedom_ls/<app>/factories.py`") that differs from the "factories live under `tests/`" layout
some external sources describe — and it's the right call *for this project*, because:
- Factories are imported **across app boundaries** by other apps' test suites (see below), and
  importing from another app's `tests/` package as if it were a normal module is unusual and
  would blur the "tests" vs "production-adjacent code" boundary; an app-root `factories.py`
  reads like ordinary importable app code.
- All follow the same base-class discipline: subclass `SiteAwareFactory`
  (`freedom_ls/site_aware_models/factories.py`), not `factory.django.DjangoModelFactory`
  directly — consistent across all 10 files, nothing to flag here.

Cross-app import graph in these factories (module-scope, direct class imports — not the
string-SubFactory circular-safe form):
- `student_management`, `course_applications`, `course_interest`, `student_progress` each import
  `UserFactory` from `accounts.factories` and/or `CourseFactory` from `content_engine.factories`
  at module scope.
- Dependency direction is consistently **one-way**: optional/feature apps
  (`course_applications`, `course_interest`) depend on core apps (`accounts`, `content_engine`);
  no core-app factory imports back from an optional app. No actual cycle exists today, so the
  direct-class-import form is safe — but it is load-bearing on that direction never reversing.
  Worth codifying as an explicit rule ("factories may only import from apps lower in the
  dependency stack; if you ever need the reverse, switch that one `SubFactory` to the
  string-path form") rather than leaving it as an accidental property of current import order.
- None of the 10 factories.py files themselves gate their cross-app imports on
  `INSTALLED_APPS` — that gating instead happens one layer up, in the **test files** that import
  from `course_applications.factories` (per the skill's existing "Collection safety for optional
  apps" pattern). That split (factories import freely; test-file callers carry the guard) is
  consistent across the repo and worth stating explicitly as the rule, since it isn't obvious
  which layer is supposed to own the guard.

### Existing testing skill content (`fls-claude-plugin/skills/testing/SKILL.md`,
`resources/testing.md`, `resources/factory_boy.md`)

- `SKILL.md` already states the `test_<module>.py` naming rule and "one behaviour per test," and
  cross-links to `factory_boy.md` for factory patterns — but has **no section at all** on
  conftest layering, fixture scope, or where a new fixture should live. That's the gap this
  research feeds.
- `testing.md` line 17: "Avoid creating fixtures that are thin wrappers around factories. Rather
  just use the factories" — stated as a flat rule, but the codebase's own root conftest defines
  `course_with_topic`, a fixture whose body **is** two factory calls plus one `.items.create(...)`.
  It isn't a *thin* wrapper (it composes two factories and adds real relationship logic the
  factories alone don't express), so it isn't actually violating the stated rule — but the rule
  as written doesn't draw that line, and a future contributor reading only that sentence could
  reasonably read it as "never wrap a single factory call in a fixture" without the nuance of
  *why* `course_with_topic` earns its place. Worth tightening the rule text itself: "thin" means
  one factory call with fixed kwargs and nothing else; a fixture that composes multiple
  factories/relationships, or that depends on another fixture (`mock_site_context`) to work, is
  not thin and is the correct use of the factory-fixture pattern.
- The **"Collection safety for optional apps"** section (`SKILL.md` lines 221–235,
  `testing.md` lines 284–324) is the one existing piece of conftest-layering guidance in the
  skill today, and it's solid: module-top `INSTALLED_APPS` guard (the "braces") plus a
  colocated `collect_ignore_glob` conftest (the "belt"), with the `apps.is_installed()` helper
  factored into `freedom_ls/tests/app_guards.py` (`app_not_installed(...)`) rather than repeated
  per-conftest string checks. `course_applications/tests/conftest.py` uses the shared helper;
  worth checking (out of scope for this research file, but flag for the skill author) whether
  every optional-app `tests/conftest.py` uses `app_guards.app_not_installed(...)` consistently or
  whether any still inline the raw `settings.INSTALLED_APPS` string check the skill's own
  example shows (the example in `SKILL.md` itself uses the raw inline check, not the shared
  helper — inconsistent with what the real `course_applications` conftest does).

### Recommendations for the skill (summary)

1. Add a "Where does this fixture/factory go?" decision section: root conftest for
   project-wide autouse/cross-cutting fixtures only; app `tests/conftest.py` for fixtures used
   by ≥2 files within that app; leave single-test-file fixtures in the test file itself.
2. State the conftest-vs-plain-module rule explicitly: `conftest.py` = `@pytest.fixture`s (+
   private underscore-prefixed helpers those fixtures call). Anything meant for manual import
   goes in a plain module, not `conftest.py`. Cite `student_interface/tests/conftest.py` as the
   pattern to avoid, `accounts/tests/conftest.py` as the pattern to follow.
3. Tighten the "thin wrapper" factory-fixture rule with the `course_with_topic` /
   `logged_in_client` examples as the "not thin, composes real logic" counter-case.
4. Codify fixture scope default (function-scope by default; module/session only for
   profiled-expensive setup) and the idempotent-reset pairing, citing
   `panel_framework/tests/conftest.py`'s `_panel_test_tables` (session) +
   `_panel_test_permissions` (function, idempotent, `ContentType.objects.clear_cache()`) as the
   in-repo worked example — this is the single best existing example of pytest-randomly-safe
   layering in the codebase.
5. Codify the factory cross-app dependency direction rule (core apps never import optional-app
   factories; optional apps import core-app factories directly; reverse or peer-to-peer needs
   the string-form `SubFactory`) and state explicitly that the `INSTALLED_APPS` guard belongs in
   the **test file / conftest that imports** the optional factory, not in the factory module
   itself.
6. Fix the inconsistency between `SKILL.md`'s inline "Collection safety" example (raw
   `settings.INSTALLED_APPS` check) and the real `app_guards.app_not_installed()` helper used in
   the actual `course_applications` conftest — update the skill's own example to call the shared
   helper so the documented pattern matches the enforced one.
7. Consider (flag, don't mandate without owner input) scoping the Playwright fixture wildcard
   re-export in the root conftest down to a conftest under the `tests/e2e/` dirs instead of
   global re-export, to avoid every non-Playwright test collecting Playwright fixture names.

status: ok
