# Panel framework: own repo, git-tag install, FLS switches over

Spec 5 of 6 in the Panel framework extraction effort. Read the "Panel framework extraction" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The panel framework leaves FLS and becomes `django-panel-framework`, a public MIT-licensed GitHub
repo checked out at `/home/sheena/workspace/lms/django_apps/panel_framework`, released as the tag
`v0.1.0`. FLS then depends on that tag, edits it live in worktrees, and carries the change to
First-Class and the concrete template through its normal upgrade-notes flow.

The package repo:
- An explicit `[build-system]` (hatchling). Templates, static files and migrations ship as package
  data. A test builds the wheel and asserts the template, static and migration files are in it,
  because an editable install hides a missing file.
- The app moves from `freedom_ls/panel_framework`. Its app label becomes `panel_framework` and its
  migrations are regenerated as one clean `0001`. The `BulkActionRun` FK to `django.contrib.sites` is
  kept.
- Its own CI runs the standalone suites that specs 3 and 4 delivered (unit, component, invariants,
  Playwright with the Tailwind build).
- `CHANGELOG.md`, one entry per tag, carrying the same flags as FLS's `upgrade_notes.md`
  (`requires_migrations`, `requires_template_review` with `changed_template_paths`,
  `requires_settings_change`, `requires_tailwind_rebuild`). The deprecation rule is written at the top:
  a breaking change keeps the old surface with a deprecation warning for one tag.

FLS:
- `[project].dependencies` gains `django-panel-framework @ git+https://github.com/<org>/django-panel-framework.git@v0.1.0`.
  There is no `[tool.uv.sources]` entry for it, and no `uv.toml` (a project `uv.toml` shadows the whole
  `[tool.uv]` table and cannot set a source).
- The in-tree app is deleted. Every import prefix `freedom_ls.panel_framework` becomes
  `panel_framework`: 55 lines in 22 files, plus `INSTALLED_APPS` in `config/settings_base.py` and the
  `config/urls.py` include. `educator_interface`, `deployment`, `learner_management` (`RunStatus`),
  `qa_helpers` and `base` are the consumers. Template paths, `panel_tags`, `data_table_tags` and cotton
  names do not change. `docs/app_structure.md`, the `alpine-js` and `testing` skills in
  `claude_plugins/fls-dev/skills/` and the import-linter contract files under `test_organisation/`
  are updated or regenerated.
- The old `freedom_ls_panel_framework_bulkactionrun` table, its `django_migrations` rows and its
  ContentType rows are removed.
- Live editing: `claude_plugins/fls-dev/scripts/rebuild_after_rebase.sh` (which `install_dev.sh`
  calls) runs `uv pip install --no-deps -e "$PANEL_FRAMEWORK_DIR"` right after `uv sync`.
  `PANEL_FRAMEWORK_DIR` is absolute and defaults to the repo path above; the step is skipped with a
  message when the directory is missing. `UV_NO_SYNC=1` keeps `uv run` from reverting the link
  (developer shell, and the per-machine Claude Code settings `env` block for agents). This lives in
  `fls-dev`, never in `sdd` or `ds`.
- CI and Docker fetch the git dependency: `.github/workflows/tests.yml` uses `uv sync --locked`; `git`
  is added to `/home/sheena/workspace/lms/freedom_ls_infra/fls-base/Dockerfile` (it installs with
  `uv pip install --system -r pyproject.toml`, which reads only `[project].dependencies`, hence the
  PEP 508 form) and to the Python stage of `/home/sheena/workspace/lms/freedom-ls-concrete-template/Dockerfile`.
- Tailwind finds the package templates through the source command spec 4 delivers. FLS's
  `tailwind.input.css` imports its generated output and `npm run tailwind_build` runs after
  `uv sync`. In the concrete template's Docker build, Tailwind runs in a Node-only first stage before
  any Python exists, so the Python-dependency phase becomes its own stage and the Tailwind stage
  copies the installed `panel_framework` directory (or the generated source file) from it. The
  generated `@source` uses `not-ignored:` because `.venv` is gitignored and Tailwind v4 skips ignored
  paths.
- The spec's `upgrade_notes.md` sets `requires_package_upgrade` (changed package
  `django-panel-framework`), `requires_migrations`, `requires_template_review` and
  `requires_tailwind_rebuild`, lists the new `INSTALLED_APPS` entry and the new Tailwind import as
  manual steps, and says the old table is dropped. First-Class and the concrete template then take it
  through `/fls-dev:update_concrete_projects`, with no new tooling.

## Why

The other Django project cannot use the framework until it is installable from outside the FLS tree.
A tag in a public repo is the whole release process: no submodule pointer per consumer, no PyPI.
Declaring the dependency in `[project].dependencies` is what lets First-Class resolve it with no entry
of its own; the editable layer gives live edits across every worktree without changing the committed
`pyproject.toml` or `uv.lock`.

## What is settled

- Public GitHub repo, MIT, distribution name `django-panel-framework`, import name and app label
  `panel_framework`, first release `v0.1.0`. No PyPI, no submodule.
- The label change drops data, not migrates it: the deployed table holds nothing worth keeping.
  The new `0001` creates `panel_framework_bulkactionrun`, a different table name, so old and new do
  not collide on a database that still has the old table.
