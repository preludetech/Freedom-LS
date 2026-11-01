# Lead monitoring API: referral data

Spec 3 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A script holding an API key with the `referral_data` scope can read a site's referral tracking data over the read-only API, as JSON, from Python. Four resources, one per model the admin already exports:

| Resource | Model | Rows |
| --- | --- | --- |
| Referral codes | `ReferralCode` | One per code: what the operator handed out (the idea calls these referral links). |
| Referral code hits | `ReferralCodeHit` | One per logged visit to a code. |
| Signup attributions | `SignupAttribution` | One per user: the first touch recorded at signup. |
| First-touch counts | `FirstTouchCount` | One per day and first-touch key: the daily denominator for conversion rates. |

Each resource returns the fields of its admin export, in the same names, with the changes below. Foreign keys that the export renders as text are returned as ids with the readable value beside them where a script needs it (a hit carries the referral code's id and its code text; a signup attribution carries the user's id and email).

Signup attributions leave out `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie` and `fbc_cookie`. The admin export still carries them.

The scripts get the funnel's top: how many visits each code drew, which first touches users arrived on, and how many first touches there were each day for a given campaign key.

## Why

Lead monitoring needs to know where leads came from and how many came from each source. Today that means downloading four separate CSV exports from the admin and joining them by hand. The scripts that watch leads need the same data on a schedule, without a person logging in. Referral data is also what payouts and campaign reporting are computed from, so the numbers have to be pullable incrementally and reliably.

The personal and device identifiers on a signup attribution (IP address, user agent, the Google and Meta cookie ids) are not needed to attribute a lead to a source. Leaving them out of the API keeps them behind the admin's `view_` permission instead of handing them to every key with the scope.

## What is settled

- The four resources sit under `/api/v1/` as plural kebab-case paths: `referral-codes`, `referral-code-hits`, `signup-attributions`, `first-touch-counts`. Fields are snake_case, explicit lists (never `__all__`), timestamps ISO 8601, UUIDs as strings.
- All four are read only (GET, HEAD, OPTIONS) and require the `referral_data` scope. A key without that scope gets a refusal on all four. Each returns only the key's own site's rows.
- Fields come from the admin export columns, minus `site`:
  - Referral codes: `id`, `code`, `label`, `notes`, `destination`, `inactive_destination`, `is_active`, `hit_count`, `last_hit_at`, `created_at`.
  - Referral code hits: `id`, `referral_code` (the code's id), the code text, `door`, `is_machine_fetch`, `hit_at`.
  - Signup attributions: `id`, the user (id and email), `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `landing_path`, `referer`, `raw_query`, `first_seen`, `signed_up_at`.
  - First-touch counts: `id`, `day`, `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `is_overflow`, `key_hash`, `count`.
- `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie` and `fbc_cookie` are not on the signup attribution resource. This is the owner's decision. The admin export is unchanged.
- Referral codes are a full pull. `ReferralCode` has no `updated_at` and `referral_tracking` stays outside the timestamped mixin, so no `updated_at` is added. Referral codes are ordered by `created_at` (with `id` as the tie-break) and have no `updated_since` filter. Because the table is small, a script pulls every page each time. `hit_count`, `label` and `is_active` can change on an existing row, so a script that wants current values re-reads the whole list.
- The other three page on the timestamp they have, ordered by that timestamp then `id`, with the effort's cursor pagination and capped page size:
  - Referral code hits on `hit_at`.
  - Signup attributions on `signed_up_at`.
  - First-touch counts on `day`.
- The effort's inclusive changed-since filter works on those three resources against the same field they are ordered on. A script that checkpoints on the last value it saw and asks again from that value gets every later row.
- First-touch counts are mutated in place (`count` rises through the day and no `updated_at` records it), so the API does not claim a changed-since signal that does not exist. The documented rule is that a script re-pulls the most recent days to pick up late increments.
- Hits and signup attributions are append-only, so ordering on their timestamp is a reliable checkpoint. Pruned hits (the `prune_referral_code_hits` command) and a `hit_count` that does not reconcile with the hit log are existing behaviour and are documented, not corrected.
- Throttling, authentication, site binding, scopes, the key model, the schema and the Python example follow child 1 unchanged. Nothing in this child redefines them.
- Deletions are not visible to the changed-since filter (inherited from the effort). Referral codes are never deleted; hits can be pruned.
- Attribution touches and conversions are not in this child. They belong to child 6, once `referral-attribution-over-time` has added them, and they will sit under the same `referral_data` scope.
- `docs/product/security-and-data-handling.md` is updated to say which referral fields the API returns and that the IP, user agent and cookie ids are withheld. The shared docs page gains these four endpoints.

## Open until the spec

- Where the four serializers and viewsets live and how they register with the API router. Child 1 decides the pattern; this spec follows it.
- The exact query-string spelling of the changed-since filter on `first-touch-counts`, whose timestamp is a date rather than a datetime, and whether the same name is used on all three resources.
- Whether the user on a signup attribution is returned as an id plus email only, or with name as well. The export carries the email only.
- Whether referral codes accept a simple filter such as `is_active`, or none at all given the full pull.

## Out of scope

- Attribution touches and conversions (child 6).
- `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie` in the API under any permission.
- Adding `updated_at` to `ReferralCode`, `FirstTouchCount` or any other `referral_tracking` model, or moving the app into the timestamped mixin.
- A deletion feed, and any correction of the `hit_count` reconciliation gap or hit pruning.
- Write endpoints, a UI, webhooks, and any change to the admin exports.
- Derived fields such as marketing channel or normalised referer host.

## Resources

- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`: models, admin export columns and timestamps for the four resources (sections 1 to 3).
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`: naming, pagination and incremental-sync conventions.
- `docs/product/referral-codes.md` and `docs/product/security-and-data-handling.md`.
- `freedom_ls/referral_tracking/` (models, `resources.py` for the export columns, `admin.py`).
- Done specs: `referral-links`, `more_lead_admin_exports`.
- Skills: `fls-dev:multi-tenant`, `ds:testing`, `fls-dev:testing`, `fls-dev:domain-glossary`.
