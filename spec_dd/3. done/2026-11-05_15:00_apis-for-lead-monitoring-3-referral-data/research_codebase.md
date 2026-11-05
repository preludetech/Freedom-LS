# Research: codebase (what the referral-data API touches, reuses, conflicts with)

All paths relative to the repo root. Facts read from the working tree on branch
`apis-for-lead-monitoring-3-referral-data` (child 1 is merged here).

## 0. Headline findings

1. **Child 1's pagination and filter are hardwired to `updated_at`.** `ApiKeysetPagination.ordering = ("updated_at", "id")`, the cursor encodes `last.updated_at`, the type bound is `TimestampedModel`, and `UpdatedSinceFilterSet` has the single field `updated_since -> updated_at__gte`. None of the four referral models has `updated_at`. This spec cannot "follow child 1 unchanged" for ordering/cursor/filter: the shared classes need a per-viewset ordering field (and a way to declare the changed-since field), or this spec needs its own subclasses. This is the main conflict. Specs 4 and 5 add `updated_at`, so they do not hit it; spec 2 does not either. Spec 3 is the only child in 2-5 that does (and 6 will).
2. **`FirstTouchCount.day` is a `DateField`**, and the current cursor code cannot carry it (see 3.4).
3. **`referral_data` is already an `ApiScope`** (`ApiScope.REFERRAL_DATA = "referral_data"`), but its description string omits `FirstTouchCount` (see 3.1, 6).
4. Serializers and viewsets live in the **domain app's `api.py`** (not in `freedom_ls/api/`), so this spec adds `freedom_ls/referral_tracking/api.py`. `referral_tracking -> api` is a new dependency edge.
5. No sibling spec (2, 4, 5) has a spec yet; only `idea.md` + `todo.md` exist. No conventions are decided there beyond what child 1 set.

## 1. How child 1 built the API

Done spec dir: `spec_dd/3. done/2026-11-03_09:54_apis-for-lead-monitoring-1-foundation-and-users/` (`1. spec.md`, `2. plan.md`, `upgrade_notes.md`, `todo.md`). `todo.md` there has no open item that defers work to later children (remaining unticked items are PR/merge/user steps). `grep TODO|@claude` in `freedom_ls/api/` finds nothing. The only forward-looking text is spec line 45: "Each API endpoint lives in the app that owns its model, in `<app>/api.py`, and registers with the router in `freedom_ls.api`. Specs 2 to 6 follow this."

### 1.1 Registration pattern

`freedom_ls/api/routers.py`: `ApiRouter(SimpleRouter)` with two routes only (list `^{prefix}{trailing_slash}$`, detail `^{prefix}/{lookup}{trailing_slash}$`), route names `{basename}_list` / `{basename}_detail`; module-level `router = ApiRouter()`.

`freedom_ls/api/urls.py`: `app_name = "api"`; `autodiscover_modules("api")` imports every installed app's `api.py` (so `api` has no static import of endpoint apps); `urlpatterns = [*router.urls, path("schema/", ApiSchemaView.as_view(), name="schema")]`. Root: `config/urls.py` includes `freedom_ls.api.urls` at `api/v1/` guarded by `apps.is_installed("freedom_ls.api")`.

Registered so far: only `router.register("users", UserApiViewSet, basename="user")` in `freedom_ls/accounts/api.py`. URL names `api:user_list`, `api:user_detail`. New resources: `referral-codes` / `referral_code`, `referral-code-hits` / `referral_code_hit`, `signup-attributions` / `signup_attribution`, `first-touch-counts` / `first_touch_count` (prefix is the kebab-case URL path; basename is snake_case singular, yielding `api:referral_code_list` etc.).

System check `freedom_ls_api.E001` (`freedom_ls/api/checks.py`, `viewsets_without_scope`) errors for any registered viewset whose `required_scope` is not an `ApiScope` instance.

### 1.2 The code shape to follow (`freedom_ls/accounts/api.py`, complete)

```python
class UserApiSerializer(serializers.ModelSerializer):
    email_verified = serializers.BooleanField(read_only=True)   # an annotation
    class Meta:
        model = User
        fields = (*USER_EXPORT_FIELDS, "updated_at")
        read_only_fields = fields

class UserFilterSet(UpdatedSinceFilterSet):
    class Meta:
        model = User
        fields: list[str] = []

class UserApiViewSet(ReadOnlyApiViewSet):
    filterset_class = UserFilterSet
    required_scope = ApiScope.USERS
    serializer_class = UserApiSerializer

    def get_queryset(self) -> QuerySet[User]:
        # The base manager crosses sites; the base viewset's filter_queryset
        # narrows every lookup to the key's site.
        return annotate_email_verified(User._base_manager.all())

router.register("users", UserApiViewSet, basename="user")
```

