# Claude Code Guidelines for this Project

## Package Management

- **Always use `uv` for package management**, never `pip`
  - Installing packages: `uv add <package-name>`
  - Example: `uv add pytest-mock`

## Testing

### Test Framework
- Use `pytest` for all testing
- Run tests with: `python -m pytest` or `python -m pytest -v` for verbose output

### Mocking
- **Use `pytest-mock` for mocking**, not `unittest.mock`
  - Access via the `mocker` fixture
  - Example: `mocker.patch("module.function", return_value=value)`
  - Example: `mocker.patch.object(obj, "attr", value, create=True)`

### Django Testing Best Practices
- When testing models that inherit from `SiteAwareModel`:
  - include the `mock_site_context` fixture

### DRY Principle (Don't Repeat Yourself)
- **Create fixtures for repeated test setup code**
- Example: Instead of repeating mock setup in every test, create a fixture in `conftest.py`
  ```python
  @pytest.fixture
  def mock_site_context(site, mocker):
      """Mock the thread local request and get_current_site for SiteAwareModel."""
      from system_base.models import _thread_locals
      mock_request = mocker.Mock()
      mocker.patch.object(_thread_locals, "request", mock_request, create=True)
      mocker.patch("system_base.models.get_current_site", return_value=site)
      return site
  ```

## Django Models

### SiteAwareModel Behavior
- The `save()` method checks for a request in thread locals before calling `get_current_site`
- In tests, you must mock both the thread local request AND `get_current_site`

## Code Quality

### Commit Messages
- Follow the existing style in the repository
- Use descriptive, imperative mood commit messages
- Include the Claude Code footer

## General Preferences

- Keep code DRY (Don't Repeat Yourself)
- Use clear, descriptive variable and function names
- When making changes that affect tests, update the tests to match
- Ask for clarification when the approach is unclear rather than guessing
