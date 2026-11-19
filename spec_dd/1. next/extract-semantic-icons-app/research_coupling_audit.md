# Coupling audit: extracting `freedom_ls/icons/` into a standalone package

Scope: what ties `freedom_ls/icons/` to FLS, and what must change so another Django project can install it, set its own custom icons, and add new semantic names without editing package code. All paths are relative to the repo root unless absolute.

## Summary

The app is small and already close to portable. Its only `freedom_ls.*` import outside itself is one line, `from freedom_ls.base.app_settings import AppSettings, Setting` (`freedom_ls/icons/config.py:3`). Everything else is intra-app `freedom_ls.icons.*` imports, which become a rename.

The real blockers to the two stated goals are not FLS imports. They are closed, hard-coded registries.

- **Semantic names are a module constant.** `SEMANTIC_ICON_NAMES` (`semantic_names.py:1`) is a closed `set[str]`. It is consulted in `render.py:138`, `checks.py:112,136`, and outside the app in `content_engine/icon_validation.py:125,156`. Four hand-written mappings (`mappings.py:10,76,142,208`) must have exactly the same keys, enforced by check `icons.E007` and tests. A host cannot add a name without editing the package.
- **Custom icons.** `FREEDOM_LS_ICON_OVERRIDES` only re-points an existing semantic name to a glyph in the active Iconify set. Overrides are rejected (`icons.E005`) if the key is not already a semantic name. There is no way to supply an icon that is not in one of the four `@iconify-json` packages (e.g. a project SVG). The only escape is a whole-backend replacement via `FREEDOM_LS_ICON_BACKEND`, which loses `build_svg`, the literal-glyph path in `render_icon` and the checks.
- **Icon sets are a closed registry.** `PACKAGE_MAP` (`loader.py:23`) and `ICON_SETS` (`mappings.py:298`) are module-level dicts. A host cannot register a fifth set.
- **File-system assumption.** Icon data is read only from `BASE_DIR/node_modules/@iconify-json/<pkg>/icons.json` (`loader.py:31-35`). A pip-installed package has no `node_modules`. This needs a settable data directory, or the Iconify JSON bundled or fetched via a Python dependency.
- **Domain names baked into generic registry.** 13 of the 63 names are FLS-domain (lists below). Those names are referenced by FLS templates and models, so they cannot simply be deleted from the package. They must move to an FLS-supplied registration.
- **Settings prefix.** `FREEDOM_LS_ICON_*` is FLS-branded. Renaming is a breaking change for First-Class (`config/customisation.py:42,57`) and every FLS doc and skill.

The host-side surface FLS depends on is: `<c-icon name=...>` (cotton component), `{% icon %}` tag, `render_icon()`, `get_icon_backend()`, `load_iconify_data()`, `ICON_SETS`, `SEMANTIC_ICON_NAMES`, `IconResolutionError`, and config attribute `FREEDOM_LS_ICON_SET`. Usage is broad: 170 `<c-icon` occurrences in 84 files, plus `icon_left`/`icon_right` on `c-button`.

## Coupling table

Size: S under 1 hour, M a few hours, L a day or more or involves a design decision.

