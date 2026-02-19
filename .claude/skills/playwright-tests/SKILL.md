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
- Prefer semantic selectors (`text="Submit"`) over CSS selectors
- Wait for elements with `wait_for_selector()` for dynamic/HTMX content
- Test location: `tests/e2e/`

Refer to @.claude/docs/playwright-testing.md for full patterns.
Refer to @.claude/docs/testing.md for general testing guidelines.