Imports used: `freedom_ls.api.filters.UpdatedSinceFilterSet`, `freedom_ls.api.routers.router`, `freedom_ls.api.scopes.ApiScope`, `freedom_ls.api.viewsets.ReadOnlyApiViewSet`. Field list reuses the admin export's list (`USER_EXPORT_FIELDS` from `accounts/resources.py`) plus `updated_at`; `read_only_fields = fields`.

### 1.3 Base viewset (`freedom_ls/api/viewsets.py`)

`ReadOnlyApiViewSet(ApiResponseMixin, ReadOnlyModelViewSet)`:
- `required_scope: ApiScope` (annotation only, subclass must set).
- `authentication_classes = [ApiKeyAuthentication]`, `permission_classes = [HasApiScope]`, `throttle_classes = [ApiKeyRateThrottle]`, `renderer_classes = [JSONRenderer]`, `pagination_class = ApiKeysetPagination`, `filter_backends = [DjangoFilterBackend]`, `metadata_class = ApiMetadata`, `http_method_names = ["get","head","options"]`, `schema = AutoSchema()`.
- `ApiResponseMixin`: `api_exception_handler` for `{detail, code}` errors; `finalize_response` sets `Cache-Control: private, no-store`.
- Site binding: `filter_queryset` calls `self.site_queryset(queryset)` first, then `super().filter_queryset`. `site_queryset` returns `queryset.none()` when `swagger_fake_view` or `request.auth` is not an `ApiKey`, else `queryset.filter(site_id=api_key.site_id)`. So a viewset's `get_queryset` may use the default (host-filtered) manager or `_base_manager`; accounts uses `_base_manager` because `User` has no site-filtered manager. All four referral models extend `SiteAwareModel` (`objects = SiteAwareManager()`, filters by the thread-local request site when present). `get_queryset` for referral models should use `Model._base_manager` (as the accounts precedent and `prune_referral_code_hits` do) so correctness never depends on thread-local state; `site_queryset` then does the binding.
- Detail lookup: default `lookup_field = "pk"`; referral PKs are UUIDs (`SiteAwareModel.id = UUIDField(primary_key=True, default=uuid.uuid4)`), so detail URLs take a UUID path segment (router lookup regex default is `[^/.]+`). `User` pk is an int, so UUID detail is not yet exercised by any test.

### 1.4 Scopes (`freedom_ls/api/scopes.py`)

`ApiScope(models.TextChoices)`: `USERS="users"`, `COURSE_APPLICATIONS="course_applications"`, **`REFERRAL_DATA="referral_data"`**, `REGISTRATIONS_AND_PROGRESS="registrations_and_progress"`. `ApiScope.description` property reads `_DESCRIPTIONS`; `REFERRAL_DATA` maps to the string `"ReferralCode, ReferralCodeHit, SignupAttribution"` (no `FirstTouchCount`). That string is used in admin help text and mirrored in the `docs/api.md` scope table and spec 1's text. The idea says the scope covers four resources, so this string and the docs row need `FirstTouchCount` added. (`freedom_ls/api/tests/test_scopes.py` exists; check whether it pins the description.)

`HasApiScope` (`freedom_ls/api/permissions.py`) reads `view.required_scope`; 403 body names the scope: `"This API key does not have the referral_data API scope."` style, as `accounts/tests/test_api.py` pins `"This API key does not have the users API scope."` (value, not label). The existing accounts test already uses `ApiScope.REFERRAL_DATA` as the "wrong scope" key.

### 1.5 Pagination (`freedom_ls/api/pagination.py`) and page size

`ApiKeysetPagination(BasePagination)`; class attr `ordering = ("updated_at", "id")`; `cursor_query_param = "cursor"`, `page_size_query_param = "page_size"`. `paginate_queryset`: `queryset.order_by(*self.ordering)`; filters `Q(updated_at__gt=ts) | Q(updated_at=ts, pk__gt=last_pk)`; fetches `page_size + 1` rows to compute `has_next`. Envelope `{"next": url|null, "results": [...]}`; `next` built with `replace_query_param` on `request.build_absolute_uri()` so other params survive. Page size: `config.API_PAGE_SIZE` default 100, `config.API_MAX_PAGE_SIZE` default 500 (`freedom_ls/api/config.py`, `AppSettings`), clamp via `min(requested, MAX)`; non-integer or `<1` is 400 `{"page_size": [...]}`. Cursor: `urlsafe_b64encode(json.dumps([updated_at.isoformat(), str(pk)]))`, max length 512, decoded with `datetime.fromisoformat` and **rejected if naive**; pk via `model._meta.pk.to_python`. Bad cursor is 400 `{"cursor": ["The cursor is not one this API issued."]}`. `get_schema_operation_parameters` documents `cursor` and `page_size`.

