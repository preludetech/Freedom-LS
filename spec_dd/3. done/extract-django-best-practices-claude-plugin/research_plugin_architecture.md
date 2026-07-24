# Research: Claude Code Plugin Architecture

This research informs the structure of the new `django-constitution-claude-plugin`.

## Sources

- [Plugins reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference)
- [Create plugins - Claude Code Docs](https://code.claude.com/docs/en/plugins)
- [anthropics/claude-code (plugins/)](https://github.com/anthropics/claude-code/tree/main/plugins)

## Key findings

### Plugin manifest

Every plugin is a directory containing `.claude-plugin/plugin.json`:

```json
{
  "name": "dc",
  "description": "Reusable Django stack conventions for Claude Code",
  "version": "1.0.0",
  "author": { "name": "..." }
}
```

- `name` is the **namespace prefix** for slash commands and skills. A skill folder `tailwind/` in plugin `dc` becomes `/dc:tailwind`.
- The idea's intended `dc` short name maps directly onto the manifest `name` field — there is no separate "alias" concept; the plugin name *is* the namespace.
- Only `plugin.json` belongs in `.claude-plugin/`. Components (`skills/`, `commands/`, `agents/`, `hooks/`, `.mcp.json`, `.lsp.json`, `bin/`, `settings.json`) live at the **plugin root**, not nested inside `.claude-plugin/`. This is the most common mistake the docs call out.
- `version` is optional — without it the git SHA is used, and every commit counts as a new version. Setting an explicit version controls when downstream users get updates.

### Component layout

| Directory         | Purpose                                                        |
| :---------------- | :------------------------------------------------------------- |
| `.claude-plugin/` | Holds `plugin.json` only                                        |
| `skills/`         | Folders containing `SKILL.md` (model-invokable, namespaced)    |
| `commands/`       | Flat markdown files (slash commands). `skills/` is preferred for new plugins. |
| `agents/`         | Subagent markdown definitions                                   |
| `hooks/`          | `hooks.json` (same shape as `.claude/settings.json` hooks)     |
| `.mcp.json`       | MCP server configurations                                       |
| `.lsp.json`       | LSP server configurations                                       |
| `bin/`            | Executables added to PATH while plugin is enabled               |
| `settings.json`   | Default settings (only `agent` and `subagentStatusLine` keys today) |
| `monitors/`       | Background monitors                                             |

### Skill format

```
skills/
  tailwind/
    SKILL.md       # required, has YAML frontmatter
    reference.md   # optional supporting file
    scripts/       # optional supporting scripts
```

`SKILL.md` frontmatter fields used in FLS today:

- `name` (optional — defaults to folder name)
- `description` — what triggers Claude to invoke the skill
- `allowed-tools` — restrict which tools the skill may call
- `disable-model-invocation: true` — make a skill manual-only (`/plugin:skill`)

Skills can reference their own files via `${CLAUDE_PLUGIN_ROOT}` (resolved to the plugin's root directory at runtime). FLS uses this throughout (e.g. `${CLAUDE_PLUGIN_ROOT}/resources/testing.md`).

### Slash command namespacing

- Plugin slash commands and skills are **always** namespaced: `/dc:testing`, `/dc:init`. There is no way to drop the prefix.
- The prefix is the `name` field of `plugin.json`. To get `/dc:tailwind`, the manifest must be `"name": "dc"`.
- This is independent of the *directory name* on disk. The folder can be `django-constitution-claude-plugin/` (matching the idea's `directory called django-constitution-claude-plugin`) while the manifest sets `name: "dc"`.

### Init / bootstrap pattern

Claude Code does not provide a built-in plugin lifecycle hook for "first-time setup". The FLS plugin uses a convention: a `commands/init.md` slash command (`/fls:init`) that:

1. Merges template `settings.json` permissions into `.claude/settings.json`
2. Creates a project-local config file (`.claude/fls/config.md`)
3. Generates wrapper scripts at the project root and under `.claude/fls/scripts/`
4. Adds gitignore entries
5. Validates the result

This is a pure markdown command — no special Claude Code support is required. The new `dc` plugin can follow the same pattern: `/dc:init` that asks the user about project specifics (Tailwind input path, settings/test paths, factory location, whether the project uses cotton, whether HTMX is loaded globally, etc.), records them in a project-local config file the skills can read, and merges any required permissions / hooks.

### Distribution

- Local development: `claude --plugin-dir ./django-constitution-claude-plugin`
- Reload after edits: `/reload-plugins`
- Sharing: marketplace (public Anthropic marketplace, private git repo, or in-house team marketplace)
- For FLS itself: the repo can keep both `fls-claude-plugin/` and `django-constitution-claude-plugin/` side-by-side and load both, since fls-claude-plugin can depend on / cooperate with dc.

### Implications for the new plugin

- **Manifest name** must be `"dc"` to honour the idea's `/dc:tailwind` slash form. The directory can stay `django-constitution-claude-plugin/`.
- **No name collisions** with FLS: namespaces (`fls:` vs `dc:`) are independent, so the same skill name (e.g. `testing`) can exist in both. We need to pick a model: extract-into-dc-only, or extract-into-dc-and-have-fls-skills-thinly-defer-to-dc.
- **Init command** is a regular slash command — no platform constraints. Configuration the init command writes should live in the project's `.claude/dc/config.md` (mirroring FLS's `.claude/fls/config.md`).
- **`${CLAUDE_PLUGIN_ROOT}`** is the standard way to reference resources inside the plugin. Skills extracted into `dc` should use it for any cross-file references.
- **Hooks** if any (e.g. ruff format, bandit scan in FLS) live in `hooks/hooks.json` not in `settings.json`. Decide per-hook whether it's universally Django-stack-appropriate.
