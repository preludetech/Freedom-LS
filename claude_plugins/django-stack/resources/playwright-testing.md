# Playwright Testing

## When to Use Playwright

Use Playwright for:
- **User flows** - Login, checkout, multi-step navigation
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

## Portability: the `playwright` marker is the browser set a downstream excludes

Every browser test is marked `@pytest.mark.playwright` and lives under `<app>/tests/playwright/`. Together these are the browser-dependent set a concrete downstream project cannot run headless-plain (no `live_server` + real browser to drive, and `pytest-socket` blocks outbound sockets by default). The marker is the only thing a downstream needs in order to exclude it — so mark every browser test, without exception.

For how the `playwright` marker sits alongside any other project-specific markers and the exact selection a downstream runs, see the `ds:testing` skill's marker guidance.

## Setup

```bash
# Install
uv add --dev playwright
playwright install

# Run tests
pytest -m playwright
pytest <app>/tests/playwright/test_comment_flow.py
```

## Test Structure

Playwright's `expect()` API auto-waits for conditions to become true and produces clear failure messages. Use it instead of `wait_for_selector` / `is_visible`.

```python
import pytest
from django.urls import reverse
from playwright.sync_api import expect

@pytest.mark.playwright
def test_user_comment_flow(page, live_server):
    """User can post a comment on an article."""
    url = reverse("articles:list")
    page.goto(f"{live_server.url}{url}")

    page.get_by_role("button", name="Post").click()

    expect(page.get_by_text("Comment posted")).to_be_visible()
```

## Best Practices

1. **Mark with @pytest.mark.playwright** - Required for all Playwright tests
2. **Test real user behavior** - Click, type, navigate like a user
3. **Use `expect()` matchers** - `expect(locator).to_be_visible()` and similar matchers auto-wait, integrate with HTMX swaps, and produce better failure messages than `wait_for_selector` / `is_visible`.
4. **Use semantic locators** - Prefer `get_by_role` / `get_by_label` / `get_by_text` over CSS selectors. See "Locator priority" below.
5. **Test happy paths first** - Core user journeys
6. **Write flows** - One journey per test: one login, one data build, many assertions, layout checks looped over the project's viewports at the end. A case that needs its own browser context or a route interception is a separate function in the same file
7. **Use live_server fixture** - Django test server integration
8. **Use reverse() for URLs** - Never hardcode URLs: `reverse('app:view')` not `'/app/view/'`
9. **Don't test what pytest can** - Avoid testing backend logic

## Locator priority

Pick the highest-priority locator that fits. Lower-priority locators are brittle to refactors and copy edits.

1. `page.get_by_role(...)` — survives copy refactors; mirrors how assistive tech sees the page.
2. `page.get_by_label(...)` — for form fields; tied to the accessible label, so it follows the field through visual redesigns.
3. `page.get_by_text(...)` — for visible text content; readable but brittle to copy edits.
4. `page.get_by_test_id(...)` — when nothing semantic is available; requires a `data-testid` attribute on the element.
5. CSS / XPath selectors — last resort; brittle to markup refactors.

```python
# GOOD — semantic, survives refactors
page.get_by_role("button", name="Submit").click()
page.get_by_label("Email").fill("user@example.test")
expect(page.get_by_text("Welcome back")).to_be_visible()
page.get_by_test_id("article-card-3").click()

# BAD — couples the test to the current markup
page.click('.form > .btn-submit')
```

## HTMX Testing

```python
from playwright.sync_api import expect

# Wait for HTMX swap via expect() — auto-waits, no explicit sleep
page.get_by_role("button", name="Load more").click()
expect(page.get_by_test_id("new-item")).to_be_visible()

# Assert resulting count
expect(page.get_by_role("listitem")).to_have_count(5)
```

For HTMX request / response patterns at the unit-test level (header simulation, `HX-Trigger` assertions, 422 validation responses) see `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` (HTMX test patterns section). For production-side HTMX conventions see the `ds:htmx` skill.

## Trace on failure

Traces are recorded on failure (`--tracing=retain-on-failure`) and written to `test-results/`. A trace holds screenshots, DOM snapshots, network logs and console output, which localises the failing step of a flow.

> **Caveat — traces capture DOM state and may contain fixture credentials, session cookies, or PII baked into seeded test data. Treat trace artefacts as sensitive: do not attach them to public bug reports, third-party support tickets, or shared chat channels without first reviewing them. If a trace must be shared externally, scrub or regenerate against a clean fixture set.**

## Login fixture pattern

Log in through the UI at the start of each flow, in a function-scoped fixture. Placeholders below stand for the project's real URL names.

```python
import pytest
from django.urls import reverse
from playwright.sync_api import expect


@pytest.fixture
def authed_page(page, live_server):
    page.goto(f"{live_server.url}{reverse('<login url name>')}")
    page.get_by_label("Email").fill("user@example.test")
    page.get_by_label("Password").fill("test-password-not-real")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{live_server.url}{reverse('<post-login url name>')}")
    return page
```

**Security caveat:** never commit session state (a `storage_state` JSON holds session cookies). Build credentials at test time from synthetic values; never hard-code real credentials. Examples here use the RFC 2606 reserved `.test` TLD and obviously synthetic passwords.

## Test Organization

```
<app>/tests/playwright/
├── conftest.py           # Playwright fixtures
├── test_comment_flow.py  # Comment-posting flow
└── test_article_nav.py   # Article navigation flow
```

## Key Differences from Pytest

- **Scope:** Browser interactions vs. backend logic
- **Speed:** Slower (use sparingly)
- **Fixtures:** `page`, `live_server` vs. `client`, `user`
- **Assertions:** Visible elements vs. data/responses

Use Playwright to complement pytest, not replace it.
