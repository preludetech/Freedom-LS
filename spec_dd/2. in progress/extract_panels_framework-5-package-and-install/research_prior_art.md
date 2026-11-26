# Research: prior art for spec 5 (package and install)

Question: what has already been tried for this, here or elsewhere, and what happened?

Short answer: specs 1 to 4 did the decoupling and left spec 5 a mechanical move. One claim in
`idea.md` is contradicted by spec 4's probe: **`@source not-ignored:` is a build error in Tailwind
4.1.16**. Spec 4 already ships the generated file with a plain `@source "<path>"`. The earlier
extraction attempt in `django_apps/` was two abandoned half-packages with no lessons for this one,
apart from the "tidy them later" note.

## 1. Here: the earlier attempt, `/home/sheena/workspace/lms/django_apps/`

Contents (top level only; each holds a `.venv`, which is noise):

| Dir | State |
| --- | --- |
| `content_engine/` | `pyproject.toml` (`content-engine` 0.1.0, deps `django>=5.2.8`, `python-frontmatter`; dev group pytest, pytest-django, pytest-mock), a two-line `README.md` ("Add `content_engine` to installed_apps"), `content_engine.egg-info/`, and a stale `build/lib/content_engine/` holding models, views, migrations `0001_initial` and `0002_add_category_to_form_page`, management commands, tests. |
| `site_aware_models/` | `pyproject.toml` (`site-aware-models` 0.1.0; its deps list is a copy of content_engine's neighbours: django-click, django-unfold, markdown-headdown, nh3, pydantic, python-frontmatter), a README that only says "add `django.contrib.sites` and `site_aware_models` to INSTALLED_APPS", `site_aware_models.egg-info/`. |

What this tells us:
- Both are **path-style, hand-built, setuptools-defaults packages** (no `[build-system]`, no
  `LICENSE`, no CI, no tag, no changelog). The `build/` and `*.egg-info/` directories are
  `setuptools` output committed to nowhere in particular; they show an install was attempted but
  not a release.
- `content_engine/build/lib` stops at migration `0002`, while FLS's `content_engine` has since
  moved on (the spec 3 QA run notes "content_engine 0012 pending"). So the copy is **months stale
  and diverged**: nothing was kept in step. That is the failure mode the idea's "edit live in the
  package, bump the tag, run the FLS suite" loop is built against.
- The dependency list of `site_aware_models` is wrong for its stated purpose (it lists unfold,
  pydantic and nh3, which it does not need): a copy-paste of the wrong app's `pyproject`. No
  package-data or `[build-system]` care was taken.
- Why it stalled cannot be read from the files (no git history inspected, no notes). Inference:
  both apps depend on each other and on FLS's multi-site base, so extraction needed a shared core
  package the effort decided not to build. The panel framework effort sidestepped this by copying
  `AppSettings`, the CSV helpers and the site hook into the package (spec 3) rather than sharing.
- `idea.md` already puts "tidying `content_engine` and `site_aware_models`" out of scope. The
  parent `research_packaging_and_distribution.md` suggested putting the new repo "beside" them in
  `django_apps/`; the idea has moved it to `software_factory/django-panel-framework.git` instead.
  Nothing in `django_apps/` is a template for this spec.

## 2. Here: the parent research and what it got wrong

`spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md` and
`research_coupling_audit.md`:
- Packaging recommendation (standalone repo, git tag, no submodule, `CHANGELOG.md` with FLS's
  upgrade flags, deprecate-for-one-tag rule, first-class gets it transitively) stands.
- **Wrong, and already corrected in `idea.md`:** keep the `uv.toml` override (uv.toml cannot set
  sources); keep the app label `freedom_ls_panel_framework`... the audit corrected the label claim
  (`apps.py:7` has `label = "freedom_ls_panel_framework"`, table `freedom_ls_panel_framework_bulkactionrun`,
  index `freedom_ls__scope_t_9e7b0b_idx` in `0001_initial.py:43`, ContentType rows and check ids
  all carry the old label). Hence the idea's clean `0001`, new table name and the drop migration.
- Audit section 3 (reverse imports): **55 lines in 22 files** (educator_interface prod 25 across 8
  files, educator_interface tests 23, deployment 4, learner_management 1, qa_helpers 1, base 1
  comment, config 2) plus non-Python: `test_organisation/import_contracts.toml` (36 hits),
  `import_baseline.txt`, `mirroring_baseline.txt`, `mirroring_exemptions.txt`,
  `docs/app_structure.md` (13), fls-dev skills `alpine-js` and `testing`. Contract files regenerate
  with `/ds:app_map`. **`comms` is a second consumer through cotton names only** (`c-panel-search-field`,
  `c-panel-avatar-chip`, `c-panel-empty-state`), no Python import: templates keep working, but the
  `comms` templates then depend on the package being installed. Template paths, `panel_tags`,
  `data_table_tags` and cotton names do not change.
- Audit section 4 (package dependencies): `django>=6.0,<6.1`, `django-cotton>=2.1.3` runtime; dev
  group with pytest, pytest-django, pytest-mock, pytest-playwright, `lxml`, `cssselect` (spec 3
  added both to FLS's dev lists), time-machine, pytest-socket, pytest-randomly, pytest-timeout,
  pytest-xdist; no `nh3`, `markdown`, `guardian`, `allauth`. A task backend is the host's.
- The roadmap note: specs touching `educator_interface`, `comms`, `reports` or `learner_management`
  rebase onto this spec once it changes the import prefix. Expect rebase pain for in-flight
  branches.

## 3. Here: what specs 1 to 4 promised spec 5 (names and locations)

All paths are in-tree today, under `freedom_ls/panel_framework/`; spec 5 moves them.

| Promise | Name | Where | Delivered by |
| --- | --- | --- | --- |
| Settings helper | `Setting`, `AppSettings` (copy of `freedom_ls.base.app_settings`, minus `required_settings_errors`); `config.PanelFrameworkConfig(AppSettings)` with `declared_settings` | `app_settings.py`, `config.py:25-44` | spec 3 |
| Declared settings | `BULK_BACKGROUND_THRESHOLD`, `PANEL_TABLE_PAGE_SIZE`, `PANEL_FRAMEWORK_SITE_RESOLVER` (default `django.contrib.sites.shortcuts.get_current_site`), `PANEL_REFERENCE_BASE_TEMPLATE` (default `panel_framework/minimal_shell.html`) | `config.py` | specs 3, 4 |
| Site resolver | `resolve_site(request) -> Site \| None`, caches on `request._panel_framework_site`, import_string at call time, `ImproperlyConfigured` on bad path; `BulkActionRun.objects.for_request(request)` / `.for_site(site_id)`; unresolved site means no runs and a 422 before the bulk preview | `sites.py`, `models.py` | spec 3 |
| FLS wiring of resolver | `PANEL_FRAMEWORK_SITE_RESOLVER = "freedom_ls.site_aware_models.models.get_cached_site"` | `config/settings_base.py` (about line 638) | spec 3 |
| CSV helpers | `escape_csv_formula`, `EchoWriter`, `UTF8_BOM`, `FORMULA_TRIGGERS`, E.164 exemption | `csv_safety.py` | spec 3 |
| Date formats | `DATE_DISPLAY_FORMAT = "j M Y"`, `DATETIME_DISPLAY_FORMAT = "j M Y, H:i"` | `field_display.py:74-75` | spec 3 |
| System checks | E001 to E008 (E009 unused), E010 and W003 (icons), W001 (non-durable `TASKS` backend), W002 (site resolver on multi-site DB); reference-base check | `checks.py`, `apps.py` | specs 1, 3, 4 |
| Standalone run | `tests/standalone_pytest.ini` (`--ds=...standalone_settings`, `-m "not needs_fls_host"`), `tests/standalone_settings.py` (SQLite in memory, `tests/standalone_app/` user model), command `uv run pytest -c freedom_ls/panel_framework/tests/standalone_pytest.ini freedom_ls/panel_framework/tests`; CI step in `.github/workflows/tests.yml` | `tests/` | spec 3, widened by spec 4 |
| Copy drift guard | `educator_interface/tests/invariants/test_framework_copies_match_base.py` (`SAME_SOURCE`, `SAME_VALUE`) | FLS, not the package | specs 3, 4 |
| Import guard | `tests/test_import_guard.py`, `EXEMPT_DIRECTORIES` now empty | `tests/` | spec 4 |
| Host contract | `HOST_CONTRACT.md`: shell ids (`#interface-main`, quick view, modal, announcer hosts), fragments, script order (htmx 2.x, `hx-headers` CSRF body attr, `shell-components.js` and `alpine-components.js` before Alpine CSP starts), Tailwind wiring, closed token list, `REQUIRED_ICON_NAMES`, twelve `c-panel-*` primitives, reference base template | `HOST_CONTRACT.md` | spec 4 |
| Primitives and icons | `c-panel-button`, `-button-group`, `-chip`, `-callout`, `-back-link`, `-pagination`, `-dropdown-menu`, `-dropdown-menu-separator`, `-page`, `-date`, `-datetime`, `-icon`; 28 icon bodies under `templates/panel_framework/icons/` with MIT notice; FLS wrappers in `freedom_ls/base/templates/cotton/panel-*.html` | templates | spec 4 |
| Minimal shell | `panel_framework/minimal_shell.html`, `reference/base.html`, `css/minimal_shell.css`, `css/reference_theme.css` | templates and css | spec 4 |
| Tailwind source command | `manage.py write_panel_framework_css` writes `BASE_DIR/tailwind.panel_framework.css` containing `@source "<templates dir>";` and `@import "<panel_framework.css>";`, relative to `BASE_DIR` (`./...`) when inside it, else absolute; rewrites only on change; gitignored. FLS's `tailwind.input.css` imports it after `tailwind.components.css` and before `tailwind.active_theme.css`; `package.json` `_write_active_theme` runs it | `management/commands/write_panel_framework_css.py` | spec 4 |
| Framework test CSS | `tests/css/reference_input.css`, npm script `panel_framework_css` builds gitignored `static/panel_framework/css/reference.css`; `tailwind_build` runs it; Playwright tier fails at session start naming `npm run panel_framework_css` if missing | `tests/css/`, `package.json` | spec 4 |
| Alpine | `panelDropdownMenu` registered in `static/panel_framework/js/alpine-components.js`; `sidePanel`, `refreshTimer` in `static/panel_framework/js/shell-components.js` | static | specs 1, 4 |
| Pytest marker | `needs_fls_host` (8 marks; must be in FLS `markers` for `--strict-markers`) | test files | spec 3 |

## 4. Here: what specs 1 to 4 deferred to spec 5 (grep of the four done specs)

- App label rename and the clean `0001` (spec 1: "the app label and the repo move"; spec 3 "Out":
  migration `0001_initial` rewrite, label rename, **check-id prefix change**, ContentType handling).
  Spec 4 repeats: it kept `freedom_ls_panel_framework.E010/W003` and says "spec 5 renames them all
  if the label changes". Open edge: every `freedom_ls_panel_framework.*` check id, and any
  `SILENCED_SYSTEM_CHECKS` entry using one (FLS tests and the spec 3 upgrade notes name W001 and
  W002), becomes `panel_framework.*`. `docs`, the `HOST_CONTRACT.md` hints and `upgrade_notes`
  mention the old ids.
- Package repo, `pyproject.toml`, `v0.1.0`, install mechanics (specs 3 and 4).
- "Whether the compiled reference stylesheet is committed to the package" (spec 4 "Out"). Spec 4
  gitignored `reference.css` and made Playwright fail at session start without it; so the package's
  own CI must run `npm run panel_framework_css` (or equivalent) before the Playwright tier. The
  package repo also needs its own `package.json`, Node and a Tailwind 4.1.16+ dependency, since
  the in-tree script lives in FLS's `package.json`.
- Spec 3 research: "Spec 5's package CI would be the place for a PostgreSQL leg"; the standalone
  suite chose SQLite on purpose (the one text lookup `icontains` at `tables.py:405` folds only
  ASCII case on SQLite). Decide whether package CI keeps SQLite only.
- Moving `tests/standalone_pytest.ini`, `standalone_settings.py`, `standalone_app/` and `conftest.py`
  "as a unit" (spec 3 answers): their `--ds=freedom_ls.panel_framework.tests.standalone_settings`
  and `-c freedom_ls/panel_framework/tests/...` paths must be rewritten; the `needs_fls_host`
  marks (FLS URLconf, FLS icon set) stay with FLS or move to FLS-owned modules.
- The `freedom_ls.tests.playwright_helpers`, `site_context` and `SiteFactory` copies were done by
  spec 4/3, but the **drift guard `test_framework_copies_match_base.py` lives in `educator_interface`
  and compares package files to FLS originals**. After the move it must import
  `panel_framework` and keep passing, or be dropped deliberately: the pairs stop being "copies that
  must not drift" once the package is the owner. Spec 5 should say which.
- The FLS wrapper tests (primitive parity: `c-panel-<name>` equals old `c-<name>`) are FLS-owned
  and stay in FLS.
- Spec 1 research_prior_art advice for spec 5: "move code first, keep tests passing before changing
  behaviour; do not rename and move in the same step; use `git mv`". The answers.md decision for
  spec 5 (fresh import commit, no history) overrides the `git mv` part.

## 5. Here: gotchas recorded by QA and done notes

- **`@source not-ignored:` does not exist** (spec 4 `research_tailwind_source_probe.md`, Tailwind
  4.1.16): `@source not-ignored "..."` fails with "`@source` paths must be quoted". A plain
  `@source "./.venv/lib/python3.x/site-packages/<pkg>/templates"` is scanned even though `.venv` is
  gitignored (also with uv's nested `.venv/.gitignore` containing `*`). Spec 4 shipped the plain form.
  `idea.md` ("The generated `@source` uses `not-ignored:`") and
  `research_uv_sources_and_consumers.md` section 5 both say otherwise and should be corrected.
  Caveat: this is one probe at 4.1.16 on a standard `.gitignore`; upstream still has reports for
  allow-list `.gitignore` patterns (see section 7).
- **A negated `@source` wins over any positive `@source` in the same directory**, regardless of
  order or path form. FLS's `@source "./freedom_ls/**/..."` glob cannot exclude `panel_framework`
  and re-add it through the generated file. After the move the framework leaves the glob anyway,
  so the generated file becomes the only route to its classes. **Consequence to test:** after
  deleting the in-tree app, FLS's compiled `tailwind.output.css` must still contain classes used
  only in framework templates, and `.panel-surface`. Spec 4's "Tailwind coverage" test proves this
  for a `source(none)` input; spec 5 must prove it on the real FLS build from an installed (non-editable)
  copy and from the editable copy.
- **Generated file holds machine-specific paths** (spec 4 upgrade notes step 1), so it must be
  regenerated "after installing or upgrading". With an editable install, the path is the editable
  repo directory (`software_factory/django-panel-framework.git/main/panel_framework/...`), outside
  `BASE_DIR`, so the command writes an absolute path; with the locked git install it points into
  `.venv/lib/python3.x/site-packages/panel_framework/`. Switching between them changes the file:
  a dev who swaps editable and installed must rebuild Tailwind.
- **Template shadowing and ordering** (spec 4 QA B2): with framework templates ahead of FLS's in
  the loader order, `/educator/` returned 500 `TemplateDoesNotExist: panel_framework/icons/home.html`
  because the framework's `c-panel-icon` has only the 28 bodies it needs, shadowing FLS's wrapper.
  The fix was to change the QA plan, not the code; the HOST_CONTRACT rule "unknown icon name raises"
  stands. After the move `freedom_ls.base` must stay ahead of `panel_framework` in `INSTALLED_APPS`
  so FLS's twelve `panel-*` wrappers win. The upgrade notes' `INSTALLED_APPS` manual step should say
  "after `freedom_ls.base`".
- **Pre-QA surprise**: after a rebase a built `reference.css` had been committed by accident (spec 4
  QA "untracked a built reference.css"). The package repo's `.gitignore` must list it and the CI
  wheel test should assert it is absent or present by decision.
- **Spec 3 QA**: a rebuilt-empty dev DB returned 500 on `/` because `FORCE_SITE_NAME` "DemoDev"
  matched no `Site`; seeding fixed it. After this spec's rebuild and table drop, expect the same on a
  fresh `rebuild_after_rebase.sh` run until demo data is seeded. Also the Playwright quick-view test
  `test_quick_view_drawer` is a known load flake (spec 2/3 notes): do not judge the "FLS unchanged"
  run on it alone.
- **Spec 4 QA gaps that become spec 5 gaps**: the minimal shell's menu, quick-view and dialog JS are
  not exercised in the reference page (four skipped tests: 4.dropdown, 4.quickview, 4.dialog,
  4.csrf). A clean-checkout run of the package will not cover them either. The minimal shell has no
  `<main>` landmark. Pre-existing, not fixed: none outstanding.
- **Spec 4 check**: `uv run manage.py check` after the move still must report no
  `freedom_ls_panel_framework`/`panel_framework` messages under the default and first_class themes.
- **Upgrade-notes shape to copy** (spec 4 `upgrade_notes.md`): front matter flags, "Breaking
  changes", "Manual steps" numbered. Spec 4's manual steps (write the CSS file before every Tailwind
  build, add the `@import`, gitignore the generated file) are already in every concrete project's
  `tailwind.input.css` by the time spec 5 lands, if they took spec 4's notes first. First-Class
  and the template **must apply spec 4's notes before spec 5's**, in order; spec 5's notes then
  change only where the command's path points.
- **Spec 3 notes still live in concrete projects**: `PANEL_FRAMEWORK_SITE_RESOLVER` is set in
  `config/settings_base.py` only; a project with its own settings module must set it, and the old
  default `freedom_ls.panel_framework.sites.current_site_or_none` in spec 3's notes is a dead path
  after the move (the real default is `django.contrib.sites.shortcuts.get_current_site`; spec 3's
  notes mention both). Both are worth one line in spec 5's notes.

## 6. Elsewhere: known experiences

Searches turned up few direct write-ups; most evidence is uv documentation or issues that touch the
same mechanics. Items marked "(inferred)" are not stated in a source I fetched.

- **`tool.uv.sources` is not carried to consumers.** uv docs: if a project is used as a git or path
  dependency by a project that is not uv-managed, only `project.dependencies` and
  `project.optional-dependencies` are respected and the `sources` table is ignored. Sources are
  uv-only. https://docs.astral.sh/uv/concepts/projects/dependencies/ . The uv issue
  https://github.com/astral-sh/uv/issues/13774 reports a `tool.uv.sources` override that works for a
  direct dependency but not when another package also pulls the same package in transitively
  (no resolution seen). This supports the idea's PEP 508 direct reference in
  `[project].dependencies` and Spike 2's expectation that a sources-only variant fails. Whether uv
  itself, when resolving a *uv-managed path dependency* (First-Class path-installing FLS), reads the
  dependency's `[tool.uv.sources]` is exactly what the spike must settle: the docs wording does not
  say, and I did not find a confirming issue.
- **A direct reference in a dependency blocks PyPI upload.** PyPI rejects uploads whose
  `Requires-Dist` has a direct URL. Cited in the sibling research
  (https://github.com/pypa/setuptools/issues/2880, https://github.com/aradng/FastLoom/pull/18).
  FLS is not published, so cost is nil now; note in the spec that publishing FLS later forces a
  switch to a version specifier.
- **A path dependency's editable-ness and `uv sync`.** uv docs: `uv sync` is exact, `uv run` is
  inexact by default and `--no-sync`/`UV_NO_SYNC` skips the environment update.
  https://docs.astral.sh/uv/concepts/projects/sync/ . No issue or blog describing "locked git
  package overlaid by `uv pip install -e` then reverted by `uv run`" turned up. Closest are
  https://github.com/astral-sh/uv/issues/8124 (a user needing `--no-editable` on every command
  because uv re-syncs and recreates the editable install) and
  https://github.com/astral-sh/uv/issues/15190 / PR 15234 (`uv sync --no-sources` failing to switch
  an editable install to a registry one). The behaviour is therefore **plausible but undocumented**:
  Spike 1 is warranted, and a record of its result is the spec's only evidence.
- **Editable installs miss new files.** https://github.com/astral-sh/uv/issues/10946 : uv editable
  installs do not pick up renamed or added files the way pip's do. For a package whose live edit
  loop adds templates and migrations, a new template may not show until the editable link is
  refreshed, and a new migration or `.py` module may need a re-install (inferred for the exact cases;
  check `uv pip install -e` with `--no-deps` after adding a file, and `reload` the dev server). Hatch
  docs say the file selection chosen for the wheel decides which directories an editable install
  adds to the path: https://hatch.pypa.io/dev/config/build .
- **Missing templates in a built package.** Django forum threads show the standard failure: a
  packaged app's templates and static folders are absent from the installed copy:
  https://forum.djangoproject.com/t/templates-and-static-folders-missing-in-installed-package/15668 ,
  https://forum.djangoproject.com/t/newbie-django-polls-tutorial-packaging-not-picking-up-templates-static-files/20292 .
  Hatchling includes everything under the package dir by default, but a nested `.gitignore` match
  (for example the gitignored `static/panel_framework/css/reference.css`, the generated
  `tailwind.panel_framework.css`) is excluded from sdists and wheels by hatchling's default
  VCS-ignore behaviour (inferred from hatch docs on `exclude` and "respects .gitignore"). The
  idea's wheel-content test is the right guard; assert `reference.css` is **not** required, and that
  `css/panel_framework.css`, `css/reference_theme.css`, `css/minimal_shell.css`, the 28 icon bodies and
  `HEROICONS_LICENSE.txt` are.
- **Git in slim images.** `python:3.x-slim` and the uv `-slim` images do not ship `git`; the usual
  failure is "Cannot find command 'git'" when a `git+https` requirement is installed. Typical
  fix: install `git` in the builder stage only and copy the venv into the final stage. Sources:
  https://gitlab.com/linkahead/linkahead-control/-/issues/17 ,
  https://docs-next.astral.sh/uv/guides/integration/docker . uv's hash-checking mode does not
  support git dependencies, so `uv pip install --require-hashes` cannot be used with this pin.
  The `uv:0.9-python3.13-bookworm-slim` image check in the idea's open list is a one-line probe:
  `docker run --rm <image> git --version`.
- **`uv pip install --system -r pyproject.toml`** reads only `[project].dependencies` (and
  extras/groups if asked), which is why FLS's own Dockerfile needs the PEP 508 form: sources are not
  read. Matches the idea. (uv docs on `uv pip install -r pyproject.toml`.)

## 7. Elsewhere: Tailwind v4 `@source` and gitignored `.venv`

- Official docs: dependencies are usually in `.gitignore` and so ignored by default; `@source`
  opts them back in. https://tailwindcss.com/docs/detecting-classes-in-source-files .
- Intended fix: Tailwind 4.1.0 made explicit `@source` paths into ignored-by-default folders
  (such as `node_modules`) take precedence over `.gitignore` rules
  (https://github.com/tailwindlabs/tailwindcss/pull/17255, https://github.com/tailwindlabs/tailwindcss/pull/17511).
- Bug reports, state uncertain:
  - https://github.com/tailwindlabs/tailwindcss/issues/15452 : a `.gitignore` inside the directory a
    `@source` names caused it to be skipped; fixed by PR 17892. Relevant: uv writes `.venv/.gitignore`
    containing `*`. Spec 4's probe covered this case at 4.1.16.
  - https://github.com/tailwindlabs/tailwindcss/issues/16920 : explicit `@source` did not override
    wildcard `.gitignore` patterns.
  - https://github.com/tailwindlabs/tailwindcss/issues/19844 : against `@tailwindcss/cli` 4.1.13, an
    allow-list `.gitignore` (starts with `*`, then `!` rules) makes `@source` into ignored directories
    silently dropped; a deny-list `.gitignore` works. Not confirmed resolved. Check First-Class's and
    the template's `.gitignore` shape: an allow-list there would break the package templates silently.
- Practical read: the framework's own `HOST_CONTRACT.md` says Tailwind 4.1.16 or later. Keep that floor,
  and add to the wheel/CI step a build of an input that holds only the generated file (spec 4's
  coverage test) run against the **installed** package, because the failure mode is a silently
  smaller stylesheet, not an error.
- Discussion for the Docker stage problem: https://github.com/tailwindlabs/tailwindcss/discussions/19118
  and the Hyvä docs on the allow-list gotcha (https://docs.hyva.io/hyva-themes/faqs/tailwindcss.html).
  No source describes a Node-only Docker stage that needs a Python package's files; the idea's own
  design (separate Python stage, `COPY --from=`) is the standard multi-stage answer (inferred).

## 8. Summary for the spec

1. Correct `idea.md`: `not-ignored:` is a build error at 4.1.16; plain `@source "<path>"` works into
   `.venv`. Spec 4's generated file already does it.
2. Spec 4 delivered the standalone suite, host contract and Tailwind command; spec 5 only needs to
   relocate and re-verify. Its carry-over work: `--ds` and `-c` paths in `standalone_pytest.ini`, the
   check-id prefix rename (`freedom_ls_panel_framework.*` to `panel_framework.*`), the drift guard in
   `educator_interface`, the package's own `package.json` for `reference.css`, package CI Node setup,
   and the wheel test's file list.
3. `django_apps/` holds only stale half-packages; no reusable tooling, no lesson beyond "the copy
   diverged".
4. Spikes 1 and 2 have no external answer; run them as planned and record results.
5. Real hazards elsewhere: git missing in slim images, `@source` and allow-list `.gitignore`, editable
   installs not seeing new files, PyPI refusal of direct references later.

status: ok
