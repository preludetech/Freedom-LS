# Idea: Split the monolithic plugin into focused, portable plugins under `claude_plugins/`

The plugin at `fls-claude-plugin/` currently mixes three separable concerns: portable Django-stack
best practices, FreedomLS-product-specific conventions, and a generic spec-driven-development (SDD)
workflow. Split it into separate plugins so the portable parts can be reused in unrelated projects,
and gather all plugins (including the existing `fls-content-plugin`) under a new top-level
`claude_plugins/` directory.

> This is a refactor of Claude Code plugin *authoring* artifacts (commands, skills, agents, hooks,
> scripts) — not a change to the Django application. The bar the idea sets for the SDD split is
> **"only do it if it's quite straightforward."**

## Supersedes an existing queued idea

This spec **absorbs and supersedes** the queued idea
`spec_dd/1. next/extract-django-best-practices-claude-plugin/`, which independently proposed
extracting the portable Django skills into their own plugin (it named it `dc`/`django-constitution`).
That idea's *resolved decisions* are carried forward here (see "Decisions carried over" below); the
older spec directory should be retired/merged as part of this work so there is a single source of
truth. The one deliberate change from it: the portable Django plugin is named **`django-stack`**
(manifest `name: "ds"`), not `dc`.

## Target layout

```
claude_plugins/
  django-stack-claude-plugin/    # name: "ds"   — portable Django/stack conventions
  fls-claude-plugin/             # name: "fls"  — FreedomLS-product-specific
  sdd-claude-plugin/             # name: "sdd"  — portable spec-driven-development workflow
  fls-content-plugin/            # name: "fls-content" — course-authoring (moved from repo root)
```

## The plugins

### `django-stack` (`ds`) — portable Django-stack conventions

Anything that helps *any* Django project on this stack (Python 3.13+, Django 6.x, PostgreSQL, HTMX,
Tailwind, optional Cotton + Alpine.js + django-tasks), with **no** FreedomLS domain knowledge. Same
tools, same code structure and quality on an unrelated project. Portable-skill candidates (per the
categorization research and the superseded spec): `testing`, `frontend-styling`/tailwind, `template`
+ cotton + partials, `htmx`, `alpine-js`, `playwright-tests`, `use-playwright`, plus the generic
`app_map` / `security-review` commands, the `code-reviewer` agent, and the three stack-generic hook
scripts (`ruff_fix.sh`, `post-edit-bandit.sh`, `security-guard.sh`), `.mcp.json` (Playwright),
`.lsp.json` (Pyright). Includes its own `/ds:init` for per-project paths/flags.

### `fls` — FreedomLS-specific

Everything tied to how *this* product works: multi-tenant/site-aware conventions, the custom user
model, registration, markdown-content models, admin, icons, brand, `qa-data-helper`, the
FLS-specific SDD steps (see below), the `concrete/update_fls.md` downstream flow, and FLS's own
`/fls:init`. Where a portable skill carried an FLS-specific layer, `fls` keeps a **thin overlay
skill** that references the `ds` skill and adds only the site-aware/FLS delta (no duplicated content).

### `sdd` — portable spec-driven-development workflow (scoped, partial extraction)

Research verdict: a clean mechanical move for ~60% of the SDD surface; the rest is genuinely tangled
with Django/FLS and stays in `fls`. **We do the scoped move and do not attempt full generalization in
this pass.** See `research_sdd_coupling.md` for the file-by-file table. Summary:

- **Moves to `sdd`:** the `sdd-worker` and `sdd-mechanic` agents, the `claude-code-authoring` skill,
  and the generic command files (`improve_idea`, `spec_from_idea`, `spec_review`, `plan_from_spec`,
  `implement_plan`, `next`, `start`, `finish_worktree`, the `protected/` helpers — including the full
  15-section `setup_todo_list` todo template, `threat-model`) — each with a namespace rename and small
  mechanical edits to strip/parameterize a few FLS-flavoured lines.
- **Stays in `fls`:** `do_qa`, `plan_security_review`, `plan_structure_review`,
  `update_product_docs`, `update_upgrade_notes`, `update_template_repo`,
  `update_claude_plugin_fls_content`, `qa-data-helper`, and `concrete/update_fls`.
