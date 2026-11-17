The SDD finish worktree command needs to be improved

If we try to finish multiple worktrees at the same time then they often clash. One will make progress, another will finish, requiring the others to be rebased and potentially causing conflicts. They will all run tests at the same time eating up ram, causing tests to crash and and need to be restarted (wasting time)

We need some kind of coordinating mechanism.

Here's an idea (maybe not a good one, feel free to suggest something else)
1. in individual worktrees, have an sdd command that marks the worktree as ready to be finished. This can either make a change in the worktree itself, or update a shared file, or edit the spec directory on main to give it a new status. Do any checks needed at this time, noting that a rebase might result in certain checks being out of date
2. In main: Have a command for "finish worktrees". It will look at the worktrees that are marked as ready and crunch through them. It must not ask for confirmation to finish things, it must just go ahead
