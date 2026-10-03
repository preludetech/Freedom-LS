# Research: making a Claude Code plugin extendable by the installing repo

Date: 2026-10-03. Sources are the current Claude Code docs plus a few community posts. The local skill `sdd:claude-code-authoring` covers only subagents, model tiering and fan-out. It has nothing on plugin extension, so everything below is web-sourced.

## 1. What the official docs say

**Skill locations and precedence**
Source: https://code.claude.com/docs/en/skills
- The locations are enterprise, personal (`~/.claude/skills`), project (`.claude/skills`), nested (`<subdir>/.claude/skills`) and plugin (`<plugin>/skills`).
- Enterprise beats personal, which beats project.
- Plugin skills are always namespaced as `plugin-name:skill-name`, so they never collide with project skills. A project skill named `widget-reference` and the plugin's `fls-content:widget-reference` both exist side by side. Neither overrides the other.
- Nested skills in a subdirectory load only when Claude works in that directory. Skills below the start directory are discovered lazily.

**Skill listing and context cost**
Source: https://code.claude.com/docs/en/skills
- Every skill contributes its name plus a truncated description to the listing, which has a budget of about 1% of the context window. When it overflows, low-use skills lose their descriptions.
- Full SKILL.md content loads only when the skill is invoked. Supporting files load only when Claude reads them.
- Skills can't directly invoke other skills. One skill can link to another's docs as plain reference text, and a `context: fork` skill can tell Claude to use another skill. `${CLAUDE_SKILL_DIR}` resolves to the skill's own directory.

**Plugin manifest and variables**
Source: https://code.claude.com/docs/en/plugins-reference
- `${CLAUDE_PLUGIN_ROOT}` is the absolute path of the installed plugin version. It changes on update, so don't write state there.
- `${CLAUDE_PLUGIN_DATA}` is `~/.claude/plugins/data/<id>/`. It survives updates and is per user, not per repo.
- `${CLAUDE_PROJECT_DIR}` is the project root. It is exported to hook processes and LSP servers only, and it is not in the Bash tool environment.
- The `${...}` variables are substituted inline in skill, command and agent Markdown bodies. They are not present in the env of commands Claude runs via Bash.
- `${user_config.KEY}` is also substituted in skill content, but only for non-sensitive values.
- The manifest `skills` field adds extra skill directories to the default `skills/`. All paths must stay inside the plugin root.
- A `CLAUDE.md` at the plugin root is not loaded as context. Instructions have to live in a skill.

**userConfig and per-project configuration**
- `userConfig` fields are `type`, `title`, `description`, `required`, `default`, `options` and `sensitive`.
- Values are stored under `pluginConfigs` in the user's settings.
  Source: https://code.claude.com/docs/en/settings-reference. This page also says `pluginConfigs` is read from user or managed scope only, not project scope.
- So `userConfig` is a per-user prompt, not a per-repo, committed config.
- Per-project control that does exist:
  - `enabledPlugins` and `extraKnownMarketplaces` can be set in the project `.claude/settings.json`.
  - A plugin-level `settings.json` only supports `agent` and `subagentStatusLine`.
- Caveat: the `pluginConfigs` scope claim comes from a WebFetch summary of the settings page. Recheck the page before relying on it.

**Per-project plugin config in practice**
- The community and Anthropic "plugin-settings" pattern is a consumer-owned file `.claude/<plugin>.local.md`. It has YAML frontmatter plus Markdown, and hooks, commands and agents read it at runtime.
  Source: https://www.skills.sh/anthropics/claude-code/plugin-settings
- It is advised to be gitignored (user-local). That is the opposite of what FLS wants, because a content repo's widget list should be committed.
- It is the same idea as `.fls-content.yaml`.

## 2. Extension patterns compared

**(a) Consumer-owned config or data in the repo**
This covers `.fls-content.yaml`, which already exists, and optionally `.fls-content/widgets/*.md`.
- Upgrade safety: best. The plugin never owns the file, and plugin updates cannot clobber it. Versioned with the content repo.
- Validator integration: best. The bundled Python validator can parse the YAML and the widget directory directly. Docs and validation can share one source, for example a widget entry with a name, attributes and a doc file path.
- Agent discoverability: only as good as the plugin skill's instructions.
  - Neither `${CLAUDE_PROJECT_DIR}` nor `${CLAUDE_PLUGIN_ROOT}` in the skill body gives the agent the repo's files. The agent works in the repo cwd anyway.
  - The skill must say something explicit such as "before using widgets, Glob `.fls-content/widgets/*.md` and read the ones relevant". Without that line, the agent will not look.
  - With it, the agent reads on demand. This is the same lazy-loading model as the plugin's own `resources/c-*.md`, so there is no extra context cost until a widget is needed.
- Pitfall: the pointer in the skill and the index must be robust. A short `index.md`, or a listing step in the skill, avoids the agent globbing and reading everything.

**(b) Consumer writes a project skill that complements the plugin skill**
`.claude/skills/<name>/SKILL.md` in the content repo.
- Upgrade safety: good. The file is consumer-owned and the plugin is untouched.
- Discoverability: depends on the project skill's own description firing.
  - The project skill appears in the listing next to the plugin skill. Claude must decide to load both.
  - Nothing links them: skills can't invoke each other, and the plugin skill can't know the project skill exists. Both only trigger by description matching, which is the weak point (see section 3).
  - A well-worded description such as "Custom FLS widgets for this repo; use whenever writing course content" works, but it is probabilistic.
