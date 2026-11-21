# Test timings

Measured the way `spec_dd/1. next/faster-test-runs/research_test_timings.md` did: serial (`-n 0`),
no coverage, no random ordering, `--durations=0`, and the test-body time is the sum of the `call`
phase lines, so database setup and fixture setup and teardown are left out. The machine was the
same 16-core one with other worktrees active; the load average was about 37 throughout, so the
absolute numbers are noisy and only the comparison matters. The permission-matrix sample is the
first 20 collected cases of `test_can_matches_the_matrix`, as the research sample used 20 cases.

The before sample ran with a temporary `fast_password_hasher` that yielded the configured hashers
without entering `override_settings`, so Argon2 stayed first. The temporary edit was reverted and
never committed. The after sample is the code as committed, with MD5 first. Each sample ran three
times.

## Test-body time

| Sample | Before runs | Before median | After runs | After median | Speed-up |
|---|---|---|---|---|---|
| `freedom_ls/course_access`, 230 tests | 31.7s, 33.0s, 27.9s | 31.7s | 11.8s, 14.3s, 13.5s | 13.5s | 2.3x |
| `test_permission_matrix.py::test_can_matches_the_matrix`, 20 cases | 34.4s, 40.5s, 36.4s | 36.4s | 8.5s, 9.2s, 9.8s | 9.2s | 4.0x |

The after times are lower on both samples, and the slowest after run is faster than the fastest
before run in each. The research doc measured 62.3s and 66.8s under Argon2 at a different moment,
so the before numbers here are lower than those; the machine load differed between the two sessions.
