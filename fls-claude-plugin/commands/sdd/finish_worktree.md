---
description: Do the final cleanup for the current worktree
allowed-tools: Bash, Read, Glob, Skill, Agent
---

This command merges the current worktree back into the main branch after doing some final cleanup and checks. It runs at **depth 0** and delegates mechanical steps to the `fls:sdd-mechanic` (Haiku) agent. See the `claude-code-authoring` skill for the model behind this.

# Step 1

```
git rebase main
```

Fix any merge conflicts (this may need judgement — keep it on the main thread).

If there are any changes to the functionality or code proceed to step 2. Otherwise skip step 2 and go to step 3.

# Step 2

Run the unit tests via `fls:sdd-mechanic`. Fix any problems.

If there is a frontend_qa.md file for the specification this branch is for (inside spec_dd/2. in progress/{branch name}/3. frontend_qa.md) then:
- summarise any changes made
- say whether you think it would be useful to run the frontend_qa again or not
- only if you think the frontend_qa should be run again, ask the user for confirmation before moving forward

# Step 3

Call `.claude/fls/scripts/dev_db_delete.sh`

# Step 4: Update the todo list

Delegate to `fls:sdd-mechanic`: invoke the helper at `fls-claude-plugin/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (now under `spec_dd/3. done/…/`)
- `tick:"Run `/finish_worktree` to clean up the worktree"`

No new items to add.

# Step 5

Delegate to `fls:sdd-mechanic`: move the current spec directory from `in progress` to `done` and name it appropriately with the current date and time.

The spec directory should be named like this:

```
yyyy-mm-dd_HH:MM_{spec title}
```

# Step 6: Tidy Claude project settings

Invoke the `update-claude-project-settings` skill to promote any useful permissions accumulated in `.claude/settings.local.json` to the shared `.claude/settings.json`, and clean up redundant entries in the project settings.

# Step 7: Commit

Delegate to `fls:sdd-mechanic`: make a commit with the latest changes.

# Step 8: Git Status

Run `git status` and confirm the working tree is clean — there must be nothing left to commit. If there are uncommitted changes, stop and resolve them before continuing.