| # | Item | Where | file:line | What must change | Size |
|---|------|-------|-----------|------------------|------|
| 1 | `AppSettings`/`Setting` import (the only outside-app `freedom_ls` import in non-test code) | `icons/config.py` | `config.py:3` | Vendor a ~40-line settings reader into the package, or use plain `getattr(settings, ...)`. The base class is generic (`base/app_settings.py:11-59`) but lives in FLS `base`. Note `AppSettings.__getattr__` treats empty string and `None` as unset. | S |
| 2 | Settings names `FREEDOM_LS_ICON_SET`, `_OVERRIDES`, `_BACKEND` | `config.py:7-15`, `backend.py:93,94,136`, `render.py:40`, `checks.py:29,57,98,102,153`; FLS `config/settings_base.py:67`; First-Class `config/customisation.py:42,57`; `contrib/conformance/test_theme.py:26` | many | Decide the package prefix (e.g. `ICONS_*`). Either break and migrate, or accept both with the old as deprecated alias. | M |
| 3 | `BASE_DIR` / `node_modules/@iconify-json/<pkg>/icons.json` path | `loader.py:31-35` | `loader.py:34` | Replace with a settable directory setting (default under `BASE_DIR/node_modules` for backward compatibility) and/or ship the JSON via a Python dependency. Also affects check E002 hint (`checks.py:46`: "npm install @iconify-json/..."). | M |
| 4 | `PACKAGE_MAP` closed registry (set name to npm package) | `loader.py:23-28` | `loader.py:23` | Make registerable (setting or `register_icon_set()` in `AppConfig.ready`). Used by `checks.py:20,30`. | M |
| 5 | `ICON_SETS`, four hand-written mappings, variant tables | `mappings.py` | `mappings.py:10-315` | Keep the four built-in sets in the package, but allow hosts to add or extend sets via a registry. Per-set mapping must stop being required to cover exactly `SEMANTIC_ICON_NAMES` (see 6). | L |
| 6 | `SEMANTIC_ICON_NAMES` closed set | `semantic_names.py` | `semantic_names.py:1`; used `render.py:25,138`, `checks.py:22,112,136`, `content_engine/icon_validation.py:20,125,156`, `content_engine/schema.py:414`, `claude_plugins/fls-content/validate/schema.py:728` | Make the effective name set = package generic names + host-registered names (setting such as `ICONS_EXTRA_NAMES = {name: {set: glyph}}` or a registry fed from AppConfigs). Every consumer must call a function (`get_semantic_names()`), not import a constant. Host-added names need a mapping per set, or a defined fallback when the active set lacks one. | L |
| 7 | Custom icon not in any Iconify set (project SVG) | `backend.py:34-78`, `render.py` | `backend.py:53-61` | No hook today. Add either a host-supplied Iconify-format JSON file or dict (extra "set" with prefix, merged into `load_iconify_data`), or a `custom icons` setting mapping semantic name to SVG body. Reuse `_validate_svg_body` (`backend.py:14`). | L |
| 8 | Custom backend hook | `backend.py:128-140` | `backend.py:136-140` | Already generic: `import_string` of a dotted path, `IconBackend.render(semantic_name, variant, css_class, aria_label)` contract. Needs only the settings rename (2). Docs in `custom-icon-backend.md` import `freedom_ls.icons.backend`. `functools.cache` means tests must `cache_clear()`. | S |
| 9 | System checks and ids | `checks.py` | `checks.py:25-168`; ids `icons.E001-E007`, `icons.W001` | The id prefix is the AppConfig label (`icons`). Keep label `icons` if the package is `icons`, or the ids change. `contrib/conformance/tests/test_app_labels.py:60` constructs `AppConfig("freedom_ls.icons", ...)` and must change. E005/E007 depend on the closed registries (4, 5, 6); E002/E003 depend on 3. | M |
| 10 | AppConfig | `apps.py` | `apps.py:5` | `name = "freedom_ls.icons"` becomes the package name; add explicit `label = "icons"` to keep check ids and dotted references stable. `INSTALLED_APPS` entries in FLS `config/settings_base.py:124` and First-Class `config/settings_base.py:114`. | S |
| 11 | Cotton component `icon.html` | `icons/templates/cotton/icon.html` | `icon.html:1-21` | Generic. The component name `c-icon` is global in cotton's namespace, so the package depends on `django-cotton` being installed (`INSTALLED_APPS`, loaders). Comment names `freedom_ls/icons/semantic_names.py` (`icon.html:8-9`). Declare django-cotton as a dependency or document it as a host requirement. | S |
| 12 | `icon_tags` templatetag library | `templatetags/icon_tags.py` | `icon_tags.py:4,9-20` | Generic, imports only `freedom_ls.icons.backend`. Library name `icon_tags` is global; fine. The FLS invariant forbids `{% load icon_tags %}` outside `icon.html` (see tests below). | S |
| 13 | `render_icon()` 5-step resolver | `render.py` | `render.py:91-182` | Generic in logic but docstring says "for the Freedom Learning System" (`render.py:1`). Course icon-specific semantics (`icon` + `icon_fallback`) are used by `content_engine`; keep but decouple docs. | S |
| 14 | Docstring/error text branding | `render.py:1`, `checks.py:1`, `backend.py:43-44` | | Reword. | S |
| 15 | FLS callers that import package internals | `content_engine/course_icon.py:18`, `icon_validation.py:18-20`, `templatetags/content_tags.py:15`, `contrib/conformance/test_theme.py:22-24`, `accounts/tests/test_legal_doc_view.py:12` (`_cache`), tests mocking `freedom_ls.icons.render.load_iconify_data` / `.backend.load_iconify_data` (`content_engine/tests/test_course_icon.py:41,45`, `icons/tests/test_render.py:38,42`, `icons/tests/test_backend.py:105,123`) | | Import path rename. Private `_cache` (`loader.py:21`) is reached across apps; expose a public `clear_cache()`. `icon_validation.py` validates `Course.icon` against `SEMANTIC_ICON_NAMES`, `ICON_SETS`, `load_iconify_data`: needs the registry function API (6). | M |
| 16 | FLS test conftest reaching icon loader | `freedom_ls/conftest.py:348-355` | `conftest.py:351-355` | Fixture sets `settings.BASE_DIR` to a tmp path and symlinks `node_modules` so the loader still works. With a settable data dir this workaround can use that setting instead. | S |
| 17 | Package build and data distribution | `pyproject.toml:82` (FLS excludes `node_modules*`), `package.json:4-7` | | New package needs its own `pyproject.toml`, templates and templatetags included as package data, and an answer for the Iconify JSON (see open questions). | M |
| 18 | Docs and skill | `claude_plugins/fls-dev/skills/icon-usage/**`, `docs/product/configuration-and-extension.md:9,50,143` | | Split: generic usage and configuration docs go with the package; FLS-domain names guidance stays in the fls-dev skill. See section 8. | M |

