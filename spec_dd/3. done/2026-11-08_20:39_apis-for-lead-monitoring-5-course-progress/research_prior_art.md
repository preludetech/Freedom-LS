# Prior art: course progress API (spec 5)

## Here: decisions already taken that this spec must follow

From the roadmap section "Lead monitoring API" (`spec_dd/1. next/roadmap.md:643-732`) and the done foundation spec (`spec_dd/3. done/2026-11-03_09:54_apis-for-lead-monitoring-1-foundation-and-users/1. spec.md`):

- Read only; DRF; explicit snake_case field lists; ISO 8601 with timezone; UUIDs as strings. Resource viewset is a `ReadOnlyApiViewSet` with a required `required_scope` (a system check fails a registered viewset without one); scope `ApiScope.REGISTRATIONS_AND_PROGRESS`.
- Pagination is the custom `ApiKeysetPagination` (not DRF `CursorPagination`), ordered `("updated_at", "id")`, tested with 1,500 rows sharing one `updated_at`. `UpdatedSinceFilterSet` maps `updated_since` to `updated_at__gte` (inclusive; naive or unparseable is 400). So the model must expose a field literally named `updated_at`.
- Foundation added an index on `User (site, updated_at, id)`. Precedent for an equivalent index on `CourseProgress`.
- Foundation docs tell clients: checkpoint at max `updated_at` minus 5 minutes, advance only after a full run, upsert by `id`, deletions need a periodic full pull. Spec 5 inherits this; it should add the endpoint to `docs/api.md` and `docs/product/security-and-data-handling.md` only.
- Foundation's precedent for "a related write must move `updated_at`": `touch_user_updated_at` receiver does `User._base_manager.filter(pk=...).update(updated_at=timezone.now())` on `EmailAddress` post_save/post_delete; it documents that queryset `update()` and bulk operations send no signals and are not covered. Same limitation will apply here. Also chosen by the owner: login churn must not flood the sync (`last_login` does not move `updated_at`), the same reasoning that says recalculation must move `updated_at` here but a player visit already moves `last_accessed_time`.
- Foundation added `freedom_ls_api.ApiKey` to `TIMESTAMPED_MODELS` in `freedom_ls/contrib/conformance/tests/test_timestamped_models.py`. That file's comment states "Progress and delivery records are deliberately absent: they carry their own domain-meaningful timestamps ... and a second pair would invite the wrong one to be read." `CourseFormAttempt` is the one progress model in the list. If spec 5 uses `TimestampedModel` the registry must change and that comment must be reconciled; if it adds a single `updated_at` field, the guardrail is untouched. This bears directly on the "mixin vs single field" open question. `TimestampedModel` (`site_aware_models/models.py:173`) declares both `created_at` (`auto_now_add`) and `updated_at` (`auto_now`); `CourseProgress` already declares its own `created_at`, so inheriting the mixin would clash on the name, not just duplicate it.
- Foundation QA found one pre-existing site-isolation gap (allauth `EmailAddress` admin, fixed by `SiteAwareEmailAddressAdmin`) by testing across two sites. Worth repeating the cross-site check for this resource. Foundation QA otherwise passed API behaviour cleanly (pagination, `updated_since`, scope 403, HEAD/OPTIONS). Nothing in it was abandoned for the API itself.
- Roadmap caution: spec 4 and spec 5 both add `updated_at` and both flatten learner to user and organisation; whichever lands second reuses the first's flattening. Spec 4 is "in progress" in a sibling worktree, so check whether its serializer exists before defining one.

## Here: course progress history (why the timestamps look the way they do)

- `spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/decision.md` (around line 190): progress rows are minted at registration, so `created_at` = registration date, `started_at` = first content access, and `last_accessed_time` was deliberately changed from `auto_now` to explicit because a background percentage recalculation bumped it. That is the abandoned approach: using `auto_now` on `last_accessed_time` made recalculation look like a visit. Do not reuse `last_accessed_time` as the sync cursor, and do not touch the player's handling of it (out of scope).
- `freedom_ls/learner_progress/signals.py:53-65`: `recalculate_progress_percentage()` does `record.save(update_fields=["progress_percentage"])`, with a docstring saying why. **Gotcha**: Django does not write an `auto_now` field that is absent from `update_fields`, so a plain `auto_now` `updated_at` would silently stay stale for exactly the case the idea cares about. The fix is to add `"updated_at"` to that `update_fields` list (and to every other `update_fields` save below).
- Writers of `CourseProgress` that bypass or restrict `save()` today (answers the open question "does any other writer bypass"):
  - `signals.py:65` recalculation: `save(update_fields=["progress_percentage"])`.
  - `management/commands/recalculate_progress_percentages.py:64`: `cp.save(update_fields=["progress_percentage"])`.
  - `signals.py:310` cohort move: `record.save(update_fields=["cohort_registration"])`.
  - `signals.py:314` cohort move swap: `CourseProgress._base_manager.filter(...).update(cohort_registration=Case(...))`. A queryset `update()`; it changes the registration id exposed by the API and would not move `updated_at` unless it adds `updated_at=Now()` or the value is set explicitly. This is the one real bulk-update bypass in production code.
  - `signals.py:84-87` docstring: `queryset.update()`, `bulk_create()`, `bulk_update()` on item progress fire no recalculation signal, so percentage drift is already a known, documented risk; the escape hatch is calling `recalculate_progress_percentage()` for affected records.
  - Test and QA-seed `.update(...)` calls (`qa_helpers/management/commands/*`, `test_signals.py`, `test_course_player.py`) set `created_at` or `progress_percentage` directly. After the migration, tests that rely on stale `updated_at` after `update()` should not exist, but QA seeds that backdate `created_at` will leave `updated_at` newer than the registration date; harmless.
  - Percentage can also move via the `recalculate_progress_percentages` command (backfill), which will then bump `updated_at` for every changed row: expected, and a reason the spec should say a full recalculation re-emits rows to scripts.
