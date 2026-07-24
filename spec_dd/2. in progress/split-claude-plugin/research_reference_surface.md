\
# Research: Complete reference surface for the plugin split/relocation

Idea: split `fls-claude-plugin/` into `django-stack` / `fls` / (maybe) `sdd` plugins, all moved under
a new `claude_plugins/` directory. This document maps **every** kind of reference in the repo that
would break, silently go stale, or need updating as a result — organized so a future plan can turn
each row into a concrete edit.

Methodology: whole-repo `Grep` (not scoped to `fls-claude-plugin/`) for `fls-claude-plugin`,
`fls-content-plugin`, `fls:`, `plugin_fls`, `$FLS_PLUGIN`/`FLS_PLUGIN=`, `CLAUDE_PLUGIN_ROOT`, plus
targeted reads of `.claude/settings.json`, `fls-claude-plugin/templates/*`, `commands/init.md`,
`hooks/hooks.json`, `.mcp.json`, `.lsp.json`, `pyproject.toml`, `.gitignore`, root `README.md`, and
the sibling `fls-content-plugin/`.

---

## 0. TL;DR — highest-risk / easiest-to-miss items

1. **`fls:sdd-worker` / `fls:sdd-mechanic` subagent-type strings are hardcoded in ~20 command/skill
   files.** The `fls:` prefix is *derived* from `plugin.json`'s `"name": "fls"` combined with the
   agent's own `name:` frontmatter (`sdd-worker`, `sdd-mechanic`, `qa-data-helper`, `code-reviewer` —
   none of the agent files hardcode `fls:` themselves). If SDD agents move to a new `sdd` plugin, every
   `subagent_type: "fls:sdd-worker"` / `"fls:sdd-mechanic"` literal across the fanned-out command files
   becomes wrong and must change to `"sdd:sdd-worker"` / `"sdd:sdd-mechanic"` (or whatever the new
   plugin is named) — grep found this string pattern in **~20 files**, not just the agent definitions.
2. **Agent-memory directory names encode the plugin name.** `.claude/agent-memory/fls-code-reviewer/`
   and `.claude/agent-memory/fls-qa-data-helper/` follow a `<plugin-name>-<agent-name>` convention
   (from `memory: project` in the agent frontmatter). If `code-reviewer` moves to `django-stack` and/or
   `qa-data-helper` stays in `fls`, the on-disk memory folder name changes (e.g. to
   `django-stack-code-reviewer`) and **all existing accumulated memory becomes orphaned** unless it is
   deliberately migrated (`git mv`) alongside the split. Easy to miss because nothing in the plugin
   source references this path — it's inferred by the Claude Code runtime.
3. **~15 self-referential hardcoded paths to `fls-claude-plugin/commands/sdd/protected/*.md`** live
   *inside the plugin's own command files* (see §2). These do not use `${CLAUDE_PLUGIN_ROOT}` and would
   need to become e.g. `${CLAUDE_PLUGIN_ROOT}/commands/protected/update_todo.md` or
   `claude_plugins/sdd/commands/protected/update_todo.md`, depending on the chosen layout.
4. **`mcp__plugin_fls_playwright__*` permission glob** in `.claude/settings.json` bakes in the plugin
   name `fls` twice over (`plugin_fls_` is Claude Code's own name-spacing of the `.mcp.json` server
   named `playwright`, owned by the `fls` plugin). Whichever new plugin ends up owning `.mcp.json` (and
   `hooks.json`/`.lsp.json`) changes this glob's exact string — it is very easy to update the
   `enabledPlugins` key and the `Skill(fls:*)` glob but forget this one, since it's a compound,
   non-obvious derived name.
5. **The slash-command-namespace convention already looks internally inconsistent** and needs to be
   verified against actual Claude Code behavior before the split, not assumed: `commands/init.md`
   (directly under `commands/`) is documented as invoked via `/fls:init` (plugin-name prefix), while
   `commands/sdd/start.md` (one level deeper) is documented and self-referenced throughout as
   `/sdd:start` (no `fls:` prefix — as if the *subdirectory* were the namespace, not the plugin name).
   If the true Claude Code rule is "prefix is always the plugin name, subdirectories just concatenate
   into the command name" (e.g. real invocation is `/fls:sdd:start`), then **all ~40 in-repo
   `/sdd:whatever` references are already documentation of the wrong invocation string**, and splitting
   `sdd` into its own plugin would coincidentally "fix" this by making `/sdd:start` correct for the
   first time. This must be confirmed against current Claude Code plugin docs before relying on it —
   flagging as open question, not deciding it here.
