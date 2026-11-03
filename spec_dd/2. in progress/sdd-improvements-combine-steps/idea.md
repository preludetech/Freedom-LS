The SDD process still requires too much input from the user for things that should just happen automatically.

Make the following changes:

1. /sdd:start

After the worktree is set up and the everything is installed (the standard start process)

- if there is a design_prompt.md then call sdd:register_design
- call spec_from_idea

Note that these commands might ask the user for input, so it would be good for you to try and get the input up front so that nothing gets stored. The idea is to get as much progress done as possible without stalling the process.

Use subagents were ever possible to protect context and run things in parallel

2. Implement plan

As soon as the plan is implemented, then run the QA.
That we may want to run the QA again after making changes to the code So it still needs to be something we can run independently

Again, make use of parallel subagents wherever possible in order to protect context and speed things up.
