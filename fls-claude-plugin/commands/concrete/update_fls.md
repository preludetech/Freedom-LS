Update the FreedomLS submodule (`submodules/Freedom-LS`) to the latest version, integrating each completed spec one at a time.

The core flow is unchanged: advance the submodule **spec by spec**, integrate each completed spec, run a test gate, and make **one commit per spec** (`Update FLS: <spec-name>`). On top of that, this command reads each spec's structured `upgrade_notes.md` to know exactly which integration steps to run, previews the whole plan before touching anything, guards migrations, and documents how to roll back a failed spec.

# Step 1: Identify new completed specs

1. `cd submodules/Freedom-LS && git fetch origin main`
2. Note the current submodule commit (this is what the concrete project currently uses).
3. Look at the FLS commit log from the current submodule commit to `origin/main`. Identify commits that moved a spec directory into `spec_dd/3. done/`. Each of these represents a completed spec. The directory names include the completion date (e.g. `2026-03-18_13:49_webhook-translation-layer`).
4. List the completed specs in chronological order. These are the ones we need to integrate.

# Step 2: Dry-run preview (no changes yet)

Before moving any pointer, show the operator the full plan so they can see what is about to happen.

For each pending completed spec, in chronological order, read its upgrade notes at:

```
submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md
```

This file is authored as part of FLS's own spec-completion workflow (the `/update_upgrade_notes` command). It carries a YAML frontmatter block of machine-readable flags:

- `requires_migrations`
- `requires_template_review` (+ `changed_template_paths`)
- `requires_settings_change` (+ `changed_settings`)
- `requires_package_upgrade` (+ `changed_packages`)
- `requires_tailwind_rebuild`

Print a preview table — one row per spec — listing the spec name and the flags its notes set. If a spec has **no `upgrade_notes.md`** (older specs predate the artifact), mark that row **"no notes — will infer from spec/plan prose"**.

Present the preview and let the operator confirm before any pointer moves. Do not modify the submodule or the concrete project during this step.

# Step 3: Integrate each spec sequentially

For each completed spec, in chronological order, use a subagent to do the following.

## 3a. Read the upgrade notes

Read `submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/upgrade_notes.md` and parse its frontmatter flags. These drive which of the steps below actually run.

**Backward compatibility:** if the file is absent, **warn** that the spec has no structured notes and **fall back to the previous prose-inference behaviour** — read the spec's `1. spec.md` and `2. plan.md` (and, if needed, the actual code diff for that commit) to infer the required integration work, exactly as before. The flag-driven steps below then become judgement calls based on that reading.

## 3b. Pre-flight migration check

Before moving the pointer, confirm the concrete project's migration state is clean:

```
uv run python manage.py migrate --check
```

If this fails, stop and resolve the dirty migration state before integrating further — do not move the pointer on top of an inconsistent database state.

## 3c. Move the submodule pointer

Update `submodules/Freedom-LS` to the commit that completed this spec:

```
cd submodules/Freedom-LS && git checkout <commit-hash>
```

## 3d. Sync dependencies

Always run `uv sync` after the pointer moves — a spec may have introduced new FLS dependencies even when `requires_package_upgrade` is not set:

```
uv sync
```

(Concrete-project CI uses `uv sync --locked`, so make sure `uv.lock` ends up committed alongside the integration.)

## 3e. Apply the flagged integration steps

Run only the steps the notes call for (or that prose inference indicated, for specs without notes):

- **`requires_migrations`** → `uv run python manage.py makemigrations && uv run python manage.py migrate`
- **`requires_settings_change`** → review and apply the listed `changed_settings` to the concrete project's `config/`.
- **`requires_package_upgrade`** → apply the listed `changed_packages` (already partly covered by `uv sync`; reconcile versions if the notes pin specific ones).
- **`requires_tailwind_rebuild`** → `npm run tailwind_build`.
- **`requires_template_review`** → run the template-drift detection in 3f.

## 3f. Template-drift detection (when `requires_template_review` is set)

For each path in `changed_template_paths`, check whether the concrete project ships its own override of that template (a file at the same template path under the concrete project's own template directories). If it does, the upstream source changed underneath the override, so the override may now be stale.

**Flag** every such override for human review — report the path and that its upstream source changed. **Do not auto-merge**; re-applying customisations is a human decision.

## 3g. Post-flight conflict check

After applying the integration, confirm no migrations are missing or in conflict:

```
uv run python manage.py makemigrations --check
```

A non-zero result here means the integration left the migration state inconsistent (e.g. a model change with no migration). Resolve it before committing.

## 3h. Verify

Run the full test suite and confirm everything passes:

```
uv run pytest
```

If there are front-end changes, use the Playwright MCP to verify things work visually.

## 3i. Commit

Commit the submodule update and any integration changes together (including the updated `uv.lock`) before moving to the next spec. Use a commit message like: `Update FLS: <spec-name>`.

If consecutive specs are trivially simple (no integration work needed beyond updating the pointer), they may be combined into a single commit — but this should be the exception, not the rule.

# Step 4: Final sync

After all completed specs have been integrated:

1. Update the submodule to the latest `origin/main`: `cd submodules/Freedom-LS && git checkout origin/main`
2. If the submodule pointer moved further (i.e. there are commits after the last spec), run `uv sync` and commit the final pointer update.
3. Run the full test suite one last time: `uv run pytest`

# Rollback: recovering from a spec that fails mid-integration

If a spec fails partway through Step 3 — tests won't pass, a migration conflicts, an override can't be reconciled — return to the last known-good state rather than committing a broken integration. The last good state is the previous `Update FLS: <spec-name>` commit (or the pre-update HEAD if this was the first spec).

1. Discard the in-progress integration changes in the concrete project (working tree and index):
   ```
   git checkout -- .
   git clean -fd            # only if the spec added new untracked files you want gone
   ```
2. Reset the submodule pointer back to the last good commit:
   ```
   git submodule update --init submodules/Freedom-LS
   ```
   This restores `submodules/Freedom-LS` to the commit recorded in the last good concrete-project commit.
3. Re-sync dependencies to the restored pointer:
   ```
   uv sync
   ```
4. Confirm you are clean and green:
   ```
   git status
   uv run python manage.py migrate --check
   uv run pytest
   ```

You are now back at the last successfully-integrated spec. Investigate the failure (often a missing override re-apply or a migration that needs to be generated by hand) before retrying that spec.

# Per-spec loop (reference)

```
for spec in pending_completed_specs (chronological):
    notes = read frontmatter of submodules/Freedom-LS/spec_dd/3. done/<spec>/upgrade_notes.md
    if notes missing: warn("no upgrade_notes.md — falling back to prose inference"); infer from spec/plan/diff
    migrate --check                      # fail early on dirty migration state
    move submodule pointer to the commit that completed <spec>
    uv sync                              # pick up new deps
    if notes.requires_migrations:        makemigrations && migrate
    if notes.requires_settings_change:   apply notes.changed_settings
    if notes.requires_package_upgrade:   reconcile notes.changed_packages
    if notes.requires_tailwind_rebuild:  npm run tailwind_build
    if notes.requires_template_review:   flag drift for notes.changed_template_paths (no auto-merge)
    makemigrations --check               # catch conflicts introduced by this spec
    uv run pytest                        # test gate
    commit "Update FLS: <spec>"          # includes uv.lock
# on failure mid-spec: follow the rollback procedure above
```
