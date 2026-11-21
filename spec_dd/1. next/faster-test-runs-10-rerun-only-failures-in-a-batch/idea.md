# A batch re-runs only the tests that failed

Spec 10 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** one whole tier run per failure inside a batch. 79 runs failed in 3.5 days, and a large one takes a median of 22 minutes.

## What

When a batch's test run fails, the batch fixes the failure and re-runs the tests that failed. Once
those pass, the batch is done. It does not run the whole tier a second time.

## Why

The tier definition says the gate is the whole tier, so every failure costs the tier twice. 46 of
79 failed runs failed three tests or fewer, and 98 of the 130 runs that did not pass covered more
than half the suite. Under load the second run can fail on a different slow test and start the
cycle again. `implement_plan` ends with a full run and `finish_worktree` has its checkpoint, so a
regression the narrow re-run misses is still caught before the branch lands.

## What is settled

- Inside a batch, a failed run is followed by a re-run of the failed tests only.
- Review fix, design fix and integration fix batches follow the same rule.
- The whole-tier gate stays at `implement_plan`'s final full run and at the `finish_worktree`
  checkpoint.
- The rule is written in the tier definition, the one place that says how a failed run is handled
  today. Commands point there and do not restate it.
- A test that crashed its worker on every attempt still counts as failed.

## Open until the spec

- Whether a fix that edits files outside the failing tests' apps widens the re-run.
- Whether the targeted run after a parallel batch wave is integrated stays.
- Whether the rebase command's test step follows the same rule.

## Out of scope

- Flaky tests; the flaky test guide owns them.
- Which tests the first run selects; `faster-test-runs-8-narrower-targeted-tier` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_batch_test_load.md`, "How often one batch runs its
  tier" and "Runs that did not pass".
- `claude_plugins/django-stack/resources/test_tiers.md`, "When a targeted run or full run fails".
- `claude_plugins/sdd/commands/implement_plan.md`.
