# Research: codebase impact of `extract-semantic-icons-app-1-standalone-app`

Question: what in the existing codebase does this work touch, reuse or conflict with? All paths are relative to the worktree root unless absolute. Line numbers were read from the worktree at HEAD `807f388c0`.

## 1. Summary: the findings that change the spec

1. **There are two precedents to copy, not one.** The panel framework already (a) carries its own copy of `AppSettings`/`Setting` at `freedom_ls/panel_framework/app_settings.py`, kept identical to `freedom_ls/base/app_settings.py` by an invariant test, and (b) runs its tests standalone through `freedom_ls/panel_framework/tests/standalone_pytest.ini` + `standalone_settings.py`, wired into CI as a second `pytest -c ...` step. Both match the idea's "copy" and "separate run" decisions.
2. **The main run does not exclude a directory today.** The panel framework's tests run in both the main run and the standalone run. The idea/answers want the icons tests to run only standalone. `[tool.pytest.ini_options] testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]` includes `freedom_ls/icons/tests`, so an exclusion (`--ignore`, `norecursedirs`, or a conftest `collect_ignore`) is new work. It also interacts with the test-tier selector, which targets `freedom_ls/icons/tests` by path (section 9).
3. **The `node_modules` packages ship no LICENSE file.** `node_modules/@iconify-json/*` contains `chars.json, icons.json, info.json, metadata.json, package.json, README.md, index.{js,mjs,d.ts}` and no `LICENSE`. Licence data is only `info.json` (`license.title/spdx/url`). The idea says "Lucide's own LICENSE is copied verbatim". That text cannot come from the installed package. It has to be fetched from the URL in `info.json` (`https://github.com/lucide-icons/lucide/blob/main/LICENSE`) or written from the upstream repo.
4. **The bundled subset cannot serve glyphs authors reference by literal name.** The loader's data also serves `render_icon`'s literal-glyph path and `<set>:<glyph>` fallbacks. `config/settings_dev.py:14` sets `"icon_fallback": "heroicons:scale"` and `scale` is not a mapped glyph. First-Class's Dockerfile copies all four sets precisely so such fallbacks resolve (quoted in section 12). With the bundled subset alone, such a fallback silently degrades to the default semantic icon (step 5 of `render_icon`), and `icon_validation.py` rejects it at save time. FLS's own settings and CI will need `SEMANTIC_ICONS_ICONIFY_DIR` pointing at `node_modules/@iconify-json` to keep today's behaviour.
5. **The `conftest.py` workaround is in `freedom_ls/conftest.py`, not the root `conftest.py`.** The root `conftest.py` only re-exports `freedom_ls.conftest` (`from freedom_ls.conftest import *`). The workaround is inside the `mock_legal_blobs` fixture, `freedom_ls/conftest.py:348-355`.
6. **The existing mirroring exemption for `freedom_ls/icons/tests/invariants/` becomes dead when the invariant leaves.** `test_organisation/mirroring_exemptions.txt:20` is checked for "an exemption that covers no violation" and fails. `freedom_ls/base/tests/invariants/` is already exempt (`mirroring_exemptions.txt:11`) and is the natural landing directory.

## 2. `freedom_ls/icons/` inventory

Files: `__init__.py`, `apps.py`, `backend.py`, `checks.py`, `config.py`, `loader.py`, `mappings.py`, `render.py`, `semantic_names.py`, `templates/cotton/icon.html`, `templatetags/icon_tags.py`, `tests/` (see section 10).

### `config.py` (18 lines)
- Only outside-app import in non-test code: `from freedom_ls.base.app_settings import AppSettings, Setting` (line 3).
- `class IconsConfig(AppSettings)` declares attributes `FREEDOM_LS_ICON_SET: str`, `FREEDOM_LS_ICON_OVERRIDES: dict[str, str]`, `FREEDOM_LS_ICON_BACKEND: str | None`, and `declared_settings` with defaults `"heroicons"`, `{}`, `None`. Module singleton `config = IconsConfig()`.
- Note `IconsConfig` is also the name of the `AppConfig` in `apps.py` (different module; no clash).

### `loader.py` (50 lines)
- `IconEntry`, `IconifyData` TypedDicts; module-level `_cache: dict[str, IconifyData] = {}` (line 21); `PACKAGE_MAP` (`heroicons->heroicons`, `lucide->lucide`, `tabler->tabler`, `phosphor->ph`).
- `iconify_json_path(pkg)` (lines 31-35): `Path(settings.BASE_DIR) / "node_modules" / f"@iconify-json/{pkg}" / "icons.json"`. This is the only `BASE_DIR` read in the app.
- `load_iconify_data(set_name)`: returns cached, raises `ValueError("Unknown icon set: ...")` for an unknown set, else `json.loads(json_path.read_text())` (raises `FileNotFoundError` when absent). It caches per set name.
- There is no public cache clear. Callers use `_cache.clear()`.

### `checks.py` (168 lines) and existing system check ids
Registered with `@register()` at import; imported from `AppConfig.ready` (`apps.py:9`). Ids in use (prefix is the bare label `icons`):

