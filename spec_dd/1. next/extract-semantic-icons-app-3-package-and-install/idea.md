# Semantic icons: own repo, git-tag install, FLS switches over

Spec 3 of 4 in the Semantic icons extraction effort. Read the "Semantic icons extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The icons app leaves FLS and becomes `django-semantic-icons`, a public GitHub repo owned by Prelude
Technologies, all rights reserved for now, checked out at
`/home/sheena/workspace/lms/django_apps/semantic_icons`, released as the tag `v0.1.0`.
FLS then depends on that tag, edits it live in worktrees, and carries the change to First-Class
through its normal upgrade-notes flow. This copies the pattern `extract_panels_framework-5-package-and-install`
proved. Wherever that spec settled a choice this idea leaves open (hosting org and pin URL, the
dev-loop fallback, the locked-rev check, the Dockerfile `git` question), this spec follows what it settled.

The package repo:
- An explicit `[build-system]` (hatchling). Templates (the `icon.html` cotton component), the
  vendored icon data and its licence notices ship as package data. A test builds the wheel and
  asserts the template, the icon data and the licence notices are in it, because an editable install
  hides a missing file.
- A `LICENSE` file that reads, in substance: "Copyright (c) 2026 Prelude Technologies. All rights
  reserved. No licence is granted to use, copy, modify or distribute this software. Licensing terms
  are to be decided." It then lists each vendored icon set, its licence and where its notice
  file sits. Prelude's notice covers only Prelude's own code; the icon sets keep their own
  licences.
- The README says the package is not open source yet and that outside contributions (pull requests,
  patches) are not accepted. No `CONTRIBUTING.md`.
- The app moves from `freedom_ls/icons`. Its import name and app label become `semantic_icons`, so
  the check ids become `semantic_icons.E0xx` and `semantic_icons.W001`. The app has no models, so
  there are no migrations to write.
- Its own CI runs the standalone suites that `extract-semantic-icons-app-1-standalone-app` and
  `extract-semantic-icons-app-2-host-icons` delivered.
- `CHANGELOG.md`, one entry per tag, carrying the same flags as FLS's `upgrade_notes.md`
  (`requires_template_review`, `requires_settings_change` and the others the panel package's
  changelog uses). The deprecation rule is written at the top: a breaking change keeps the old
  surface with a deprecation warning for one tag.
- A README covering install, settings and the `<c-icon>` component. It is the only documentation
  this spec ships.

FLS:
- `[project].dependencies` gains `django-semantic-icons @ git+https://github.com/preludetech/django-semantic-icons.git@v0.1.0`,
  the same PEP 508 form as the panel package, with no `[tool.uv.sources]` entry and no `uv.toml`.
- `freedom_ls/icons` is deleted. Every import prefix `freedom_ls.icons` becomes `semantic_icons`,
  in `content_engine` (`course_icon`, `icon_validation`, `content_tags`, `course_icon_tags`),
  `contrib/conformance`, `accounts` tests, `course_access`, and the `INSTALLED_APPS` entry in
  `config/settings_base.py`, which becomes `semantic_icons`. Test patches of
  `freedom_ls.icons.*.load_iconify_data` follow the new path. `<c-icon>` calls and its arguments do not
  change, so no template edit is needed.
- `invariants/test_no_font_awesome.py`, already an FLS test, updates its path to the cotton
  `icon.html` in the installed package.
- The FLS-side settings use the new `SEMANTIC_ICONS_*` names; nothing in FLS keeps a
  `FREEDOM_LS_ICON_*` setting.
- `docs/app_structure.md`, the `icon-usage` and `testing` skills in `claude_plugins/fls-dev/` and the
  import-linter contract files under `test_organisation/` are updated or regenerated where they name
  `freedom_ls.icons`.
- Live editing uses the same mechanism as the panel package: `rebuild_after_rebase.sh` installs the
  local checkout editable after `uv sync`, with an absolute `SEMANTIC_ICONS_DIR` defaulting to the
  repo path above, skipped with a message when missing. The `UV_NO_SYNC=1` requirement and the
  fallbacks are whatever `extract_panels_framework-5-package-and-install` settled. This lives in
  `fls-dev`, never in `sdd` or `ds`.
- CI and Docker already fetch git dependencies once the panel package has landed
  (`uv sync --locked`, `git` in the images), so this spec adds no new fetch mechanism.
- The spec's `upgrade_notes.md` sets `requires_package_upgrade` (changed package
  `django-semantic-icons`), `requires_settings_change` and `requires_template_review` (only the
  `INSTALLED_APPS` rename and the settings names, no template edits). It tells First-Class what to
  change:
  - `INSTALLED_APPS` swaps `freedom_ls.icons` for `semantic_icons`.
  - Its Dockerfile comment about `icons.E002` is updated to the new id.
  First-Class and any other consumer take it through `/fls-dev:update_concrete_projects`, with no new tooling.

