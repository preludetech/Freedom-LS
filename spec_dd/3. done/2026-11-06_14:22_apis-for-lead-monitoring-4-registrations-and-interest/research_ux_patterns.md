# Research: UX patterns for registrations and course interest endpoints

Developer experience only. Builds on the foundation's fixed conventions (see `spec_dd/3. done/2026-11-03_09:54_apis-for-lead-monitoring-1-foundation-and-users/research_ux_patterns.md`): bearer key, `{"detail","code"}` errors, `next`/`results` envelope with no `previous` or count, ascending `(updated_at, id)`, inclusive `updated_since`, checkpoint = max `updated_at` minus 5 minutes, upsert by `id`, full pull to catch deletions.

## Repo facts (shipped by foundation)

- `docs/api.md` is one page. Order: Before you start, API keys, Making requests (Errors, Rate limit, Schema), Syncing data (Pages, `updated_since`, Deletions, Example), Versioning, then one section per resource. The intro says "Today there is one: [users](#users)" and the scope table says "Only `users` has an API endpoint so far". Both sentences go stale and must be edited.
- The per-resource section template is: a two-column summary table (API scope, List, Detail, Filters), a `### Fields` table (Field | Type | Notes), then a `### What moves updated_at` note. There is no example response per resource, only the generic list envelope.
- The Python example is `sync_users(updated_since)` with module-level helpers `get_page` and `upsert_user`; it hardcodes the users URL and the `email` print. `freedom_ls/api/tests/invariants/test_api_docs.py` guards the docs (check what it asserts before editing).
- Pagination and filters live in `freedom_ls/api/pagination.py`, `filters.py`, `viewsets.py`.

## 1. One endpoint with a kind field vs separate endpoints

How comparable APIs treat polymorphic or two-source lists:
- Stripe: separate endpoints per object type (`/v1/charges`, `/v1/refunds`); polymorphism within one list is expressed by an `object` or `type` discriminator (events list: `type`, `data.object`).
- GitHub: separate endpoints for distinct resources; the issue-events and timeline endpoints use an `event` discriminator and per-kind optional fields.
- Fivetran and Airbyte (sync destinations): each source table is its own stream with its own cursor/state. Mixing tables in one stream is not the norm; a consumer maps one stream to one table.

What the consumer joins on: a script writing to a warehouse or CRM wants one table per kind with a uniform column set. Learner registration has learner columns; cohort registration has cohort columns. A single merged feed forces nullable columns (`user_id`, `email`, `organisation` null for cohort rows; `cohort_*` null for individual rows) and a client-side split.

Cursor problem with a merged endpoint: ids come from two tables and collide (two integers or UUIDs from different tables), so `id` alone is no key; upsert would need `(kind, id)`, and the server cursor needs `(updated_at, kind, id)` over a UNION across two querysets, which DRF cursor pagination does not support natively. This is cost with no consumer benefit.

Recommendation: **two endpoints**, plus the third for interest: `/api/v1/learner-course-registrations/`, `/api/v1/cohort-course-registrations/`, `/api/v1/course-interest/` (kebab-case paths per project rule; match the names the model docs use). Each has its own plain `(updated_at, id)` cursor and a stable column set; each is one sync loop. Still include a constant `kind`-free design: do not add a `kind` field. If the spec wants a hint for joins, the endpoint name is the discriminator. This also settles the course progress child: each `CourseProgress` row points at exactly one registration kind, so it should carry `learner_course_registration_id` and `cohort_course_registration_id` (one null) with both UUIDs/ids, which join straight to the two endpoints. Say so in the registration docs section ("joined by `CourseProgress` later") only if progress ships; do not promise it in docs now.

If the spec nonetheless picks a merged endpoint: add `kind` (`"learner"` / `"cohort"`), upsert key `(kind, id)`, cursor over a UNION, and null-fill the other kind's fields. Not recommended.

## 2. Field naming and shape

