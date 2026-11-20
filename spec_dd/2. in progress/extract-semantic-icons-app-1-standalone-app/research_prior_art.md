# Prior art: standalone icons app, extracting FLS apps, renaming settings, dropping node_modules

Scope: what the repo has already tried and what happened. Everything is from files in this worktree
and First-Class's checkout; no web sources. Paths are relative to the worktree root unless absolute.

## 1. Headline

- Nobody has yet tried the specific moves in this idea. No FLS app has been published, and no
  setting has been renamed with a deprecation alias.
- The closest precedent is the panel framework extraction. Its spec 3 (`standalone-backend`) is the
  template this spec copies: sever imports in place, copy small helpers, run the unit tests under a
  minimal settings module, add an import guard. It shipped and QA passed, but several decisions in
  the shipped spec changed during PR 254 review.
- The "deprecated names kept for one tag" rule exists only as a plan. It is written in
  `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md:114` and repeated
  in the ideas for `extract_panels_framework-5-package-and-install`, `-6-claude-plugin` and
  `extract-semantic-icons-app-3-package-and-install`. No shipped spec has used it. The panel
  framework's own renames (spec 1 and spec 4) deliberately broke old names with no alias. So this
  spec is the first one to build a deprecated-alias path, and there is no code pattern to copy.

## 2. The icons app's own history

- `spec_dd/3. done/2026-03-01_22:40_open-source-icons/` replaced `django-heroicons` with Iconify JSON
  read from `BASE_DIR/node_modules/@iconify-json/<pkg>/icons.json`. The npm-only data source dates
  from here.
- `spec_dd/3. done/2026-04-01_09:27_allow override icons/` added the pluggable backend and the three
  `FREEDOM_LS_ICON_*` settings. Its QA (`qa_report.md`) passed all 12 cases across the four sets and
  overrides. Its `upgrade-guide.md` is the only prior upgrade doc for icons. It predates the
  `requires_settings_change` front matter and is stale on check ids: it lists `E001` as "JSON not
  found", but `freedom_ls/icons/checks.py` now has `E001` unknown set and `E002` JSON missing. The
  idea's `icons.E002` is right. Do not copy the upgrade guide's id list.
- Where `node_modules` was already patched around rather than fixed:
  - `freedom_ls/conftest.py:348-355` points `settings.BASE_DIR` at a tmp dir and symlinks the real
    `node_modules` into it, because icon-bearing pages (the 404 page) still need icon data. This is
    the workaround the idea says to remove.
  - `freedom_ls/accounts/tests/test_legal_doc_view.py:12,49-58,79-84` imports `loader._cache` and
    clears it around a test, with a docstring about the stubbed `BASE_DIR` having to "still reach the
    real node_modules". This is a reach-in the idea lists. Both workarounds only go away once the
    loader no longer reads `BASE_DIR` and offers a public cache clear.
- First-Class coupling found in `/home/sheena/workspace/first_class/First-Class-LMS.git/main`:
  - `config/customisation.py:42,57` set `FREEDOM_LS_ICON_SET = "phosphor"` and
    `FREEDOM_LS_ICON_OVERRIDES = {}`.
  - `Dockerfile:97,144-149` copies `/app/node_modules/@iconify-json` into the runtime image
    (about 8 MB, per its own comment) and mentions `icons.E002`.
  - `.github/workflows/build-and-push.yml:145-149` has a comment that says the `manage.py check`
    step relies on `icons.E002` finding the JSON for `phosphor` (`@iconify-json/ph`). The idea
    mentions the Dockerfile but not this workflow. The upgrade notes should name both.
  - `package.json:4-7` lists all four `@iconify-json` packages.
- `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md` is the earlier audit. Its
  claims hold: the only non-test `freedom_ls` import is `config.py:3`; `loader.py:34` is the only
  `BASE_DIR` read; items 1-3, 8, 15, 16 are this spec's. Its open question 1 (alias or break) is now
  answered by the idea (alias, one tag).