- **Consequence (accepted for now):** the dependency is bidirectional. `fls` depends on `sdd` (its
  FLS-specific SDD steps spawn `sdd:sdd-worker` / `sdd:sdd-mechanic`), and `sdd` depends on `fls`
  (the `setup_todo_list` template and `next` dispatch reference FLS-specific steps). We accept this
  coupling in this pass and untangle it later — so `sdd` is not yet fully standalone-portable.

General-dev skills that fit neither `django-stack` nor `fls`: `git-worktree-setup` and
`update-claude-project-settings` **move to `sdd`**; `request-code-review` is **deleted** (no longer
used).

### `fls-content` — course-authoring (relocated)

Moves from the repo root into `claude_plugins/` alongside the rest. Its only coupling to the others is
a one-way, file-copy sync (`/update_claude_plugin_fls_content`), whose hardcoded output paths need
updating for the new location.

## "Update all references" — the load-bearing workstream

The split is a large, mostly-mechanical rename plus real infrastructure and design work. Claude Code
does **no** cross-plugin static validation, so a missed reference fails silently at invoke time. Key
surfaces (full checklist in `research_reference_surface.md`):

- **Launcher:** `claude.sh` (and the generated wrapper template) must load every plugin — one
  `--plugin-dir` per plugin pointed under `claude_plugins/`. This is the single most important change;
  miss it and every cross-plugin reference breaks.
- **Derived namespaced identifiers:** `Skill(fls:*)` → per-plugin globs; `subagent_type` strings
  (`fls:sdd-worker`/`fls:sdd-mechanic` → `sdd:…`, `~30` occurrences across ~20 files);
  `mcp__plugin_fls_playwright__*`; `enabledPlugins` keys; slash-command prefixes.
- **Hardcoded intra-plugin paths:** ~16 literal `fls-claude-plugin/commands/sdd/protected/*.md`
  self-references (not `${CLAUDE_PLUGIN_ROOT}`-based) must be rewritten for the new locations.
- **`${CLAUDE_PLUGIN_ROOT}` is per-plugin** — a hook/MCP/LSP config in one plugin can't reach files in
  another, so shared hook scripts must be physically copied into the owning plugin, not referenced.
- **Agent-memory dirs** (`.claude/agent-memory/fls-code-reviewer/`, `…-qa-data-helper/`) encode the
  plugin name; migrate them (`git mv`) or accumulated memory is orphaned.

## Decisions carried over (from the superseded django-extraction idea)

1. **Extract-and-remove with FLS overlays.** Portable skills leave `fls` and live in `ds`; `fls`
   declares a dependency on `ds` and keeps thin overlay skills for its site-aware layer. No duplicated
   content.
2. **Templates / cotton / partials are separate skills** under `ds`.
3. **Hook split 3-of-4:** `ruff_fix.sh`, `post-edit-bandit.sh`, `security-guard.sh` → `ds`; the
   `uv … pytest` pre-commit runner stays FLS-only (belongs in `.pre-commit-config.yaml`).
4. **Versioning:** rely on git SHA for now; add `version`/release tags later if `ds`/`sdd` get
   external consumers.

## Init & per-plugin config (decided)

Each plugin ships **its own init command** — `/ds:init`, `/fls:init`, `/sdd:init` (and the existing
`/fls-content:init`) — rather than one init that loops over plugins. Each plugin stores its
configuration under **its own directory inside `.claude/`** (`.claude/ds/`, `.claude/fls/`,
`.claude/sdd/`, `.claude/fls-content/`), keeping the **same internal structure** each `.claude/fls/`
uses today (`config.md`, `config.local.md`, `scripts/`, etc.). Today's 8-step `/fls:init` is the
template: split it so each plugin's init merges only its own `enabledPlugins` key + permissions,
writes only its own `.claude/<plugin>/` config, and validates its own plugin path — no shared
single-plugin assumptions.

## Todo template (decided)

