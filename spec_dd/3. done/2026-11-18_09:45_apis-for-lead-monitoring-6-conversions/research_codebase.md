# Research: codebase (apis-for-lead-monitoring-6-conversions)

Paths are relative to the worktree root. Read: `idea.md`, `answers.md`, the child 3 spec, and the shipped code.

## 1. Shipped models: `freedom_ls/referral_tracking/models.py`

Both models extend `SiteAwareModel` (UUID pk via `default=uuid.uuid4`, a `site` FK). Both call `_refuse_update(self)` in `save()` (line 45): an append-only guard on `save()` alone. `QuerySet.update()` bypasses it, so tests set timestamps with `Model._base_manager.filter(...).update(...)`, as child 3 does.

### `AttributionTouch` (line 169)

| Field | Type |
| --- | --- |
| `user` | FK to `AUTH_USER_MODEL`, `on_delete=CASCADE`, `related_name="attribution_touches"` |
| `advert_code`, `referral_code` | `CharField(blank=True)`, max length from `CAPS` |
| `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` | `CharField(blank=True)` |
| `landing_path` | `CharField(blank=True)`. Blank on a flushed list entry. |
| `occurred_at` | `DateTimeField(db_index=True)` |
| `recorded_at` | `DateTimeField(auto_now_add=True)`, not nullable |
| `recorded_via` | `CharField(max_length=16, choices=TouchSource)`. Values `live`, `signup_flush`, `login_flush`. |
| `key_hash` | `CharField(max_length=64)` |

- Meta constraint: unique on `(site, user, occurred_at, key_hash)`.
- Meta indexes: `(site, user, occurred_at)`, `(site, referral_code)`, `(site, recorded_at)`.
- Meta ordering: `["-occurred_at", "-recorded_at"]`.
- No IP, user agent, referer, raw query or click id on the model.

### `Conversion` (line 235)

| Field | Type |
| --- | --- |
| `user` | FK, `CASCADE`, `related_name="referral_conversions"` |
| `kind` | `CharField(max_length=32, choices=ConversionKind)`. Values `account_signup`, `course_application`, `course_interest`, `course_registration`. |
| `content_type` | nullable FK to `ContentType`, `CASCADE` |
| `object_id` | `CharField(blank=True)` |
| `target` | `GenericForeignKey` |
| `target_label` | `CharField(blank=True, max_length=255)` |
| `occurred_at` | `DateTimeField(db_index=True)` |
| `recorded_at` | `DateTimeField(auto_now_add=True)` |
| `window_days` | `PositiveSmallIntegerField` |
| `first_touch` | nullable FK to `AttributionTouch`, `on_delete=RESTRICT`, `related_name="conversions_as_first"` |
| `last_touch` | nullable FK to `AttributionTouch`, `on_delete=RESTRICT`, `related_name="conversions_as_last"` |
| `first_referral_code`, `last_referral_code` | `CharField(blank=True)` |

- Meta constraint: unique on `(site, kind, content_type, object_id)`.
- Meta indexes: `(content_type, object_id)`, `(site, kind, occurred_at)`, `(site, recorded_at)`.
- Meta ordering: `["-occurred_at"]`.
- `RESTRICT` is deliberate. Deleting a user cascades to both touches and conversions, and `PROTECT` would block account erasure.

### Index answer

There is no index on `(site, recorded_at, id)`. The only one is `(site, recorded_at)` on each model, and the model comment calls it "a cursor for a changed-since conversions feed". The paginator orders by `(recorded_at, "id")` with a `recorded_at__gte` range, so the `(site, recorded_at)` index gives the same range start that `(site, hit_at)` gives child 3. The `id` tie-break only sorts rows that tie. Child 3 shipped with no migration on the same reasoning (its Decisions table). Adding `id` to the index is optional, and the spec has to decide. Child 3 sets the precedent for no migration.

Also, `Conversion` has no index with `user`, and `AttributionTouch` has `(site, user, occurred_at)` and `(site, referral_code)`. A `user` filter on touches is covered by `(site, user, occurred_at)`. On conversions it is not indexed. `first_referral_code` and `last_referral_code` are not indexed on `Conversion`. `(site, recorded_at)` bounds the scan when `updated_since` is given, and the filters run inside it. The `referral_code` OR across two columns can use no single index.

### Mismatches between idea and shipped code

