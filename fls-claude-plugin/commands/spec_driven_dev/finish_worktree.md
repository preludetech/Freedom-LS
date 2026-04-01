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

Call `./dev_db_delete.sh`

# Step 4

Move the current spec directory from `in progress` to `done` and name them appropriately with the current data and time