| Id | Function | Meaning |
|---|---|---|
| `icons.E001` | `check_iconify_json_exists` | unknown icon set |
| `icons.E002` | `check_iconify_json_exists` | JSON file missing; hint is `f"Run: npm install @iconify-json/{pkg}"` (`checks.py:46`) |
| `icons.E003` | `check_mapping_values_exist` | mapping value not in JSON |
| `icons.E004` | `check_mapping_values_exist` | variant-suffixed name not in JSON |
| `icons.E005` | `check_overrides_exist` | override key not a semantic name |
| `icons.E006` | `check_overrides_exist` | override glyph not in JSON |
| `icons.E007` | `check_mapping_keys` | mapping keys differ from `SEMANTIC_ICON_NAMES` |
| `icons.W001` | `check_variant_support` | outline/solid variant unsupported |

Free ids: `E008+` (for "`SEMANTIC_ICONS_ICONIFY_DIR` does not exist") and `W002+` (for deprecated-setting warnings). Reads of the setting: `checks.py:29,57,98,102,153`. `check_iconify_json_exists` uses `iconify_json_path` (line 20 import, line 41 use). `check_mapping_values_exist` and `check_overrides_exist` catch `(ValueError, FileNotFoundError)` around `load_iconify_data` and defer to E001/E002.
- Existing test `TestCheckIconifyJsonExists.test_missing_json_file_produces_e002` patches `freedom_ls.icons.checks.iconify_json_path` (`tests/test_checks.py:39`), so renaming or removing that function changes the test.

### `apps.py`
`IconsConfig(AppConfig)`: `name = "freedom_ls.icons"`, `verbose_name = "Icons"`, no explicit `label` (so label is `icons`). `ready()` imports `freedom_ls.icons.checks`.

### `backend.py`
Reads `config.FREEDOM_LS_ICON_SET` (line 93), `config.FREEDOM_LS_ICON_OVERRIDES` (94), `config.FREEDOM_LS_ICON_BACKEND` (136). `get_icon_backend` is `functools.cache`d (its docstring, line 133, names `override_settings(FREEDOM_LS_ICON_BACKEND=...)` and `cache_clear()`). Imports `load_iconify_data` from the loader (line 8).

### `render.py`
`_active_set_name()` returns `config.FREEDOM_LS_ICON_SET` (line 40). Imports `load_iconify_data` (line 23). The literal-glyph path (`_render_literal`) and `<set>:<glyph>` regex `_FALLBACK_RE` read icon data through the loader, so the subset's coverage affects them.

### `templates/cotton/icon.html`, `templatetags/icon_tags.py`
No change needed. How the invariant finds `icon.html`: see section 10.

### Mappings
`mappings.py`: `HEROICONS_MAPPING`, `LUCIDE_MAPPING`, `TABLER_MAPPING`, `PHOSPHOR_MAPPING` (63 keys each), `*_VARIANTS`, `ICON_SETS`. Not edited by this spec.

## 3. `freedom_ls/base/app_settings.py` (the helper to copy)

- 75 lines in total. Imports: `copy`, `typing.NamedTuple`, `django.conf.settings`, `django.core.checks.CheckMessage/Error`, `django.core.exceptions.ImproperlyConfigured`. **No `freedom_ls` imports.**
- Contents: `Setting(NamedTuple)` (`default: object = None`, `required: bool = False`), `AppSettings` with `declared_settings`, `__getattr__` (strips strings; treats `None` and `""` as unset; raises `ImproperlyConfigured` for a missing required setting; returns `copy.deepcopy(setting.default)`), `missing_required()`, and the module function `required_settings_errors(config, app_label)` (lines 62-75).
- Icons uses no required setting, so `missing_required` and `required_settings_errors` are unused by icons. The `CheckMessage`/`Error` imports exist only for `required_settings_errors`.
- **Precedent:** `freedom_ls/panel_framework/app_settings.py` starts with the same imports minus the `django.core.checks` ones (it defines `Setting` at line 10 and `AppSettings` at line 17). `freedom_ls/educator_interface/tests/invariants/test_framework_copies_match_base.py` keeps them in step: `SAME_SOURCE` contains `(base_app_settings.Setting, framework_app_settings.Setting)` and `(base_app_settings.AppSettings, framework_app_settings.AppSettings)`, compared with `inspect.getsource`. A copy in `freedom_ls/icons/` would have to either match source exactly (and be added to that list) or be allowed to differ (then not added). That test lives in `educator_interface`, which would then import `freedom_ls.icons`; `test_organisation/import_contracts.toml` may need a contract change (it is generated by `/ds:app_map`; section 9).
- `__getattr__` only resolves names present in `declared_settings`. Reading the deprecated `FREEDOM_LS_ICON_*` names through the same helper requires declaring them too, or reading `django.conf.settings` directly.
- Skill: `claude_plugins/fls-dev/skills/app-settings/SKILL.md` documents the convention (it does not mention copies).
- Apps using `AppSettings` today: 46 files match `AppSettings|app_settings` under `freedom_ls/` and the fls-dev skills; each app has a `config.py`.

## 4. Every reader of `FREEDOM_LS_ICON_*`

Grep over the repo excluding `node_modules` and `spec_dd` history.

**Python, app code (rename targets):**
- `freedom_ls/icons/config.py:7-9,12-14`
- `freedom_ls/icons/backend.py:93,94,133 (docstring),136`
- `freedom_ls/icons/checks.py:29,57,98,102,153`
- `freedom_ls/icons/render.py:40`
- `freedom_ls/contrib/conformance/test_theme.py:26` (`icons_config.FREEDOM_LS_ICON_SET`). This file is exported to downstream conformance suites (`__all__`, docstring). It will need the new attribute name.

