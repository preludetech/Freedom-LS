Recently, we upgraded the sdd process so it doesn't run the full test run as often as it did. It still does it far too much.

If we rebase on main from a worktree and only change some stuff in the spec directory, then that triggers a full test rerun. This is a giant waste of time!

When rebasing: Check what code changed, run the effected tests. Tests are not a sledgehammer. You are wasting hours and hours of time!
