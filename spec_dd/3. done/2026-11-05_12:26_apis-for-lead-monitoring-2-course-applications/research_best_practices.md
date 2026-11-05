# Research: best practices for a read-only incremental-sync course applications API

Topic: `best_practices`. Scope: DRF read-only endpoint for `CourseApplication` with nested answers,
polled by scripts with `updated_since` plus cursor pagination. Terms for this project follow the idea
file (`CourseApplication`, `AnonymousApplicant`, `FormProgress`). Web evidence was thin and mostly
practitioner guidance, so each point is marked **[web]** (sourced) or **[general]** (established
engineering knowledge, not verified in this pass; the spec should confirm by test or migration).

## 1. What "last modified" should mean for a parent with child rows

Findings
- A changed-since filter only works if every change a consumer cares about moves the one timestamp the
  filter and cursor order on. A "created but never modified" record can be skipped by an updated-after
  filter if its timestamp is null, so the column must be non-null and set at create time. **[web]**
  (Flxpoint).
- Two real options for a parent whose children change independently:
  1. **Denormalised timestamp bumped on child save.** Child `save()`/signal (or a DB trigger) updates
     the parent's `updated_at`. Pros: a single real column on one table, so it can have a plain
     B-tree index on `(updated_at, id)`; cheap filter and cursor. Cons: every write path must bump it.
     `bulk_create`, `bulk_update`, `QuerySet.update()` and `delete()` skip `save()` and signals
     (`post_save` is not sent), so those paths silently break the guarantee. Bump with a targeted
     `QuerySet.filter(pk=...).update(updated_at=now)` (not `parent.save()`, which re-saves all fields
     and races) inside the same transaction as the child write. **[general]**
  2. **Annotated `Greatest(app.updated_at, applicant.updated_at, form_progress.last_updated_time,
     max(answer.updated_at))`.** Always correct with no write-path discipline, and picks up writes
     from any path including raw admin edits. Cons: an expression index can only reference columns of
     the one table being indexed, so a Greatest across joined tables (and any aggregate over answers)
     cannot be indexed. The filter and the `ORDER BY` then force a computed value for every row of the
     site, followed by a sort, per page request. That is fine for thousands of rows, poor for hundreds
     of thousands. Django supports `Index(Greatest(...))` expression indexes but PostgreSQL requires
     index functions to be IMMUTABLE and Django does not validate this; `Greatest` over timestamptz
     columns of one table should be allowed but confirm in a migration. **[web]** for the immutability
     rule; **[general]** for the cross-table limit.
- Hybrid (commonly the pragmatic answer): keep a real indexed `updated_at` column on the parent as the
  single sync clock, and make it the maximum of everything by bumping from each child path, plus a
  test that enumerates every child write path. Alternatively annotate `Greatest()` over only the
  cheap, 1:1, same-row-count joins (applicant, form progress) and bump the parent from the answers
  path, which is the many-rows child. Either way, use the *same expression* for the response field,
  the `updated_since` filter and the ordering, so what a script sees equals what it filtered on.
- A DB-level guard against missed write paths is a trigger; this repo's conventions (ORM only) lean
  against it, so the spec should say so explicitly if it rejects triggers.
- Invariant to test: for each child write (answer create/edit/delete-of-answer if exposed, sitting
  submit, applicant verification/claim fields that are in the response) the parent's sync timestamp
  strictly advances to at least the change time. Note deletion of an answer changes the nested payload
  but leaves no row to carry a timestamp; only the parent bump (option 1) captures it. Option 2 with
  `Greatest` over remaining answers will not see it. That is a concrete reason to prefer a bumped
  column. **[general]**
- Only timestamps of data actually in the response should move `updated_at`. Fields the endpoint hides
  (consent evidence, claim state) should not cause a bump, or consumers see spurious changes. **[general]**

Sources
- https://www.apihelpcenter.flxpoint.com/docs/guides/syncing-data-incrementally
- https://docs.djangoproject.com/en/stable/ref/models/indexes/ (expression indexes)
- https://code.djangoproject.com/ticket/26167 and https://forum.djangoproject.com/t/generatedfield-with-postgresql/33007 (immutability requirement for index/generated expressions)

## 2. Guaranteeing no missed changes

- **Inclusive lower bound** (`updated_at >= since`), as already settled. Consumers de-duplicate by id;
  processing must be idempotent (upsert keyed by id). Feeds are at-least-once. **[web]** (Elementary).
