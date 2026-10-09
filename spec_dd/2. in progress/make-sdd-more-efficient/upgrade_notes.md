---
requires_migrations: false
requires_template_review: false
changed_template_paths: []
requires_settings_change: true
changed_settings:
  - ".claude/sdd/config.md ## Test Hooks → Test tiers"   # optional: blank falls back to plain `uv run pytest`
  - "pyproject.toml [tool.test_tiers]"                    # optional: absent table keeps the plugin's generic lists
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: make-sdd-more-efficient

## Breaking changes

None. No model, migration, template, URL, Django setting or Python dependency changed. Nothing
in your application code needs to change.

This feature changes only the `django-stack` (`ds`) and `sdd` Claude Code plugins and FLS's own
test configuration. It affects you only if your project runs those plugins from the FLS checkout
(the `PLUGINS_ROOT` your `claude.sh` points at). The plugin commands that used to run the full
pytest suite now name one of three tiers (`none`, `targeted`, `full`), defined once in
`claude_plugins/django-stack/resources/test_tiers.md`. The `sdd` plugin reaches that file through a
new `Test tiers` key under `## Test Hooks` in `.claude/sdd/config.md`, read by
`claude_plugins/sdd/commands/protected/run_test_tier.md`. A project without that key still works:
every tiered step falls back to a plain `uv run pytest`, which is the behaviour you had before.

Partial runs (a targeted tier, a single TDD test, `pytest --co`) now pass `--no-cov`, and the
targeted and full tiers pass `-n auto`. Both flags need `pytest-cov` and `pytest-xdist`, which
FLS already depends on.

## Manual steps

Skip this section if your project does not run the `ds` and `sdd` plugins.

1. **Install the new wrapper script.** Re-run `/ds:init`. It copies the new
   `claude_plugins/django-stack/templates/wrapper_scripts/select_tests.sh` template to
   `.claude/ds/scripts/select_tests.sh`, fills in `PLUGINS_ROOT` and leaves your existing wrappers
   untouched. If your `.claude/settings.json` lists each `ds` wrapper script by name instead of the
   template's `Bash(.claude/ds/scripts/*.sh:*)` entry, add
   `Bash(.claude/ds/scripts/select_tests.sh:*)` beside the others.

2. **Point `sdd` at the tier definition.** Re-run `/sdd:init`, which adds a blank `## Test Hooks`
   section with a `Test tiers` key to `.claude/sdd/config.md`. Then set it:

   ```
   ## Test Hooks

   - Test tiers: claude_plugins/django-stack/resources/test_tiers.md
   ```

   The path is relative to your project root, the same way the `Rebase command` key is. Leave it
   blank to keep running the whole suite at every step.

3. **Generate the app dependency map if you do not have one.** The targeted tier selects tests
   from `docs/app_structure.md`. When that file is missing, every targeted run escalates to the
   full suite. Run `/ds:app_map` to create it.

4. **Optionally add `[tool.test_tiers]` to your `pyproject.toml`.** The table extends the
   plugin's generic lists with your project's own paths: `none` for paths that cannot change a test
   result, `escalation` for paths whose fan-out the mirror and the app map cannot see, and
   `tooling` for repository paths outside any app whose tests live elsewhere. FLS's own table in
   its `pyproject.toml` is a worked example, and `claude_plugins/fls-dev/resources/testing.md`
   explains each of its entries. The `[tool.test_tiers]` table in FLS's `pyproject.toml` is not
   inherited by your project, so copy whichever entries apply.

5. **Optionally ignore per-worker coverage fragments.** A full run under `-n auto` writes
   `.coverage.*` files and combines them at the end. Add `.coverage.*` to your `.gitignore` beside
   `.coverage` so an interrupted run leaves nothing to commit.

No migrations, no Tailwind rebuild, no package or npm installs are required for this upgrade.