- `spec_dd/2. in progress/extract-semantic-icons-app-1-standalone-app/research_icon_data_distribution.md`
  (already moved here) recommends the bundled generated subset plus a settable directory. It gave
  byte sizes only as estimates and said to measure before quoting. The idea already carries that rule.

## 3. Panel framework extraction: what carries over

The effort is four specs shipped so far (all under `spec_dd/3. done/2026-11-*_extract_panels_framework-*`),
with spec 5 (package) and 6 (plugin) still in `spec_dd/1. next/`.

### 3.1 Spec 3 "standalone backend": the direct template

Source: `.../2026-11-19_06:59_extract_panels_framework-3-standalone-backend/{1. spec.md, answers.md,
upgrade_notes.md, qa_report.md, todo.md}`. Spec 3's shape matches the idea: copy the helpers, keep FLS's
own, standalone run, import guard.

What was done, and is now in the tree:

- **Copied helpers, FLS keeps its own.** `freedom_ls/panel_framework/app_settings.py` is a copy of
  `AppSettings`/`Setting`, without `required_settings_errors`. Same rule as this idea. The copy is
  covered by a mirrored test file. Reviewers asked about the duplication (PR 254 finding #8) and the
  decision was to keep the copies per spec (`todo.md` line 38).
- **Separate pytest run, not a tier.**
  - `freedom_ls/panel_framework/tests/standalone_pytest.ini` is named so pytest does not discover it
    by itself. The comment at its top explains why: a discovered `pytest.ini` would switch FLS runs
    aimed at those files to standalone settings.
  - Its `addopts` has `--ds=...standalone_settings`, `--nomigrations`, `--strict-markers`,
    `-m "not needs_fls_host"`, and socket blocking. `pythonpath = ../../..`, `norecursedirs = playwright`.
  - The command carries the test path (`uv run pytest -c <ini> <tests dir>`), because `-c` makes the
    ini's directory the rootdir and `testpaths` would not scope a run from the repo root.
  - It was wired into CI as one extra step: `.github/workflows/tests.yml:90-91`, after the main
    unit-test step. The spec had to choose "documented command plus CI step" because
    `[tool.test_tiers]` cannot name an extra tier without a change to the generic plugin
    (spec "Open questions"). Spec 3's `answers.md` had said "its own test tier", which the spec then
    overrode. The icons idea's answer 4 says "wired into the project's test tiers". That is the same
    conflict and needs a decision: the tier table is in a generic plugin, which `CLAUDE.md` forbids
    adding FLS knowledge to.
  - The main FLS run does not exclude the standalone suite in spec 3: the framework tests run in
    both. The icons idea instead says the main run excludes `freedom_ls/icons/tests`. That is a
    different design (exclusion), and nothing prior does it. `pyproject.toml:88` has
    `testpaths = ["freedom_ls", "tests", "claude_plugins/fls-content"]`, so exclusion needs an
    `--ignore` or `norecursedirs` entry, and coverage (`--cov-fail-under=92` in `tests.yml:88`) will
    drop the icons app's lines from the main run unless the second run also reports coverage.
- **Minimal settings module.** `freedom_ls/panel_framework/tests/standalone_settings.py`: in-memory
  SQLite, a handful of `django.contrib` apps, `django_cotton.apps.SimpleAppConfig`, a test app,
  cotton loader. Notes from it that apply to icons:
  - `COTTON_SNAKE_CASED_NAMES = False` is set, because FLS keeps hyphenated component file names
    (`c-icon` file is `icon.html`, no issue for icons, but any new test component names need care).
  - `SITE_ID` unset, `ALLOWED_HOSTS = ["testserver"]`. Icons does not need sites, so its settings
    can be shorter: cotton, the app, and templates. `SimpleAppConfig` (not plain `django_cotton`) is
    what the working settings use.
  - Standalone test app had to be labelled `standalone_app` with no `apps.py`, because an app-map
    generator broke `lint-imports` with one (`todo.md` line 24). Check whether a test settings
    module or app under `freedom_ls/icons/tests/` trips the same generator
    (`claude_plugins/django-stack/scripts/generate_app_map.py`).
- **Test fixtures that delegate.** In the FLS run the framework's `site` and `mock_site_context`
  fixtures delegate to FLS's of the same name; in standalone they are replaced. There is a file
  `freedom_ls/panel_framework/tests/standalone_fixtures.py`. The icons suite uses no FLS fixtures
  (coupling audit section 2), so it needs no such split. It does use `override_settings`, and
  `get_icon_backend.cache_clear()`, which the new public cache clear should cover.
- **`needs_fls_host` marker.** Tests that need FLS's real templates were marked and deselected in the
  standalone run, rather than weakened. Registered in `pyproject.toml:99`. Icons' `components/test_icon.py`
  renders `<c-icon>` through a template and uses `CottonCompiler` directly, so it may be portable.
  Check before marking anything.
- **Stand-in templates.** About 16 test-only `.html` stubs under
  `freedom_ls/panel_framework/tests/standalone_templates/`, found by running a render pass and
  not from memory (`qa_report.md` lists them as the reason QA ran in FULL class). For icons the
  real `icon.html` is in the app, so no stand-ins are needed, but the 63-name x 4-set render
  tests need the real data, which the bundle supplies.
- **Import guard** (`tests/test_import_guard.py`): an `ast` scan of every `.py` under the package,
  failing on `freedom_ls` imports outside the package, with named exemptions pinned in the test,
  and run in both the FLS and standalone runs. The icons idea has no such guard. "Nothing in it
  imports `freedom_ls.*` outside its own package" is a success criterion with no test behind it.
  Add one, copying this. Note one wrinkle: the icons app's own imports are `freedom_ls.icons.*`,
  so the guard must allow that prefix. Spec 3 reasons the same way for `freedom_ls.panel_framework`.
- **What went wrong or was reworked in spec 3** (from `todo.md`, `qa_report.md`, `upgrade_notes.md`):
  1. The shipped upgrade notes diverge from the spec text. The spec set the default resolver to
     Django's `get_current_site`. It shipped as `freedom_ls.panel_framework.sites.current_site_or_none`.
     The notes also add `W002` (a `SITE_ID` plus default resolver plus several sites warning) that
     the spec never mentioned, and a `Site.DoesNotExist` that now propagates. These came from
     PR 254 review findings. Lesson: the first design of a "neutral default" settings change was
     wrong in a way review caught; leave room in the icons spec for the precedence edge cases
     (already flagged open in the idea).
  2. A reviewer finding was a silently swallowed exception (`resolve_site` swallowing
     `Site.DoesNotExist`); the fix kept raising. Relevant to the icons answers: a nonexistent
     `SEMANTIC_ICONS_ICONIFY_DIR` is a check error (answer 1), not a silent fallback. That matches.
  3. The upgrade notes' guidance on the marker changed: the spec said the FLS run does not deselect it;
     the notes tell downstream "do not deselect the marker". The spec said W001 appears in every
     `call_command("check")` in the suite. Tests still passed. So a new check that fires under
     pytest must be assumed to appear in tests that count check messages: the new deprecation warning
     for `FREEDOM_LS_ICON_*` will appear only when an old name is set, so FLS's own settings must
     already be on the new names or every `check` call in the suite shows it.
  4. Full-run instability not caused by the spec: the full test run was unusable after Docker went
     down (8976 connection errors), plus an audit-log ordering flake and xdist-only failures of
     tests that reload `config.urls`. Both were filed as separate ideas rather than fixed in the
     spec. A second pytest invocation for icons adds CI time and another place for these to appear;
     keep it SQLite-only if possible, as spec 3 did.
  5. A migration was added late (`0002_bulk_action_run_site_has_no_reverse_accessor.py`)
     for state-only changes. The icons app has no models, so this does not apply.
  6. QA was thin for this kind of spec: 17 browser tests, 0 bugs, and the spec's own items (checks,
     resolver errors, scoping guard) were declared "not driven in the browser" and left to unit tests. Expect
     the same for icons: the user-visible surface is "pages still render icons", so QA is a smoke
     pass in all four icon sets plus unit-level proof of the loader and checks.