## 1. Detail: imports, settings, file system, hooks

Imports from `freedom_ls.*` outside the app, in non-test package code: one, `freedom_ls.base.app_settings` (`config.py:3`). `app_settings.py` imports only Django (`settings`, `checks`, `ImproperlyConfigured`), so it is trivially copyable. `required_settings_errors` (`app_settings.py:62`) is unused by icons since no setting is required.

Settings read: `FREEDOM_LS_ICON_SET` (default `"heroicons"`), `FREEDOM_LS_ICON_OVERRIDES` (default `{}`), `FREEDOM_LS_ICON_BACKEND` (default `None`) via `config`. Directly: `settings.BASE_DIR` (`loader.py:34`). `BASE_DIR` is a convention not a Django built-in, so a host without it breaks with `AttributeError`.

System checks: `icons.E001` unknown set, `E002` JSON missing (hint tells user to `npm install`), `E003` mapping value missing, `E004` variant name missing, `E005` override key not a semantic name, `E006` override glyph missing, `E007` mapping keys mismatch, `W001` missing outline/solid variant. All registered in `AppConfig.ready` by importing `checks` (`apps.py:9`). E003/E004 iterate every semantic name for the active set (loads the JSON at check time, so any `manage.py` command that runs checks reads `icons.json`).

Custom backend hook: `backend.py:21-31` (`IconBackend.render` signature), `:128-140` (`get_icon_backend`). The `data-icon` attribute (`backend.py:67`) is relied on by FLS tests (`svg[data-icon='send']` etc. in `educator_interface/tests/`, `comms/tests/test_views.py`, `base/tests/components/test_pagination_component.py:144-145`). Custom backends must preserve it for those tests; the contract is undocumented in the `IconBackend` docstring.