1. **The idea's field lists match the shipped fields.** Touch: `id`, `user`, `advert_code`, `referral_code`, five `utm_*`, `landing_path`, `occurred_at`, `recorded_at`, `recorded_via`. Conversion: `id`, `user`, `kind`, `target_label`, `occurred_at`, `recorded_at`, `window_days`, `first_touch`, `last_touch`, `first_referral_code`, `last_referral_code`. No mismatch found. `key_hash` is on the touch model and must be left out explicitly. `content_type` and `object_id` are on the conversion and must be left out.
2. **The unique constraint on touches is `(site, user, occurred_at, key_hash)`.** The row id, not any natural key, is the upsert key for a script.
3. **`first_touch` and `last_touch` are nullable.** A conversion with no codes in play has them `null`, so the API returns `null` for the ids. A touch can be deleted only when no conversion rests on it (`RESTRICT`), so an id a script reads from a conversion always resolves in the touches list, unless the pruning command or user deletion removes both together.
4. **Touches cascade with the user, and conversions cascade with the user.** Deleting a user removes both rows. A deleted-user row disappears from the API with no deletion feed (out of scope in the idea). This is the same "invisible" case as `signup-attributions` in the `docs/api.md` Deletions table.
5. **The model comment on `(site, recorded_at)` says "a cursor for a changed-since conversions feed".** It was added in anticipation of this child. The index is on `AttributionTouch` and `Conversion` both.
6. **`recorded_at` is `auto_now_add`.** It is stamped in Python at `save()` before the transaction commits, so a row can commit later with an earlier `recorded_at`. The 5-minute margin recipe in `docs/api.md` ("Both are stamped before the write commits") applies unchanged. The idea's claim "a script that follows pages and remembers its last `recorded_at` misses nothing" holds only with that margin, so the spec should word the recipe like the hits one.
7. **Touch `ordering = ["-occurred_at", "-recorded_at"]` and conversion `ordering = ["-occurred_at"]` are model defaults.** The paginator overrides with `order_by(cursor_field, "id")`, so there is no conflict. Detail routes are unaffected.

## 2. API machinery: `freedom_ls/api/`

- `viewsets.py`: `ReadOnlyApiViewSet(ApiResponseMixin, ReadOnlyModelViewSet)`.
  - Attributes: `required_scope: ApiScope`, `cursor_field: str = DEFAULT_CURSOR_FIELD` (`"updated_at"`), `authentication_classes=[ApiKeyAuthentication]`, `permission_classes=[HasApiScope]`, `throttle_classes=[ApiKeyRateThrottle]`, `renderer_classes=[JSONRenderer]`, `pagination_class=ApiKeysetPagination`, `filter_backends=[DjangoFilterBackend]`, `metadata_class=ApiMetadata`, `http_method_names=["get","head","options"]`, `schema=AutoSchema()`.
  - `filter_queryset` runs `site_queryset`, which filters `site_id=api_key.site_id` and returns `none()` for schema generation or no key. A viewset only needs `queryset = Model._base_manager...`.
  - Responses get `Cache-Control: private, no-store`.
- `pagination.py`: `ApiKeysetPagination`.
  - Reads `view.cursor_field`, orders by `(cursor_field, "id")`, and filters with `field__gte` AND (`field__gt` OR (`field`==value AND `pk__gt`)). The leading `__gte` lets the `(site, field)` index start at the cursor.
  - **Mismatch with the child 3 spec.** The shipped cursor is `[cursor_field_name, value.isoformat(), str(pk)]` (three strings, base64), not the two-element form the child 3 spec described. The field name ties a cursor to its endpoint, so a cursor from another endpoint is a 400. A cursor must round-trip the exact isoformat (`_exactly`), and a naive datetime is rejected. Both new resources page on `recorded_at`, a non-null `DateTimeField`, which is supported with no change to pagination.
  - `cursor_field_problem()` and `_cursor_parser()` back system check `freedom_ls_api.E002` (`freedom_ls/api/checks.py`). `recorded_at` passes (non-null `DateTimeField`).
  - Page size: `config.API_PAGE_SIZE` (100) and `config.API_MAX_PAGE_SIZE` (500), from `freedom_ls/api/config.py`.
