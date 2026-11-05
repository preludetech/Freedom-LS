# Research: codebase (course progress API)

What the `/api/v1/course-progress/` work touches, reuses or conflicts with. Paths are relative to the
repo root. Domain words follow the project vocabulary (CourseProgress, Learner, Organisation).

## 1. Headline findings

1. **Every in-tree writer of `CourseProgress.progress_percentage` uses `save(update_fields=[...])`
   or `QuerySet.update()`. A plain `updated_at = DateTimeField(auto_now=True)` will NOT move on any
   of them.** Django's `auto_now` stamps the in-memory attribute in `pre_save`, but with
   `update_fields` the UPDATE only writes the listed columns. So the field alone does not satisfy the
   idea; every writer below must add `"updated_at"` to `update_fields` (precedent:
   `freedom_ls/learner_management/learner_actions.py:138` does
   `locked.save(update_fields=["is_active", "updated_at"])`).
2. The foundation's user resource has a ready template (`freedom_ls/accounts/api.py`). A new
   resource is one `api.py` module in `learner_progress` plus a model field, migration, docs and tests.
3. `TimestampedModel` cannot be mixed in as-is: it declares `created_at` (auto_now_add), which
   `CourseProgress` already declares itself with the registration-date meaning. An explicit single
   `updated_at` field is the clean route (see section 3).
4. No shared learner-flattening helper exists yet. Child 4 (registrations) has only an idea. The
   first of 4 / 5 to land defines it. Where to put it is a decision for the spec (section 6).

## 2. `CourseProgress` today

`freedom_ls/learner_progress/models.py:106-240`

- Base: `SiteAwareModel` (`freedom_ls/site_aware_models/models.py:166`): UUID pk `id`, `site` FK
  (PROTECT), `objects = SiteAwareManager()` (filters by the thread-local request site only;
  returns everything when there is no request). Not `TimestampedModel`.
- FKs: `learner` -> `Learner` (PROTECT, related `course_progress_records`), `course` -> `Course`
  (PROTECT, related `progress_records`), `learner_registration` -> `LearnerCourseRegistration`
  (null, PROTECT, related `course_progress_records`), `cohort_registration` ->
  `CohortCourseRegistration` (null, PROTECT, same related name), `last_accessed_item` ->
  `ContentCollectionItem` (SET_NULL; out of scope for the API).
- Timestamps/values (lines 134-142): `created_at` = `auto_now_add` = **registration date** (the row is
  minted by the registration; comment at 134-137 forbids reading it as started); `started_at` null,
  stamped once at first content access by the player; `last_accessed_time` null, written by the
  player, deliberately not `auto_now`; `completed_time` null; `progress_percentage`
  `IntegerField(default=0, db_index=True)`.
- Constraints: `one_course_progress_per_learner_registration` (learner_registration, learner);
  `one_course_progress_per_cohort_registration` (cohort_registration, learner, `Deferrable.IMMEDIATE`);
  CheckConstraint `course_progress_has_exactly_one_grant` (exactly one registration FK set). So
  `kind` is derivable from `learner_registration_id is not None`; no ambiguous rows.
- Indexes: `(learner, course)` only. Plus the db_index on `progress_percentage`. **No index on
  `(site, updated_at, id)`.**
- Migrations: `freedom_ls/learner_progress/migrations/0001_initial.py`,
  `0002_course_progress_cohort_constraint_deferrable.py`. App label `freedom_ls_learner_progress`
  (`apps.py:7`). New migration is `0003_...`, dependencies on `0002` (and `freedom_ls_content_engine`/`sites` not needed).
- Admin: `CourseProgressAdmin` at `freedom_ls/learner_progress/admin.py:215`. `auto_now` fields are
  non-editable so `updated_at` will not appear in the form; add to `list_display`/readonly only if the
  spec wants it visible.
- No post_save receiver is registered on `CourseProgress` itself (grep `sender=CourseProgress`
  returns none), so adding `updated_at` triggers no side effects.
