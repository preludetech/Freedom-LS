---
description: Advance the FreedomLS submodule one completed spec at a time, from inside a concrete project
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Skill, Agent, AskUserQuestion, mcp__plugin_ds_playwright__*
---

Update the FreedomLS submodule (`submodules/Freedom-LS`) to the latest version, integrating each completed spec one at a time.

The core flow is: advance the submodule **spec by spec**, integrate each completed spec, run a test gate, and make **one commit per spec** (`Update FLS: <spec-name>`). On top of that, this command reads each spec's structured `upgrade_notes.md` to know exactly which integration steps to run, previews the whole plan before touching anything, guards migrations, and documents how to roll back a failed spec.

# Step 1: Identify new completed specs

Before anything else, confirm the working tree is clean: `git status --porcelain` prints nothing and `git submodule status submodules/Freedom-LS` does not start with `+`. Otherwise stop and ask the operator to commit or stash first. The integration's commit in 3j stages everything with `add -A`, and its rollback deletes every untracked file, so both treat whatever is in the tree as the integration's own.

1. `git -C submodules/Freedom-LS fetch origin main`
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
- `requires_npm_install` (+ `changed_npm_packages`)
- `requires_tailwind_rebuild`

Print a preview table — one row per spec — listing the spec name and the flags its notes set. If a spec has **no `upgrade_notes.md`** (older specs predate the artifact), mark that row **"no notes — will infer from spec/plan prose"**.

Present the preview and let the operator confirm before any pointer moves. Do not modify the submodule or the concrete project during this step.

# Step 3 and 4: integrate

For each pending spec in order, follow `${CLAUDE_PLUGIN_ROOT}/resources/concrete_spec_integration.md` with `<project-root>` `.` and `<spec-commit>` the spec's commit, running its test run in 3i and its commit in 3j. After the last spec, run its final-sync section. On a failure mid-spec, run its rollback section before retrying.

# Step 5: Commit and push

This is the last step of the run. An integration that only exists locally is a submodule pointer nobody else's checkout can resolve, so the update is not finished until it is pushed.

1. Confirm nothing is left uncommitted:

   ```
   git status
   ```

   Anything still outstanding belongs in a final commit before the push — a stray `uv.lock` or `package-lock.json`, a regenerated Tailwind bundle, the conformance test file added in 3i. Use `Update FLS: final sync` for it.

2. Push the branch:

   ```
   git push
   ```

Only the concrete project is pushed. The submodule needs no push of its own: every commit the pointer now references is already on FLS's `origin/main`, which is what Step 1 fetched.

Do not push while any spec is still mid-integration or a template override is still flagged for human review — finish or roll back first. If the run happened on the concrete project's default branch, move the commits onto a branch and open a PR rather than pushing to the default branch directly.
