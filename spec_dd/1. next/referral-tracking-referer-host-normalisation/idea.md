# Idea: referer host normalisation for referral tracking

## What

Two small helpers that turn a stored Referer into a host that can be compared: strip the port, a
leading `www.` and a trailing dot, and read the package name out of an `android-app://` referer.

## Why

`SignupAttribution` stores the raw referer. Anything that asks "which site sent this visitor" has to
normalise it first, and getting it slightly wrong splits one source into several (`www.google.com`,
`google.com.`, `google.com:443`). The marketing channel classifier
(`referral-tracking-marketing-channels`) and external-referer capture
(`referral-tracking-external-referer-first-touch`) both need it.

## Reference implementation

First-Class-LMS, `apps/lead_forms/referers.py` (`normalised_host`, `referer_host`). Pure functions
with no project data; the project would delete its copy.

## Settled

- It lives in `referral_tracking`.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-10-30).
