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
- See `@.claude/docs/factory_boy.md` for the full factory reference
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

### Qualities of a good test

1. **Focused** — tests exactly one behaviour or rule. If the test name needs "and" in it, split it.
2. **Readable** — a developer can understand what's being tested and why without reading the implementation. The test name and docstring are the spec.
3. **Resilient** — doesn't break when you refactor internals. Tests that are tightly coupled to implementation details create drag, not safety.
4. **Fast** — avoids unnecessary setup. Only create the data the test actually needs.
5. **Honest** — fails when the behaviour is broken, passes when it works. No tests that pass by coincidence.

### Red flags in tests

- A test with no meaningful assertions (or only `assert response.status_code == 200` when the view does complex work)
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
3. **REFACTOR** - Improve design (tests still pass)
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
