# Research: fixture/factory mechanics behind the testing-standards idea

Verifies the mechanics `idea.md` rests its rules on, against official docs and the versions
actually pinned in this repo. Builds on `research_test_organisation.md` Part A (general
conftest/fixture/factory best practice) — not repeated here. Structured by the five numbered
questions in the brief.

## Installed versions (from `pyproject.toml` / `uv.lock`)

- pytest: `>=8.4.2` constraint, **9.0.3** resolved in `uv.lock`.
- pytest-django: `>=4.11.1` constraint, **4.12.0** resolved.
- factory-boy: `>=3.3.3` (pinned floor, resolved to 3.3.3), with **faker 40.13.0**.
- pytest-randomly: `>=4.1.0`, **4.1.0** resolved.
- pytest-xdist: `>=3.8.0`, **3.8.0** resolved.
- pytest import mode: `pyproject.toml`'s `[tool.pytest.ini_options]` sets no `--import-mode`, so
  the repo runs pytest's default, **`prepend`** — confirmed still the default in pytest 9 (the
  team intended to eventually default to `importlib` but has since said prepend stays the
  default "for the foreseeable future"; see Sources). `-n`/xdist is **not** passed anywhere:
  not in `addopts`, not in `.github/workflows/tests.yml` (`uv run pytest -m "not playwright"` and
  `uv run pytest -m playwright --no-cov`, neither with `-n`). xdist is an installed dev
  dependency but not part of the repo's standard invocation today.

## 1. factory_boy dotted-string `SubFactory` / `RelatedFactory`

- **Exact syntax.** Both `SubFactory` and `RelatedFactory` accept, as their first positional
  argument, either a `Factory` subclass object **or** "the fully qualified import path to that
  Factory" — a plain dotted string ending in the factory's class name, e.g.
  `factory.SubFactory("users.factories.GroupFactory")`. There is no documented shorthand (no
  module-only path with an implicit "find the factory" convention, no relative-import form) —
  the string must be the complete `module.path.ClassName`. This is identical for `RelatedFactory`
  (its `factory` argument takes the same two forms, cross-referenced to the same
  circular-import section). factory_boy docs give no example or caveat about relative imports;
  treat the dotted path as an absolute Python import path, matching how `SubFactory`'s own
  worked example writes it (repo convention: `"freedom_ls.<app>.factories.<Class>"`).
- **When it resolves.** Lazily, at first use — not at class-definition or module-import time.
  This is the documented reason the string form exists ("such circular relationships require
  careful handling… breaking cycles"): the string is stored as-is; resolution happens inside
  factory_boy's declaration-evaluation machinery (`get_factory()` → `factory.utils.import_object()`,
  which does the equivalent of `importlib.import_module` + `getattr`) the first time that
  particular `SubFactory`/`RelatedFactory` declaration is actually built for an instance. Because
  Python caches imported modules in `sys.modules`, the *cost* of the target module's import is
  paid once; the attribute lookup happens every time the declaration is evaluated.
- **Gotcha — infinite recursion.** factory_boy's own docs warn: when two factories each eagerly
  build the other via `SubFactory`, you get infinite recursion. The documented fix is to break
  the loop by constructing one side with the FK explicitly `None` and wiring it up after.
