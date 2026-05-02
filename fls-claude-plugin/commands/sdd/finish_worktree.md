---
description: Do the final cleanup for the current worktree
allowed-tools: Bash, Read, Glob, Skill
---

This command merges the current worktree back into the main branch after doing some final cleanup and checks.

# Step 1

```
git rebase main
```

Fix any merge conflicts.

If there are any changes to the functionality or code proceed to step 2. Otherwise skip step 2 and go to step 3.

# Step 2

Run the unit tests in a sub-agent. Fix any problems

If there is a frontend_qa.md file for the specification this branch is for (inside spec_dd/2. in progress/{branch name}/3. frontend_qa.md) then:
- summarise any changes made
- say whether you think it would be useful to run the frontend_qa again or not
- ask the user for confirmation before moving forward

# Step 3

Call `.claude/fls/scripts/dev_db_delete.sh`

# Step 4: Update the todo list

Invoke the helper at `${CLAUDE_PLUGIN_ROOT}/commands/sdd/protected/update_todo.md` with:

- `<todo-path>`: the `todo.md` in the spec directory (now under `spec_dd/3. done/…/`)
- `tick:"Run `/finish_worktree` to clean up the worktree"`

No new items to add.

# Step 5

Move the current spec directory from `in progress` to `done` and name them appropriately with the current data and time

The spec directory should be named like this:

```
yyyy-mm-dd_HH:MM_{spec title}
```

# Step 6: Commit

Make a commit with the latest changes.