Cotton `icon.html`: `<c-vars name="" variant="outline" class="size-5" aria_label="" />` then `{% icon name variant=variant css_class=class aria_label=aria_label %}`. `class` default `size-5` is a Tailwind class; the SVG always gets `class="inline ..."` (`backend.py:76`). Hosts need Tailwind to scan their own templates; the `size-*` and `inline` utilities are used by the package. The package must note this (Tailwind source scanning) or the `size-5` default will not exist in the host's CSS (SVG still has width/height attributes, see `backend.py:69-72`).

## 2. Tests in `freedom_ls/icons/tests/`

Whole app is covered by pytest; the project runs it via FLS settings and `freedom_ls/conftest.py` (plugin or autouse fixtures there are not icons-specific).

| Test file | Relies on | Notes |
|-----------|-----------|-------|
| `test_loader.py` | real `node_modules/@iconify-json/*` on disk via `BASE_DIR`; `_cache` private | Needs a data-dir fixture in the package. |
| `test_mappings.py` | loads real Iconify JSON, `ICON_SETS`, `SEMANTIC_ICON_NAMES` | Needs real icon data in the package test env. |
| `test_semantic_names.py` | every name x every set renders; `get_icon_backend.cache_clear()` | Becomes registry-driven; stays for the generic names. |
| `test_checks.py` | `override_settings` for `FREEDOM_LS_ICON_*`; patches `freedom_ls.icons.checks.iconify_json_path` | Rename settings and patch targets. |
| `test_backend.py` | `override_settings`; dotted path `freedom_ls.icons.tests.test_backend.MockBackend` (`:40,55,62`); patches `freedom_ls.icons.backend.load_iconify_data` | Rename; also needs `star`/`success` overrides in generic set. |
| `test_render.py` | `override_settings`; patches `render.load_iconify_data`, `backend.load_iconify_data` | Rename only. |
| `components/test_icon.py` | `django_cotton.compiler_regex.CottonCompiler` imported directly, and renders `<c-icon name="next" />` through `Template` without the cotton loader | Needs `django-cotton` in the package test deps. Uses `Context()` only; no FLS fixtures. |
| `invariants/test_no_font_awesome.py` | See below | |

No test in the icons app uses FLS models, site-aware fixtures, or `freedom_ls.conftest` fixtures. The coupling is the pytest-django settings module (`config` FLS test settings, which set `BASE_DIR`, `INSTALLED_APPS` with cotton and icons) and the real node_modules.

`invariants/test_no_font_awesome.py` scans `freedom_ls/**/*.html` (`TEMPLATE_DIR = ...parent x4`, `:4`) for Font Awesome classes, raw inline `<svg viewBox>` icons, and `{% load icon_tags %}` outside `icons/templates/cotton/icon.html` (`:50`, hard-codes the relative path `icons/templates/cotton/icon.html`). It is an FLS-wide policy test, not a package unit test. Recommend it stays in FLS (move to a path like `freedom_ls/base/tests/invariants/`), with `COTTON_ICON_PATH` updated to wherever the package's `icon.html` lives (or the check changed to "icon_tags is loaded only inside the icons package"). The package may ship its own narrower invariant: no inline SVG or `{% load icon_tags %}` in its own templates.

`contrib/conformance/test_theme.py:21-30` (`test_active_icon_set_resolves`) is a host conformance test exported from FLS; it uses `render_icon("", default_semantic="home")`, so `home` must remain a package-guaranteed name.

## 3. Semantic names classified (63 names)

Counts: generic 50, FLS-domain 13. Classification of borderline names is a judgement call (see open questions).

### Generic UI (keep in package)

Navigation (13): `next`, `previous`, `home`, `expand`, `collapse`, `menu_open`, `menu_close`, `menu`, `table_of_contents`, `dropdown`, `fullscreen`, `quick_view`, `open_page`.

Status (10): `success`, `error`, `warning`, `info`, `in_progress`, `complete`, `locked`, `rate_limit`, `maintenance`, `not_started`, `paused`. (`paused` is used by the `base/notification_categories.py:51` category, which is FLS data, but the name is generic.) That is 11 names; the count of status names in the source block is 11 (the `paused` entry makes it 11).

