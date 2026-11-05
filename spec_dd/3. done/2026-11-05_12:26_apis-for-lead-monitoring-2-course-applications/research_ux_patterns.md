# Research: UX patterns (developer experience of a read-only course applications API)

The "user" is a developer writing a polling script. There is no UI. Sources: the existing
`docs/api.md` (child 1, read in full) and general knowledge of comparable APIs. The web links
below were NOT fetched in this run; they are pointers from background knowledge, so treat them as
unverified. Child 1's `research_comparable_apis.md` is the better source for naming.

## 1. Established docs style (docs/api.md)

The page is one file with: "Before you start", "API keys", "Making requests" (with Errors, Rate
limit, Schema), "Syncing data" (Pages, `updated_since`, Deletions, a full httpx Example),
"Versioning", then one section per resource. The Users section is the template to copy:

- A two-column key/value table: API scope, List URL, Detail URL, Filters.
- `### Fields` table with columns `Field | Type | Notes`. Types are written as `integer`,
  `string`, `boolean`, `string (ISO 8601)`, `string (ISO 8601) or null`. Nullability is stated in
  the Type column, and the Notes column says when (`null if the user has never signed in`).
- "May be empty" is used for blank strings; `null` is used for absent timestamps.
- A closing sentence listing what is never returned (passwords etc.).
- A `### What moves updated_at` subsection that explains the changed-since rule, including what
  does NOT move it and why.
- The intro of the page says "Today there is one: users", and the scope table says "Only `users`
  has an API endpoint so far". Both sentences go stale when this spec lands and must be edited.
- Errors are `{"detail", "code"}`; 403 says "The detail names the API scope"; docs say "Branch on
  the status and code, not on detail text".
- Domain words: "API endpoint", "API scope", "row". Keep them.

## 2. Response shape: nested answers vs flat

Recommendation (consistent with the idea): nested `answers` array on each application.

- Flat columns named after question text (the admin export) break scripts when form wording
  changes. Keyed by question id is stable.
- An array of entries rather than an object keyed by question id: it can carry self-describing
  metadata per entry, preserves form order, and avoids JSON keys that are UUID/integer strings.
  Scripts that want a map do `{a["question_id"]: a for a in app["answers"]}`.
- Self-describing entry (question id + text + type + value) means a developer can read a raw
  response and understand it without a second call to a forms endpoint. Costs a little payload
  size; acceptable under the 500 page cap.
- Suggested entry: `{"question_id": 12, "question_text": "Why do you want to join?",
  "question_type": "multiple_choice", "value": "Career change"}`. Name it `question_id`, not `id`,
  so it is not mistaken for an answer row id. Match the field names to the project's existing
  question-type vocabulary (check the form_engine question type values and use them verbatim).
