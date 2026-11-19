# Semantic icons: a generic Claude Code plugin

Spec 4 of 4 in the Semantic icons extraction effort. Read the "Semantic icons extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The package repo (`/home/sheena/workspace/lms/django_apps/semantic_icons`, published as
`django-semantic-icons`, created by `extract-semantic-icons-app-3-package-and-install`) gains a generic
Claude Code plugin and a host-facing developer doc. FLS loads the plugin and `fls-dev:icon-usage`
shrinks to FLS specifics plus a pointer.

- **The plugin**, `claude_plugins/semantic-icons/` in the package repo, with a
  `.claude-plugin/marketplace.json` at the repo root listing it by relative path, so one clone is
  both the package and the marketplace. Layout, marketplace entry and install route follow whatever
  `extract_panels_framework-6-claude-plugin` settled.
- **One skill**, `semantic-icons`, taken from the current `fls-dev:icon-usage` and made generic. It
  covers:
  - choosing a semantic name (where the list lives in the package, how host-added names layer on top);
  - rendering with `<c-icon>` (static `name`, `:name` from a variable, `variant`, `class` replacing
    the default size);
  - sizing guidance phrased generically (a scale by kind of use, not by named FLS components);
  - accessibility (decorative by default, `aria_label` for a meaning-bearing icon, the label on the
    control for icon-only buttons, the `data-icon` attribute for tests);
  - toggling with Alpine (`x-show` on wrapper spans, rotating a wrapper);
  - host configuration: switching the icon set, overriding a name within the set, pointing a name at
    the host's own SVG, registering a custom icon set, adding semantic names, the registry API for
    reusable apps, and the custom backend (with the `data-icon` contract and test cache clearing).
  Configuration and backend detail sit in `resources/`, as today. The skill describes the features
  delivered by `extract-semantic-icons-app-1-standalone-app` and `extract-semantic-icons-app-2-host-icons`,
  under their `SEMANTIC_ICONS_*` settings and `semantic_icons` imports.
- **The host developer doc**, written once, in the package repo, covering the same ground for a
  human reading it cold. The package `README.md` links it.
- **FLS side.**
  - `claude.sh` gains a `--plugin-dir` line for the plugin in the package checkout.
  - `claude_plugins/fls-dev/skills/icon-usage/` shrinks to FLS specifics: FLS's active icon set and
    settings values, FLS-only conventions (including FLS-domain semantic names and how FLS adds
    names), and size choices tied to FLS components. It points at the `semantic-icons` skill for
    everything generic and does not restate it. The generic `resources/configuring-icons.md` and
    `resources/custom-icon-backend.md` leave, with anything FLS-specific in them kept in the slimmed
    skill.
  - First-Class's install route for the plugin goes into FLS's upgrade notes.

## Why

The icon guidance exists only inside FLS: `fls-dev:icon-usage` names `freedom_ls.icons`,
`FREEDOM_LS_ICON_*` and an "edit package code to add a name" workflow, all of which the extraction
removes or renames. Once the app is its own package used by a second project, an agent in either
project needs guidance that matches the installed version and names the real settings and imports.
The guidance has to ship with the package so its version matches the code, and it has to be generic
so any host can use it. Writing it once in the package stops it drifting from the FLS copy, and
splitting the FLS-only parts out keeps the CLAUDE.md "Plugins" rule intact. First-Class gets plugins
today only because the whole FLS tree is a submodule; the plugin leaves that tree, so that project
needs an explicit route.

## What is settled

- **Where the plugin lives.** In the `django-semantic-icons` repo at `claude_plugins/semantic-icons/`,
  with `.claude-plugin/marketplace.json` at the repo root. Plugin `name` and marketplace entry `name`
  are both `semantic-icons`. The skill runs as `/semantic-icons:semantic-icons` unless the layout
  settled by `extract_panels_framework-6-claude-plugin` argues otherwise.
- **Follows the panel plugin spec.** Install routes (`--plugin-dir` in `claude.sh` for FLS and its
  concrete projects; a `github` marketplace source pinned by `ref` plus `enabledPlugins` for a project
  without that convention and for CI), version handling (plugin version equals the package tag, bumped
  by the release step), the generic-content check, the pointer pattern in `fls-dev`, and the
  `sdd:claude-code-authoring` conventions all follow whatever
  `extract_panels_framework-6-claude-plugin` settled. Where that spec leaves a choice open, this spec
  takes the same answer.
- **Generic, absolutely.** The plugin and doc never contain an FLS name, path or value: not
  `freedom_ls`, `FREEDOM_LS_ICON_*`, course, cohort, learner, organisation or an FLS component name.
  Imports and settings are written in their final form (`semantic_icons`, `SEMANTIC_ICONS_*`). Project
  values reach the plugin only through per-project config, if the panel plugin's settled pattern
  gives it one.
- **FLS specifics stay in `fls-dev`.** The 63 shipped names include FLS-domain ones; the generic
  skill describes the mechanism and points at the package's name list rather than copying names tied
  to FLS concepts. Which set FLS runs, FLS-only conventions and sizes tied to FLS components live in
  the slimmed `fls-dev:icon-usage`.
- **Docs only.** No code changes to the package beyond docs and plugin files.
- **The package README links the doc.** The doc has no links out to anything outside the repo.
- **Unchanged contract.** `<c-icon>` and its arguments do not change, so no template edits anywhere.
- **Upgrade notes** for FLS (`fls-dev:update_upgrade_notes`) cover the First-Class route: a new
  `--plugin-dir` line in First-Class's `claude.sh` pointing at the package clone, or the marketplace
  route for a setup without sibling clones.
- **Out of the plugin:** no commands. The panel plugin's init and update commands are not repeated
  here unless `extract_panels_framework-6-claude-plugin` settled that every package plugin carries
  them.

## Open until the spec

- Where the developer doc lives in the package repo (default: a single file `docs/semantic-icons.md`,
  linked from `README.md`), following the location pattern the panel package uses.
- Whether one skill with `resources/` suffices or the size warrants splitting configuration and
  backend into a second skill.
- The exact generic size scale, and which FLS component-tied sizes move to the slimmed skill.
- How the FLS-word check on the plugin directory runs, following the panel package's choice.
- Whether the plugin reads a per-project config file at all, or the skill is config-free.
- Whether `fls-dev` references to the old skill's resource files (for example
  `claude_plugins/fls-dev/resources/testing.md` pinning the icon set) need edits beyond renamed
  settings.

## Out of scope

- Changing package code, templates, the settings or the registry API (specs before this one).
- New commands, scaffolders or an icon picker.
- A second marketplace repo or bundling plugins from other repos.
- Rewriting FLS's product doc `docs/product/configuration-and-extension.md` beyond a link to the
  package doc, if it needs one.
- PyPI publishing.

## Resources

- Research: `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md` (section 8, docs and
  skills; items 8 and 18).
- Analogous idea: `spec_dd/1. next/extract_panels_framework-6-claude-plugin/idea.md`.
- Skill to split: `claude_plugins/fls-dev/skills/icon-usage/` (`SKILL.md`,
  `resources/configuring-icons.md`, `resources/custom-icon-backend.md`).
- Conventions: skill `sdd:claude-code-authoring` (`claude_plugins/sdd/skills/claude-code-authoring`),
  `CLAUDE.md` "Plugins" section.
- Claude Code docs: https://code.claude.com/docs/en/plugin-marketplaces.
- Downstream: First-Class at `/home/sheena/workspace/first_class/First-Class-LMS.git/main` (its
  `claude.sh` and `.claude/settings.json`).
