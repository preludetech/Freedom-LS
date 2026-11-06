# Lead monitoring API: course registrations and course interest

Spec 4 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A script holding an API key with the `registrations_and_progress` scope can read, for its own site:

- course registrations of both kinds: individual (`LearnerCourseRegistration`) and cohort
  (`CohortCourseRegistration`);
- course interest (`CourseInterest`).

Each is read only, paged, and accepts `updated_since`, following the conventions the foundation
child defines. A registration row carries the course (id and title), `is_active`, `registered_at`
and `updated_at`. An individual registration also carries `self_registered` and the learner's
identity flattened to user id, email and organisation, so a script never walks `Learner`. A cohort
registration carries the cohort in place of a learner. A course interest row carries the user (id
and email), the course and its timestamps.

This child does not cover course progress.

## Why

Lead monitoring asks who has enrolled and who has shown interest, and today no export covers
either. A registration is the point where a lead becomes a learner, and `self_registered` separates
a learner who chose the course from one staff placed in it. Course interest is an earlier signal of
the same funnel. The source idea does not name it, but a lead monitor would want it.

## What is settled

- Everything is read only, under the `registrations_and_progress` scope, one site per key.
- `LearnerCourseRegistration`, `CohortCourseRegistration` and `CourseInterest` each gain an
  `updated_at`, so that `updated_since` and cursor pagination on `(updated_at, id)` work like every
  other resource. Without it, deactivating or reactivating a registration leaves no timestamp.
- Identity is flattened: user id, user email and organisation come from `Learner`, and the learner
  is not exposed as its own nested object.
- `self_registered` and `is_active` are exposed on individual registrations, and `is_active` on
  cohort registrations.
- Course interest is part of this child even though the source idea does not name it.
- A deleted course interest (toggled off by the user) is not visible to `updated_since`. No
  deletion feed exists in this effort.
- Fields are an explicit list, snake_case, with UUIDs as strings and ISO 8601 timestamps. Only the
  fields above are exposed, and nothing from `Learner` beyond user and organisation.
- Course progress belongs to the course progress child, which also adds an `updated_at` to a
  `learner_progress` model. Whichever of the two lands second reuses the first one's flattening of
  learner to user and organisation.
- `docs/product/security-and-data-handling.md` is updated for the new endpoints, and the endpoints
  are added to the docs page and the Python example that the foundation child ships.

## Open until the spec

- Whether individual and cohort registrations share one endpoint with a `kind` field, or are two
  endpoints. Tied to this: how one cursor orders rows drawn from two tables, and what a cohort
  registration shows where an individual one shows a learner. The course progress child reads this
  answer, because each `CourseProgress` row points at exactly one of the two registration kinds.

## Out of scope

- Course progress, topic progress, form attempts and scores.
- A deletion feed for course interest or registrations, and any change to how toggling interest off
  works.
- Cohort membership, `Learner` as a resource, HR attributes and legal consent records.
- Write endpoints, any UI, and changing the admin exports.

## Resources

- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`: the models, their missing
  timestamps and the hard-delete hazard.
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`: naming and conventions.
- `freedom_ls/learner_management/models.py`: `LearnerCourseRegistration`,
  `CohortCourseRegistration`, `Learner`, `Cohort`.
- `freedom_ls/course_interest/models.py`: `CourseInterest`.
- Skills: `fls-dev:multi-tenant`, `ds:testing`, `fls-dev:testing`, `fls-dev:domain-glossary`.