- **Upgrade notes form.** `upgrade_notes.md` front matter keys, copied by every shipped spec:
  `requires_migrations`, `requires_template_review`, `changed_template_paths`,
  `requires_settings_change`, `changed_settings` (a list, each with an inline comment saying
  optional or not), `requires_package_upgrade`, `changed_packages`, `requires_npm_install`,
  `changed_npm_packages`, `requires_tailwind_rebuild`. Spec 3's notes set `requires_settings_change: true`
  with `changed_settings` listing both the new setting and `SILENCED_SYSTEM_CHECKS`. For icons:
  `requires_settings_change: true`, `changed_settings` listing the three renames and
  `SEMANTIC_ICONS_ICONIFY_DIR`; also consider `requires_npm_install` (no longer needed for runtime)
  and `changed_npm_packages`, since the four `@iconify-json` packages move to dev dependencies.
  Check the schema in `claude_plugins/fls-dev/commands/update_upgrade_notes.md`, which the idea
  lists, before choosing; no prior notes have set `requires_npm_install` to a value that means
  "no longer required", so the flag semantics need checking.
  Section structure in all shipped notes: `## Breaking changes` then `## Manual steps`.

### 3.2 Spec 1 and spec 4: renames without aliases

- Spec 1 (`.../2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/`) renamed many public
  names (`form_url` to `action_url`, `*_template` to `*_template_name`, removed filters) with no
  alias. Its research (`research_best_practices.md:20`) recommended that: "With a single importer,
  update imports and delete the old modules. Compat aliases add untested surface that must later be
  removed". The panel framework had one importer (FLS). The icons settings have two (FLS and
  First-Class), plus the rule in the roadmap, so the idea's alias is a deliberate departure.