6. **`init.md`'s hard requirements assume exactly one plugin.** Step 1 merges `"fls": true` into a
   single `enabledPlugins` key; Step 5/6 assume one `${CLAUDE_PLUGIN_ROOT}`, one `fls-claude-plugin/`
   directory check (`<fls_path>/fls-claude-plugin/`), and one `claude.sh` wrapper. A split needs either
   three separate `init` commands (one per plugin) or one command taught to loop over multiple
   plugins/roots — this is real design work, not a find-and-replace.
7. **Whether `fls-content-plugin` also moves under `claude_plugins/` is undecided** — the idea text
   only names `django-stack`/`fls`/`sdd`. `fls-content-plugin` is today a fully independent sibling
   plugin (own `plugin.json` name `fls-content`, own `/fls-content:init` etc.) with only a one-way,
   file-copy sync relationship to `fls-claude-plugin` (see §7). Flagged for a human decision, not
   resolved here.

---

## 1. Plugin-name-derived identifiers

Everywhere Claude Code derives a namespaced identifier from `plugin.json`'s `"name": "fls"` (or the
agent/skill's own name). All of these are indirect — none of them say `fls-claude-plugin` as a string;
they say `fls:` because that's the plugin's declared name.

### 1a. `enabledPlugins` keys

| File | Line | Reference |
|---|---|---|
| `.claude/settings.json` | 61-63 | `"enabledPlugins": { "fls": true }` |
| `fls-claude-plugin/templates/settings.json` | n/a | template does **not** include `enabledPlugins` at all — it's added by `commands/init.md` Step 1 at merge time, not shipped in the template |

**Change needed:** once split, every downstream project's `.claude/settings.json` needs one
`enabledPlugins` key **per new plugin** (`"django-stack": true`, `"fls": true`, `"sdd": true` or
similar), and `commands/init.md` Step 1 (and its validation Step 8, "Confirm `fls` is in
`enabledPlugins`") must be taught to write/check multiple keys.

### 1b. `Skill(fls:*)` permission entries

| File | Line |
|---|---|
| `.claude/settings.json` | 32: `"Skill(fls:*)"` |

Only one occurrence in this repo's own settings (the template doesn't grant it — see §1a). If skills
are split across `django-stack`/`fls`/`sdd`, this single glob must become three globs
(`Skill(django-stack:*)`, `Skill(fls:*)`, `Skill(sdd:*)`) or a broader pattern, in both this repo's
`.claude/settings.json` and, if the template ever adds it, `fls-claude-plugin/templates/settings.json`.

### 1c. Agent types `fls:sdd-worker` / `fls:sdd-mechanic` / `fls:qa-data-helper` / `fls:code-reviewer`

The **agent files themselves** only declare an unprefixed `name:` (confirmed by reading all four):

- `fls-claude-plugin/agents/sdd-worker.md` → `name: sdd-worker`
- `fls-claude-plugin/agents/sdd-mechanic.md` → `name: sdd-mechanic`
- `fls-claude-plugin/agents/qa-data-helper.md` → `name: qa-data-helper`
- `fls-claude-plugin/agents/code-reviewer.md` → `name: code-reviewer`

The `fls:` prefix appears only where **other files reference these agents** via `subagent_type:` or
prose. Grep for `fls:sdd-worker` / `fls:sdd-mechanic` (pattern `fls:sdd`) found it in:

- `fls-claude-plugin/commands/sdd/finish_worktree.md` (4 places)
- `fls-claude-plugin/commands/sdd/improve_idea.md` (2)
- `fls-claude-plugin/commands/sdd/update_upgrade_notes.md` (1)
- `fls-claude-plugin/commands/sdd/protected/setup_todo_list.md` (1, as `fls:qa-data-helper`)
- `fls-claude-plugin/commands/sdd/update_product_docs.md` (3, incl. `fls:qa-data-helper`)
- `fls-claude-plugin/commands/sdd/do_qa.md` (7, all `fls:qa-data-helper`)
- `fls-claude-plugin/commands/sdd/update_claude_plugin_fls_content.md` (2)
- `fls-claude-plugin/commands/sdd/start.md` (2)
- `fls-claude-plugin/commands/sdd/implement_plan.md` (4, prose mentions of `fls:sdd-mechanic` /
  `fls:sdd-worker` as contrast points, plus `subagent_type: "general-purpose"` explicitly *not*
  `fls:sdd-worker`)
