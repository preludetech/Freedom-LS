---
name: testing
description: Write pytest tests. Use when implementing features, fixing bugs, or when the user mentions testing, TDD, or pytest
allowed-tools: Read, Grep, Glob
---

# Testing

This skill helps implement features and fix bugs using Test-Driven Development, following the Red-Green-Refactor cycle.

## When to use this skill

- **Implementing new features** — write tests first, then implement
- **Fixing bugs** — write a failing test that reproduces the bug, then fix
- **Refactoring** — ensure tests pass throughout
- User mentions "TDD", "test", "pytest"

## Key rules

- Test files: `freedom_ls/<app_name>/tests/test_<module>.py`
- Use `@pytest.mark.django_db` for database tests
- Use `mock_site_context` fixture for site-aware models — never manually set site
- Use factory_boy factories for all test data creation — never use `.objects.create()` directly
- Use `reverse()` for URLs, never hardcode
- No conditionals or loops in test bodies — one behaviour per test
- TDD cycle: RED (failing test) → GREEN (minimal code) → REFACTOR → REPEAT
- Tests must pass in any order. `pytest-randomly` randomises order on every run — do **not** add `@pytest.mark.order` to paper over ordering bugs; fix the test instead.
- Do not open network sockets in tests; `pytest-socket` blocks outbound sockets and only allows `127.0.0.1` / `::1`. Mock at the boundary, or add `@pytest.mark.allow_hosts(["host"])` for a genuine integration test (never `["*"]`).
- Use `time-machine` for time-shaped code (deadlines, expiry windows, scheduled jobs) — prefer `time_machine.travel(...)` over manual `datetime.now()` patching.
- Run the full suite in parallel locally with `uv run pytest -n auto` (xdist is opt-in, not baked into `addopts`).

See:
- `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` — full patterns, examples, TDD workflow, red flags
- `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` — factory patterns and available factories
- The `fls:playwright-tests` skill for browser / E2E tests
- The `fls:htmx` skill for production-side HTMX rules

Future phases (tooling install, flaky / redundant cleanup, factory sweep, parametrize / tautology fixes, coverage gaps, E2E hardening) are tracked under `spec_dd/`; see the "Future phases" section in `${CLAUDE_PLUGIN_ROOT}/resources/testing.md`.

## Best practices

### Test behaviour, not implementation

Assert on what a function **returns or does**, not **how it works inside**. Implementation tests break on every refactor and give false security.

```python
# BAD — re-implements the check; couples to current internals
def test_is_valid_email():
    email = "test@example.com"
    assert "@" in email and "." in email

# GOOD — asserts the observable contract
def test_valid_email_passes():
    assert is_valid_email("test@example.com") is True

def test_email_missing_at_fails():
    assert is_valid_email("not-an-email") is False
```

If you find yourself asserting call counts on internal helpers, reading private attributes, or matching exact SQL — stop. Test the output.

### Don't assert the absence of arbitrary things

A negative-existence assertion (`assert not hasattr(obj, "x")`, `assert "x" not in context`) only means something when `x` is a thing the code could *realistically* produce **and** its absence is the observable contract. Asserting the absence of a name the code was never asked to produce passes for any name you invent — it tests nothing.

```python
# BAD — proves nothing; passes for any made-up name
assert not hasattr(course, "preview_start_url")
assert not hasattr(course, "squirrels")  # ...exactly as meaningful

# GOOD — assert the positive behaviour the code now exhibits
assert course.detail_url == reverse("student_interface:course_detail", args=[course.slug])
```

This bites most often during a refactor that *removes* an internal attribute. Don't write a test to "prove it's gone" — the deleted internal was never part of the contract, and the attribute is absent by construction. Assert the new observable behaviour instead, and delete any leftover absence-check during the REFACTOR step.

### Don't write tautological tests

A tautological test re-derives the expected value from the input using the same logic as the code under test. It passes by coincidence and catches nothing.

```python
# BAD — the test is the implementation, run twice
def test_discount():
    price, rate = 100, 0.2
    expected = price * (1 - rate)
    assert apply_discount(price, rate) == expected

# GOOD — independent oracle; hard-coded answer for hard-coded input
def test_20_percent_off_100_is_80():
    assert apply_discount(100, 0.2) == 80

def test_discount_cannot_exceed_price():
    assert apply_discount(100, rate=1.5) == 0
```

