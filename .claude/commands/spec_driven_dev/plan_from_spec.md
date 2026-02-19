---
description: Create an implementation plan based on a spec file
allowed-tools: Read, Write, Glob
---

You are helping to take a comprehensive development plan, based on this a spec file. Always adhere to any rules or requirements set out in any CLAUDE.md files when responding.

# Output 

- Create a plan document in the same directory as the spec file. Name it `2. plan.md`
- Optionally: Create a document called `3. frontend_qa.md`
- Print a short summary of what you did

# Step 1

Read the spec carefully and make sure you understand what is needed.

If there are any contradictions then ask for clarification and fix the spec before continuing.

# Step 2

Investigate existing code to find relevant files and functionality. Make sure the code is kept DRY. If there is existing functionality we should be using, mention it in the plan.

# Step 3 

Write the plan document.

# Step 4 

Look over all the available skills and mcps. Update the plan to say what skills and mcps should be used where. 

# Step 5

If there are changes to any frontend then create a frontend_qa.md file.

This should explain how to check that the feature works using a browser. It should explain where to go, how to log in, what urls to visit, what buttons to click, what you expect to see, etc. 

This can include multiple tests and workflows. 

If this plan is created then reference it in the plan file as a final step. 

# Notes

- Note we will be following TDD. Do not write out all the tests at this point. 
- Include pseudocode for desired functionality where appropriate
- if specific functions should be used or edited, or specific files need to be edited or referenced, mention them in the task description
