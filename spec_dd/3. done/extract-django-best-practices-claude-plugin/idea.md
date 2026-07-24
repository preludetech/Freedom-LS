# Idea: Extract reusable Django stack conventions into a new Claude plugin

> **Superseded** by `spec_dd/2. in progress/split-claude-plugin/1. spec.md`, which splits the monolithic plugin into `ds`/`fls-dev`/`sdd` (the `ds` plugin subsumes this idea's generic Django-stack extraction).

## Problem

The `fls-claude-plugin` directory currently mixes two different concerns:

1. **FLS-specific** conventions (multi-tenant sites, FLS user model, FLS app structure, brand guidelines, registration policy, markdown content models)
2. **Generic Django-stack** conventions that would help on *any* Django project using the same stack (testing, templates, cotton, HTMX, Alpine.js, Tailwind, factory_boy, partials, django-tasks)

Whenever I start a new Django project I want the second group available without dragging in the FLS-specific bits.

## Proposal

Create a new Claude Code plugin in a sibling directory called **`django-constitution-claude-plugin/`**. The plugin manifest will set `name: "dc"` so skills and commands are namespaced as `/dc:tailwind`, `/dc:testing`, etc.

The plugin must:

- Be useful for any Django project using this stack (Python 3.13+, Django 6.x, PostgreSQL, HTMX, TailwindCSS, optional Cotton + Alpine.js + django-tasks).
- Still be useful for FLS itself (FLS plugin will continue to add site-aware overlays on top).
- Include a `/dc:init` command for project-specific bootstrap when paths or feature flags differ between projects (Tailwind input file, apps root, base template, etc.).

## Skills the new plugin should contain

Confirmed in scope by the original idea:

- `dc:testing` — pytest + factory_boy + TDD conventions (stack-generic parts of the current FLS testing skill)
- `dc:templates` — Django templates + Cotton components + partials conventions
- `dc:cotton` — *(possibly merged into `dc:templates`; see open questions)*
- `dc:htmx` — HTMX conventions
- `dc:factory-boy` — factory patterns and best practices
- `dc:partials` — `{% partialdef %}` patterns *(possibly merged into `dc:templates`; see open questions)*
- `dc:django-tasks` — `django-tasks` queue conventions (new content; not currently in FLS)

Likely also in scope (stack-generic content already exists in FLS):

- `dc:tailwind` — frontend styling with Tailwind utilities (renamed from `frontend-styling`)
- `dc:alpine` — Alpine.js CSP-build conventions
- `dc:playwright-tests` — pytest-playwright E2E conventions
- `dc:use-playwright` — exploratory MCP browser usage

Out of scope (stays in `fls-claude-plugin`):

- multi-tenant, registration, markdown-content, admin-interface, icon-usage, brand guidelines.

## Init command — `/dc:init`

Each project may differ in paths and feature flags. The init command should:

- Ask the user about project specifics and write them to `.claude/dc/config.md`.
- Likely inputs: apps root path, base template path, Tailwind input CSS path, Tailwind build command, factories module path, whether the project uses cotton / Alpine.js CSP build / global HTMX CSRF / django-tasks.
- Merge any required permissions / hooks into `.claude/settings.json` (mirroring how `/fls:init` works today).

## Plugin layout

Standard Claude plugin layout (see `research_plugin_architecture.md`):

```
django-constitution-claude-plugin/
  .claude-plugin/plugin.json     # name: "dc"
  commands/init.md
  skills/<skill-name>/SKILL.md
  resources/                     # supporting markdown referenced via ${CLAUDE_PLUGIN_ROOT}
  hooks/hooks.json               # only stack-generic hooks
```

## Research

Background research lives next to this file:

- `research_plugin_architecture.md` — Claude Code plugin manifest, namespacing, init-command pattern.
- `research_existing_skills_portability.md` — per-skill assessment of what is portable vs FLS-specific, init-command inputs, and resource files to move.

## Decisions

1. **Extract-and-remove with overlays for FLS-specific bits** — portable skills are *removed* from `fls-claude-plugin` and live in `dc`. `fls-claude-plugin` declares a dependency on `dc`. Where an extracted skill carried FLS-specific content (e.g. site-aware testing, FLS template conventions, FLS-specific factories), keep a thin overlay skill in `fls-claude-plugin` that references the `dc` skill and adds the FLS-specific layer on top. No duplicated content between the two plugins.
2. **Templates / cotton / partials are separate skills** — `dc:templates`, `dc:cotton`, and `dc:partials` each stand alone. `dc:templates` covers general Django template conventions and refers out to `dc:cotton` and `dc:partials`, including guidance on when to reach for each (and when both apply together).
3. **Scope is Django-stack topics only** — `git-worktree-setup`, `request-code-review`, and `update-claude-project-settings` are deliberately *not* extracted. They stay FLS-only (or move elsewhere later); `dc` is for general Django conventions only.
4. **Hook portability** — three of the four existing FLS hooks move to `dc`, one stays FLS-only:
   - **Move to `dc`:**
     - `ruff_fix.sh` (PostToolUse on Edit|Write) — generic Python autoformatting.
     - `post-edit-bandit.sh` (PostToolUse on Edit|Write) — generic Python security linting.
     - `security-guard.sh` (PreToolUse on Bash|Write|Edit) — its blocklist (raw-SQL escapes, manual HTML safety markers, CSRF-exempt decorators, dynamic-code execution primitives, unsafe deserialization) is exactly the canonical Django footgun set, mirroring the "ORM only / escape by default" conventions taught by `dc`'s skills. Skills teach the convention; the hook enforces it. `dc:init` should expose an opt-out for projects that legitimately need some of these primitives so the hook doesn't fight the user.
   - **Stay FLS-only:**
     - The `git commit` PreToolUse runner (`uv run ruff check . && uv run mypy . && uv run pytest`) — bound to `uv`, to a strict mypy baseline, and to a fast-enough test suite. Idiomatic home for this is `.pre-commit-config.yaml`, not a Claude hook.

5. **Versioning / distribution** — rely on git SHA per commit for now; downstream projects pin to a SHA and update by bumping it. A `version` field in `plugin.json` and proper release tagging can be added later once `dc` has external consumers and a meaningful change cadence.

## Open questions for the spec phase

_None — all open questions resolved._