- `fls-claude-plugin/commands/sdd/plan_security_review.md` (2)
- `fls-claude-plugin/commands/sdd/README.md` (2, incl. model-tiering explainer)
- `fls-claude-plugin/commands/sdd/plan_structure_review.md` (2)
- `fls-claude-plugin/commands/sdd/plan_from_spec.md` (3)
- `fls-claude-plugin/commands/sdd/spec_from_idea.md` (2)
- `fls-claude-plugin/skills/claude-code-authoring/resources/model_tiering.md` (2)
- `fls-claude-plugin/skills/claude-code-authoring/resources/fanout_recipe.md` (2)

Plus the `qa-data-helper`/`code-reviewer` references baked into `.claude/agent-memory/` directory
names (see §0.2) and into `.claude/settings.json`'s comment-free `Skill(fls:*)` glob.

**Change needed:** if the SDD workflow (worker/mechanic) moves to a new `sdd` plugin, every one of
these ~30 literal occurrences of `fls:sdd-worker`/`fls:sdd-mechanic` must become
`sdd:sdd-worker`/`sdd:sdd-mechanic` (exact new name TBD by the plan). If `qa-data-helper` and
`code-reviewer` land in a *different* plugin than the SDD agents (likely, since they're not SDD-specific
— `code-reviewer` looks like a `django-stack`/general candidate and `qa-data-helper` an `fls` candidate),
those need their own distinct prefix, independent from the SDD agents' prefix. **This is not a single
find-and-replace** — the three (or four) agent files may end up in three different plugins with three
different prefixes, so each reference site needs to be re-checked individually, not bulk-renamed.

### 1d. Slash-command prefixes `/fls:...`

Documented/self-referenced command invocations found:

- `/fls:init` — `fls-claude-plugin/README.md:17`, `fls-claude-plugin/commands/init.md:12` (x2)
- `/sdd:start`, `/sdd:next` — used **without** an `fls:` prefix throughout `commands/sdd/*.md` and
  `commands/sdd/protected/*.md` (see §0.5 — this inconsistency needs resolving/verifying, not assumed)
- `/update_fls`, `/update_template_repo`, `/update_claude_plugin_fls_content`,
  `/update_upgrade_notes`, `/update_product_docs`, `/address_pr_review`, `/finish_worktree`,
  `/do_qa`, `/app_map` — top-level commands, referenced unprefixed in prose throughout
  `commands/sdd/README.md` and other command files (their true invocation form also depends on
  resolving §0.5)

**Change needed:** once the split determines which plugin owns which command file, every prose
reference to that command's slash-invocation string across the whole `commands/sdd/` tree (and
`skills/claude-code-authoring/resources/*.md`, which documents the convention) must be checked for the
correct new prefix. Given the volume (~40+ prose mentions of `/sdd:...` alone), this is best handled as
a dedicated fan-out unit in the eventual plan, not a manual pass.

### 1e. MCP permission globs `mcp__plugin_fls_playwright__*`

| File | Line |
|---|---|
| `.claude/settings.json` | 31: `"mcp__plugin_fls_playwright__*"` |

Only one live occurrence in actual config (plus a handful of prose mentions inside `spec_dd/3. done/`
historical QA docs — those are frozen history, not live references, but are still literal string
matches: `spec_dd/3. done/2026-05-06_07:52_toasts-bottom-viewport/2. plan.md`,
`spec_dd/3. done/2026-05-05_21:18_fix-fouc-and-empty-sections/3. frontend_qa.md`,
`spec_dd/3. done/2026-05-02_19:32_.../2. plan.md`, `spec_dd/3. done/2026-05-05_13:11_.../3. frontend_qa.md`).

The glob's `plugin_fls_` segment is Claude Code's own derivation from the plugin name (`fls`) + the MCP
server key (`playwright`, declared in `fls-claude-plugin/.mcp.json`). **Change needed:** whichever new
plugin ends up owning `.mcp.json` (playwright) determines the new glob string, e.g.
`mcp__plugin_django-stack_playwright__*` or `mcp__plugin_fls_playwright__*` unchanged if `fls` keeps
Playwright. This is the kind of derived, compound identifier that's trivial to forget when eyes are on
the more obvious `enabledPlugins`/`Skill(...)` edits.

