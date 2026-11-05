# Research: best practices for the registrations and interest endpoints

Builds on the foundation's `research_best_practices.md` (sections 7 and 8: inclusive `updated_since`, at-least-once, `(updated_at, id)` cursor, `bulk_update` hazard, additive-only v1). Does not repeat them. Items tagged [fetched] were read this run; [knowledge] are from memory of established practice and need verifying before quoting. Foundation conventions are treated as fixed.

## 1. One endpoint with `kind`, or two endpoints

Recommendation: two endpoints (plus a third for interest), one per table. Suggested paths in the foundation's kebab-case style: `/api/v1/learner-course-registrations/`, `/api/v1/cohort-course-registrations/`, `/api/v1/course-interests/`.

Reasons:
- The foundation cursor is `CursorPagination` ordering `("updated_at", "id")` over one queryset. A union of two tables is not one queryset. `QuerySet.union()` cannot be filtered or ordered the way DRF's cursor needs (it applies `filter()` and `order_by` to the queryset), and the foundation's `UpdatedSinceFilterSet` assumes a model. A single endpoint would need a bespoke keyset paginator and a hand-built `UNION ALL`. That relitigates the foundation for no gain. [knowledge, DRF CursorPagination source: https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination]
- The two shapes differ (learner: `self_registered`, user id/email/organisation; cohort: cohort id/name). A merged serializer needs nullable fields keyed on `kind`, which makes the OpenAPI schema a `oneOf` that drf-spectacular handles poorly and that script authors must branch on. Separate endpoints give flat, fully typed schemas.
- Separate resources get separate checkpoints. A script stores one `updated_since` per resource, which is exactly how it already treats `users`. No new concept.
- Industry precedent for per-type feeds, not one polymorphic feed: Zendesk's incremental exports are one endpoint per resource type (tickets, users, organizations, custom objects), each with its own cursor. [fetched: https://developer.zendesk.com/documentation/ticketing/managing-tickets/using-the-incremental-export-api/]

If the spec still wants one endpoint (not recommended), the minimum correct design is: order by `(updated_at, kind, id)`; cursor encodes all three; per-kind queries each fetch `page_size` rows after the position, merge in Python, take `page_size`, and the next cursor is the last emitted row. UUID ids cannot collide across tables, but ties on `updated_at` between kinds still need the `kind` tie-break to be total. This is the "merge of two sorted streams" pattern. [knowledge]

For the progress child: with two endpoints, a `CourseProgress` row naturally carries `learner_course_registration_id` and `cohort_course_registration_id` (exactly one non-null), each matching the `id` of the corresponding endpoint. No `kind` field is needed anywhere. Flag that as the answer the progress child reads.

What a cohort registration shows where an individual one shows a learner: `cohort_id` and `cohort_name` (flat, same naming as `course_id`, `course_title`). No members, no user fields. Cohort membership is out of scope.

## 2. Soft state versus hard deletes