**Settings:**
- `config/settings_base.py:67` `FREEDOM_LS_ICON_SET = "heroicons"` (comment at 65-66 names `freedom_ls.icons.mappings.ICON_SETS`).
- `config/settings_base.py:655` is a comment only, listing `FREEDOM_LS_ICON_BACKEND` as an example of the `import_string` seam.
- `config/settings_dev.py:14` has `"icon_fallback": "heroicons:scale"` (not a `FREEDOM_LS_ICON_*` setting; relevant to subset coverage).
- `config/settings_base.py:35` defines `BASE_DIR`; line 124 has `"freedom_ls.icons"` in `INSTALLED_APPS`.

**Tests (override_settings):**
- `freedom_ls/icons/tests/`: `test_backend.py` (40, 55, 62 with the dotted path `freedom_ls.icons.tests.test_backend.MockBackend`; 98, 115, 167, 176, 184, 193), `test_checks.py` (31, 37, 51, 56, 69, 74, 79, 86, 91), `test_render.py` (81, 103, 132, 167, 244, 265), `test_semantic_names.py:29`.
- `freedom_ls/content_engine/tests/test_course_icon.py:69, 91, 149, 170`.
- `freedom_ls/panel_framework/tests/components/test_inline_record_form_template.py:57,71`, `.../test_modal_form_template.py:256,278`, `.../test_tables.py:2259,2279`.

**Docs and skills:**
- `docs/product/configuration-and-extension.md:9, 50, 143`.
- `claude_plugins/fls-dev/resources/testing.md:57`.
- `claude_plugins/fls-dev/skills/icon-usage/resources/configuring-icons.md:5, 8, 19, 22` and line 38 ("Loader ... Reads and caches Iconify JSON data from `node_modules/@iconify-json/{pkg}/icons.json`").
- `claude_plugins/fls-dev/skills/icon-usage/resources/custom-icon-backend.md:8, 39, 46`.
- `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md:14` (agent memory; leave alone, per the earlier audit).
- `docs/app_conventions.md:31-36` calls icons "on its way to becoming the standalone `django_semantic_iconify` package" and says `icons` is the only entry in `UNPREFIXED_LABEL_ALLOWLIST`. That package name differs from the roadmap's `django-semantic-icons`. It is not part of this spec but is a stale name.

**Other repo (First-Class):** `/home/sheena/workspace/first_class/First-Class-LMS.git/main/config/customisation.py:42` and `:57` (section 12).

**Spec history (read-only, do not edit):** `spec_dd/3. done/2026-04-01_09:27_allow override icons/0. idea.md`, the 1-next idea files for specs 2-4, `research_coupling_audit.md`.

## 5. Reach-ins to `loader._cache` outside the app

Only one, plus two inside `freedom_ls/icons/tests/`:
- `freedom_ls/accounts/tests/test_legal_doc_view.py:12` `from freedom_ls.icons.loader import _cache`; fixture `cold_icon_cache` (lines 48-58) calls `_cache.clear()` before and after. Test `test_missing_doc_returns_404_with_a_cold_icon_cache` (line 79) exists only to prove the stubbed `BASE_DIR` still reaches `node_modules` (its docstring begins "The stubbed BASE_DIR must still reach the real node_modules.").
- Inside the app's tests: `tests/test_checks.py:16,21,23` and `tests/test_loader.py:5,10,12`.

Other `loader` imports are public (`load_iconify_data`): `content_engine/icon_validation.py:18`, `content_engine/tests/test_course_icon.py:17`, `content_engine/tests/test_icon_validation.py:17`, and the app's own modules.

The test-organisation import baseline records this edge: `test_organisation/import_baseline.txt:10` `freedom_ls.accounts.tests.test_legal_doc_view -> freedom_ls.icons.loader` and `test_organisation/import_contracts.toml:17` (the contract file is generated: "Generated by /ds:app_map. Do not hand-edit"). If the test keeps importing `freedom_ls.icons.loader` (for a public `clear_cache`), the edge is unchanged. If the fixture is dropped entirely, both entries go stale and have to be regenerated.

Note also `get_icon_backend` is `functools.cache`d and has its own `cache_clear()`. The idea only asks for a loader clear.

## 6. The `BASE_DIR` / `node_modules` workaround

`freedom_ls/conftest.py:325-364`, fixture `mock_legal_blobs`:
```
    # The icon loader reads BASE_DIR too, and pages rendered under this stub
    # (the 404 page among them) carry icons. Link the real node_modules into
    # the stub root so they resolve whether or not the loader's cache is warm.
    node_modules = Path(settings.BASE_DIR) / "node_modules"
    if node_modules.is_dir():
        (tmp_path / "node_modules").symlink_to(node_modules, target_is_directory=True)

    settings.BASE_DIR = tmp_path
    settings.LEGAL_DOCS_MANIFEST_PATH = None
```
Lines 348-353 (comment, `node_modules` lookup and symlink) are the part to delete. `settings.BASE_DIR = tmp_path` (355) stays because the legal-doc loader still needs it. The tests that use it: `freedom_ls/accounts/tests/test_legal_doc_view.py` (and any other `mock_legal_blobs` user). The root `/conftest.py` (22 lines) is a re-export plus `pytest_xdist_auto_num_workers`; no change is needed there.

## 7. `config/settings_base.py`, `package.json`, `pyproject.toml`

