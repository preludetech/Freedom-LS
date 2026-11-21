# Tests run in Claude Code cloud sessions

Spec 7 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** none for a full run beyond what `faster-test-runs-5-full-suite-on-github-actions` gives.

## What

A test run, or a whole SDD batch with its tests, can be handed to a Claude Code cloud session and
its result brought back to the worktree.

## Why

This is the fallback. It is built only if the rest of the effort leaves the local machine unable to
run several worktrees at once. A cloud session moves the agent as well as the tests off the
machine, which GitHub Actions cannot do.

## What is settled

- Nothing here starts until every other spec in the effort is done and the owner has confirmed the
  local machine is still the bottleneck.
- Usage must stay inside the existing Claude subscription. No separately billed compute.

## Open until the spec

- How the `sdd`, `ds` and `fls-dev` plugins become available in a cloud session, which does not
  install plugins a repository enables through marketplaces.
- Whether the suite passes on PostgreSQL 16, the version a cloud session ships, or PostgreSQL 17
  is run in Docker there.
- Whether a 4 vCPU, 16 GB session finishes the full suite in useful time.
- Whether the Playwright browser can be installed at the default network level.
- Which unit is handed over: a test tier, a batch, or a whole spec.

## Out of scope

- Scheduled cloud runs.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Claude Code cloud sessions".
- <https://code.claude.com/docs/en/claude-code-on-the-web.md>
