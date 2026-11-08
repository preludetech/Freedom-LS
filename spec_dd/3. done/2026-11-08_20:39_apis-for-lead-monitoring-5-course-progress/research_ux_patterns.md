# Research: UX patterns (developer experience) for the course-progress API resource

Audience: a script author syncing course progress into a CRM or warehouse.

## 1. How the existing FLS API docs page lists resources (the new row must match)

The page is `docs/api.md` (not a template or view). A test, `freedom_ls/api/tests/invariants/test_api_docs.py`,
only checks the Python code block compiles.

Structure to follow:
- Intro (line 7-8) says "Today there is one: [users](#users)". It must be updated to list course progress.
- "API scopes" table (line 41-49) already lists `registrations_and_progress` -> `LearnerCourseRegistration`,
  `CohortCourseRegistration`, `CourseInterest`, `CourseProgress`. The sentence "Only `users` has an API endpoint so far"
  (line 48) goes stale and needs an edit (the registrations/applications children edit it too; expect merge overlap).
- Shared sections ("Pages", "Incremental syncs with `updated_since`", "Deletions") are generic. They say "Rows come in
  ascending `(updated_at, id)` order" and that deletions are not reported. Course progress should link to them and not repeat them.
- Per-resource section (the `## Users` pattern, line 232-267):
  1. one-line description: "`/api/v1/<name>/` lists ... of the key's site."
  2. A two-column header-less table: API scope / List / Detail / Filters
     (`updated_since`, plus `cursor` and `page_size` on the list).
  3. `### Fields` table with columns `Field | Type | Notes`. Types written as `integer`, `string`, `boolean`,
     `string (ISO 8601)`, `string (ISO 8601) or \`null\``. The `id` row says "Upsert on this."
  4. `### What moves \`updated_at\`` section. It states what does and does not move it (users: sign-in does not).
  For course progress this section matters more than for users: say that background progress recalculation
  moves `updated_at`, that `last_accessed_time` is player-written and is **not** the sync key, and that rows are hard-deleted
  (no feed; full pull to catch removals).
- Docs vocabulary: "API endpoint", "API scope", "row". No "resource" and no "endpoint" on its own.
- Detail path uses `<id>`; for course progress the id is a UUID string (say so in the `id` Notes, unlike users' integer).
- No example response exists on the page today (only the list envelope with `[ ... ]`). Adding one short JSON row to the
  course-progress section is a cheap win, and matches the field table. Keep the single Python example generic.

## 2. Patterns from comparable APIs

Fetched and confirmed:
- Canvas course progress (https://canvas.instructure.com/doc/api/courses.html): `CourseProgress` object has
  `requirement_count`, `requirement_completed_count`, `next_requirement_url`, `completed_at` (null if not complete).
  Completion is a **nullable timestamp**, not a status enum; progress is expressed as counts, not a percent.
  Per-learner endpoint `/courses/:id/users/:uid/progress` and a bulk `/courses/:id/bulk_user_progress`.
  Progress is a nested object on the course, not a flat row.
- Stripe (https://docs.stripe.com/api/events/object): every object has `id` and `object` (string, value is the type name,
  "Objects of the same type share the same value"); events add a `type` discriminator. Nullable fields are marked "(string, nullable)"
  in the attributes list; timestamps are Unix seconds (FLS uses ISO 8601, deliberately). Stripe's
  `object` field is a **resource-type** discriminator, not a "kind of registration"; it is not needed here
  since each API endpoint returns one type.

From general knowledge, not fetched in this run (treat as lower confidence):
- Moodle web services (`core_completion_get_course_completion_status`) return a `completed` boolean, per-criterion
  `complete`, and `timecompleted`. Open edX completion/enrollment APIs return `completion` with `earned`/`possible` and a
  `percent`-style float. Both pair a boolean/percent with a timestamp.

## 3. Design-relevant conclusions

| Question | Common practice | Recommendation for this spec |
| --- | --- | --- |
| Completion state | Nullable `completed_at` (Canvas, Moodle `timecompleted`); status enums are rarer on progress rows | Expose `completed_time` as nullable ISO 8601 (idea already does). Do not add a `status` enum or `is_completed`; document "`null` means not completed". Script authors derive "not started" as `started_time` null. |
| Percentage | Int 0-100 is easy to compare/threshold; floats cause `99.99999` and equality surprises | Integer 0-100 (already settled). State range and that 100 does not imply `completed_time` is set (if that can differ, document it). |
| Related objects | Stripe/Canvas nest or expand; sync/CRM-oriented APIs flatten so no join | Flatten (already settled). Use prefixes only where ambiguous; reuse child 4's names exactly (`user_id`, `email`, `first_name`, `last_name`, `organisation_id`, `organisation_name` or whatever child 4 fixes). |
| Course | Id + title is the usual compact reference | `course_id` and `course_title` flat, consistent with learner flattening. |
| Registration discriminator | Stripe `object`/`type`; polymorphic refs usually use `<thing>_id` plus `<thing>_type`/`kind` | Two flat fields: `registration_id` + `registration_kind` with enum values `individual`/`cohort`, documented in the Notes column with both values listed. Match child 4's `kind` if it exists. A caveat to document: the ids of the two registration tables can collide, so `registration_id` is only unique together with `registration_kind`. |
| Filters | Canvas/Moodle filter by course id; kind filter is rarer | `updated_since` only unless child 4 already ships `course_id`/`kind` filters. A `course_id` filter is the most useful one for a script (per-course sync). Only add if free. |
| Timestamps | ISO 8601; name the field that drives sync | Fields table must mark `updated_at` as "Drives paging and `updated_since`" (copy users' wording). Naming: `started_time`, `completed_time`, `last_accessed_time` come from the model; the API's docs already use `created_at`/`updated_at`/`last_login`. Spec should decide whether to expose model names or `*_at`; mixed naming in one payload (`updated_at` beside `started_time`) is a DX wart. |
| Docs example | Show one request and one trimmed JSON row beside the field table | Add a one-row example JSON response. |

## 4. Open DX risks to surface in the spec

- Mixed `_time` / `_at` naming in one row (see above); pick one and justify it.
- `registration_id` ambiguity across two tables (see above).
- `progress_percentage` may change with no user action (recalculation); the docs must say the row reappears in `updated_since`
  syncs for that reason, so scripts upsert rather than append.
- `CourseProgress` hard deletion: point to the shared "Deletions" section.

status: ok
