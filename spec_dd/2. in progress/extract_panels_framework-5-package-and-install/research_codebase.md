# Research: codebase inventory for `extract_panels_framework-5-package-and-install`

Question: what in the existing codebase does moving `freedom_ls/panel_framework` into the
`django-panel-framework` package touch, reuse or conflict with?

Snapshot: worktree `extract_panels_framework-5-package-and-install`, branch tip `6eda71eaa`. All paths are
relative to the worktree root unless absolute. Counts come from ripgrep over the tree, `spec_dd/` and
`.test_durations` excluded.

## 0. Findings that change the idea (read first)

1. **The "55 lines in 22 files" count is stale.** `freedom_ls.panel_framework` appears on **161 lines in 91 files**
   outside the app (section 1). Of those, 114 lines in 62 files are non-test code. Plan for a scripted rewrite
   plus `ruff check --fix` (import order), not a hand edit.
2. **Three existing educator_interface migrations name the old app label** and will make the migration loader
   raise `NodeNotFoundError` the moment `freedom_ls_panel_framework` leaves `INSTALLED_APPS`
   (`freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py:35` is a hard
   `dependencies` entry, 0002 and 0003 chain from it). The "never edit an existing migration" rule cannot
   hold for these; the spec must decide how (section 3).
3. **`base` has no `migrations/` package** (no models), nor does `deployment`. The idea's candidate host for the
   drop-table migration would need a new migrations package. `educator_interface` already has one
   (0001 to 0003, no models) and is the only app that ever depended on the old label. See section 4.
4. **`write_panel_framework_css` does not emit `not-ignored:`.** The idea says the generated `@source` uses it;
   the command as it stands writes `@source "<path>"` with no modifier
   (`freedom_ls/panel_framework/management/commands/write_panel_framework_css.py:43-44`). Either spec 4's final
   form differs from what is on this branch, or the change is still to make (in the package, not in FLS).
5. **First-Class imports the framework CSS straight from the submodule path**, not through the generated file
   (`/home/sheena/workspace/first_class/First-Class-LMS.git/main/tailwind.input.css:54`), and the concrete
   template's input imports no panel-framework CSS at all (section 8). Both need an upgrade-notes edit.
6. **The pre-commit hook runs `uv run`** (`claude_plugins/django-stack/scripts/install_pre_commit_hook.sh:29`),
   so every plain `git commit` is a `uv run` that would revert a hand-installed editable copy unless
   `UV_NO_SYNC=1` is in the committing process's environment. Relevant to Spike 1 and to where the env var lives.
7. **Mypy, ruff isort and bandit config see `panel_framework` as a third-party package afterwards** (section 6).
   Without `py.typed` in the package, mypy fails 91 files on `import-untyped`.
8. **The package's check IDs are spelled with the old label** (`freedom_ls_panel_framework.E009/E010/W001/W002/W003`).
   Renaming the label does not rename them, and a downstream `SILENCED_SYSTEM_CHECKS` entry may name them.
   The idea says nothing; the spec has to choose (section 2.5).
9. **The local package checkout is a bare repo plus an empty `main/README.md`**, and the GitHub repo holds one
   commit with only `README.md` (section 9).

## 1. Every `freedom_ls.panel_framework` reference outside the app

### 1.1 Totals

| Scope | Lines | Files |
| --- | --- | --- |
| Whole `freedom_ls/` tree outside `freedom_ls/panel_framework/` | 161 | 91 |
| of which `educator_interface` | 142 | 78 |
| of which every other consumer | 19 | 13 |
| Non-test code only (any app) | 114 | 62 |
| Inside `freedom_ls/panel_framework/` itself (app code / tests) | 65 / 116 | 19 / 45 |

Idea's "55 lines in 22 files" matches neither cut. Not found anywhere: a consumer outside `freedom_ls/`,
`config/`, `claude_plugins/`, `test_organisation/`, `package.json`, `.gitignore`, `docs/app_structure.md`.

Two lines are not import statements: `freedom_ls/educator_interface/tests/panels/common/test_bulk_actions.py:169`
(`monkeypatch.setattr("freedom_ls.panel_framework.bulk_runs.run_apply", _explode)`, the only mock-patch-style
dotted target) and `freedom_ls/educator_interface/tests/invariants/test_framework_copies_match_base.py:18`
(`import freedom_ls.panel_framework.templatetags.data_table_tags as ...`).

### 1.2 Consumers other than educator_interface (19 lines, 13 files)

- `accounts`: `freedom_ls/accounts/panels/personal_details/actions.py:31,37,38`; `config.py:10`;
  `instance_view.py:5,6`; `panels.py:13,14`; `freedom_ls/accounts/views.py:13`;
  `freedom_ls/accounts/tests/panels/personal_details/test_panels.py:15`
- `base`: `freedom_ls/base/tests/invariants/test_panel_template_rules.py:17` (imports
  `freedom_ls.panel_framework.tests.invariants.template_rules`, a test module, see 1.5)
- `deployment`: `freedom_ls/deployment/housekeeping.py:33,39`; `freedom_ls/deployment/tests/test_housekeeping.py:50,57`
- `learner_management`: `freedom_ls/learner_management/models.py:12` (`RunStatus`, used at module level in
  `ImportStatus` at `:362-370`)
- `qa_helpers`: `freedom_ls/qa_helpers/management/commands/qa_create_bulk_operations_scenario.py:56`
  (`BulkActionRun`, `scope_lookup`)
- `reports`: `freedom_ls/reports/report_data.py:18`; `freedom_ls/reports/tests/test_report_data.py:5`
  (`PanelBodyTooLargeError`). The idea's list of consumers omits `accounts` and `reports`.

### 1.3 educator_interface (142 lines, 78 files)

All under `freedom_ls/educator_interface/`: `forms.py:24`, `learner_import.py:46,47`, `notification_urls.py:12`,
`views.py:36`, `templatetags/educator_tags.py:26`, and every `panels/{audit_log,cohort,common,course,dashboard,learner,staff}/*.py`
module (30 modules; for example `panels/cohort/config.py:32-35`, `panels/learner/import_views.py:79-81`,
`panels/staff/actions.py:87,97,290`). Tests: `tests/interface_walk.py:32-35`,
`tests/invariants/*` (8 files), `tests/migrations/test_0002_move_learner_bulk_runs.py:16`,
`test_0003_move_cohort_bulk_runs.py:16`, `tests/panels/**` (17 files), `tests/test_notification_urls.py:12`.
Regenerate the full list with `rg -n 'freedom_ls\.panel_framework' freedom_ls --glob '!panel_framework/**'`.

