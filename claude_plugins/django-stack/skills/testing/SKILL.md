---
name: testing
description: Write pytest tests for Django projects. Use when implementing features, fixing bugs, or when the user mentions testing, TDD, or pytest
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

Each pointer names a section of `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` unless stated otherwise.

- Tests mirror the app, subpackages included: `<app>/<module>.py` → `<app>/tests/test_<module>.py`. See "Mirroring".
- An app's tests import only apps the app depends on at runtime. A test that spans several apps belongs in the lowest app that depends on every app it touches. See "Test organisation and hygiene".
- `conftest.py` holds fixtures only; a helper that tests import by hand goes in a plain module beside them. See "`conftest.py` vs. plain module" and "Fixture placement".
- A foundational app proves genericity with a stub model in its own tests, never by importing a downstream app's model. See "Stub-model technique".
- Fixtures are function-scoped unless profiling justifies wider, and a wide-scoped fixture never hands back state a test mutates. See "Fixture scope and idempotent reset".
- A factory imports another app's factory only in the runtime dependency direction. See "Factory cross-app direction" in `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md`.
- Use `@pytest.mark.django_db` for database tests.
- Use factory_boy factories for all test data. Never use `.objects.create()` directly.
- Use `reverse()` for URLs, never hardcode.
- Tests that run without a browser have no conditionals or loops and test one behaviour each. Flows that need a real browser follow `ds:playwright-tests` instead.
- TDD cycle: RED (failing test) → GREEN (minimal code) → REFACTOR → REPEAT.
- Tests must pass in any order. `pytest-randomly` shuffles on every run; fix an ordering bug instead of adding `@pytest.mark.order`. See "Test order independence".
- `pytest-socket` blocks outbound sockets except `127.0.0.1` and `::1`. Mock at the boundary. See "No unexpected network sockets".
- Use `time-machine` (`time_machine.travel(...)`) for deadlines, expiry windows and scheduled jobs. See "Time-shaped code".
- pytest: before running it, read `${CLAUDE_PLUGIN_ROOT}/resources/test_tiers.md`. It holds `-n auto`, `--no-cov`, the background rule and the tier to run.

See:
- `${CLAUDE_PLUGIN_ROOT}/resources/test_tiers.md` — the tiers, their commands and how to run them
- `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` — full patterns, examples, TDD workflow, red flags
- `${CLAUDE_PLUGIN_ROOT}/resources/factory_boy.md` — factory patterns
- The `ds:playwright-tests` skill for browser tests (slow; reach for it only when a real browser is needed, marked `@pytest.mark.playwright`)
- The `ds:htmx` skill for production-side HTMX rules

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
```

If you find yourself asserting call counts on internal helpers, reading private attributes, or matching exact SQL, stop and test the output.

### Don't assert the absence of arbitrary things

A negative-existence assertion (`assert not hasattr(obj, "x")`, `assert "x" not in context`) only means something when `x` is a thing the code could *realistically* produce **and** its absence is the observable contract. Asserting the absence of a name the code was never asked to produce passes for any name you invent.

When a refactor removes an internal attribute, assert the new observable behaviour and delete any leftover absence-check during REFACTOR.

### Don't write tautological tests

A tautological test re-derives the expected value from the input using the same logic as the code under test. It passes by coincidence and catches nothing.

```python
# BAD — the test is the implementation, run twice
expected = price * (1 - rate)
assert apply_discount(price, rate) == expected

# GOOD — independent oracle; hard-coded answer for hard-coded input
assert apply_discount(100, 0.2) == 80
```

Any time the expected value is computed with arithmetic, string-building, or a loop over the input the code sees, you are writing a tautology. See "Tautology guidance" in the resource.

### Name tests after behaviour

Format: `test_<subject>_<condition>_<expected>`, for example `test_inactive_users_excluded_from_report`. If the name needs "and", split the test.

### Arrange / Act / Assert

Keep the three phases visible and in order. In a test that runs without a browser, call the code once; a second call is a second test.

### Mock only at system boundaries

Boundaries are network, external APIs, filesystem, clock, randomness and subprocess. Do not mock code you own: internal helpers, ORM calls, your own service classes. A test that needs more than two mocks means the unit has too many dependencies, so refactor it.

### Parametrize for inputs, separate tests for behaviours

Use `@pytest.mark.parametrize` when the assertion shape is identical and only the input varies. A per-instance copy of one generic check (the same test repeated for each model, view or field) is one parametrised test. Use separate tests when the paths differ: success vs. raises, happy path vs. permission denied, create vs. update.

### Test validation both ways

For validation the project wrote, test that invalid input is **rejected**, not only that valid input is accepted. A validator that accepts everything passes a happy-path test silently. Validation Django or a library already provides is not yours to test.

### Test hygiene

- In tests that run without a browser, no `if`, `for` or `try` in the body.
- No shared mutable state between tests. Use factories or fixtures.
- Delete flaky tests, or fix the flakiness.
- Keep tests fast. A unit test taking >100ms is probably hitting real I/O.
- Coverage is a signal, not a goal. High coverage with weak assertions is worse than moderate coverage with strong ones.
- Don't assert on styling (CSS classes, colours, font sizes). Assert the contract attributes instead: `aria-*`, `role`, `href`, `hx-*`, `data-*`.
- Don't assert hardcoded config values (`assert settings.TIMEOUT == 30`). A string in a shipped CSS or JS file is the same ban. Feeding live configuration through the code and asserting a derived result against a hardcoded expected is the subtler variant. See "Decoupling tests from ambient config".
- Don't assert a long copy literal. Assert a stable hook (`data-testid`, `role`, a URL), unless the copy is the feature.
- Don't write a render-only admin test. Test permissions, validation and read-only behaviour instead.
- An N+1 guard asserts an upper bound on queries (`django_assert_max_num_queries`), never an exact count.
- Tests of developer tooling (QA seeders, dev scripts) stay out of the default run under the project's own marker. See "Markers".

### Testing HTMX views

Pass `HTTP_HX_REQUEST="true"` to the test client for the partial-response branch, assert `HX-Trigger` headers when the view emits client-side events, and expect HTTP `422` on validation errors. See "HTMX test patterns".

### Auth in tests

Use `client.force_login(user)`. Patching `request.user` bypasses the real permission decorators and produces tests that pass while production breaks. See "Auth-bypass anti-pattern".

### Collection safety for optional apps

A module that imports an optional app's factory or model at module scope aborts the whole session at collection time when a downstream hasn't installed that app. Guard the import with `pytest.skip(..., allow_module_level=True)` under `apps.is_installed(...)`. See "Collection safety for optional apps" for the guard and the `collect_ignore_glob` conftest.

## Anti-pattern cheatsheet

| Pattern | Issue | Fix |
|---|---|---|
| Test re-computes the expected value from the input | Tautology | Assert against a hard-coded known-good value |
| Mocks an internal helper or ORM call | Hides real bugs | Mock at system boundaries only |
| No assertion, or only `status_code == 200` | False confidence | Assert on the behaviour the code produces |
| Asserts the absence of an attribute the code never sets | Passes for any invented name | Assert the positive behaviour |
| Test catches and swallows the exception | Hides failures | Let it propagate, or use `pytest.raises()` |
| Asserts a hardcoded value derived from live config | Breaks when config changes | Explicit inputs; a system check for real config |
| Test imports an app its own app does not depend on | Hides a real dependency | Move to the lowest app that depends on everything it touches |
| Session-scoped fixture returns rows a test mutates | Order-dependent failures | Reset the mutable part per test |

For the longer list of red flags, see "Red flags in tests" in the resource.