- **Commit-order race.** A row whose `updated_at` was assigned by `now()` in a slow transaction can
  commit after a later-timestamped row has already been served and the consumer's watermark advanced.
  The row is then permanently skipped. Sequence ids have the same flaw. **[web]** (DEV Community
  "cursor pagination … shared a timestamp"; Stacksync keyset article).
  Mitigations, in order of how common they are:
  1. Client **overlap window**: next poll starts at `last_seen - overlap`. Guidance: begin around 5
     minutes, raise to 30-60 minutes if updates go missing; persist the watermark only after the full
     run succeeds. **[web]** (ERP.net, Elementary, dlt `lag`).
  2. Server-side **safe upper bound**: the API only returns rows with `updated_at <= now() - delay`
     (e.g. 30-60 s, longer than the longest write transaction), so uncommitted in-flight rows cannot
     lag behind the served frontier. Document the delay. **[general]** This makes the client overlap
     mostly a safety net, at the cost of a slightly stale feed.
  3. Keep write transactions short, and take the timestamp as late as possible. Django's
     `auto_now` uses `timezone.now()` at `save()` time, not commit time, so a long `atomic()` block
     widens the window. **[general]**
- **Clock skew**: application servers set `updated_at` from their own clocks. With multiple app hosts,
  timestamps from different hosts can disagree by milliseconds to seconds. Overlap covers it; using
  DB `Now()` (a `Now()` expression in the bump `update()`) removes the skew. **[general]**
- **Precision**: keep microsecond precision end to end and treat the cursor as an opaque token. A
  cursor truncated to milliseconds and compared against a microsecond column drops rows that share a
  timestamp. Timestamps in the response must be serialised at full precision, otherwise a script that
  feeds the response timestamp back as `updated_since` can lose rows. **[web]** (DEV Community).
- **Ties**: order on `(updated_at, id)`; id as tiebreaker is the standard keyset pattern. DRF
  `CursorPagination` is offset-within-ties based on the ordering field and can degrade or loop when
  many rows share the exact ordering value (for example a bulk update stamping thousands of rows with
  the same time) because it encodes a position by offset among equal values. Pin a test with more
  tied rows than the page size. DRF's `ordering` accepts a tuple, so `("updated_at", "id")` works, but
  confirm tie handling by test. **[general]**
  https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- **Stable traversal**: because the order key is the one that rows move on (an edit during pagination
  moves a row to the end), a row can be seen twice or, if it moves *behind* the cursor, be picked up
  only on the next poll. That is acceptable with inclusive bounds + overlap; state it in the docs.
  Capturing an upper bound before paginating is a known mitigation. **[web]** (Stacksync).
- **Periodic full reconcile**: since deletions are not exposed (settled), and watermarks can miss
  edge cases, recommend scripts do an occasional full pull and diff to notice deleted applications.
  **[web]** (Flxpoint).
- Document in the docs page: store the *max* `updated_at` seen, subtract the overlap, persist only
  after success, upsert by id.

Sources
- https://docs.erp.net/dev/domain-api/data-sync/incremental-pull.html
- https://docs.elementary-data.com/api/incremental-sync
- https://docs.airbyte.com/connector-development/config-based/understanding-the-yaml-file/incremental-syncs
- https://www.mintlify.com/dlt-hub/dlt/api/sources/incremental
- https://dev.to/kingsleyonoh/the-cursor-pagination-that-worked-until-five-rows-shared-a-timestamp-47p3
- https://www.stacksync.com/blog/keyset-cursors-postgres-pagination-fast-accurate-scalable
- https://www.apihelpcenter.flxpoint.com/docs/guides/syncing-data-incrementally

## 3. Representing nested answers with heterogeneous types

- **Stable identity**: key each entry by `question_id` (UUID string / pk), never by question text.
  Include `question_text` and `question_type` as denormalised convenience so a consumer needs no second
  call; text can change, id cannot. Do not use position as identity. **[general]**
- **Unanswered: pick one and document it.** Options: (a) omit the entry; (b) include the entry with
  `value: null`. Recommendation: **always list every question on the form with `value: null` when
  unanswered** is the more stable schema (a consumer sees the question set and can distinguish
  "not answered" from "question absent from this form version"), but costs a join to the form's
  questions and complicates the query count. Omitting is cheaper (answers prefetch only) and matches
  how rows exist in the DB. The idea allows either; whichever is chosen, separate `null` (no answer)
  from empty string/empty list (answered with nothing) and say so. Avoid mixing both. **[general]**
  (JSON:API and Stripe-style APIs both document explicit-null for known-but-empty fields.)
