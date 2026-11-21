# The permission matrix test builds its world once

Spec 3 of 13 in the Faster test runs effort. Read the "Faster test runs" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

**Estimated time saving:** about 11 minutes off a full run if done on its own. About 2 minutes if `faster-test-runs-1-fast-password-hasher` lands first, because that spec takes most of the saving.

## What

The educator-interface permission matrix test checks the same matrix as today in a small fraction
of the time. Every cell it checks now is still checked, and a failure still names the permission,
role, object and relation that disagreed.

## Why

`test_permission_matrix.py` holds 763 parametrized cases, and each builds its own users, cohorts
and roles. At about 3.5s a case that is roughly 45 minutes of CPU, the largest single cost found in
the suite. A fast password hasher brings a case to about 0.67s, which still leaves several minutes
spent rebuilding identical data.

## What is settled

- Coverage does not shrink: the set of cells checked after the change equals the set checked before.
- A failing cell is identified in the test output as precisely as it is now.
- The spec measures the file before and after.

## Open until the spec

- Whether any case changes the data another case reads, which decides how much can be shared.
- Whether the cases stay as separate tests over shared data or become a few tests that walk the
  matrix.

## Out of scope

- Changing the permission matrix or any permission rule.
- Other slow tests; `faster-test-runs-6-prune-slow-tests` finds those.

## Resources

- `spec_dd/1. next/faster-test-runs/research_test_timings.md`, "Largest parametrized tests".
- `freedom_ls/educator_interface/tests/invariants/test_permission_matrix.py`.