Hardwired points that this spec must change or work around:
- `ordering` and the two literal `updated_at` references in `paginate_queryset`, `last.updated_at` in `_next_link`, `_encode_cursor(updated_at, pk)`.
- `M = TypeVar("M", bound=TimestampedModel)` (also `paginate_all` in `freedom_ls/api/tests/helpers.py`).
- `_decode_cursor` rejects a naive datetime; `datetime.fromisoformat("2026-11-03")` (what a `date.isoformat()` cursor would decode to on Python 3.11+) is a naive midnight, so a `DateField` cursor round-trips only if the date case is handled explicitly (e.g. encode/parse as `date`, or convert to an aware midnight), and the comparison must be `day__gt=<date>`, not a datetime.
- The page-size cap and default are global settings; not changeable per viewset without a new hook.
- Python 3.13 and `from __future__ import annotations` are used throughout; PEP 695 generics (`def paginate_all[M: TimestampedModel]`) appear in test helpers.

### 1.6 Changed-since filter (`freedom_ls/api/filters.py`)

- Param name `updated_since`, single field declared on the base class: `UpdatedSinceFilterSet(django_filters.FilterSet)` with `updated_since = AwareIsoDateTimeFilter(field_name="updated_at", lookup_expr="gte")`. Inclusive (`gte`).
- Per viewset: subclass with `Meta: model = X; fields: list[str] = []`, set `filterset_class` on the viewset. The field name is fixed in the base class by `field_name="updated_at"`; it cannot be repointed per viewset without redeclaring the filter in a subclass or generalising the base.
- `AwareIsoDateTimeField.to_python`: parses with `parse_datetime`, rejects naive values (error code `naive`, "Give the time with a timezone offset or Z.") and unparseable ones (`invalid`). Both give 400 keyed `updated_since`.
- **DateField: not supported.** `AwareIsoDateTimeFilter` is datetime-only. For `first-touch-counts` a date filter is needed (django-filter `IsoDateTimeFilter` does not parse a bare date; `django_filters.DateFilter` would). The idea leaves the name open (open question 2): options are reusing `updated_since` (misleading: `day` is not an update stamp), `since`, `day_since`, or `day_gte`/`day_from`. `docs/api.md` currently says every list endpoint "pages and filters the same way" and documents only `updated_since`; the 400 row in the errors table gives `{"updated_since": ["..."]}` as the example.
- Existing tests to mirror: `freedom_ls/api/tests/test_filters.py` (boundary inclusive, boundary exclusive, naive/unparseable rejected) uses a local `ApiKeyFilterSet(UpdatedSinceFilterSet)` over `ApiKey._base_manager`.

### 1.7 Ordering

Fixed ascending `(updated_at, id)` via the paginator. Views do not need their own `ordering`; `ReadOnlyApiViewSet` has no `OrderingFilter`. Model `Meta.ordering` is overridden by the paginator's `order_by` (existing `ordering = ["-created_at"]` on `ReferralCode` and `["-signed_up_at"]` on `SignupAttribution` are descending, so they are irrelevant but must not be relied on). `id` as tie-break is a UUID; sort order of UUIDs is deterministic in Postgres, so keyset ties work, as `pk__gt` on a UUID works with the converted `to_python`.

### 1.8 Throttling, auth, OpenAPI, caching

- `ApiKeyRateThrottle(SimpleRateThrottle)` (`freedom_ls/api/throttling.py`): rate from `API_THROTTLE_RATE` (default `"600/min"`), key per API key, counts in the `default` cache. Inherited via the base viewset; nothing to add.
- `ApiKeyAuthentication` (`authentication.py`): Bearer only, site check against host, `request.auth` is the `ApiKey`.
- OpenAPI: drf-spectacular `AutoSchema()` on the base; `freedom_ls/api/schema.py` registers the `ApiKeyAuth` http bearer scheme; `GET /api/v1/schema/` needs any active key. New serializers are picked up automatically. Serializer method fields or a nested `SerializerMethodField` need `extend_schema_field` hints or the schema generator warns. `ApiMetadata` returns `{"name": "<View Name>"}` for OPTIONS only.
- Cache-Control `private, no-store` on every response.

### 1.9 Docs page and Python example

