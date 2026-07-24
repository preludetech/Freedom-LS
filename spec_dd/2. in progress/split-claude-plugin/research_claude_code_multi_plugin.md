# Research: Multi-plugin support in Claude Code, and what a plugin split must respect

Scope: how Claude Code discovers/enables more than one plugin at once, how components in one
plugin reference components in another, how names/prefixes are derived from `plugin.json`'s
`name` field, and the concrete gotchas for splitting `fls-claude-plugin/` into
`claude_plugins/{django-stack,fls,sdd}` (or however many of the three land).

Grounded in this repo's actual files (read directly) plus the official Claude Code docs (fetched
live, cited inline). Target: Claude Code 2.1.x, per the repo's own
`fls-claude-plugin/skills/claude-code-authoring/SKILL.md`.

---

## 0. How this repo is wired *today* (ground truth before proposing changes)

- **One plugin is actually loaded in this repo's own sessions**: `fls-claude-plugin/`
  (`.claude-plugin/plugin.json` → `"name": "fls"`). It is loaded via the CLI flag
  `--plugin-dir`, not a marketplace:
  - `claude.sh` (repo root): `FLS_PLUGIN=1 claude --plugin-dir "$SCRIPT_DIR/fls-claude-plugin" "$@"`
  - The generated wrapper template (`fls-claude-plugin/templates/wrapper_scripts/claude.sh`) does
    the same for downstream/concrete projects, with `FLS_PATH` substituted.
  - `.claude/settings.json` additionally has `"enabledPlugins": {"fls": true}` (bare key, no
    `@marketplace` suffix) and a `SessionStart` hook that hard-fails (`"continue": false`) if
    `$FLS_PLUGIN` isn't set — i.e. **the real gate is the wrapper script + hook, not
    `enabledPlugins`.** Per the official docs, `--plugin-dir` plugins are session-scoped, have "no
    installed record" and are not part of the `/plugin` install/enable state machine at all — they
    load simply because the flag was passed. The bare `"fls": true` entry is therefore most likely
    inert for a `--plugin-dir`-loaded plugin; it reads as leftover/defensive bookkeeping rather
    than an active gate. This has no bearing on whether the split works, but it means **the plugin
    count/paths that matter today are entirely determined by `claude.sh`'s `--plugin-dir`
    argument(s)**, not by `.claude/settings.json`.
- **A second plugin exists in the repo but is not loaded here**: `fls-content-plugin/`
  (`"name": "fls-content"`) is authored in this monorepo but is meant for *external* content-author
  repos, distributed later via a marketplace (see `spec_dd/1. next/content-plugin-distribution/idea.md`).
  It has no entry in `.claude/settings.json` and is not passed to `--plugin-dir` anywhere in this
  repo. It's useful precedent (a second, independently-named, independently-versioned plugin
  living beside `fls-claude-plugin/`), but it is *not* proof that this repo's own session already
  runs two plugins concurrently — today it only ever runs one.
- Component inventory of the one active plugin, for reference: `commands/`, `agents/`, `skills/`,
  `hooks/hooks.json`, `.mcp.json` (playwright), `.lsp.json` (pyright), all at
  `fls-claude-plugin/` root, manifest only in `.claude-plugin/plugin.json` — the standard layout.

---

## 1. Marketplace & discovery

### Is there a `marketplace.json` today?

**No.** Neither `fls-claude-plugin/` nor `fls-content-plugin/` has a
`.claude-plugin/marketplace.json` anywhere in this repo today. Both plugins are discovered by two
different *non-marketplace* mechanisms:

- `fls-claude-plugin` → `--plugin-dir` (session-scoped CLI flag), as above.
- `fls-content-plugin` → not loaded in this repo at all; its distribution plan (still "next", not
  built) is a **separate** marketplace repo/catalog that content-author repos add with
  `/plugin marketplace add` ([content-plugin-distribution/idea.md](../../1.%20next/content-plugin-distribution/idea.md)).

A marketplace is not required to run multiple local plugins in one repo — `--plugin-dir` alone is
sufficient and is simpler for a monorepo that only needs to enable its own plugins for its own
contributors.

### How `--plugin-dir` scales to multiple plugins

Official CLI reference, quoted verbatim:

> `--plugin-dir` — Load a plugin from a directory or `.zip` archive for this session only. **Each
> flag takes one path. Repeat the flag for multiple plugins:** `--plugin-dir A --plugin-dir B.zip`