The `setup_todo_list` helper moves to `sdd` and its generated `todo.md` keeps all 15 sections,
including the FLS-only ones — we don't build a cross-plugin todo-composition seam now (that's part of
the untangling deferred below). **Every command/skill the generated `todo.md` lists must be written
fully namespaced** so each step names its owning plugin (`/sdd:improve_idea`, `/fls:do_qa`,
`/ds:app_map`, `Skill(ds:testing)`, etc.), rather than bare unprefixed names.

## Directory layout (decided)

Each plugin's commands and skills live **directly at the plugin root — no extra grouping
subdirectory**. The `sdd` plugin uses flat `commands/*.md` (e.g. `sdd-claude-plugin/commands/start.md`,
`…/improve_idea.md`), not `commands/sdd/*.md`: the plugin name already supplies the `sdd` namespace,
so the old `sdd/` folder is redundant. This also settles the namespacing question — a flat `start.md`
in a plugin named `sdd` is invoked as `/sdd:start` unambiguously (no `/fls:sdd:start` double-segment).
The one subdirectory we keep is `commands/protected/` for the read-and-followed helper files, so they
don't register as invocable `/sdd:*` commands.

## Command dispatch in `next.md` (decided)

Fully namespacing the todo lines (above) also resolves how `next.md` finds each command file. Today it
**strips** the prefix (`strip_leading("/sdd:", "/", …)`) and probes two hardcoded
`fls-claude-plugin/commands/` directories — which would guess wrong across three plugins and risk
name collisions. Instead, **keep the prefix and map it to the owning plugin's commands directory**:

- `sdd:` → `claude_plugins/sdd-claude-plugin/commands/`
- `fls:` → `claude_plugins/fls-claude-plugin/commands/`
- `ds:`  → `claude_plugins/django-stack-claude-plugin/commands/`

Deterministic, no probing. The map is a hardcoded within-repo lookup (fine — `${CLAUDE_PLUGIN_ROOT}`
only points at `next.md`'s own plugin, and cross-repo portability is deferred). This is a small
mechanical rewrite of Step 3, not a design problem.

## Deferred (out of scope this pass)

- **Cross-project portability / distribution of `ds`.** The split cleanly *separates* the portable
  content, but actually making `ds` reusable in unrelated repos (each consumer's launcher, or a
  marketplace) is not a goal now. We wire everything via `--plugin-dir` inside this repo only;
  distribution is a later concern.
- **Untangling the `fls` ↔ `sdd` bidirectional dependency** (see the SDD "Consequence" note).

## Session sentinel rename (decided)

The launch sentinel **`$FLS_PLUGIN` is renamed to `$CLAUDE_PLUGINS_LOADED`** — it now proves "the dev
launcher ran and every `claude_plugins/` plugin is loaded," so a plugin-neutral name fits. It stays a
single boolean set by the launcher and checked by the `SessionStart` hook (one launcher loads all
plugins together, so no per-plugin sentinel is needed). **`FLS_PATH` / `__FLS_PATH__` is kept as-is** —
its name is still accurate (it locates the FLS repo/submodule checkout, under which `claude_plugins/`
now lives).

> Migration note for the plan: `init` is additive / skip-existing, so renaming the sentinel means the
> init command must **actively rewrite** the old `$FLS_PLUGIN` name in an existing downstream project's
> `claude.sh` and `.claude/settings.json` `SessionStart` hook (and the root `claude.sh` here) — a
> plain additive merge won't pick up the new name on its own.

## Research

Durable research artifacts next to this file:

- `research_claude_code_multi_plugin.md` — how Claude Code loads/namespaces multiple plugins, cross-plugin references, `${CLAUDE_PLUGIN_ROOT}` scoping, and split gotchas.
- `research_plugin_categorization.md` — complete inventory of all 105 plugin artifacts classified into `ds`/`fls`/`sdd`/ambiguous with FLS-coupling evidence.
- `research_sdd_coupling.md` — how tangled SDD is with FLS, and the file-by-file recommended split (verdict: scoped partial extraction).
- `research_reference_surface.md` — the complete "update all references" checklist across the whole repo.
