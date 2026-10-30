# Integrating one completed FLS spec into a concrete project

Inputs from the caller: `<project-root>` (absolute path, or `.` when run inside the project) and `<spec-commit>` (the FLS commit that moved the spec into `spec_dd/3. done/`).

Every command below targets the project through `<project-root>`, so it behaves the same from any working directory: `git -C <project-root> …`, `uv run --directory <project-root> …`, `uv sync --directory <project-root>`, `npm --prefix <project-root> …`. The working tree must be clean when the integration starts. That precondition is what lets 3j commit everything and Rollback delete every untracked file.

# Per-spec integration

Run 3a to 3j in order for one spec.

## 3a. Read the upgrade notes

Read `<project-root>/submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md` and parse its frontmatter flags. These drive which of the steps below actually run.

**Backward compatibility:** if the file is absent, **warn** that the spec has no structured notes and **fall back to prose inference**: read the spec's `1. spec.md` and `2. plan.md` (and, if needed, the actual code diff for that commit) to infer the required integration work. The flag-driven steps below then become judgement calls based on that reading.

## 3b. Pre-flight migration check

Before moving the pointer, confirm the concrete project's migration state is clean:

```
uv run --directory <project-root> python manage.py migrate --check
```

If this fails, stop and resolve the dirty migration state before integrating further. Do not move the pointer on top of an inconsistent database state.

## 3c. Move the submodule pointer

Update `submodules/Freedom-LS` to the commit that completed this spec:

```
git -C <project-root>/submodules/Freedom-LS fetch origin main
git -C <project-root>/submodules/Freedom-LS checkout <spec-commit>
```

## 3d. Sync dependencies

Always sync after the pointer moves. A spec may have introduced new FLS dependencies even when `requires_package_upgrade` is not set:

```
uv sync --directory <project-root>
```

Concrete-project CI uses `uv sync --locked`, so make sure `uv.lock` ends up committed alongside the integration.

## 3e. Apply the flagged integration steps

Run only the steps the notes call for (or that prose inference indicated, for specs without notes). **Apply settings before migrations.** `migrate` and `makemigrations` run Django's full system-check set, so a spec that adds both a boot-enforced setting and a migration aborts on that setting's check if the migration runs first:

- **`requires_settings_change`**: review and apply the listed `changed_settings` to the concrete project's `config/`.
- **`requires_migrations`**: `uv run --directory <project-root> python manage.py makemigrations`, then `uv run --directory <project-root> python manage.py migrate`.
- **`requires_package_upgrade`**: apply the listed `changed_packages`. `uv sync` already covers part of this; reconcile versions if the notes pin specific ones.
- **`requires_npm_install`**: add the listed `changed_npm_packages` to the concrete project's own `package.json`, then run `npm --prefix <project-root> install`. Unlike `uv sync`, this is **not** auto-resolved from the submodule. The concrete project keeps a standalone `package.json`, so the new deps must be mirrored in by hand. Commit the updated `package-lock.json` alongside the integration. Run this **before** any Tailwind rebuild so new icon sets and packages are present when the bundle is built.
- **`requires_tailwind_rebuild`**: `npm --prefix <project-root> run tailwind_build`.
- **`requires_template_review`**: run the template-drift detection in 3f.

## 3f. Template-drift detection (when `requires_template_review` is set)

The project's template directories are the ones listed under `TEMPLATES[*]['DIRS']` in its settings, plus the `templates/` directory of each project app. For each path in `changed_template_paths`, check whether any of those directories holds a file at the same template path. If one does, the upstream source changed underneath the override, so the override may now be stale.

**Flag** every such override for human review: report the path and the sentence that its upstream source changed. **Do not auto-merge.** Re-applying customisations is a human decision.

## 3g. System check

After applying the integration, run FreedomLS's system checks to catch configuration drift the pointer move introduced:

```
uv run --directory <project-root> python manage.py check
uv run --directory <project-root> python manage.py check --deploy --settings=<the project's production settings>
```

Both runs are needed. FLS registers checks in both groups and neither run is a superset of the other. The deploy-gated ones guard production-only configuration (storage, caches, proxy headers), and a pointer move is exactly what lands new configuration for them to catch. Skipping that run is how a misconfigured production setting reaches production silently. The spec's `upgrade_notes.md` names any check ids that spec adds or changes; FLS's own `docs/deployment-security-checklist.md` documents what every id reports.

`--deploy` needs the production settings module, since the checks read settings that only exist there. If the environment this runs in cannot supply the production settings, say so and hand the `--deploy` run to the deploy pipeline rather than skipping it.

`migrate` and `makemigrations` already run the non-deploy check set internally, so that half is not the only place a failure would surface. Running it directly here is about attribution (a configuration `Error` would otherwise read as a migration-gate failure) and warning visibility (only a direct `check` sets `display_num_errors`). Errors abort the run: stop and resolve them. Warnings do not abort, but read and act on them rather than skimming past.

## 3h. Post-flight conflict check

After applying the integration, confirm no migrations are missing or in conflict:

```
uv run --directory <project-root> python manage.py makemigrations --check
```

