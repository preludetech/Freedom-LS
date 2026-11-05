# Research: best practices (course progress incremental-sync API)

Written from established Django/DRF documentation and common API practice. URLs are the docs the claims rest on. Nothing was re-fetched this session, so check the exact wording before quoting.

## 1. Most relevant to this idea (recommendations)

1. **Add a single explicit `updated_at = DateTimeField(auto_now=True, db_index=...)` on `CourseProgress`**, not the `TimestampedModel` mixin. The mixin would bring a second `created_at` that clashes with the existing registration-date meaning. Pair it with a composite index on `(updated_at, id)`.
2. **Treat `auto_now` as save()-only.** It is set in `pre_save`, so `QuerySet.update()` and `bulk_update()` bypass it. The recalculation path must be made to move it. Options, in order of preference:
   - Route the writer through `save(update_fields=["progress_percentage", "updated_at"])`. `auto_now` fields are only written if they are named in `update_fields`, so you must add `updated_at` explicitly.
   - For `QuerySet.update()` or `bulk_update()`, set `updated_at=timezone.now()` explicitly, and include `"updated_at"` in the `bulk_update` fields list.
   - Optionally centralise this in a custom QuerySet or manager method (for example `update_progress(...)`) that always adds `updated_at=now`. Then grep every other writer of `CourseProgress` (`.update(`, `bulk_update`, `bulk_create(update_conflicts)`) and move it to that method. A test should assert `updated_at` advances for each writer.
3. **Backfill in the migration** in three steps: add the field nullable (or with a default), backfill, then alter to non-null.
   - Backfill with one set-based `UPDATE` through the ORM: `Greatest(Coalesce(last_accessed_time, ...), Coalesce(completed_time, ...), Coalesce(started_time, ...), created_at-equivalent)`.
   - Wrap each column in `Coalesce(..., <fallback>)`. Postgres `GREATEST` ignores NULLs, but the ORM `Greatest` returns NULL on some backends, so a Coalesce to a floor value is safe and portable.
   - Use a `RunPython` that calls `.update(updated_at=Greatest(...))`, or `RunSQL` if the table is huge. Both are a single statement, with no per-row Python loop.
   - Create the index afterwards, with `AddIndexConcurrently` (needs `atomic = False`) if the table is large. For this LMS, a normal index is probably fine.
   - Never edit existing migrations (project rule). Add new ones.
4. **Pagination**: cursor/keyset on `(updated_at, id)` with `id` as the unique tiebreaker. DRF `CursorPagination` with `ordering = ("updated_at", "id")` fits. Its position is encoded from the ordering fields, so non-unique timestamps are handled only if the ordering is deterministic. A composite index lets Postgres do an index range scan instead of an offset scan.
5. **`updated_since` is inclusive (`>=`)** and the consumer deduplicates by `id`. Document that clients should keep the max `updated_at` seen and re-send it. Duplicates are cheap and missed rows are not.
6. **Late-commit visibility**: a row that is created in a transaction and committed after a later-timestamped row has already been served can be skipped. `auto_now` stamps at the Python time of `save()`, not at commit.
   - Mitigation: tell clients to subtract a small overlap window (for example 1 to 5 minutes) from their stored cursor, and dedupe by id.
   - Document this in the API docs page. The server cannot fully fix it without a commit-time sequence.
   - Clock skew between app servers has the same effect, and the same overlap handles it.
7. **Progress representation**: expose `progress_percentage` as an integer 0..100. Expose started and completed times as nullable ISO 8601 timestamps. "Not started" is `started_time: null`. Let the script derive state from the nulls rather than adding a status enum, unless the owner wants one. Do not return `0` as a proxy for "not started" if `started_time` can distinguish them.
8. **"Exactly one of two FKs"**: do not expose both nullable FK ids. Expose `registration_id` plus `registration_kind` (`"individual"` or `"cohort"`).
   - Compute them in the serializer from whichever FK is set.
   - The id is unique only within its kind, so `kind` is required to disambiguate. Document that.
   - Reuse the child 4 name if it exists (for example `kind`), for consistency across resources.
   - A DB `CheckConstraint` (xor) already guarantees the invariant. Select both relations (`select_related`) to avoid N+1.
