# Semantic icons app: standalone, neutral settings, bundled icon data

Spec 1 of 4 in the Semantic icons extraction effort. Read the "Semantic icons extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The icons app stops depending on FLS, while staying at `freedom_ls/icons`. After this spec nothing
in it imports `freedom_ls.*` (outside its own package), reads `BASE_DIR`, needs an npm step, or
uses an FLS-branded setting name. Its tests run without FLS.

- **Neutral settings.** `FREEDOM_LS_ICON_SET`, `FREEDOM_LS_ICON_OVERRIDES` and
  `FREEDOM_LS_ICON_BACKEND` become `SEMANTIC_ICONS_SET`, `SEMANTIC_ICONS_OVERRIDES` and
  `SEMANTIC_ICONS_BACKEND`. FLS's own settings and First-Class's `config/customisation.py` move
  over; First-Class takes it through the upgrade notes.
- **Own settings helper.** The app carries its own copy of the generic settings reader instead of
  importing `AppSettings` from `freedom_ls.base`.
- **Bundled icon data.** A generated subset of the four Iconify sets (heroicons, lucide, tabler,
  phosphor) ships inside the app, so icons render with no `npm install`. A script regenerates it
  from the `@iconify-json` packages, records the upstream versions it used, and the app carries the
  licence notices.
- **Optional full data.** A setting points at a directory laid out like `node_modules/@iconify-json`.
  When set, it is read first, so a host that remaps a name to a glyph outside the subset can reach it.
- **No private reach-ins.** The loader exposes a public cache clear. The FLS callers and tests that
  reach into `loader._cache`, and the root `conftest.py` workaround that fakes `BASE_DIR` and
  symlinks `node_modules`, use it instead.
- **Standalone tests.** The app's tests run under the app's own minimal Django settings, with no FLS
  settings module or fixtures.

## Why

A host project cannot use the icons app while it imports FLS, is configured through FLS-branded
names, and finds its icon data only in an FLS checkout's `node_modules`. A pip or git install has no
`node_modules` at all. The later specs in the effort (host-added names, the package repo, the
Claude plugin) all assume an app that already stands alone, so this work comes first and is done
inside FLS where the existing suites can prove nothing broke.

## What is settled

- Settings are flat, prefix `SEMANTIC_ICONS_`: `SEMANTIC_ICONS_SET`, `SEMANTIC_ICONS_OVERRIDES`,
  `SEMANTIC_ICONS_BACKEND`, plus `SEMANTIC_ICONS_ICONIFY_DIR` for the optional full-data directory.
  Defaults are unchanged (`heroicons`, no overrides, no custom backend).
- The old `FREEDOM_LS_ICON_*` names are still read, with a deprecation warning, for one tag. The new
  name wins when both are set. The deprecation rule is the one the panel framework uses: a breaking
  change keeps the old surface for one tag.
- FLS settings and First-Class `config/customisation.py` (it sets `FREEDOM_LS_ICON_SET="phosphor"`
  and an empty overrides dict) move to the new names in this spec. First-Class's change is carried
  by the spec's `upgrade_notes.md` with `requires_settings_change`, which also tells First-Class its
  Dockerfile no longer needs to copy `node_modules/@iconify-json` into the runtime image.
- The settings reader is a copy of the generic `AppSettings` helper, living in the icons app.
  `freedom_ls.base` keeps its own; nothing is shared and no new shared package is created.
- Bundled data is a generated subset of the four Iconify sets, in Iconify JSON format, so the loader's
  data shapes do not change. It covers every glyph the four built-in mappings reference. All 63
  current semantic names keep shipping and render in all four sets with no host action.
- Lookup order for icon data: the `SEMANTIC_ICONS_ICONIFY_DIR` directory when set, then the bundled
  subset. No `BASE_DIR` anywhere in the app.
- The generation script lives in the repo, not in the host-facing app, and is run by maintainers
  only. It records the `@iconify-json` version of each set next to the data. FLS keeps the four
  `@iconify-json` packages in `package.json` as dev dependencies for this script and for hosts that
  want full data; the runtime no longer needs them.