A non-zero result here means the integration left the migration state inconsistent (for example a model change with no migration). Resolve it before committing.

## 3i. Verify

Confirm the concrete project has a `tests/` file that imports `freedom_ls.contrib.conformance`. If no such file exists, write one with **exactly** the contents below, note that it was added, and continue:

```python
# tests/test_fls_conformance.py
from freedom_ls.contrib.conformance import *  # noqa: F401,F403
```

Write it verbatim and customise nothing. In particular, **never** add a `conformance.drop(...)` call: dropping a probe is a decision about a route that project has actually customised, and it belongs in the project's own `conftest.py`, not in a file this procedure generates.

If the project already has a conformance file but wants to avoid shadowing same-named tests of its own, the collision-safe form binds all seven probes explicitly:

```python
from freedom_ls.contrib import conformance

test_active_icon_set_resolves = conformance.test_active_icon_set_resolves
test_active_theme_resolves = conformance.test_active_theme_resolves
test_admin_registry_survives_installed_apps_override = (
    conformance.test_admin_registry_survives_installed_apps_override
)
test_configured_backend_instantiates = conformance.test_configured_backend_instantiates
test_fls_namespace_reverses = conformance.test_fls_namespace_reverses
test_migration_state_consistent = conformance.test_migration_state_consistent
test_reference_url_reverses = conformance.test_reference_url_reverses
```

Binding a subset is a silent false green: the probes you leave out never run.

**Why add the file even though the probes may already be running.** A concrete project that falls back to recursive collection over the vendored `submodules/Freedom-LS` tree already collects `freedom_ls/contrib/conformance/test_*.py` directly, so the suite runs whether or not this file exists. That is incidental, not a contract: it depends on collection scope the project can change at any time, and if it later points `testpaths` at its own `tests/` dir the conformance signal disappears with no error. An explicit opt-in file makes the conformance contract intentional, keeps it stable under either collection scope, and gives the probes node IDs under the project's own `tests/`.

Stop and report only if the file cannot be written.

A caller may stop before this test run to run its own gate. Otherwise run the portable contract test set and confirm everything passes. This is where the conformance suite above actually runs, alongside the concrete project's own suite. The set deselects FLS's browser tests, brand/demo-coupled tests, and slow-only tests, because the concrete project is verifying its own wiring, not re-running FLS's regression suite:

```
uv run --directory <project-root> pytest -m "not playwright and not fls_internal and not ci_only and not weasyprint and not dev_tooling"
```

If there are front-end changes, use the Playwright MCP to verify things work visually.

## 3j. Commit

The tree was clean when the integration started, so everything changed or untracked is the integration's. Commit the submodule update and all integration changes together, including the updated `uv.lock`, before moving to the next spec:

```
git -C <project-root> add -A
uv run --directory <project-root> git commit -m "Update FLS: <spec-name>" -m "spec_dd/3. done/<spec-dir>
submodules/Freedom-LS: <old-sha> -> <new-sha>"
```

`<spec-name>` is the spec's done directory name, the same string as `<spec-dir>`, so a later run can match the subject against `spec_dd/3. done/`. Both `-m` arguments are required: a commit with no message would open an editor, which has no terminal here. The first is the subject; the second is the body, naming the FLS spec directory and the pointer move.

If consecutive specs are trivially simple (no integration work needed beyond updating the pointer), they may be combined into a single commit, but this should be the exception, not the rule.

# Final sync

Run once, after the last spec has been integrated:

1. Update the submodule to the latest `origin/main`: `git -C <project-root>/submodules/Freedom-LS checkout origin/main`.
2. If the submodule pointer moved further (there are commits after the last spec), run `uv sync --directory <project-root>` and commit the final pointer update.
3. Run the test run in 3i one last time.

# Rollback

If a spec fails partway through (tests won't pass, a system check fails, a migration conflicts, an override can't be reconciled), return to the last known-good state rather than committing a broken integration. The last good state is the previous `Update FLS: <spec-name>` commit, or the pre-update HEAD if this was the first spec. First, reset the tracked state and list what the run left behind:

```
git -C <project-root> reset --hard <last-good-sha>
git -C <project-root> submodule update --init submodules/Freedom-LS
git -C <project-root> status --porcelain -z --untracked-files=all
```

Every `?? ` entry of that NUL-separated output is the run's own file, because a clean tree was a precondition. Delete them with one `git -C <project-root> clean -f -- '<path>' '<path>' …` call, each path single-quoted so no name is shell-interpreted. Then run `rmdir -p --ignore-fail-on-non-empty` on the directory each one lived in, because `clean -f` removes files, not the directories they leave empty. Neither `git checkout -- .` nor an unscoped `git clean` is used.

Last, re-sync dependencies to the restored pointer, including npm packages, since the reset restored `package.json` and `package-lock.json`:

```
uv sync --directory <project-root>
npm --prefix <project-root> install
```

Then run `uv run --directory <project-root> python manage.py migrate --check` and the test run in 3i to confirm green. You are now back at the last successfully integrated spec. Investigate the failure (often a missing override re-apply or a migration that needs to be generated by hand) before retrying that spec.
