# Research: the panel framework plugin, where it lives, how projects install it

## Summary

- There is almost no panel guidance to extract today. The framework's knowledge lives in code, one
  reference page, one agent-memory note, and scattered cross-references in `fls-dev` skills. The
  plugin is therefore mostly **new writing**, not a move. Educator-interface spec 12 is the only spec
  that promises the docs and skill, and it should hand the skill to the plugin effort.
- The plugin should live **in the panel framework repo** (`claude_plugins/panel-framework/`, as the
  packaging research already says), be a **generic plugin** (no FLS names), and be installed by every
  consumer through a **git marketplace** (or a `--plugin-dir` line in `claude.sh` on dev machines,
  which is what all current FLS plugins use).
- The plugin **can be written first, inside FLS's `claude_plugins/`**, and moved with the code. It
  should not be, if spec 12 is to be kept small: write it in the new repo layout from day one, in an
  FLS-resident directory, then `git mv` it. Details in section 5.

## 1. Inventory of existing panel guidance

Searched `claude_plugins/`, `.claude/`, `docs/`, `freedom_ls/panel_framework`, `README.md`, and the
First-Class checkout.

| Path | What it says | Classification |
| --- | --- | --- |
| `freedom_ls/panel_framework/reference.py`, `templates/panel_framework/reference/component_reference.html` and `_examples.html`, `tests/test_reference.py` | A DEBUG-only (`staff_member_required`) living reference page: every `c-panel-*` / `c-data-table*` component in every state, with static example data. Test at `tests/test_reference.py`. | Generic framework knowledge. Ships with the package. Extends `_base.html`, which the packaging research makes a setting. The plugin's component-inventory skill should point at it rather than copy it. |
| `.claude/agent-memory/ds-code-reviewer/project_panel_framework.md` (+ index line in `MEMORY.md`) | `panel_framework_view` dispatches HTMX vs full page, OOB fragment assembly, `HX-Target == "main-content"`, Alpine registration. | Generic content, wrong home: it is agent memory for one reviewer in one checkout. Fold into the plugin's architecture skill, then delete. (Note: it may describe the pre-rebuild API; spec 1 of the rebuild reworked panels/tabs/actions, so verify against code before reusing.) |
| `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` lines 20-21 | Component inventory rows for `appModal` (`partials/modal_host.html`) and `quickView` (`partials/quick_view_host.html`) from `panel_framework/.../alpine-components.js`. | Generic framework facts inside an FLS skill. Move the two rows' detail to the plugin; `alpine-js` keeps a one-line pointer. Spec 12 says this skill's inventory is already wrong ("lists one that does not exist"). |
| `claude_plugins/fls-dev/skills/testing/SKILL.md` lines 21, 57-75 | `panel_framework/tests/root_urls.py` and `stub_panels.py` as sanctioned test-only modules; the double-import hazard (URL resolver loads `stub_panels.py` under another module path, so `apps.get_model` at call time); `_panel_test_tables` in `panel_framework/tests/conftest.py` as the worked example of session-scoped table creation with the DB unblock. | Mixed. The stub-model and double-import guidance is generic "how to test panels" and moves to the plugin's testing skill. The pointers to FLS's test-organisation rules (what is a sanctioned test module, the DB-unblock mechanism) stay in `fls-dev:testing`. |
| `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` line 181 | Verb vocabulary for event names: `bulk_action` is a noun in the list of event nouns (deactivate, reactivate, remove, unregister). | FLS-specific (product vocabulary). Stays in `fls-dev`. |
| `claude_plugins/django-stack/skills/htmx/SKILL.md` line 41-44 | `render_to_string()` for "panel systems that assemble multiple partials". | Generic, not about this framework. Leave. |
| `claude_plugins/django-stack/resources/alpine_*.md` | `expandablePanel` examples. | Unrelated (a different "panel"). Leave. |
| `claude_plugins/sdd/commands/do_qa.md`, `sdd/agents/qa-bugfixer.md`, `sdd/resources/roadmap_format.md` | QA heuristics mention drawers and sidebars; the roadmap-format example uses `educator-interface-1-panel-framework-core`. | Unrelated or example text. Leave. |
| `docs/product/educator-interface.md` | Product behaviour: single-page HTMX panel, sections, quick view, bulk actions (section "Bulk actions" line 65), screenshots. | FLS product doc. Educator-facing behaviour, not framework API. Stays in FLS. Spec 12 rewrites it. |
| `docs/app_structure.md` | Dependency graph: `panel_framework --> accounts, base, site_aware_models`; who depends on it. | FLS-specific, generated (`/ds:app_map`). Drops `panel_framework` after extraction. |
| `docs/product/configuration-and-extension.md`, `docs/how tos/theme-fls.md`, `learner-experience.md`, `admin-interface.md`, `notifications.md` | Incidental "panel" mentions (UI regions, theme overrides). | Not about the framework. Theme how-to may need a line on overriding `panel_framework/...` templates. |
| `claude_plugins/fls-dev/resources/templates_and_cotton.md` | Referenced by CLAUDE.md for HTMX conventions (422 for validation errors). No panel text found. | Generic HTMX/cotton convention; stays. The plugin links to it conceptually, not by path (a generic plugin cannot cite an FLS path). |
| `spec_dd/1. next/roadmap.md` lines 52-110 | The educator-interface rebuild effort; source of the "complete, self-contained and powerful" goal. | Planning, not guidance. |
| Specs 1-11 of the educator-interface effort | Each documents its own change (per spec 12). | Per-spec design record. Raw material for the plugin skills, but not guidance. |

