---
name: playwright-tests
description: Write Playwright tests for user flows and browser interactions. Use when testing HTMX, user journeys, or when the user mentions Playwright, browser testing, or E2E.
allowed-tools: Read, Grep, Glob
---

# Playwright Testing

This Skill helps write browser tests for behavior that needs a real browser.

## When to Use This Skill

- **Testing user flows**: login, checkout, multi-step processes
- **Testing HTMX interactions**: dynamic updates, partial swaps
- **Testing JavaScript behavior**: Alpine.js, modals, interactive elements
- **Integration testing across pages**: navigation, full user journeys
- **User asks for a browser test**, however they phrase it
- **Visual verification needed**: layout, responsive behavior

## Key Rules

- A browser test is a flow: one journey, one login, one data build, many assertions, with layout checks looped over the project's viewports at the end. A case that needs its own browser context or a route interception is a separate function in the same file.
- Only use Playwright for browser-required behavior. If pytest can test it, use pytest.
- Mark every browser test `@pytest.mark.playwright`, without exception: a consumer that can't run a real browser excludes exactly this set. See the Portability note in the resource file and the `ds:testing` skill's marker guidance.
- Use `page` and `live_server` fixtures.
- Use `reverse()` for URLs, never hardcode.
- Use `expect(locator).to_be_visible()` and similar `expect()` matchers for all assertions: they auto-wait and surface better failure messages than `wait_for_selector` / `is_visible`.
- Locator priority: `get_by_role` → `get_by_label` → `get_by_text` → `get_by_test_id` → CSS as a last resort.
- Test location: see the project's testing skill.

## Best practices

- Log in once per flow. See the resource file for the login pattern.
- Trace and screenshot-on-failure are captured automatically (`--tracing=retain-on-failure --screenshot=only-on-failure` in `pyproject.toml` `addopts`). Traces land in `test-results/<nodeid>/trace.zip` and CI uploads `test-results/` as the `playwright-traces` artifact on failure. Treat trace artefacts as sensitive: they may contain fixture credentials or session cookies.

## Cross-links

- For HTMX request / response patterns at the unit-test level (header simulation, `HX-Trigger` assertions, 422 validation responses) see the `ds:testing` skill.
- For production-side HTMX conventions see the `ds:htmx` skill.

Refer to `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md` for full patterns.
Refer to `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` for general testing guidelines.
