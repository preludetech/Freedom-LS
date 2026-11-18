The spec_dd process is very slow and not very clear in places.

1. Update the spec_dd docs so it shows drawio diagrams of the major commands, to show the process they follow.  Eg when implementing a plan the main agent reads the plan, then splits things into subagents. Subagents do stuff, run tests, etc.
I want a clear visual representation of each step in the process and where the hooks fit in.

When do things call the rebase workflow, etc

2. Find space for time-efficiency
It seems that we run the full test suite quite often. It seems repetitive.  It takes really long

3. token efficiency
Are there any sections that take too many tokens? Research to find best practices. We still want the skills etc to be clear to read for a human. And we dont want to compromise on quality
