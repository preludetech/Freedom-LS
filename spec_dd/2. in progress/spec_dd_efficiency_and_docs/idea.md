The spec_dd process is very slow and not very clear in places.

1. Update the spec_dd docs so it shows drawio diagrams of the major commands, to show the process they follow.  Eg when implementing a plan the main agent reads the plan, then splits things into subagents. Subagents do stuff, run tests, etc.
I want a clear visual representation of each step in the process and where the hooks fit in.

When do things call the rebase workflow, etc

2. Find space for time-efficiency
It seems that we run the full test suite quite often. It seems repetitive.  It takes really long

3. token efficiency
Are there any sections that take too many tokens? Research to find best practices. We still want the skills etc to be clear to read for a human. And we dont want to compromise on quality

4. remove steps we dont do
We don't use: address_pr_review

5. rebase on main
This often results in a full test run, even if there are only changes to the spec files

6. finish worktree randomly stops
Eg if the main branch has not been pushed, it stops. Just push the main branch. Find ways to solve problems yourself.
If there are flakey tests then diagnose and fix problems with a subagent if you can
if main moved rebase. keep going every time main moves unless there is some kind of incompatable change that would require a new qa run

Main thing:
The full test run takes a long time, and we run it over and over again. We need to not treat tests like a hammer.
We do need to run the full test suite
