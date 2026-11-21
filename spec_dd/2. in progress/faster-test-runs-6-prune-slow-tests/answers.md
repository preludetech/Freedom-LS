# Answers: faster-test-runs-6-prune-slow-tests

Asked by `/sdd:start` before the spec was written.

- Q: How is the full run's CPU-time target for pruning set? → A: Set after the ranking: the first step records the full per-test ranking, then fixes the target from it and records it in the spec (asked up front)
- Q: How is the per-test duration ranking refreshed after this spec? → A: By hand, with one documented command that runs the suite with per-test timings and rewrites a committed ranking file; CI can run it later (asked up front)
- Q: Should a per-test time limit fail a new test that is too slow? → A: No, report only; the ranking shows slow tests and nothing fails, and the existing 300s pytest-timeout stays (asked up front)
- Q: Does each test removal or merge need the owner's approval, or is naming the covering test in the spec enough? → A: Naming the covering test is enough, with the coverage threshold still holding; no separate sign-off per test (asked up front)