The test must be an **independent source of truth**. If the code is wrong and the test repeats the same wrong logic, the bug is invisible.

This is the single most common failure mode. Watch for it in yourself: any time the "expected" value is computed with arithmetic, string-building, or a loop over the same input the code sees, you're writing a tautology.

### Name tests after behaviour

Good test names describe what is being verified, not which function is being called. They read like a spec.

```python
# BAD — tells you nothing
def test_user(): ...
def test_calculate(): ...
def test_1(): ...

# GOOD — subject, condition, expected outcome
def test_inactive_users_excluded_from_report(): ...
def test_discount_rounds_down_not_up(): ...
def test_missing_required_field_raises_validation_error(): ...
```

Format: `test_<subject>_<condition>_<expected>`. If the name needs "and", split the test.

### Arrange / Act / Assert

Keep the three phases visible, in order, with one of each:

```python
def test_registered_student_appears_in_cohort_roster(mock_site_context):
    # Arrange
    cohort = CohortFactory()
    student = StudentFactory()

    # Act
    cohort.register(student)

    # Assert
    assert student in cohort.roster()
```

No multi-act tests. If you need to call the code twice, that's two tests.

### Mock only at system boundaries

Boundaries = network, external APIs, filesystem, clock, randomness, subprocess. **Do not** mock code you own: internal helpers, ORM calls, your own service classes. Mocking internals locks the test to the current implementation and the mock will happily lie when the real code breaks.

```python
# BAD — mocks an internal helper; the real bug could live inside it
with mock.patch("freedom_ls.billing.services._apply_tax") as m:
    m.return_value = 110
    assert charge(100) == 110

# GOOD — mock the outbound HTTP call, let the real code run
with mock.patch("freedom_ls.billing.services.requests.post") as m:
    m.return_value.status_code = 200
    assert charge(100).succeeded
```

Rule of thumb: if a test needs more than two mocks, the unit under test has too many dependencies — refactor instead of piling on mocks.

### Parametrize for inputs, separate tests for behaviours

Use `@pytest.mark.parametrize` when the assertion shape is identical and only the input varies:

```python
@pytest.mark.parametrize("email,expected", [
    ("a@b.co", True),
    ("no-at-sign", False),
    ("double@@at.com", False),
    ("", False),
])
def test_email_validity(email, expected):
    assert is_valid_email(email) is expected
```

Use **separate tests** when the paths differ — success vs. raises, happy path vs. permission denied, create vs. update. Separate tests fail one at a time and read like documentation.

### Test validation both ways

For anything with a validation rule, test that invalid input is **rejected**, not only that valid input is accepted. A validator that accepts everything will pass a "happy path" test silently.

### Test hygiene