- `spec_dd/3. done/2026-10-29_12:46_more_lead_admin_exports/`: contains no course-progress export (grep finds none). The idea confirms no admin export covers progress, so there is no existing column set to match. The admin `CourseProgressAdmin` (`learner_progress/admin.py:216`) lists `progress_percentage`, `created_at`, `last_accessed_time` and is the closest existing field naming.
- `spec_dd/1. next/apis-for-lead-monitoring/research_data_sources.md` section 1: `TopicProgress.last_accessed_time` is `auto_now` (usable cursor) but `CourseProgress` has none; the research flagged "needs the changed-since decision". This spec is that decision.

## Elsewhere

- Django treats `auto_now` as applying only in `Model.save()`. `QuerySet.update()` leaves it alone (docs-only fix, ticket 26239, 15566), and `save(update_fields=...)` skips an `auto_now` field not listed (ticket 22981 wontfix; 35499 closed as duplicate on the argument that auto-adding it would remove any way to save without bumping it). Workaround recorded in the tickets: name the field explicitly in `update()` or `update_fields`; some teams use DB triggers.
  - https://code.djangoproject.com/ticket/26239
  - https://code.djangoproject.com/ticket/22981
  - https://code.djangoproject.com/ticket/35499
  - https://code.djangoproject.com/ticket/15566
  - https://code.djangoproject.com/ticket/35125
- Incremental sync with equal or late cursor values: Airbyte's discussion on a coarse cursor with a strict `>` shows rows sharing the last cursor value being missed; the answer was a lookback window or periodic full refresh, and that a primary key de-dupes but does not close the gap. Airbyte's docs also say the cursor only advances at the end of the sync and parent cursors must move when children change. This matches the foundation's choices (inclusive `>=`, `(updated_at, id)` keyset, minus-5-minute checkpoint) and supports documenting a lookback for this resource too.
  - https://github.com/airbytehq/airbyte/discussions/79103
  - https://docs.airbyte.com/platform/connector-development/config-based/understanding-the-yaml-file/incremental-syncs
  - The commit-order case (a long transaction commits a row with an older `auto_now` timestamp after a later one was read) was not confirmed by a source here; it is general knowledge. `auto_now` takes `timezone.now()` at save time in Python, not at commit, so the 5-minute lookback is the mitigation.
- Adding a column with backfill on a large table: add nullable, backfill in batches, tighten to NOT NULL separately; single-transaction row-by-row backfills caused outages (one report: 180,000 rows, 47 minutes); a volatile per-row default forces a table rewrite. Relevant to the migration "set `updated_at` to the latest of the row's existing timestamps": do it as one set-based `UPDATE ... GREATEST(created_at, started_at, last_accessed_time, completed_time)` (nulls need `COALESCE`/`GREATEST` handling; Postgres `GREATEST` ignores NULLs), not a Python per-row loop. `CourseProgress` is likely small, but the pattern is cheap.
  - https://django-safe-migrations.readthedocs.io/en/latest/patterns/
  - https://buildsmartengineering.substack.com/p/the-django-migration-bug-that-took
- Progress percentage drift in other LMS products: LifterLMS caches student progress in the database for report speed and the vendor advises clearing the "Student Progress Cache" to regenerate; a WordPress LMS report shows the summary stuck at 33.33% while the per-student view showed 100%; SAP SuccessFactors shows two views with different calculation methods classed as by design; Adobe Workfront percent complete freezes until a manual recalculate. Lesson: the API should serve the stored column, document that it is the stored value, and keep one calculation path (`calculate_course_progress_percentage`).
  - https://lifterlms.com/?p=28656
  - https://wordpress.org/support/?p=8732409
  - https://experienceleaguecommunities.adobe.com/t5/workfront-questions/frozen-project-percent-complete/m-p/467631

## Summary for the spec

1. Prefer a single added `updated_at = DateTimeField(auto_now=True)` (with a `(site, updated_at, id)` index) over `TimestampedModel`, since the mixin collides with the existing `created_at` and contradicts the conformance guardrail's stated reasoning; the spec should say so and leave `TIMESTAMPED_MODELS` alone, or consciously change that comment.
2. `auto_now` alone fails for the recalculation path: every `save(update_fields=[...])` on `CourseProgress` (signals.py:65, :310, the management command) must list `updated_at`, or recalculation should go through one helper that does. The cohort-swap `.update()` at signals.py:314 must set `updated_at` explicitly.
3. A test should pin that `recalculate_progress_percentage()` moves `updated_at` and not `last_accessed_time`.
4. Follow the foundation's checkpoint/lookback documentation; deletions stay invisible.

status: ok
