# Playwright E2E Testing

## When to Use Playwright

Use Playwright for:
- **User flows** - Login, enrollment, course navigation
- **HTMX interactions** - Dynamic updates, partial swaps
- **JavaScript behavior** - Alpine.js interactions, modals
- **Integration across pages** - Multi-step processes
- **Visual verification** - Layout, responsive design

## When NOT to Use Playwright

Use pytest instead for:
- Model logic and methods
- View responses and context
- Template rendering
- Database operations
- Utility functions
- API endpoints

**Rule:** If it can be tested with pytest, test it with pytest. Playwright is for browser-required behavior only.

## Setup

```bash
# Install
uv add --dev playwright
playwright install

# Run tests
pytest tests/e2e/
pytest tests/e2e/test_enrollment.py
```

## Test Structure

```python
import pytest
from django.urls import reverse

@pytest.mark.playwright
def test_user_enrollment_flow(page, live_server):
    """Test user can enroll in a course."""
    # Navigate
    url = reverse('courses:list')
    page.goto(f"{live_server.url}{url}")

    # Interact
    page.click('text="Enroll"')
    page.wait_for_selector('.success-message')

    # Assert
    assert page.is_visible('text="Enrolled"')
```

## Best Practices

1. **Mark with @pytest.mark.playwright** - Required for all Playwright tests
2. **Test real user behavior** - Click, type, navigate like a user
3. **Wait for elements** - Use `wait_for_selector()` for dynamic content
4. **Use semantic selectors** - Text content over CSS classes: `'text="Enroll"'` not `'.btn-enroll'`
5. **Test happy paths first** - Core user journeys
6. **Keep tests independent** - Each test should setup/teardown its own data
7. **Use live_server fixture** - Django test server integration
8. **Use reverse() for URLs** - Never hardcode URLs: `reverse('app:view')` not `'/app/view/'`
9. **Don't test what pytest can** - Avoid testing backend logic

## Selectors

```python
# Prefer text content
page.click('text="Submit"')

# Use role when appropriate
page.click('role=button[name="Submit"]')

# Avoid brittle CSS selectors
page.click('.form > .btn-submit')  # BAD
```

## HTMX Testing

```python
# Wait for HTMX swap
page.click('button[hx-get="/more"]')
page.wait_for_selector('#content .new-item')

# Check dynamic updates
assert page.locator('.item').count() == 5
```

## Test Organization

```
tests/
└── e2e/
    ├── conftest.py          # Playwright fixtures
    ├── test_enrollment.py   # Enrollment flows
    └── test_course_nav.py   # Course navigation
```

## Key Differences from Pytest

- **Scope:** Browser interactions vs. backend logic
- **Speed:** Slower (use sparingly)
- **Fixtures:** `page`, `live_server` vs. `client`, `user`
- **Assertions:** Visible elements vs. data/responses

Use Playwright to complement pytest, not replace it.