- `config/settings_base.py:35` `BASE_DIR = Path(__file__).resolve().parent.parent`; `:67` icon set; `:124` `"freedom_ls.icons"` in `INSTALLED_APPS`. Nothing else in `config/` mentions icons or iconify.
- `package.json` lists `@iconify-json/heroicons ^1.2.3`, `@iconify-json/lucide ^1.2.101`, `@iconify-json/ph ^1.2.2`, `@iconify-json/tabler ^1.2.33` under **`dependencies`** (lines 3-10), not `devDependencies` (which holds only `difit` and `wrangler`). The idea says FLS "keeps the four `@iconify-json` packages in `package.json` as dev dependencies". Moving them to `devDependencies` is therefore a change, and it affects `npm ci --omit=dev` style installs in First-Class's `tailwind-builder` stage (not inspected beyond the quoted line). Decide whether the spec moves them or leaves them under `dependencies`.
- `package.json` scripts: `tailwind_build`, `tailwind_watch`, `panel_framework_css`, `_write_active_theme`, `difit`. None relate to icons. CI runs `npm ci` (`.github/workflows/tests.yml:82`, also at lines 131, 177 and `security.yml:85` per the earlier audit).
- `pyproject.toml:79-82` `[tool.setuptools.packages.find]` has `include = ["freedom_ls*"]` and `exclude` containing `node_modules*`; there is no `package-data` / `include-package-data` / `MANIFEST.in` setting. Files such as `freedom_ls/icons/data/*.json` would be included in an sdist/wheel only through setuptools' VCS-file detection. First-Class consumes FLS as a git submodule, so a built wheel is not the consumer today; spec 3 owns packaging. Flag it for spec 3 only.
- `.gitignore:27` ignores `node_modules/`.

## 8. `freedom_ls/contrib/conformance/test_theme.py`

32 lines. `test_active_icon_set_resolves` (lines 21-30) imports `freedom_ls.icons.config.config`, `freedom_ls.icons.mappings.ICON_SETS`, `freedom_ls.icons.render.render_icon`; reads `icons_config.FREEDOM_LS_ICON_SET`; asserts the set is in `ICON_SETS`; calls `render_icon("", default_semantic="home")` and asserts `"<svg"`. It is exported to downstream projects (`__all__` at line 11), so a downstream running this conformance file against a newer FLS pulls the renamed attribute. Related: `freedom_ls/contrib/conformance/tests/test_app_labels.py:23` `UNPREFIXED_LABEL_ALLOWLIST = frozenset({"icons"})`, and line 60 `AppConfig("freedom_ls.icons", freedom_ls)`. Neither changes while label and name stay.

## 9. pytest configuration and test tiers

### Main run
`pyproject.toml:84-101`:
- `DJANGO_SETTINGS_MODULE = "config.settings_dev"`, `python_files = ["tests.py", "test_*.py", "*_tests.py"]`, `env = ["DJANGO_ALLOW_ASYNC_UNSAFE = True"]`.
- `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`.
- `addopts = "--strict-markers -m 'not ci_only and not weasyprint and not dev_tooling' --disable-socket --allow-hosts=127.0.0.1,::1 --tracing=retain-on-failure --screenshot=only-on-failure --dist loadfile"`.
- Markers include `needs_fls_host` ("needs FLS's real templates, icon set or URLconf; deselected when the panel framework's unit tests run on their own") and `fls_internal`.
- No `norecursedirs`, `--ignore`, or `collect_ignore` exists anywhere for the main run. Excluding `freedom_ls/icons/tests` from it is new wiring.

### Standalone precedent (panel framework)
- `freedom_ls/panel_framework/tests/standalone_pytest.ini`:
  ```
  [pytest]
  # Not one of the file names pytest discovers by itself: discovered, it would
  # switch any run aimed at these files to the standalone settings.
  pythonpath = ../../..
  python_files = test_*.py
  norecursedirs = playwright
  timeout = 300
  addopts =
      --ds=freedom_ls.panel_framework.tests.standalone_settings
      --nomigrations
      --strict-markers
      -m "not needs_fls_host"
      --disable-socket --allow-hosts=127.0.0.1,::1
  markers =
      needs_fls_host: ...
  ```
- `freedom_ls/panel_framework/tests/standalone_settings.py` (65 lines): `SECRET_KEY`, in-memory SQLite, `INSTALLED_APPS` (auth, contenttypes, sessions, sites, messages, admin, `django_cotton.apps.SimpleAppConfig`, the app, a stub app for the user model), `TEMPLATES` with `loaders` `django_cotton.cotton_loader.Loader` + filesystem + `app_directories` and `builtins: ["django_cotton.templatetags.cotton"]`, `COTTON_SNAKE_CASED_NAMES = False`, `ROOT_URLCONF`. An icons version needs far less: no database (no icons test uses `django_db`), `INSTALLED_APPS = ["django_cotton.apps.SimpleAppConfig", "freedom_ls.icons"]`, and the same `TEMPLATES` cotton loader, which is how `c-icon` resolves `icons/templates/cotton/icon.html` through `app_directories`. `DATABASES` still needs a value, or pytest-django must be run with a dummy.
- CI wiring: `.github/workflows/tests.yml:90-91`:
  ```
  - name: Run the panel framework's unit tests on their own
    run: uv run pytest -c freedom_ls/panel_framework/tests/standalone_pytest.ini freedom_ls/panel_framework/tests
  ```
  It runs after the main unit step (line 88: `uv run pytest -m "not playwright and not dev_tooling" -n auto --cov --cov-fail-under=92`). Note the main step carries a coverage gate of 92%; excluding `freedom_ls/icons` tests from the main run drops those lines' coverage unless the standalone step also collects coverage or the app is omitted from the gate (`[tool.coverage.run]` at `pyproject.toml:166`, not read in full).