- Keep `answers` at the same level as the scalar fields, and keep scalars flat: `course_id`,
  `course_title` (two flat fields, not a nested `course` object, to mirror the export and child
  1's flat style). A nested `course` object would be friendlier but breaks "flat scalars" unless
  child 1 already uses nested objects. Flag for the spec to pick one; flat is the recommendation.
- Value typing: one `value` field whose JSON type varies by question type is the hard part. Options:
  (a) always a string, so every script handles one type; (b) native JSON types per question type
  (number for numeric, array for multi-select). The idea fixes "option text; date/time as ISO
  text", which points to string-like values. Multi-select needs a decision: array of strings is the
  natural reading. Whatever is chosen, the docs need a table of `question_type -> value shape`.

## 3. Unanswered questions: absent entry vs null value

The idea leaves this to the spec. DX analysis:

- **Entry present with `value: null` (recommended)**: the script sees every question the form
  asks, including text and type, and can tell "asked, unanswered" from "form did not have this
  question when the application was made". Stable shape; no key-existence checks. Downside: for
  a draft the list is long and mostly null.
- **No entry**: smaller payload, but a script cannot distinguish unanswered from unknown, and has
  to join against the form definition (which this API does not expose) to find gaps.
- Either way, document the choice in one sentence in the Fields notes and say that an empty answer
  and an unanswered question are (or are not) the same. Decide whether a blank string answer is
  `""` or `null`, and state it. Prefer one rule: unanswered is `null`, never `""`.
- Absent vs null generally: always return every documented field (never omit keys), use `null` for
  "no value", and say so once in the page's Fields conventions. This matches child 1's
  `last_login: null`.

## 4. Drafts vs submitted made obvious

- `is_submitted` (boolean) plus `submitted_time` (ISO 8601 or `null`). `submitted_time` is `null`
  exactly when `is_submitted` is false. Say so in the Notes column.
- Put the two fields next to each other in the table and in the example response.
- Docs should open the endpoint section with a one-line warning: "The list includes drafts. Filter
  on `is_submitted` in your script if you only want submitted applications." Since no server-side
  `is_submitted` filter is in the idea (and "Don't build what's not requested"), call this out
  as a client-side filter. Candidate for the spec to consider: an `is_submitted` query filter,
  but it is NOT requested, so leave out unless the spec decides.
- State that a draft's answers can still change, and that a later submit moves `updated_at`
  (ties into the changed-since rule), so re-upsert by `id`.
- The idea notes both come from one property so a future `state` field follows; docs should say
  "A `state` field may be added; ignore fields you do not know" by pointing at the existing
  Versioning section rather than promising it.

## 5. Signed-in vs anonymous applicants

There is no discriminator field in the idea. DX risk: a script cannot easily tell whom an
application belongs to. The docs must explain how to read it: `applicant_email`/`applicant_name`
come from the user when signed in, from the anonymous applicant otherwise, and
`is_email_verified` says whether the address is verified. Document: an anonymous applicant's
email may be unverified; the same person can appear as two different applications over time; do not
key people on email alone. Recommend a short "Who applied" subsection in the docs rather than a new
field.

## 6. How the docs should present the resource

Follow the Users template exactly, then add:

1. Endpoint table: API scope `course_applications`; List `GET /api/v1/course-applications/`;
   Detail `GET /api/v1/course-applications/<id>/`; Filters `updated_since`, `cursor`, `page_size`.
2. `### Fields` table for the application (id, applicant_email, applicant_name, is_email_verified,
   is_submitted, submitted_time, course_id, course_title, created_at, updated_at, answers).
3. `### Answers` table for the answer entry fields, plus a `question_type -> value` table (how each
   type renders: text, option text, ISO date/time, filename for file upload, `null`).
4. `### Example response`: one realistic object: a submitted application with 3-4 answers of mixed
   type (one option, one date, one file upload showing the filename only, one null), because
   examples teach shape faster than tables. Optionally a second tiny draft example showing
   `is_submitted: false`, `submitted_time: null`.
5. `### What moves updated_at` (mirror the Users section): state the spec's changed-since rule,
   explicitly that submitting a sitting and editing an answer both move it, and what does not.
   This is the most important doc paragraph because the open question is a correctness
   guarantee for pollers.
6. `### Files`: "A file upload answer gives the filename only. FreedomLS does not return the
   file or a link to it."
7. `### Example` Python: reuse the page's existing `get_page` and checkpoint logic rather than
   repeating the whole script. Show a short `sync_course_applications(updated_since)` that reuses
   `get_page`, upserts by `id`, branches on `is_submitted`, and walks `answers` into a dict keyed
   by `question_id`. Keep the same helpers, env vars (`FLS_BASE_URL`, `FLS_API_KEY`,
   `FLS_CHECKPOINT`) and the "checkpoint = largest updated_at minus 5 minutes, only after a full
   run" pattern. Better still: refactor the existing example to be endpoint-generic
   (`sync(path, upsert)`) so one loop is shown once; if that is too invasive, add the new snippet
   as a minimal delta and link back to the Example. The spec should choose, avoiding two diverging
   copies of the loop (repo rule: avoid repeating code applies to docs too).
8. Edit the stale sentences: "Today there is one", "Only `users` has an API endpoint so far", and
   the scope table's reserved note.
9. A note in `security-and-data-handling.md` (required by the idea): PII (email, name, free-text
   answers) readable via this scope; file uploads as filenames only. Use "API scope" wording.

## 7. Error responses for a missing scope

Child 1 already defines: 403 with `{"detail": "...", "code": "permission_denied"}` where the
detail names the API scope. Recommendation for this spec: do not invent anything; add one
example in the docs, e.g.
`{"detail": "This API key does not have the 'course_applications' API scope.", "code": "permission_denied"}`
(verify the real text and code from child 1's implementation before copying; do not guess in the
docs). Test it: key without the scope -> 403 on list and on detail; key with it -> 200; wrong
site's id -> 404 (not 403, so existence is not leaked). Document the three-way distinction in the
endpoint section: 401 bad key, 403 wrong scope, 404 not on your site.

## 8. Other DX details worth specifying

- Field order in JSON: put `id` first, scalars next, timestamps, then `answers` last so a human
  scanning the response sees the application summary before the long array.
- IDs: application `id` format (UUID vs integer) is whatever the model uses; the Fields table must
  state the type (idea says UUIDs as strings for child 1's convention). Same for `question_id`.
- Detail URL returns the same object as a list entry (no different shape), say so.
- `course_id` + `course_title` are denormalised; note that title can change and `course_id` is
  the key to rely on.
- `OPTIONS` and the OpenAPI schema at `/api/v1/schema/` should describe `answers` entries;
  the serializer should use a typed nested serializer (not a free `dict`) so the schema is
  useful. Worth a schema test.
- Large payload per page: with 500 rows x many answers the response can be big; mention that
  `page_size` can be lowered, and that the default 100 is the recommended start.
- Query-count test is a DX guard: a slow endpoint makes pollers hit the 600/min rate limit.
- Keep CSV concerns out: no formula escaping, no `TRUE`/`FALSE`; real JSON booleans.
- Timestamps: ISO 8601 with offset, same as Users.

## 9. Open items for the spec writer (UX-related)

1. Unanswered: null-valued entry (recommended) vs no entry.
2. Multi-select value shape (array of strings vs joined string) and the full type -> value table.
3. Flat `course_id`/`course_title` (recommended) vs nested `course`.
4. Whether to refactor the docs example into a generic loop.
5. Whether an `is_submitted` filter is wanted (not requested; leave out by default).
6. Exact `question_type` strings; reuse the form_engine's.

## Reference URLs (unverified, not fetched)

- Stripe API reference conventions (expandable nested objects, example response beside field
  table): https://docs.stripe.com/api
- GitHub REST docs (cursor/`Link` pagination, per-endpoint example responses):
  https://docs.github.com/en/rest
- Typeform Responses API (answers as an array with `field` id, `type` and value per answer;
  closest comparable to self-describing answer entries): https://www.typeform.com/developers/responses/
- Google Forms API responses (answers keyed by question id): https://developers.google.com/forms/api/reference/rest/v1/forms.responses
- Python polling with `updated_since`/cursor: see existing `docs/api.md` "Syncing data".

status: ok