- **Value shape**: a polymorphic `value` is awkward for typed consumers. Options: (a) one `value`
  field whose JSON type depends on `question_type` (string, list of strings, number, bool, null) with
  the mapping tabulated in the docs and OpenAPI; (b) always a string plus the type tag. (a) is the
  common choice; for drf-spectacular express the `value` as `oneOf`/untyped via a documented
  `extend_schema_field` since a `SerializerMethodField` otherwise appears as an untyped object.
  Keep it consistent per `question_type`: a given type must never return a string in one row and a
  list in another. **[general]**
- **Multiple choice**: always a JSON array of option texts (in a stable order, e.g. option order),
  even with one selected; single choice is a string. The idea says "option answers give the option
  text"; consider also exposing option ids if option text is editable (text edits otherwise look like
  data changes). Out of the idea's explicit field list, so only if the spec adds it. **[general]**
- **Dates and times**: ISO 8601 text (`YYYY-MM-DD`, `HH:MM:SS`, datetimes with offset); do not emit
  localised display formats. Numbers: JSON numbers or decimal strings; if decimals matter for money
  or precision, DRF `DecimalField` defaults to string (`COERCE_DECIMAL_TO_STRING`) and consistency
  matters more than the choice. **[general]**
- **Reuse** the value-extraction logic of `freedom_ls/form_engine/exports.py` rather than writing a
  parallel one (project rule: avoid repeating code), but return native JSON types, not CSV strings.
  CSV-only concerns (formula escaping, BOM, `TRUE`/`FALSE`) are explicitly dropped.
- Free-text answers are untrusted user input. JSON output is safe from formula injection, but the
  text is not HTML-escaped by DRF's JSON renderer; consumers that put it in HTML must escape.
  Say so in the docs. **[general]**
- Answers are the child collection of `CourseApplication` through form progress/attempt; confirm that
  only the *current* answers are listed (no history) and that `question_type` is a stable enumerated
  string, listed in OpenAPI as an enum.

## 4. File-upload answers as metadata only

- Return only the filename (as the idea settles): the base name, not `FieldFile.url`, not the storage
  path (paths may embed directory structure, UUID, or site/user ids). Use `os.path.basename(f.name)`
  of the stored name, or the original filename if the model keeps it. Never call `.url` or generate
  a signed/media URL. In DRF, a plain `FileField` serialises to an absolute URL by default, so the
  serializer must not auto-map it. Use an explicit method that reads `.name`. **[general]**
- Test that a file answer's payload contains no `/media/`, no scheme, no directory components, and
  that the value equals the filename string. For an answer where the file is missing/empty, return
  `null`.
- Optional extras if the spec wants them: size or content type. Not requested; the project rule is
  not to build what was not asked. Note the filename itself can be PII (people name CVs after
  themselves), which belongs in the security doc update.
- OWASP API3 (excessive data exposure) is the relevant risk.
  https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/

## 5. Avoiding N+1 and pinning query counts

- Pattern: `select_related("user", "anonymous_applicant", "course", "form_progress")` for the
  to-one links, `prefetch_related(Prefetch("form_progress__answers" ..., queryset=Answer.objects
  .select_related("question")...))` for the many side. Prefetch the *question* (and for option
  answers, the selected options) too; the usual N+1 leak is in the answer-value method touching
  `answer.question` or `answer.selected_options.all()` inside the serializer. Verify the exports'
  prefetches in `freedom_ls/course_applications/resources.py` and reuse them. **[general]**
- Use `.only()`/explicit `Prefetch(queryset=...)` to avoid loading unneeded columns (consent
  evidence, long text) if cheap; do not over-engineer.
- The viewset's `get_queryset` must be the single site-scoped source for list and detail; filtering by
  `updated_since` and the `Greatest` annotation (if used) sit on top of it.
- Prefetch with cursor pagination works (pagination slices the base queryset, prefetch runs on the
  page); it does not work with `iterator()` without `chunk_size` on Django 4.1+. Do not use
  `iterator()` in the viewset. **[general]**
