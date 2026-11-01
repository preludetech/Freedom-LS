# Research: reference implementations (claude-plugin-tidy-up)

Question: how do published plugin collections package skills, and how does this repo compare?

## 1. Plugin directory layout (official)

Source: https://code.claude.com/docs/en/plugins-reference (manifest reference), https://github.com/anthropics/claude-code/tree/main/plugins (README), https://github.com/anthropics/claude-plugins-official

- Layout: `plugin-name/.claude-plugin/plugin.json` plus optional `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`, `README.md`. Everything except `plugin.json` sits at the plugin root, not inside `.claude-plugin/`.
- A skills-only plugin is `plugin.json` plus `skills/<name>/SKILL.md` (one folder per skill; extra files such as `references/` or `scripts/` live beside SKILL.md). The manifest is optional: without it Claude Code scans the standard layout and takes the name from the marketplace entry or directory.
- `commands/` is described as legacy ("Prefer `skills/` for new plugins").
- `claude-plugins-official` repo: `.claude-plugin/marketplace.json`, `plugins/` (Anthropic-maintained), `external_plugins/` (third-party). Entries carry a `category` (e.g. `productivity`, `development`).
- `anthropics/skills` (https://github.com/anthropics/skills): `skills/` grouped by theme, `spec/`, `template/`, `.claude-plugin/`. Skills are bundled as two plugins (`document-skills`, `example-skills`) in marketplace `anthropic-agent-skills`. A bundle may omit `plugin.json` and use a marketplace entry with `strict: false` and an explicit `skills: ["./skill-a", ...]` list.
- Every skill is namespaced `<plugin-name>:<skill-name>`. This is the main consequence for moving project skills into plugins: bare `answer` becomes `productivity:answer`, so every reference must be rewritten.

## 2. plugin.json fields

Only `name` is required (kebab-case; namespaces all components; must not start with `claude-`/`anthropic-` or be reserved). Optional: `displayName` (UI label, safe to change), `version` (pins users until changed; set it in one place only), `description`, `author{name,email,url}`, `homepage`, `repository`, `license`, `keywords`, `defaultEnabled`, `dependencies` (array of `"name"`, `"name@marketplace"` or `{name, marketplace, version}`), `skills` (extra dirs; adds to `skills/`), `commands`/`agents` (replace the default dir scan), `hooks`, `mcpServers`, `userConfig`, `settings`. Unknown top-level keys are stripped with a warning. `claude plugin validate <dir>` (`--strict` for CI) is the authoritative check.

Relevant for the spec: `dependencies` is the official way to express "overlay needs generic plugin". Local plugins use none (see section 5).

## 3. How a productivity/writing-style plugin is packaged

- Anthropic's own: `claude-md-management` and `code-review` are listed with `category: productivity`, both normal plugins (not renamed skill bundles). No Anthropic writing-style plugin was found in the part of marketplace.json that was read (first ~100k of 190k chars; not exhaustive).
- Community: humanizer / anti-slop skills (blader/humanizer origin, many derivatives) ship as a single skill folder (`SKILL.md` with before/after examples, and pattern lists), installed by cloning into `~/.claude/skills/` or via `npx skills add <owner>/<repo> --skill <name>`; some marketplaces vendor them as a one-skill plugin. Sources: https://claudemarketplaces.com/skills/pedronauck/skills/humanizer, https://claudemarketplaces.com/skills/richtabor/agent-skills/humanize, https://gitea.inmedias.it/inmedias.it/claude-plugins/commit/5648bd45518a779c32a5c609037d9562c832dd90. These pages were not verified at SKILL.md level; treat as pattern evidence only.
- Pattern: a small plugin of a few independent prose skills, `skills/<name>/SKILL.md` each, a `description` stating what and when, no commands/agents.

## 4. Generic vs project-specific layering

- Official docs have no "overlay" concept. Layering is by `dependencies` between plugins, plus marketplace `strict` mode (an entry can append `skills` to a plugin that has its own manifest). Marketplaces can share a skill across plugins via symlink inside the plugin dir (dereferenced at cache time; works only within the same marketplace): https://code.claude.com/docs/en/plugins/host-marketplace.md.
- This repo's own pattern is the clearest reference: `fls-dev` ships "thin overlay skills" (same skill name as the `ds` skill, e.g. `fls-dev:testing` starting "Read `Skill(ds:testing)` first ... This overlay adds only the FreedomLS specifics"), plus `resources/` addenda that extend the matching `ds` resource. Description wording to keep: "Use alongside ds:testing when ...". Generic plugins carry no FLS content (CLAUDE.md rule), project values come in through `.claude/<plugin>/config.md`.

## 5. Local plugins compared

Local plugins: `claude_plugins/{django-stack,fls-content,fls-dev,sdd,turn-progress}`.

| Aspect | Official | This repo |
|---|---|---|
| plugin.json | `name` required; version/description/author/license/etc optional | `fls-dev`, `ds`, `sdd`: only `name`, `version` ("1.0.0"), `description`. No author, license, `dependencies`. |
| name vs directory | name = identifier, entry name must match manifest | `django-stack/` dir has manifest name `ds`; `fls-dev` -> `fls-dev`. Namespace is the manifest name (`ds:testing`). |
| Marketplace | marketplace.json with `plugins`, `renames` | None. No `.claude-plugin/marketplace.json` found at repo root. Plugins are loaded by `claude.sh` with `--plugin-dir "$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/<dir>"` lines (one per plugin, each plugin's init adds its own), and enabled in `.claude/settings.json` via `"enabledPlugins": {"ds": true, "fls-dev": true, "sdd": true}`. |
| Dependencies | `dependencies` field | Prose only (README: "`fls-dev` depends on `sdd` at runtime"); enforced by `/fls-dev:init` preflight ("`/ds:init` must run first"). |
| Init | n/a | Each plugin has `commands/init.md`; `/ds:init` owns shared artifacts (`claude.sh`, SessionStart hook, `.gitignore` line), `/fls-dev:init` detects and skips them and wires only its slice (enabledPlugins key, permissions, `.claude/fls-dev/` config dir, wrapper scripts). Includes per-file migration of the legacy `.claude/fls/` dir. |
| README | per-plugin README | Each README lists counts "counted from disk" (e.g. fls-dev "Skills (13)", "Resources (15)"). These counts go stale when skills move; the spec should update READMEs of `ds`, `fls-dev`, and the new plugin. |
| Per-plugin resources | skills use `references/` inside the skill folder | Plugin-level `resources/` shared by commands and skills, read via `${CLAUDE_PLUGIN_ROOT}/resources/...`; `fls-dev/skills/icon-usage/resources/` shows skill-local resources too. Resources are duplicated across plugins where `${CLAUDE_PLUGIN_ROOT}` is per-plugin (e.g. `agent_memory_guidelines`). |
| turn-progress | mod/tool plugin | README + tsconfig, no skills; not relevant to skill moves. |

Project-level skills to move (current `.claude/skills/`, line counts of SKILL.md from a grep count): answer 24, unslop 58, writing-for-agents 48 (+ `SKILL-MECHANICS.md` 12), domain-glossary 211, notifications 76, code-comments 136, brand-guidelines 19 (+ `voice.md` 64, `visual.md` 90; stays). All are well under 500 lines.

Gotcha: `.claude/skills/writing-for-agents` has a `SKILL-MECHANICS.md` sidecar; keep it one level deep from SKILL.md when relocating. A new `productivity` plugin has no `.claude-plugin/plugin.json` yet; follow the local convention of `name`, `version`, `description` (no extras), then register in `claude.sh` (--plugin-dir line), `.claude/settings.json` `enabledPlugins`, and add a `productivity` init (or have `/ds:init` / `/fls-dev:init` handle the wiring).

## 6. SKILL.md length and reference splitting

Source: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

- Keep SKILL.md body under 500 lines; split into sibling files when approaching it.
- SKILL.md is an overview/table of contents; reference files are loaded on demand. Patterns: high-level guide with references, domain-specific `reference/<domain>.md`, conditional details.
- Keep references one level deep from SKILL.md (nested references get partially read with `head`).
- Reference files over 100 lines get a table of contents at the top.
- Name constraints: `name` max 64 chars, lowercase/digits/hyphens; `description` max 1024 chars, third person, says what and when. Gerund or noun-phrase names; avoid vague names.
- "Concise is key": assume Claude is smart; challenge each paragraph's token cost. This supports task 2 (tightening) and matches what the writing-for-agents skill already enforces. Use consistent terminology; avoid time-sensitive text; give a default, not many options.
- Local gap: `fls-dev:testing` is ~140 lines and is a thin-overlay skill with long concrete detail; fine on length but it is prose-dense. The best-practices guide suggests moving the marker-taxonomy and fixture-placement detail to a resource, which the repo already does for the addendum (`resources/testing.md`).

## 7. Renaming / moving skills

- Official: a plugin `name` is the identifier users store in `enabledPlugins`; changing it breaks installs. Use `displayName` for label changes. If unavoidable, add a top-level `renames` map in marketplace.json (`"old": "new"` or `null` when removed); Claude Code rewrites `enabledPlugins`/`pluginConfigs` keys in user, project, local scopes. Treat as append-only; `claude plugin validate .` rejects cycles. `forceRemoveDeletedPlugins` uninstalls removed plugins. Source: https://code.claude.com/docs/en/plugins/host-marketplace.md (Rename or remove a plugin). `claude-plugins-official` uses it (e.g. `vals` -> `valtown`).
- Skills have no rename mechanism. Moving a skill between plugins changes its namespace (`.claude/skills/answer` -> `productivity:answer`, `domain-glossary` -> `fls-dev:domain-glossary`, `code-comments` -> `ds:code-comments`), so all references must be updated by hand. No alias or redirect exists, and the official docs say nothing about leaving a stub. This is a repo-wide grep-and-update task: `Skill(...)`, backticked skill names, CLAUDE.md, config files, other plugins' skills/commands/resources, specs.
- Local precedent for migrations: `/fls-dev:init` migrates the legacy `.claude/fls/` dir per file (move if no counterpart, delete only byte-identical duplicates, `.legacy` copy on conflict). It is the model for any init-based migration of old project-level skills; project-level `.claude/skills/<name>` copies left alongside the plugin version would shadow or duplicate it, so the old directory should be deleted in the same change.

## 8. Findings that bear on the spec

1. Layout for new `productivity`: `claude_plugins/productivity/{.claude-plugin/plugin.json, skills/{answer,unslop,writing-for-agents}/SKILL.md, README.md}`. `plugin.json` minimal like siblings (`name`, `version`, `description`); consider `dependencies` only if it is wanted (local plugins do not use it).
2. Directory name and manifest `name` need not match (`django-stack` vs `ds`); decide the namespace explicitly because it is the skill prefix.
3. Wiring is manual, not marketplace-based: `claude.sh` `--plugin-dir` line and `enabledPlugins` key; the new plugin needs both, and any init command that writes them.
4. Overlay convention exists locally; domain skills moved into `fls-dev` should follow "Use alongside ..." descriptions and `fls-dev` README counts must be updated.
5. Tightening is consistent with the official guidance (500-line cap, concise, one-level references, TOC for 100+ line references); the 500-line cap is not violated by any moved skill, so the tightening goal is token cost, not size limits.
6. Skill moves have no official migration aid; plan a grep sweep and removal of the old `.claude/skills` entries.
7. Generic plugin rule from CLAUDE.md still applies: `productivity` and `ds:code-comments` must contain no FLS names; `domain-glossary` and `notifications` are FLS-flavoured so belong in `fls-dev`.

## Sources

- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/plugin-marketplaces
- https://code.claude.com/docs/en/plugins/host-marketplace.md
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://github.com/anthropics/claude-plugins-official
- https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json
- https://github.com/anthropics/skills
- https://github.com/anthropics/claude-code/tree/main/plugins
- https://claudemarketplaces.com/skills/pedronauck/skills/humanizer
- https://claudemarketplaces.com/skills/richtabor/agent-skills/humanize
- https://gitea.inmedias.it/inmedias.it/claude-plugins/commit/5648bd45518a779c32a5c609037d9562c832dd90
- Local: `claude_plugins/*/.claude-plugin/plugin.json`, `claude_plugins/fls-dev/README.md`, `claude_plugins/fls-dev/skills/testing/SKILL.md`, `/home/sheena/workspace/lms/freedom-ls-worktrees/claude-plugin-tidy-up/claude.sh`, `.claude/settings.json`, `.claude/skills/`

status: ok · reason: complete; limits: marketplace.json read only first 100k of 190k chars, community writing-plugin evidence is third-party directory pages, not verified at SKILL.md level