- Specs 3 and 4 have already made the package standalone: its own settings helper, CSV helpers,
  site-resolver hook, host contract and Tailwind source command. This spec moves the code and
  re-verifies it from a clean checkout, and does not change behaviour. If the moved suite fails
  standalone, the fix goes back to the cause in the package, not into a shim.
- Dependency form and dev loop, as above. The earlier `uv.toml` and `[tool.uv.sources]` path
  proposals are not options. Fallbacks for the dev loop, in order: `uv run --with-editable
  "$PANEL_FRAMEWORK_DIR"`, then `PYTHONPATH="$PANEL_FRAMEWORK_DIR"`.
- The pin bump ships in the same FLS change as any framework change FLS needs: edit in the package,
  test there, tag, bump the pin and `uv lock`, run the FLS suite. Local editable code can pass where
  CI on the old tag fails, so a pre-merge check fails when the installed `panel_framework` is not
  the locked rev.
- The package repo's `tests/` and `conftest.py` are self-contained (specs 3 and 4); the repo has a
  `dev` dependency group including `lxml`.
- The repo layout leaves room for `claude_plugins/panel-framework/`, which spec 6 fills. This spec
  creates no plugin, `update` command, consumer-suite script or developer doc.

## Open until the spec

- **Spike 1, run first: does `uv run` revert a hand-installed editable copy of a locked git
  package?** Install the locked git copy, `uv pip install --no-deps -e` the local repo, then run
  `uv run python -c ...` without `UV_NO_SYNC`. Fallback if it reverts (assumed): `UV_NO_SYNC=1` is
  mandatory and documented in `fls-dev:git-worktree-setup`. If even that is unreliable, fall back to
  `PYTHONPATH`.
- **Spike 2, run first: does First-Class resolve FLS's git dependency?** In a First-Class sandbox
  with FLS path-installed, confirm the PEP 508 line resolves transitively, and that a sources-only
  variant fails. Fallback if the PEP 508 line does not resolve: First-Class and the concrete
  template add the same line, or a `[tool.uv.sources]` entry, to their own `pyproject.toml`, and the
  upgrade notes list it as a manual step (`requires_package_upgrade`).
- **How FLS drops the old table, its history and its ContentType rows.** Recommended default: one new
  FLS migration in an app that survives (`base` is the candidate), run on every environment, with
  three steps: `RunSQL` `DROP TABLE IF EXISTS freedom_ls_panel_framework_bulkactionrun`, then
  `RunPython` that deletes the `django_migrations` rows for app `freedom_ls_panel_framework` and the
  ContentType rows for that app label (Permission rows cascade), both through the ORM. `IF EXISTS`
  makes it a no-op on a fresh database. The `RunSQL` needs the project's security review under the
  "no raw SQL" convention before it lands; if the review refuses it, the fallback is a
  documented manual step in the upgrade notes. The spec confirms the host app and the migration
  order against the new package's `0001`.
- Which hosting org owns the repo, and the exact URL in the pin.
- Whether CI needs a `pre-merge` job or a pre-commit hook for the locked-rev check, and where the
  check lives.
- Whether the Python stage added to the concrete template's Dockerfile needs `git` installed
  (the `uv:0.9-python3.13-bookworm-slim` image is not known to ship it) or the git fetch already
  happens in a stage that has it.

## Out of scope

- The Claude Code plugin, its `init` and `update` commands, the consumer-suite script and the
  developer doc (spec 6).
- Any change to the framework's behaviour or its host contract (specs 1 to 4).
- PyPI publishing, a private repo, a git submodule, a shared core package.
- Migrating data from the old table.
- Tidying `/home/sheena/workspace/lms/django_apps/content_engine` and `site_aware_models`.
- Re-auditing the framework's tests in `test-organisation-and-hygene-15-educator-interface`.

## Resources

- Source idea and effort material: `spec_dd/1. next/extract_panels_framework/idea.md`,
  `research_uv_sources_and_consumers.md` (this spec's research: dev loop, CI, Docker, Tailwind, the
  two spikes), `research_packaging_and_distribution.md` (repo layout, changelog flags, deprecation
  rule; its `uv.toml` and app-label claims do not apply), `research_coupling_audit.md` (reverse
  import list, section 3).
- `claude_plugins/fls-dev/commands/update_upgrade_notes.md` for the flag schema;
  `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md`,
  `claude_plugins/fls-dev/scripts/install_dev.sh` and `rebuild_after_rebase.sh`.
- `.github/workflows/tests.yml`, `tailwind.input.css`, `pyproject.toml`,
  `freedom_ls/deployment/housekeeping.py`, `test_organisation/import_contracts.toml`.
- First-Class at `/home/sheena/workspace/first_class/First-Class-LMS.git/main` and the concrete
  template at `/home/sheena/workspace/lms/freedom-ls-concrete-template`.
- Skills: `fls-dev:git-worktree-setup`, `fls-dev:update_upgrade_notes`, `ds:testing`.
- uv docs: https://docs.astral.sh/uv/concepts/projects/sync/,
  https://docs.astral.sh/uv/concepts/projects/dependencies/,
  https://docs.astral.sh/uv/concepts/configuration-files/.