- **Gotcha for the idea's optional-app use case, worth stating explicitly since the idea doesn't
  spell it out.** The string form defers *when* an import happens, not *whether* it succeeds. If
  `OtherFactory`'s module fails to import when the optional app isn't installed — e.g. its
  `Meta.model = "optionalapp.Model"` triggers `apps.get_model()`/`LookupError` at class-body
  evaluation time, which happens at module import — then a **direct class import** of
  `OtherFactory` at another factory's module scope fails at **collection time**, aborting the
  whole pytest session (per Part A's "import-time DB/model access... fails at collection, not at
  test-run time" pitfall). The **string form only postpones** that failure to the moment some
  test actually builds the field that needs it — and since `SubFactory`/`RelatedFactory` fields
  are evaluated on every instantiation unless a caller overrides them, in practice this means
  "postponed to the first test that instantiates the parent factory at all," not "avoided
  entirely." So: **the dotted-string form fixes a genuine circular-import problem between two
  factory modules; it does not, by itself, make a factory safe to import when its target app may
  be absent.** That safety still comes from the separate, already-documented mechanism: the
  `INSTALLED_APPS` guard living in the test file/conftest that imports the optional factory (plus
  `collect_ignore_glob`), never in the factory module. The idea keeps these two techniques
  correctly separate (string-`SubFactory` for real circular deps between factories;
  `app_not_installed`/`collect_ignore_glob` for optional-app collection safety) and does not
  conflate them — worth confirming this distinction stays explicit in the written skill text, since
  a reader could otherwise infer "use string SubFactory to make an optional-app dependency safe,"
  which isn't true on its own.
- No existing use of the string form appears anywhere in the current codebase
  (`grep 'SubFactory("' freedom_ls` — no hits), so this is new guidance, not a documented existing
  pattern; nothing to correct there.

## 2. conftest.py: plain functions and "don't import from conftest"

- **pytest's own reference docs** describe `conftest.py` purely as an auto-discovery mechanism:
  fixtures defined there "can be used by any test in that package without needing to import
  them." They do not, on the current fixtures-reference page, spell out the negative corollary
  (don't import *plain* functions from it) in so many words.
- **That corollary is documented elsewhere, and is real, established pytest guidance, not
  something Part A invented.** An older pytest docs page (2.x "Working with plugins and conftest
  files") states the practice in almost the exact words the idea/Part A use: "It is good practice
  for projects to ... never import anything from a conftest.py file", because a `conftest.py` not
  sitting under a package root can be ambiguous — `import conftest` may resolve to a different
  `conftest.py` elsewhere on `sys.path`/`PYTHONPATH`. Under `--import-mode=importlib` this
  ambiguity is structurally worse: importlib mode gives every test module a synthesized unique
  name so "test modules can't import each other" at all — the current pytest docs page on
  import mechanics states this explicitly (relevant if the repo ever switches import modes; it
  currently uses the default `prepend`, where cross-module import is technically possible but
  still fragile for the reasons above).
- **This is a live, acknowledged documentation gap in pytest itself**, not resolved into one
  authoritative page: open pytest issue #13148 ("Improve documentation around conftest-files and
  importing of fixtures") has a maintainer response proposing pytest "should discourage importing
  anything from test files or `conftest.py`" more clearly, precisely because doing so causes
  confusing behaviour (e.g. a session-scoped fixture appearing to run multiple times when
  imported into another module). This corroborates — via a currently-open pytest-dev issue, not
  just third-party blogs — that the idea's "manual import from conftest.py is an anti-pattern"
  framing matches pytest maintainers' own stated position, even though it isn't yet consolidated
  into one canonical docs page.
- **Repo import-mode check.** No `--import-mode` is set in `pyproject.toml`, so the repo is on
  pytest's default `prepend` mode. All `freedom_ls/<app>/tests/` directories are regular Python
  packages (have `__init__.py`), which is the case prepend mode handles safely — the
  name-collision risk the old docs page warns about applies to conftest files sitting *outside*
  a package, which isn't this repo's layout. This doesn't undercut the idea's rule (the "requires
  manual import, defeats auto-discovery" argument holds regardless of import mode) but it means
  the repo isn't currently exposed to the sharper `importlib`-mode failure mode; worth knowing if
  anyone ever proposes switching import modes for this project.
- **Verdict: the idea's rule is correct and appropriately hedged.** Nothing to flag as wrong; the
  citation trail (open pytest issue + the older docs page's literal wording) is stronger than
  what Part A cited (a third-party blog), worth folding into the skill's citation if it wants an
  official-pytest-side source alongside the blog.

## 3. Fixture scope with pytest-django, pytest-randomly, pytest-xdist

- **Session/module-scoped DB fixtures + `django_db_blocker.unblock()`.** Confirmed against
  pytest-django 4.12's own database docs and the repo's actual `_panel_test_tables`: any DB
  access outside the standard per-test transactional fixtures must be wrapped in
  `with django_db_blocker.unblock():`, and a custom `django_db_setup` override must chain the
  original fixture. `panel_framework/tests/conftest.py`'s `_panel_test_tables` does exactly this
  (session-scoped, autouse, `django_db_blocker.unblock()` around `schema_editor()` calls) — matches
  documented practice.
- **`transaction=True` flush interaction — confirmed, the idea's reasoning is correct.**
  pytest-django's own docs state plainly that non-transactional `django_db`-marked tests get
  data "saved in the database and will not be reset," while tests using real transactions
  (`transaction=True`, or anything that needs `TransactionTestCase` semantics) get the database
  **flushed** between tests, and session-scoped setup data must be **repopulated** because
  "the database is cleared between tests." That is precisely why `_panel_test_permissions` (the
  `ContentType`/`Permission` rows) must be function-scoped rather than session-scoped even though
  `_panel_test_tables` (the schema itself, DDL not data) is safely session-scoped: DDL survives a
  flush (`TRUNCATE`/`DELETE FROM`, not `DROP TABLE`), but rows don't. The repo's own comment on
  `_panel_test_permissions` states this exact reasoning; confirmed correct against pytest-django's
  documented flush semantics, not just plausible.
- **`ContentType` cache staleness — confirmed as a real, documented Django gotcha**, not an
  invented one: `ContentType.objects.get_for_model()`/manager caches results in-process. After a
  transaction-rollback or flush wipes the underlying rows, a stale cached `ContentType` PK can
  point at a row that no longer exists (or now belongs to different content), which is why
  `_panel_test_permissions` calls `ContentType.objects.clear_cache()` before its
  `get_or_create()`. This is standard, widely-documented Django testing advice (not unique to this
  repo) and the fixture's comment correctly names the mechanism.
- **pytest-randomly (4.1.0) — what it randomises, confirmed against its own docs/README.**
  Randomises **test collection order** each run (seeded, reported, and repeatable via
  `--randomly-seed`), and additionally resets the global `random.seed()` at the start of **every
  individual test**, not just once per session. Critically for this idea: **if factory_boy is
  installed, pytest-randomly resets factory_boy's own random state at the start of every test**
  (factory_boy's "fuzzy" declarations use `random`), and **if Faker is installed it resets Faker's
  random state too, since factory_boy uses Faker for most of its fake data** — confirmed via
  pytest-randomly's own README/docs, not inferred. So pytest-randomly's job is broader than "test
  order": it also guarantees any *given* seed reproduces the same factory-generated field values
  test-by-test, which is exactly why a session/module-scoped fixture handing back **mutable**
  state (an object a test then `.save()`s or mutates) is the dangerous pattern — reordering
  changes which test "goes first" and inherits which mutation, even though the underlying
  random data generation itself stays reproducible per seed. Confirms the idea's framing
  ("pytest-randomly is built to expose" this class of bug) rather than needing correction.
- **`_panel_test_permissions` function-scope requirement — confirmed, not merely asserted.**
  Verified by reading the fixture directly (`freedom_ls/panel_framework/tests/conftest.py`
  lines 107–129): it's `@pytest.fixture(autouse=True)` (function-scoped, the default), its
  docstring states the `transaction=True`-flush reasoning verbatim, and it clears the
  `ContentType` cache then uses `get_or_create()` for exactly the idempotency Part A's "expensive
  read-only part at wide scope, reset the mutable part at function scope, idempotently" pattern
  describes. This is a correct, already-in-repo worked example; nothing to fix.
- **pytest-xdist (3.8.0) — installed but not invoked (`-n` absent everywhere: `addopts`,
  CI workflow).** If it were ever turned on, the relevant mechanics (confirmed against
  pytest-django's DB docs and general pytest-xdist behaviour, not this repo's own docs, since the
  repo doesn't exercise this path today): pytest-xdist runs each worker as an **independent
  pytest session in its own process**, so "session scope" means *once per worker*, not once
  globally — `_panel_test_tables` would re-run its `schema_editor()` DDL once per worker, which is
  safe *because* pytest-django gives each xdist worker its **own separate test database** by
  default (`django_db_modify_db_settings_xdist_suffix` appends a per-worker suffix to the DB
  name) specifically so parallel transactional tests don't collide. So xdist wouldn't break the
  `_panel_test_tables`/`_panel_test_permissions` split as designed — each worker gets its own
  fresh schema and its own idempotent permission rows — but it's worth noting in the skill (as a
  "why this still works if xdist is ever turned on" aside) rather than assuming it, since the repo
  doesn't currently prove this empirically.

## 4. Test-only models via `connection.schema_editor()` in conftest

- **No single official "how to create a test-only model" page exists** in either Django's or
  pytest-django's docs; the pattern (subclass `models.Model`, set `Meta.app_label`, register into
  `apps.all_models[label]`, then `schema_editor().create_model()`/`delete_model()` in a
  session-scoped fixture with teardown) is a documented-by-example community technique (see
  Sources), consistent with what `panel_framework/tests/conftest.py` does — nothing in official
  docs contradicts it.
- **A newer, narrower official alternative exists and is worth naming, without overturning the
  idea's choice.** pytest-django **4.12.0 — the exact version pinned in this repo's `uv.lock`** —
  added `@pytest.mark.django_isolate_apps("app_label", ...)` and a `django_isolated_apps` fixture,
  wrapping Django's own `django.test.utils.isolate_apps()`. Both are confirmed, from Django's own
  docs, to do **registry isolation only**: they let you define a `models.Model` subclass inside a
  test "cleanly deleted afterward, with no risk of name collisions" — but neither Django's docs
  nor pytest-django's docs say this creates any database table. It exists for testing a model
  **class's** behaviour (field definitions, `Meta` options, validation) without touching the DB at
  all — `isolate_apps` is documented as usable from plain `SimpleTestCase` (no DB). **It does not
  cover panel_framework's actual need**: the stub models there (`StubModel`/`StubChild`/
  `StubProtectedChild`) need real rows, real `ContentType`/`Permission` entries, and real
  `on_delete` collector behaviour (`CASCADE`/`PROTECT` exercised against actual FK rows) — none of
  which `isolate_apps`/`django_isolate_apps` provides. So: **the idea's schema_editor technique is
  not wrong and is not superseded** by the new pytest-django feature; the two solve different
  problems (model-definition-only vs. real-DB-row scenarios), and the skill should say so rather
  than silently drop the schema_editor technique in favour of the "newer" one. Worth one line in
  the skill noting `django_isolate_apps`/`isolate_apps` as the right tool for the narrower
  "just need a model class to exist, no DB rows" case, so a future author doesn't reach for
  `schema_editor()` when the lighter tool would do.
- **Gotchas confirmed relevant to this repo, and one confirmed *not* relevant:**
  - `app_label` **is required** on any model defined outside its "real" app's `models.py` — the
    stub models correctly set `Meta.app_label = "freedom_ls_panel_framework"`.
  - A known pytest-django gotcha (its issue tracker: "Tables in test db are not created for
    models with app_label" under `--no-migrations`) does **not** apply here: the repo runs with
    normal migrations (no `--no-migrations` flag anywhere in `pyproject.toml`/CI), confirmed by
    grep — so this particular trap isn't live for this project, but the skill should still flag it
    if anyone later adds `--no-migrations` for speed.
  - A commonly-cited SQLite-specific gotcha (needing to toggle
    `schema_editor.connection.in_atomic_block = False` around `create_model()`, because SQLite's
    `ALTER TABLE` limitations force non-atomic DDL) does **not** apply to this project: FLS runs
    on **PostgreSQL 17**, which supports transactional DDL natively, and
    `panel_framework/tests/conftest.py` does not do this workaround — correctly, since it isn't
    needed on Postgres. Worth a one-line note in the skill so nobody "fixes" a non-bug by copying
    an SQLite-oriented blog post's workaround.
  - Manually registering into `apps.all_models[label][...] = Model` (as `_panel_test_tables` does)
    is the same registry Django's own `isolate_apps()` manipulates internally, just done by hand
    with matching manual teardown (`app_models.pop(...)`) instead of a context manager restoring
    it automatically — functionally equivalent, more verbose, defensible given the need to pair
    it with real `schema_editor()` DDL that `isolate_apps` doesn't provide anyway.

## 5. "Shallowest directory containing every consumer" / "one-file fixture stays local"

- **Not stated verbatim as a rule in pytest's official docs.** What pytest's fixtures reference
  *does* state authoritatively: conftest.py files are collected by walking **upward** from the
  test being collected, fixtures defined **closer** to a test **override** same-named fixtures
  defined higher up, and a test can never reach a fixture defined in a sibling or child directory
  — only an ancestor's. This upward-walk-and-override mechanism is real pytest mechanics
  (authoritative source), and the "put a fixture at the shallowest directory that still reaches
  every consumer" placement rule is the practical rule that *follows from* that mechanism (a
  fixture placed too deep literally cannot be seen by a sibling directory's tests; one placed too
  shallow pollutes every directory below it), but pytest's own docs never phrase it as an explicit
  prescriptive rule. The explicit phrasing comes from secondary, well-known community sources
  (already cited in Part A: Pytest with Eric's conftest-best-practices guide; the same guidance
  also appears in widely-cited pytest style guides such as Brian Okken's "Python Testing with
  pytest"). **Recommendation for the skill:** cite the pytest docs for the *mechanism*
  (upward walk + override-nearest-wins) as the authoritative "why," and keep the community guide
  as the source for the *prescriptive phrasing* Part A already uses — don't imply pytest's own
  docs state the placement rule outright, since they don't.
- "A fixture used by only one test file stays in that file" is the same rule taken to its logical
  endpoint (shallowest directory containing every consumer, where the consumer set is exactly one
  file) rather than a separately-sourced rule — no additional citation needed beyond the above.

## Summary for the idea author

1. String `SubFactory`/`RelatedFactory`: syntax and lazy-resolution claims are correct;
   flag one nuance worth stating explicitly in the skill text — the string form fixes circular
   imports between factories, it does **not** make a factory safe to use when its target app is
   absent (that's still the `INSTALLED_APPS`-guard's job).
2. conftest-import discouragement is real pytest-maintainer-acknowledged practice (open issue
   #13148, plus an older docs page's near-identical wording), stronger sourcing than the blog Part
   A cites — nothing to correct, one better citation to add.
3. All of `_panel_test_tables`/`_panel_test_permissions`'s stated reasoning (transaction=True
   flush, ContentType cache, idempotent reset) checks out against pytest-django's actual database
   docs, not just plausible-sounding comments. pytest-randomly's scope is confirmed broader than
   test order alone — it also reseeds factory_boy/Faker per test. xdist is installed but not
   currently invoked anywhere in this repo; if it ever is, the session-per-worker + per-worker-DB
   model means the existing session/function split still works, nothing to fix pre-emptively.
4. The idea's `schema_editor()` stub-model technique is correct and still necessary; pytest-django
   4.12.0's new `django_isolate_apps` (exact version pinned here) is a real, official, *narrower*
   alternative for model-definition-only cases with no DB rows — worth one line naming it as the
   lighter tool for that narrower case, not a replacement for the panel_framework use case.
5. "Shallowest directory" isn't pytest's own documented wording; it's the correct practical
   consequence of pytest's documented upward-walk/override mechanism. Keep both citations (docs
   for mechanism, community guide for the prescriptive phrasing) rather than implying pytest's
   docs state the rule outright.

## Sources

- factory_boy reference docs (SubFactory/RelatedFactory string form, circular imports):
  https://factoryboy.readthedocs.io/en/stable/reference.html
  https://github.com/FactoryBoy/factory_boy/blob/master/docs/reference.rst
- pytest fixtures reference (conftest discovery, override-nearest-wins, upward walk):
  https://docs.pytest.org/en/stable/reference/fixtures.html
- pytest import mechanisms (`--import-mode`, prepend default, importlib "test modules can't
  import each other"): https://docs.pytest.org/en/stable/explanation/pythonpath.html
- pytest issue on conftest-import documentation gap (maintainer position on discouraging
  imports from conftest.py): https://github.com/pytest-dev/pytest/issues/13148
- Older pytest docs on conftest/plugins ("never import anything from a conftest.py file"):
  https://docs.pytest.org/en/2.7.3/plugins.html (historical wording; see also secondary
  discussion at https://qaskills.sh/blog/pytest-fixtures-conftest-complete-guide-2026)
- pytest-django database docs (`django_db_blocker.unblock()`, `django_db_setup` chaining,
  transaction/flush semantics, xdist per-worker DB suffixing):
  https://pytest-django.readthedocs.io/en/latest/database.html
- pytest-django helpers docs (`django_isolate_apps` marker, `django_isolated_apps` fixture):
  https://pytest-django.readthedocs.io/en/latest/helpers.html
- pytest-django changelog (confirms `django_isolate_apps` added in 4.12.0, the version pinned
  in this repo): https://pytest-django.readthedocs.io/en/latest/changelog.html
- pytest-django issue on `isolate_apps` marker feature request/implementation:
  https://github.com/pytest-dev/pytest-django/issues/1253
- Django testing tools docs (`django.test.utils.isolate_apps`, registry-only, no DB table
  creation): https://docs.djangoproject.com/en/6.0/topics/testing/tools/
- pytest-django issue on `app_label` models being skipped under `--no-migrations`:
  https://github.com/pytest-dev/pytest-django/issues/1134
- pytest-randomly source/README (test-order randomisation, per-test `random.seed()` reset,
  factory_boy/Faker random-state reset per test):
  https://github.com/pytest-dev/pytest-randomly
- pytest-xdist docs/how-to (session scope is per-worker-process, not global):
  https://pytest-xdist.readthedocs.io/en/stable/how-to.html
  https://qaskills.sh/blog/pytest-session-fixture-with-xdist-workers
- Repo files read directly to verify claims:
  `freedom_ls/panel_framework/tests/conftest.py`, `freedom_ls/accounts/tests/conftest.py`,
  `freedom_ls/tests/app_guards.py`, `pyproject.toml`, `uv.lock`,
  `.github/workflows/tests.yml`.

status: ok
