# Testing

## Setup
- Framework: pytest (pytest-django)
- Settings: `pyproject.toml`
- Default settings: `config.settings_dev`
- Run specific test: `pytest path/to/test_file.py::test_name`

## Creating Test Data

Use factory_boy factories for all test data creation. Never use `.objects.create()` directly.

- Import factories from the app's `factories.py` (e.g., `from freedom_ls.accounts.factories import UserFactory`)
- Override only the fields relevant to the test; let factories provide sensible defaults
- Always check existing factories before creating new ones
- See `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` for the full factory reference
- Avoid creating fixtures that are thin wrappers around factories. Rather just use the factories

## Test Patterns

### Model Tests

```python
@pytest.mark.django_db
def test_model_method(mock_site_context):
    """Test a specific model method."""
    instance = MyModelFactory(field1="value")
    result = instance.some_method()
    assert result == expected_value
```

### View Tests

```python
@pytest.mark.django_db
def test_endpoint(client, mock_site_context):
    """Test endpoint returns expected response."""
    user = UserFactory()
    client.force_login(user)
    response = client.get(reverse('app:endpoint'))
    assert response.status_code == 200
    assert response.context['key'] == expected_data
```

### Utility Tests

```python
def test_utility_function():
    """Test utility function."""
    result = utility_function(input_value)
    assert result == expected_output
```

### Error Tests

```python
@pytest.mark.django_db
def test_requires_field(mock_site_context):
    """Test that field is required."""
    with pytest.raises(IntegrityError):
        MyModelFactory(required_field=None)
```

## HTMX test patterns

All patterns in this section are **(currently available)** — usable today against the existing test client and HTMX integration.

For production-side HTMX conventions (header semantics, swap targets, validation status codes) see the `fls:htmx` skill.

### Simulating HTMX requests

Pass HTMX request headers via Django test client kwargs to exercise the `HX-Request` branch of a view. The most common kwarg is `HTTP_HX_REQUEST="true"`; related headers (`HTTP_HX_TARGET`, `HTTP_HX_TRIGGER`, `HTTP_HX_CURRENT_URL`) are added when the view inspects them.

```python
@pytest.mark.django_db
def test_topic_list_returns_partial_for_htmx_request(client, mock_site_context):
    user = UserFactory(email="student@example.test")
    client.force_login(user)

    response = client.get(
        reverse("student_interface:topic_list"),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert "<html" not in response.content.decode()  # partial, not full page

@pytest.mark.django_db
def test_topic_list_returns_full_page_for_normal_request(client, mock_site_context):
    user = UserFactory(email="student@example.test")
    client.force_login(user)

    response = client.get(reverse("student_interface:topic_list"))

    assert response.status_code == 200
    assert "<html" in response.content.decode()
```

### Asserting on `HX-Trigger` response headers

Views can emit client-side events by setting `HX-Trigger`. Tests should assert both that the header is present and that the JSON-shaped event payload matches.

```python
import json

@pytest.mark.django_db
def test_enrolment_emits_enrolled_event(client, mock_site_context):
    student = StudentFactory()
    client.force_login(student.user)
    course = CourseFactory()

    response = client.post(
        reverse("student_interface:enrol", args=[course.pk]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    triggers = json.loads(response.headers["HX-Trigger"])
    assert "enrolled" in triggers
    assert triggers["enrolled"]["course_id"] == course.pk
```

### 422-for-validation-errors convention

FLS returns HTTP 422 for HTMX validation errors so `hx-swap` can replace the form fragment without triggering a redirect. See `${CLAUDE_PLUGIN_ROOT}/resources/templates_and_cotton.md` for the production-side rule.

```python
@pytest.mark.django_db
def test_invalid_form_returns_422_with_error_fragment(client, mock_site_context):
    user = UserFactory(email="educator@example.test")
    client.force_login(user)

    response = client.post(
        reverse("educator_interface:cohort_create"),
        data={"name": ""},  # name is required
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert b"This field is required" in response.content
```

### Out-of-band swap testing

When a view returns multiple fragments swapped into different targets via `hx-swap-oob`, assert that the rendered response carries the OOB markup for each expected element id.