Local imports inside functions (do not miss when scripting): `educator_interface/notification_urls.py:12`
(indented), `panels/staff/actions.py:290` (indented).

### 1.4 Label strings (`freedom_ls_panel_framework`), outside the app

- `freedom_ls/educator_interface/migrations/0001_rename_unregister_bulk_runs.py:26,35`;
  `0002_move_learner_bulk_runs.py:30`; `0003_move_cohort_bulk_runs.py:27` (`apps.get_model(...)`)
- `freedom_ls/educator_interface/tests/migrations/test_0001...py:16`, `test_0002...py:19`, `test_0003...py:19`
  (`RUNS = "freedom_ls_panel_framework"`)
- `freedom_ls/educator_interface/tests/invariants/test_system_checks.py:44` (`freedom_ls_panel_framework.E010`, `.W003`)
- `freedom_ls/deployment/tests/test_settings_defaults.py:357` (`freedom_ls_panel_framework.W001`)
- Nothing in `config/` silences these checks (`rg SILENCED_SYSTEM_CHECKS config` finds nothing).

### 1.5 Path-based references (not dotted, break on the move)

These read files at `freedom_ls/panel_framework/...` and fail when the directory is gone:

- `freedom_ls/base/tests/invariants/test_panel_framework_css_copies.py:22,59` (`FREEDOM_LS_PACKAGE_DIR / "panel_framework/css/panel_framework.css"`, `.../templates/cotton/data-table-actions.html`)
- `freedom_ls/base/tests/invariants/test_panel_framework_tailwind.py:27` (`reference_theme.css`), `:92` (gitignore check on `freedom_ls/panel_framework/static/panel_framework/css/reference.css`), `:64` (`call_command("write_panel_framework_css")`)
- `freedom_ls/base/tests/invariants/test_panel_template_rules.py:28` (`FREEDOM_LS_PACKAGE_DIR / "panel_framework" / "templates" / "cotton" / "modal-footer.html"`)
- `freedom_ls/educator_interface/tests/invariants/test_bulk_run_scoping.py:21,115` (`PACKAGE_ROOT / "panel_framework" / "bulk_runs.py"`; `ALLOWED = {("panel_framework/bulk_runs.py", "_base_manager")}`)
- `freedom_ls/educator_interface/tests/invariants/test_framework_copies_match_base.py:36-46` (framework `alpine-components.js` and `tests/playwright/helpers.py` found beside `app_settings.__file__`; this one resolves through the import, so it follows the package if the wheel ships `static/` and the `tests/playwright/helpers.py` file)
- `freedom_ls/educator_interface/tests/invariants/test_panel_template_rules.py:15,28-30` (resolves through the import)

**Test modules the package must keep shipping, or these FLS tests change**: `panel_framework.tests.invariants.template_rules`
is imported by `freedom_ls/base/tests/invariants/test_panel_template_rules.py:17` and
`freedom_ls/educator_interface/tests/invariants/test_panel_template_rules.py:16`; the educator test also reads
`tests/playwright/helpers.py` (above). Whether the wheel includes a `tests` package is a layout decision for the
package repo. The import-linter baseline lists this exact edge
(`test_organisation/import_baseline.txt:18`, `test_organisation/import_contracts.toml:63`).

### 1.6 Settings, URLs, config

- `config/settings_base.py:145` `"freedom_ls.panel_framework",` in `INSTALLED_APPS` (between `freedom_ls.site_aware_models`
  at 144 and `freedom_ls.educator_interface` at 146). Keep the same position: FLS overrides framework templates
  (`freedom_ls/base/templates/panel_framework/reference/base.html`, `freedom_ls/base/templates/cotton/panel-icon.html` per
  `HOST_CONTRACT.md:194,245`) and the app-directories loader order follows `INSTALLED_APPS`.
- `config/urls.py:97` `path("panel-framework/", include("freedom_ls.panel_framework.urls"))`, inside `if settings.DEBUG:` only
  (the staff-only component reference). Not in `config/settings_dev.py` or `settings_prod.py`.
- No other settings module names the app; `rg 'panel_framework' config` returns only those two lines.
- The app's own setting default is a dotted string: `freedom_ls/panel_framework/config.py:42`
  `default="freedom_ls.panel_framework.sites.current_site_or_none"`. It moves with the app.

### 1.7 Template/static references that do NOT change (bare `panel_framework/...` paths)

Template paths, static paths, cotton names, `panel_tags`, `data_table_tags` stay valid because the app label was
never in them. Consumers: `freedom_ls/accounts/templates/accounts/_account_shell.html:5,25,29,37,41`,
`accounts/templates/accounts/panels/*.html`, `allauth/elements/h1__manage.html:12`, `allauth/layouts/manage.html:20`,
`freedom_ls/base/templates/_base.html:73` (`shell-components.js`), `base/templates/partials/form.html:1`,
`base/templates/partials/page_title.html:1`, 38 educator_interface templates (48 lines). `rg` check:
`rg -l 'panel_framework' freedom_ls --glob '*.html'`.

### 1.8 Docs, skills, resources (edit by hand or regenerate)

Skills and resources under `claude_plugins/fls-dev/`:

| File | Lines naming `freedom_ls.panel_framework` or `freedom_ls/panel_framework` or the old label |
| --- | --- |
| `skills/panel-framework/SKILL.md` | 9, 119, 132, 141, 157, 162, 187, 230, 231, 560, 594, 595, 612, 615 (14 lines; the skill documents the app's layout, so it also needs a path rewrite to "installed package" wording; spec 6 later moves it) |
| `skills/testing/SKILL.md` | 23, 73, 79, 114, 124, 127, 130, 133 (standalone command now lives in the package; 130 and 133 name `freedom_ls/panel_framework/tests/standalone_pytest.ini` and `--ds=freedom_ls.panel_framework.tests.standalone_settings`) |
| `skills/playwright-tests/SKILL.md` | 18 (`freedom_ls/panel_framework/tests/playwright/helpers.py`, "edit both together") |
| `skills/app-settings/SKILL.md` | 17 (names `freedom_ls/panel_framework` as an app that must not import `freedom_ls.base`) |
| `skills/icon-usage/SKILL.md` | 15 (two `freedom_ls/panel_framework` mentions) |
| `skills/alpine-js/SKILL.md` | **no `freedom_ls.panel_framework` string**; lines 22, 24, 29, 46-52, 67 use bare `panel_framework` as the owner column. Idea lists it as needing an update; only the "framework's own copy ... Edit both together" wording at :22 goes stale |
| `resources/multi_tenant.md` | 21 (`freedom_ls.panel_framework.models.BulkActionRun`) |
| `resources/testing.md` | 51 (a long line naming `panel_framework`; narrow-selection example) |
| `skills/multi-tenant/SKILL.md` | 15 (`panel_framework.BulkActionRun`, label-style, already prefix-free) |

Other:

- `.claude/skills/brand-guidelines/visual.md:96` (long line, names the app); `.claude/agent-memory/sdd-qa-data-helper/reference_in_progress_learner_import.md` (one hit)
- `docs/app_structure.md`: **generated** by `claude_plugins/django-stack/scripts/generate_app_map.py`
  (CI lint runs it with `--check`, tests.yml:43; pre-commit `app-map-fresh`, `.pre-commit-config.yaml:70-72`).
  Do not hand edit; regenerate. Present lines: 45 (node), 60, 131, 150, 186, 210 (`panel_framework --> accounts`, from the `BulkActionRun`
  FK to `AUTH_USER_MODEL`), 228, 256, 279, 324, 328, 338, 340, 347, 354, 355, 358.
- `test_organisation/import_contracts.toml`: **generated** by `/ds:app_map` (header line 1). 36 hits: `root_packages` (4), one `forbidden_modules` entry in nearly every app
  contract, the `panel_framework` contract itself (343-349, `source_modules = ["freedom_ls.panel_framework.tests"]`)
  and the allowance at :63. Regenerate; the contract and `root_packages` entry disappear.
- `test_organisation/import_baseline.txt:18` (the `base` to `panel_framework.tests` edge) and `:76` (empty `# panel_framework` section);
  `test_organisation/mirroring_baseline.txt:52` (empty section);
  `test_organisation/mirroring_exemptions.txt:14,15,28,29` (four exemptions for package tests). These are hand-maintained or
  tool-maintained lists; delete the package's entries.
- `test_organisation/test_cost_ranking.md` (13 rows), `.test_durations` (1732 occurrences across the tree, most of them
  package tests; CI uses `--durations-path .test_durations`, tests.yml:27). Both are generated; stale rows are harmless to
  pytest-split but the ranking doc is noise.
- `.gitignore:32` (`tailwind.panel_framework.css`) stays; `.gitignore:83-84` (`freedom_ls/panel_framework/static/panel_framework/css/reference.css`) goes.

## 2. The app today

### 2.1 AppConfig

`freedom_ls/panel_framework/apps.py:4-23`: `PanelFrameworkConfig`, `default_auto_field = BigAutoField`,
`name = "freedom_ls.panel_framework"`, `label = "freedom_ls_panel_framework"`, `verbose_name = "Panel framework"`.
`ready()` registers four system checks from `checks.py` (`check_icon_names`, `check_panels`, `check_task_backend`,
`check_site_resolver`) with a `freedom_ls.panel_framework.checks` import at :13. After the move `name` and the import become
`panel_framework`, and `label` becomes `panel_framework` (or is dropped, since the default equals it).

### 2.2 Migrations (2)

- `freedom_ls/panel_framework/migrations/0001_initial.py`: `CreateModel BulkActionRun` (UUID pk, `scope_id`, `action_path`, `table_key`, `action_name`,
  `target` JSON, `keys` JSON, `status` with four choices and `db_index`, `processed_count`, `error_message`, `result` JSON,
  `created_at`, `started_at`, `finished_at`, FK `requested_by` to `AUTH_USER_MODEL` (CASCADE, `related_name='+'`), FK `scope_type` to `contenttypes.contenttype`
  (nullable, CASCADE), FK `site` to `sites.site` (PROTECT)), `ordering = ['-created_at']`, an index named `freedom_ls__scope_t_9e7b0b_idx`.
  Dependencies: `contenttypes 0002`, `sites 0002_alter_domain_unique`, swappable user (`:13-17`). The table is `freedom_ls_panel_framework_bulkactionrun`.
- `0002_bulk_action_run_site_has_no_reverse_accessor.py:15-19`: `AlterField site` adds `related_name='+'`. Depends on `freedom_ls_panel_framework 0001_initial` and `sites 0002`.
- Model: `freedom_ls/panel_framework/models.py:28` `RunStatus(TextChoices)`, `:49` `BulkActionRun` with `site = ForeignKey(Site, on_delete=PROTECT, related_name="+")` at `:73`,
  `objects = BulkActionRunQuerySet.as_manager()` at `:108`. The regenerated `0001` creates `panel_framework_bulkactionrun`, so the new name does not collide with the old table.
- Keep in the regenerated index name: Django derives it from the table, so the old name `freedom_ls__scope_t_9e7b0b_idx` will not be reused. No clash on a database that still holds the old table.

### 2.3 Templates, static, templatetags, management, CSS

- `templates/cotton/` (about 50 files: `data-table*.html`, `panel-*.html`, `modal-*.html`, `quick-view-trigger.html`, `data-table-cells/*.html`);
  `templates/panel_framework/{icons,modal,partials,panels,reference,views}/...` including
  `templates/panel_framework/icons/HEROICONS_LICENSE.txt` (the notice the wheel test must find).
- `static/panel_framework/js/alpine-components.js`, `static/panel_framework/js/shell-components.js`.
- `css/panel_framework.css`, `css/reference_theme.css`, `css/minimal_shell.css` (`css/` sits beside the app, not under `static/`; `write_panel_framework_css` points at it by path).
- `templatetags/panel_tags.py`, `templatetags/data_table_tags.py`.
- `management/commands/write_panel_framework_css.py` (the Tailwind source command spec 4 delivered; the file it writes is `tailwind.panel_framework.css`
  at `settings.BASE_DIR`, `:19,46`). Its only coupling to the label: `apps.get_app_config("freedom_ls_panel_framework")` at `:41`.
- `HOST_CONTRACT.md` (25 hits for the old dotted prefix and label, including check IDs at `:198-199`).
- Modules: `actions, app_settings, bulk_actions, bulk_runs, checks, config, context, csv_safety, errors, events, field_display, filters, forms, housekeeping,
  lazy_panels, models, panels, quick_view, reference, run_records, sites, tables, tasks, urls, views`.
- Ignored build product: `static/panel_framework/css/reference.css`, built by `npm run panel_framework_css` from `tests/css/reference_input.css`
  (`package.json:11`, `.gitignore:83-84`).

### 2.4 Tests and conftest

Layout: `freedom_ls/panel_framework/tests/` holds `components/` (about 30 modules), `invariants/` (9 incl. `template_rules.py`), `management/commands/`,
`templatetags/`, `playwright/` (8 flow tests, `conftest.py`, `helpers.py`, `assertions.py`), `standalone_app/` (`models.py` user model, `context_processors.py`),
`templates/panel_framework/test_*.html` (18 test-only templates), `template_overrides/panel_framework/panels/panel.html`, `css/reference_input.css`,
about 30 `test_*.py` at top level, and helpers `conftest.py`, `cotton_helpers.py`, `helpers.py`, `root_urls.py`, `urls.py`, `stub_models.py`, `stub_panels.py`,
`standalone_fixtures.py`, `standalone_settings.py`, `standalone_pytest.ini`, `view_helpers.py`.

- `tests/standalone_pytest.ini:1-15`: `pythonpath = ../../..`, `--ds=freedom_ls.panel_framework.tests.standalone_settings`, `--nomigrations`,
  `-m "not needs_fls_host"`, `--disable-socket`, `norecursedirs = playwright`, own `needs_fls_host` marker.
- `tests/standalone_settings.py:25-26,52,64`: `INSTALLED_APPS` lists `freedom_ls.panel_framework` and `freedom_ls.panel_framework.tests.standalone_app`; context processor and
  `ROOT_URLCONF` are dotted `freedom_ls.panel_framework.tests...` strings.
- `tests/conftest.py`: `:45` compares `SETTINGS_MODULE` to `"freedom_ls.panel_framework.tests.standalone_settings"`; `:64` `apps.all_models.get("freedom_ls_panel_framework", {})`;
  `:110-113` deletes ContentType rows for `app_label="freedom_ls_panel_framework"`; `:198` sets `ROOT_URLCONF`. A comment (`:20-25`) records a namespace-package double-import hazard
  that depends on `freedom_ls` having no `__init__.py`; that reasoning changes in a standalone repo.
- `tests/stub_models.py` (9 label strings), `tests/stub_panels.py` (14 hits, 4 label), `test_checks.py` (33 hits, 27 label), `test_actions.py`, `test_panels.py`, `test_field_display.py`: stub models declare the old app label; after the move they
  declare `panel_framework`.
- `test_import_guard.py:12-20` forbids any `freedom_ls` import inside the framework (`EXEMPT_DIRECTORIES = ()`). **The guard passes today: no file in the app imports another `freedom_ls` app** (see 2.6).
- Tests that mention FLS by name or path and need rewording or removal in a standalone repo: `tests/invariants/test_templates.py:650-721` (`FLS_APP_LABELS`, `FLS_ONLY_NAMES`),
  `tests/test_reference.py:384-387` (monkeypatches `freedom_ls.api.urls` in `sys.modules`), `tests/test_standalone_fixtures.py:12,22`, `tests/test_models.py:99`
  (`freedom_ls.site_aware_models` asserted absent), `tests/test_housekeeping.py`, `tests/helpers.py:4`.
- `needs_fls_host` appears 14 times, all in five package test files (`components/test_inline_record_form_template.py`, `components/test_modal_form_template.py`,
  `test_reference.py`, `test_tables.py`, `standalone_pytest.ini`). FLS's `pyproject.toml:103` marker then has no user inside FLS.

### 2.5 System check IDs

`checks.py` ids: `freedom_ls_panel_framework.E009` (`:33`), `.W001` (`:119,122`), `.E010` (`:158`), `.W003` (`:167`) and W002 (`check_site_resolver`, per `SKILL.md:162`).
Referenced by `HOST_CONTRACT.md:198-199`, `skills/panel-framework/SKILL.md:157,162`, FLS tests (1.4), package tests (`test_checks.py`, 27 lines).
The label change does not force a rename. Decide: keep the IDs and document, or rename to `panel_framework.*` and list `SILENCED_SYSTEM_CHECKS` in `changed_settings`
(the `update_upgrade_notes` command treats a renumbered ID as a hard settings change, `claude_plugins/fls-dev/commands/update_upgrade_notes.md:55`).

### 2.6 Remaining imports from other `freedom_ls` apps

None. `rg` for `(from|import) freedom_ls.<other app>` and `"freedom_ls..."` strings inside `freedom_ls/panel_framework` (code and tests) finds only:

- FLS names in prose and comments: `HOST_CONTRACT.md:79,80,194,229,244,245`, `housekeeping.py:6`, `tests/conftest.py:164`, `tests/helpers.py:4`,
  `tests/stub_models.py:3`, `tests/test_bulk_actions.py:1364`.
- The import guard's own parametrised source strings (`tests/test_import_guard.py:61-66`).
- `tests/test_reference.py:384-387` (`freedom_ls.api.urls` as a `sys.modules` key) and `tests/test_models.py:99` and `tests/test_standalone_fixtures.py:22` (string checks, no import).
- `tests/invariants/test_templates.py:692,721` (regexes naming `freedom_ls`, `FREEDOM_LS_PACKAGE_DIR`, `freedom_ls.tests.playwright_helpers`).

Specs 3 and 4 delivered the standalone state. The only residual FLS coupling in the app is the model FK to `AUTH_USER_MODEL` (the `panel_framework --> accounts` edge in `docs/app_structure.md:210`)
and to `django.contrib.sites`.

## 3. The old table and everything that depends on it

### 3.1 References to `freedom_ls_panel_framework_bulkactionrun`

None in code. The table name is only implied by the label and model name. `rg freedom_ls_panel_framework_bulkactionrun` finds nothing outside this spec dir.
`BulkActionRun` is used by `deployment/housekeeping.py` (3.3), `educator_interface` (`panels/common/bulk_actions.py:26`, `notification_urls.py:12`, tests), `qa_helpers`
(`qa_create_bulk_operations_scenario.py:56`).

### 3.2 `RunStatus` in `learner_management`

`freedom_ls/learner_management/models.py:12` imports `RunStatus` at module import; `ImportStatus(models.TextChoices)` at `:362-370` copies four values and labels from it.
`RunStatus` must stay a public name of `panel_framework.models`. No `learner_management` migration references the framework (its migration `0009_learnerimport_learnerimportrow.py`
holds literal choices). `educator_interface/learner_import.py:46` and `panels/learner/import_views.py:80` also import it.

### 3.3 `freedom_ls/deployment/housekeeping.py`

Imports at `:33-39`: `ReportClosed`, `delete_finished_records`, `mark_orphaned_runs_failed`, `mark_unpicked_runs_failed` from `...housekeeping` and `BulkActionRun` from `...models`.
`BULK_RECORD_MODELS = (BulkActionRun, LearnerImport)` at `:236` feeds three sweeps in `run_housekeeping_sweeps` (`:401-447`). Tests: `deployment/tests/test_housekeeping.py:50,57`
and about 30 `RunStatus` uses (`:975-1436`). The package's own `tests/test_housekeeping.py` covers the framework half.

### 3.4 Migrations in other apps that depend on `freedom_ls_panel_framework`

Only `educator_interface`. No other app has a dependency or `get_model` on the label (`rg freedom_ls_panel_framework freedom_ls` outside the app: educator_interface migrations and tests only).

| Migration | Reference | Effect when the app is removed |
| --- | --- | --- |
| `educator_interface/migrations/0001_rename_unregister_bulk_runs.py:35` | `dependencies = [("freedom_ls_panel_framework", "0001_initial")]`; `:26` `apps.get_model("freedom_ls_panel_framework", "BulkActionRun")` | `NodeNotFoundError` at graph build: every `migrate`, `makemigrations`, `showmigrations` and the pytest DB setup fail |
| `0002_move_learner_bulk_runs.py:30,44` | `get_model` only; depends on 0001 of its own app | Runtime `LookupError` in `RunPython` (once 0001 loads) |
| `0003_move_cohort_bulk_runs.py:27,41` | same | same |

All three are data migrations that repoint a stored `action_path` string on `BulkActionRun` rows. The idea drops the old table and keeps no data, so the work is moot on every
environment. Options for the spec (the migration-edit rule is the constraint):

1. **Repoint to the new label**: change the dependency to `("panel_framework", "0001_initial")` and `get_model` to `"panel_framework"`. Works on fresh databases (empty table) and on deployed
   ones (the new table is empty; old rows are discarded anyway). Smallest edit, breaks "never edit existing migrations" once, and needs a documented exception.
2. **Neutralise**: keep file names and the migration chain, replace operations with `RunPython.noop` and drop the framework dependency. Same rule break, more honest about the data being gone.
3. **Squash/replace**: delete the three files and add a fresh `0001` with `replaces` or a no-op. Deployed databases hold `django_migrations` rows for all three names; a replacement has to keep those names
   valid, so this is more fragile than 2.
The three migration tests need the same treatment: `educator_interface/tests/migrations/test_0001..0003` drive `MigrationExecutor` through `(RUNS, "0001_initial")` and import
`freedom_ls.panel_framework.bulk_actions.RecordedBulkAction` (`test_0002...py:16,19,50`). Delete them with option 2, or repoint with option 1.

## 4. Host for the drop-old-table migration

Constraints the migration must meet: survive in an app that exists on every environment; run on deployed databases (old table and rows present), per-branch dev databases (old table present)
and fresh databases (nothing to drop); use `connection.introspection` + `schema_editor.delete_model` on a throwaway model, never raw SQL; delete `django_migrations` and `ContentType` rows through the ORM.

Candidates:

| App | Has `migrations/` | Models | Verdict |
| --- | --- | --- | --- |
| `educator_interface` | yes (0001 to 0003, no models, `apps.py:6-7` label `freedom_ls_educator_interface`) | none | **Recommended.** Its three migrations are the only ones that referenced the old app, so the drop migration is the natural 0004 beside the fix from section 3.4. No new package |
| `base` | **no** `migrations/` directory | none | The idea's candidate, but a migration-only app needs a new `migrations/__init__.py` and a first migration for a model-less app. Works, adds a state-only app to every deploy |
| `deployment` | no | none | Same cost as `base` |
| `learner_management` | yes (0001 to 0012+) | yes | Possible, but couples an unrelated app's history to this change |

Ordering for `educator_interface` 0004:

- `dependencies`: the previous educator migration (0003), plus `("contenttypes", "0002_remove_content_type_name")` for the ORM `ContentType`, and `("auth", ...)` so `Permission` is in the
  state and the historical collector cascades them. `django-guardian` object-permission rows and `admin.LogEntry` rows hold FKs to `ContentType` too; guardian is installed
  (`settings_base.py:112`). The historical state only cascades to models in the migration graph that the migration depends on, so check whether `BulkActionRun` ever had object
  permissions or admin log entries (likely none: no admin for it, `rg` finds no `admin.register` for it).
- No dependency on the new `panel_framework` migrations. Its `0001` creates `panel_framework_bulkactionrun`; the drop targets `freedom_ls_panel_framework_bulkactionrun`.
  Neither depends on the other and the order is free on the table level. The educator 0001 to 0003 fix of 3.4 **does** need `panel_framework 0001` first if option 1 is taken.
- The old table has FKs out to `django_site`, the user table and `django_content_type` and nothing in. `delete_model` therefore drops it without touching other tables. On PostgreSQL the DDL is transactional.
- `django_migrations` rows: the ORM model for them is `django.db.migrations.recorder.MigrationRecorder(connection).migration_qs` (filter `app="freedom_ls_panel_framework"`, delete). Rows for the old app
  (`0001_initial`, `0002_bulk_action_run_site_has_no_reverse_accessor`) become orphans otherwise; Django ignores them, `showmigrations` does not list them, but they linger.
- ContentType rows: `ContentType.objects.filter(app_label="freedom_ls_panel_framework").delete()` via the historical model.
- Reverse: `RunPython.noop`. The throwaway model must be built in a private `Apps()` registry (and cleared) so it does not register `freedom_ls_panel_framework` as an app label again.
- Dev DBs and pytest DBs: `install_dev.sh` runs `uv run manage.py migrate` (`claude_plugins/fls-dev/scripts/install_dev.sh:16`), so every per-branch database fixes itself on first migrate.

## 5. `pyproject.toml`, CI, Tailwind, npm

### 5.1 `pyproject.toml`

- `[project].dependencies` is `:7-48` (one line per dependency, no VCS entries yet); the dev group is duplicated at `[project.optional-dependencies].dev` (`:50-81`) and
  `[dependency-groups].dev` (`:245-277`). The new line goes in `[project].dependencies` only; there is no `[tool.uv.sources]` table in FLS's `pyproject.toml` today (First-Class and the template have one for `freedom_ls`).
- Build config: only `[tool.setuptools.packages.find]` (`:83-86`) with `include = ["freedom_ls*"]`; there is **no `[build-system]`**. Nothing to remove for the app (a glob), per the earlier research.
- `[tool.pytest.ini_options]` (`:88-105`): `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`; `addopts` uses `-m 'not ci_only and not weasyprint and not dev_tooling'`; markers include
  `needs_fls_host` (`:103`) which only package tests use (2.4). No `panel_framework` string anywhere in `pyproject.toml`.
- Tooling that treats `panel_framework` differently once it is site-packages code:
  - `[tool.ruff.lint.isort] known-first-party = ["freedom_ls"]` with custom section order (`:349-358`): `from panel_framework...` imports move from the first-party block into third-party (or
    need `known-first-party`/a section entry). Expect an isort reshuffle in 91 files; run `ruff check --fix`.
  - `[tool.mypy]` (`:375-424`): `mypy_path = "."`, `namespace_packages`, `explicit_package_bases`; no override for `panel_framework`. The package needs `py.typed` or an
    `ignore_missing_imports` override. `[[tool.mypy.overrides]] module = ["*.tests.*", ...]` does not touch it.
  - `[tool.coverage.run] source = ["freedom_ls"]` (`:209`): framework code leaves the coverage number; `COVERAGE_FAIL_UNDER: 92` (tests.yml:291) may shift (the framework's own tests currently count).
  - `[tool.bandit]` and ruff `per-file-ignores` do not reach the package any more.
- `tests/test_tests_workflow.py` and `tests/test_remote_full_run.py` pin job shapes; the standalone job is found by name (`STANDALONE_JOB = "standalone-tests"`, `:23`) and `standalone-icons` is the one used in fixtures
  (`test_remote_full_run.py:158,766,782`). Dropping `panel_framework` from the matrix does not break them; check the fixtures that mention `standalone-panel_framework`: none found.

### 5.2 `.github/workflows/tests.yml`

Every job: `actions/checkout@v6`, `astral-sh/setup-uv@v7` (`enable-cache: true`), `uv python install 3.13`, then a bare `uv sync`. Lines of `uv sync`: `lint :40`, `type-check :57`,
`unit-tests :98`, `playwright-tests :177`, `standalone-tests :254`, `coverage :304`, `test-verdict :367`. Neither `--locked` nor `--frozen` is present anywhere. The idea's `uv sync --locked`
means editing all seven.

| Job | Tailwind build | Notes |
| --- | --- | --- |
| lint (`:30-45`) | none | runs `generate_app_map.py --check` (`:43`), `lint-imports` (`:44`), `check_test_mirroring.py` (`:45`): all three change output when the app leaves |
| type-check (`:47-60`) | none | `uv run mypy .` (`:58`) |
| unit-tests (`:62-139`, 6 groups) | `npm ci` `:107`, `npm run tailwind_build` `:109-110`, after `uv sync` `:98` | already the order the idea needs: `uv sync` before Tailwind |
| playwright-tests (`:141-216`, 2 groups) | `:188-189`, after `uv sync` `:177`; `playwright install` `:191-192` | package Playwright tests leave the FLS run (they sit under `freedom_ls/panel_framework/tests/playwright`, collected by `-m playwright`); the package CI needs its own Tailwind + Playwright |
| standalone-tests (`:218-283`) | `:265-266` | matrix `app: [panel_framework, icons]` at `:225`; the run uses `-c freedom_ls/${{ matrix.app }}/tests/standalone_pytest.ini` (`:273-274`) and the artifact name `group-report-standalone-${{ matrix.app }}` (`:281`). Remove `panel_framework`; the job's shape holds for `icons` |
| coverage (`:285-332`) | none | needs only `uv sync` |
| test-verdict (`:334-402`) | `:378-379` | `uv run pytest --collect-only` (`:399-400`) |

Postgres `services` blocks sit on unit, playwright, standalone and verdict. No job needs `git` installed (GitHub runners ship it) and the package repo is public, so no credentials step.

### 5.3 Tailwind

- `tailwind.input.css:30-34` imports `./tailwind.panel_framework.css`. The generated file today holds
  `@source "./freedom_ls/panel_framework/templates";` and `@import "./freedom_ls/panel_framework/css/panel_framework.css";`
  (`tailwind.panel_framework.css:3-4`, gitignored at `.gitignore:32`).
- The command spec 4 delivered: `manage.py write_panel_framework_css`, output `tailwind.panel_framework.css` at `settings.BASE_DIR`. It writes `./relative` when the target is under `BASE_DIR` and an absolute path otherwise (`:28-33`),
  so the installed `.venv/lib/python3.13/site-packages/panel_framework/` gives a relative `./.venv/...` path (gitignored, so Tailwind skips scanning it without `not-ignored:`), and an editable install of the
  `main` checkout gives an absolute path outside the repo. No `not-ignored:` token in `:43-44`.
- `package.json:9-12`: `_write_active_theme` runs `uv run manage.py write_active_theme_css && uv run manage.py write_panel_framework_css`; `tailwind_build` runs `_write_active_theme`, then the main build, then `npm run panel_framework_css`.
  `panel_framework_css` (`:11`) builds the package's own `reference.css` from `./freedom_ls/panel_framework/tests/css/reference_input.css`; both paths vanish. That script moves to the package repo. FLS's
  `tailwind_build` becomes `_write_active_theme && npx @tailwindcss/cli ...`.
- `tailwind_watch` (`:10`) also runs `_write_active_theme`.
- `freedom_ls/base/tests/invariants/test_panel_framework_tailwind.py` (whole file) builds with the generated file, uses `REFERENCE_THEME`, and asserts the gitignore entries for both generated files; the `reference.css` assertion (`:92`) goes.
  `test_stylesheet_boundary.py:56` lists `./tailwind.panel_framework.css`.
- `tailwind.input.css:10` also has `@source "./freedom_ls/**/templates/**/*.html"`, which no longer matches the framework templates.

## 6. Dev loop, worktrees and the locked-rev check

### 6.1 Scripts

- `claude_plugins/fls-dev/scripts/install_dev.sh` (17 lines): `git submodule update --init --recursive` (`:7`), the pre-commit hook installer (`:11`), `rebuild_after_rebase.sh` (`:13`), `uv run manage.py migrate` (`:16`).
- `claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` (14 lines, `set -eu`, `#!/bin/sh`): `uv sync` (`:10`), `npm i` (`:11`), `npm run tailwind_build` (`:12`), `dev_db_init.sh` (`:13`).
  The editable-install step belongs between `:10` and `:11`: `tailwind_build` (`:12`) runs `uv run manage.py write_panel_framework_css` and so needs the package in place. `/bin/sh` and `set -eu` mean the new step needs POSIX syntax and an explicit `if [ -d "$PANEL_FRAMEWORK_DIR" ]`.
- `.claude/fls-dev/scripts/rebuild_after_rebase.sh` is a generated wrapper (`:1-19`) that `exec`s the plugin script; the project hook values name the wrapper (`.claude/sdd/config.md:5`, `:24`; `.claude/ds/config.md:30`).
- `.claude/settings.json:78-79,91-92,103-104` already allows the three wrapper forms prompt-free; the plugin-path forms in `claude_plugins/fls-dev/scripts/` are listed only for `concrete_pointer_move.sh` and `concrete_rollback.sh` (`:122,131,140`). A new script run from its plugin path needs its own allow lines in all three forms.
- `claude.sh:11-17` is the launcher; `CLAUDE_PLUGINS_LOADED=1 claude --plugin-dir ...`. There is no `env` block in the committed `.claude/settings.json` and no `UV_NO_SYNC` anywhere under `claude_plugins/` (`rg` finds none). The idea puts `UV_NO_SYNC=1` in per-machine settings; nothing in the repo records that today.
- **`uv run` is used by every automated path**: `.claude/ds/scripts/run_tests.sh`, the CI jobs, `package.json:9` and, importantly, the pre-commit hook shim `claude_plugins/django-stack/scripts/install_pre_commit_hook.sh:29`
  (`exec uv run --project "$root" pre-commit hook-impl ...`). Without `UV_NO_SYNC=1` in the committing environment each commit re-syncs the venv. This is the Spike 1 trigger; it also decides whether the locked-rev check
  sees the editable copy or the locked copy.
- `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md:7-13`: only 22 lines; says the Setup script is `install_dev.sh`; the overlay sections are "Per-worktree setup step" and "Per-branch databases". The idea says
  `UV_NO_SYNC=1` is "documented" there: that note is new text.

### 6.2 "Before landing" hooks

- Landing path: `sdd:finish_worktree` Step 1 requests the test runner with the request `before landing` and `<prepare>` = the `Pre-test rebuild` value (`claude_plugins/sdd/commands/finish_worktree.md:83-106`).
  In this repo that value is `.claude/fls-dev/scripts/rebuild_after_rebase.sh` (`.claude/sdd/config.md:24`). The runner resolves `before landing` to a checkpoint (`claude_plugins/django-stack/resources/test_runner.md:25-39`) and runs `<prepare>` for `tier: targeted` and `tier: full`
  only; **`tier: none` runs neither the prepare script nor any check** ("run nothing").
- The same `rebuild_after_rebase.sh` is also the Setup script's child (`install_dev.sh:13`) and `/ds:rebase_main` Step 8 (`.claude/ds/config.md:30`). A locked-rev check put inside it would fail
  at Setup (when `uv sync` has just installed the locked copy and the editable link is fresh, which passes) but also on every rebase, not just at landing, and not at all on a `tier: none` landing.
- Hooks that exist and could carry the check, without touching generic plugins: (a) `.claude/sdd/config.md` `Pre-test rebuild` pointing at a new fls-dev wrapper that calls `rebuild_after_rebase.sh` then the check; (b) a pre-commit local hook
  next to `app-map-fresh` (`.pre-commit-config.yaml:70-84`) but the idea rejected blocking commits; (c) a `[tool.test_tiers]` test (`tests/` is where plugin scripts are tested; `[[tool.test_tiers.tooling]]` at `pyproject.toml:149-155` maps
  `claude_plugins/*/scripts/**` to `tests`); (d) the sdd `Documentation Hooks` / `Front-end check` style hooks do not run at landing. (a) is closest to the answers.md decision ("an fls-dev check when a worktree lands").
- The check is itself generic-plugin-clean only if it lives under `claude_plugins/fls-dev/scripts/` (FLS name allowed there) and is wired through `.claude/sdd/config.md`, per `CLAUDE.md`.

## 7. `update_upgrade_notes` flag schema

`claude_plugins/fls-dev/commands/update_upgrade_notes.md:18-35` (frontmatter keys, in order): `requires_migrations`, `requires_template_review`, `changed_template_paths: []`,
`requires_settings_change`, `changed_settings: []` (block-sequence form with `# hard` or `# optional` comments when populated), `requires_package_upgrade`, `changed_packages: []`
(`package==version` entries), `requires_npm_install`, `changed_npm_packages: []` (`package@version`), `requires_tailwind_rebuild`. Body: `# Upgrade notes: <spec-name>`, `## Breaking changes`, `## Manual steps`.

- `changed_packages` is documented as `package==version` (`:51`), but this spec's package is a git tag; the entry will read `django-panel-framework @ git+https://github.com/preludetech/django-panel-framework.git@v0.1.0` or
  `django-panel-framework==0.1.0` with a note. The schema does not say which; the spec should fix one form.
- `requires_template_review` / `changed_template_paths` are about templates a downstream project typically overrides under `freedom_ls/`; the framework's templates leave `freedom_ls/` (paths unchanged as template names but moved on disk).
  Downstream copies that override `panel_framework/...` templates stay valid by name.
- Step 4 verification (`:109-125`): every name in the notes is resolved against the tree. The notes must name `panel_framework` (new `INSTALLED_APPS` entry), the new
  Tailwind import, the removed `freedom_ls.panel_framework` entry in `INSTALLED_APPS` and the `config/urls.py` include (`:97`), the check IDs (2.5) and the migration name of the drop (section 4).
- The package's `CHANGELOG.md` carries the same four boolean flags (idea), so the keys named there are `requires_migrations`, `requires_template_review` with `changed_template_paths`, `requires_settings_change`, `requires_tailwind_rebuild`.

## 8. Other repos (read-only)

### 8.1 `/home/sheena/workspace/lms/freedom_ls_infra/fls-base/Dockerfile` (91 lines)

- Stage 1 `node:20-slim AS frontend-builder` (`:4`): `npm install`, `COPY . .`, `npm run tailwind_build` (`:19-22`). It is pure Node, but **FLS's `npm run tailwind_build` runs `uv run manage.py ...` via `_write_active_theme`**
  (`package.json:9`), which a Node-only image cannot do. That stage is already inconsistent with FLS's own `package.json`; the image takes whatever `package.json` is in its build context
  (the concrete project's, which has no `_write_active_theme`: `freedom-ls-concrete-template/package.json:13-14`).
- Stage 2 `python:3.13-slim` (`:26`): `apt-get install -y libpq-dev gcc gosu` (`:35-39`, **no `git`**); `COPY --chown=appuser:appuser pyproject.toml ./` (`:52`); `uv pip install --system -r pyproject.toml && uv pip install --system gunicorn`
  (`:55-56`). `-r pyproject.toml` reads `[project].dependencies` only, so the PEP 508 form is required. `git` goes on the apt line at `:35-39`.
- It then `COPY . .` (`:59`) and copies `tailwind.output.css` in from stage 1 (`:62`).

### 8.2 `/home/sheena/workspace/lms/freedom-ls-concrete-template/Dockerfile` (88 lines)

- Stage `tailwind-builder` (`node:22-slim`, `:6-17`): `npm ci`, `COPY . .`, `npm run tailwind_build`, with the comment (`:10-15`) that the `@import`/`@source` paths must resolve inside the copied tree.
- Stage `python-builder` (`ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim`, `:23`): **no `git` install** (`rg git` finds none in the file). `uv sync --frozen --no-install-project --no-install-package freedom_ls` at `:31-34` is the third-party layer;
  the git dependency would be fetched there (a `--no-install-package freedom_ls` does not skip `django-panel-framework`). So the idea's open question has an answer on this evidence: **yes, `git` must be installed in this stage**, and the stage
  must come before Tailwind (`:42` copies `tailwind.output.css` from stage 1 after the Python stage; the split puts the Python deps phase earlier and feeds Tailwind from it).
  Compare First-Class's Dockerfile (8.4), which installs `git` for a different reason (`:32-36`).
- Phase 2 `uv sync --frozen` (`:41-44`) installs `freedom_ls` editable from the submodule; runtime stage copies `/app` (`:72`), so `.venv` including `panel_framework` copies through.
- `freedom-ls-concrete-template/tailwind.input.css` (47 lines): `@source "./submodules/Freedom-LS/freedom_ls/**/templates/**/*.html"` (`:20`) and `**/*.py` (`:26`), local sources, the default theme import (`:37`) and the custom theme (`:43`).
  **It imports no panel-framework CSS and does not use the generated file**; its `package.json` (`:13-14`) has only `tailwind_watch` and `tailwind_build` with no `manage.py` step. After the move its template scan no longer
  covers the framework templates, and the framework CSS (`.panel-surface` and friends) is not imported at all (it never was). So the template needs both an `@source not-ignored:` for the installed package and
  an `@import` of its CSS, or the generated-file mechanism plus a `manage.py` step in its `package.json`.
- `freedom-ls-concrete-template/config/settings_base.py:99` has `"freedom_ls.panel_framework",` in `INSTALLED_APPS`; its `config/urls.py` has no panel include.
- `pyproject.toml:77-78` `[tool.uv.sources] freedom_ls = { path = "submodules/Freedom-LS", editable = true }`; `testpaths = ["tests"]` (`:84`).

### 8.3 First-Class (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`)

- `pyproject.toml:8` `"freedom_ls"` dependency; `:104` `freedom_ls = { path = "submodules/Freedom-LS", editable = true }` under `[tool.uv.sources]`; `testpaths` includes the submodule (`:119`); several `--deselect submodules/Freedom-LS/freedom_ls/...` lines
  (`:154-157`) none of which name the framework. No direct `panel_framework` import: `rg panel_framework` hits only `config/settings_base.py:135` (`"freedom_ls.panel_framework",`), `config/urls.py:105`
  (`path("panel-framework/", include("freedom_ls.panel_framework.urls"))`), `.gitignore:41` (`tailwind.panel_framework.css`), a comment at `.github/workflows/build-and-push.yml:67` and spec history under `spec_dd/`. It has
  no `apps/` code importing the framework.
- `tailwind.input.css:47-54`: the framework CSS is imported straight from the submodule (`@import "./submodules/Freedom-LS/freedom_ls/panel_framework/css/panel_framework.css";`) with a comment explaining why the generated file is not used:
  "the Dockerfile's tailwind-builder stage is pure Node and cannot run manage.py. Its templates are already covered by the submodule @source glob at the top." After the move **both halves break**: the import path no longer exists and the template glob
  no longer matches. `@source "./submodules/Freedom-LS/freedom_ls/**/templates/**/*.html"` (`:20`) is at `:20`; there is no `not-ignored:` anywhere in this file (comment at `:7-16` discusses the option).
- `Dockerfile` (First-Class): Node-only `tailwind-builder` `:6-22`; `python-builder` `:28` already installs `git` (`:32-36`, build-time only, for `build_legal_docs_manifest`) before `uv sync --frozen --no-dev --no-install-project --no-install-package freedom_ls` (`:45`).
  So First-Class needs no `git` change for the package fetch; it needs the Tailwind-stage change.
- First-Class's `package.json` (`:12-15`) has `tailwind_watch` and `tailwind_build` only, same as the template (no `manage.py` step).
- CI: `.github/workflows/build-and-push.yml:135,203` `submodules: recursive`; `:142` `uv sync --frozen` (no `--locked`).
- `/home/sheena/workspace/lms/freedom-ls-concrete-template` and First-Class are the two concrete projects `.claude/fls-dev/config.md` lists (only First-Class is listed there: `.claude/fls-dev/config.md:5`).

## 9. The local package checkout

`/home/sheena/workspace/software_factory/django-panel-framework.git` exists.

- It is a **bare repo** (`config:4`) with `[remote "origin"] url = git@github.com:preludetech/django-panel-framework.git` (`config:5-6`), so the remote is SSH, not the HTTPS URL used in the PEP 508 line.
- `packed-refs`: one ref, `refs/heads/main` at `fda431b876b6805f38bf9919a8a739b69d52b2f7`. No tags, no other branches.
- One worktree, `main/`, registered under `worktrees/main/`. Its content is a `.git` file and an **empty** `README.md` (0 bytes). Nothing else.
- The GitHub page `https://github.com/preludetech/django-panel-framework` is public, one commit on `main`, only `README.md`, no licence, no tags or releases (fetched this run). Local and remote therefore agree on the one empty-README commit
  (`fda431b`), unverified by hash.
- Consequences: no `pyproject.toml`, no `LICENSE`, no `CHANGELOG.md`, no `.github/` exist; the fresh import commit in `answers.md` (first row) starts from this single commit. The `PANEL_FRAMEWORK_DIR` default
  (`/home/sheena/workspace/software_factory/django-panel-framework.git/main`) exists today as a directory but cannot be installed (`uv pip install -e` fails without a `pyproject.toml`); the "skip with a message when the directory is missing" test
  must also cover "present but not a project".

## 10. Remaining small items

- `freedom_ls/panel_framework/management/commands/write_panel_framework_css.py:41`, the migration `0002:10` dependency, `checks.py` IDs, `apps.py:6,7`, `config.py:17,42` and the 65 dotted prefixes in app code plus 116 in tests are the package-side rewrite; they belong to the package repo's import commit.
- Test layout in the package: nothing in FLS pins where `tests/` ends up (inside the app dir today); the wheel test the idea asks for has to decide whether `tests/` ships (1.5 says FLS imports `tests.invariants.template_rules` and reads `tests/playwright/helpers.py`).
- Generated-artefact ownership: after the move `tailwind.panel_framework.css` stays FLS-side (`.gitignore:32`); `reference.css` becomes package-side.
- `docs/app_structure.md:3` says the file is generated by `/app_map`; `claude_plugins/django-stack/scripts/generate_app_map.py` exits non-zero in `--check` mode until regenerated (CI lint `:43`).

Sources (web): https://github.com/preludetech/django-panel-framework (fetched for section 9).

status: ok