- Deletions: hard deletes only via `danger_clear_all_course_progress`
  (`freedom_ls/dev_tools/management/commands/danger_clear_all_course_progress.py:19`) and cascades;
  PROTECT FKs keep registrations undeletable while a record exists. Consistent with "deletions not
  visible".

## 3. `TimestampedModel` and the `updated_at` decision

`freedom_ls/site_aware_models/models.py:173-185`: abstract, `created_at = DateTimeField(auto_now_add=True)`,
`updated_at = DateTimeField(auto_now=True)`. Used by `Cohort`, `Organisation`, `CohortMembership`,
`CourseFormAttempt` (same file as CourseProgress, `models.py:243`), `User` (via composition).

- Mixing it into `CourseProgress` redeclares `created_at`. Django raises `FieldError` ("clashes with
  field from abstract base") only for non-abstract-parent clashes; for abstract parents a child
  field of the same name silently overrides, so it would run but is misleading and the pagination
  type bound (`M = TypeVar(bound=TimestampedModel)`, `freedom_ls/api/pagination.py:27`;
  `freedom_ls/api/tests/helpers.py:32`) would be satisfied only nominally. Cleaner: add one explicit
  `updated_at = models.DateTimeField(auto_now=True)` with a comment that it is the changed-since
  signal and that `last_accessed_time` is not it. Typing note: `ApiKeysetPagination` is typed to
  `TimestampedModel`; the users model satisfies it via the mixin. A `CourseProgress` queryset passed
  in is a typing mismatch at most (runtime reads only `.updated_at`, `.pk`, `_meta.pk`). Decide
  whether to loosen the TypeVar to a protocol or accept it; do not add `# type: ignore` (CLAUDE.md).
- Meaning of the two columns stays split: `created_at` = registration date, `updated_at` = last row
  change (including progress recalculation and player visits, which does move it because the player
  saves `last_accessed_time`).

## 4. Every writer of `CourseProgress` (and what bypasses `auto_now`)

| Writer | Location | Mechanism | Moves plain `auto_now`? |
|---|---|---|---|
| Percentage recalculation (topic complete, form attempt complete) | `freedom_ls/learner_progress/signals.py:53-65` `recalculate_progress_percentage` | `record.save(update_fields=["progress_percentage"])` | **No** |
| Backfill command | `freedom_ls/learner_progress/management/commands/recalculate_progress_percentages.py:62-64` | `cp.save(update_fields=["progress_percentage"])` | **No** |
| Cohort move, no existing record | `signals.py:309-310` | `save(update_fields=["cohort_registration"])` | **No** |
| Cohort move, swap | `signals.py:314-319` | `CourseProgress._base_manager.filter(...).update(cohort_registration=Case(...))` | **No** (bypasses save) |
| Player visit | `freedom_ls/learner_interface/views.py:1555-1568` | `save(update_fields=["last_accessed_item","last_accessed_time","started_at"])` | **No** |
| Course completion | `freedom_ls/learner_interface/views.py:2202-2204` | `save(update_fields=["completed_time"])` | **No** |
| Mint per cohort registration | `freedom_ls/learner_progress/utils.py:123` | `_base_manager.bulk_create(...)` | Yes (`pre_save` runs on insert) |
| Mint, single | `utils.py:91` `ensure_course_progress_record` | `_base_manager.get_or_create` | Yes (insert) |
| Factory / tests | `learner_progress/factories.py` | direct save | Yes |
| QA seed commands | `freedom_ls/qa_helpers/management/commands/*` (e.g. `qa_create_dashboard_paging_fixtures.py:410-424`) | attribute set + `save()`, and one `.update(created_at=...)` | mostly yes; dev data only |
| Dev wipe | `danger_clear_all_course_progress.py` | delete | n/a |

Consequence for the spec: the idea's phrase "recalculation must go through a path that moves
`updated_at`" understates it. The player visit and completion writes (`views.py:1566`, `2204`) also
use `update_fields` and also must change. Options for the spec:

- (a) Add `"updated_at"` to each `update_fields` list (6 call sites, easy to regress; a future
  `save(update_fields=[...])` silently drops it).
- (b) Override `CourseProgress.save()` to append `"updated_at"` to a non-None `update_fields`, so every
  `save()` path is covered by construction. Does not cover `QuerySet.update()`, so `signals.py:314`
  still needs `updated_at=Now()` set explicitly in the `update(...)` call.
- A guard test can pin it: assert `updated_at` advances after each of the writers above. Existing
  tests to extend: `learner_progress/tests/test_signals.py`, `tests/management/commands/test_recalculate_progress_percentages.py`,
  `learner_interface` player tests.
- Precedent for non-`save` paths moving `updated_at` by hand: `freedom_ls/accounts/signals.py:20`
  (`User._base_manager.filter(pk=...).update(updated_at=timezone.now())`) and
  `role_based_permissions/utils.py:345,436,484`. Also note the `accounts/models.py:226` comment about
  guards covering only `.save()`.
- `bulk_update` is not used on `CourseProgress` anywhere in non-test code.
- Because `last_accessed_time`/`started_at` writes will now move `updated_at`, a lead monitor's
  incremental sync sees every learner visit as a changed row. That is arguably correct (last accessed
  is a returned field) but increases row churn on every page view of the player; worth stating in the
  spec and the docs ("What moves `updated_at`", as the users docs section does).

## 5. Existing API foundation: what a new resource copies

All in `freedom_ls/api/` unless noted. Foundation spec:
`spec_dd/3. done/2026-11-03_09:54_apis-for-lead-monitoring-1-foundation-and-users/1. spec.md`.

- **Viewset base**: `ReadOnlyApiViewSet` (`api/viewsets.py:46`): `ApiKeyAuthentication`,
  `HasApiScope`, `ApiKeyRateThrottle`, `JSONRenderer`, `ApiKeysetPagination`, `DjangoFilterBackend`,
  `http_method_names = get/head/options`. Subclass sets `required_scope`, `serializer_class`,
  `filterset_class`, `get_queryset`.
- **Site isolation**: `filter_queryset` (`viewsets.py:59-75`) always applies
  `queryset.filter(site_id=api_key.site_id)` and returns `.none()` without a key. So `get_queryset`
  should use `CourseProgress._base_manager` (the request has no host-matched thread-local the way a
  browser request does; the users viewset does the same with `User._base_manager.all()`,
  `accounts/api.py:37`). Detail lookups go through the same path, so cross-site rows 404.
- **Template resource**: `freedom_ls/accounts/api.py`: a `ModelSerializer` with explicit `fields` and
  `read_only_fields = fields`; a `UpdatedSinceFilterSet` subclass (`api/filters.py:37`, filters
  `updated_at__gte` via `AwareIsoDateTimeFilter`, rejects naive datetimes) with `Meta.fields = []`;
  a viewset; `router.register("users", UserApiViewSet, basename="user")` from `api/routers.py`.
  URL name pattern is `api:user_list` / `api:user_detail`, so `api:course_progress_list` /
  `api:course_progress_detail` with `basename="course_progress"`. URL prefix `"course-progress"`
  (kebab-case plural per the roadmap).
- **Discovery**: `api/urls.py:11` and `api/checks.py:63` call `autodiscover_modules("api")`, so a new
  `freedom_ls/learner_progress/api.py` is auto-imported with no URL edit. System check
  `freedom_ls_api.E001` errors if `required_scope` is not an `ApiScope`.
  Use `ApiScope.REGISTRATIONS_AND_PROGRESS` (`api/scopes.py:8`; description already names
  `CourseProgress`, `scopes.py:23-25`). Scope already exists in the migration (`api/migrations/0001_initial.py:27`);
  no API migration needed.
- **Pagination**: `ApiKeysetPagination` (`api/pagination.py:30`): `ordering = ("updated_at","id")`,
  opaque base64 cursor of `[updated_at.isoformat(), str(pk)]`, decodes pk via `model._meta.pk.to_python`
  so a UUID pk works; page size `API_PAGE_SIZE`/`API_MAX_PAGE_SIZE` (defaults 100/500 per docs).
  Needs `updated_at` on the model; fetches `page_size + 1`. Postgres orders UUID by bytes, which is
  consistent with the filter on `pk__gt`.
- **Serializer details to settle**: UUID fields serialise as strings by default; `progress_percentage`
  is an int; timestamps ISO 8601 with `Z` (users test asserts `endswith("Z")`).
- **Docs**: `docs/api.md`. Edits needed: intro line 8 ("Today there is one: users"); scope table
  line 46 and the paragraph at 48-49 ("Only `users` has an API endpoint so far"); a new
  "Course progress" section modelled on "Users" (lines 232-267): scope, list and detail URLs, filters,
  fields table, "What moves `updated_at`". The Python example (line 177) targets users; it is compiled
  by `freedom_ls/api/tests/invariants/test_api_docs.py`, so any change to it must still compile.
  Children 2-6 all edit these lines: expect merge conflicts (roadmap line 677).
- **Security doc**: `docs/product/security-and-data-handling.md:110-120` "API Access (built)" has a
  "What it exposes" paragraph that names only the users endpoint. Add the course-progress rows there
  with the email/name note. Line 22 summary says "serves a site's user data"; may need widening.
  (Children 2, 3, 4 also edit this paragraph.)
- **Tests to copy**: `freedom_ls/accounts/tests/test_api.py` is the full template: fixtures
  `api_key` (`ApiKeyFactory()` under `mock_site_context`; factory default scope is `[ApiScope.USERS]`
  so pass `scopes=[ApiScope.REGISTRATIONS_AND_PROGRESS]`, `api/factories.py:12-17`), `auth` headers,
  `APIClient`, `collect_pages` (`api/tests/helpers.py:19`), `site_context(SiteFactory(...))` for
  cross-site isolation, scope 403 text ("This API key does not have the users API scope." -> course
  scope name will be `registrations_and_progress`), 405/404/HEAD/OPTIONS tests, shared-`updated_at`
  paging with `_base_manager.update(updated_at=...)`, naive `updated_since` 400, throttle test, and
  a query bound `django_assert_max_num_queries(8)` for 20 rows
  (`test_a_page_of_twenty_users_stays_under_a_query_bound`). The new test should pin the count
  for the select_related shape and for a mix of learner and cohort registrations.
  Tests live at `freedom_ls/learner_progress/tests/test_api.py`.
- Note `test_options_is_200...` asserts body `{"name": "User Api List"}` (name derived from class
  name); copy with `Course Progress Api List` equivalent as the viewset is named.

## 6. Learner -> user -> organisation flattening

- `Learner` (`freedom_ls/learner_management/models.py:151`): `user` FK (`AUTH_USER_MODEL`, CASCADE),
  `organisation` FK (`freedom_ls_organisations.Organisation`, PROTECT), `is_active`, `created_at`;
  unique per `(site, user, organisation)`. `Organisation` (`freedom_ls/organisations/models.py:63`):
  `name`, `slug`, logos, `TimestampedModel`; no `kind`.
- A `CourseProgress` always has `learner` set (non-null), whichever registration granted it, so the
  flattening for progress goes `learner.user` / `learner.organisation` with no dependence on the
  registration kind. (For a cohort registration, `cohort.organisation_id` equals
  `learner.organisation_id` by `clean()`, `models.py:221`.)
- Fields per the idea: `user_id` (int, `User` pk is integer, not UUID), `user_email`, `user_first_name`,
  `user_last_name`, `organisation_id` (UUID string), `organisation_name`. **Names are not yet
  decided anywhere**: child 4's idea says only "user id, email and organisation" for individual
  registrations. The two specs must agree on names; the roadmap says whichever lands second reuses
  the first. Child 4 is "in progress" (idea only), so this spec either defines a shared mixin first or
  states the names and a compatibility note for child 4.
- No existing shared helper. Where it could live (generic API layer must stay free of FLS names per
  CLAUDE.md plugin rule; that rule concerns `claude_plugins`, not `freedom_ls/api`, so FLS-specific
  code in `freedom_ls/api` is permitted but `freedom_ls/api` today imports no learner model). Candidates:
  `freedom_ls/learner_management/api_fields.py` (new serializer mixin `LearnerIdentityFieldsMixin`
  using `source="learner.user.id"` etc.) imported by both `learner_management/api.py` (child 4) and
  `learner_progress/api.py` (this spec). `learner_progress` already imports from
  `learner_management` (`models.py:10-15`), so the direction is correct and creates no cycle.
- Query shape: `select_related("learner__user", "learner__organisation", "course",
  "learner_registration", "cohort_registration")`. Existing analogue at
  `freedom_ls/learner_progress/queries.py:173,268` (`select_related("learner__organisation", "course")`).
  Note `User` has its own `SiteAwareManager`; `select_related` joins bypass managers so no extra
  query. Do not select `last_accessed_item` (out of scope). `CourseProgress.__str__` hits
  `learner` and `course` and `Learner.__str__` hits user/organisation: not used by the serializer.
  Do not use `SerializerMethodField` per row that does lookups.
- `kind` value for registration: computed from `learner_registration_id is not None` (`"individual"`
  vs `"cohort"`); `registration_id` from whichever FK is set. Cohort/individual registration models
  have no `updated_at` today (child 4 adds one); this spec exposes only ids, so no dependency on
  those columns. Child 4 may name its `kind` `individual`/`cohort`; coordinate values.
  Registration ids are UUIDs (`SiteAwareModel`).

## 7. Factories and fixtures

- `CourseProgressFactory` (`freedom_ls/learner_progress/factories.py:23`): learner via `LearnerFactory`,
  course via `CourseFactory`, default `learner_registration` for the same learner and course. Cohort
  grant: pass `cohort_registration=...` and `learner_registration=None`.
- `LearnerFactory` (`learner_management/factories.py:28`, delegates to `ensure_learner`, so repeated
  calls with the same user/org return the same row), `CohortFactory` (`:71`),
  `CohortMembershipFactory` (`:81`, learner defaults into cohort's organisation),
  `LearnerCourseRegistrationFactory` (`:99`), `CohortCourseRegistrationFactory` (`:110`),
  `OrganisationFactory` (`organisations/factories.py:11`), `UserFactory` (`accounts/factories.py:10`),
  `ApiKeyFactory` (`api/factories.py:12`). Base `SiteAwareFactory` takes the site from the
  `mock_site_context` fixture.
- Factory caveat: it builds records directly because the on_commit mint receivers never fire in a
  rolled-back test transaction. `created_at` is `auto_now_add`, so tests that need specific timestamps
  set them with `_base_manager.filter(pk=).update(...)` (also the way the users test pins
  `updated_at`). For `updated_at` that update bypasses `auto_now`, which is what tests want.
- Seed fixtures that set specific CourseProgress timestamps live in `qa_helpers` commands; none of them
  needs change, but `qa_create_dashboard_paging_fixtures.py:424` writes `created_at` via `.update`.

## 8. Migration concerns

- `AddField updated_at DateTimeField(auto_now=True)` on a populated table needs a default for existing
  rows. Pattern: add the field nullable (or with a one-off `default=timezone.now`, `preserve_default=False`),
  `RunPython`/`RunSQL`-free `UPDATE` setting `updated_at = GREATEST(created_at, started_at,
  last_accessed_time, completed_time)`; Postgres `GREATEST` ignores NULLs, and `created_at` is never
  NULL so the result is never NULL. In ORM terms:
  `CourseProgress.objects.update(updated_at=Greatest("created_at", "started_at", "last_accessed_time", "completed_time"))`
  using `django.db.models.functions.Greatest` (use `_base_manager` in the migration with historic
  models; manager from `apps.get_model` is plain). Percent-only changes made earlier have no timestamp,
  so for existing rows `updated_at` is a lower bound: it may be earlier than the true last change;
  alternative is `Now()` for all existing rows, which makes the first `updated_since` pull return
  everything and is safer for correctness at the cost of one big first pull (first pull is a full pull
  anyway). The idea settles on "latest existing timestamp"; worth flagging that
  `progress_percentage`-only changes are invisible for backfill.
- Order the migration steps: AddField (nullable) -> RunPython/Update -> AlterField to NOT NULL
  `auto_now`. Or a single AddField with a `default=` callable then AlterField removing it. `auto_now`
  fields cannot take `null=True` forever without a model change, so keep the model field non-null.
- Index: the users model has `Index(fields=["site","updated_at","id"], name="accounts_user_site_updated_idx")`
  (`accounts/models.py:98-101`, migration `accounts/migrations/0004_user_accounts_user_site_updated_idx.py`).
  Copy: `models.Index(fields=["site", "updated_at", "id"], name="learner_progress_cp_site_updated_idx")`
  on `CourseProgress.Meta.indexes` (name <= 30 chars; Django requires it, e.g.
  `lp_courseprogress_site_upd_idx`). The existing `(learner, course)` index stays.
- On a big table, `AddIndex` locks writes. Consider `AddIndexConcurrently`
  (`django.contrib.postgres.operations`, `atomic = False`) if the table is large; check the
  project's migration convention first (accounts/0004 used plain `AddIndex`).
- Never edit existing migrations (CLAUDE.md); run `uv run manage.py makemigrations` and `migrate`.
- Foundation's `ApiKey` model, throttle and cache config need no change.

## 9. Conflicts and risks

1. **`update_fields` writers silently skip `auto_now`** (section 4): the main correctness risk and a
   regression trap for any future `save(update_fields=...)`.
2. **Churn**: player visits (`views.py:1566`) now move `updated_at` on every content item view; an
   incremental sync sees large volumes of changed rows. Fine, but document it.
3. **`created_at` naming**: the API field set in the idea excludes `created_at`, but "registration date"
   might be wanted by a lead monitor (the idea lists "started time, completed time, last accessed
   time" and not registered time). Decide whether to expose `created_at` as e.g. `registered_at`
   (sibling registrations expose `registered_at`, `learner_management/models.py:255,290`). Naming
   consistency: the model field is `started_at`, `completed_time`, `last_accessed_time`; the API
   should either mirror the model names or normalise (e.g. `completed_at`); the spec must choose and
   note child 4 uses `registered_at`.
4. **Sibling merge conflicts** with children 2, 3, 4 on `docs/api.md`, `docs/product/security-and-data-handling.md`,
   and (for 4) shared flattening code. Child 4 also adds `updated_at` to registration models in
   `learner_management`, a separate migration; migration dependency graph does not conflict because
   they are different apps.
5. **Pagination typing**: `ApiKeysetPagination` and `paginate_all` are bound to `TimestampedModel`;
   `CourseProgress` will not be one (section 3).
6. **Default `ApiKeyFactory` scope is `users`** only; tests must pass the registrations scope.
7. **Site filter is explicit**: `site_queryset` filters by `api_key.site_id`; with `_base_manager` no
   host-based filtering interferes. If the spec uses `CourseProgress.objects`, the manager would also
   filter by the thread-local request site (set by middleware for the API host); the users viewset
   deliberately uses `_base_manager`, copy that.
8. `Learner.is_active` / `User.is_active`: inactive learners and deactivated users still have
   `CourseProgress` rows; the endpoint should return them (consistent with users returning inactive
   users) and the spec should say so; consider exposing no `is_active` (not in the idea).

## 10. Files expected to change

- `freedom_ls/learner_progress/models.py` (field, index, maybe `save()` override)
- `freedom_ls/learner_progress/migrations/0003_*.py`
- `freedom_ls/learner_progress/signals.py` (lines 65, 310, 314-319)
- `freedom_ls/learner_progress/management/commands/recalculate_progress_percentages.py` (line 64)
- `freedom_ls/learner_interface/views.py` (lines 1566-1568, 2204) unless a `save()` override covers them
- `freedom_ls/learner_progress/api.py` (new; serializer, filterset, viewset, router registration)
- shared learner identity serializer fields (new; location per section 6)
- `freedom_ls/learner_progress/tests/test_api.py` (new) plus updated-at tests for each writer
- `docs/api.md`, `docs/product/security-and-data-handling.md`
- optionally `freedom_ls/learner_progress/admin.py` (`updated_at` read-only display)

Sources: all from the local repository (no web sources used).

status: ok