```python
@pytest.mark.django_db
def test_complete_topic_swaps_progress_bar_oob(client, mock_site_context):
    student = StudentFactory()
    client.force_login(student.user)
    topic = TopicFactory()

    response = client.post(
        reverse("student_interface:complete_topic", args=[topic.pk]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert 'hx-swap-oob="true"' in body
    assert 'id="progress-bar"' in body
```

At the unit-test level the response is raw bytes, so OOB assertions are necessarily string-based — they confirm the markup is *emitted*, not that the browser actually swapped it. Match the literal `hx-swap-oob` value the view sets (`"true"`, `"innerHTML"`, `"outerHTML"`, etc.). For an end-to-end check that the swap reaches the DOM, use a Playwright test (see `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md`).

### Auth-bypass anti-pattern

Manually constructing a request via `RequestFactory`, attaching `user` directly, and calling the view function looks convenient but skips middleware and the real permission decorators (`@login_required`, custom site / role checks). Tests pass while production breaks. Use `client.force_login(user)` so the request travels the real auth path.

```python
from django.test import RequestFactory
from freedom_ls.educator_interface.views import cohort_detail

# BAD — skips middleware and the @login_required / site-permission checks
factory = RequestFactory()
request = factory.get(reverse("educator_interface:cohort_detail", args=[cohort.pk]))
request.user = staff_user  # ← attaches the user without going through auth middleware
response = cohort_detail(request, cohort_pk=cohort.pk)
assert response.status_code == 200

# GOOD — exercises the real auth path through middleware and the URL dispatcher
client.force_login(staff_user)
response = client.get(
    reverse("educator_interface:cohort_detail", args=[cohort.pk]),
    HTTP_HX_REQUEST="true",
)
assert response.status_code == 200
```

For production-side HTMX conventions see the `fls:htmx` skill.

## Time-shaped code

**(planned for upcoming phase 2)** — The `time-machine` package is not yet installed; this pattern is documented now so phase-2 tests have a target.

Reach for `time-machine` whenever production behaviour depends on the current time: deadline checks, scheduled-job windows, token-expiry logic, "is open / closed" status, anywhere `timezone.now()` or `datetime.now()` drives a branch.

The pattern is to `travel` time around the **act** phase and assert on the resulting state. Do **not** patch out the comparison itself or freeze time around the production check in a way that hides the underlying logic — the test must exercise the real `now()` call inside the production code.

```python
import time_machine
from datetime import datetime, UTC

@pytest.mark.django_db
def test_cohort_deadline_passes_after_due_date(mock_site_context):
    cohort = CohortFactory(deadline_at=datetime(2026, 5, 1, tzinfo=UTC))

    with time_machine.travel("2026-05-02T00:00:01Z"):
        assert cohort.is_overdue() is True

@pytest.mark.django_db
def test_cohort_deadline_not_passed_before_due_date(mock_site_context):
    cohort = CohortFactory(deadline_at=datetime(2026, 5, 1, tzinfo=UTC))

    with time_machine.travel("2026-04-30T23:59:59Z"):
        assert cohort.is_overdue() is False
```

## factory_boy patterns matrix