- Documented in `claude_plugins/fls-dev/skills/testing/SKILL.md:119-125` as "a documented command, not a `[tool.test_tiers]` tier".
- `freedom_ls/panel_framework/tests/conftest.py:20-26` warns that this repo's namespace-package layout (no `freedom_ls/__init__.py`) makes pytest import test modules as `panel_framework.tests.*`; it uses relative imports for that reason. `freedom_ls/icons/tests/__init__.py` exists; the icons tests use absolute `freedom_ls.icons...` imports and the dotted path `freedom_ls.icons.tests.test_backend.MockBackend` in settings (`test_backend.py:40,55,62`). The standalone ini needs `pythonpath = ../../..` for the same reason, and the module-name hazard should be checked once.
- Importing guard precedent: `freedom_ls/panel_framework/tests/test_import_guard.py` AST-walks every `.py` in the app and fails on any `freedom_ls.*` import outside `freedom_ls.panel_framework` (`EXEMPT_DIRECTORIES = ()`). It is the model for "nothing in the icons app imports `freedom_ls.*` outside its own package"; it is exempt from mirroring (`mirroring_exemptions.txt:27`). A standalone-settings test run also needs a check that the settings module itself is the one loaded (`freedom_ls/panel_framework/tests/test_standalone_fixtures.py`).

### Tier config and runner scripts
- `.claude/ds/scripts/run_tests.sh` and `select_tests.sh` are thin wrappers that `exec uv run python claude_plugins/django-stack/scripts/run_tests.py` / `select_tests.py`; per the file header nothing project-specific may go in them. `.claude/ds/config.md` has no test configuration. Tier config lives in `pyproject.toml`:
  - `[tool.test_tiers]` `none = ["spec_dd/**", "claude_plugins/**/*.jsx"]`, `escalation = ["config/**", "freedom_ls/site_aware_models/**", "freedom_ls/content_base/**"]`, `markers = "not ci_only and not weasyprint"`.
  - `[tool.test_tiers.memory]` `max_workers = 4`, `per_worker_mb = 768`.
  - `[[tool.test_tiers.tooling]]` entries map plugin paths to test paths (none for icons).
- `select_tests.py` (`FULL_COMMAND = "uv run pytest -n auto"`, `TARGETED_PREFIX = "uv run pytest -n auto --no-cov"`) maps a changed app path to `tests_dir_of(app)` = `<app>/tests` (line 207-208, `decide_app_path`), then one decision per importer of that app, and composes one `uv run pytest -n auto --no-cov <markers> <paths>` line (`compose_command`, lines 408-425). **It only ever produces one pytest invocation with the project's main config.** A change under `freedom_ls/icons/` selects `freedom_ls/icons/tests`, which would then run under `config.settings_dev` and the main `addopts` unless the main config ignores it (then it would run nothing, silently) or a second command is added. The panel framework avoided the question by running its tests in both runs. The idea's "wired into the project's test tiers" needs a design: a `[[tool.test_tiers.tooling]]`-style entry cannot express a second `-c` invocation with what I read. I did not read `select_tests.py` past line 28 beyond the functions quoted, so this needs a close read before the spec fixes the approach. `claude_plugins/django-stack` is a generic plugin (CLAUDE.md: no FLS knowledge in generic plugins), so a tier change that needs script changes has to be expressed through per-project config, not by editing it for FLS.
- `claude_plugins/django-stack/scripts/run_tests.py` accepts a command that starts with `pytest`, `python -m pytest`, `python3 -m pytest` or `uv run pytest` (line 9 and 47-48 of the file), so `uv run pytest -c <ini> <dir>` is an accepted command.
- Other places that touch test layout and will need updates when tests move or exemptions change: `test_organisation/import_contracts.toml` has an `icons` contract (lines 242-248: `source_modules = ["freedom_ls.icons.tests"]`, forbidding imports from 36 other apps). The list excludes `site_aware_models`? No: it includes `freedom_ls.site_aware_models`. It does **not** forbid `freedom_ls.base`... it does include `freedom_ls.base`? The `icons` contract's forbidden list (line 248) does not contain `freedom_ls.base`. That is why `config.py`'s `freedom_ls.base` import is currently allowed and the `test_import_guard`-style test is what will newly enforce it. `test_organisation/mirroring_baseline.txt:53` has an empty `# icons` section; `mirroring_exemptions.txt:19-20` exempt `freedom_ls/icons/tests/components/` and `freedom_ls/icons/tests/invariants/`.
- Pre-commit hooks (`.pre-commit-config.yaml`) that new files must satisfy: `check-added-large-files --maxkb=1024` (each bundled JSON must stay under 1 MB), `trailing-whitespace` and `end-of-file-fixer` (these rewrite files; a verbatim Lucide LICENSE with trailing spaces would be changed on commit, and the generator must write a final newline and no trailing spaces), `detect-secrets` with `.secrets.baseline` (generated SVG path strings could trip entropy detectors; unverified), `ruff-check`/`ruff-format`, `mypy .` (a Python generator script under the repo is type-checked, so full type hints are required), `lint-imports`, `test-mirroring`, `app-map-fresh`.

