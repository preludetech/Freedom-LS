---
name: template
description: "The freedom_ls/<app>/templates/ path convention and theme shadowing by path. Use alongside ds:template when creating or editing templates in the FreedomLS repo."
allowed-tools: Read, Grep, Glob
---

# Templates (FreedomLS overlay)

Read `Skill(ds:template)` first for the cotton/HTMX/Alpine template conventions. This overlay adds **only** the path convention and theme mechanism. Full detail: `${CLAUDE_PLUGIN_ROOT}/resources/templates_and_cotton.md`.

## FLS template paths

- **Pages:** `freedom_ls/<app>/templates/<app>/<page>.html` - always extend `_base.html` (`freedom_ls/base/templates/_base.html`).
- **Cotton components:** `freedom_ls/<app>/templates/cotton/<name>.html` - use `<c-vars>` with defaults.
- **Partials:** `freedom_ls/<app>/templates/<app>/partials/<name>.html`.

Check available components with `ls freedom_ls/*/templates/cotton/`. Which component a job takes (a person link, a dialog footer, buttons in a table cell) is the table in `.claude/skills/brand-guidelines/visual.md`: invoke `Skill(brand-guidelines)` before choosing one, and `Skill(fls-dev:panel-framework)` for a panel-framework page.

## Theme shadowing by path

Themes are sparse: a theme ships only the files it overrides, and shadows a template by placing a file at the matching loader path inside its `templates/` directory. Cotton components are shadowed at `themes/<slug>/templates/cotton/<name>.html` (the `cotton/` namespace is flat); pages and partials keep their app namespace. The active theme's `templates/` dir is prepended by `configure_theme()` in `freedom_ls/base/theming.py`, so a theme file wins when it exists and otherwise falls through to the app default.
