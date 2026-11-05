# Lead monitoring API: course applications

Spec 2 of 6 in the Lead monitoring API effort. Read the "Lead monitoring API" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A script holding an API key with the `course_applications` scope reads every `CourseApplication` on its site from `GET /api/v1/course-applications/`, with each application's answers nested inside it. Applications held by signed-in users and applications from anonymous applicants (`AnonymousApplicant`) come back in one list. Drafts are in the list alongside submitted applications, as they are in the course applications admin export.

Each application carries what the admin export carries: `id`, `applicant_email`, `applicant_name`, `is_email_verified`, `is_submitted`, `submitted_time`, `created_at`. The export's course title column becomes two fields, the course id and the course title. `updated_at` is added. A single application is also readable at its detail URL.

Answers are an array on each application. Each entry gives the question id, the question text, the question type and the value. A file upload answer gives the filename only, never the file or a link to it.

## Why

Application data is what lead monitoring reads most. Today it reaches scripts only as a spreadsheet download from the admin, whose answer columns are named after question text and shift as forms change. A nested answers array keyed by question id gives scripts a stable shape, and `updated_since` lets them pull only what changed instead of re-downloading everything.

## What is settled

- The endpoint is read only: GET, HEAD and OPTIONS. It sits under `/api/v1/` as `/api/v1/course-applications/` and requires the `course_applications` scope on the key.
- The conventions are the ones child 1 sets for every resource: `Authorization: Bearer <key>`, a key bound to one site that reads only that site's rows, cursor pagination ordered on `(updated_at, id)` with a capped page size, `updated_since` (inclusive), per-key throttling, snake_case fields from an explicit list, ISO 8601 timestamps, UUIDs as strings.
- One list covers both kinds of applicant. Whether an application belongs to a signed-in user or to an anonymous applicant is shown by data the response already carries (`applicant_email`, `applicant_name`, `is_email_verified`), not by a separate endpoint.
- Drafts are included, matching the admin export. `is_submitted` and `submitted_time` tell them apart, and both come from the one property on `CourseApplication`, so they follow when the application review spec adds a `state`.
- The fields are the admin export's columns plus course id, course title and `updated_at`. The CSV concerns of the export (formula escaping, BOM, `TRUE`/`FALSE`) are not carried into JSON.
- Answers are nested under each application, not flattened into columns. Each has the question id, question text, question type and value. Option answers give the option text; date and time answers are ISO text; an unanswered question has no entry or a null value (the spec picks one and states it). File uploads give the filename only.
- Query cost is bounded: the viewset selects the related user, anonymous applicant, course and form progress and prefetches the answers, and a test pins the query count.
- Deleted applications do not appear in `updated_since` results. There is no deletion feed.
- The consent evidence on `AnonymousApplicant` (`consent_ip_address`, `terms_version`, `consented_at`) and its claim state are not in this endpoint's fields.
- `docs/product/security-and-data-handling.md` is updated to say that application answers and applicant contact details are readable through the API by a key with this scope, and that file uploads are exposed as filenames only. The child 1 docs page gains this endpoint and a Python example of reading it.

## Open until the spec

- The changed-since rule for applications. Submitting a sitting moves `FormProgress.last_updated_time` but not `CourseApplication.updated_at`, and edits to answers move the answers' own `updated_at`. The spec decides what the API's `updated_at` reports and what `updated_since` and the cursor order on, for example the greatest of the application's, its `AnonymousApplicant`'s and its `FormProgress`'s timestamps, and how that is made efficient enough to filter and page on. The rule has to guarantee that a script polling with `updated_since` sees every submission and every answer change.
- Where the serializer and viewset live, following whatever child 1 decides for resource code.

## Out of scope

- Write endpoints, a UI, a browsable API, and webhooks.
- Downloading uploaded files, or links to them.
- `AnonymousApplicant` consent evidence and claim state.
- Linking an anonymous application to signup attribution.
- Application review state, decisions and the `view_application` permission, which belong to the application review work.
- Changing the course applications admin export.
- The API framework, keys, scopes, pagination and `updated_since` themselves, which child 1 provides.

## Resources

- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md`: `CourseApplication`, `AnonymousApplicant`, the application answers models, the course applications admin export, and the hazards on changed-since and PII.
- `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md`: naming and conventions.
- Done specs: `more_lead_admin_exports`, `ananomous-course-applications`, `anon-application-improvements`.
- Code to read: `freedom_ls/course_applications/resources.py` (export and its prefetches), `freedom_ls/form_engine/exports.py` (answer values).
- Skills: `fls-dev:multi-tenant`, `ds:testing`, `fls-dev:testing`, `fls-dev:domain-glossary`.