---

## 2. Hardcoded paths pointing into the plugin

### 2a. `fls-claude-plugin/` string occurs in **177 files** repo-wide (grep count).

Breaking that down by realm:

- **Live, functional references (must change on relocation):**
  - `pyproject.toml`:
    - line 251: `[tool.mypy] exclude = ["migrations/", "manage\\.py", "fls-claude-plugin/"]`
  - `claude.sh` (repo root): `--plugin-dir "$SCRIPT_DIR/fls-claude-plugin"` (hardcoded, not templated —
    see §4)
  - `fls-claude-plugin/agents/sdd-mechanic.md:40` — prose pointing at
    `fls-claude-plugin/commands/sdd/protected/update_todo.md` (see §2b, full list there)
  - ~15 command files under `fls-claude-plugin/commands/sdd/**` — the "invoke the helper at
    `fls-claude-plugin/commands/sdd/protected/update_todo.md`" pattern (full list in §2b)
  - `fls-claude-plugin/skills/claude-code-authoring/SKILL.md:87-88` — "Living examples" section
    literally lists `fls-claude-plugin/agents/sdd-mechanic.md`, `sdd-worker.md`, `code-reviewer.md`,
    `qa-data-helper.md` as canonical example paths
  - `fls-claude-plugin/README.md` — self-describes its own structure (`commands/`, `skills/`,
    `agents/`, etc.) relative to itself; if the directory is renamed/moved this doc's framing (and any
    reference to its own path from outside, e.g. from root docs) needs review
- **Historical/narrative references (should NOT be silently bulk-edited — they're point-in-time
  records of what was true when written):** the remaining ~155 files are almost entirely under
  `spec_dd/3. done/**`, `spec_dd/2. in progress/**`, and `spec_dd/1. next/**` — completed or pending
  spec/plan/todo/research documents that mention `fls-claude-plugin` as a path when describing past or
  proposed work (e.g. `spec_dd/3. done/2026-04-02_12:31_make-claude-code-plugin/` — the spec that
  originally created the plugin). These are historical records; only `spec_dd/2. in progress/` and
  `spec_dd/1. next/` entries are "live" enough that a human should skim them for now-stale path
  assumptions before those specs are picked up (see §6).

### 2b. The `update_todo.md` self-reference pattern — full list (highest-risk cluster, §0.3)

Exact string `fls-claude-plugin/commands/sdd/protected/` (or `.../setup_todo_list.md`,
`.../move_spec_to_in_progress.md`, `.../start_worktree.md`) appears hardcoded, **not** via
`${CLAUDE_PLUGIN_ROOT}`, in:

- `fls-claude-plugin/agents/sdd-mechanic.md:40`
- `fls-claude-plugin/commands/sdd/update_upgrade_notes.md:101`
- `fls-claude-plugin/commands/sdd/start.md:10,16,22` (three different protected helpers)
- `fls-claude-plugin/commands/sdd/plan_structure_review.md:103`
- `fls-claude-plugin/commands/sdd/plan_from_spec.md:93`
- `fls-claude-plugin/commands/sdd/next.md:65`
- `fls-claude-plugin/commands/sdd/README.md:135`
- `fls-claude-plugin/commands/sdd/finish_worktree.md:33`
- `fls-claude-plugin/commands/sdd/update_product_docs.md:145`
- `fls-claude-plugin/commands/sdd/update_template_repo.md:87`
- `fls-claude-plugin/commands/sdd/update_claude_plugin_fls_content.md:58`
- `fls-claude-plugin/commands/sdd/improve_idea.md:47`
- `fls-claude-plugin/commands/sdd/do_qa.md:141`
- `fls-claude-plugin/commands/sdd/implement_plan.md:76`
- `fls-claude-plugin/commands/sdd/spec_review.md:41`
- `fls-claude-plugin/commands/sdd/spec_from_idea.md:56`