And from the plugin-authoring guide: *"You can load multiple plugins at once by specifying the
flag multiple times: `claude --plugin-dir ./plugin-one --plugin-dir ./plugin-two`."*
(https://code.claude.com/docs/en/plugins, https://code.claude.com/docs/en/cli-reference)

So for this repo, splitting into up to three plugins under `claude_plugins/` means `claude.sh`
(and the generated wrapper template) becomes:

```bash
claude --plugin-dir "$SCRIPT_DIR/claude_plugins/django-stack-claude-plugin" \
       --plugin-dir "$SCRIPT_DIR/claude_plugins/fls-claude-plugin" \
       --plugin-dir "$SCRIPT_DIR/claude_plugins/sdd-claude-plugin" \
       "$@"
```

(exact directory names TBD by the plan — see idea.md's `claude_plugins/` requirement.) This is a
**required change**: today's `claude.sh` only passes one `--plugin-dir`. Every plugin the split
produces needs its own `--plugin-dir` entry, or it silently isn't loaded and every cross-plugin
`Skill(...)`/`subagent_type: "...":...` reference in another plugin will fail to resolve (see §2).

`--plugin-dir` is **additive**, not exclusive — it loads the named plugin(s) in addition to
anything already installed/enabled via marketplaces, and (per the plugin guide) *"When a
`--plugin-dir` plugin has the same name as an installed marketplace plugin, the local copy takes
precedence for that session"* — irrelevant here since nothing is marketplace-installed today, but
worth knowing if the project later also adds a marketplace for `fls-content-plugin`.

### What `enabledPlugins` entries actually key on

From the plugin manifest reference: *"`name` ... Unique identifier... When a marketplace entry
lists the plugin under a different name, the marketplace entry name is what `enabledPlugins` keys
and `/plugin` use."* For **marketplace-installed** plugins, `enabledPlugins` keys are
`plugin-name@marketplace-name` (e.g. `{"code-formatter@company-tools": true}` in the docs'
"Require marketplaces for your team" example). For plugins loaded by `--plugin-dir`, there is no
evidence in the docs that `enabledPlugins` gates them at all — they're not part of that install
model. This repo's existing bare `"fls": true"` key is consistent with that: it does nothing
functional for a `--plugin-dir` plugin (the effective gate is the wrapper script/hook), and it's
reasonable to expect the split to keep or extend this same harmless bookkeeping key (e.g. add
`"django-stack": true`, `"sdd": true`) purely for documentation/consistency, not because Claude
Code requires it.
(https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema,
https://code.claude.com/docs/en/discover-plugins#configure-team-marketplaces)

### What must change for plugins under `claude_plugins/` to be discovered

1. **`claude.sh` (repo root) and the generated template
   `fls-claude-plugin/templates/wrapper_scripts/claude.sh`** must pass one `--plugin-dir` per new
   plugin directory, pointed at `claude_plugins/<new-plugin-dir>/` instead of the current single
   `fls-claude-plugin/` path. This is the load-bearing change — everything else about "discovery"
   in this repo flows from this flag.
2. **`fls-claude-plugin/commands/init.md`** (the `/fls:init` bootstrap command) hardcodes the
   plugin path assumption in several places: Step 5 validates `"<fls_path>/fls-claude-plugin/"
   exists"`, and the wrapper-script template substitution (`__FLS_PATH__`) assumes a single plugin
   directory sibling to the project root. If `fls-claude-plugin` moves to
   `claude_plugins/fls-claude-plugin/`, every literal path in `init.md` (and in
   `commands/sdd/*.md`, which resolve helper files like
   `fls-claude-plugin/commands/sdd/protected/update_todo.md` by literal relative path — see §2)
   needs the `claude_plugins/` prefix added. This is a **large mechanical find-and-replace** across
   the whole plugin, not just a config change.
3. **`.claude/settings.json`** — no functional discovery change required (per above), but for
   consistency/documentation the `enabledPlugins` block should probably gain one key per new
   plugin name (`django-stack`, `fls`, `sdd`), and the `mcp__plugin_fls_playwright__*` permission
   allow-list entry must be renamed if the MCP server moves to a different plugin (see §3).
4. **No `marketplace.json` is required** for this split to work inside this repo — only if/when
   `django-stack` or `sdd` are meant to be *installed into unrelated Django projects* (the idea's
   explicit goal for `django-stack`) does a marketplace (or at minimum, each downstream project's
   own `--plugin-dir`/`claude.sh` wiring) become relevant. That's a distribution question, not a
   same-repo-multi-plugin question — see §4 for the caveat this creates.

---

## 2. Cross-plugin references

### Can plugin A invoke a skill/agent/command that lives in plugin B?

**Yes, unconditionally, as long as both plugins are loaded in the same session.** Claude Code does
not scope the `Skill` tool or `Agent` tool to "only this plugin's own components" — any
namespaced skill or agent from any currently-loaded plugin (or the user's personal/project
skills) is invocable by name, including from within another plugin's command/skill/agent content.
Nothing in the plugin schema or the sub-agents docs restricts lookup to same-plugin components;
namespacing exists purely to **prevent name collisions**, not to sandbox plugins from each other.
(https://code.claude.com/docs/en/plugins-reference, https://code.claude.com/docs/en/sub-agents)

The corollary is the actual risk: **if plugin B isn't loaded in the session, plugin A's reference
to `pluginB:thing` simply fails to resolve** — there's no compile-time link checking across
plugin boundaries. This is why `claude.sh` must load every split plugin together (§1) — the
existing `fls-claude-plugin/commands/sdd/*.md` files are full of exactly this kind of reference
today (52+ occurrences of `subagent_type: "fls:sdd-worker"` / `"fls:sdd-mechanic"`, plus
`Skill(fls:*)` in `.claude/settings.json`'s permission allow-list, plus literal file-path
references to `fls-claude-plugin/commands/sdd/protected/update_todo.md` from six different
command files) — and every one of these must still resolve after the split.

### Namespacing mechanics observed/confirmed

- **Skills**: `plugin-name:skill-name` (folder name or frontmatter `name`, namespaced by the
  plugin). E.g. `Skill(fls:testing)`. Confirmed both in this repo's own
  `.claude/settings.json` allow-list (`"Skill(fls:*)"`) and in the official skills doc's naming
  table: *"Plugin `skills/` subdirectory → Frontmatter `name` or the directory name, namespaced by
  plugin → `my-plugin/skills/review/SKILL.md` → `/my-plugin:review`."*
- **Agents**: same pattern — *"Agents appear in the @-mention typeahead under their scoped name,
  such as `my-plugin:code-reviewer`, once the plugin is enabled"* — confirmed by this repo's
  `subagent_type: "fls:sdd-worker"` usage throughout `commands/sdd/*.md`.
- **Slash commands**: *"Skills are prefixed with this (e.g., `/my-first-plugin:hello`)"* — and
  namespacing is **mandatory and unavoidable** for plugin commands (only standalone
  `.claude/commands/` files get unprefixed names like `/hello`).
- **MCP tools**: `mcp__plugin_<plugin-name>_<server-name>__<tool-name>` — confirmed by this
  repo's own permission entry `"mcp__plugin_fls_playwright__*"` in `.claude/settings.json`,
  matching plugin name `fls` + server key `playwright` from `fls-claude-plugin/.mcp.json`.
- **Hook/mcp_tool matchers**: hooks that target the plugin's *own* bundled MCP server must use the
  scoped name too — *"Tool matchers and `if` fields take the scoped tool name
  `mcp__plugin_<plugin-name>_<server-name>__<tool>`, and an `mcp_tool` hook's `server` field takes
  `plugin:<plugin-name>:<server-name>`. A matcher written against the bare server key never
  fires."* Not currently used in this repo's `hooks.json` (which only has `command`-type hooks),
  but relevant if a future hook needs to gate a playwright/MCP tool call.

### An important nuance the docs are silent on: nested `commands/` subdirectories

This repo's `fls-claude-plugin/commands/sdd/*.md` live in a **subdirectory** of `commands/`
(`commands/sdd/start.md`, `commands/sdd/next.md`, etc.), and the plugin's own docs refer to them
informally as `/sdd:start`, `/sdd:next` (i.e. as if `sdd` were an extra namespace segment before
the filename). The official docs' explicit naming table only documents:
- flat `.claude/commands/deploy.md` → `/deploy` (no subdirectory segment), and
- nested **`skills/`** directories (`.claude/skills/`, or plugin `skills/<name>/SKILL.md`) getting
  directory-qualified names.

There is **no documented row for a plugin's `commands/<subdir>/file.md`**. Given the "commands are
flat markdown files" framing throughout the reference docs (*"Commands: Skills as flat Markdown
files. Use `skills/` for new plugins"*), a `commands/sdd/` subdirectory is a **legacy pattern
already in this repo** that the docs don't explicitly bless with subdirectory namespacing — its
actual current invocation semantics (does `/fls:sdd:start` work as a true harness-invoked slash
command, or is `sdd/` cosmetic and it's really `/fls:start`, colliding with any other `start.md`?)
should be verified empirically before relying on it further. **Regardless, this matters directly
for the split**: this repo's SDD workflow is deliberately designed so that only `/sdd:start` and
`/sdd:next` are ever *actually invoked* as slash commands — every other `commands/sdd/*.md` file
(e.g. `spec_from_idea.md`, `plan_from_spec.md`) is **read-and-followed inline by `/sdd:next`**,
never invoked as `/pluginname:sdd:whatever` (see `commands/sdd/next.md` Step 3, which resolves the
target file by literal path search, not by typing a slash command). So the split's biggest
"namespace" risk here isn't command-invocation syntax breaking — it's the **literal path search**
`next.md` performs (§2 continued below), and the double-segment problem if `sdd` becomes its own
plugin *and* keeps a `commands/sdd/` subdirectory (see §3/§4).

### Literal path references (not just namespaced skill/agent names)

Several SDD commands do **not** use Claude Code's namespacing at all — they reference sibling
command files by **literal relative file path**, then `Read` and follow them inline (per the
"subagents/commands can't invoke slash commands, so read-and-follow" pattern documented in this
repo's own `claude-code-authoring` skill). Concretely:

- `commands/sdd/next.md` Step 3 builds `candidates = ["fls-claude-plugin/commands/sdd/{name}.md",
  "fls-claude-plugin/commands/{name}.md"]` — a **hardcoded plugin directory name in a path
  string**, not a namespace reference.
- `commands/sdd/*.md` (6 files) invoke the mechanic via: *"Read the helper file at
  `fls-claude-plugin/commands/sdd/protected/update_todo.md` and follow its steps..."* — again a
  literal path baked into the prompt text, handed to a **spawned agent** (`fls:sdd-mechanic`) whose
  `Read` tool must be able to resolve that exact path from the project root.

These are **not** governed by Claude Code's plugin-namespacing rules at all — they're plain
strings in markdown files, resolved by whatever `cwd` the reading tool call happens to run from
(the project root, since these are absolute-from-repo-root paths). **Every one of these literal
paths must be rewritten** to include the new `claude_plugins/` prefix (and the plugin's possibly
new directory name, e.g. `sdd-claude-plugin/` if the SDD commands move out) as part of the split —
this is unrelated to `${CLAUDE_PLUGIN_ROOT}` and won't be fixed by using that variable, because
these are cross-file references *between command files*, not "a file referencing its own plugin's
resources" (see next section for why `${CLAUDE_PLUGIN_ROOT}` doesn't help here).

### `${CLAUDE_PLUGIN_ROOT}` — per-plugin, and what breaks if plugin A hardcodes a path into plugin B

`${CLAUDE_PLUGIN_ROOT}` resolves to **"Absolute path to the plugin's installation directory"** —
i.e. it is always the root of the plugin whose file is currently executing/being read, never
another plugin's root. It is substituted in skill/agent content, hook and monitor commands, MCP
`stdio`/`http`/`sse`/`ws` server fields, and LSP server fields.
(https://code.claude.com/docs/en/plugins-reference#environment-variables)

Consequences for the split:
1. **A hook, MCP server, or LSP server declared in plugin A can never use `${CLAUDE_PLUGIN_ROOT}`
   to reach a script/binary that lives in plugin B.** If `django-stack`'s `hooks.json` needs
   `ruff_fix.sh`, that script must physically live inside `django-stack`'s own directory tree
   (e.g. `claude_plugins/django-stack-claude-plugin/scripts/hooks/ruff_fix.sh`), not be referenced
   via a relative `../` path into `fls-claude-plugin/` or `sdd-claude-plugin/`. This repo's four
   hooks (`ruff_fix.sh`, `post-edit-bandit.sh`, security-guard.sh`, the `git commit` test runner)
   are currently all colocated under one plugin's `scripts/hooks/`; the split (per
   `extract-django-best-practices-claude-plugin/idea.md`'s already-made decision) moves three of
   the four to `django-stack` and each script must be **physically copied**, not referenced, into
   that plugin.
2. **This also governs marketplace-distributed plugins, more strictly**: *"Installed plugins
   cannot reference files outside their directory. Paths that traverse outside the plugin root
   (such as `../shared-utils`) will not work after installation because those external files are
   not copied to the cache."* Even for same-repo development via `--plugin-dir` (which does *not*
   copy to a cache — see §4), any plan to eventually publish `django-stack` to a marketplace for
   use in unrelated Django projects must assume **zero cross-plugin file paths**, `${CLAUDE_PLUGIN_ROOT}`
   or otherwise, will survive packaging.
   (https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution)
3. **The one sanctioned escape hatch is symlinks *within the same marketplace*** — *"If your
   plugin needs to share files with other parts of the same marketplace, you can create symbolic
   links... Elsewhere within the same marketplace: the symlink is dereferenced. The target's
   content is copied into the cache in its place."* This only applies once plugins are marketplace
   entries sharing one `marketplace.json`; it doesn't apply to `--plugin-dir` development, and
   symlinks that resolve outside the marketplace are skipped entirely for security.
   (https://code.claude.com/docs/en/plugins-reference#share-files-within-a-marketplace-with-symlinks)

### Does extracting `sdd` into its own plugin break `fls:sdd-worker` / `fls:qa-data-helper` references?

**Yes — that's the whole point of the namespace, and it's exactly why every occurrence must be
mechanically updated, not left alone.** If the `sdd-mechanic`/`sdd-worker` agents move out of
`fls-claude-plugin/agents/` into a new `sdd` plugin's `agents/`, their invocable name changes from
`fls:sdd-worker` / `fls:sdd-mechanic` to `sdd:sdd-worker` / `sdd:sdd-mechanic` (namespace tracks
the **declaring plugin's** `name` field, not the historical name). Every `subagent_type: "fls:sdd-*"`
string across the ~17 files that reference it (`commands/sdd/*.md`, `README.md`,
`skills/claude-code-authoring/*.md`) must be updated to the new prefix. The reverse case —
`fls:qa-data-helper`, which the idea/todo suggests should probably **stay** in the `fls` plugin
(it's about FLS's own test-data model, not a portable SDD concept) — keeps its `fls:` prefix
unchanged, but any `sdd`-plugin command that references it (`do_qa.md` mentions it) becomes a
**cross-plugin reference from `sdd` into `fls`**, which is legal (§2, first paragraph) but only
works if both plugins are loaded together — reinforcing that `sdd` cannot be a fully
freestanding/portable plugin if it keeps calling back into `fls`-specific agents. This is a
concrete design fork the plan phase needs to resolve: either (a) `qa-data-helper` becomes
FLS-generic enough to move to `sdd` or `django-stack`, or (b) the `do_qa` SDD step's reference to
it is guarded/optional so the `sdd` plugin doesn't *hard-depend* on `fls` being present.

---

## 3. Naming & prefix impact — every kind of name derived from `plugin.json`'s `name`

Enumerated, with before/after for the concrete split (`fls` → possibly `django-stack`, `fls`,
`sdd`):

| Kind of name | Rule | Before (today) | After split (example) |
|---|---|---|---|
| Skill invocation | `Skill(<plugin-name>:<skill-or-dir-name>)` | `Skill(fls:testing)` | `Skill(django-stack:testing)` if `testing` moves; unchanged `Skill(fls:multi-tenant)` if it stays |
| Slash command | `/<plugin-name>:<file-name>` (flat `commands/`); subdirectory nesting is *not* explicitly documented (see §2) | `/fls:init` | `/fls:init` unchanged (init stays FLS-specific per idea.md); a new `/django-stack:init` would be created fresh, not renamed |
| Subagent type | `subagent_type: "<plugin-name>:<agent-name>"`, and `@-mention` typeahead shows the same scoped name | `fls:sdd-worker`, `fls:sdd-mechanic`, `fls:qa-data-helper`, `fls:code-reviewer` | `sdd:sdd-worker`, `sdd:sdd-mechanic` if SDD extracted; `fls:qa-data-helper`, `fls:code-reviewer` likely stay `fls:` |
| MCP tool | `mcp__plugin_<plugin-name>_<server-name>__<tool>` | `mcp__plugin_fls_playwright__*` | `mcp__plugin_django-stack_playwright__*` if `.mcp.json`'s `playwright` server moves to `django-stack` (playwright/e2e conventions are listed as portable in the extract-idea's skill list) |
| `mcp_tool` hook `server` field | `plugin:<plugin-name>:<server-name>` | n/a (not currently used) | would follow the same rename if a hook is added later |
| Plugin data dir | `${CLAUDE_PLUGIN_DATA}` → `~/.claude/plugins/data/{id}/`, where `{id}` derives from `name@marketplace` (or bare name for non-marketplace) | n/a (not used today) | would need a fresh id per new plugin if adopted |
| `enabledPlugins` key (marketplace) | `<plugin-name>@<marketplace-name>` | n/a — no marketplace | only relevant if/when `django-stack`/`sdd` are marketplace-distributed |
| `enabledPlugins` key (bare, `--plugin-dir`/local) | bare `<plugin-name>` (functionally inert per §1, but documented) | `{"fls": true}` | `{"django-stack": true, "fls": true, "sdd": true}` |
| Permission-rule prefixes in `.claude/settings.json` | `Skill(<plugin-name>:*)`, `mcp__plugin_<plugin-name>_<server>__*` | `"Skill(fls:*)"`, `"mcp__plugin_fls_playwright__*"` | needs a `"Skill(django-stack:*)"` and/or `"Skill(sdd:*)"` entry added, and the playwright MCP permission entry renamed if that server moves |
| Directory name on disk | **Independent of `name`** — directory name and manifest `name` need not match (confirmed by the earlier `extract-django-best-practices` research: *"This is independent of the directory name on disk... the folder can be `django-constitution-claude-plugin/`... while the manifest sets `name: "dc"`"*) | `fls-claude-plugin/` ↔ `name: "fls"` | `claude_plugins/django-stack-claude-plugin/` could set `name: "django-stack"` (or a shorter alias) — **this choice is entirely the author's**; nothing in Claude Code ties them together |
| `claude plugin tag` release tags (only if marketplace + dependency versioning adopted) | `{plugin-name}--v{version}` | n/a | only relevant if `plugin.json`'s `dependencies` field / semver pinning is adopted (see §4 caveat) |

**Everything in this table is driven purely by the `name` field in each plugin's
`.claude-plugin/plugin.json`.** There is no separate "alias" or "display name for namespacing"
concept — `displayName` exists (v2.1.143+) but is explicitly *"Not used for namespacing or
lookup"*, purely a cosmetic label in UI pickers.
(https://code.claude.com/docs/en/plugins-reference#metadata-fields)

**Renaming a plugin later is expensive**: *"A plugin's `name` is its stable identifier. Users
reference it in `enabledPlugins`, `pluginConfigs`, and `/plugin install` commands, so changing it
breaks every existing install."* — this only bites for marketplace-distributed plugins (a
`renames` map in `marketplace.json` is the escape hatch), but it argues for picking each split
plugin's final `name` deliberately in the plan phase rather than iterating on it later, since every
occurrence in the table above has to be re-grepped-and-replaced on a rename.
(https://code.claude.com/docs/en/plugin-marketplaces#rename-or-remove-a-plugin)

---

## 4. Constraints & gotchas

1. **Splitting is a big mechanical rename, not just a directory move.** Every literal
   `fls-claude-plugin/...` path string (path references in `commands/sdd/*.md`, `commands/init.md`,
   the wrapper-script templates, this repo's own `README.md`/skill docs) and every
   `fls:<component>` namespace reference whose component moves plugins must be updated in lockstep.
   Missing one produces a **silent failure at spawn/invoke time** (a `subagent_type` or `Skill()`
   that doesn't resolve, or a `Read` on a path that no longer exists) — there is no static
   validation across plugin boundaries; `claude plugin validate` validates one plugin/marketplace
   at a time, not cross-plugin references baked into markdown prose.
2. **`claude.sh` (and the generated wrapper template) must load every split plugin together**, or
   cross-plugin references silently break (§1, §2). This is the single most important
   infrastructure change and the one most likely to be missed if only the plugin directories are
   moved without updating the launcher.
3. **The nested `commands/sdd/` subdirectory pattern is on shaky documented ground** (§2). If SDD
   is extracted into its own plugin literally named `sdd`, keeping a `commands/sdd/*.md`
   subdirectory inside it would (if subdirectory-namespacing behaves the way this repo's own docs
   assume) produce a redundant `/sdd:sdd:start`-shaped name. **The safe, docs-aligned move is to
   flatten the new `sdd` plugin's commands directly into `commands/*.md`** (no `sdd/`
   subdirectory), since the plugin name itself now supplies that namespace segment. This also
   simplifies every literal-path reference in `next.md`'s candidate-search logic (§2).
4. **`${CLAUDE_PLUGIN_ROOT}`-based hooks/MCP/LSP configs cannot span plugins** (§2) — the
   already-decided hook split (3 of 4 hook scripts move to `django-stack`, one stays FLS-only, per
   `extract-django-best-practices-claude-plugin/idea.md` Decision 4) requires **physically copying**
   `ruff_fix.sh`, `post-edit-bandit.sh`, and `security-guard.sh` into the new plugin's own
   `scripts/hooks/` directory, and splitting `hooks/hooks.json` itself into two files (one per
   plugin) rather than one shared file two plugins both point at.
5. **`.mcp.json` (playwright) and `.lsp.json` (pyright) are both stack-generic**, matching the
   extract-idea's proposed `dc:playwright-tests`/`dc:use-playwright` skills — if these move to
   `django-stack`, the MCP tool-name permission entries in `.claude/settings.json`
   (`mcp__plugin_fls_playwright__*`) must be renamed to match the new plugin name, and any skill
   prose that says "the `fls:playwright-tests` skill" needs updating to `django-stack:playwright-tests`.
6. **Plugin "dependencies" (the `plugin.json` `dependencies` field, e.g. `fls` declaring it needs
   `django-stack`) is a real, documented feature — but it is a *marketplace* feature**, not a
   `--plugin-dir` one. It resolves dependency versions against **git tags on the marketplace
   repository** in the form `{plugin-name}--v{version}`, and auto-enable/auto-install only fires
   through the `/plugin install`/`/plugin enable` install pipeline. For this repo's actual
   development mode (`--plugin-dir`, no marketplace), **declaring `dependencies` in `plugin.json`
   has no observed enforcement effect** — nothing will auto-load `django-stack` because `fls`
   declares a dependency on it; the `--plugin-dir` flag list in `claude.sh` remains the only thing
   that actually loads it. If the idea/plan wants a `fls → django-stack` dependency to be
   *meaningful* (auto-enable, version pinning), that requires wrapping both in a marketplace
   (`.claude-plugin/marketplace.json` at the repo root, source type `"./plugins/django-stack"` or
   similar relative path — see [Relative paths](https://code.claude.com/docs/en/plugin-marketplaces#relative-paths))
   and tagging releases — a materially bigger scope than "just split the directories."
   (https://code.claude.com/docs/en/plugin-dependencies)
7. **Portability goal vs. same-repo convenience are in tension for `django-stack`.** The idea
   explicitly wants `django-stack` "portable... usable in unrelated Django projects." Today's
   `--plugin-dir`-only wiring only works *inside this repo* (or any repo that clones/vendors the
   plugin directory and points a launcher at it). Making `django-stack` genuinely reusable
   elsewhere implies either (a) every consuming project also runs a `--plugin-dir`-style launcher
   pointed at a copy/submodule/subtree of `claude_plugins/django-stack-claude-plugin/`, or (b)
   publishing it via a marketplace (`git-subdir` source pointing at
   `claude_plugins/django-stack-claude-plugin` inside this monorepo, mirroring the
   `content-plugin-distribution/idea.md` pattern already chosen for `fls-content`). This is a
   distribution decision the split's plan phase should make explicit, not an automatic consequence
   of moving files into `claude_plugins/`.
8. **Version pinning caveat, if adopted later**: *"If you set `version` in `plugin.json`, you must
   bump it every time you want users to receive changes... Avoid setting `version` in both
   `plugin.json` and the marketplace entry."* Not relevant to same-repo `--plugin-dir` use (there's
   no "update" concept for a session-scoped local plugin — the *files on disk* are always current),
   but relevant the moment any split plugin is marketplace-distributed.
   (https://code.claude.com/docs/en/plugins-reference#version-management)
9. **Plugin `CLAUDE.md`, if any, is never loaded as project context** — *"A `CLAUDE.md` file at the
   plugin root is not loaded as project context. Plugins contribute context through skills, agents,
   and hooks rather than CLAUDE.md."* Not an issue today (no plugin has a root `CLAUDE.md`), but
   worth remembering if someone reflexively adds one to a new split plugin expecting it to behave
   like the project's own `CLAUDE.md`.
10. **No cross-plugin static validation exists.** `claude plugin validate <dir>` validates one
    plugin (or one marketplace + its listed plugins) at a time — it will not catch a dangling
    `subagent_type: "sdd:sdd-worker"` reference in a plugin that no longer ships that agent, or a
    stale `fls-claude-plugin/...` path string post-move. Manual grep-and-fix (or a dedicated
    plan-phase checklist) is the only safety net.
11. **Target version**: all of the above is current as of the Claude Code 2.1.x docs fetched during
    this research (some cited behaviors are gated to specific 2.1.1xx–2.1.21x point releases, noted
    inline above, e.g. the `renames` field requiring 2.1.193+, plugin-detail "Will install" listing
    requiring 2.1.145+). None of the load-bearing mechanics for this split (multi `--plugin-dir`,
    namespacing rules, `${CLAUDE_PLUGIN_ROOT}` scoping) are behind a version gate — they're
    long-standing baseline behavior.

---

## Sources

- This repo (read directly): `fls-claude-plugin/skills/claude-code-authoring/SKILL.md` +
  `resources/{subagents,fanout_recipe,model_tiering,interactive_cli}.md`;
  `fls-claude-plugin/.claude-plugin/plugin.json`; `fls-content-plugin/.claude-plugin/plugin.json`;
  `fls-claude-plugin/.mcp.json`; `fls-claude-plugin/.lsp.json`; `fls-claude-plugin/hooks/hooks.json`;
  `.claude/settings.json`; `claude.sh`; `fls-claude-plugin/templates/{settings.json,wrapper_scripts/claude.sh}`;
  `fls-claude-plugin/commands/{init.md,sdd/*.md}`; `fls-claude-plugin/agents/*.md`;
  `spec_dd/3. done/2026-04-02_12:31_make-claude-code-plugin/research_plugin_system.md`;
  `spec_dd/1. next/extract-django-best-practices-claude-plugin/{idea.md,research_plugin_architecture.md}`;
  `spec_dd/1. next/content-plugin-distribution/idea.md`;
  `spec_dd/3. done/2026-06-24_00:22_course-editing-plugin/research_claude_plugin_structure.md`.
- [Plugins reference — Claude Code Docs](https://code.claude.com/docs/en/plugins-reference)
  (manifest schema, component locations, `${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PLUGIN_DATA}`, plugin
  caching & file resolution, symlink sharing, version management)
- [Create plugins — Claude Code Docs](https://code.claude.com/docs/en/plugins) (namespacing
  quickstart, `--plugin-dir` multiple-flag usage, migration guide)
- [Create and distribute a plugin marketplace — Claude Code Docs](https://code.claude.com/docs/en/plugin-marketplaces)
  (`marketplace.json` schema, source types, relative-path resolution, `renames`, cross-marketplace
  dependency allowlist, `enabledPlugins` for marketplace plugins)
- [Discover and install prebuilt plugins — Claude Code Docs](https://code.claude.com/docs/en/discover-plugins)
  (team marketplace config, `extraKnownMarketplaces`, `--plugin-dir` precedence, reload behavior)
- [Constrain plugin dependency versions — Claude Code Docs](https://code.claude.com/docs/en/plugin-dependencies)
  (`dependencies` field, semver ranges, git-tag resolution, cross-marketplace dependency rules,
  enable/disable cascading — all marketplace-scoped)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
  ("How a skill gets its command name" naming table, nested `.claude/skills/` directory-qualified
  naming, plugin skill naming)
- [Sub-agents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents) (agent scoped-name
  `@-mention`, plugin agent frontmatter restrictions)
- [CLI reference — Claude Code Docs](https://code.claude.com/docs/en/cli-reference) (`--plugin-dir`
  flag exact syntax, repeatability)

status: ok