Actions (11): `check`, `check_all`, `close`, `retry`, `download`, `more_options`, `settings`, `edit`, `add`, `send`, `message`.

User/system (4): `user`, `notifications`, `mail`, `loading`.

Data display (7): `sort_asc`, `sort_desc`, `sort_neutral`, `boolean_true`, `boolean_false`, `search`, `filter`.

Trends/misc (3): `trend_up`, `trend_down`, `unknown`, `star`. (4 names.)

Generic total as listed: 13 + 11 + 11 + 4 + 7 + 4 = 50 names.

### FLS-domain (move to FLS registration)

`course`, `topic`, `form`, `cohort`, `achievement`, `deadline`, `price`, `notes`, `sentiment_good`, `sentiment_bad`, `audio_play`, `audio_playing`, `folder`.

That is 13 names. `folder` is arguably generic (content-type group in source comment), as are `notes` (used as a generic admonition icon, and in First-Class `config/customisation.py:90`), `sentiment_*` (feedback), `deadline` (could be "calendar/clock"), `price` (commerce), `achievement` (trophy/award). Total check: 50 generic + 13 domain = 63; source has 63 names (counted from `semantic_names.py` lines 3-75). The lists here are authoritative: **50 generic, 13 FLS-domain**.

Notes on classification:
- Used by name from generic FLS components that must keep working in a host: `check`, `close`, `dropdown`, `loading`, `menu`, `next`, `search` (panel framework host contract, `extract_panels_framework/research_packaging_and_distribution.md:94`), plus `add`, `filter`, `retry` (via `c-button icon_left`, same idea.md item 4). All are in the generic list.
- `notes` and `tip`-style admonition icons are chosen by `customisation.py` ADMONITION config, so `notes`, `star`, `info`, `warning`, `error`, `check` must resolve in any host that also uses FLS content.
- `course` is the hard-coded `default_semantic` for course icons (`content_engine/course_icon.py`, field help text in `content_engine/migrations/0001_initial.py:78`), so FLS content needs it registered at startup.

## 4. Who uses icons in FLS

Counts of `<c-icon` by app (templates only, from grep of `**/*.html`; total 170 across 84 files including icons tests, panel framework tests and standalone test templates):

| App | `<c-icon` | Notes |
|-----|-----------|-------|
| base | 24 | includes `cotton/button.html`, `callout.html`, `chip.html`, `error-page.html`, `partials/_toast.html` (dynamic names) |
| learner_interface | 36 | `course_form_complete.html` 9, `course_form_page.html` 6, `course_minimal_toc.html` 6, `course_status_label.html` 6, `deadline-label.html` 3 (dynamic `icon_name`) |
| panel_framework (templates) | ~33 | `data-table*.html`, `panel-*.html`, `sidebar_nav.html` (dynamic `item.icon`), `table_toolbar.html`, etc.; plus tests, invariants and `standalone_templates/cotton/*` stubs |
| comms | 17 | `notification_row.html:11` uses `notification.icon` |
| educator_interface | 11 | `course_outline_title.html:4` uses `object.icon` |
| content_engine | 10 | `course_details_hero.html:20` `stat_icon`; `audio.html` 3, `flashcard.html` 2 |
| course_applications | 8 | `claim_link_notice.html` 7 |
| form_engine | 5 | |
| course_interest | 1 | |
| icons (own tests and component) | 15 | |

`{% icon %}` tag directly: none outside `icon.html` (grep for `{% icon ` and `icon_tags` outside `icons/` found only the unrelated `course_icon_tags` library). `icon_left`/`icon_right` usage: 86 occurrences in 42 files (button, pagination, error pages, comms, content_engine file-download, picture, course_applications, educator_interface, form_engine, learner_interface, panel_framework table_toolbar 4, table_selection_bar, quick_view_host). Python usage of `freedom_ls.icons`: `content_engine/course_icon.py`, `icon_validation.py`, `templatetags/content_tags.py`, `contrib/conformance/test_theme.py`, tests in `accounts`, `content_engine`, `panel_framework` (override_settings only).