- `filters.py`: `AwareIsoDateTimeField` and `AwareIsoDateTimeFilter` (rejects naive datetimes with a 400), `IsoDateField` and `IsoDateFilter`, and `UpdatedSinceFilterSet`.
  - `UpdatedSinceFilterSet.updated_since` is hard-wired to `field_name="updated_at"`, `gte`. It is not usable here, since neither new model has `updated_at`. Child 3 redeclared `updated_since` on a plain `django_filters.FilterSet` with `AwareIsoDateTimeFilter(field_name=..., lookup_expr="gte", help_text=...)` in `freedom_ls/referral_tracking/api.py`. Two filtersets now need the same `recorded_at` declaration (touch and conversion), so a shared filterset base within `referral_tracking/api.py` is the alternative to copying it. The CLAUDE.md rule against repeated code points to extracting it. The spec should say which.
- `scopes.py`: `ApiScope.REFERRAL_DATA = "referral_data"`. `_DESCRIPTIONS[REFERRAL_DATA]` is `"ReferralCode, ReferralCodeHit, SignupAttribution, FirstTouchCount"`. It needs `AttributionTouch, Conversion` added, and `docs/api.md` line 54 (the scope table) must match it. A test in `freedom_ls/api/tests/test_scopes.py` may pin the string, so check it.
- `routers.py`: `router` is the shared router that `api.py` modules call `router.register(prefix, ViewSet, basename=...)` on. `freedom_ls/referral_tracking/api.py` registers `referral-codes`, `referral-code-hits`, `signup-attributions` and `first-touch-counts`. Basenames are snake_case singular, so the new ones would be `attribution-touches` / `attribution_touch` and `conversions` / `conversion`. The `api.py` module is already discovered for `referral_tracking`, so no autodiscovery change is expected. Confirm in `freedom_ls/api/apps.py` and `urls.py`.
- `throttling.py`: `ApiKeyRateThrottle`, per key, inherited by the base viewset. `schema.py`: drf-spectacular. `freedom_ls/api/tests/test_schema.py` runs `spectacular --validate --fail-on-warn`. New filters need `help_text`, and the serializer fields need types spectacular can resolve (the `first_touch` and `last_touch` FKs as UUID or null, and `user` as an integer).
- Other API modules for convention: `freedom_ls/accounts/api.py` (template), `course_applications/api.py`, `learner_management/api.py`, `learner_progress/api.py`, `course_interest/api.py`. **No existing endpoint offers a filter on user, on a code or on a kind.** Only `updated_since`, `day_since`, `cursor` and `page_size` exist today. These filters would be a first, and no precedent exists for naming a user filter. Plain `django_filters.NumberFilter` or `ModelChoiceFilter`/`UUIDFilter` choices are open. The user pk is an integer (see the `SignupAttribution` docs row: "user: integer").

## 3. Existing referral resources: `freedom_ls/referral_tracking/api.py`

- Serializers are `ModelSerializer` with an explicit `fields` tuple and `read_only_fields = fields`. They carry no `*_email` field except `SignupAttributionApiSerializer.user_email` (`source="user.email"`, with `select_related("user")` on the viewset).
- **Answer to the open question about returning email beside the user id.** Child 3's signup attributions return `user` (integer id) plus `user_email`. Hits return `referral_code` (UUID) plus `referral_code_text`. The established pattern is id plus a readable sibling. For touches and conversions the idea's field list says "the user's id". The spec has to decide whether to add `user_email`. It would add a `select_related("user")` and extend the personal-data statement in `security-and-data-handling.md` (the email already reaches a `referral_data` key via signup attributions, so no new exposure class).
- `ReferralCodeHitFilterSet` and `SignupAttributionFilterSet` each define `updated_since` on their timestamp, with `Meta.model` and `fields: list[str] = []`.
- Queryset convention: `Model._base_manager.select_related(...)`.
- A viewset with a nullable FK in the serializer (`first_touch`, `last_touch`) renders `null` as plain `ModelSerializer` FK fields do (the pk value, or `None`).
- Tests: `freedom_ls/referral_tracking/tests/test_api.py` (about 700 lines). Fixtures `api_key(mock_site_context)`, `auth(api_key)` and `client()`. A `TestSharedResourceBehaviour` class is parametrised over resources (line 141) for shared checks, which the new two resources join. Other tests cover 1,500 rows sharing one timestamp paged at maximum page size, order across pages, `updated_since` inclusive bound and naive datetime 400, `next` link keeps filters, and query-count bounds via `select_related`. `_cursor()` helper builds cursors. Factories: `AttributionTouchFactory` and `ConversionFactory` already exist in `freedom_ls/referral_tracking/factories.py` (lines 74 and 101). `ConversionFactory` defaults the target to the owning user, and has no `first_touch` or `last_touch` default, so those are `null` unless the test sets them.
- Shared tests: `freedom_ls/api/tests/` (`test_pagination.py`, `test_filters.py`, `test_scopes.py`, `test_schema.py`, `test_viewsets.py`, `test_routers.py`, `test_throttling.py`, `test_permissions.py`, `invariants/test_api_docs.py`). The `api` import contract keeps them away from models with a `DateField`, so referral-specific tests live in the `referral_tracking` tests.