- No `if`, `for`, `try` in test bodies. Tests are linear.
- No shared mutable state between tests — use factories or fixtures; tests must pass in any order.
- Delete flaky tests. A flaky test is worse than no test. Fix the flakiness or remove it.
- Keep tests fast. A unit test taking >100ms is probably hitting real I/O.
- Coverage is a signal, not a goal. High coverage with weak assertions is worse than moderate coverage with strong ones.
- Don't assert on styling (CSS classes, colours, font sizes) — only on functionality.
- Don't assert hardcoded config values (`assert settings.TIMEOUT == 30`) — you're testing the config file, not behaviour. This includes the subtler variant: feeding **live** configuration (a settings value, a theme `.css`, any file that exists to be edited) *through* the code under test and asserting the **derived** result against a hardcoded expected (`assert resolve_color(load_theme("first_class")) == "#283593"`). Configuration is meant to change — such a test breaks the moment someone re-skins a theme or edits a setting, while testing nothing the controlled-input tests don't already cover. Instead, test the function with an **explicit input** (`assert resolve_color({"color-primary": "#283593"}) == "#283593"`), and let a system check or smoke test guard that the *real* config still resolves without error.
  - Worked examples from FLS's own de-branding pass: a `viewBox="0 0 \d+ \d+"` regex instead of the ambient-default `24 24` literal; pinning `@override_settings(FREEDOM_LS_ICON_SET=...)` when a test's subject really is one specific set (leave those literals as-is — they're controlled-input assertions, not brand coupling); a logo-scaling test that `monkeypatch`es a **controlled** native size and asserts a hand-computed width, never re-deriving from the shipped `512x248` asset; and `pytestmark = pytest.mark.fls_internal` for a test that reads `demo_content/` (excluded from the packaged distribution). Full examples in `${CLAUDE_PLUGIN_ROOT}/resources/testing.md`.

### Testing HTMX views

For HTMX-aware views at the unit-test level (currently available):

- Pass `HTTP_HX_REQUEST="true"` to the Django test client to exercise the partial-response branch.
- Assert on `HX-Trigger` response headers when the view emits client-side events (`assert "HX-Trigger" in response.headers`).
- Expect HTTP `422` on validation errors so HTMX swaps the form fragment instead of redirecting.

See `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (HTMX test patterns section) for full examples.

### Auth in tests

Use `client.force_login(user)` to authenticate. Do **not** patch `request.user` — that bypasses the real permission decorators (`@login_required`, site / role checks) and produces tests that pass while production breaks. See the resource file for the full anti-pattern example.

### Playwright tests

Playwright is slow; prefer pytest. Reach for Playwright only when testing interactivity that requires a real browser (HTMX swaps, Alpine-driven behaviour, JS-rendered UI). See the `fls:playwright-tests` skill for details.

### Marker taxonomy

- **Unmarked (default) = portable** — contract/unit tests; the downstream-valuable set.
- **`playwright`** — browser-dependent (see `fls:playwright-tests`).
- **`fls_internal`** — only valid under FLS's own settings/theme/branding/demo content.
- **`ci_only`** — existing slow tests (unchanged).

Reach for `fls_internal` only when a test genuinely can't run outside FLS's own repo/brand/demo state — **de-brand first** (pin the input or assert the contract; see "Don't assert hardcoded config values" above). Prefer a file-level `pytestmark = pytest.mark.fls_internal` only for wholly brand-coupled files; mark individual tests in mixed files.

See `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` for the full taxonomy and worked examples.

### Collection safety for optional apps

A module that imports an optional app's factory/model (e.g. `freedom_ls.course_applications`) at module scope raises Django's model-registry `RuntimeError` at **collection** time when a downstream hasn't installed that app — aborting the whole session, not just that module. Guard it immediately above the import:

```python
import pytest
from django.conf import settings

if "freedom_ls.course_applications" not in settings.INSTALLED_APPS:
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory  # now safe
```

`pytest.importorskip(...)` doesn't work here (the package *is* importable — it's the model-registry `RuntimeError` that fires); `@pytest.mark.skipif` doesn't either (the module-scope import raises before the decorator is ever reached). Belt-and-braces: colocate a `conftest.py` that sets `collect_ignore_glob` under the same condition so the offending files are never even imported — see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` for the full pattern.

## Anti-pattern cheatsheet

| Pattern | Issue | Fix |
|---|---|---|
| Test re-computes the expected value from the input | Tautology — passes by coincidence | Assert against a hard-coded known-good value |
| Test name describes the function, not the behaviour | Couples to internals; breaks on rename | Name after subject/condition/expected outcome |
| Mocks an internal helper or ORM call | Brittle; hides real bugs | Mock at system boundaries only |
| Test has no assertion (or only `status_code == 200`) | False confidence | Assert on the behaviour the code actually produces |
| Asserts the absence of an attribute/key the code never sets (`assert not hasattr(obj, "x")`) | Passes for any invented name; tests nothing; couples to removed internals | Assert the positive observable behaviour instead; delete the check during REFACTOR |
| More than 2 mocks in one test | Unit has too many dependencies | Refactor the code; don't pile on mocks |
| Test catches and swallows the exception | Hides failures | Let it propagate, or use `pytest.raises()` |
| Commented-out test | Dead test hiding a real failure | Delete it or fix it — never both |
| Multiple assertions on unrelated behaviours | "and" test; unclear failure signal | Split into separate tests |
| Patches `request.user` to skip auth | Bypasses real permission code | Use `client.force_login(user)` |
| Asserts a hardcoded value derived from live config (a settings value, a theme `.css`) | Breaks when config legitimately changes; duplicates the controlled-input tests | Test the function with explicit inputs; guard real config with a system check |

For the longer list of red flags, see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md`.