## 10. `freedom_ls/icons/tests/`

Files: `__init__.py`, `components/{__init__,test_icon}.py`, `invariants/{__init__,test_no_font_awesome}.py`, `test_backend.py`, `test_checks.py`, `test_loader.py`, `test_mappings.py`, `test_render.py`, `test_semantic_names.py`.

- No icons test uses `django_db`, FLS models, site fixtures or `freedom_ls.conftest` fixtures. Imports outside the app: none (every `from freedom_ls...` import in `tests/` is `freedom_ls.icons.*`; confirmed by grep).
- What they need from the environment: real icon data (`test_loader.py` asserts all four sets load with `len(data["icons"]) > 0` and that `check-circle` is in heroicons; `test_mappings.py` and `test_semantic_names.py` render every name in every set), cotton (`components/test_icon.py:4` imports `django_cotton.compiler_regex.CottonCompiler` and renders through `Template(...).render(Context())`, so the cotton template loader must be configured to find `cotton/icon.html`), and `override_settings`.
- `_cache` use: `test_checks.py:16,21-23`, `test_loader.py:5,10-12`.
- `tests/test_render.py:161,198` and `content_engine/tests/test_course_icon.py:57,120`, `test_icon_validation.py:28,62,173,218,224` use the literal `phosphor:drone` (and `phosphor:halfshipped`, `phosphor:zzz`). The `test_render.py` cases build fake data through `_stub_iconify(monkeypatch, {...})` after loading the real sets (`load_iconify_data("heroicons")`/`("phosphor")` at lines 174-175) and add a `drone` entry. They therefore still work on the subset as long as the sets load. The `content_engine` tests were not read in full; confirm they stub the same way before relying on the subset in FLS's main run.
- The pre-existing `test_loader.py::test_all_sets_loadable` etc. will pass on the subset as well.

### `invariants/test_no_font_awesome.py` (71 lines)
- `TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent` with the comment `# freedom_ls/` (line 4). The four `.parent` calls take `invariants` -> `tests` -> `icons` -> `freedom_ls`. Moving the file to `freedom_ls/base/tests/invariants/` keeps the depth identical (also `invariants` -> `tests` -> `base` -> `freedom_ls`), so `TEMPLATE_DIR` would still resolve to `freedom_ls/` with no edit.
- `_get_template_files()` globs `TEMPLATE_DIR/**/*.html`.
- It finds `icon.html` through `COTTON_ICON_PATH = Path("icons/templates/cotton/icon.html")` (line 50), compared to `path.relative_to(TEMPLATE_DIR)` (lines 61-62) inside `test_no_direct_icon_tags_load_outside_cotton`. That relative path is hard-coded to the app's current location under `freedom_ls/`. This path stays valid while the app stays at `freedom_ls/icons` (this spec) and breaks in spec 3 when the app moves out; the test should locate the file from the app's own location (for example `Path(freedom_ls.icons.__file__).parent / "templates/cotton/icon.html"`) so the later move does not break it.
- It also runs `test_no_font_awesome_patterns_in_templates` and `test_no_inline_svg_icons_in_templates` over all FLS templates; these are FLS policy tests.
- It is under a directory the mirroring check exempts today. Landing options: `freedom_ls/base/tests/invariants/` (exempt, already holds repo-wide template invariants such as `test_app_templates_use_app_components.py`, `test_stylesheet_boundary.py`).

## 11. Real sizes and versions

### Installed `@iconify-json` versions (`node_modules/@iconify-json/*/package.json`)
| Set (FLS name) | npm package | Version | `license` field | Icons (`info.json`/earlier audit) |
|---|---|---|---|---|
| heroicons | `@iconify-json/heroicons` | 1.2.3 | MIT | 1288 |
| lucide | `@iconify-json/lucide` | 1.2.101 | ISC | 1694 (`info.json` `total`) |
| tabler | `@iconify-json/tabler` | 1.2.33 | MIT | 6092 |
| phosphor | `@iconify-json/ph` | 1.2.2 | MIT | 9072 |

These match `package.json` ranges (`^1.2.3`, `^1.2.101`, `^1.2.2`, `^1.2.33`). `info.json` `license.url` values: Heroicons `https://github.com/tailwindlabs/heroicons/blob/master/LICENSE`, Lucide `https://github.com/lucide-icons/lucide/blob/main/LICENSE`, Tabler `https://github.com/tabler/tabler-icons/blob/master/LICENSE`, Phosphor `https://github.com/phosphor-icons/core/blob/main/LICENSE`. The installed Lucide package alone does not carry the Feather MIT notice; per `info.json` the licence title is just "ISC".

### Byte sizes of `icons.json`: **not measurable with the tools I had**
I only had Read, Glob and Grep, which report no byte sizes. What I can state is the line count of each pretty-printed (tab-indented) file, from `grep -c ^`:
| File | Lines |
|---|---|
| `heroicons/icons.json` | 5181 |
| `lucide/icons.json` | 5978 |
| `tabler/icons.json` | 19030 |
| `ph/icons.json` | 27693 |
(57,882 lines in all.) The research file's byte figures (about 1 MB, 0.7-1 MB, 3-5 MB, 4-6 MB) are estimates and the First-Class Dockerfile comment says "~8 MB" for the four directories. Run `du -b node_modules/@iconify-json/*/icons.json` (or `wc -c`) before any size is quoted in docs; the spec's "measured, not estimated" rule needs that from a shell.