- **Pin the query count** with `django_assert_num_queries` (pytest-django) at a fixed page: build N=1
  application and N=5 applications with answers of every question type, assert the same number of
  queries for both (this catches N+1 regressions better than a single absolute number), and also
  assert the absolute number so a drift is noticed. Account for auth/key lookup and throttle cache
  queries in the number or use `django_assert_max_num_queries` for the total. Separate the detail
  endpoint with its own pin. Include an application with no answers, one anonymous and one signed-in
  so the join paths both run. **[general]**
  https://pytest-django.readthedocs.io/en/latest/helpers.html#django-assert-num-queries
  https://www.django-rest-framework.org/api-guide/serializers/ (nested relations and prefetching)

## 6. PII handling in APIs

- The endpoint exposes names, emails and free-text answers of leads, so it is high-sensitivity even
  though read-only. Controls established in the effort (site-bound key, scope, hashing, expiry,
  throttle, audit on issue) are the right baseline; best practice adds:
  - **Explicit field lists** (settled) so a new model field never leaks by default. Add a test that
    asserts the exact key set of an application and of an answer entry, so adding a field is a
    conscious change. OWASP API3:2023 broken object property level authorization.
  - **Data minimisation**: exclude consent evidence (IP, terms version), claim state (settled). Make
    sure the nested `AnonymousApplicant` is not serialised wholesale.
  - **No PII in URLs / logs**: filters by email in a query string would land in access logs. The idea
    provides only `updated_since`; keep it so. Do not echo free text in error messages.
  - **Cache headers**: responses with personal data should send `Cache-Control: no-store` (or
    `private`) so intermediaries do not cache them. **[general]**
  - **Access audit**: key `last_used_at` is settled; request logging of key id + path (no bodies) is
    useful but the project says do not add logging unless asked, so leave it out of the spec unless
    requested.
  - **Documentation**: the security-and-data-handling doc update the idea requires is the
    transparency half (GDPR/POPIA-style): state purpose, who can read, that filenames only are
    exposed, that filenames can themselves identify a person.
  - **Retention / erasure**: deleted applications vanish from results, so scripts that copied data
    keep it. The docs page should tell consumers that they become responsible for data they copy,
    and that deleting an application at source does not delete their copy (no deletion feed).
  - Throttling and pagination caps limit bulk-exfiltration speed by a leaked key. Short key expiry
    is a documented hygiene.
  - Do not return `applicant_email` unmasked to a scope that does not need it: here the scope is
    purpose-built for lead monitoring so full email is expected; no masking.
  - Sensitive question answers (a form may ask for ID numbers, health, etc.): flag in the docs that
    any answer is exposed; there is no per-question opt-out in this spec (do not build one unless
    asked), but note it as a known risk/follow-up.
- Sources
  - https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/
  - https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
  - https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

## 7. Recommendations for the spec (summary)

1. Prefer a **real indexed `updated_at` column on `CourseApplication` as the sync clock**, bumped (via
   a `QuerySet.update()` in the same transaction, using DB `Now()`) from every child write path
   (answers save and delete, form progress submit, `AnonymousApplicant` fields shown in the response).
   Reason: indexable, and the only option that sees a deleted answer. If the spec prefers the
   annotated `Greatest()`, it must accept an unindexable filter/sort and say it is fine at the
   expected row count, and must state that answer deletion is not detected.
2. Same expression for the response `updated_at`, `updated_since` filter and ordering `(updated_at, id)`.
3. Add a **server-side settle delay** or a documented **client overlap (start 5 min)**; store max seen,
   persist after success, idempotent upsert by id; recommend an occasional full reconcile.
4. Test: ties larger than page size; microsecond precision round trip; every child write path moves
   the clock; a bulk path (if any) is called out.
5. Answers: array keyed by `question_id`, with `question_text`, `question_type`, `value`; decide
   omit-vs-null (recommend cheap omit, or all questions with null, but state it); multi-choice as
   array of option texts, single as string, dates as ISO text; one JSON type per `question_type`.
6. File uploads: basename only, `null` if empty, tested for no URL or path.
7. Query-count tests comparing 1 vs N applications plus an absolute pin; detail endpoint separately.
8. Exact key-set tests; `Cache-Control: no-store`; docs cover consumer responsibility for copied PII.

status: ok
reason: web evidence limited to practitioner docs for sync/overlap and Django index immutability; other points are marked [general] and should be verified by test in the spec.
