## Step 1 

Fetch the PR comments made by claude by using this command

```
gh pr view {pr_id} --comments --json comments
```

## Step 2 

For each issue that was raised:

```
mention the issue
if you think the issue needs to be addressed:
   address it immediately
else:
   say why you wont/can't address the issue
   ask for user confirmation from the user
```