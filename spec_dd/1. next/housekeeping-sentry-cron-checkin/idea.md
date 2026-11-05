# Idea: Sentry Crons check-ins for the housekeeping sweep

## What

Have `fls_run_housekeeping` check in with Sentry Crons when a monitor slug is configured: an
in-progress check-in when it starts, then OK or ERROR when it ends. A run that completes its sweeps but
reports findings elsewhere (for example a stalled worker) still checks in OK, because housekeeping
itself did its job; a sweep failure checks in ERROR. With no slug set, or no Sentry DSN, nothing is
sent.

## Why

Housekeeping runs on a schedule outside the web process, so the only way to notice it stopped
running is a monitor that expects a check-in. FLS already initialises Sentry (`init_sentry`) and
already reports sweep exceptions to it, but never says "the sweep ran". Every deployed project needs
that, and First-Class-LMS wrote a wrapper command to get it.

## Reference implementation

First-Class-LMS, `apps/project_setup/management/commands/run_housekeeping.py`. It wraps
`call_command("fls_run_housekeeping")` in `capture_checkin` calls and tells findings from sweep
failures by the `"Findings:"` prefix of the `CommandError` message, which is fragile; FLS can read the
distinction from `HousekeepingOutcome` directly. The project's slug and monitor schedule become
settings. The project would delete its wrapper.

## Settled

- It lives in `freedom_ls.deployment`, beside `fls_run_housekeeping` and `HousekeepingOutcome`.
- It is off unless a monitor slug is configured.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-11-04).
