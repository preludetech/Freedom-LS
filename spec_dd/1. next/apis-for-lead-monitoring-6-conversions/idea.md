# Lead monitoring API: attribution touches and conversions

Spec 6 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A script holding an API key with the `referral_data` scope can read two more lists under `/api/v1/`: the attribution touches recorded for the site's accounts, and the conversions recorded against them. Both come from `referral-attribution-over-time`, which adds the `AttributionTouch` and `Conversion` models.

An attribution touch is one tracked landing, kept per person and in order. A conversion is one moment worth attributing (an account signup, a course application, an expression of interest or a self-registration), carrying the first and last referral code that were in play when it happened. Together they let a lead-monitoring script work out which referral link brought which person, and which of their actions to credit, without the admin CSV export.

## Why

Child 3 gives a script the referral links, the hits and the signup attributions. That answers "who arrived through which link". It does not answer "which of their later actions came from it", which is what `referral-attribution-over-time` records and what a payout or a lead report actually needs. Without this child, that data is only reachable through the admin export, which the effort exists to move scripts away from.

## What is settled

- Two read-only resources, attribution touches and conversions, under the `referral_data` scope that child 3 uses. GET, HEAD and OPTIONS only. A key without the scope gets a refusal, as on every other resource.
- Rows are limited to the key's site, as everywhere else in the effort.
- Both models are append-only: rows are written once and never changed. The API does not rely on a modification time.
- The effort's `updated_since` convention maps onto `recorded_at`, the time the row was written. Cursor pagination orders on `(recorded_at, id)` and `updated_since` is inclusive on `recorded_at`. Because rows never change, "written since" is the same as "new or changed since", so a script that follows pages and remembers its last `recorded_at` misses nothing.
- Neither resource filters or orders on `occurred_at`. A touch carried in the browser cookie is written when the visitor signs up or logs in, so it is recorded after it happened, and a row can arrive with an `occurred_at` older than rows the script has already read. `occurred_at` is returned in every row so a script can order the timeline itself, but it is not the paging key.
- Attribution touches return the fields the spec names: the account (as the user's id), `advert_code`, `referral_code`, the five UTM fields (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`), `landing_path`, `occurred_at`, `recorded_at` and `recorded_via` (`live`, `signup_flush` or `login_flush`, which tells a reader how far to trust the ordering). The row's own id is included.
- Conversions return the fields the spec names: the row's id, the account (user id), `kind` (`account_signup`, `course_application`, `course_interest`, `course_registration`), `target_label`, `occurred_at`, `recorded_at`, `window_days` (the attribution window in days that applied when the conversion was resolved), the ids of `first_touch` and `last_touch`, and `first_referral_code` and `last_referral_code`. Both codes blank means nothing was in play, which is a recorded answer and is returned as it is.
- Conversions carry `target_label`, the frozen course title or account email, and nothing else about the target. The API does not resolve the generic target, and does not return `content_type` or `object_id`. This keeps the list free of per-row lookups and keeps it readable after the target is deleted.
- Fields that identify a device or browser stay out, matching child 3: no IP address, user agent or cookie identifiers. The touch model holds none of these today, and the API's explicit field list keeps it that way if that changes. `key_hash` is an internal idempotency detail and is not returned.
- Filters: both resources filter by the user and by `referral_code`; conversions also filter by `kind`. A filter on the first or last code of a conversion is available, since that is the payout query.
- Conventions from child 1 apply unchanged: explicit field lists, snake_case, ISO 8601 timestamps, UUIDs as strings, capped page size, per-key throttling, and the OpenAPI schema entry.
- The field lists follow whatever `referral-attribution-over-time` ships. If its model shape changes before it does, this child exposes the shipped fields under the same rules above (explicit list, no device or browser identifiers, no generic target resolution).
- `docs/product/security-and-data-handling.md` is updated, as in every child, and the docs page with the Python example gains these two endpoints.

## Open until the spec

- Whether a script reads touches and conversions as two flat lists joined by id, or whether a conversion also embeds its first and last touch. The default is flat lists with ids, matching the rest of the effort.
- Whether the user is returned as the id only or with the email beside it, following whatever child 3 does for signup attributions.
- The exact filter names and whether date-range filters beyond `updated_since` are offered.
- How the endpoints behave on a project where `referral-attribution-over-time` is not installed or has no rows: an empty list is the expected answer, to be confirmed.

## Out of scope

- Any write endpoint, and any change to how touches or conversions are recorded.
- Resolving the conversion's target into a course, application or registration record. A script that needs it uses the other resources.
- Credit rules, payout calculation or summaries. The API returns rows; it does not decide who gets credit.
- The prune command for old touches, and any deletion feed.
- Device and browser identifiers, and personal data beyond what child 3 returns.
- Changing the admin exports.

## Resources

- The referral-attribution-over-time spec (`spec_dd/*/referral-attribution-over-time/1. spec.md`, under `2. in progress` or `3. done`): the `AttributionTouch` and `Conversion` model sections and the export section.
- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`, section 5 on `referral-attribution-over-time`.
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`, for naming.
- `spec_dd/1. next/apis-for-lead-monitoring/idea.md`, the parent brief.
