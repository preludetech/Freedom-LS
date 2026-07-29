---
name: use-playwright
description: Use Playwright MCP to interactively browse, inspect, and interact with the running dev site. Use when the user asks you to look at a page, check how something looks, click through a flow, fill in forms, or debug UI issues in the browser.
---

# Use Playwright MCP

This skill uses the Playwright MCP server to interactively browse and interact with the running development site.

## When to Use This Skill

Use this skill when:
- **Visually inspecting pages** — check how a page looks, verify layout and content
- **Debugging UI issues** — inspect what's rendered, check for missing elements
- **Interacting with the site** — click buttons, fill forms, navigate between pages
- **Verifying HTMX behavior** — trigger dynamic updates and confirm results
- **Checking network requests or console errors** — diagnose frontend issues

## Connection Details

Read the project's dev-site config file (`.claude/ds/config.md` by default) before using this skill.
If `.claude/ds/config.local.md` exists it carries machine-specific overrides and takes precedence.

| Value | Section → key |
|---|---|
| Base URL | `## Project Settings` → `Dev base URL` |
| Login email | `## Dev Credentials` → `Admin email` |
| Login password | `## Dev Credentials` → `Admin password` |

The credential keys ship **blank** — `ds` carries no product knowledge, so it cannot invent a login.
A blank value means "this dev site needs no login, or the user has not recorded one": proceed without
signing in, and ask the user only if you hit a login wall.

## Tool names

`ds` ships the Playwright MCP server in its own `.mcp.json`, so its tools are exposed under the
plugin-namespaced prefix `mcp__plugin_ds_playwright__*` (e.g.
`mcp__plugin_ds_playwright__browser_snapshot`). A project that *also* declares a `playwright` server in
its own root `.mcp.json` starts the server twice and gets the same tools again under the plain
`mcp__playwright__*` prefix — drop the root declaration and rely on the one `ds` ships. The tool names
in this file are written without a prefix, so use whichever prefix is present in your available tools.

## Key Rules

- Always start by navigating to the base URL if no page is open
- Use `browser_snapshot` (accessibility tree) for understanding page structure and finding element refs — prefer this over screenshots for interaction
- Use `browser_take_screenshot` when the user wants to see what a page looks like visually
- Use `browser_fill_form` for login and multi-field forms — it's more reliable than individual `browser_type` calls
- After clicking or submitting, use `browser_snapshot` or `browser_wait_for` to confirm the page updated
- Use `browser_console_messages` and `browser_network_requests` to debug errors
- For HTMX interactions, wait for the swap to complete before taking a snapshot

## Login Flow

1. Navigate to the login page (use the base URL from the dev-site config file)
2. Fill the form with the credentials from the dev-site config file
3. Submit the form
4. Verify login succeeded by checking the redirected page

## Tips

- `browser_snapshot` returns an accessibility tree with `ref` attributes — use these refs for `browser_click`, `browser_type`, etc.
- If an element isn't visible in the snapshot, it may be off-screen or hidden — try scrolling or checking if a modal needs to be opened
- Use `browser_wait_for` with a `text` parameter after HTMX requests to wait for content to appear
- Use `browser_evaluate` to run JavaScript when you need to inspect page state beyond what the snapshot provides
