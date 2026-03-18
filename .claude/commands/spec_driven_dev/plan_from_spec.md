---
description: Create an implementation plan based on a spec file
allowed-tools: Read, Write, Glob
---

You are helping to take a comprehensive development plan, based on this a spec file. Always adhere to any rules or requirements set out in any CLAUDE.md files when responding.

# Output

- Create a plan document in the same directory as the spec file. Name it `2. plan.md`
- Optionally: Create a document called `3. frontend_qa.md`
- Print a short summary of what you did

DO NOT mention the frontend qa in the plan file. We will run the qa process after the plan is complete.

# Step 1

Read the spec carefully and make sure you understand what is needed.

If there are any contradictions then ask for clarification and fix the spec before continuing.

# Step 2

Investigate existing code to find relevant files and functionality. Make sure the code is kept DRY. If there is existing functionality we should be using, mention it in the plan.

# Step 3

Write the plan document.

# Step 4

Use a subagent to look over all the available skills and mcps. Update the plan to say what skills and mcps should be used where.

# Step 5

If there are changes to any frontend then create a frontend_qa.md file.

This should explain how to check that the feature works using a browser. It should explain where to go, how to log in, what urls to visit, what buttons to click, what you expect to see, etc.

This can include multiple tests and workflows.

If this plan is created then reference it in the plan file as a final step.

IMPORTANT: We will be generating a webserver port at random. we wont be using port 8000 (the default django runserver port). Don't talk about port 8000 in the test.
- `PORT=$(./find_available_port.sh)`
- We run the runserver command like this: `uv run python manage.py runserver $PORT`
- Base ul is `http://127.0.0.1:$PORT`

## Notes

- Note we will be following TDD. Do not write out all the tests at this point.
- Include pseudocode for desired functionality where appropriate
- if specific functions should be used or edited, or specific files need to be edited or referenced, mention them in the task description

## IMPORTANT

- DO NOT include any manual verification in the plan.md file, ALL manual verification should be in the frontend_qa file
- If you created a `3. frontend_qa.md` file, DO NOT mention it inside `2. plan.md`

# Step 6

Create subagents to review the plan and frontend_qa plan against the spec file. Make sure that:

- All the success criteria will be met by the plan in place
- No step in the plan contradicts any skill
- No step will result in junk files that need to be manually cleaned up
- All suggested code changes are clean and simple

### IMPORTANT
The plan.md file MUST NOT say that the frontend_qa should be run. We will run that separately.