- Spec 4 (`.../2026-11-20_15:18_extract_panels_framework-4-template-contract/`) did add a form of
  backward compatibility: FLS ships `c-panel-*` wrapper templates that render the existing
  components, and `partials/page_title.html` became a one-line include of the framework's version.
  That is "keep the old path as a thin forwarder", not a deprecation warning. Its
  `upgrade_notes.md` still had a long Manual steps list (7 steps plus an optional one,
  `requires_tailwind_rebuild: true`), and added a startup check (`E010`/`W003` for required icons).
  Spec 4 also shipped `HOST_CONTRACT.md` for what a host must provide.
- Spec 4 has a link to icons: the panel framework now requires icon names in `REQUIRED_ICON_NAMES`
  (`freedom_ls/panel_framework/checks.py`) and reaches icons through FLS's `c-panel-icon` wrapper
  that forwards to `c-icon`. That wrapper uses only `<c-icon>` and not the Python API, so this spec's
  renames do not touch it. But panel framework tests that use `override_settings(FREEDOM_LS_ICON_SET=...)`
  are marked `needs_fls_host` (`test_tables.py` about lines 2208, 2225; `test_modal_form_template.py`,
  `test_inline_record_form_template.py`). These `override_settings` calls name the old setting and
  are among the places that must move to the new name.

### 3.3 What has not happened yet (so no lessons)

- Spec 5 (repo, `pyproject` build, git-tag install, CHANGELOG with flags) and spec 6 (plugin) for
  the panel framework are in `spec_dd/1. next/` and unstarted. Any claim about "how a one-tag
  deprecation window worked" cannot be backed by shipped practice yet. Research files that discuss
  it: `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md:107-128`,
  `spec_dd/1. next/extract_panels_framework-5-package-and-install/research_uv_sources_and_consumers.md`.