## Why

The other Django project cannot use the semantic icons until they install from outside the FLS tree.
A tag in a public
repo is the whole release process, as with the panel package. Declaring the dependency in
`[project].dependencies` lets First-Class resolve it with no entry of its own, and the editable layer
gives live edits across every worktree without changing the committed `pyproject.toml` or `uv.lock`.

## What is settled

- Public GitHub repo at `preludetech/django-semantic-icons`, owned by Prelude Technologies.
  Distribution name `django-semantic-icons`, import name and app label `semantic_icons`, first
  release `v0.1.0`. No PyPI, no submodule.
- Licence, contributions and First-Class's permission follow the panel package: all rights
  reserved until a licence is chosen, no outside contributions, no tag or file stating an
  open-source licence.
- Each vendored icon set keeps its own licence. Its notice ships with its data, `LICENSE` names
  the set and its licence, and any attribution a set's licence requires is met. A set whose
  licence the package cannot meet is not vendored.
- `extract-semantic-icons-app-1-standalone-app` and `extract-semantic-icons-app-2-host-icons` have
  already made the package standalone and complete: neutral settings, bundled icon data, host
  icons, startup checks. This spec moves the code and re-verifies it from a clean checkout, and does
  not change behaviour. If the moved suite fails standalone, the fix goes back to the cause in the
  package, not into a shim.
- The `<c-icon>` cotton component name and arguments are unchanged.
- The vendored icon data and its licence notices ship as package data, and the wheel test asserts both.
- The deprecated `FREEDOM_LS_ICON_*` aliases from `extract-semantic-icons-app-1-standalone-app` are
  still honoured in `v0.1.0`, with their deprecation warning. FLS and First-Class already moved to the
  new names in that spec. They are removed no sooner than one
  tag later, under the changelog's deprecation rule.
- `invariants/test_no_font_awesome.py` stays in FLS.
- The panel framework package does not depend on this package, and this package does not depend on
  it. Both are installed by FLS side by side.
- Dependency form, dev loop and the pin-bump rule are the panel package's: the pin bump ships in the
  same FLS change as any package change FLS needs, and a pre-merge check fails when the installed
  `semantic_icons` is not the locked rev.
- The repo layout leaves room for `claude_plugins/semantic-icons/`, which
  `extract-semantic-icons-app-4-claude-plugin` fills. This spec creates no plugin, no `update`
  command and no host doc beyond the README.
- Package data layout and the wheel contents test copy the panel package's approach.

## Open until the spec

- **Template-tag library name.** The library is `icon_tags`. It is renamed only if the name would
  clash in a host project or with another installed package; the spec checks the FLS libraries
  (`course_icon_tags` is distinct) and the panel package, and decides.
- **How the package declares `django-cotton`.** As a `[project].dependencies` entry or as a documented
  host requirement, given `<c-icon>` needs cotton installed and its loaders configured.
- Whether the locked-rev check is shared with the panel package's or a second copy.

## Out of scope

- Host-icon features, the settings rename and the bundled data build
  (`extract-semantic-icons-app-1-standalone-app`, `extract-semantic-icons-app-2-host-icons`).
- The Claude Code plugin and the host doc (`extract-semantic-icons-app-4-claude-plugin`).
- Changing how templates call `<c-icon>`, new icon sets beyond the four, an icon picker UI.
- PyPI publishing, a private repo, a git submodule.
- Choosing an open-source licence, and accepting outside contributions.
- Tidying the other repos in `/home/sheena/workspace/lms/django_apps/`.

## Resources

- Source idea and effort material: `spec_dd/1. next/extract-semantic-icons-app/research_coupling_audit.md`
  (reverse import list, First-Class usage in section 6, docs in section 8);
  `spec_dd/1. next/extract_panels_framework/research_packaging_and_distribution.md` (repo layout,
  changelog flags, deprecation rule; its `uv.toml` and app-label claims do not apply).
- The pattern to copy: `spec_dd/1. next/extract_panels_framework-5-package-and-install/idea.md`.
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` for the flag schema;
  `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md`,
  `claude_plugins/fls-dev/scripts/install_dev.sh` and `rebuild_after_rebase.sh`.
- `freedom_ls/icons/`, `config/settings_base.py`, `pyproject.toml`, `package.json`,
  `.github/workflows/tests.yml`, `test_organisation/import_contracts.toml`.
- First-Class at `/home/sheena/workspace/first_class/First-Class-LMS.git/main`
  (`config/customisation.py`, `Dockerfile`).
- Skills: `fls-dev:git-worktree-setup`, `fls-dev:update_upgrade_notes`, `fls-dev:icon-usage`, `ds:testing`.