### Unique glyphs referenced by the four mappings (hand-counted from `mappings.py:10-272`, de-duplicated; each mapping has 63 keys)
| Set | Unique base glyphs | Variants in `*_VARIANTS` (non-`None` suffixes the checks E004 enforce) | Icon entries the subset must hold (base x (1 + suffixes)) |
|---|---|---|---|
| heroicons | 55 | `-solid`, `-20-solid`, `-16-solid` (3) | 220 |
| lucide | 56 | none (outline only) | 56 |
| tabler | 55 | `-filled` (1) | 110 |
| phosphor | 57 | `-fill`, `-bold`, `-light`, `-thin` (4) | 285 |
| **Total** | **223** | | **671** |

Counts are by hand and could be off by one or two; the generator's own output is the authority. The subset is therefore 671 of about 18,146 upstream icons (3.7%). All variant suffixes are mandatory because `check_mapping_values_exist` raises E004 for every `base + suffix` missing from the JSON, and `render_icon` raises `IconResolutionError` for a half-shipped literal glyph. Aliases are not read by the loader (it only reads `icons`, `width`, `height`, `prefix`), so the subset need not carry `aliases`. Several mapped names are only valid as `icons` entries in this version (for example lucide `search`, `menu`, `circle-question-mark`; these are verified by the existing E003 check passing today).

## 12. First-Class (`/home/sheena/workspace/first_class/First-Class-LMS.git/main`)

`config/customisation.py:38-57`:
```
###
# ICONS
# The icon set used throughout the UI. Valid sets (keys of
# freedom_ls.icons.mappings.ICON_SETS):
#   "heroicons" | "lucide" | "tabler" | "phosphor"
FREEDOM_LS_ICON_SET = "phosphor"
...
# Semantic names (see submodules/Freedom-LS/freedom_ls/icons/semantic_names.py):
...
FREEDOM_LS_ICON_OVERRIDES: dict[str, str] = {}
```
Lines 40, 49 reference module paths. The semantic-name list in the comment (lines 50-56) names `course_part`, which is not one of the current 63 names; stale, harmless. Line 82 documents `icon_fallback — optional explicit "<set>:<glyph>", e.g. "heroicons:scale"` and 101 `"icon_fallback": "heroicons:scale"` in a commented example. `config/settings_base.py:114` lists `"freedom_ls.icons"`.

`Dockerfile`:
- Lines 97-99: `# freedom_ls icons.E002, asserts that node_modules/@iconify-json/<set>/` / `# icons.json exists — and this stage deliberately has no node_modules, since` / `# the icon JSON is copied straight from tailwind-builder into the runtime` (inside the explanation of why `build_legal_docs_manifest` runs with `--skip-checks`). With bundled data and no `BASE_DIR` read, the `icons.E002` reason for `--skip-checks` goes away, but the comment says other checks also apply, so `--skip-checks` should not be removed without reading that stage.
- Lines 143-149 (the copy step):
  ```
  # The FLS icon renderer reads Iconify icon-set JSON from
  # BASE_DIR/node_modules/@iconify-json/<set>/icons.json at request-render time
  # (freedom_ls/icons/loader.py). node_modules is otherwise excluded from the
  # image (.dockerignore), so ship just the icon-set JSON: without it, every page
  # that renders an icon 500s with FileNotFoundError. All four sets are included
  # (~8 MB) so FREEDOM_LS_ICON_SET and any "<set>:<glyph>" icon_fallback resolve.
  COPY --from=tailwind-builder --chown=appuser:appuser /app/node_modules/@iconify-json /app/node_modules/@iconify-json
  ```
- The last sentence of that comment is the conflict from finding 4: dropping the copy removes the data that `"<set>:<glyph>"` fallbacks resolve against. The upgrade notes' statement that the Dockerfile "no longer needs to copy" is correct for the 63 semantic names, not for literal glyphs. For First-Class either (a) keep the copy and set `SEMANTIC_ICONS_ICONIFY_DIR`, or (b) accept the subset, with `icon_fallback` glyph literals restricted to the subset.

## 13. Deprecation precedent (panel framework) and existing upgrade notes

- The "keeps the old surface for one tag" rule is **stated but not yet applied** anywhere in code. It lives in `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md:114-116` ("Rename in tag N with an alias and a deprecation warning; remove in tag N+1."), and is repeated in `spec_dd/1. next/extract_panels_framework-5-package-and-install/idea.md:26` and `...-6-claude-plugin/idea.md:88`. No spec in `spec_dd/3. done/` implements it, and grep for `DeprecationWarning|warnings.warn|deprecat` in `freedom_ls/panel_framework/*.py` finds no deprecation code. So this spec is the first user of the rule, and the "system check warning" shape in `answers.md` is new design, not reuse.
- The closest existing model of check-based configuration messages is `freedom_ls/panel_framework/checks.py`: warnings `W001` (line 122, with a hint telling the host it can add the id to `SILENCED_SYSTEM_CHECKS`: `"... or add freedom_ls_panel_framework.W001 to SILENCED_SYSTEM_CHECKS if ..."`, lines 119-122), `W002` (200-205), `W003` (167). The `SILENCED_SYSTEM_CHECKS` hint wording is reusable. Panel framework ids use the prefix `freedom_ls_panel_framework`; icons uses the bare `icons`.
- Existing `upgrade_notes.md` examples to copy shape from:
  - `spec_dd/3. done/2026-08-27_12:32_prod_bucket_setup/upgrade_notes.md:7-8`: annotated block-sequence form, e.g. `  - STORAGES                          # hard: public, course_media and reports must be declared or model import raises ImproperlyConfigured; ...`.
  - `spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/upgrade_notes.md:8-9`: `  - INSTALLED_APPS   # hard: add "freedom_ls.content_base" ...`.
  - `spec_dd/3. done/2026-08-24_06:31_test_portability_4_upgrade_notes_and_docs/upgrade_notes.md:7-8` for `pyproject` setting entries.
  - `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/upgrade_notes.md` for the full frontmatter shape.
