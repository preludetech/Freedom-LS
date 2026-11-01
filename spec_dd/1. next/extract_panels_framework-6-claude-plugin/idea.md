# Panel framework: a generic Claude Code plugin

Spec 6 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The package repo (`/home/sheena/workspace/lms/django_apps/panel_framework`, created by spec 5) gains
a generic Claude Code plugin, a developer doc and a release-check script. FLS loads the plugin and
shrinks its own panel guidance to a pointer.

- **The plugin**, `claude_plugins/panel-framework/` in the package repo, with a
  `.claude-plugin/marketplace.json` at the repo root listing it by relative path, so one clone is both
  the package and the marketplace.
- **Skills** describing the framework's API: the entry skill (vocabulary, map of the others, how to
  mount the shipped reference page), defining a panel, tables and filters, actions and bulk actions,
  dialogs and quick view, the host contract, testing panels, and components and templates.
- **Two commands.**
  - `/panel-framework:init` wires a host: checks the package is installed and in `INSTALLED_APPS`,
    creates `.claude/panel-framework/config.md` from a template without overwriting, runs the
    package's host-contract system checks (from spec 4) and reports what is outstanding, and adds the
    `enabledPlugins` key. It merges and never replaces, writes nothing before its checks pass, and
    does not scaffold a host project.
  - `/panel-framework:update` bumps the tag in the host's `pyproject.toml`, runs `uv lock`, reads the
    `CHANGELOG.md` entries between the old and new tags, runs the steps the flags ask for, runs the
    host's tests and commits. When the host loads the plugin through a marketplace it also moves the
    `ref` in `extraKnownMarketplaces` to the new tag.
- **Per-project config**, `.claude/panel-framework/config.md` (committed) and `config.local.md`
  (gitignored: the local path to the package repo for the editable install).
- **The developer doc**, written once, in the package repo.
- **A consumer-suite script** in the package repo. It reads a gitignored list of consumer paths and
  runs each consumer's panel-related tests against the package's working copy before a tag is cut.
- **FLS side.**
  - `claude.sh` gains a `--plugin-dir` line for the plugin in the package checkout.
  - `claude_plugins/fls-dev` drops its generic panel content: the `appModal` and `quickView` detail
    rows in `skills/alpine-js/SKILL.md`, and the generic double-import hazard and stub-panel text in
    `skills/testing/SKILL.md`. Each leaves a pointer to the plugin.
  - `fls-dev` gains a thin skill with the FLS-specific section conventions: organisation scope,
    `role_based_permissions` hooks, audit-log events and glossary wording. It names `panel-framework`
    skills and does not restate them.
  - `.claude/agent-memory/ds-code-reviewer/project_panel_framework.md` and its line in `MEMORY.md`
    are removed, or rewritten as a pointer if the reviewer still needs one. Anything generic in it is
    checked against the code and folded into the plugin first.
  - First-Class's install route for the plugin goes into FLS's upgrade notes.

## Why

Today the panel framework is documented only by its code and the educator-interface specs. There is no
README, no docs page and no skill describing the API. The only panel guidance elsewhere is generic
text inside FLS skills, one agent-memory note and a promised `fls-dev` skill that was never written.
Once the framework is its own package used by a second project, an agent in either project that builds
a section needs the contract in front of it instead of guessing from the educator interface. The
guidance has to ship with the package so its version matches the code, and it has to be generic so the
other project can use it. Writing the doc and the skills once, in the package, stops the three places
(spec 12, `fls-dev`, the package) from drifting apart. First-Class today gets plugins only because the
whole FLS tree is a submodule; the plugin leaves that tree, so that project needs an explicit route.

## What is settled

- **Where the plugin lives and how it is found.** In the package repo at
  `claude_plugins/panel-framework/`, with `.claude-plugin/marketplace.json` at the repo root. Plugin
  `name` and marketplace entry `name` are both `panel-framework`. Skills run as
  `/panel-framework:<skill>`.
- **Install routes.** FLS and its concrete projects on a dev machine use `--plugin-dir` in `claude.sh`
  (the practice every FLS plugin uses today: no marketplace, no trust dialog). A project without that
  convention, and CI, use a `github` marketplace source in `extraKnownMarketplaces` pinned by `ref` to
  the same tag as the Python dependency, plus `enabledPlugins`, plus a one-time
  `claude plugin install panel-framework@panel-framework --scope project` per contributor.
- **Version.** The plugin's `plugin.json` version equals the package tag and is bumped by the same
  release step that tags.
- **Generic, absolutely.** The plugin never contains an FLS name, path or value: not `freedom_ls`,
  `educator_interface`, `learner_management`, organisation, cohort or learner. Project values reach it
  only through `.claude/panel-framework/config.md`. Imports are written in their final form
  (`panel_framework...`). A test or check in the package repo greps the plugin directory for FLS words.
- **Skill set** is the eight listed under "What". `testing-panels` is written for pytest and
  pytest-django and leaves a host's own test rules to a host skill named in the config. It covers stub
  models, stub panels, `tests/root_urls.py`, session-scoped table creation, the double-import hazard
  (the URL resolver loads `stub_panels.py` under another module path, so `apps.get_model` runs at call
  time) and Playwright against the reference page. `host-contract` mirrors spec 4's system checks.
  `components-and-templates` points at the shipped reference page rather than copying it.
