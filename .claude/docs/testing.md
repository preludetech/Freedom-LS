# Testing

## Setup

- Framework: pytest (pytest-django)
- Settings: `pyproject.toml`
- Default settings: `config.settings_dev`
- Run specific test: `pytest path/to/test_file.py::test_name`

## Test Patterns

### Model Tests

```python
@pytest.mark.django_db
def test_model_method(mock_site_context):
    """Test a specific model method."""
    instance = ModelName.objects.create(field1="value")
    result = instance.some_method()
    assert result == expected_value
```

### View Tests

```python
@pytest.mark.django_db
def test_endpoint(client, user, mock_site_context):
    """Test endpoint returns expected response."""
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
        Model.objects.create(required_field=None)
```

## Best Practices

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
    instance = Model.objects.create(field="value")
    assert instance.site is not None
```

**Don't manually set site** - `mock_site_context` handles it automatically.

### Keep Tests DRY

Avoid repetition:
- Create helper functions
- Create fixtures in `conftest.py`
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
2. Follow RED → GREEN → REFACTOR → REPEAT

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
4. Don't hardcode URLs - use `reverse()`
5. Be explicit in assertions
6. Keep tests focused and DRY