- Validator integration: none by default. Docs live apart from validator data unless the skill also points at the config file.
- Costs the consumer more authoring effort (frontmatter, a description tuned for triggering).
- Namespacing means it cannot replace the plugin skill. It can only add to it.

**(c) Fork or overlay the plugin**
- Fork: the consumer owns a full copy, so extension is trivial. Upgrade safety is poor, because they must merge upstream changes. It also loses marketplace auto-update.
- Overlay (the consumer's own plugin depending on `fls-content`, or adding a second plugin):
  - Plugin `dependencies` exist in the manifest (https://code.claude.com/docs/en/plugins-reference#dependencies).
  - An overlay plugin is the consumer-owned analogue of (b), with the same linking problem: two independently triggered skills.
  - The manifest `skills` array cannot reach outside the plugin root, so an overlay cannot inject into the base plugin's directory.
  - Marketplace entries can add `skills` to a plugin with a `plugin.json` (default `strict: true`). That happens at marketplace level (https://code.claude.com/docs/en/plugins-reference, "Marketplace entries and the manifest"). It allows a consumer-owned marketplace to wrap `fls-content` plus extra skill directories, but it is heavy machinery.
- Both options carry high maintenance cost for small gains.

**(d) Plugin settings and `userConfig`**
- Its scope (user or managed only, not project) makes it a poor fit for per-repo widget lists.
- `userConfig` can hold a `directory` or `file` path, `${user_config.KEY}` is substituted into skill body text, and values come from per-user prompts.
- Verdict: unsuitable for committed per-repo extension. At most it points at a user-specific path.

**Summary**

| | Discoverability | Upgrade safety | Validator |
|---|---|---|---|
| (a) repo config/data dir | Needs an explicit instruction in the plugin skill; then reliable | Best | Best |
| (b) project skill | Probabilistic, description-triggered | Good | None unless it reads the config file |
| (c) fork/overlay | Same as (b) for an overlay; full control for a fork | Poor (fork); plugin dependencies are heavy | Fork only |
| (d) userConfig | Substituted only as text | Fine | Wrong scope (user-level) |

Combinations also work. A common one is (a) as the source of truth, with the plugin skill instructing the agent to read it. Consumers can optionally add (b) for extra guidance.

## 3. Pitfalls and evidence

**Skills not triggering**
- The listing budget is about 1% of the context window.
  - Each entry's `description` plus `when_to_use` is capped at 1,536 characters.
  - Descriptions of low-use skills are dropped when the budget overflows, and truncated descriptions lose trigger keywords.
  - A silently dropped skill never fires and shows no error.
  - Sources: https://dev.to/rulestack/too-many-claude-code-skills-how-the-listing-budget-decides-which-descriptions-claude-sees-4a6m, https://claudefa.st/blog/guide/mechanics/skill-listing-budget, https://scalably.io/blog/claude-code-skills
- Relevance for FLS: a content repo that installs a few plugins plus project skills is at risk. Adding a (b)-style skill adds one more listing entry competing for budget. Pattern (a) adds none.

**Context bloat**
- SKILL.md bodies persist in the conversation once loaded. Post-compaction re-attachment is limited to 5,000 tokens per skill and 25,000 combined, so a long SKILL.md or one that references many resources can lose content after compaction.
  Source: https://code.claude.com/docs/en/skills
- Resource files cost nothing until read. The keys are a short SKILL.md plus an index so the agent reads the one or two relevant `c-*.md` files rather than all of them.
- Consumer-added widget docs should follow the same shape as the plugin's own `c-*.md`, to keep the loading behaviour uniform.

**Drift**
- Consumer widget docs and the validator or format rules can disagree, for example docs listing an attribute the validator rejects. A single machine-readable source (the config file) read by both the validator and the agent reduces this, while prose-only project skills drift freely.
- Plugin updates change core widget docs. Consumer-owned extension files that reference the plugin's resource files by path can break, since `${CLAUDE_PLUGIN_ROOT}` changes per version and project files cannot hardcode it.

**Other facts**
- Plugin skills never fall under project-skill precedence, so name-collision "override" tricks don't work. A consumer cannot shadow `fls-content:widget-reference` with a project skill.
- Plugin updates replace the plugin root, so anything a consumer writes into the plugin directory is lost. Only consumer-owned locations, or `${CLAUDE_PLUGIN_DATA}` (per user, not per repo), persist.

## Gaps
- I found no well-known public plugin built explicitly for consumer extension beyond the `.claude/<plugin>.local.md` settings convention. I did not find evidence of a standard "extension registry" in the plugin spec.
- Whether a skill-body instruction to read a project file reliably triggers on each invocation is not documented. It is model behaviour and should be tested.

## References
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/settings-reference
- https://www.skills.sh/anthropics/claude-code/plugin-settings
- https://dev.to/rulestack/too-many-claude-code-skills-how-the-listing-budget-decides-which-descriptions-claude-sees-4a6m
- https://claudefa.st/blog/guide/mechanics/skill-listing-budget
- https://scalably.io/blog/claude-code-skills

status: ok