`docs/api.md`: sections "Before you start", "API keys" (incl. scopes table with the `referral_data` row listing three models and the sentence "Only `users` has an API endpoint so far. The others are reserved..."), "Making requests", "Errors", "Rate limit", "Schema", "Syncing data" (Pages: "Rows come in ascending `(updated_at, id)` order"; Incremental syncs with `updated_since` incl. the 5-minute margin; Deletions; Example: one httpx `sync_users` script), "Versioning", "Users" (endpoint table: API scope / List / Detail / Filters; Fields table; "What moves `updated_at`"). The intro says "Today there is one: [users](#users)."

Statements that become wrong or incomplete when this spec lands: intro "Today there is one"; "Only `users` has an API endpoint so far"; "Rows come in ascending `(updated_at, id)` order" and "Paging is by position... rows that share one `updated_at`"; "Every list API endpoint pages and filters the same way ... `updated_since`"; "Checkpoint at the largest `updated_at` you saw, minus 5 minutes"; "A deleted row stops appearing ... periodic full pull" (hits can be pruned and codes are never deleted); the Python example is users-only. Each new resource section copies the Users layout (header table, Fields table, notes). A test (`freedom_ls/api/tests/invariants/test_api_docs.py`, mark `fls_internal`) extracts every ```` ```python ```` fence in `docs/api.md` and `compile()`s it, so any added example must compile.

### 1.10 Test fixtures and helpers

- `freedom_ls/api/factories.py`: `ApiKeyFactory` (accepts `scopes=[...]`; `.issued_key` gives the plaintext key; goes through the model's issue path). Used as `ApiKeyFactory(scopes=[ApiScope.REFERRAL_DATA])`.
- `freedom_ls/api/tests/helpers.py`: `api_route_names()`, `collect_pages(client, url, headers)` (follows `next` until null, returns list of bodies), `paginate_all(queryset, path)` (bound to `TimestampedModel`, needs generalising for non-timestamped models).
- `freedom_ls/api/tests/conftest.py`: autouse `_clear_cache` fixture (throttle counts) applies only inside `freedom_ls/api/tests/`. Endpoint tests in another app (`freedom_ls/accounts/tests/test_api.py` precedent) define their own `clean_cache` fixture where they test throttling.
- Fixtures used in `accounts/tests/test_api.py`: `mock_site_context` (project-level conftest), `api_key` (`ApiKeyFactory()` under `mock_site_context`), `auth` (a Bearer header built from the key's `issued_key`), `client` (`rest_framework.test.APIClient`), `site_context(SiteFactory(...))` from `freedom_ls.tests.site_context` for a second site. `ApiKeyFactory()` defaults must include the `users` scope only or all scopes; check `freedom_ls/api/factories.py` before relying on defaults (accounts test builds a `referral_data`-only key for the refusal case, so the default must include `users`; the referral tests need to pass `scopes=[ApiScope.REFERRAL_DATA]` or rely on an all-scopes default).
- The accounts API test file is the template: exact-field-set test, cross-site absence + 404, detail, pages followed, wrong-scope 403 body, no key 401 + `WWW-Authenticate`, session-only 401, bad key 401, method 405 JSON, unknown id 404 JSON (`"No User matches the given query."`, so a UUID miss for referral models gives `"No ReferralCode matches..."`), HEAD, OPTIONS (`{"name": "User Api List"}`), a query-count bound (`django_assert_max_num_queries(8)` for 20 rows), a 1500-rows-sharing-one-timestamp paging test (bulk_create then `_base_manager.update(updated_at=...)`), `updated_since` boundary, naive `updated_since` 400, throttle 429.
- Referral factories exist: `freedom_ls/referral_tracking/factories.py` `SignupAttributionFactory` (creates a user via `UserFactory`), `FirstTouchCountFactory` (`day = timezone.localdate()`, `key_hash` computed from key fields via `attribution_key_hash`), `ReferralCodeFactory`, `ReferralCodeHitFactory`. All `SiteAwareFactory`. `hit_at`, `signed_up_at`, `created_at` are `auto_now_add`, so tests set them with `Model._base_manager.filter(pk=...).update(...)` (note `SignupAttribution.save` raises on a second save of an existing row, so `.update()` is the only path; `QuerySet.update` is exempt).

## 2. Sibling specs and branches

`spec_dd/2. in progress/apis-for-lead-monitoring-{2,4,5}-*/` contain only `idea.md` and `todo.md` (no research, no spec). Nothing is decided there beyond:
- 2 (course applications): "Where the serializer and viewset live, following whatever child 1 decides" (so `<app>/api.py`); `updated_since` inclusive; cursor on `(updated_at, id)`.
- 4 (registrations and interest) and 5 (course progress): both add `updated_at` to a model; both flatten learner to user id, email, plus organisation and, in 5, first and last name. Whichever lands second reuses the first's flattening. Spec 5 notes "email and name are exposed" in `security-and-data-handling.md`. Spec 4/5 flatten as **separate fields** (user id, user email; spec 5: first and last name), not a nested object. For consistency spec 3's signup-attribution user should likewise be flat or small; the idea says "the user (id and email)", and open question 3 is whether name is added; nothing in siblings forces either. Field-name choice (e.g. `user_id` / `user_email` vs nested `user: {id, email}`) is **not decided anywhere yet**; spec 3 may be first or second to decide. Existing precedent in this effort for FK ids: none in code (only `User`, no FK field). Roadmap "Decisions already taken" line 718 and "Unknowns" table: serializer location owned by 1 (decided: per domain app); changed-since spelling on `first-touch-counts` owned by 3.
- Roadmap caution (line 677): specs 2-6 each register routes with the router and add a docs section; expect small merge conflicts in `docs/api.md`. Nothing in `freedom_ls/api/*.py` is touched by 2, 4, 5 by design, so spec 3 modifying `pagination.py`/`filters.py` is a shared-file change that other children will then build on; spec 6 (conversions) needs the same non-`updated_at` ordering.
- I could not read other branches' working trees from here; the worktree tree contains only the committed "start the spec" commits for 2, 4 and 5 (git log: `097cee3ce`, `e827ba710`, `ee49918f7`).

## 3. `freedom_ls/referral_tracking/`

### 3.1 Base classes and sites

`SiteAwareModel` (`freedom_ls/site_aware_models/models.py`): `id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`, `site = ForeignKey(Site, on_delete=PROTECT)`, `objects = SiteAwareManager()` (filters `site=<request site>` when a thread-local request exists, else unfiltered). `_base_manager` is the plain manager. `TimestampedModel` (abstract, `created_at` auto_now_add, `updated_at` auto_now) is **not** used by any referral_tracking model. All four models are in `freedom_ls/referral_tracking/models.py`.

### 3.2 Models, every field

`CAPS` dict gives max lengths: advert_code 64, utm_source 64, utm_medium 64, utm_campaign 255, utm_content 128, utm_term 128, gclid 128, gbraid 128, wbraid 128, fbclid 256, landing_path 255, referer 255, raw_query 512, ga_cookie 64, fbp_cookie 64, fbc_cookie 320, user_agent 512, referral_code 64. `ATTRIBUTION_KEY_FIELDS = (advert_code, utm_source, utm_medium, utm_campaign, utm_content, utm_term, referral_code)`.

**ReferralCode**: `code` CharField(64); `label` CharField(200); `notes` TextField(blank); `destination` CharField(512, `validate_site_path`); `inactive_destination` CharField(512, blank, validator); `is_active` Boolean default True; `hit_count` PositiveIntegerField default 0; `last_hit_at` DateTimeField(null, blank); `created_at` DateTimeField(auto_now_add). Constraints: `UniqueConstraint(Lower("code"), "site", name="unique_referral_code_per_site")`. `Meta.ordering = ["-created_at"]`. No explicit index on `created_at` or `(site, created_at)` (table is small; ordering by `(created_at, id)` for a site filter is a seq scan or a sort of a small set, acceptable per the idea). Never deleted (admin `has_delete_permission` False; `ReferralCodeHit.referral_code` is `on_delete=PROTECT`).

**ReferralCodeHit**: `referral_code` FK to ReferralCode (`PROTECT`, `related_name="hits"`, non-null); `door` CharField(2, choices `Door`: `"go"` -> "/go/", `"d"` -> "/d/"); `is_machine_fetch` Boolean (no default); `hit_at` DateTimeField(auto_now_add). Indexes: `(site, hit_at)` (migration 0002, name `freedom_ls__site_id_0b8d40_idx`) and `(hit_at)` alone (migration 0003, for the prune). No `Meta.ordering`. Serializing the code text needs `select_related("referral_code")` (or a `source="referral_code.code"` field with the queryset select_related) to avoid N+1; the project convention requires select_related.

**SignupAttribution**: `user` OneToOneField(AUTH_USER_MODEL, CASCADE, `related_name="signup_attribution"`); then the CharFields (all `blank=True`, no null): `advert_code`, `referral_code` (text, not an FK), `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `landing_path`, `referer`, `raw_query`; `first_seen` DateTimeField (required, no auto); sensitive: `ga_cookie`, `fbp_cookie`, `fbc_cookie`, `client_ip` GenericIPAddressField(null, blank), `user_agent`; `signed_up_at` DateTimeField(auto_now_add). Indexes: `(site, signed_up_at)`, `(site, utm_source)`, `(site, utm_campaign)`. `Meta.ordering = ["-signed_up_at"]`. `save()` raises `ValueError` on an update of an existing row (`_state.adding is False`); append-only (`QuerySet.update()` bypasses). Needs `select_related("user")` for id+email. The user is added to `USER_ERASURE_CASCADE_MODELS` (account erasure deletes the attribution row, so rows can disappear: a deletion not visible to a checkpoint; docs should say attributions go when the user is erased).

**FirstTouchCount**: `day` **DateField**; the attribution key CharFields `advert_code`, `referral_code`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (blank); `is_overflow` Boolean default False; `key_hash` CharField(64); `count` PositiveIntegerField default 0. Constraint: `UniqueConstraint(fields=["site","day","key_hash"], name="unique_first_touch_count")` (its backing index serves `site`+`day` prefix lookups and range scans, so `ORDER BY day, id` with `site=` filter uses it partially; remaining sort is bounded by the daily key cap). Indexes: `(site, utm_source)`, `(site, utm_campaign)`. No `Meta.ordering`. No `updated_at`; rows are mutated in place with `F("count") + 1` (`freedom_ls/referral_tracking/counters.py`: `increment_first_touch`, `create_or_increment_first_touch` with an `IntegrityError` fallback). An overflow row (`is_overflow=True`, `key_hash = attribution_key_hash(OVERFLOW_SENTINEL)`) folds keys past `REFERRAL_TRACKING_FIRST_TOUCH_KEY_CAP` per site and day, so rows per day are bounded. `day` is `timezone.localdate()`-derived in the factory; check `capture.py`/`middleware.py` for which time zone defines "day" before documenting it (not verified here).

### 3.3 Export columns (`freedom_ls/referral_tracking/resources.py`)

All four extend `SiteAwareModelResource` (`freedom_ls/site_aware_models/admin_exports.py`) with `Meta.exclude = ("site",)` inherited-style and **no explicit `fields`**, so each export is every model field except `site`, in model definition order, including `id`. Widgets: ISO 8601 datetimes (`IsoDateTimeWidget`), ISO dates (`IsoDateWidget`, used for `day`), `TRUE`/`FALSE` booleans. Overrides: `SignupAttributionResource.user = Field(attribute="user", widget=ForeignKeyWidget(get_user_model(), "email"))`; `ReferralCodeHitResource.referral_code = Field(attribute="referral_code", widget=ForeignKeyWidget(ReferralCode, "code"))`. So `SignupAttribution` export currently includes `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie`; the API list in the idea matches the export minus those five (and `site`). The idea's field lists equal the model fields minus `site`, so the explicit serializer `fields` tuple can be written literally. Note the export is derived from the model, so a new column added to a model silently appears in the export but not in the API's explicit list; a test that pins the API field set (as `EXPECTED_FIELDS` in accounts) covers that, and a test that the five sensitive fields are absent from the serializer is worth having. Resources are not reusable for the API (no `USER_EXPORT_FIELDS`-style constant exists in this app); accounts defines `USER_EXPORT_FIELDS` in `accounts/resources.py`, a precedent for exporting a field tuple from `resources.py` if a shared list is wanted. Test: `freedom_ls/referral_tracking/tests/test_resources.py`.

### 3.4 Admin (`freedom_ls/referral_tracking/admin.py`)

All four extend `SiteAwareExportModelAdmin` with `resource_classes = [...]`. `SignupAttributionAdmin`, `FirstTouchCountAdmin`, `ReferralCodeHitAdmin`: add/change/delete permissions all False (read-only, `readonly_fields = _readonly_field_names(model)`). `ReferralCodeAdmin`: writable (except `code` after create and the counters), delete forbidden, bulk action `deactivate_referral_codes` using `queryset.update(is_active=False)` (so `is_active` changes in place with no timestamp). Admin access to the API data is governed by Django `view_` permission; the API scope replaces that for keys (see security doc).

### 3.5 `hit_count` and hits

`freedom_ls/referral_tracking/hits.py` line ~129: `ReferralCode.objects.filter(...).update(hit_count=F("hit_count") + 1, last_hit_at=timezone.now())` only for hits not flagged `is_machine_fetch`; the hit row is written for every logged hit (machine fetches included), and a per-address cap (`REFERRAL_TRACKING_HIT_LOG_LIMIT`, default 30 an hour) stops both the log row and the count. The `hit_count` model help_text states the non-reconciliation. `ReferralCodeHit` rows are deleted in batches of 1000 by `prune_referral_code_hits --older-than-days N` (`freedom_ls/referral_tracking/management/commands/prune_referral_code_hits.py`, `djclick`, `_base_manager.filter(hit_at__lt=cutoff).order_by("hit_at")`, across every site, constant `PRUNE_BATCH_SIZE = 1000`). So a script's `hit_at` checkpoint is safe against pruning of older rows (pruning only removes rows older than the cutoff), but `hit_at` is `auto_now_add` taken at insert time inside the request, so a row can commit slightly after a later-timestamped row; the 5-minute margin in `docs/api.md` applies to hits and attributions as well.

### 3.6 Indexes relevant to cursor ordering

| Resource | Order | Existing index | Note |
| --- | --- | --- | --- |
| referral-codes | `(created_at, id)` | none on `created_at` (unique `Lower(code), site`) | Small table, full pull; fine without. |
| referral-code-hits | `(hit_at, id)` | `(site, hit_at)`, `(hit_at)` | Site filter + range on `hit_at` uses `(site, hit_at)`; `id` tie-break sorts equal timestamps only. Largest table; this is the one that matters. |
| signup-attributions | `(signed_up_at, id)` | `(site, signed_up_at)` | Same. |
| first-touch-counts | `(day, id)` | unique `(site, day, key_hash)` | Serves `site`,`day` prefix; no new index needed. |

No migration appears necessary for this spec (child 1 added `accounts_user_site_updated_idx` as the precedent for adding a `(site, updated_at, id)` index; the referral equivalents `(site, hit_at)` and `(site, signed_up_at)` exist, without the trailing `id`).

## 4. Docs that need updating

- `docs/api.md` (see 1.9): intro, scopes table `referral_data` row (add `FirstTouchCount`, drop "Only `users`... so far"), paging/ordering statement, the incremental-sync section (generalise `updated_at`, add re-pull-recent-days rule for first-touch counts and full pull for referral codes), deletions section (hits can be pruned; attributions go with an erased user; codes are never deleted), four new resource sections following the Users layout, and a note that `client_ip`, `user_agent`, `ga_cookie`, `fbp_cookie`, `fbc_cookie` are withheld. Python example must still compile (`test_api_docs.py`).
- `docs/product/security-and-data-handling.md`: the "API Access (built)" section (lines ~110-120). The "What it exposes" paragraph is users-only ("It returns no ... signup attribution"), which becomes wrong once a key with `referral_data` can read signup attributions; it must state which referral fields the API returns and that IP, user agent and cookie ids are withheld, plus that referral codes, hits and first-touch counts hold no personal data and signup attributions carry the user's email. The "Built" summary on line 22 ("serves a site's user data") also needs widening. The "Personal Data Collected" bullet (line 133, signup attribution, includes IP/user agent/cookies) should be cross-referenced to the withheld-in-API note. Bump the "Last updated" line (other docs in `docs/product/` carry one; `referral-codes.md` has `_Last updated: 2026-09-12_`).
- `docs/product/referral-codes.md`: "Reviewing and Exporting" says both the code list and the hit log "export to CSV" and has a "Not Built" list; add that the same data (codes, hits, signup attributions, first-touch counts) is readable through the API, and in the hit-log paragraph that pruned hits disappear from the feed and `hit_count` stays unreconciled. Bump "Last updated". Also see `docs/product/signup-attribution.md` (exists, linked from referral-codes.md; not read here) for an export/API mention.
- `docs/product/authentication.md#api-client-authentication` (linked from security doc; not read) may list the scope-to-data mapping.
- Scope description string in `freedom_ls/api/scopes.py` (`_DESCRIPTIONS[REFERRAL_DATA]`) lacks `FirstTouchCount`.
- `docs/app_structure.md` and `test_organisation/import_contracts.toml`: see 5.
- Per CLAUDE.md the generic plugins stay generic; nothing here goes into `claude_plugins/{ds,sdd,productivity}`. Domain terms (`fls-dev:domain-glossary`) to check before using "referral link" vs "referral code" in user-facing docs: the idea says operators call codes "referral links"; the models and admin say "referral code".

## 5. Dependency direction (`docs/app_structure.md`)

- Dependency table (lines 292-335): `api | base, site_aware_models`; `api_admin | accounts, api, audit_log, site_aware_models`; `accounts | api, base, mail, markdown_rendering, site_aware_models, webhooks` runtime and `icons, organisations, referral_tracking` test-only; `referral_tracking | accounts, base, site_aware_models`, test-only none. Mermaid edges: `accounts --> api`, `api --> base`, `api --> site_aware_models`, `referral_tracking --> accounts/base/site_aware_models`; dotted `accounts -.-> referral_tracking` (test-only).
- Direction: **domain app imports `api`**, never the reverse (`api` discovers `<app>/api.py` through `autodiscover_modules`). `referral_tracking/api.py` would add the edge `referral_tracking --> api`. Does this close a loop? `api` imports `base` and `site_aware_models` only; `referral_tracking` already imports `accounts` (which imports `api`). `accounts -.-> referral_tracking` is test-only, so no runtime cycle. The edge requires regenerating the map (`/ds:app_map`) and `test_organisation/import_contracts.toml` (the import-linter contract file; spec 1 did the same for `accounts --> api`, flagged "for approval").
- Because `api/urls.py` imports every installed app's `api.py` at URL load, `referral_tracking/api.py` must import cleanly even when `freedom_ls.api` is installed but is only imported when the router module is; but if a downstream project installs `referral_tracking` and **not** `freedom_ls.api` (the API is opt-in), `autodiscover_modules` only runs from `api/urls.py` so `referral_tracking/api.py` is never imported and costs nothing; however `djangorestframework` must not be needed at import of `referral_tracking` modules other than `api.py`. Importing `rest_framework` from `api.py` only keeps it so. (Same constraint holds for `accounts/api.py`.)
- `referral_tracking/api.py` needs `freedom_ls.api.{filters,routers,scopes,viewsets}` and, for the user, the `accounts` model via `settings.AUTH_USER_MODEL` or the `user` relation on `SignupAttribution`; no new `accounts` edge.

## 6. Open questions in the idea, and what the code says

1. **Where serializers/viewsets live**: decided by child 1, `freedom_ls/referral_tracking/api.py`, `router.register(...)`. The spec should cite spec 1 line 45.
2. **Changed-since spelling for `first-touch-counts` and whether the name is shared**: the base filter is `updated_since` on `updated_at`, datetime-only and aware-only. A date needs its own filter class (`DateFilter` or a custom field accepting `YYYY-MM-DD`), and the base `field_name` is fixed. Using the same query name `updated_since` on all three but pointing it at `hit_at` / `signed_up_at` / `day` is possible only if the base filterset is generalised (e.g. a factory taking the model field name and a filter class), which also touches `docs/api.md` (it documents `updated_since` as "rows whose `updated_at` is at or after"). That choice is for the spec; both options need a change to shared code or new per-resource filter classes.
3. **User id plus email, or name too**: export carries email only; siblings 4/5 flatten learner to user id, email (+ name in 5). No code constraint. The serializer needs `select_related("user")` either way.
4. **`is_active` filter on referral codes**: purely optional; `ReferralCodeAdmin` already has `list_filter = ["is_active"]`. A filter would be `django_filters.BooleanFilter` in a `FilterSet` whose `Meta.fields = ["is_active"]`; with no filter set, `filterset_class` can be omitted and `DjangoFilterBackend` does nothing (confirm `fields: list[str] = []` FilterSet is not required for a viewset with no filters).

## 7. Things that will break or need touching when generalising child 1's classes

- `freedom_ls/api/pagination.py` (ordering fields, cursor encode/decode for datetime vs date, `TimestampedModel` bound) and its tests `freedom_ls/api/tests/test_pagination.py`; `freedom_ls/api/tests/helpers.py::paginate_all` type bound.
- `freedom_ls/api/filters.py` (`UpdatedSinceFilterSet` field name fixed) and `freedom_ls/api/tests/test_filters.py`.
- `freedom_ls/api/viewsets.py` if the ordering/filter field is declared as a viewset attribute (e.g. `cursor_ordering = ("hit_at", "id")`) read by the paginator through `view`; `paginate_queryset` already receives `view`, so a per-view hook is available without changing the DRF signature (the current code ignores `view`). Tests: `freedom_ls/api/tests/test_viewsets.py` (`StubViewSet`).
- `docs/api.md` statements in 1.9.
- Unverified in this pass: `freedom_ls/api/tests/test_scopes.py` content, `freedom_ls/api/factories.py` default scopes, `docs/product/signup-attribution.md`, `docs/product/authentication.md`, the `site_aware_models` registry that lists `TIMESTAMPED_MODELS` (spec 1 added `ApiKey` to it; referral models stay out by decision), the timezone used for `FirstTouchCount.day` in `capture.py`.

status: ok
