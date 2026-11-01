---
name: use-playwright
description: FreedomLS-specific extension of the ds:use-playwright skill. Points the base-URL and login credentials at `## QA Login` in the sdd config. Use alongside ds:use-playwright when browsing the FreedomLS dev site.
allowed-tools: Read
---

# Use Playwright (FreedomLS overlay)

Read `Skill(ds:use-playwright)` first for the generic Playwright MCP interaction mechanics. This overlay adds **only** the FreedomLS login-config location.

## Connection details

Wherever `ds:use-playwright` reads the project's dev-site config for the base URL and login credentials, FreedomLS uses `## QA Login` in `.claude/sdd/config.md` (`config.local.md` wins):

- **Connection Details** — read `## QA Login` (above) for the base URL and login credentials before using this skill.
- **Login Flow, step 1** — navigate to the login page (use the base URL from `## QA Login`).
- **Login Flow, step 2** — fill the form with the credentials from `## QA Login`.