- Licence texts for the four sets are shipped with the data (Heroicons MIT, Lucide ISC with its
  Feather MIT notice, Tabler MIT, Phosphor MIT). Lucide's own `LICENSE` is copied verbatim.
- The missing-data system check (`icons.E002`) stops telling the host to run `npm install`. It names
  `SEMANTIC_ICONS_ICONIFY_DIR` when a configured directory lacks a set. The other check ids stay.
- A test confirms the bundled files match what the script would generate from the recorded upstream
  versions, so the subset cannot drift from the mappings. File sizes are measured, not
  estimated, before any size is quoted in docs.
- Private reach-ins are replaced by one public cache-clear on the loader. Nothing outside the icons
  app touches `loader._cache`, and the root `conftest.py` no longer sets `BASE_DIR` or symlinks
  `node_modules` for icons.
- The app's tests run under their own minimal Django settings with `django-cotton` installed. They no
  longer rely on FLS's settings module, `BASE_DIR` or `node_modules`.
- `invariants/test_no_font_awesome.py` scans the whole FLS template tree, so it is an FLS policy
  test and stays in FLS. It leaves the icons app's test directory.
- The app stays at `freedom_ls/icons` with import name `freedom_ls.icons` and label `icons`, so check
  ids and `INSTALLED_APPS` do not change here.
- `<c-icon>`, `{% icon %}`, `render_icon()` and their arguments do not change. No template edits.

## Open until the spec

- Where the subset generation script lives in the repo, and how it is invoked (it needs Node and the
  four npm packages, so it is a maintainer command, not part of `uv run pytest`).
- Where the minimal test settings and a pytest configuration for the app live, and how the app's
  suite is selected from the main FLS run so both stay green.
- Precedence edge cases: a set present in `SEMANTIC_ICONS_ICONIFY_DIR` but missing an icon the subset
  has; a configured directory that does not exist. Fallback to the subset or a startup error.
- Where `invariants/test_no_font_awesome.py` lands in FLS, and how it finds `icon.html` after the move.
- Whether the deprecated names warn once at startup or on each read, and the warning category.
- The exact on-disk layout and manifest format for the bundled data and recorded upstream versions.

## Out of scope

- Host-added semantic names, a host's own SVG files, custom icon sets and the registry API
  (`extract-semantic-icons-app-2-host-icons`). The four mapping dicts and the closed name set stay as
  they are.
- Moving or renaming the app to `semantic_icons`, the package repo, the `v0.1.0` tag, the `pyproject`
  build and installing by git tag (`extract-semantic-icons-app-3-package-and-install`).
- The generic Claude Code plugin, host documentation and the trimmed `fls-dev:icon-usage` skill
  (`extract-semantic-icons-app-4-claude-plugin`).
- New icon sets beyond the four, an icon picker, any change to how templates call `<c-icon>`.

## Resources

- Research: `spec_dd/1. next/extract-semantic-icons-app-1-standalone-app/research_icon_data_distribution.md`
  (data options and licences; moves into this directory) and
  `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md` (coupling table items 1 to
  3, 8, 15, 16 and the tests section).
- Original brief: `spec_dd/1. next/extract-semantic-icons-app/idea.md`.
- Code: `freedom_ls/icons/` (`config.py`, `loader.py`, `checks.py`, `tests/`),
  `freedom_ls/base/app_settings.py`, `freedom_ls/conftest.py`, `config/settings_base.py`,
  `package.json`, `freedom_ls/contrib/conformance/test_theme.py`.
- First-Class at `/home/sheena/workspace/first_class/First-Class-LMS.git/main`
  (`config/customisation.py`, its Dockerfile's `@iconify-json` copy step).
- Skills: `fls-dev:icon-usage`, `fls-dev:app-settings`, `ds:testing`, `fls-dev:testing`.
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` for the upgrade flag schema.
