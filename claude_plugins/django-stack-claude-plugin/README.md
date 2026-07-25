# django-stack (`ds`) plugin

Portable Django-stack conventions for Claude Code. Everything here helps *any* project on this stack —
Python 3.13+, Django 6.x, PostgreSQL, HTMX, Tailwind, and optionally Cotton / Alpine / Playwright — and
carries **zero product-specific domain knowledge** and depends on no other plugin. Product-specific
conventions (multi-tenant / site-aware models, registration, markdown content, brand, etc.) belong in a
separate downstream plugin that layers thin overlay skills on top of the `ds` skills here.

Manifest name: `ds`. Namespace: `/ds:*`, `Skill(ds:*)`.

## What's inside (counted from disk)

### Skills (9)
`admin-interface`, `alpine-js`, `app-settings`, `frontend-styling`, `htmx`, `playwright-tests`,
`template`, `testing`, `use-playwright`.

### Commands (12 files)
Top level: `init`, `commit`, `app_map`, `catchup`, `make_github_issue`, `rebase_main`, `tdd_implement`,
`security-review`, `threat-model`, `placeholder_page`.
`periodic/`: `README`, `dependabot_prs`.

`/ds:init` wires up `ds` and, when they are missing, creates the generic plugin-neutral artifacts any
Claude Code project needs: a root `claude.sh` launcher (starting with the `django-stack` `--plugin-dir`
flag + `$CLAUDE_PLUGINS_LOADED`), the `SessionStart` hook, and the `.gitignore` `settings.local.json`
line. `claude.sh` is a shared file — `ds:init` only ensures its own `--plugin-dir` line and leaves any
other plugin's line untouched, so if other plugins are installed their inits add their own lines the
same way.

### Agents (1)
`code-reviewer` — a generic Python/Django/HTMX reviewer. Its persistent memory lives at the unprefixed
`.claude/agent-memory/code-reviewer/`.

### Scripts
`find_available_port.sh`, `generate_app_map.py`, `db_clear.sh`, `fetch_pr_comments.sh`,
`kill_runserver.sh`, plus the hook scripts under `scripts/hooks/` (`ruff_fix.sh`,
`post-edit-bandit.sh`, `security-guard.sh`).

### Resources (7)
`admin_interface`, `factory_boy`, `frontend_styling`, `templates_and_cotton`, `testing`,
`playwright-testing`, `agent_memory_guidelines` (a self-contained copy — duplicated here because
`${CLAUDE_PLUGIN_ROOT}` is per-plugin and `code-reviewer` reads it).

### Hooks & configs
`hooks/hooks.json` (ruff-fix + bandit on edit; a security guard on Bash/Write/Edit — any
product-specific pytest pre-commit runner is intentionally **not** here), `.mcp.json` (Playwright MCP
server), `.lsp.json` (Pyright).

### Templates
`ds:init` ships `templates/settings.json` (the generic permission baseline + the `SessionStart` hook)
and `templates/wrapper_scripts/` (`claude.sh` launcher plus `find_available_port.sh`, `db_clear.sh`,
`kill_runserver.sh`, `fetch_pr_comments.sh`).