**Why hardcoded instead of `${CLAUDE_PLUGIN_ROOT}`-relative:** per
`fls-claude-plugin/skills/claude-code-authoring/resources/subagents.md:14-15`, this is deliberate — the
mechanic is told to "read the helper `.md` and follow its steps" literally (there is no `SlashCommand`
tool inside a subagent), so the path has to be resolvable by the calling **agent**, which doesn't
automatically get `${CLAUDE_PLUGIN_ROOT}` substituted into prose the way command frontmatter does.
**Change needed:** every one of these ~16 occurrences must be updated to the new path once `sdd/` (or
wherever `protected/` lives) moves under `claude_plugins/sdd/...` — and the fix should probably
introduce a variable/convention robust to the move, not just a literal string swap, since this pattern
clearly already caused drift once (this repo already treats it as `${CLAUDE_PLUGIN_ROOT}`-worthy in
spirit).

### 2c. `${CLAUDE_PLUGIN_ROOT}` usage (the "does it right" cases — 5 files)

- `fls-claude-plugin/templates/settings.json` — n/a (doesn't use it; it's the merge *source*, not a
  live settings file)
- `fls-claude-plugin/templates/wrapper_scripts/claude.sh` — doesn't use `${CLAUDE_PLUGIN_ROOT}`
  either; uses its own `__FLS_PATH__` substitution mechanism instead (see §3/§4)
- `fls-claude-plugin/commands/init.md` — uses `${CLAUDE_PLUGIN_ROOT}` correctly for
  `templates/settings.json`, `templates/fls.md`, `templates/fls.local.md`,
  `templates/wrapper_scripts/` (4 distinct uses)
- `claude.sh` (repo root) and `.claude/settings.json` — matched by the broader
  `CLAUDE_PLUGIN_ROOT` grep only because of false-positive overlap with `FLS_PLUGIN`/`fls-claude-plugin`
  substring matching; recheck confirms **only `commands/init.md` actually uses**
  `${CLAUDE_PLUGIN_ROOT}` as a real variable.

**Change needed:** none directly — `${CLAUDE_PLUGIN_ROOT}` is plugin-relative and Claude Code resolves
it per-plugin at runtime, so as long as `templates/` moves with `commands/init.md` inside whichever
plugin owns it, these references keep working unmodified. This is the "did it right" example to follow
when fixing §2b.

### 2d. `$FLS_PLUGIN` env var (session-loaded marker, not a path, but plugin-identity-coupled)

- `claude.sh` (repo root): `FLS_PLUGIN=1 claude --plugin-dir "$SCRIPT_DIR/fls-claude-plugin" "$@"`
- `fls-claude-plugin/templates/wrapper_scripts/claude.sh`: same pattern, templated with
  `__FLS_PATH__`
- `.claude/settings.json` `SessionStart` hook: checks `[ -n "$FLS_PLUGIN" ]`, prints a "FLS PLUGIN NOT
  LOADED" error telling the user to run `./claude.sh` if unset
- `fls-claude-plugin/templates/settings.json` `SessionStart` hook: identical check, shipped as the
  template merged by `init.md`
- `fls-claude-plugin/commands/init.md:94` — Step 7 looks for a **legacy** `CLAUDE.md` line mentioning
  `FLS_PLUGIN` (pre-hook-era) to clean up
- All 8 wrapper scripts under `.claude/fls/scripts/*.sh` and
  `fls-claude-plugin/templates/wrapper_scripts/*.sh` carry the comment `# FLS_PATH is set during
  \`fls:init\` to the path where FLS is installed` (not `$FLS_PLUGIN` itself, but the sibling
  `FLS_PATH` convention — see §3/§4)

