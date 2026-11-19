# Answers: spec_dd_efficiency_and_docs

Asked by `/sdd:start` before the spec was written.

- Q: The idea ends with "We do need to run the full test suite": when should the full suite run in an SDD cycle? → A: At sensible checkpoints (the spec names them; targeted tests everywhere else) (asked up front)
- Q: What format should the SDD process diagrams be? → A: `.drawio.svg`: editable in draw.io and renders inline on GitHub (asked up front)
- Q: When finish_worktree hits flaky tests, where should the subagent's fix land? → A: Fix in the current branch (asked up front)
- Q: For removing steps we don't use: besides address_pr_review, what should the spec do? → A: Remove address_pr_review; audit for other likely-unused commands and steps and list them as candidates for the user to confirm (asked up front)
- Q: Which files are in scope for the token-efficiency pass? → A: Everything an SDD run loads: sdd commands, resources and agents, plus the ds and fls-dev skills and resources it reads; the generic/FLS split is kept (asked up front)
- Q: What should still stop finish_worktree and ask the user? → A: Rebase conflicts in code (outside `spec_dd/`) and real, non-flaky test failures. A force-push: if finish_worktree can force-push, it does; otherwise it pauses, asks the user to force-push, then continues (asked up front)
- Q: Should this spec take on `0. maybe/better-finish-worktree-command` (finishing several worktrees at once)? → A: No, leave it out (asked while research ran)
- Q: finish_worktree stops today on a dirty main worktree and on an upstream change review of `direction: changed`. Keep those stops? → A: If the changes are only in the `spec_dd/` directory, continue. If code changes, pause (asked while research ran)
- Q: The dirty-main rule above fails as written (committing on local main leaves it diverged). How should finish_worktree handle someone's uncommitted edits in the main worktree that overlap the landing? → A: Never stash or touch them: another process may be working there. Tell the user main is dirty and ask whether finish_worktree should commit the edits itself, or wait for the user to commit main, then continue. This replaces the dirty-main half of the answer above (asked after the spec review)
- Q: How are the `.drawio.svg` diagrams produced and kept in sync? → A: Hand-authored in uncompressed draw.io XML, plus a check that every step heading of a command appears as a label in its diagram (asked while research ran)
- Q: The spec says there are two full-run points and names only `implement_plan` Step 3. What is the second? → A: `finish_worktree` does a full run. `qa_fix` can do targeted tests (asked after implementation)
- Q: With `finish_worktree` Step 1 on `full` and `qa_fix` on `targeted`, what does `do_qa` run after its last fix? → A: Targeted, like `qa_fix` (asked after implementation)
- Q: After Step 1's full run, what do the main-moved loop passes run? → A: The checkpoint tier (asked after implementation)
- Q: A main-moved loop pass entered before Step 7 stops after its rebase so nothing lands before the PR check and the close-out. Confirm? → A: Yes, and no PR approval check is needed: remove the PR guard from Step 7 (asked after implementation)
- Q: `test_memory_that_becomes_sufficient_ends_the_wait_with_the_sized_count` failed once under load. Fix or leave? → A: Fix it now (asked after implementation)
- Q: `plan_from_spec.md` Step 5 tells the plan to reference the QA file, and the same command says a plan never mentions QA. Which wins? → A: Delete the Step 5 line (asked after implementation)