- Keep a flat, explicit, snake_case list. Names mirror model fields so a reader can map them: `id`, `is_active`, `self_registered`, `registered_at`, `updated_at`.
- Flattened identity (Stripe prefers expandable nested objects, but nested requires the consumer to flatten; this API's settled decision is flat): use prefixed scalars. Recommendation: `user_id`, `user_email`, `organisation` is ambiguous (id or name?). Prefer `organisation_id` plus `organisation_name`, or a single `organisation` string only if the model really holds a text value. Pick by the model; the field table must say which, and must say "may be `null`/empty" when a learner has none. Do not name it `learner_*`: the spec says Learner is not a resource, and `user_id` is the id that joins to `/api/v1/users/` (the foundation `id`). State that explicitly: "`user_id` joins to `id` on the users endpoint".
- Course: `course_id` and `course_title` (flat, same prefix style). Cohort: `cohort_id` and `cohort_name` (check the model's actual field; `Cohort` title vs name). Use the same `<thing>_id` + `<thing>_<label>` pattern everywhere so the shapes read alike across the three endpoints.
- Interest: `user_id`, `user_email`, `course_id`, `course_title`, `created_at`/`registered_at` as the model holds, `updated_at`. Use the model's own timestamp names; do not rename for symmetry.
- Types: UUIDs as strings, timestamps ISO 8601 with offset, booleans real booleans. Note in the table which ids are integer (users) and which are UUID, since `user_id` is an integer while registration `id` may be a UUID.
- Denormalised labels (`user_email`, `course_title`) are a snapshot at response time. Document that changes to a user's email or a course title do not move the registration's `updated_at`, so an incremental sync will hold a stale label until the row changes. This is the main trap of flattening; flag it in a "What moves `updated_at`" note (the template already has that heading) and point to `/users/` as the source of truth for the email. Whether the spec makes the user or course change bump the registration is a design decision; recommend not, and document it.

## 3. Docs presentation

Stripe/GitHub reference pages present, per endpoint: summary line, parameters table, response object attributes with type and notes, then a full example response. Recommendation for each new section, using the existing template:
1. Summary table (API scope, List, Detail if any, Filters). Decide whether detail endpoints exist; the foundation has `GET /users/<id>/`. If the idea only needs lists, omit detail and say "list only" rather than leaving the row blank. Fewer endpoints, less to document.
2. `### Fields` table, with the same three columns. Group visually in this order: `id`, relationship ids and labels, state (`is_active`, `self_registered`), timestamps, `updated_at` last (matches users).
3. `### Example response`: one JSON block, a full list response with the `next` envelope and two rows (one active, one inactive), so the shape of `is_active: false` and a null `organisation` are visible. The users section has none, so this is new; consider adding one for users too, but that is out of scope for this spec.
4. `### What moves updated_at` listing: registration save, activate/deactivate (this is why the field is added), what does not move it (label changes, see section 2).
5. A single cross-reference table at the top of a new "Registrations and interest" heading that tells the reader which of the three endpoints answers which question ("who has enrolled themselves" = learner registrations with `self_registered`; "which cohorts are enrolled" = cohort registrations; "who showed interest" = course interest). Group the three under one `##` parent with three `###` children, or three `##` sections; recommend three `##` sections to match the users one and keep anchors short. Add them in the order learner registrations, cohort registrations, course interest.
6. Update the stale sentences: intro "Today there is one", scope table note "Only `users` has an API endpoint so far" (now `users` and `registrations_and_progress` have endpoints; `registrations_and_progress` still lacks course progress, so say "course progress is still to come").
7. Scope table row for `registrations_and_progress` already lists `CourseProgress`; leave it and note it is not yet served, so a key with the scope does not 404 on progress by surprise.

## 4. Python example extension

Existing code is users-specific. Options: (a) copy `sync_users` three times (repetition, drift); (b) generalise.
Recommendation: refactor to `sync(path: str, updated_since: str | None, upsert: Callable[[dict[str, object]], None]) -> str | None`, keeping `get_page` unchanged, and show `sync("users", ...)`, `sync("learner-course-registrations", ...)` etc. in `__main__` with one checkpoint per endpoint (a dict keyed by path, or one env var per endpoint). Reasons: the project rule against repeated code; a single loop teaches "one loop for all endpoints", which the "Syncing data" section already claims. Remove the `dict` bare types (project rules ban `Any`; `dict[str, object]` is acceptable). Keep it complete and runnable, and keep the docs example tested by the invariants test if it executes it.
- One checkpoint per endpoint, because each endpoint's `updated_at` advances independently; a shared checkpoint would skip rows. Say this in a line under the example.
- Keep upsert keys simple: the three endpoints have distinct `id` namespaces, so store each in its own table; for a flattened store key by `id` within the endpoint.
- Show the join in one comment: registrations carry `user_id`, matching `id` in the users table, so the script can join without calling anything else.
- Deliberately do not show cohort-specific handling beyond calling the same function.
- Keep the example under ~60 lines; the page is one page, so long examples bury the endpoint tables.

## 5. Inactive rows and unseen deletions

Pattern in comparable systems:
- Stripe/GitHub-like APIs: soft state appears as a status field (`status: canceled`, `state: closed`), and hard deletes appear only through a separate events feed or a `deleted` tombstone. Fivetran and Airbyte documentation of incremental syncs states plainly that cursor-based incremental sync cannot see hard deletes and recommend a periodic full resync ("re-sync" or "full refresh") or a delete feed. Zapier polling triggers likewise rely on a dedupe key and cannot observe deletes.
- So: the doc must say, per endpoint, in one or two sentences in the same section (not only in the shared "Deletions" section), what a consumer will and will not see.

Recommended doc text per endpoint:
- Registrations: "A deactivated registration still appears, with `is_active` set to `false`, and its `updated_at` moves. Treat it as ended, not as deleted. Rows are filtered by nothing except site: there is no `is_active` filter, so a script chooses what to do with inactive rows."
- Whether an `is_active` filter is wanted is a question for the spec; recommended not (not requested; `Don't build functionality that is not explicitly requested`).
- Course interest: "Switching interest off deletes the row. The API cannot tell you; a row that stops appearing in a full pull has been switched off. Run a full pull (no `updated_since`) when you need to remove those, and compare ids." Make this bold and visible because, unlike registrations, interest has no inactive state at all, so the only signal is absence. Suggest a cadence ("for example weekly") but not a rule.
- Also note: registrations can be deleted by staff (hard delete hazard in `research_data_sources.md`); the same full-pull advice applies. Put a three-row table in the "Deletions" shared section: User (deactivated: visible; deleted: invisible), registration (same), interest (toggled off: invisible).
- Warn about the full-pull diff approach: build the set of ids from the pull and delete local rows not in it only after the pull completes (partial pull deletes everything). One sentence.

## 6. Error and empty-state clarity

- Wrong scope: the foundation's 403 already names the scope; add nothing. Make sure the three new endpoints require `registrations_and_progress`, and say in the section that a key lacking it gets a 403 naming it.
- Empty list is a 200 with `{"next": null, "results": []}`, not a 404. State it once under "Pages" or in the new sections ("An empty `results` with `next: null` means nothing changed since your checkpoint; keep the old checkpoint"). The example already does this (`latest is None` returns the old checkpoint); say why in a comment.
- A site with no registrations yet returns the same empty list; no special case.
- 404 only on detail with another site's id; do not distinguish "exists on another site" from "does not exist" (already so in the shared table).
- Unknown query parameters: DRF ignores them silently, so a typo such as `updated_after` returns everything and looks like it works. Foundation convention; consider noting in docs "unknown parameters are ignored". Do not add a strict-parameter check here: it is a cross-cutting change.
- `updated_since` with a timestamp in the future returns an empty list, not an error; mention in passing.

## 7. Recommendations summary

1. Three endpoints (learner registrations, cohort registrations, course interest); no `kind` field; per-endpoint `(updated_at, id)` cursor; avoids cross-table cursor and id collision.
2. Flat prefixed scalars: `user_id`, `user_email`, `organisation_*` (exact name from the model), `course_id`, `course_title`, `cohort_id`, `cohort_name`. `user_id` joins to `id` on `/users/`. Document nullability.
3. Document that label changes (email, course title, cohort name) do not move the registration `updated_at`, and where to find the source of truth.
4. Docs: new `##` section per endpoint using the existing template, plus a new `### Example response` with an inactive row; fix the two stale "only users" sentences; add a per-endpoint inactive/deleted paragraph and a three-row table under "Deletions".
5. Example: generalise to one `sync(path, updated_since, upsert)` loop with one checkpoint per endpoint; no copy-paste per endpoint.
6. Make interest's "absence is the only signal" prominent; give the full-pull diff safely (only after complete pull).
7. Empty page is 200 with `next: null`; keep the old checkpoint.
8. Do not add an `is_active` filter or deletion feed.

## References

- Foundation research and shipped docs: `spec_dd/3. done/2026-11-03_09:54_apis-for-lead-monitoring-1-foundation-and-users/research_ux_patterns.md`, `docs/api.md`, `freedom_ls/api/tests/invariants/test_api_docs.py`.
- https://docs.stripe.com/api/pagination and https://docs.stripe.com/api/events (list envelope, `type` discriminator, event feed for deletions)
- https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api and https://docs.github.com/en/rest/issues/events (separate endpoints, `event` discriminator)
- https://fivetran.com/docs/core-concepts#incrementalsync and https://docs.airbyte.com/platform/using-airbyte/core-concepts/sync-modes/incremental-append (per-stream cursors; hard deletes need full refresh or a delete feed)
- https://docs.zapier.com/platform/build/deduplication (polling triggers dedupe on id; no delete visibility)
- Caveat: these were not fetched this session; they are from background knowledge. Verify before the spec quotes them.

status: ok