Dynamic names from data (the places where a name is not a literal in a template):
- `base/notification_categories.py:31` `NotificationCategory.icon: str`; instances use `course`, `paused`, `deadline`, `check_all` (`:44,51,61,69,78`). `comms/models.py:144` returns it; rendered in `notification_row.html:11`. Names are not validated against `SEMANTIC_ICON_NAMES` there (a bad name raises `KeyError` at render time).
- `content_engine/models/courses.py:220-229`: `Course.icon` (CharField 64) and `icon_fallback` (80), validated at `models/courses.py:364`, `schema.py:534`, `management/commands/content_save.py:567`. `educator_interface/.../course_outline_title.html:4` renders `{{ object.icon }}` straight to `c-icon`, bypassing `render_icon` (so a literal glyph there raises; possible latent bug, to confirm).
- Admonition config (`content_engine/templatetags/content_tags.py:36` `admonition_icon`, via `render_icon`) reads `icon` and `icon_fallback` from the `ADMONITION_*` setting (First-Class `customisation.py:79-101`).
- Panel framework `sidebar_nav.html:24` `item.icon`, `panel-empty-state.html:26`, `panel-attention-row.html:50`, `panel-avatar-chip.html:72` `fallback_icon` (host data).
- Learner interface `deadline-label.html` `icon_name`; `base/_toast.html:30` `icon_name`; `callout.html`, `chip.html`, `error-page.html` take `icon` attribute; `button.html` `icon_left`/`icon_right`.

Validation against `SEMANTIC_ICON_NAMES` outside the app: `content_engine/icon_validation.py:125,156` (course icon save-time validation; also the error message lists `sorted(SEMANTIC_ICON_NAMES)`). Documentation-only mentions in `content_engine/schema.py:414` and `claude_plugins/fls-content/validate/schema.py:728` (Pydantic field description). `claude_plugins/fls-content` is a generic content validator naming an FLS constant, which is itself a coupling.

## 5. Panel framework icon host contract

`spec_dd/2. in progress/extract_panels_framework-4-template-contract/idea.md:37-43` (item 4): the 21 static `c-icon` names the panel templates use, plus those via `c-button icon_left` (`add`, `filter`, `retry`), become a documented closed list; a system check in `freedom_ls/panel_framework/checks.py` is planned to render each icon name and report missing ones. Line 127 lists "Making the icon registry or token set open-ended" as out of scope for that spec, meaning this extraction is where openness lands. `freedom_ls/panel_framework/checks.py` has no icon references at present (grep returned no matches), so the check is not yet built. Panel framework tests carry stub components under `freedom_ls/panel_framework/tests/standalone_templates/cotton/` (button, chip, back-link, dropdown-menu) but no `icon` stub; they use the real `c-icon` via `override_settings(FREEDOM_LS_ICON_SET=...)` (`test_tables.py:2259,2279`, `test_modal_form_template.py:255,275`, `test_inline_record_form_template.py:98,110`).

How an icons package meets the contract:
- Host provides `c-icon` by installing the package (with cotton). The panel framework check calls `render_icon`/`get_icon_backend().render(name)` for each required name. With the package, the check can use a public helper `icon_names_missing(names) -> list[str]` instead of rendering.
- The required generic names (`check`, `close`, `dropdown`, `loading`, `menu`, `next`, `search`, plus `add`, `filter`, `retry` and the rest of the 21) must all stay in the package's generic list. None of them is in the FLS-domain list above.
- If the host passes custom names to panel components (`sidebar_nav item.icon`, `panel-empty-state icon`), they must be registered via mechanism 6.
- Panel framework dependency on `freedom_ls.icons` should be declared as optional/peer: `panel_framework` references the `c-icon` name only, not a Python import.

## 6. First-Class usage