- **Config keys, kept minimal:** section modules, test command and how to select panel-related tests,
  page-shell component and base template, the host's icon-set doc, related host skills by name (how a
  generic plugin points at FLS without naming it), and package source (`path` or `tag`) so `update`
  knows its mode. `config.local.md` holds the local package path.
- **`update` reads the changelog flags** `requires_migrations`, `requires_template_review` with
  `changed_template_paths`, `requires_settings_change` and `requires_tailwind_rebuild`, and relies on
  the deprecation rule (a breaking change keeps the old surface, with a warning, for one tag).
  Spec 5 creates the first tag and `CHANGELOG.md`; this spec only reads them.
- **Plugin conventions** come from `sdd:claude-code-authoring`: reusable logic in skills, deeper
  reading in `resources/`, and a command from another plugin invoked through the `Skill` tool, never
  read by path. An FLS command that wants `update` calls it that way.
- **Rejected, not built:** a `/panel-framework:new_panel` scaffolder, and a consumer-test-runner
  command (that is the script).
- **The consumer-suite script** lives in the package repo (for example `scripts/`), reads a gitignored
  list of consumer paths, and relies on the editable install so it needs no pointer moving. It is the
  small counterpart of FLS's concrete-project update flow.
- **Spec 12 hands over.** `educator-interface-12-docs-and-polish` no longer writes the developer doc
  or the `fls-dev` panel skill; it keeps the `alpine-js` inventory fix. This spec writes both
  once, in the package. FLS's `docs/product/educator-interface.md` links to the package doc.
- **What `fls-dev` keeps:** the domain glossary verbs and nouns (`bulk_action`, deactivate,
  reactivate, remove, unregister), FLS's test-organisation rules (what a sanctioned test-only module
  is, `_panel_test_tables` as the example of the DB-unblock rule), and `alpine-js` rows for FLS-only
  components. Everything that explains how panels, tables or bulk actions work leaves.
- **FLS's own config.** FLS gets `.claude/panel-framework/config.md` with its values (section modules
  under `educator_interface` and `learner_management`, icon backend, page-shell names, FLS test
  command), written by running `/panel-framework:init` in FLS.
- **Upgrade notes** for FLS (`fls-dev:update_upgrade_notes`) cover the First-Class route: a new
  `--plugin-dir` line in First-Class's `claude.sh` pointing at the package clone, or the marketplace
  route above for a setup without sibling clones.

## Open until the spec

- **Where the developer doc lives in the package repo.** Recommended default: a single file
  `docs/panel-framework.md`, linked from `README.md`, with no links out to anything outside the repo.
  The skills and the `init` output point at it by repo-relative path. The spec may pick another
  location if the repo layout from spec 5 argues for it.
- The name of the thin `fls-dev` skill (research suggested `educator-sections`).
- How the FLS-word check on the plugin directory runs (a pytest invariant in the package or a script
  beside the consumer-suite script).
- Whether `update` supports a `path` package source or only a tag source.
- How the consumer-suite script selects "panel-related" tests in each consumer: a marker, a path
  pattern, or a command read from the consumer's own `.claude/panel-framework/config.md`.
- Whether the memory note holds anything not already in the code and the new skills; if not, it is
  deleted rather than rewritten.

## Out of scope

- A scaffolder or generator for host projects or panels.
- A second marketplace repo, or bundling plugins from other repos.
- Per-spec commits, rollback scripts or preview matrices for `update`; one package and a few hosts do
  not need them.
- Changing framework code, templates or the changelog format (specs 1 to 5), beyond what the script and
  checks need.
- Rewriting FLS's product doc `docs/product/educator-interface.md` (spec 12) beyond a link to the
  package doc, or the `alpine-js` inventory correction (spec 12).
- Support in `fls-dev:update_concrete_projects` or `concrete:update_fls` for a second plugin source.
- PyPI publishing and a shared core package.

## Resources

- Research moved in: `spec_dd/1. next/extract_panels_framework/research_plugin_distribution.md`
  (guidance inventory, spec 12 split, marketplace behaviour and source shapes, proposed skills, config,
  what `fls-dev` keeps and drops).
- Parent research: `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md`
  (the `update` command, the consumer-suite script, the deprecation rule, changelog flags). Its
  `uv.toml` and app-label claims are superseded by the cut.
- Parent idea: `spec_dd/1. next/extract_panels_framework/idea.md`.
- Spec 12 idea (the paragraphs that move here): `spec_dd/1. next/educator-interface-12-docs-and-polish/idea.md`.
- Existing FLS guidance to trim: `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`,
  `claude_plugins/fls-dev/skills/testing/SKILL.md`, `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`,
  `.claude/agent-memory/ds-code-reviewer/project_panel_framework.md`.
- Conventions: skill `sdd:claude-code-authoring` (`claude_plugins/sdd/skills/claude-code-authoring`),
  `claude_plugins/fls-dev/skills/init` as the model for `init` rules, `CLAUDE.md` "Plugins" section.
- Claude Code docs: https://code.claude.com/docs/en/plugin-marketplaces,
  https://code.claude.com/docs/en/plugins/org.md,
  https://code.claude.com/docs/en/plugins/marketplace-reference.md.
- Downstream: First-Class at `/home/sheena/workspace/first_class/First-Class-LMS.git/main` (its
  `claude.sh` and `.claude/settings.json`).
