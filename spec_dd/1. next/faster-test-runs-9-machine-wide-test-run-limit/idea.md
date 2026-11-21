# Test runs across worktrees share one machine-wide limit

Spec 9 of 10 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** not measured. Today a run of two changed files can sit for 39 minutes behind other runs, on a machine at four times its core count in load.

## What

Every test run on the machine counts against one shared limit, whichever worktree or session
started it. Runs beyond the limit wait their turn and say so. The machine is not asked for more
test workers than it has cores.

## Why

The test runner gives each run up to 4 workers after checking free memory. It never looks at CPU
load or at other runs. With 13 sessions open the load average sat between 40 and 77 on 16 cores,
with 21 GB in swap. Every run slows every other, and Playwright flows are the tests that fail most
often under that load. Three of six live runs had been started without the runner, so even its
memory check did not apply to them.

## What is settled

- The limit lives in the `ds` test runner and stays generic. Its numbers come from
  `[tool.test_tiers.memory]` or a sibling table in `pyproject.toml`, or from environment variables.
- It counts CPU as well as memory, across every worktree on the machine.
- A run that waits prints that it is waiting and why, and how long it waited is recorded.
- Tier runs go through the runner. Briefs and tier definitions leave an agent no reason to call
  pytest with `-n` directly.
- A run whose owner has died does not hold the limit for ever.

## Open until the spec

- One budget of workers shared between runs, or a queue of whole runs.
- Whether a single-test run (TDD red and green) counts against the limit.
- How a run is found to be dead, and who clears it.
- Whether the batch-wave capacity check in `implement_plan` reads the same limit.

## Out of scope

- Runs started by the First Class project.
- Running tests off the machine; `faster-test-runs-5-full-suite-on-github-actions` owns that.
- Which tests a run selects; `faster-test-runs-8-narrower-targeted-tier` owns that.

## Resources

- `spec_dd/1. next/faster-test-runs/research_batch_test_load.md`, "Machine state while measured"
  and "What the runner limits".
- `claude_plugins/django-stack/scripts/run_tests.py`,
  `claude_plugins/django-stack/resources/test_tiers.md`.
