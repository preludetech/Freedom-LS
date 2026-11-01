# Research: packaging and distributing the panel framework

How to organise the code once the panel framework leaves FLS, so that changing the framework stays
cheap and the projects that use it stay in step without a heavy update process.

## Recommendation

A standalone git repository, installed into every consumer as a `uv` **path** dependency on
development machines and as a **git tag** everywhere else. No git submodule. The Django app label,
template namespace, template-tag library names and cotton component names stay exactly as they are
today, so the extraction is a rename of the Python import path and nothing else.

## Why not the First-Class submodule pattern

First-Class embeds FLS as a submodule (`submodules/Freedom-LS`, installed editable through
`[tool.uv.sources]`) because a concrete project needs the whole FLS tree: the spec directories and
their `upgrade_notes.md`, the test suite collected through `testpaths`, and the template tree for
drift detection. `/fls-dev:update_concrete_projects` and `/fls-dev:concrete:update_fls` exist to
advance that pointer one spec at a time across several projects.

The panel framework is the opposite case:

| | FLS into a concrete project | Panel framework into a host |
| --- | --- | --- |
| Size | ~40 apps, specs, themes, demo content | one app: ~4,900 lines of Python, ~100 templates, one model |
| What the consumer needs | the whole tree | an importable package |
| Release unit | a completed spec | a tag |
| Consumers today | First-Class | FLS, then the new project |

A submodule pointer per consumer, a clean-tree precondition before every operation, and one commit
per integrated spec is exactly the ceremony the idea wants to avoid. None of it is needed for a
package this size.

## Repository layout

`/home/sheena/workspace/lms/django_apps/` already holds two earlier extraction attempts
(`content_engine`, `site_aware_models`, both with stale `*.egg-info` and `build/` directories).
Put the new repo beside them and tidy or delete the two old ones so the folder means one thing.

```
/home/sheena/workspace/lms/django_apps/panel_framework/
  pyproject.toml                    # name = "django-panel-framework", with an explicit [build-system]
  panel_framework/                  # the app; top-level import; app_label unchanged
  tests/ + conftest.py              # self-contained settings; stub models and stub panels exist already
  claude_plugins/panel-framework/   # the plugin (step 2 of the idea)
  CHANGELOG.md                      # one entry per tag, with the upgrade flags (see below)
```

**Keep the top-level package named `panel_framework`.** That preserves:

- `app_label = "panel_framework"`, so the `panel_framework_bulkactionrun` table, its ContentType
  row and the recorded migration history are untouched on every deployed database;
- the `panel_framework/...` template namespace, so theme overrides by path keep resolving;
- the `panel_tags` and `data_table_tags` template-tag libraries;
- every `c-panel-*`, `c-data-table*` and `c-modal-header` cotton name.

The distribution name on the index can be anything. The import name is what costs you.

## How FLS consumes it

On a development machine, in FLS's `pyproject.toml`:

```toml
[tool.uv.sources]
django-panel-framework = { path = "../../django_apps/panel_framework", editable = true }
```

This is the mechanism First-Class already uses for FLS. An edit in the panel repo is live in every
FLS worktree at once, with no pointer to move and nothing to commit in FLS.

CI and Docker cannot see that path, so the committed source is a git tag:

```toml
django-panel-framework = { git = "git@github.com:preludetech/django-panel-framework.git", tag = "v0.3.0" }
```

The spec decides how the two sources coexist (a gitignored `uv.toml` override on dev machines is the
simplest). The one invariant: the committed `uv.lock` must resolve on a clean machine.

First-Class and other concrete projects get the package transitively through `freedom_ls` and
declare nothing of their own.

## Couplings that must be severed before the move

Found by grepping `freedom_ls/panel_framework` for imports and template references outside the app.
Each is small.