- `is_active` is soft state: expose it as a plain boolean and do not filter inactive rows out by default. A deactivation is an update that bumps `updated_at`; if inactive rows were hidden, `updated_since` would never tell a script a registration ended. Do not add an `?is_active=` default; an optional filter is fine but not required (the idea says expose only what is listed; skip it).
- Hard deletes (admin delete, cascade from user or course deletion, interest toggled off) leave nothing for `updated_since`. Settled as out of scope. The established fallback is periodic full resync with an id-set diff (foundation 7.9). Document it per resource, with extra emphasis for course interest: because toggling off is a delete, the interest feed is "currently interested", and a re-toggle creates a new row with a new id, so a script sees an "add" and never the removal.
- Precedent for the deferred feature, for the roadmap not this spec: Zendesk includes deleted records in incremental exports, flagged or scrubbed, with `exclude_deleted` to opt out, and drops them after 30 days. [fetched: https://developer.zendesk.com/documentation/ticketing/managing-tickets/using-the-incremental-export-api/] Google Calendar-style sync uses a `deleted`/`status: cancelled` tombstone instead. [knowledge] Either needs a soft-delete column or a separate tombstone table; neither exists, so do not build it here.
- Recommend a one-line statement in the docs page: "A row missing from a full listing was deleted; `is_active=false` means ended but retained."

## 3. Adding `updated_at` to existing tables

- `auto_now=True`: Django updates it only in `Model.save()`; `QuerySet.update()` leaves it alone unless you pass the value. [fetched: https://docs.djangoproject.com/en/5.2/ref/models/fields/#django.db.models.DateField.auto_now] `bulk_update()` also bypasses `save()`; list `updated_at` in its `fields` or set it explicitly. `bulk_create()` does run `pre_save`, so it is set. [knowledge]
- Audit before shipping: grep for `.update(`, `bulk_update(` and `update_or_create` on the three models, including toggling interest, deactivating registrations (admin actions, management commands, signals). Fix each to pass `updated_at=timezone.now()` or switch to `save(update_fields=[..., "updated_at"])`. Note `save(update_fields=[...])` skips `auto_now` unless `updated_at` is listed. [knowledge: the field must be in `update_fields`]
- Add a regression test per model: change `is_active` through every code path found and assert `updated_at` advanced. Cheaper guard: a test that fails if a new `.update(` on these models lacks `updated_at`; a lint-style grep test is acceptable.
- Backfill choices for existing rows (only decision with real consequences):
  1. Default `timezone.now` at migration time: every row looks changed at deploy. Simple, correct for sync (first full sync takes everything anyway), but loses ordering information.
  2. Backfill from best existing timestamp (`registered_at`, or the model's created field) via `RunPython` or `UpdateQuerySet.update(updated_at=F("registered_at"))`, then set `auto_now`. Gives sensible history; rows deactivated before the migration still carry the old date, which is unavoidable and should be said in the docs ("`updated_at` before <deploy date> is the registration date, not the last change").
  Recommend 2 where a creation timestamp exists, else 1. Both are fine for scripts because the first sync is a full read.
- Migration shape (Postgres 17): add the column with a constant `default=timezone.now` plus `auto_now`, or add nullable, backfill, then `AlterField` to non-null, as separate steps in one migration or two. Adding a column with a constant default is metadata-only on Postgres 11+, so no long table lock. Add the composite index `(updated_at, id)` in the model `Meta.indexes`; on a big table consider `AddIndexConcurrently` in a non-atomic migration. [knowledge]
- Site scoping: the foundation filters by site first; consider whether the index should lead with the site column, since every query is `WHERE site_id = ? ORDER BY updated_at, id`. Check how the site-aware base declares its site FK and index; an index on `(site, updated_at, id)` may serve better. [recommendation; verify with EXPLAIN]

## 4. Flatten or nest related identity

- Flatten. Scripts typically load rows into pandas, CSV or a warehouse table; flat scalars map one-to-one. Nested objects force a second flattening step and enlarge the contract. The idea already settles flat. Naming: `<relation>_<attr>` such as `user_id`, `user_email`, `organisation_id`/`organisation_name` (match whatever the users resource ships in child 1 so both endpoints use identical names and types), `course_id`, `course_title`, `cohort_id`, `cohort_name`. Foreign keys as `<thing>_id` strings (UUIDs as strings per the foundation).
- Stripe, Zendesk and most export-style APIs expose ids by default and expand on request; the equivalent here is: id plus the few display fields the script needs, no expansion. [knowledge: https://docs.stripe.com/api/expanding_objects]
- Staleness trap specific to flattening: `updated_at` on a registration does not change when the user's email or organisation, the course title or the cohort name changes. A script keying `updated_since` on registrations would carry stale email forever. Options: (a) document that flattened fields are as of the row's `updated_at` and the `users` resource (child 1) is authoritative for identity, joined on `user_id`; (b) annotate `Greatest(updated_at, user__updated_at, course__updated_at)` and filter on it, which defeats the plain `(updated_at, id)` index and the foundation's convention. Recommend (a). It is cheap, honest and keeps the foundation filter unchanged. State it in the docs page next to the at-least-once note.
- Query shape: `select_related("learner__user", "learner__organisation"?, "course")` for individual, `select_related("cohort", "course")` for cohort; assert query count at max page size.
- Reuse for progress: define the learner-to-user/organisation flattening once (a serializer mixin or shared field set) so the progress child imports it instead of re-inventing it, as the idea requires.

## 5. PII minimisation

- Data minimisation (GDPR Art. 5(1)(c)) means expose only fields the stated purpose needs. [knowledge: https://gdpr-info.eu/art-5-gdpr/] Email is the one direct identifier the idea justifies (the lead monitor must match a person); omit names, phone, address, free text, HR attributes and consent records (already out of scope).
- Use an explicit `fields = [...]` list, never `__all__` or `exclude`, so a column added later on a model cannot leak. Add a test asserting the exact key set of each endpoint's response, so adding a field is a conscious change (this also guards additive versioning).
- `self_registered` and `is_active` are behavioural not personal; fine. Cohort registrations carry no person data at all; keep it that way (no member counts needing a join, no member lists).
- Do not include the `Learner` id as its own field unless the users resource exposes it, since the idea says the learner is not a resource; `user_id` is the join key.
- Update `docs/product/security-and-data-handling.md` with the field list per endpoint and the retention note (rows leave the API when deleted; nothing is retained by the API).
- Filtering: site scope is applied by the foundation base queryset; add a cross-site test per endpoint (a registration on another site, plus a registration whose learner belongs to another site) as for `users`.

## 6. Versioning field additions

- Within `/api/v1/`, adding fields to a response is backward compatible; renaming, removing or changing type or meaning needs v2. Stripe documents exactly this: new resources, new optional parameters and new response properties are compatible, and clients should ignore unknown fields. [fetched: https://docs.stripe.com/api-versions and https://stripe.com/docs/upgrades]
- Consequences for this spec:
  - The new `updated_at` field and the three new endpoints are additive; no version bump.
  - Fields should not be renamed after release. Pick final names now (`user_email` not `email`, say) and match child 1. The progress child may add fields to registrations only additively.
  - A new field on an existing row does not bump `updated_at`, so existing consumers will not see its value on old rows until a full resync. Put a changelog line "after adding field X, run a full resync" in the docs page; this is the only operational cost of additive change in a sync API. [knowledge]
  - Keep the field set small: every added field is a permanent commitment in v1.
- Scope name `registrations_and_progress` is stored on keys; do not rename.

## 7. Short list of recommendations for the spec

1. Three read-only endpoints, one per table; no `kind` field; no union cursor. Registration rows in the progress child reference the two ids separately.
2. Cohort registration: `cohort_id`, `cohort_name` in place of learner fields.
3. `is_active` returned as a flag; inactive rows included; hard deletes documented as full-resync only; interest is a "currently interested" snapshot.
4. `updated_at` with `auto_now`, backfilled from the registration timestamp where present; audit every `.update()` / `bulk_update()` / `update_fields` on the three models; test each toggle path; composite index (site-leading if the base does so).
5. Flat fields; identity is as of the row's `updated_at`; users resource is authoritative; no `Greatest` annotation.
6. Explicit field lists plus exact-key-set tests; no names or other `Learner` data.
7. Additive-only within v1; changelog note that new fields need a full resync.
8. Shared learner-to-user/organisation flattening reused by progress.

## References

- Zendesk incremental export (per-resource feeds, deleted records, cursor) [fetched via search summary]: https://developer.zendesk.com/documentation/ticketing/managing-tickets/using-the-incremental-export-api/
- Django `auto_now` and `QuerySet.update()` [fetched]: https://docs.djangoproject.com/en/5.2/ref/models/fields/#django.db.models.DateField.auto_now
- Stripe API versioning, backward-compatible changes [fetched via search]: https://docs.stripe.com/api-versions and https://stripe.com/docs/upgrades
- Stripe versioning engineering post: https://stripe.com/blog/api-versioning
- DRF CursorPagination: https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- Stripe expanding objects [knowledge]: https://docs.stripe.com/api/expanding_objects
- GDPR Art. 5 data minimisation [knowledge]: https://gdpr-info.eu/art-5-gdpr/

status: ok