- Flag schema (`claude_plugins/fls-dev/commands/update_upgrade_notes.md:14-44`): `requires_migrations`, `requires_template_review` + `changed_template_paths`, `requires_settings_change` + `changed_settings` (block-sequence with inline `# hard:`/`# optional` comments), `requires_package_upgrade` + `changed_packages`, `requires_npm_install` + `changed_npm_packages`, `requires_tailwind_rebuild`. Rules that apply here: a renumbered/repurposed check id is a hard settings change naming `SILENCED_SYSTEM_CHECKS` (line 55) — this spec reuses `icons.E002` with new meaning and adds new ids, so a host that silenced `icons.E002` for the npm hint should be told; step 4 requires every named setting, check id and path to resolve in the tree at the end. For this spec: `requires_settings_change: true` with `FREEDOM_LS_ICON_SET`, `FREEDOM_LS_ICON_OVERRIDES`, `FREEDOM_LS_ICON_BACKEND` renamed (optional/soft since the old names still work, plus the new `SEMANTIC_ICONS_ICONIFY_DIR`), and probably `requires_npm_install: false`, as no npm package is added. The Dockerfile change is a manual step in the prose, not a flag.
- Spec-specific warning for the notes: the schema says `requires_npm_install` is for "new or updated npm packages"; this change makes the npm packages optional, which the schema has no flag for.

## 14. Other things the work touches

- `freedom_ls/content_engine/icon_validation.py:18-20,125,156` imports `ICON_SETS`, `load_iconify_data`, `SEMANTIC_ICON_NAMES`; `course_icon.py:18`, `templatetags/content_tags.py:15` import from `freedom_ls.icons`. These stay as they are; they read subset data unless FLS sets `SEMANTIC_ICONS_ICONIFY_DIR` (finding 4).
- `claude_plugins/fls-dev/skills/icon-usage/` must be updated in this spec for renamed settings and the loader note (`configuring-icons.md:38` says loader reads `node_modules`). Any fuller rewrite belongs to spec 4. `claude_plugins/fls-dev/skills/testing/SKILL.md` needs the new standalone icons command added beside the panel framework one (lines 119-125). Those two are FLS-specific plugin files, so editing them is allowed; `claude_plugins/django-stack`, `sdd` and `productivity` must not gain icons knowledge.
- `docs/app_conventions.md:31-36` says icons is becoming `django_semantic_iconify`; the roadmap says `django-semantic-icons`. Not owned by this spec but stale.
- `test_organisation/import_baseline.txt` and `import_contracts.toml` are generated by `/ds:app_map`; any change to a test import edge means regenerating them, not hand-editing.
- `.github/workflows/tests.yml` needs a new step for the standalone icons run (and still needs `npm ci` for the generator drift test and for FLS's `SEMANTIC_ICONS_ICONIFY_DIR`). `security.yml:85` also runs `npm ci`.
- Existing `scripts/` convention for maintainer scripts: **there is no top-level `scripts/` directory** (Glob `scripts/**/*` found nothing; the repo root contains `docs/`, `test_organisation/`, `tests/`, `config/`, `freedom_ls/`, `claude_plugins/`, `demo_content/`). Dev scripts live under `.claude/fls-dev/scripts/*.sh` (`dev_db_delete.sh`, `dev_db_init.sh`, `install_dev.sh`, `rebuild_after_rebase.sh`) and plugin scripts under `claude_plugins/*/scripts/`; plugin scripts are tested in `tests/` (`[[tool.test_tiers.tooling]]` entries at `pyproject.toml:136-142`). `freedom_ls/*/scripts` does not exist. `docs/build_product_docx.py` is the one Python maintainer script outside a plugin. A new `scripts/` at the root would be new, and `answers.md` says "e.g. `scripts/`". Note that the `tests/` directory plus a `tooling` tier glob would be the existing route for testing a script's pure function; the drift test in the idea imports it from the icons tests, which under standalone settings would import a module outside the app (outside `freedom_ls.icons`, so not caught by an AST guard that only forbids `freedom_ls.*`, but still outside "the app's tests run without FLS").

## 15. Things I could not establish

- Byte sizes of the four `icons.json` files (section 11).
- Whether `pytest --ignore=<dir>` still skips an explicitly named directory when the tier runner passes it as an argument. (I believe `--ignore` also applies to explicit arguments, so a directory both ignored in `addopts` and selected by a tier would run nothing; verify.)
- The content of `.secrets.baseline` and whether generated SVG strings trip detect-secrets.
- The remaining `content_engine/tests/test_course_icon.py` and `test_icon_validation.py` bodies (whether every literal glyph used is stubbed).
- First-Class's `.dockerignore`, `tailwind-builder` stage and CI, beyond the quoted lines.

status: ok