| Coupling | Where | Resolution |
| --- | --- | --- |
| `BulkActionRun(SiteAwareModel)` | `models.py` | The `site` FK targets `django.contrib.sites`, which a package may depend on. Keep the FK so migration `0001_initial` stays byte-identical to what is deployed, and make request-to-site resolution a settings-declared callable. |
| `AppSettings`, `Setting` | `config.py` → `freedom_ls.base.app_settings` (75 lines) | Copy into the package. Do not create a shared "core" package for it. |
| `escape_csv_formula`, `EchoWriter`, `UTF8_BOM` | `tables.py`, `views.py` → `freedom_ls.base.csv_*` | Copy into the package. |
| FLS base cotton components: `button`, `button-group`, `chip`, `pagination`, `page`, `dropdown-menu`, `callout`, `back-link`, `modal-trigger`, `quick-view-trigger` | templates | Ship the package's own copies of the small ones. Declare the page shell as a host contract. |
| `c-icon` with names `check`, `close`, `dropdown`, `loading`, `menu`, `next`, `search` | templates → `freedom_ls.icons` | Host contract: the host provides `c-icon` and these semantic names. Enforce with a system check. |
| `{% extends "_base.html" %}` | `reference/component_reference.html` | Make the base template name a setting. |
| `freedom_ls.tests.site_context`, `playwright_helpers`, `factories.SiteFactory` | the test tree | Copy into the package's tests. `tests/stub_models.py`, `stub_panels.py`, `root_urls.py` and `urls.py` already give the suite a standalone fixture set. |
| `FREEDOM_LS_PACKAGE_DIR` | `tests/invariants/test_templates.py` | Replace with the package's own directory. |
| Tailwind `@source "./freedom_ls/**/templates/**/*.html"` | `tailwind.input.css` | The package's templates live outside the host tree. Ship a management command that writes a generated CSS file holding the resolved `@source` path, the same way `write_active_theme_css` writes `tailwind.active_theme.css`, and import it from the host's input CSS. |

Consumers inside FLS: `educator_interface` (about 40 files), `learner_management`, `deployment`,
`base` (one cotton component), `qa_helpers`, plus `config/urls.py` and `settings_base.py`. All of
them change one import prefix.

The import-linter contracts in `test_organisation/import_contracts.toml` need no hand edit;
`freedom_ls.panel_framework` drops out of the generated root list on the next `/ds:app_map` run.

## Keeping consumers in step without the FLS machinery

- **Tags are the release unit.** Every change a consumer should pick up gets a tag and a
  `CHANGELOG.md` entry. The entry carries the same flags FLS's `upgrade_notes.md` uses
  (`requires_migrations`, `requires_template_review` + `changed_template_paths`,
  `requires_settings_change`, `requires_tailwind_rebuild`) so an update command has something
  mechanical to read, without a second spec system.
- **A breaking change keeps the old surface for one tag.** Rename in tag N with an alias and a
  deprecation warning; remove in tag N+1. This single rule is what stops a host update from turning
  into a migration project.
- **Run the consumers' suites from the package repo before tagging.** A script in the package repo
  reads a gitignored list of consumer paths and runs each one's panel-related tests against the
  working copy. The editable install means this needs no pointer dance. It is the small equivalent
  of `/fls-dev:update_concrete_projects`.
- **One update command in the plugin**, `/panel-framework:update`: bump the tag in the host's
  `pyproject.toml`, `uv lock`, read the changelog entries between the old and new tags, run the
  flagged steps, run the host's tests, commit. No per-spec commits, no rollback script, no preview
  matrix. Those exist in FLS because it integrates many specs into many projects in one run; here
  there is one package and a handful of hosts.
- **FLS's existing flow carries it downstream.** When FLS bumps its panel-framework tag, that FLS
  spec's `upgrade_notes.md` sets `requires_package_upgrade`, and the existing concrete-project
  integration handles First-Class with no new tooling.

## The plugin

Lives in the package repo and follows the `ds` / `fls-dev` split: generic skills describing the
framework's API, the component inventory, how to define a panel, bulk actions and testing, with
per-project values in `.claude/panel-framework/config.md`. `fls-dev` then drops what it says about
panels and points at the new plugin, which keeps the `CLAUDE.md` rule that a generic plugin never
carries a project name.

## Sequence

1. **Inside FLS, under the existing app, sever the couplings above while nothing moves.** Copy in
   the helpers, add the hooks, make the base template configurable, add the tailwind source
   command. Add a test proving the app imports nothing from `freedom_ls` outside the declared
   hooks. This is step 1 of the idea and holds most of the risk.
2. **Create the repo, move the directory, rename the import prefix in one pass, run the package's
   suite standalone, tag `v0.1.0`.**
3. **FLS: add the dependency, delete the in-tree app, run the full suite, write the upgrade notes
   with `requires_package_upgrade`.** Integrate into First-Class through the normal flow.
4. **Write the plugin and the update command.**

Checkpoint between 1 and 2: if step 1 cannot make the app standalone without a shared core package,
stop and reconsider. That is the point at which the extraction stops being cheap.