- `spec_dd/3. done/2026-08-24_20:56_extract_forms_into_seperate_app/` is a different style of
  extraction (inside the repo). Its plan (section 10.8, `2. plan.md:30`) is "no compatibility shims,
  no deprecation re-export", for the same single-importer reason. Same direction as the panel
  framework.

## 4. Renaming settings with a deprecation window: what exists in the repo

- No existing FLS setting has been renamed with an alias. A search of the `extract*` spec files
  found only plans and rules, never an implementation.
- Reusable pieces that exist:
  - `freedom_ls/base/app_settings.py` `AppSettings`/`Setting`. It treats empty string and `None`
    as unset (coupling audit item 1). That matters for "new name wins when both set": a host that
    sets `SEMANTIC_ICONS_SET = ""` falls through to the old name or default. Decide if that is
    wanted.
  - The panel framework's `checks.py` registers checks in `AppConfig.ready()` with ids
    `freedom_ls_panel_framework.W001` etc. The pattern is a check function returning `Warning` with
    `id`, a message that names the item, and a hint that says it can be silenced by id. Spec 3's
    answers use the same wording the icons answer 2 asks for ("silenceable through
    `SILENCED_SYSTEM_CHECKS`"). So the answer to open question "warn once or on each read" is
    already effectively settled: a check, so once per `check` run, no per-read warning.
  - Check ids for icons: shipped ones are `icons.E001`-`E007` and `icons.W001`. The new warning
    would be the next free number (`W002` or higher) and the label stays `icons` in this spec, so ids
    do not change. Spec 3 for the panel framework did the opposite for the future: its "label and
    check-id prefix change" were pushed to the package spec. Same for icons spec 3.
- Where old names are read today (so the rename covers everything): `freedom_ls/icons/config.py`,
  `backend.py` (lines about 93-94, 136), `render.py` (about 40), `checks.py` (about 29, 57, 98, 102,
  153), `config/settings_base.py` (5 `FREEDOM_LS_ICON`/`_cache` hits per grep, line about 67 is the
  setting), `freedom_ls/contrib/conformance/test_theme.py:26`, the panel framework tests listed
  above, `freedom_ls/content_engine/tests/test_course_icon.py` and `test_icon_validation.py`, plus
  docs: `claude_plugins/fls-dev/skills/icon-usage/resources/configuring-icons.md`,
  `custom-icon-backend.md`, `claude_plugins/fls-dev/resources/testing.md`,
  `docs/product/configuration-and-extension.md`. The coupling audit counts these
  (items 2, 15, 18). Re-run a grep for `FREEDOM_LS_ICON` at spec time; this research did not
  produce a clean per-file list because the grep in the worktree was noisy with unrelated `_cache`
  matches.
- `freedom_ls/contrib/conformance/test_theme.py` is "a host conformance test exported from FLS": a
  host that runs it with the old setting would break on rename. It is a downstream surface, the
  strongest argument for the alias.

## 5. Dropping node_modules: what is known

- No prior spec has removed an npm runtime dependency. The nearest is panel framework spec 4, which
  added a Tailwind source command that writes a generated CSS file (`write_panel_framework_css`)
  instead of reading framework templates from the host tree. It required a manual step
  ("run it before every Tailwind build") in the upgrade notes. This is a pattern of "generate a file
  with a maintainer or build command", similar to the icon subset script, but the subset script is
  a maintainer-only command whose output is committed. So no host step is needed. That is simpler
  for hosts than the Tailwind one.
- CI today installs npm in three places (`tests.yml:82,131,177`) and in `security.yml:85`
  (coupling audit item 7). Icons no longer need that, but Tailwind still does, so those steps
  stay. Not a saving.
- `pyproject.toml:82` excludes `node_modules*` from the FLS build, meaning a pip install of FLS
  has had no icon data at all (coupling audit). Bundled data fixes that, but the data files must be
  included as package data. Check how `pyproject.toml` includes non-Python files for other apps before
  relying on it; this spec keeps the app in the FLS tree so it is fine now, but spec 3's package
  build will need the data directory declared.
- Deployment: First-Class's Dockerfile copy step (about 8 MB) is removed through the upgrade notes
  (already in the idea). The `build-and-push.yml` comment says `manage.py check` in that workflow
  asserts the JSON exists via `icons.E002`. After this spec that assertion is satisfied by the
  bundled data, so the workflow comment is stale, and E002 becomes a check that only fires when a
  configured directory lacks a set.
- Data licences: no earlier spec shipped third-party data in the repo. No precedent for how to hold
  licence texts. The research file's rules (copy Lucide's LICENSE verbatim) are the only guidance.