## 4. Admin, resources and "code in play"

- `freedom_ls/referral_tracking/admin.py` line 113: `CodeInPlayFilter(TextFilter)`, `parameter_name = "code_in_play"`, `Q(first_referral_code__iexact=code) | Q(last_referral_code__iexact=code)`. **Case-insensitive.** The answers.md says `referral_code` on conversions "matches either the first or the last code, as the admin's 'code in play' filter does", and `first_referral_code` and `last_referral_code` "each match their own code exactly". Open question for the spec: does "exactly" mean case-sensitive? `ReferralCode.code` is unique ignoring case (`Lower("code")` constraint), and the `/go/` door lowercases and the `/d/` door uses uppercase print codes, so stored touch and conversion codes may differ only in case. The spec must say whether the three filters are `exact` or `iexact`. This is the biggest design hazard in the filter set. Note the touch's `(site, referral_code)` index serves `exact` but not `iexact`.
- `freedom_ls/referral_tracking/resources.py`: `AttributionTouchResource` (no `fields`, so it exports every column including `key_hash`) and `ConversionResource` (fields `id, user (email), kind, target_label, occurred_at, first_referral_code, first_touch__occurred_at, last_referral_code, last_touch__occurred_at, window_days`; no `recorded_at`). The export uses the user's email in the `user` column. The API unchanged: do not reuse these resources (child 3 decision "no export resource or widget is reused"). The admin export omits `recorded_at`, `first_touch`/`last_touch` ids and `recorded_via` on conversions. The idea's API field list is therefore richer than the export, by design.
- Admin exports are out of scope and stay unchanged.

## 5. Dependency map

- `docs/app_structure.md` line 234 already shows `referral_tracking --> api`. `test_organisation/import_contracts.toml` already allows it (child 3 did this). Adding two viewsets to the existing `freedom_ls/referral_tracking/api.py` needs no map change, and no new import edge. Confirm that a regenerate with `ds:app_map` produces no diff.
- The idea's "project where `referral-attribution-over-time` is not installed" question is moot in this codebase: the models are in `freedom_ls/referral_tracking/models.py` (migrations `0005_attributiontouch.py`, `0006_conversion.py`) in the same app as the other referral resources. The endpoints are always registered with the app, and an empty site returns `{"next": null, "results": []}`. There is no optional installation case to handle.

## 6. Docs

### `docs/api.md` (about 1,047 lines)

Sections to touch:

- Lines 3-17 intro list. Add the two resources to the referral bullet.
- Line 48-55 API scopes table. `referral_data` row.
- Lines 166-177 incremental syncs table. Add rows for `attribution-touches` and `conversions`: ordering field `recorded_at`, `updated_since` on `recorded_at`, Checkpoint.
- Lines 187-190 Checkpoint text lists which endpoints use `hit_at` / `signed_up_at`, with the sentence about the 5-minute margin because they are stamped before the write commits. This needs `recorded_at` added.
- Lines 232-243 Deletions table. Add rows. Touches and conversions go when their user is deleted. Touches may also be removed by the retention/prune command (the idea puts the prune command out of scope, so the doc should say it happens). Verify the retention setting name in `docs/product/signup-attribution.md` before wording it.
- Lines 251-330 "Example: checkpoint sync" (Python, httpx). The `PATHS` dict (line 274) maps path to filter field. **Adding `"attribution-touches": "recorded_at"` and `"conversions": "recorded_at"` is the whole code change to the example.** The `upsert` function special-cases `course-applications`. The loop is generic, and the `datetime.fromisoformat(row[field])` call works with ISO 8601 `recorded_at`. The `FLS_CHECKPOINT_*` naming follows the path. The prose at line 257-258 about scopes already names `referral_data`.
- Lines 875-1046. "Referral data" intro says "Four API endpoints"; it needs "Six", plus a note about `referral_code` meaning on the new endpoints (text captured at the landing, as on signup attributions). New sections go before "Known data caveats", which is a subsection of "First-touch counts" at the end of the file, so placing the new sections requires moving or keeping that heading in mind. Section layout: a header table (API scope, List, Detail, Ordering field, Filters, Recipe), `### Fields` table, notes.
- Line 1045-1046 caveat "No conversion uploads" says the data cannot feed a Google or Meta conversion upload. It remains true. The word "conversion" is overloaded with the `Conversion` model here, and a short wording check is worth it.
- `freedom_ls/api/tests/invariants/test_api_docs.py` compiles the python fences, so the edited example must still compile.