**(currently available)** — decision guidance for which factory_boy primitive to reach for. Deep examples live in `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.

| Need | Reach for | Cross-link |
|---|---|---|
| A unique value per row (e.g. email, slug, sequence id) | `factory.Sequence` | `factory_boy.md` — Sequence |
| A related object that should be created automatically | `factory.SubFactory` | `factory_boy.md` — SubFactory |
| A related object that should be created **after** the parent (e.g. m2m / reverse FK) | `factory.RelatedFactory` | `factory_boy.md` — RelatedFactory |
| A field derived from other fields on the same instance | `factory.LazyAttribute` | `factory_boy.md` — LazyAttribute |
| A field that needs to call a function (no obj reference) | `factory.LazyFunction` | `factory_boy.md` — LazyFunction |
| Reusable named field combinations (e.g. `staff=True`) | `factory.Trait` in `Params` | `factory_boy.md` — Traits |
| Logic that must run after the model is saved (e.g. set password, attach m2m) | `@factory.post_generation` | `factory_boy.md` — post_generation |

If you find yourself calling `.objects.create()` in a test, stop and add a factory instead. See `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` for the full pattern reference.

## Test order independence

**(planned for upcoming phase 2)** — `pytest-randomly` will shuffle the suite by default, surfacing tests that depend on execution order.

The rule: **tests must pass in any order.** Forbidden patterns:

- Asserting on insertion order of querysets without an explicit `order_by(...)`.
- Assuming auto-incrementing PKs are sequential or start at 1.
- Sharing module-level mutable state between tests (e.g. a class attribute that one test mutates and another reads).
- Relying on a previous test having created data — every test must build its own fixtures via factories.

If a test fails only when run in isolation, or only when run as part of the full suite, that's order dependence; treat it as a bug, not a flaky test.

### `transaction=True` is expensive — justify it

The default `@pytest.mark.django_db` runs each test inside a transaction that is rolled back at teardown. `@pytest.mark.django_db(transaction=True)` instead runs each test in its own transaction and **truncates tables** between tests, which is dramatically slower *and* exposes signal handlers and `transaction.on_commit(...)` callbacks that the rollback path was hiding.

Use `transaction=True` **only** when the test genuinely needs:
- `transaction.on_commit(...)` callbacks to fire (e.g. webhook event delivery).
- `select_for_update` semantics inside the test.
- Cross-connection visibility (e.g. Playwright e2e tests where the browser runs in a separate process and must see committed data).

When `transaction=True` is used, **add a one-line comment** on the marker explaining the reason. Example:

```python
# transaction=True so that on_commit hooks for webhook delivery fire under test
@pytest.mark.django_db(transaction=True)
```

If you are tempted to add `transaction=True` for any other reason (it makes a flaky test pass, you don't know why the rollback path is failing), do not — it is masking a real bug in the test or the production code.

## Marker taxonomy

**(currently available)** — every test falls into exactly one of four buckets, all registered in `pyproject.toml`'s `[tool.pytest.ini_options]` `markers = [...]` (mandatory: `--strict-markers` is on, so an unregistered marker is a hard collection error):

- **Unmarked (default) = portable.** The downstream-valuable set — contract/unit tests that pass under any settings, theme, icon set, or installed-app list. Most tests belong here.
- **`playwright`** — browser-dependent; needs a running server (`live_server`) and a real browser. See the `fls:playwright-tests` skill. Lives under per-app `tests/e2e/` dirs.
- **`fls_internal`** — only valid under FLS's own settings, theme, branding, or demo content. Reach for it when a test's assertion is inherently tied to FLS's own repo state (a shipped `demo_content/` file excluded from the packaged distribution, for example) — not merely because the test happens to assert an FLS-default value it could instead assert as a contract.
- **`ci_only`** — existing slow / real-time tests, excluded from FLS's own default run too.

FLS's own `uv run pytest` runs everything except `ci_only` — it must exercise `fls_internal` and `playwright` tests against FLS's own settings, since that *is* FLS regression testing. A concrete downstream project instead runs
`uv run pytest -m "not playwright and not fls_internal and not ci_only"` to get only the portable contract set (this is the selection `commands/concrete/update_fls.md` runs at its downstream call sites).

**The reach-for-`fls_internal`-last rule:** every test that stays portable is real integration signal for a downstream. Before marking a test `fls_internal`, ask whether it genuinely depends on FLS's own repo/brand/demo state, or whether it's a contract test wearing a brand-literal disguise — see the worked examples further down this file (next to "Don't assert hardcoded config values").

**Scoping the marker:** prefer a file-level `pytestmark = pytest.mark.fls_internal` only when *every* test in the file is brand/demo-coupled (e.g. a file that only ever reads `demo_content/`). In a file that mixes portable and brand-coupled tests, mark the individual `fls_internal` tests instead — a blanket file-level marker would wrongly de-scope real integration signal a downstream needs.

## Collection safety for optional apps

**(currently available)** — a module that imports an optional app's factory or model at **module scope** (e.g. `from freedom_ls.course_applications.factories import CourseApplicationFactory` at the top of a test file) raises Django's model-registry `RuntimeError: Model class ... isn't in an application in INSTALLED_APPS` at **collection** time when a downstream has legitimately not installed that app. This aborts the *entire* pytest session (`Interrupted: N errors during collection`, exit code 2) — not just the one module.

### The guard (braces)

Place a module-top `INSTALLED_APPS` check **immediately above** the offending import, keyed on a plain string check (safe to read without app-registry readiness):

```python
from __future__ import annotations

import pytest
from django.conf import settings

if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```