## 6. Recommendations for the spec

1. Copy panel framework spec 3's structure: copied settings helper plus own test, import guard test,
   separate pytest ini named so pytest does not discover it, CI step, `--ds` with its own
   minimal settings. Take its ini as the starting file.
2. Add an import guard test for the icons app. The idea lists "nothing imports `freedom_ls.*`" as a
   goal with no proof.
3. Resolve the "tier" wording. Spec 3 first answered "its own test tier" and the spec then
   replaced it with "command + CI step" because the tier table is in a generic plugin. The icons
   answer 4 repeats the original wording. Decide up front which it is.
4. Decide how the main run excludes the icons tests and how coverage is kept (the main run
   enforces `--cov-fail-under=92`).
5. Make the deprecation warning a system check (answer 2), and make FLS's own settings and test
   `override_settings` calls use the new names, so `call_command("check")` in the suite does not gain
   a warning (spec 3's W001 lesson).
6. Put the two First-Class touchpoints in the upgrade notes: `config/customisation.py:42,57`, and
   the Dockerfile copy step and `build-and-push.yml` comment.
7. Record that this spec is the first real deprecated-alias implementation in the repo, so the
   alias, its test (new wins, old still works, warning fires) and its removal date (next tag, spec
   3 of this effort, which keeps the aliases in `v0.1.0` per its idea lines 83-86) should be
   written so the next specs can copy them.
8. Expect review to produce edge cases in the neutral default (spec 3's resolver default changed
   in review). The idea's open "precedence edge cases" already covers the main ones; add empty-string
   handling of `AppSettings` and an `ICONIFY_DIR` that is a relative path.

## Sources (local files)

- `spec_dd/2. in progress/extract-semantic-icons-app-1-standalone-app/{idea.md, answers.md, research_icon_data_distribution.md}`
- `spec_dd/1. next/roadmap.md` (Semantic icons extraction section, lines 381-403)
- `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md`
- `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md`
- `spec_dd/3. done/2026-03-01_22:40_open-source-icons/`, `spec_dd/3. done/2026-04-01_09:27_allow override icons/{upgrade-guide.md, qa_report.md}`
- `spec_dd/3. done/2026-11-19_06:59_extract_panels_framework-3-standalone-backend/{1. spec.md, answers.md, upgrade_notes.md, qa_report.md, todo.md}`
- `spec_dd/3. done/2026-11-16_19:13_extract_panels_framework-1-gather-generic-code/{upgrade_notes.md, research_best_practices.md}`
- `spec_dd/3. done/2026-11-18_18:50_extract_panels_framework-2-new-capabilities/upgrade_notes.md`
- `spec_dd/3. done/2026-11-20_15:18_extract_panels_framework-4-template-contract/{upgrade_notes.md, answers.md}`
- `freedom_ls/panel_framework/tests/{standalone_pytest.ini, standalone_settings.py}`, `.github/workflows/tests.yml`,
  `pyproject.toml`, `freedom_ls/conftest.py:348-355`, `freedom_ls/accounts/tests/test_legal_doc_view.py`,
  `freedom_ls/icons/checks.py`
- `/home/sheena/workspace/first_class/First-Class-LMS.git/main/{Dockerfile, config/customisation.py, package.json, .github/workflows/build-and-push.yml}`

status: ok
