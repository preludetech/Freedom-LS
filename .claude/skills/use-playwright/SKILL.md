---
name: use-playwright
description: Use Playwright MCP to interactively browse, inspect, and interact with the running dev site. Use when the user asks you to look at a page, check how something looks, click through a flow, fill in forms, or debug UI issues in the browser.
allowed-tools: mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_fill_form, mcp__playwright__browser_hover, mcp__playwright__browser_press_key, mcp__playwright__browser_select_option, mcp__playwright__browser_drag, mcp__playwright__browser_evaluate, mcp__playwright__browser_wait_for, mcp__playwright__browser_navigate_back, mcp__playwright__browser_tabs, mcp__playwright__browser_console_messages, mcp__playwright__browser_network_requests, mcp__playwright__browser_close, mcp__playwright__browser_resize, mcp__playwright__browser_handle_dialog, mcp__playwright__browser_file_upload, mcp__playwright__browser_run_code, mcp__playwright__browser_install
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

- **Base URL:** `http://127.0.0.1:8000`
- **Login credentials:**
  - Email: `demodev@email.com`
  - Password: `demodev@email.com`

## Key Rules

- Always start by navigating to the base URL if no page is open
- Use `browser_snapshot` (accessibility tree) for understanding page structure and finding element refs — prefer this over screenshots for interaction
- Use `browser_take_screenshot` when the user wants to see what a page looks like visually
- Use `browser_fill_form` for login and multi-field forms — it's more reliable than individual `browser_type` calls
- After clicking or submitting, use `browser_snapshot` or `browser_wait_for` to confirm the page updated
- Use `browser_console_messages` and `browser_network_requests` to debug errors
- For HTMX interactions, wait for the swap to complete before taking a snapshot

## Login Flow

1. Navigate to `http://127.0.0.1:8000/accounts/login/`
2. Fill the form with email `demodev@email.com` and password `demodev@email.com`
3. Submit the form
4. Verify login succeeded by checking the redirected page

## Tips

- `browser_snapshot` returns an accessibility tree with `ref` attributes — use these refs for `browser_click`, `browser_type`, etc.
- If an element isn't visible in the snapshot, it may be off-screen or hidden — try scrolling or checking if a modal needs to be opened
- Use `browser_wait_for` with a `text` parameter after HTMX requests to wait for content to appear
- Use `browser_evaluate` to run JavaScript when you need to inspect page state beyond what the snapshot provides
