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

For unit-level HTMX patterns (header simulation, `HX-Trigger` assertions, 422 validation responses) and general testing guidelines see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md`.

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

**(currently available)** — Playwright's `expect()` API auto-waits for conditions to become true and produces clear failure messages. Use it instead of `wait_for_selector` / `is_visible`.

```python
import pytest
from django.urls import reverse
from playwright.sync_api import expect

@pytest.mark.playwright
def test_user_enrollment_flow(page, live_server):
    """User can enroll in a course."""
    url = reverse("courses:list")
    page.goto(f"{live_server.url}{url}")

    page.get_by_role("button", name="Enroll").click()

    expect(page.get_by_text("Enrolled")).to_be_visible()
```

## Best Practices

1. **Mark with @pytest.mark.playwright** - Required for all Playwright tests
2. **Test real user behavior** - Click, type, navigate like a user
3. **Use `expect()` matchers** - `expect(locator).to_be_visible()` and similar matchers auto-wait, integrate with HTMX swaps, and produce better failure messages than `wait_for_selector` / `is_visible`.
4. **Use semantic locators** - Prefer `get_by_role` / `get_by_label` / `get_by_text` over CSS selectors. See "Locator priority" below.
5. **Test happy paths first** - Core user journeys
6. **Keep tests independent** - Each test should setup/teardown its own data
7. **Use live_server fixture** - Django test server integration
8. **Use reverse() for URLs** - Never hardcode URLs: `reverse('app:view')` not `'/app/view/'`
9. **Don't test what pytest can** - Avoid testing backend logic

## Locator priority

**(currently available)** — pick the highest-priority locator that fits. Lower-priority locators are brittle to refactors and copy edits.

1. `page.get_by_role(...)` — survives copy refactors; mirrors how assistive tech sees the page.
2. `page.get_by_label(...)` — for form fields; tied to the accessible label, so it follows the field through visual redesigns.
3. `page.get_by_text(...)` — for visible text content; readable but brittle to copy edits.
4. `page.get_by_test_id(...)` — when nothing semantic is available; requires a `data-testid` attribute on the element.
5. CSS / XPath selectors — last resort; brittle to markup refactors.

```python
# GOOD — semantic, survives refactors
page.get_by_role("button", name="Submit").click()
page.get_by_label("Email").fill("student@example.test")
page.get_by_text("Welcome back").is_visible()
page.get_by_test_id("course-card-3").click()

# BAD — couples the test to the current markup
page.click('.form > .btn-submit')
```

## HTMX Testing

```python
from playwright.sync_api import expect

# Wait for HTMX swap via expect() — auto-waits, no explicit sleep
page.get_by_role("button", name="Load more").click()
expect(page.locator("#content .new-item")).to_be_visible()

# Assert resulting count
expect(page.locator(".item")).to_have_count(5)
```

For HTMX request / response patterns at the unit-test level (header simulation, `HX-Trigger` assertions, 422 validation responses) see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (HTMX test patterns section). For production-side HTMX conventions see the `fls:htmx` skill.

## Trace on failure

**(planned for upcoming phase 2)**

Playwright traces capture screenshots, DOM snapshots, network logs, and console output for failed tests; they are invaluable for debugging flaky / environment-dependent failures. Phase 2 will land the configuration that turns this on by default.

```python
# pytest configuration — to be enabled in phase 2
# pyproject.toml [tool.pytest.ini_options]:
#   playwright_browser_args = ["--trace=retain-on-failure"]
# or via the playwright fixtures / conftest as appropriate for our setup
```

> **Caveat — traces capture DOM state and may contain fixture credentials, session cookies, or PII baked into seeded test data. Treat trace artefacts as sensitive: do not attach them to public bug reports, third-party support tickets, or shared chat channels without first reviewing them. If a trace must be shared externally, scrub or regenerate against a clean fixture set.**

## Login fixture pattern

**(currently available)** — a real browser login takes seconds; running it once per test makes the suite slow. Reuse the logged-in state instead.

Two approaches:

1. **`storage_state`** (preferred) — log in once in a session-scoped fixture, save the resulting `storage_state` JSON, reuse it across tests via `browser.new_context(storage_state=...)`. Cookies and `localStorage` are restored without re-running the login flow.
2. **Programmatic login** — call the backend login endpoint directly via `page.request.post(...)` rather than driving the form UI. Faster than UI login but slower than `storage_state` reuse, and useful when individual tests need fresh sessions.

```python
import pytest
from django.urls import reverse
from playwright.sync_api import expect


@pytest.fixture(scope="session")
def authed_storage_state(live_server, browser):
    """Log in once per session; reuse the resulting cookies + localStorage."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{live_server.url}{reverse('accounts:login')}")
    page.get_by_label("Email").fill("student@example.test")
    page.get_by_label("Password").fill("test-password-not-real")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{live_server.url}{reverse('student_interface:home')}")
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture
def authed_page(browser, authed_storage_state):
    context = browser.new_context(storage_state=authed_storage_state)
    page = context.new_page()
    yield page
    context.close()
```

**Security caveat:** do not commit the resulting `storage_state` JSON to the repo; it contains session cookies. The fixture builds it at test time from synthetic credentials; never hard-code real credentials anywhere in the fixture. All examples here use the RFC 2606 reserved `.test` TLD and obviously-synthetic placeholder passwords.

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
