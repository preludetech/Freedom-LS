# The full test suite runs on GitHub Actions on demand

Spec 5 of 7 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** the full run uses none of the local machine, where today it uses 4 workers for about 25 minutes. The wait for the result is 5 to 8 minutes, a guess.

## What

The full test suite can run on GitHub Actions instead of the developer's machine. The FLS tests
workflow passes again, finishes in a few minutes by splitting the suite across parallel jobs, and
can be started by hand for any branch. An SDD run that needs the full tier can start that run, wait
for it and read its result in place of a local run.

## Why

A local full run takes more than ten minutes and most of the machine, so only one worktree can be
verified at a time. The repository is public, so standard GitHub-hosted runners cost nothing. The
workflow has been red since October: the unit job is cancelled at its 15-minute cap less than half
way through, and the Playwright job cannot install its browser on the current runner image.

## What is settled

- Standard free runners only. No paid larger runners and no third-party runner service.
- The suite is split across parallel jobs, as the First Class concrete project's workflow already
  does. Every test runs in exactly one job.
- The workflow can be started manually for a branch as well as on pull requests and pushes to main.
- Where the full tier runs is a per-project choice. The generic `sdd` and `ds` plugins learn that a
  full tier may run remotely; the command that does it comes from per-project configuration. No
  FLS name, path or value goes into a generic plugin.
- A remote pass counts as a full run for the full-run record, for the commit the run tested.
- A local full run stays available.

## Open until the spec

- How the split is defined so that a new app cannot be left out of every job.
- How a remote failure comes back to the agent that has to fix it: which failing tests, and their
  output.
- Whether coverage and its threshold are still enforced once the unit tests run in several jobs.
- What an SDD run does when GitHub is unreachable or the queue is slow.

## Out of scope

- Running targeted tiers or single tests remotely.
- Changing the First Class workflow.
- Claude Code cloud sessions; `faster-test-runs-7-claude-cloud-test-runs` owns those.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "GitHub Actions on this repository".
- `.github/workflows/tests.yml`, `claude_plugins/sdd/commands/protected/run_test_tier.md`,
  `claude_plugins/django-stack/resources/test_tiers.md`.
- <https://github.com/posthog/pytest-split>
