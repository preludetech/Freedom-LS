---
name: playwright-tests
description: Write Playwright E2E tests for user flows and browser interactions. Use when testing HTMX, user journeys, or when the user mentions E2E, Playwright, or browser testing.
allowed-tools: Read, Grep, Glob
---

# Playwright E2E Testing

This Skill helps write end-to-end tests for browser-required behavior.

## When to Use This Skill

Use this Skill when:
- **Testing user flows** - Login, enrollment, multi-step processes
- **Testing HTMX interactions** - Dynamic updates, partial swaps
- **Testing JavaScript behavior** - Alpine.js, modals, interactive elements
- **Integration testing across pages** - Navigation, full user journeys
- **User mentions "E2E", "Playwright", "browser testing", "end-to-end"**
- **Visual verification needed** - Layout, responsive behavior

## Key Rules

- Only use Playwright for browser-required behavior — if it can be tested with pytest, use pytest instead
- Mark all tests with `@pytest.mark.playwright`
- Use `page` and `live_server` fixtures
- Use `reverse()` for URLs, never hardcode
- Use `expect(locator).to_be_visible()` and similar `expect()` matchers — they auto-wait and surface better failure messages than `wait_for_selector` / `is_visible`.
- Locator priority: `get_by_role` → `get_by_label` → `get_by_text` → `get_by_test_id` → CSS as a last resort.
- Test location: `tests/e2e/`

## Best practices

- The `expect()` API is **(currently available)** — use it for all auto-waiting assertions instead of `wait_for_selector` / `is_visible`.
- Reuse a session-scoped login fixture (`storage_state`) so most tests skip the login flow. See the resource file for the full pattern.
- Trace-on-failure config is **(planned for upcoming phase 2)** — once enabled, traces capture DOM, network, and console output for failed tests. Treat trace artefacts as sensitive (they may contain fixture credentials or session cookies).

## Cross-links

- For HTMX request / response patterns at the unit-test level (header simulation, `HX-Trigger` assertions, 422 validation responses) see the `fls:testing` skill.
- For production-side HTMX conventions see the `fls:htmx` skill.

Refer to `${CLAUDE_PLUGIN_ROOT}/resources/playwright-testing.md` for full patterns.
Refer to `${CLAUDE_PLUGIN_ROOT}/resources/testing.md` for general testing guidelines.
