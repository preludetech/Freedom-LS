# Idea: marketing channels for referral tracking

## What

Classify a first touch into a marketing channel: direct, organic search, paid search, organic social,
paid social, email or referral, with the platform (Google, Facebook, LinkedIn, ...) and the basis the
call rests on (a UTM medium, a click identifier, or the referring host).

`referral_tracking` already records what a visitor arrived with on `SignupAttribution` (UTM fields,
advert and referral codes, the referer). It never says what kind of traffic that was, so every project
that reports on signups re-derives the same answer from the same fields.

## Why

First-Class-LMS needed this for its admin lead reports and wrote a pure classifier for it. Any project
using `referral_tracking` asks the same question ("where are our signups coming from?") of the same
data, and the answer does not depend on the project.

## Reference implementation

First-Class-LMS, `apps/admin_dashboard/channels.py`. It is pure: no request, no database. It takes a
first-touch record, and its one project tie is a `from_record` helper that reads the project's own
`LeadSubmission`; in FLS the input would be shaped like `SignupAttribution`. Its host tables (search
engines, social sites, mail providers) are plain constants. It depends on the referer host helpers in
`referral-tracking-referer-host-normalisation`.

The project would delete its copy and keep only a thin adapter for its lead records.

## Settled

- It lives in `referral_tracking`, beside `SignupAttribution`.
- It is a classifier over data FLS already stores. It adds no new capture.

Found during `/fls-dev:update_concrete_projects` (pull-in from First-Class-LMS, 2026-10-30).
