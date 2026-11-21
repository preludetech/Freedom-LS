# Answers: faster-test-runs-10-rerun-only-failures-in-a-batch

Asked by `/sdd:start` before the spec was written.

- Q: After a failed run inside a batch, if the fix edits files outside the failing tests' apps, does the re-run widen? → A: Yes, by the fix's diff: re-run the failed tests plus the targeted selection for the files the fix itself changed. (asked up front)
- Q: Does the targeted run after a parallel batch wave is integrated stay? → A: Keep it; it is the only test of the combined batches before the next wave builds on them, and its failures follow the new failed-only re-run rule. (asked up front)
- Q: Does the rebase command's test step follow the same rule? → A: For `targeted`, yes: a failed run re-runs only the failures. A `full` run keeps the whole-tier gate, so the `finish_worktree` checkpoint is unchanged. (asked up front)
