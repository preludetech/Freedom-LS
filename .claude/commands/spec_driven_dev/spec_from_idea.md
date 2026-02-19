---
description: Create a specification based on an idea 
allowed-tools: Read, Write, Glob
# based on https://github.com/iamshaunjp/Claude-Code-Masterclass/blob/claude/snippets/commands/spec-v1.md
---

You are helping to spin up a new feature spec for this application, from a short idea provided in the user input below. 

Always adhere to any rules or requirements set out in any CLAUDE.md files when responding.

# Output 

- Create a spec document in the same directory as the idea file. Name it `1. spec.md`
- Print a short summary of what you did

# Step 1: gather information

Read the idea carefully.

Create sub agents to do the following:

- Analyze the existing codebase
- Research relevant best practices
- Examine reference implementations

# Step 2: User input

Ask questions if you are unsure of anything, or if you need further information.

If there are edge cases that can be handled in multiple ways, then ask what to do.

If there are any contradictions or ambiguity, ask what to do. 

If the idea includes implementation details and you think there is a better way to do things, then make suggestions. Challenge anything that looks wrong. 

Think carefully about what questions to ask and then ask the user to answer one question at a time. 

# Step 3: Create the specification document

Create a specification document based on the idea. Include:

- Why different features/functionality matter
- If decisions were made, why were they made
- Success criteria 

