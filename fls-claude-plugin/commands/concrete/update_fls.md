Update the FreedomLS submodule (`submodules/Freedom-LS`) to the latest version, integrating each completed spec one at a time.

# Step 1: Identify new completed specs

1. `cd submodules/Freedom-LS && git fetch origin main`
2. Note the current submodule commit (this is what the concrete project currently uses).
3. Look at the FLS commit log from the current submodule commit to `origin/main`. Identify commits that moved a spec directory into `spec_dd/3. done/`. Each of these represents a completed spec. The directory names include the completion date (e.g. `2026-03-18_13:49_webhook-translation-layer`).
4. List the completed specs in chronological order. These are the ones we need to integrate.

# Step 2: Integrate each spec sequentially

For each completed spec, in chronological order. Use a subagent to do the following:

## 2a. Update the submodule pointer

Update `submodules/Freedom-LS` to the commit that completed this spec:
```
cd submodules/Freedom-LS && git checkout <commit-hash>
```

## 2b. Understand what changed

Read the spec's `1. spec.md` and `2. plan.md` inside `submodules/Freedom-LS/spec_dd/3. done/<spec-dir>/` to understand what was built. This tells you what integration work may be needed in the concrete project.

## 2c. Integrate

Based on the spec, make any required changes to the concrete project. This varies widely — it could include:
- Running `uv run python manage.py makemigrations && uv run python manage.py migrate`
- Updating template overrides to match new FLS templates
- Adding new settings or config values
- Updating models that extend FLS base models
- Upgrading packages (e.g. if FLS upgraded Django, the concrete project must too)
- Rebuilding tailwind: `npm run tailwind_build`

If the spec and plan aren't enough to understand the required changes, look at the actual code diff for that commit in the submodule.

## 2d. Verify

Run the full test suite and confirm everything passes:
```
uv run pytest
```

If there are front-end changes, use the Playwright MCP to verify things work visually.

## 2e. Commit

Commit the submodule update and any integration changes together before moving to the next spec. Use a commit message like: `Update FLS: <spec-name>`.

If consecutive specs are trivially simple (no integration work needed beyond updating the pointer), they may be combined into a single commit — but this should be the exception, not the rule.

# Step 3: Final sync

After all completed specs have been integrated:

1. Update the submodule to the latest `origin/main`: `cd submodules/Freedom-LS && git checkout origin/main`
2. If the submodule pointer moved further (i.e. there are commits after the last spec), commit the final pointer update.
3. Run the full test suite one last time: `uv run pytest`