Not found: any README, any `docs/` page, or any skill that documents the panel API (defining a
panel, tabs, tables, filters, actions, bulk actions, permission hooks, URL state, host contract).
The only complete description of the API is the code and the educator-interface specs.

## 2. Educator-interface spec 12: what it promises and the overlap

`spec_dd/1. next/educator-interface-12-docs-and-polish/idea.md` promises, for the panel framework:

1. **Developer doc**: `docs/product/panel-framework.md` (or `docs/how tos/`). Contents: what a
   section is, the three view kinds, panels and tabs and their binding, actions, tables with filters
   and selection, the modal and the quick view, the permission hooks, URL state, the cotton
   components, how a downstream project registers a section and overrides a template, one worked
   example. Audience: a Django developer who has not seen the code.
2. **An `fls-dev` skill**: `claude_plugins/fls-dev/skills/panel-framework/`, "so an agent building a
   section reads the contract instead of guessing from the educator interface", same shape as
   existing skills.
3. **Correct the `alpine-js` skill's component inventory** to what is registered.

It also promises non-framework work (product doc rewrite, polish pass, consistency pass,
consolidated upgrade notes, deletions, Playwright suites) which is unaffected.

**Overlap.** Promise 2 is exactly the plugin's core, but in the wrong place: a skill in `fls-dev`
carrying generic framework knowledge, which the new repo must then reproduce. Promise 1 overlaps
too: after extraction the developer doc belongs in the package repo (it is the package's README /
`docs/`), not in FLS's `docs/product/` (which is product behaviour). Promise 3 stays in FLS.

**Proposed split.**

| Item | Where it lands |
| --- | --- |
| Developer doc (promise 1) | Written in spec 12 **as the package-ready doc**, but in a location that moves cleanly: a single file, `freedom_ls/panel_framework/docs/panel-framework.md`, with no links out to `docs/product/`. It moves with the directory. FLS's `docs/product/educator-interface.md` links to the package's doc after extraction. (Alternative: leave spec 12 with only an FLS product-level "how educator sections are built" note and let the extraction effort write the developer doc. Not recommended: it makes spec 12 deliver "document the panel framework" with nothing.) |
| Skill content (promise 2) | **Moves to the plugin effort** as the generic `panel-framework` plugin, not `fls-dev/skills/panel-framework`. Spec 12 does not write an `fls-dev` skill; it writes at most the FLS-specific slice (below) and points at the plugin. |
| `alpine-js` inventory correction (promise 3) | Stays in spec 12 (FLS skill). Rows for `appModal` and `quickView` shrink to a pointer once the plugin exists. |
| Polish, consistency, product doc, upgrade notes, deletions | Stay in spec 12. Add: "the developer doc and the plugin skills are consistent with the code after the polish pass" as the sequencing reason. |
| Agent-memory note `project_panel_framework.md` | Spec 12's "agent memory notes" deletion pass folds it into the plugin architecture skill. |

