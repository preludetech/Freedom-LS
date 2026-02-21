---
description: Check that the spec makes sense
allowed-tools: Read, Glob
---

You are helping to refine a feature spec. The spec might have problems. You are doing a final check to make sure it can be implemented.

Always adhere to any rules or requirements set out in any CLAUDE.md files when responding.

# Output

- Edit the spec document to overcome all the problems
- Print a short summary of what you did 

# Step 1 

Read over the spec and look for contradictions. Handle one contradiction at a time.

For each contradiction:
- Clearly describe the contradiction, ask for input
- Edit the spec file to fix the contradiction 

Keep repeating this process until there are no more contradictions.

# Step 2

Read over any implementation details mentioned in the spec and make sure that they adhere to project norms, and that they are technically feasible.

Read through all the documentation in @.claude/docs/ and make sure the spec does not go against any project norms defined there.

Read any mentioned source code files and any related code and look for inconsistencies and problems.

For each problem you find:
- Clearly describe the problem, ask for input if the solution if needed
- Edit the spec file to fix the contradiction 

# Step 3

Return to Step 1 and make sure no new problems were introduced. Repeat the whole process until the spec has no unaddressed problems

# Out of scope 

- Do not add technical implementation details to the spec. Just check the ones already included.
- If there are any technical concerns then raise them in a high level way, don't write unnecessary code