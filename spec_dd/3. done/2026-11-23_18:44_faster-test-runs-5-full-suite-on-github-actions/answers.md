# Answers: faster-test-runs-5-full-suite-on-github-actions

Asked by `/sdd:start` before the spec was written.

- Q: Once the unit tests run across several GitHub jobs, should the 92% coverage threshold still be enforced? → A: Combine and enforce: each job uploads its coverage data, a final job combines it and fails under 92% (asked up front)
- Q: When an SDD run needs the full tier remotely, may it push the branch itself first? → A: Push automatically: the SDD run pushes the branch, starts the workflow on that commit and waits (asked up front)
- Q: When GitHub is unreachable, the run fails to start, or the queue is slow, what should the SDD run do? → A: Fall back to local: past a configured wait, cancel the remote run and run the full tier locally, saying why (asked up front)
- Q: For FLS itself, should the full tier run on GitHub Actions by default once this lands? → A: Remote by default: FLS's config points the full tier at GitHub; a local run stays available on request (asked up front)
- Q: The main worktree had uncommitted changes from other processes; create the worktree anyway? → A: Create it anyway; the clean-tree check was waived for this run (asked up front)
- Q: How should the suite be split across GitHub jobs? → A: pytest-split by duration: a committed durations file, each job runs one group of N (asked while research ran)
- Q: How should the workflow fix the Playwright install failure on ubuntu-latest (26.04)? → A: Pin `ubuntu-24.04` for every test job; no Playwright bump (asked while research ran)
- Q: Which marker set should the remote full run cover? → A: Superset: include `ci_only` and `weasyprint` (install the WeasyPrint system libraries on the runner); a remote pass still counts as a full run (asked while research ran)
- Q: Should a remote full-tier verdict include the lint and type-check jobs? → A: Tests only: the verdict reads the test jobs and the coverage combine job (asked while research ran)
- Q: Where should each test job's group report come from? → A: Extend the generic test runner: an opt-in keep path and failure text on failed outcomes (asked at review)
- Q: How should the remote command avoid queueing behind a pull_request run (26 jobs vs the 20-job limit)? → A: "we dont need the pr run. Just tests." Read as: drop the `pull_request` trigger; dispatch runs run the test jobs only (asked at review)
- Q: When should FLS's remote default switch on? → A: Ship enabled and rely on the local fallback (asked at review)
- Q: Split by test or by file, given `--dist loadfile`? → A: By test, then measure each group against a 12-minute bar (asked at review)