9. **PII minimisation for a scoped key**:
   - Use an explicit allow-list of serializer fields, never `__all__`.
   - Expose only identifiers, email, first and last name, and organisation. No phone, no username, no last-login, no per-item data.
   - The scope name should map to the data class. Document exposure in `docs/product/security-and-data-handling.md`.
   - Filter by site explicitly in the queryset, and keep the rule that a key without the scope gets 403.

## 2. Supporting notes

### `auto_now` and `update_fields`
- `auto_now` values are applied in `pre_save()`. With `save(update_fields=[...])`, only the listed fields are written, so `updated_at` is not touched unless it is listed. This is the usual cause of "stale `updated_at`".
- `update()` issues a direct `UPDATE`, with no `save()`, no signals and no `pre_save`.
- `bulk_update(objs, fields)` also skips `pre_save` for fields not listed. For `auto_now`, set the attribute yourself and list it.
- Alternatives that avoid relying on discipline:
  - A DB trigger (strong, but out of the Django idiom and hidden).
  - `db_default=Now()` (Django 5+), which covers inserts only, not updates.
  - A custom `QuerySet.update()` override that injects `updated_at`. This is simple and catches stray `.update()` calls, but not `bulk_update` or raw SQL.
- Django docs: https://docs.djangoproject.com/en/stable/ref/models/fields/#django.db.models.DateField.auto_now and https://docs.djangoproject.com/en/stable/ref/models/querysets/#update and https://docs.djangoproject.com/en/stable/ref/models/querysets/#bulk-update

### Migrations
- Adding a column with a constant default is cheap on Postgres 11+ (no rewrite). `auto_now` fields need a one-off default in `AddField`. Use `default=timezone.now` with `preserve_default=False`, or add nullable and backfill.
- Django docs on data migrations and concurrent index: https://docs.djangoproject.com/en/stable/topics/migrations/#data-migrations and https://docs.djangoproject.com/en/stable/ref/contrib/postgres/operations/#django.contrib.postgres.operations.AddIndexConcurrently
- `Greatest` and `Coalesce`: https://docs.djangoproject.com/en/stable/ref/models/database-functions/#greatest

### Pagination and sync
- DRF cursor pagination (ordering must be unchanging and unique-ish, and is not suited to a mutable ordering field, which is exactly why a stable tiebreaker `id` is needed): https://www.django-rest-framework.org/api-guide/pagination/#cursorpagination
- Because `updated_at` is mutable, a row can move to a later position while a client pages. It then appears again later (harmless duplicate) rather than being missed. Syncing by `updated_at ASC` is therefore safe, whereas syncing by a descending order is not.
- Keyset pagination background: https://use-the-index-luke.com/no-offset
- Prior art for the changed-since pattern with an overlap and dedupe: Stripe (`created`/`starting_after`), Microsoft Graph delta, and Zendesk incremental exports (explicitly recommend a lookback and dedupe on id).
  - https://developer.zendesk.com/documentation/ticketing/managing-tickets/using-the-incremental-export-api/
- Deletions are invisible to this pattern. State that plainly in the docs (it is already out of scope).

### Filtering
- DRF/django-filter: define `updated_since` as a `DateTimeFilter(field_name="updated_at", lookup_expr="gte")`. Reject non-ISO values with a 400. Require timezone-aware input, or define how naive input is treated.
- Extra filters (`course`, `registration_kind`) only if they match what child 4 offers.

### Percentages in APIs
- Keep it a bare number with no `%` string. Document the range and that it is a snapshot recalculated in the background, so it can lag the underlying activity. `updated_at` reflects the last recalculation write, not the last learner activity. `last_accessed_time` is the latter.

## 3. Risks for the spec to settle
- Recalculation writers that skip `save()` (audit needed).
- Recalculation that rewrites an unchanged percentage will bump `updated_at` and flood the feed. Guard with "only write if changed" if the recalc is a bulk job.
- Late-commit and clock-skew gaps need a documented overlap.
- Backfill value for rows with all-null timestamps needs a floor (for example the registration date or the migration time).

status: ok
