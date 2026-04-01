# FLS Claude Code Plugin

FreedomLS development conventions, skills, commands, agents, hooks, and scripts packaged as a Claude Code plugin.

## What It Provides

- **Skills**: 13 development skills (testing, templates, HTMX, Alpine.js, multi-tenant, admin, etc.)
- **Commands**: 16 commands including spec-driven development workflow, code review, commits, and more
- **Agents**: Code reviewer and QA data helper with persistent memory
- **Hooks**: Automated ruff formatting, bandit security scanning, and pre-commit checks
- **Scripts**: Base developer scripts (DB management, dev setup, port finding, etc.)
- **MCP**: Playwright browser automation
- **LSP**: Python language server (Pyright) for diagnostics

## How to Enable

Run `/fls:init` in Claude Code to bootstrap the plugin for your project. This will:

1. Merge recommended permissions into `.claude/settings.json`
2. Create `.claude/fls.md` with dev credentials
3. Generate wrapper scripts at your project root
4. Validate the setup

## Structure

- `commands/` — Slash commands
- `skills/` — Development skills with context and rules
- `agents/` — Agent definitions (code reviewer, QA data helper)
- `resources/` — Reference documentation
- `hooks/` — Hook event configuration
- `scripts/` — Base shell scripts and hook scripts
- `templates/` — Templates for init command (settings, wrapper scripts)