`allow_module_level=True` is required — `pytest.skip()` at module scope is otherwise a usage error.

**Why not `pytest.importorskip` or `@pytest.mark.skipif`:**

- `pytest.importorskip("freedom_ls.course_applications")` doesn't help — the *package* is importable; it's the **model class definition** that raises `RuntimeError` because the model isn't registered under `INSTALLED_APPS`. `importorskip` only catches `ImportError` unless you pass an explicit `exc_type`.
- `@pytest.mark.skipif(...)` doesn't help either — the module-scope import statement executes (and raises) while pytest is still *collecting* the module, before the decorator is ever reached.

### The colocated `collect_ignore_glob` conftest (belt)

Add a `conftest.py` in the **same directory** as the guarded test files (`collect_ignore*` is scoped to the conftest's own directory) that skips importing them at all when the app is absent:

```python
# freedom_ls/course_applications/tests/conftest.py
from django.conf import settings

collect_ignore_glob: list[str] = []
if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    collect_ignore_glob = ["test_*.py"]
```

This is defense-in-depth: the conftest never imports the file at all (belt); the module-level guard skips cleanly even if something did import it (braces). Use the conftest for files that live entirely inside the optional app's own `tests/` dir; a test module that lives in a *different* app's `tests/` dir (a cross-app integration test) can't use a directory-level ignore without also hiding its sibling tests, so it relies on the module-top guard alone.

## Writing High-Value Tests

Every test must justify its existence. A test has value when it catches real bugs, documents important behaviour, or protects against meaningful regressions. Tests that merely exercise code without asserting anything interesting are noise.

### What to test

- **Business logic and domain rules** — the core "why" of the feature. If a method calculates scores, enforces permissions, or applies rules, test those rules thoroughly.
- **Edge cases that have bitten you** — empty collections, None values, boundary conditions, off-by-one errors.
- **Integration points** — where two systems meet (view + model, serializer + database, HTMX partial + context). These are where bugs hide.
- **Error paths that matter** — invalid user input, missing objects, permission denied. Only test error handling that could realistically occur.

### What NOT to test

- **Django/framework internals** — don't test that `CharField` stores strings, that `ForeignKey` creates a column, or that `reverse()` resolves a URL you just defined. Trust the framework.
- **Trivial CRUD with no logic** — a model with only auto-generated fields and no custom methods rarely needs its own test. If `MyModelFactory()` succeeds, you already know the model works.
- **Implementation details** — don't assert the exact SQL query, the number of times a method was called, or internal state that could change during refactoring. Test observable behaviour, not how it's achieved.
- **Duplicate coverage** — if one test already proves a code path works, don't write another that proves the same thing with slightly different data unless the variation exercises a genuinely different branch.
- **The absence of arbitrary things** — `assert not hasattr(obj, "x")` or `assert "x" not in context` proves nothing when `x` is a name the code never produces; it passes for any name you invent (`assert not hasattr(obj, "squirrels")`). If a refactor removed something, assert the replacement behaviour, not the disappearance of the old internal.

### Qualities of a good test

1. **Focused** — tests exactly one behaviour or rule. If the test name needs "and" in it, split it.
2. **Readable** — a developer can understand what's being tested and why without reading the implementation. The test name and docstring are the spec.
3. **Resilient** — doesn't break when you refactor internals. Tests that are tightly coupled to implementation details create drag, not safety.
4. **Fast** — avoids unnecessary setup. Only create the data the test actually needs.
5. **Honest** — fails when the behaviour is broken, passes when it works. No tests that pass by coincidence.

### Tautology guidance — worked example

**Expected values must be hard-coded oracles, independent of the production code.** This rule does not say "do not test derivations" — it says the expected value must come from your understanding of the spec, written down by hand, not from re-running the production formula in the test.

```python
# BAD — re-runs the production formula; passes by coincidence
def test_course_progress_calculation_bad():
    completed, total = 3, 4
    expected = (completed / total) * 100  # same arithmetic the code uses
    assert calculate_progress_percent(completed, total) == expected

# GOOD — independent oracle
def test_three_of_four_topics_complete_is_seventy_five_percent():
    assert calculate_progress_percent(completed=3, total=4) == 75
```

Rule of thumb: **if you delete the production code and your test still computes the expected value correctly, your test is a tautology.** A correct test cannot tell you the right answer on its own — it must compare the production output against a value you wrote down by hand.

### Red flags in tests

- A test with no meaningful assertions (or only `assert response.status_code == 200` when the view does complex work)
- A negative-existence assertion (`assert not hasattr(...)`, `assert key not in context`) where the named thing was never part of the contract — equivalent to asserting `not hasattr(obj, "squirrels")`
- A test that creates 10 objects but only uses 2
- Multiple tests that are copy-pasted with one field changed — use `@pytest.mark.parametrize`
- A test that mocks so much that it's no longer testing real behaviour
- A test file with 50 tests for a model that has 2 methods

### Writing Tests

1. Use descriptive names explaining what's tested
2. Include docstrings
3. Use `@pytest.mark.django_db` for database tests
4. Use `mock_site_context` for site-aware models
5. Write one test at a time
6. No conditionals in tests - test one path at a time

### Assertions

- Be explicit: `assert result == []` NOT `assert type(result) is list`
- No if statements in tests
- Use `pytest.raises` for exceptions
- Assert exact values, not types

### Site-Aware Models

Always use `mock_site_context` fixture:

```python
@pytest.mark.django_db
def test_creation(mock_site_context):
    instance = MyModelFactory()
    assert instance.site is not None
```

**Don't manually set site** - `mock_site_context` handles it automatically.

### Keep Tests DRY

Avoid repetition:
- Use factories with overrides instead of duplicating setup code
- Create helper functions for complex multi-step setup
- Use parameterized tests

## TDD Workflow

### Red-Green-Refactor Cycle

1. **RED** - Write failing test (verify it fails)
2. **GREEN** - Write minimal code to pass
3. **REFACTOR** - Improve design (tests still pass) **and remove useless things** — delete assertions or whole tests that no longer prove anything, e.g. a check tied to internals you just removed, or an absence-of-arbitrary-thing assertion. Refactoring is not only about production code; the test you just wrote also gets cleaned up here.
4. **REPEAT** - Next test

IMPORTANT: Do not forget the refactor step. All tests should be clean and DRY!

### New Features

1. Understand requirements (models, views, behavior, edge cases)
2. Follow RED -> GREEN -> REFACTOR -> REPEAT

### Bug Fixes

1. **Understand bug** - Read code, identify behavior
2. **Write failing test** - Proves bug exists (ask before implementing)
3. **Verify test fails** - Don't continue until it does
4. **Fix bug** - Minimal code
5. **Verify test passes**
6. **Run all tests** - Ensure no regressions

### Legacy Code

1. Read code
2. Check existing tests
3. Create test file if needed: `freedom_ls/<app_name>/tests/test_<module>.py`
4. Write tests one at a time
5. Run each test

## Test Coverage

Cover these for each feature:
- Happy path
- Edge cases (empty, None, boundaries)
- Error cases (invalid inputs)
- Business logic (custom methods)
- Relationships (ForeignKey, M2M)
- Permissions (if applicable)

## Key Rules

1. Write tests BEFORE implementation (TDD)
2. Make one test at a time
3. Use `mock_site_context` for site-aware models
4. Use factory_boy factories for test data — never `.objects.create()`
5. Don't hardcode URLs - use `reverse()`
6. Be explicit in assertions
7. Keep tests focused and DRY

# Some guidelines

When testing validation logic: Test the happy and unhappy path. Don't just test things that will pass, assert that validation FAILS when it is supposed to

Never test that a hardcoded configuration value is what it is meant to be. Eg never say `assert config.hardcoded_value == [whatever]` or `assert "something" in config.hardcoded_value`

This also covers the subtler version where you read live configuration and run it **through** the code under test, then assert the **derived** result against a hardcoded expected — eg loading a real theme `.css` and asserting `resolve_color(load_theme("first_class")) == "#283593"`, or `email_safe_font_stack(theme["font-sans"]) == "sans-serif"`. Configuration exists precisely so it can change; a test like that breaks the day someone re-skins a theme or edits a setting, even though the code is still correct, and it duplicates the behaviour your controlled-input tests already cover. Test the function with an explicit input instead (`assert resolve_color({"color-primary": "#283593"}) == "#283593"`). If you genuinely need to know that the *real* shipped config still resolves, assert that via a system check / smoke test that the resolution succeeds (no exception) — not by pinning the exact values.

**Worked examples from FLS's own de-branding pass** (each swaps an FLS-default literal for a contract assertion, a pinned input, or an `fls_internal` marker — see "Marker taxonomy" above for when each applies):

- **Ambient-default icon viewBox** — `icons/tests/test_renderer.py::test_returns_svg_with_viewbox` hardcoded `viewBox="0 0 24 24"` on the *ambient* default icon set. Rewritten to `assert re.search(r'viewBox="0 0 \d+ \d+"', result)` — matches `icons/tests/test_no_font_awesome.py`'s existing style, and is proven to actually flex (not just asserted to in theory) by a second case that stubs a non-`24 24` glyph set and asserts the same regex against it.
- **Pinned icon set — leave as-is.** `icons/tests/test_renderer.py::test_lucide_icon_set` asserts the literal `viewBox="0 0 24 24"` under `@override_settings(FREEDOM_LS_ICON_SET="lucide")`. The set is *pinned*, so the literal is a controlled-input assertion, not brand coupling — don't loosen it to a regex. Where a test stubs one specific icon set (e.g. `icons/tests/test_render.py::test_literal_glyph_in_active_set`) without pinning `FREEDOM_LS_ICON_SET`, pin it with `@override_settings(FREEDOM_LS_ICON_SET="heroicons")` so the test doesn't silently depend on heroicons being the ambient default.
- **Logo scaling with an independent oracle** — `accounts/tests/test_email_utils.py::test_email_logo_dimensions_scales_to_display_height` used to hardcode the shipped `512x248` logo. Re-deriving the expected width by re-running the SUT's own `round(nw * H / nh)` formula against that asset would be a tautology (see "Tautology guidance" above) — instead, `monkeypatch` a **controlled** native size onto `image_dimensions` and assert against a **hand-computed** expected width:

  ```python
  def test_email_logo_dimensions_scales_to_display_height(monkeypatch):
      monkeypatch.setattr(email_utils, "image_dimensions", lambda _p: (300, 100))
      # 300 wide at native height 100, scaled to display height 48 -> 144 (hand-computed)
      assert email_logo_dimensions("images/any.png") == (144, EMAIL_LOGO_DISPLAY_HEIGHT)
  ```

- **Demo content → `fls_internal`** — `content_engine/tests/test_demo_content_picture_titles.py` reads a `demo_content/` file that is excluded from the packaged distribution; a downstream hits `FileNotFoundError`, not a mismatch. The whole file is demo-coupled, so a file-level `pytestmark = pytest.mark.fls_internal` is correct there.

Never test trivial model instance creation. Eg never test that default values are as they should be, or that passed in values are saved unless the model is meant to do something unusual. Assume Django's model implementation works, don't waste time testing it.

Never test trivial Admin panel functionality. Assume Django's Admin interface just works, don't write tests that assert that the admin shows up exactly as it was configured because it will always do that. If you have done something unusual in the admin then test that.

### No unexpected network sockets

**(planned for upcoming phase 2)** — once `pytest-socket` is installed, all sockets are blocked by default during the test run.

The fix when a test needs to call out is **not** to whitelist sockets. Mock at the boundary instead — the `requests.post` call, the SDK client, the email backend — so the test exercises the real production code up to the boundary and replaces only the outbound side. See "Mock only at system boundaries" in the testing SKILL.md for the underlying rule.

### Branch coverage

**(planned for upcoming phase 2)** — branch coverage will be measured as part of phase 2; the threshold approach (ratchet vs. fixed target) is deferred to that spec.

Implication for test authoring today: when a test exercises a branch (`if x:` vs. `else:`, `try:` vs. `except:`, presence vs. absence of an HTMX header), make sure both sides have a test. Don't write only the happy path.

## Future phases

Phase 1 (this update) lands the skill / resource changes. Subsequent phases (tooling install, cleanup of flaky / redundant tests, factory sweep, parametrize / tautology fixes, coverage gaps, E2E hardening) are tracked in their own spec directories under `spec_dd/`. The high-level dependency map and the skip-list rationale (why we are not adopting `freezegun`, `assertpy`, `cosmic-ray`, `pytest-rerunfailures`, `pytest-django-queries`, or visual-regression tools) live in the Phase-1 spec at `spec_dd/<phase>/testing-best-practice/1. spec.md`.
