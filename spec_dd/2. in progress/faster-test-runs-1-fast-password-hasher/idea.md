# Tests hash passwords with a fast hasher

Spec 1 of 7 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** about half of the test time of a full run, a guess from two samples that ran 3x and 5x faster; the whole suite has not been measured. It also removes most of the memory and thread load that stops worktrees running side by side.

## What

Under pytest, FLS hashes passwords with a fast hasher instead of Argon2. Production and the dev
server keep Argon2. A concrete project that runs FLS's tests gets the same behaviour without
configuring anything.

## Why

`UserFactory` sets a password on every user it builds, and most database tests build at least one
user. Argon2 is deliberately expensive in time, memory and threads, so the suite pays that cost
thousands of times and competes with every other worktree for the machine. On the two samples
measured, a fast hasher cut test-body time to between a fifth and a third, with every test passing.

## What is settled

- The fast hasher applies to test runs only. Nothing a deployed site or the dev server uses changes.
- It applies to every test by default. A test that is about the production hasher opts back in.
- The spec re-measures the two samples in `research_test_timings.md` and reports before and after.

## Open until the spec

- Whether any existing test asserts the Argon2 hasher or a hash's format.
- Where the switch lives so that concrete projects, which star-import `freedom_ls/conftest.py` and
  run under their own settings, inherit it.

## Out of scope

- Changing the production hasher list.
- Any other test speed-up; the siblings own those.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Password hashing".
- `config/settings_base.py` (`PASSWORD_HASHERS`), `freedom_ls/accounts/factories.py` (`UserFactory`).