Sequencing: roadmap marks 12 as depending on 8, 10 and 11; the extraction's step 1 (complete the
framework) overlaps with those. The cleanest order is: 12 (doc + polish, FLS-resident), extraction
step 1-2 (sever, move), plugin written from spec 12's doc and the specs. If extraction must start
earlier, the plugin author writes the doc and spec 12 drops promises 1 and 2 outright. Either way
the doc must be written once.

## 3. How the existing plugins are structured and installed

**Structure.** Six plugins under `claude_plugins/`: `django-stack` (`ds`), `fls-dev`, `fls-content`,
`sdd`, `productivity`, `turn-progress`. Each has `.claude-plugin/plugin.json` (e.g.
`fls-dev`: `{"name": "fls-dev", "version": "1.0.0", "description": "..."}`), `skills/`, `commands/`,
`resources/`, `scripts/`, `templates/` (wrapper scripts, `config.md`, `config.local.md`).

**No marketplace.** No `marketplace.json` exists in the repo or under `/home/sheena/workspace`
(search of the repo; the wider workspace search timed out). `.claude/settings.json` has
`enabledPlugins` (`ds`, `fls-dev`, `sdd`, `productivity`: bare names, no `@marketplace`) and **no
`extraKnownMarketplaces`**. Plugins are loaded by `claude.sh`, generated by `/ds:init`, which passes
`--plugin-dir` for each plugin and sets `CLAUDE_CODE_PLUGINS_LOADED=1`; a SessionStart hook in
`.claude/settings.json` blocks the session if it is not set.

**Per-project config.** Each plugin has `/<plugin>:init` that merges into `.claude/settings.json`
(allow-list entries, `enabledPlugins` key), creates `.claude/<plugin>/config.md` and
`config.local.md` from `templates/`, installs wrapper scripts into `.claude/<plugin>/scripts/` (only
when absent), and appends its `--plugin-dir` line to `claude.sh`. `fls-dev:init` documents hard
requirements: merge, never replace; never overwrite existing config; never force-delete; nothing is
written before a Step 0 that can abort.

**First-Class.** `.gitmodules` has `submodules/Freedom-LS`. First-Class's `claude.sh` sets
`PLUGINS_ROOT="submodules/Freedom-LS"` and passes `--plugin-dir
"$SCRIPT_DIR/$PLUGINS_ROOT/claude_plugins/<plugin>"` for `django-stack`, `fls-dev`, `sdd`. Its
`.claude/settings.json` allows scripts at `submodules/Freedom-LS/claude_plugins/sdd/scripts/...`. It
has its own `.claude/{ds,fls-dev,sdd}/config.md`. So the plugins reach First-Class **only because the
whole FLS tree is a submodule**. After extraction, First-Class gets the panel package transitively
through `freedom_ls`, but its plugin does **not** come with it: the plugin lives in a different repo
and is not under the FLS submodule.

