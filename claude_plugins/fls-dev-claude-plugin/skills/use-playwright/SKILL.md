---
name: use-playwright
description: FreedomLS-specific extension of the ds:use-playwright skill. Points the base-URL and login credentials at FLS's own config file. Use alongside ds:use-playwright when browsing the FreedomLS dev site.
allowed-tools: Read
---

# Use Playwright (FreedomLS overlay)

Read `Skill(ds:use-playwright)` first for the generic Playwright MCP interaction mechanics. This overlay adds **only** the FreedomLS credentials-file path.

## Connection details

Wherever `ds:use-playwright` reads the project's dev-site config for the base URL and login credentials, FreedomLS uses `.claude/fls-dev/config.md`:

- **Connection Details** — read `.claude/fls-dev/config.md` for the base URL and login credentials before using this skill.
- **Login Flow, step 1** — navigate to the login page (use the base URL from `.claude/fls-dev/config.md`).
- **Login Flow, step 2** — fill the form with the credentials from `.claude/fls-dev/config.md`.
