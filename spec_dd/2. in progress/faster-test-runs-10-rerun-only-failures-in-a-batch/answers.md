# Answers: faster-test-runs-10-rerun-only-failures-in-a-batch

Asked by `/sdd:start` before the spec was written.

- Q: After a failed run inside a batch, if the fix edits files outside the failing tests' apps, does the re-run widen? → A: Yes, by the fix's diff: re-run the failed tests plus the targeted selection for the files the fix itself changed. (asked up front)
- Q: Does the targeted run after a parallel batch wave is integrated stay? → A: Keep it; it is the only test of the combined batches before the next wave builds on them, and its failures follow the new failed-only re-run rule. (asked up front)
- Q: Does the rebase command's test step follow the same rule? → A: For `targeted`, yes: a failed run re-runs only the failures. A `full` run keeps the whole-tier gate, so the `finish_worktree` checkpoint is unchanged. (asked up front)

Asked at the end of `/sdd:spec_from_idea`, after the review wave.

- Q: How does the failed-only re-run get the failed node IDs through `run_test_tier.md`? → A: Extend the helper: a failed-only input, and it returns the failing node IDs.
- Q: What happens to tests a `RESULT FAIL` run left unfinished? → A: The runner prints them as `run: unfinished` lines and the failed-only re-run includes them.
- Q: Does the spec touch `implement_plan` Step 3 point 3 (the fix after the final full run)? → A: Keep the single-test loop, then point at the failed-only re-run; a `tier: full` escalation there is an ordinary full run and records.
- Q: Should the runner cap its `run: failed` lines? → A: Yes, at 200, then "and N more"; past the cap the whole-tier re-run applies.