**Plugin conventions** (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md`): skills over
slash commands for reusable logic (subagents cannot invoke slash commands); per-agent `model:`
frontmatter is the tiering knob; a command inlined into another keeps the caller's model and its
own frontmatter is inert; a hook from **another plugin** must be invoked with the `Skill` tool, never
read by path, because `${CLAUDE_PLUGIN_ROOT}` would resolve to the caller's plugin. Directly
relevant: `/panel-framework:update` called from an FLS command must be a Skill-tool call.

**Current Claude Code docs (marketplaces).** A marketplace is a directory or repo with
`.claude-plugin/marketplace.json` (`name`, `owner`, `plugins[]`), each plugin with a `name` and a
`source`. Source types: relative path (`"./plugins/x"`, must not contain `..`, resolved from the
marketplace root), `github` (`{"source":"github","repo":"org/x"}`), `git-subdir`
(`{"source":"git-subdir","url":"org/monorepo","path":"tools/x"}`), `url`, `archive`, `npm`,
`command`; git sources can pin `ref` or `sha`. Entry `name` must equal the manifest `name`.
Registering a marketplace: `claude plugin marketplace add <path|owner/repo|git-url>` or
`/plugin marketplace add`; install with `claude plugin install <plugin>@<marketplace>
[--scope project]`. Local directory marketplaces read plugin files directly, so edits apply at the
next session start or `/reload-plugins`, with no version bump.

**Project-level declaration** in `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "panel-framework": {
      "source": { "source": "github", "repo": "org/django-panel-framework" }
    }
  },
  "enabledPlugins": { "panel-framework@panel-framework": true }
}
```

Behaviour that matters: `extraKnownMarketplaces` in a repo's settings applies only in a **trusted**
folder (silent otherwise); `enabledPlugins` applies at session start. A plugin listed by **relative
path** inside the marketplace loads once the marketplace is registered. A plugin pointing at an
external source "doesn't install from the repository's settings alone": each contributor runs
`claude plugin install <name>@<marketplace> --scope project` once. A `directory`/`file` source with a
relative path resolves against the repository's **main checkout**, so all git worktrees share one
location (convenient for the FLS worktree workflow). Git-based marketplaces clone with the user's own
git credentials, so a private repo works for anyone with read access; in CI a credential helper or
token is needed. A git marketplace fetches only the submodules that hold plugin files (Claude Code
2.1.295+).

**Consequence for this repo.** A marketplace file at the **root of the panel package repo** listing
`{"name": "panel-framework", "source": "./claude_plugins/panel-framework"}` makes the package repo
both the pip/uv package and the plugin marketplace, from one clone. Then:

- *Dev machine, local clone:* `claude plugin marketplace add
  /home/sheena/workspace/lms/django_apps/panel_framework` (user scope), or a project `directory`
  source. Edits are live at next session / `/reload-plugins`.
- *Anyone else:* `github`/`git` source in `extraKnownMarketplaces`, pinned by `ref` to the same tag
  as the Python dependency so skills match the installed code.
- *Compatibility with how FLS works today:* add a `--plugin-dir
  ".../django_apps/panel_framework/claude_plugins/panel-framework"` line to `claude.sh`
  (the established mechanism). It needs no marketplace and no trust dialog; it is the most
  consistent choice for FLS and First-Class on dev machines. The marketplace route is for the new
  project and for CI.

References:

- https://code.claude.com/docs/en/plugin-marketplaces
- https://code.claude.com/docs/en/plugins/org.md (repo-level `extraKnownMarketplaces`, relative
  paths, trusted folders, project install scope)
- https://code.claude.com/docs/en/plugins/marketplace-reference.md (source shapes, `ref`/`sha`)
- https://code.claude.com/docs/en/plugins/host-marketplace.md (updates and versioning)

## 4. Proposed plugin contents

**Name:** `panel-framework` (plugin `name` = marketplace entry name; skills run as
`/panel-framework:<skill>`). Lives at `claude_plugins/panel-framework/` in the package repo.
Generic: never mentions FLS, `freedom_ls`, educator, learner, cohort, organisation.

### Skills (conventions from `claude-code-authoring`: one SKILL.md per topic, deeper reading in `resources/`)

| Skill | Content |
| --- | --- |
| `panel-framework` (entry) | What the framework is, when to use it, the vocabulary (section, the three view kinds, panel, tab, action), a map of the other skills, the shipped reference page URL and how to mount it. |
| `defining-a-panel` | Sections, panels, tabs, their binding, URL state, permission hooks, registering a section from a host app. One worked example. |
| `tables-and-filters` | The table layer: columns, `field_display`, filters, selection, pagination, CSV export (formula escaping), `c-data-table*` components. |
| `actions-and-bulk-actions` | Row and page actions, bulk actions, "everything matching the filter" selection, `BulkActionRun`, run records, tasks, events. |
| `dialogs-and-quick-view` | `c-modal-*`, the native `<dialog>` host (`appModal`), the quick-view drawer (`quickView`), 422 re-render and focus, close events, triggers. |
| `host-contract` | What a host must provide: `c-icon` and the seven semantic icon names, page-shell cotton component, base template setting, site-resolution callable, `AppSettings`, tailwind `@source` command, `django.contrib.sites`. Mirrors the system checks. |
| `testing-panels` | Stub models, stub panels, `root_urls.py`, session-scoped table creation, the double-import hazard, Playwright against the reference page. Written generically (pytest + pytest-django), with project test rules left to the host's own plugin. |
| `components-and-templates` | The cotton/template-tag inventory, theme overrides by `panel_framework/...` template path, Tailwind rebuild trigger. |

### Commands

Only two, matching the packaging research's "one update command"; keep the surface small.

- `/panel-framework:init`: wire a host. Steps: check the package is installed and in
  `INSTALLED_APPS`; create `.claude/panel-framework/config.md` from `templates/config.md` (never
  overwrite); run the package's host-contract system checks and report outstanding items (missing
  `c-icon` names, page shell, tailwind `@source` command, site resolver); add the plugin's
  `enabledPlugins` key. Follows the `fls-dev:init` rules: merge don't replace, nothing written
  before the checks, nothing force-deleted. Does **not** scaffold a host project.
- `/panel-framework:update`: as already specified in the packaging research (bump tag in
  `pyproject.toml`, `uv lock`, read `CHANGELOG.md` between tags, run flagged steps, run the host's
  tests, commit). Reads the changelog flags (`requires_migrations`,
  `requires_template_review` + `changed_template_paths`, `requires_settings_change`,
  `requires_tailwind_rebuild`). Must also bump the plugin pin so skills match the installed code
  (for a git marketplace pinned by `ref`, update the `ref` in `extraKnownMarketplaces`).

Rejected: a `/panel-framework:new_panel` scaffolder (CLAUDE.md: do not build what is not asked); a
consumer-test-runner command (that is a script in the package repo, per the packaging research).

### Config (`.claude/panel-framework/config.md`, `config.local.md`)

Per-project values only, read by the skills and commands. Candidate keys (keep minimal):

- host app(s) where sections are registered (`Section modules`),
- test command and how to select panel-related tests (`Test command`),
- page-shell component name and base template (mirrors the host's settings),
- the host's own icon-set doc, and the host's own plugin skills to cross-reference by name
  (`Related skills`, e.g. host testing and glossary skills). This is how a generic plugin points at
  FLS without naming it.
- `Package source` (`path` or `git tag`) so `update` knows which mode applies.

`config.local.md` (gitignored): the local path to the package repo for the editable install.

### What `fls-dev` keeps vs drops

| Keeps (FLS-specific) | Drops or reduces to a pointer |
| --- | --- |
| Domain glossary verbs/nouns (`bulk_action`, deactivate/reactivate/remove/unregister) | Any description of how panels, tables, bulk actions work |
| FLS test-organisation rules: what a sanctioned test-only module is, `_panel_test_tables` as the FLS example of the DB-unblock rule | The generic double-import hazard text and stub-panel how-to (moves to `testing-panels`) |
| `alpine-js` inventory row for FLS-only components | `appModal` / `quickView` detail rows (pointer to plugin; spec 12 fixes the incorrect row) |
| FLS's `.claude/panel-framework/config.md` values (section modules under `educator_interface`, `learner_management`, icon backend `freedom_ls.icons`, `_base.html`/`c-page` names, FLS test command) | The planned `fls-dev/skills/panel-framework/` (never created) |
| An optional thin `fls-dev` skill "educator-sections" that covers the FLS-specific section conventions (organisation scope, `role_based_permissions` hooks, audit-log events, domain glossary wording) and references `panel-framework:*` by name | Agent-memory note `project_panel_framework.md` (folded into the plugin, then deleted) |

The thin FLS skill is the only thing spec 12 should author inside `fls-dev`; it does not restate the
contract.

## 5. Can the plugin be written before the code moves?

Yes, and it should be. Constraints:

- **The plugin must be correct against the final API, not the in-flight one.** Skills describe
  imports (`panel_framework.panels`, not `freedom_ls.panel_framework.panels`), the template
  namespace, settings names and host-contract hooks. Imports and hooks change in step 1 of the
  extraction (severing couplings) and the import prefix changes in step 2. Writing the skills before
  step 1 means writing against code that will move. Writing after step 1 and before step 2 is safe:
  the API is final, only the import prefix is renamed.
- **Where to write it before the move.** `claude_plugins/panel-framework/` in the FLS tree,
  loaded by one extra `--plugin-dir` line in `claude.sh`. This is allowed by CLAUDE.md: it is a
  generic plugin, so no FLS name goes in it; FLS values live in `.claude/panel-framework/config.md`
  and `fls-dev`. A per-plugin FLS directory also keeps `/ds:init` and the plugin-checking tools
  working with no special case.
- **Write imports in the final form** (`panel_framework....`) from day one, with a note in the
  config that before extraction the prefix is `freedom_ls.`. Better: parametrise the one place via
  config (`Import root`) so the move does not touch the skills.
- **Order I recommend.**
  1. Extraction step 1 (sever couplings, tests prove independence). Skills' `host-contract`
     content falls out of this work.
  2. Write the plugin skills + `init` against the final API, inside `claude_plugins/panel-framework/`
     in FLS. Spec 12's doc is written as the package doc here too.
  3. Extraction step 2: `git mv` the plugin directory with the code into the new repo, add
     `.claude-plugin/marketplace.json` at the repo root, flip FLS's `claude.sh` line to the new path.
  4. Write `/panel-framework:update` after the first tag exists (it needs a `CHANGELOG.md` to read).
     This is the one piece that must come after the move. The packaging research already puts "write
     the plugin and the update command" last in its sequence; the corrected order is: plugin skills
     and `init` before the move, `update` after.
- **First-Class.** Because the plugin leaves the FLS tree on the move, First-Class's `claude.sh`
  needs a new `--plugin-dir` line pointing at the sibling clone (or, if it must be a submodule-free
  setup, a project `extraKnownMarketplaces` entry plus `claude plugin install ... --scope project`).
  Add this to the upgrade notes of the FLS spec that does the removal. `fls-dev:update_concrete_projects` /
  `concrete:update_fls` do not know about a second source of plugins; they will need either a line in
  `.claude/panel-framework/config.md` or no support at all (the update command stays inside each host).
- **The new project** has no FLS tree at all. It needs: the Python dependency (path dev / tag
  otherwise), the marketplace registration (local `directory` source on dev machines;
  `github`/`git` + `ref` pin elsewhere), `enabledPlugins`, then `/panel-framework:init`.

## 6. Open questions for the spec

- Whether the package repo is also the marketplace (recommended, one clone) or a separate
  marketplace repo lists it by `git-subdir`. Separate marketplace is only worth it when a second
  plugin from another repo is bundled.
- Whether the plugin's version tracks the package's tag exactly. Recommended: same number, bumped by
  the same release script, `ref`-pinned in `extraKnownMarketplaces`.
- Whether `claude.sh --plugin-dir` (current FLS convention) or `extraKnownMarketplaces` +
  `enabledPlugins` is the supported install for FLS-family projects. Both work; the marketplace
  route is the only one that works for a project without FLS's `claude.sh` convention.
- Whether spec 12 keeps the developer doc (and where) or defers it wholesale to the extraction
  effort (section 2).

## Sources

- https://code.claude.com/docs/en/plugin-marketplaces
- https://code.claude.com/docs/en/plugins/org.md
- https://code.claude.com/docs/en/plugins/marketplace-reference.md
- https://code.claude.com/docs/en/plugins/host-marketplace.md
- Repo files cited inline above.

status: ok