Path: `/home/sheena/workspace/first_class/First-Class-LMS.git/main/config/customisation.py`.
- `:42` `FREEDOM_LS_ICON_SET = "phosphor"`.
- `:57` `FREEDOM_LS_ICON_OVERRIDES: dict[str, str] = {}` (empty, with a comment listing semantic names at `:49` pointing into `submodules/Freedom-LS/freedom_ls/icons/semantic_names.py`).
- `:79-101` `ADMONITION` config uses semantic names `info`, `star`, `warning`, `error`, `notes`, `check`, with a commented example using `icon_fallback "heroicons:scale"`.
- No `FREEDOM_LS_ICON_BACKEND` and no custom backend. `config/settings_base.py:114` lists `freedom_ls.icons` in INSTALLED_APPS; `:415-437` mention `icon` only as cotton-attribute allowlists for the landing page (`c-lp.check-item`, `c-lp.trust-item`).
- First-Class consumes FLS as a git submodule (`submodules/Freedom-LS/`). A pip package changes this only for icons if the host settings and dotted paths change. Landing-page components use `icon` attributes with semantic names, so the generic name set must stay stable.
- `Dockerfile:97-99,143-149`: references `icons.E002` and copies `/app/node_modules/@iconify-json` from the `tailwind-builder` stage into the runtime image because the loader reads it at request time ("all four sets included, ~8 MB, so `FREEDOM_LS_ICON_SET` and any `<set>:<glyph>` icon_fallback resolve"). A package that bundles or pre-processes icon data removes this Dockerfile special case.

## 7. package.json, npm, deploy

- `package.json:4-7` dev dependencies: `@iconify-json/heroicons ^1.2.3`, `@iconify-json/lucide ^1.2.101`, `@iconify-json/ph ^1.2.2`, `@iconify-json/tabler ^1.2.33`. `PACKAGE_MAP` maps `phosphor` to npm package `ph` (`loader.py:27`).
- CI runs `npm ci` in `.github/workflows/tests.yml:82,131,177` and `security.yml:85`, so tests and checks find the JSON on disk. No npm script is dedicated to icons; the icons are not built, only read.
- FLS repo has no root `Dockerfile` (grep failed); the deploy Dockerfile lives in First-Class (see section 6) and copies the whole `@iconify-json` directory.
- `pyproject.toml:82` excludes `node_modules*` from FLS packaging; so a pip install of FLS gets no icon data at all, a pre-existing gap the extraction must solve.
- Options for the standalone package (see open questions): (a) keep reading from `node_modules` via a data-dir setting; (b) depend on a PyPI Iconify data distribution if one exists (to verify, not checked here); (c) vendor the four JSON files (~8 MB) in the wheel; (d) generate trimmed JSON containing only the used glyphs (smallest, needs a build step and a way to add glyphs for host-added names).

## 8. Docs and skills

- `claude_plugins/fls-dev/skills/icon-usage/SKILL.md:13` names `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py` and "if nothing fits, add a semantic name".
- `.../resources/configuring-icons.md`: `FREEDOM_LS_ICON_SET` (supported values, `:5-8`), `FREEDOM_LS_ICON_OVERRIDES` (`:19-22`), and the steps for adding a semantic name (`:31`: "Add the name to `SEMANTIC_ICON_NAMES` in `freedom_ls/icons/semantic_names.py`" followed by mapping edits in all four sets). This is the "edit package code to add a name" workflow that the extraction must replace.
- `.../resources/custom-icon-backend.md`: `FREEDOM_LS_ICON_BACKEND`, `from freedom_ls.icons.backend import IconBackend` (`:15,18`), `get_icon_backend.cache_clear()` (`:39-46`).
- `claude_plugins/fls-dev/resources/testing.md:57`: pinning `FREEDOM_LS_ICON_SET` in tests.
- `docs/product/configuration-and-extension.md:9,50,143`: product docs; line 50 says "Adding another [set] requires supplying a mapping from FLS's semantic names to that library's identifiers." There is no `docs/**/*icon*` file.
- `.claude/agent-memory/ds-code-reviewer/project_admonition_widgets.md:14`: describes the 5-step resolution order (agent memory; leave alone).
- Per CLAUDE.md the generic plugins (`ds`, `sdd`, `productivity`) must not carry FLS knowledge, so package docs go in the package README, with FLS's domain-name guidance remaining in `fls-dev`. `claude_plugins/fls-content/validate/schema.py:728` refers to FLS names; check whether it is generic or FLS-specific.