### `docs/product/security-and-data-handling.md` (last updated 2026-11-13, line 3)

- Line 22: the "Built" bullet for the API lists referral codes, link visits, signup attributions and first-touch counts. It needs touches and conversions.
- Line 120: the **Referral data** paragraph in "API Access (built)". It needs the two new resources: they return the user's id (and an email if the spec adds it), codes, campaign parameters, `landing_path` and times. They return no IP, user agent, referer, raw query, click id or cookie id. Also `landing_path` is stored as sent and may carry personal data.
- **Line 140 is now wrong once this ships.** It says of attribution touches and conversions "neither is readable through the API". It must change to say they are readable through `referral_data`, and the cross-reference to `signup-attribution.md` for retention stays.
- Line 139 (Signup attribution bullet) points to the API and is unaffected.
- Bump `_Last updated:_` to the ship date.

### Other docs

- `docs/product/signup-attribution.md` lines 47 and 51 mention touches and conversions and retention. Each "Omitted long matching line" is long. The spec author should read them for any "not available through the API" claim. Child 3 also updated `docs/product/referral-codes.md` and `docs/product/signup-attribution.md`, so the same two pages are likely to need a pointer here.
- `docs/product/configuration-and-extension.md` line 165 documents `REFERRAL_TRACKING_ATTRIBUTION_WINDOW_DAYS` (90). `window_days` in the API is the value stored on the row when the conversion was resolved, not the current setting.

## 7. Cross-cutting points for the spec

1. Paging key `recorded_at` needs no pagination change. `freedom_ls_api.E002` passes. `cursor_field = "recorded_at"` goes on both viewsets.
2. `updated_since` must be redeclared on `recorded_at` (the shared `UpdatedSinceFilterSet` is fixed to `updated_at`), either twice or via one small shared base within `referral_tracking/api.py`.
3. A `referral_code` filter on touches is a column match on `AttributionTouch.referral_code`. On conversions it is the OR of two columns (admin parity, `iexact` in the admin). The case-sensitivity of all five code filters, and what an empty value means (`?referral_code=` for "no code in play"), are open. `django_filters` treats an empty string value as "no filter" by default, so the idea's "both codes blank is a recorded answer" cannot be queried with a plain empty filter value.
4. `user` filter: no precedent. The user's pk type is integer.
5. `kind` filter should be a `ChoiceFilter` on `ConversionKind`, so an unknown value is a 400, and OpenAPI lists the choices. Check how `django_filters` plus `drf_spectacular` render choices, with `--fail-on-warn`.
6. Query counts: the conversion list needs no `select_related` if `first_touch` and `last_touch` return ids only (`first_touch_id` is a local column, and the serializer's PK-related field reads `first_touch_id` without a query via `use_pk_only_optimization`, which DRF applies to `PrimaryKeyRelatedField` on `ModelSerializer`). Verify with a query-count test as child 3 did. If a user email is added, `select_related("user")` is required.
7. Detail routes: both resources get list and detail like every other resource (the idea says "lists" only, so confirm detail is wanted).
8. The `AttributionTouch` and `Conversion` models have `RESTRICT` and `CASCADE` behaviour that affects docs on deletions only, not code.
9. Prior art for vocabulary: use "API endpoint", "API scope", "ordering field", "Checkpoint" as `docs/api.md` does.

## References

All local. No web sources were used.

status: ok · reason: complete