**Change needed:** if the plugin now loads as three separate plugin directories (one `--plugin-dir` per
plugin, or a single directory containing all three under `claude_plugins/`), `claude.sh`'s
`--plugin-dir` argument(s) need to change from a single `fls-claude-plugin` path to either three
`--plugin-dir` flags or one `--plugin-dir claude_plugins` (if Claude Code supports directories-of-plugins
in one flag — needs confirming against Claude Code CLI docs, not assumed here). The `$FLS_PLUGIN`
sentinel var itself could stay name-stable (it's just a loaded/not-loaded marker) or could reasonably
be renamed if the "FLS" identity no longer maps 1:1 onto "the plugin" once there are three plugins —
flag as a design question for the plan, not resolved here.

---

## 3. The `init` command surface — what it writes into a target project

Read in full: `fls-claude-plugin/commands/init.md`. It performs 8 steps. Every one of them is
currently written assuming **exactly one plugin**:

| Step | What it writes/checks | Single-plugin assumption baked in |
|---|---|---|
| 1 | Merge `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` allow/deny rules; add `"fls": true` to `enabledPlugins`; merge one `SessionStart` hook | Hardcodes the literal key `"fls"`; assumes only one plugin's permissions template needs merging |
| 2 | Create/extend `.claude/fls/config.md` from `${CLAUDE_PLUGIN_ROOT}/templates/fls.md` | Path `.claude/fls/` is FLS-specific; a `django-stack` or `sdd` plugin would need its own config namespace, or all three would need to agree to share `.claude/fls/` (semantically odd if `fls` is no longer "the whole plugin") |
| 3 | Create/extend `.claude/fls/config.local.md` from `templates/fls.local.md`, incl. the `## Template Repo` path used by `/update_template_repo` | Same `.claude/fls/` coupling; also couples the SDD-specific `update_template_repo` step's config location to the `fls` plugin's directory even though that command may move to `sdd` |
| 4 | Append to `.gitignore`: `.claude/fls/config.local.md`, `.claude/settings.local.json` | Path `.claude/fls/...` again |
| 5 | Ask for FLS path; validate `<fls_path>/fls-claude-plugin/` exists | **Directly hardcodes `fls-claude-plugin/` as a literal path segment to validate** — breaks the instant the directory is renamed/moved, regardless of split |
| 6 | Generate wrapper scripts from `${CLAUDE_PLUGIN_ROOT}/templates/wrapper_scripts/*`, substituting `__FLS_PATH__` | `__FLS_PATH__` bakes in "FLS" as the name of the placeholder even for scripts (db scripts, etc.) that are arguably `django-stack`-generic, not FLS-specific |
| 7 | Clean up legacy `CLAUDE.md` line mentioning `FLS_PLUGIN` | Not split-sensitive per se, but historical cruft cleanup logic that assumes one plugin identity |
| 8 | Validate: confirm `"fls"` in `enabledPlugins`; confirm `SessionStart` hook checks `$FLS_PLUGIN`; etc. | Same single-key/single-var assumptions as Step 1 |

**Change needed:** this is the single largest design surface in the whole idea. Concretely:
- Step 1/8's `"fls"` key literal must become N keys (one per new plugin) — needs the command to either
  hardcode all N plugin names or be told which plugins exist.
- Step 5's `<fls_path>/fls-claude-plugin/` existence check is a literal path string that must be
  updated regardless of how the split resolves (it's really `<fls_path>/claude_plugins/` post-move even
  without a split) — this is probably the **single most obvious, easy-to-find** required edit in this
  whole document, in contrast to §0's harder-to-find ones.
- Whether `init.md` becomes **one command that loops over N plugin manifests**, or **N separate
  `init.md` files (one per plugin, each merging its own `enabledPlugins` key/templates)** is an open
  design question for the plan — this research doesn't resolve it, only flags that today's single
  8-step script assumes "one plugin" pervasively enough that it can't be patched with a few renames.
- `.claude/fls/` as the config-directory name becomes semantically confusing once `fls` is one of
  three plugins rather than "the whole thing" — worth flagging to the plan even though it's a naming
  question, not a strict breakage.

---

## 4. Root-project wiring

| File | Coupling |
|---|---|
| `claude.sh` (repo root) | `FLS_PLUGIN=1 claude --plugin-dir "$SCRIPT_DIR/fls-claude-plugin" "$@"` — hardcoded single-plugin dir, **not** generated from a template (this is FLS's own root wrapper, distinct from the templated one `init.md` generates for downstream projects) |
| `.claude/settings.json` | `enabledPlugins: {"fls": true}`; `Skill(fls:*)`; `mcp__plugin_fls_playwright__*`; `SessionStart` hook checking `$FLS_PLUGIN` — all covered in §1 |
| `CLAUDE.md` (repo root) | Read in full at the top of this task — contains **no** direct `fls-claude-plugin`/`fls:` references; only prose instructions (e.g. "Whenever you are asked to do anything, check what skills are available"). Not a reference-surface hit, but worth a final read-through once skills relocate, since its instructions assume skills exist somewhere discoverable — no path assumption to fix. |
| `.claude/fls/config.md` | Dev credentials (`demodev@email.com`, base URL) — created by `init.md` Step 2; directory name `fls` per §3 |
| `.claude/fls/scripts/*.sh` (8 scripts) | Each carries the comment `# FLS_PATH is set during \`fls:init\` to the path where FLS is installed` — copied verbatim from `fls-claude-plugin/templates/wrapper_scripts/*.sh` (see §2d) |
| `.gitignore` | Lines 31-32: `.claude/settings.local.json`, `.claude/fls/config.local.md` — path literal `.claude/fls/` per §3 |
| `fls-claude-plugin/hooks/hooks.json` | Uses `${CLAUDE_PLUGIN_ROOT}/scripts/hooks/ruff_fix.sh`, `.../post-edit-bandit.sh`, `.../security-guard.sh` — correctly plugin-relative, no literal path; will keep working as long as `scripts/hooks/` moves together with `hooks.json` inside whichever plugin owns hooks |
| `fls-claude-plugin/.mcp.json` | Declares the `playwright` MCP server (`npx @playwright/mcp --headless`) — owning plugin determines the `mcp__plugin_<name>_playwright__*` glob (§1e) |
| `fls-claude-plugin/.lsp.json` | Declares the `python` LSP (`uv run pyright --stdio`) — no plugin-name-derived identifier found in this repo's config referencing it directly by a compound name (unlike MCP), but confirm whether Claude Code namespaces LSP tool permissions the same way before assuming it's "free" |

---

## 5. Marketplace / manifest

- **No `marketplace.json` exists anywhere in the repo** (glob search came back empty).
- Plugin discovery today happens purely via **`--plugin-dir`**, passed explicitly by `claude.sh`
  (pointing at `fls-claude-plugin`) — there is no marketplace/registry layer; each plugin is loaded by
  direct filesystem path.
- `fls-claude-plugin/.claude-plugin/plugin.json` → `{"name": "fls", "version": "1.0.0", ...}`
- `fls-content-plugin/.claude-plugin/plugin.json` → `{"name": "fls-content", "version": "1.0.0", ...}`
  (loaded independently — not via the same `claude.sh`; no wiring found in this repo's root `claude.sh`
  that loads `fls-content-plugin` at all, meaning **it currently isn't loaded when running FLS's own
  `./claude.sh`** — it must be loaded some other way, e.g. by whoever authors course content directly
  passing `--plugin-dir fls-content-plugin`, or manually. This is itself worth confirming, independent
  of the split.)

**Change needed:** moving to `claude_plugins/django-stack/`, `claude_plugins/fls/`,
`claude_plugins/sdd/` implies **either**:
- (a) `claude.sh` grows multiple `--plugin-dir` flags (one per subdirectory), or
- (b) Claude Code supports pointing `--plugin-dir` at a parent directory containing multiple
  plugin subdirectories (each with its own `.claude-plugin/plugin.json`) and auto-discovering them —
  **this needs to be verified against current Claude Code CLI docs**, since nothing in this repo
  currently exercises that shape (today there is exactly one `--plugin-dir` argument, one plugin).
- If (b) isn't supported, introducing a real `marketplace.json` (or equivalent) at
  `claude_plugins/` may become newly necessary just to make the split loadable at all — flagging this
  as a possible **hidden prerequisite** of the idea, not just a reference to update.

---

## 6. Docs & specs mentioning the plugin by path or name

- Root `README.md` — **no matches** for `fls-claude-plugin`, `fls-content-plugin`, or `claude_plugins`
  (confirmed by direct grep of the file). No change needed there.
- `docs/` — **no matches** for `fls-claude-plugin` or `fls-content-plugin` anywhere under `docs/`
  (confirmed by grep scoped to that directory). No change needed there.
- `spec_dd/` — 177 files match `fls-claude-plugin` and 211 files match `fls:` (see §2a breakdown).
  Overwhelmingly these are `spec_dd/3. done/**` historical records that should be left untouched (they
  document what was true at the time). The **live** exceptions worth a human skim before/after the
  split lands:
  - `spec_dd/2. in progress/split-claude-plugin/` (this spec itself — its own `todo.md`/`idea.md`
    already reference `fls-claude-plugin` and `/update_claude_plugin_fls_content`)
  - `spec_dd/2. in progress/support-concrete-project-deployment/idea.md`,
    `spec-order.md`, `research_importable_base_settings.md`,
    `research_deployment_scaffolding_references.md` — active spec referencing `/fls:sdd:update_fls`,
    `/fls:sdd:update_template_repo` (note: uses the `/fls:sdd:...` **three-level** form, in contrast to
    the `/sdd:...` two-level form used inside `fls-claude-plugin/commands/sdd/*.md` itself — another
    data point for the §0.5 namespace-inconsistency flag)
  - `spec_dd/2. in progress/fls-test-portability-part-2/`,
    `spec_dd/2. in progress/test_portability_3_system_checks/`,
    `spec_dd/2. in progress/compliance-form-randomization/` — each has a `todo.md` line
    `Run \`/update_claude_plugin_fls_content\` to sync the course-author plugin` (the SDD workflow's own
    generated checklist item — will need the command name kept in sync with wherever
    `update_claude_plugin_fls_content.md` ends up living)
  - `spec_dd/1. next/extract-django-best-practices-claude-plugin/` (idea + 2 research files) — an
    **already-queued, not-yet-started idea** that explicitly proposes extracting portable Django
    best-practice skills into their own plugin, i.e. **directly overlaps with this idea's
    `django-stack` plugin**. This needs reconciling by a human — either this idea supersedes that one,
    or the two should be merged/sequenced, before planning proceeds.
  - `spec_dd/1. next/content-plugin-distribution/idea.md` — a queued idea about distributing
    `fls-content-plugin` separately; relevant context for the §7 open question about whether
    `fls-content-plugin` also relocates.
- `fls-claude-plugin/README.md`, `fls-claude-plugin/commands/**/README.md` (root, `concrete/`,
  `periodic/`, `sdd/`) — self-describing docs; content will need updating in place as part of whichever
  plugin each ends up in (already covered file-by-file in §1/§2).

---

## 7. The sibling `fls-content-plugin` — open question, not decided here

Findings, not a decision:

- `fls-content-plugin/` is a **fully separate, independently-versioned plugin** today: own
  `.claude-plugin/plugin.json` (`"name": "fls-content"`), own `/fls-content:init`,
  `/fls-content:format-content`, `/fls-content:validate-content` commands, own skills
  (`fls-content:content-types`, `fls-content:widget-reference`, `fls-content:markdown-conversion`,
  `fls-content:conventions`), own bundled Python validator (`fls-content-plugin/validate/`).
- The **only** coupling to `fls-claude-plugin` is a **one-way, file-copy sync**, not a runtime
  dependency: `fls-claude-plugin/commands/sdd/update_claude_plugin_fls_content.md` is an SDD workflow
  step (Step 9, run via `/update_claude_plugin_fls_content`) that fans out one `fls:sdd-worker` to copy
  changes from `freedom_ls/content_engine/{schema,validate}.py` into
  `fls-content-plugin/validate/{schema,validate}.py` (each bundled file's top comment says `# Bundled
  from freedom_ls/content_engine/... — re-sync via /update_claude_plugin_fls_content`) and to update
  `fls-content-plugin`'s reference skills when authoring functionality changes. There is a corresponding
  `.claude/agent-memory/fls-code-reviewer/project_fls_content_plugin.md` memory file documenting the
  exact re-apply patches needed on each re-sync (Django-icon stub, standalone CLI shim).
- `fls-content-plugin` is **not loaded by this repo's own root `claude.sh`** (which only passes
  `--plugin-dir fls-claude-plugin`) — confirming it's used independently (e.g. by course-authoring
  repos), not as part of the same session as the dev-facing plugin.
- The idea text (`spec_dd/2. in progress/split-claude-plugin/idea.md`) names only
  `django-stack`/`fls`/`sdd` as the target plugins and says "Put all the plugins into a new directory
  called `claude_plugins/`" without mentioning `fls-content-plugin`.

**Open question for the human (not decided here):** does `claude_plugins/` become the new home for
*all* plugins in this repo (i.e. `fls-content-plugin` also moves to `claude_plugins/fls-content/`), or
does it stay at the repo root as it is today, sitting alongside the new `claude_plugins/` directory? If
it moves, the `update_claude_plugin_fls_content.md` sync command's hardcoded output path
(`fls-content-plugin/validate/...`) needs updating too, and the command's own name
(`update_claude_plugin_fls_content`) — which literally embeds "claude_plugin_fls_content" — becomes an
odd fossil either way and may be worth renaming as part of this same piece of work (flagging, not
deciding).

---

## Footer

status: ok
