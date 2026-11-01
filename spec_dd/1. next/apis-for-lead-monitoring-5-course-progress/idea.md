# Lead monitoring API: course progress

Spec 5 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A script author with a key holding the `registrations_and_progress` scope can read, at
`/api/v1/course-progress/`, how far each learner has got in each course they are registered on. One
row per learner per course registration (a `CourseProgress` row). Each row carries:

- the progress percentage, started time, completed time and last accessed time;
- the course, as id and title;
- the registration it hangs off: its id, and whether it is an individual or a cohort registration;
- the learner's identity, flattened: user id, email, first and last name, and the organisation (id
  and name).

The list is read-only, paged and filtered by `updated_since` like every other resource in the API.
Pulling it on a schedule tells a lead monitor which registered learners have started, how far they
are and who finished.

To make `updated_since` honest, `CourseProgress` gains an `updated_at` that moves whenever the row
changes. That includes a change to `progress_percentage` made by background recalculation, which
touches no other timestamp today.

## Why

Registrations say who was enrolled. Progress says whether the enrolment is turning into activity
and completion, which is the second half of lead monitoring: a lead who registered and never
started is a different lead from one who finished. No admin export covers course progress today,
so scripts have no way to get it.

`CourseProgress` has no changed-since signal. `last_accessed_time` is written by the player and is
deliberately not `auto_now`, and `progress_percentage` can change without any timestamp moving. An
incremental pull keyed on the existing timestamps would silently miss those changes.

## What is settled

- The endpoint is `/api/v1/course-progress/`. List and detail, GET, HEAD and OPTIONS only. It sits
  under the `registrations_and_progress` scope, the same scope as registrations and course
  interest. A key without the scope gets a permission error.
- Course level only. No topic progress, no form attempts, no scores, no `last_accessed_item`.
  This was the owner's decision.
- One row per `CourseProgress`. Its identity in the API is the row's UUID. Exactly one of the
  individual or cohort registration is set on each row; the row exposes that registration's id and
  its kind.
- Fields are an explicit list, snake_case, ISO 8601 timestamps, UUIDs as strings. `progress_percentage`
  is an integer.
- `CourseProgress` gains `updated_at`, set automatically on every save. The progress
  recalculation that updates the percentage in the background must go through a path that moves
  `updated_at`, so a bulk update that bypasses it is not allowed to leave the field stale. Existing
  rows are backfilled so that `updated_since` ignores nothing: the migration sets `updated_at` to
  the latest of the row's existing timestamps.
- The learner is flattened to the user (id, email, first and last name) and to the organisation (id
  and name) so a script never joins. This reuses the learner identity flattening that the
  registrations resource (child 4) settles; this resource does not define a second shape. The
  names of these fields match what child 4 uses.
- Cursor pagination ordered on `(updated_at, id)`, capped page size, `updated_since` inclusive,
  throttled per key, all as the foundation (child 1) defines them.
- Site isolation as the foundation defines it: a key reads only its own site's rows, and the
  queryset is filtered explicitly by that site.
- Query shape: the queryset selects the learner, user, organisation, course and both registration
  relations up front; a test pins the query count.
- Deletions are not visible to `updated_since`. `CourseProgress` rows are not soft-deleted.
- The endpoint is added to the API docs page the foundation ships, and to
  `docs/product/security-and-data-handling.md`, which notes that email and name are exposed under
  this scope.

## Open until the spec

- Whether `updated_at` comes from the shared `TimestampedModel` mixin (which would also add
  `created_at` twice over) or is a single added field. The spec decides, given that `created_at`
  already means the registration date on this model.
- How the recalculation path is made to move `updated_at`, and whether any other writer of
  `CourseProgress` currently bypasses `save()`.
- Whether a filter by course id or registration kind is offered beyond `updated_since`. The spec
  adds one only if the filters child 4 offers make it free to match.
- Whether the registration kind field is shared with, and named as, the `kind` field child 4 may
  introduce on its registrations list.

## Out of scope

- Topic progress, form attempts, quiz scores and `last_accessed_item`.
- Write endpoints, webhooks and push.
- Any deletion feed.
- HR attributes and legal consent records.
- Changes to the player's own handling of `last_accessed_time`.
- Admin exports for course progress.

## Resources

- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`: `CourseProgress`, its
  timestamps and why `progress_percentage` can change without one moving (sections 1 and 4), and the
  learner to user flattening.
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`: resource and field
  naming.
- `freedom_ls/learner_progress/models.py`: `CourseProgress`.
- Skills: `fls-dev:multi-tenant`, `ds:testing`, `fls-dev:testing`, `domain-glossary`.