## Proposed shape (for the spec author, not a decision)

1. Package `freedom-icons` (name TBD) with generic names only; settings reader vendored; `label = "icons"` kept.
2. Registry API: `register_semantic_name(name, {set: glyph})`, `register_icon_set(name, package, mapping, variants)`, plus a declarative setting for hosts, resolved lazily after app loading; `checks.py` generalised to the registry (E005/E007 keyed to the effective set).
3. Custom icons: support host-supplied extra Iconify-format JSON (or SVG body dict) as an extra data source consulted by `load_iconify_data`.
4. FLS keeps a small `AppConfig.ready` module registering its 13 domain names with mappings for all four sets, plus the policy invariant test.
5. FLS migrates settings names (decide alias vs break) and updates First-Class `customisation.py`.

## Open questions

1. Settings prefix: keep `FREEDOM_LS_ICON_*` (zero migration, FLS-branded in a generic package) or rename to `ICONS_*` with a deprecation alias? First-Class sets two of them.
2. Package name and import path (`freedom_icons`? `semantic_icons`?), and app label: keeping `icons` preserves check ids `icons.E001-E007` and the `icons.W001` warning that docs and the Dockerfile comment (`Dockerfile:97`) mention.
3. Where does the Iconify data come from: node_modules path setting, bundled wheel (~8 MB), a PyPI data package, or a build step that emits trimmed JSON? This also decides how a host adds a glyph from a set the package does not already include.
4. Should host-added names require a mapping for every registered set, or only for the active set with a defined fallback (default glyph, or the `unknown` name) plus a check warning? The current E007 demands exact key equality across sets.
5. Which borderline names are generic: `folder`, `notes`, `star`, `sentiment_*`, `deadline`, `price`, `achievement`, `audio_*`? Panel framework templates and First-Class admonitions already depend on `notes`, `star`, and others; moving a name out of the package breaks hosts that rely on them without FLS.
6. Should the `data-icon` attribute become part of the documented backend contract (FLS tests rely on it)?
7. Does the resolver's literal-glyph path and `<set>:<glyph>` fallback (course icon feature) belong in the generic package or in `content_engine`? `render_icon` currently serves only content (`Course.icon`, admonitions).
8. `icon_validation.py` (FLS `content_engine`) imports `ICON_SETS`, `load_iconify_data`, `SEMANTIC_ICON_NAMES` directly. Should the package expose a single `validate_icon_name(icon, icon_fallback)` so content_engine and `claude_plugins/fls-content` stop reaching in?
9. `educator_interface/.../course_outline_title.html:4` passes `object.icon` directly to `c-icon`, which only accepts semantic names. Confirm whether a literal glyph there raises, and whether the extraction should fix it by routing through `render_icon`.
10. Where does the Tailwind `size-*` default class and the `inline` class get scanned in a host project? Should `class` default change to something not tied to Tailwind?
11. `django-cotton` as a hard dependency vs optional (the `{% icon %}` tag works without it). Does the package ship both?
12. The panel framework's planned icon check (`panel_framework/checks.py`, item 4 of the template-contract spec) does not exist yet: build it against the package's public registry API, not against a re-render of every name.
13. Should `functools.cache` on `get_icon_backend()` and the module `_cache` in the loader be replaced by a settings-aware cache with a public `clear_cache()` (and `setting_changed` signal handler), given tests across three apps reach into them?

Counting caveat: grep counts of `<c-icon` and `icon_left` are line/occurrence counts from ripgrep per-file counts; per-app totals are summed by hand and approximate (+/- 2). The 63-name total and 50/13 split were counted by hand from `semantic_names.py`.

status: ok
