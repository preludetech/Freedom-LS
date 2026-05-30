Read over the entire sdd workflow and make it more token efficient:

See what is possible by researching claude code. Eg subagents can't call slash commands, can they use skills? Do they need permission to use skills? Etc
Find places in the current SDD workflow where wa are telling Claude to do things that are not possible

Look over new claude code features and see what functionality exists that we could benefit from

Where possible, code what type of model should run differnt parts of the workflow. For example, can we use Haiku in a subagent for running tests or making commits? Where and how can we control this. Aim for token efficiency and speed.

There are places where we execute batches of tasks in subagents, if one task fails then the whole batch needs to restart. Find possible problem areas and find ways to make things run more safely.

Sometimes sub-agents need input from the user so the main agent requests that input, but then can't pass it on to the sub agent. How can we address this? So the agents have the information they need as they need it?
