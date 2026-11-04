# Research: codebase (course applications API)

Paths are relative to the project root. Line numbers are from the current tree.

## 1. What child 1 provides (the pattern to copy)

The `freedom_ls/api/` app is merged and complete. Resource code does NOT live in `freedom_ls/api/`; each
endpoint app owns an `api.py` that registers with the shared router.

- Discovery: `freedom_ls/api/urls.py:11` `autodiscover_modules("api")` imports every installed app's `api.py`,
  which is what registers viewsets. So a new `freedom_ls/course_applications/api.py` is picked up with no
  edit to `freedom_ls/api/`. Router: `freedom_ls/api/routers.py` (`ApiRouter`, list + detail routes only,
  names `{basename}_list` / `{basename}_detail`; `router = ApiRouter()` at line 25). URL names under
  `app_name = "api"`, e.g. `api:course_application_list`.
- Users endpoint, the template: `freedom_ls/accounts/api.py` (40 lines).
  - `UserApiSerializer(ModelSerializer)`, `fields = (*USER_EXPORT_FIELDS, "updated_at")`, `read_only_fields = fields`.
    It reuses the export's field tuple from `accounts/resources.py` (`USER_EXPORT_FIELDS`); the analogue here is
    `APPLICATION_EXPORT_FIELDS` in `course_applications/resources.py:25` (but see section 3: it holds `course`
    as title, which the API splits).
  - `UserFilterSet(UpdatedSinceFilterSet)` with empty `Meta.fields`.
  - `UserApiViewSet(ReadOnlyApiViewSet)`: `filterset_class`, `required_scope = ApiScope.USERS`, `serializer_class`,
    `get_queryset()` returns `User._base_manager.all()` (+ annotation). Comment says the base viewset narrows to the key's site.
  - `router.register("users", UserApiViewSet, basename="user")` (line 40).
  - Tests: `freedom_ls/accounts/tests/test_api.py`; shared helpers `freedom_ls/api/tests/helpers.py`, `conftest.py`.
- Base viewset: `freedom_ls/api/viewsets.py` `ReadOnlyApiViewSet` (line 46): `ApiKeyAuthentication`, `HasApiScope`,
  `ApiKeyRateThrottle`, JSON renderer, `ApiKeysetPagination`, `DjangoFilterBackend`, `http_method_names = get/head/options`.
  `filter_queryset` (59) calls `site_queryset` (65) which does `queryset.filter(site_id=api_key.site_id)`; returns `.none()` with no key
  or during schema generation. So `get_queryset` must start from a manager that crosses sites (`_base_manager`), exactly as users does;
  `CourseApplication.objects` is the host-filtered `SiteAwareManager`, so use `CourseApplication._base_manager`.
  The detail lookup also goes through `filter_queryset`, so detail 404s for other sites for free.
- Scope: already declared. `freedom_ls/api/scopes.py:6` `ApiScope.COURSE_APPLICATIONS = "course_applications"`, described at line 21
  as "CourseApplication and its answers". Nothing to add. `docs/api.md:44` already lists it and line 48 says "Only `users` has an API endpoint so far" (needs updating).
- Pagination: `freedom_ls/api/pagination.py` `ApiKeysetPagination` (line 30). `ordering = ("updated_at", "id")` (31) is a class attribute
  but `paginate_queryset` (41-46) hard-codes `queryset.order_by(*self.ordering)` and filters `Q(updated_at__gt) | Q(updated_at=, pk__gt)` on
  the model field named `updated_at`. `_next_link` (109) reads `last.updated_at` off the row. Cursor payload is `[iso, str(pk)]`; pk decoded via
  `model._meta.pk.to_python`, so UUID pks already work. Typed `TypeVar M bound=TimestampedModel`.
  IMPLICATION: the pagination reads `updated_at` as an attribute of the instance AND as a queryset field in order_by/filter.
  An annotation named `updated_at` would collide with the real model field `CourseApplication.updated_at` (Django raises
  "The annotation 'updated_at' conflicts with a field on the model"). So either the annotation has a different name and pagination is made to take
  the field name from the view/ordering, or the real column is made to be the effective changed-since value (denormalised option). This is the main design fork.
- Filter: `freedom_ls/api/filters.py:37` `UpdatedSinceFilterSet.updated_since = AwareIsoDateTimeFilter(field_name="updated_at", lookup_expr="gte")`
  (inclusive, rejects naive datetimes). Subclassing and overriding `field_name` (or the name of an annotation) is the hook for a different field.
- Throttling: `freedom_ls/api/throttling.py`, per key, 600/min default (`docs/api.md:106`). Nothing resource specific.
- Docs: `docs/api.md` is the page. It has shared sections then a per-resource section (`## Users`, line 232, with table of API scope/List/Detail/Filters,
  Fields table, "What moves `updated_at`" subsection) and a full httpx example syncing users (lines 171-224). Line 7-8 says "Today there is one: users";
  line 48 says only `users` has an endpoint. A test enforces the docs: `freedom_ls/api/tests/invariants/test_api_docs.py` (read it before editing docs/api.md
  so the new section satisfies it).
- Schema: `freedom_ls/api/schema.py`, `AutoSchema` on the base viewset; nested serializers need drf-spectacular-friendly declarations
  (explicit nested serializer, not a SerializerMethodField returning dicts, or give `@extend_schema_field`).
- Security doc: `docs/product/security-and-data-handling.md` line 22 (summary bullet: "serves a site's user data") and section `### API Access (built)` at line 110 need the
  course_applications scope added; line 136 lists applicant data held. Other lines in the file are very long.
- No other app has an `api.py` yet apart from `accounts` (grep for `router.register` returned only `freedom_ls/accounts/api.py:40`).

## 2. Models, timestamps and indexes

`freedom_ls/course_applications/models.py`
- `AnonymousApplicant(SiteAwareModel, TimestampedModel)` (29): `created_at`, `updated_at` (auto_now) from `TimestampedModel`
  (`freedom_ls/site_aware_models/models.py:173`). Fields: course FK, email, first_name, last_name, consent_*, user FK null, claimed_at,
  claim_email_sent_at, claim_link_version. One-to-one back to application via `course_application`.
- `CourseApplication(SiteAwareModel)` (84): NOT `TimestampedModel`; declares its own `created_at` auto_now_add (133) and `updated_at` auto_now (134).
  Pk is UUID (SiteAwareModel). Relations: `user` FK null (103, related_name `course_applications`), `anonymous_applicant` O2O null (110),
  `course` FK (117, related_name `applications`), `form_progress` O2O null RESTRICT (126, related_name `course_application`).
  Meta: only `unique_application_per_site_user_course` (137). NO index on `updated_at` or `(site, updated_at, id)`. Migrations have no indexes
  on any of the three tables (grep of `course_applications/migrations`, `form_engine/migrations`: only `AddIndex` hits are in accounts).
  Contrast: `User` has `Index(fields=["site","updated_at","id"], name="accounts_user_site_updated_idx")` (`accounts/models.py:99`, migration `accounts/migrations/0004_user_accounts_user_site_updated_idx.py`). That is the precedent for an index in this effort.
- Properties used by the API (all from the one place; spec says they must follow when review adds `state`):
  - `is_submitted` (159): `form_progress is None or form_progress.completed_time is not None`.
  - `submitted_time` (171): `created_at` if no sitting, else `form_progress.completed_time` (None for drafts).
  - `is_email_verified` (179): `user_id is not None`.
  - `applicant_email` (195) / `applicant_name` (203): from `user` else `anonymous_applicant`; "" if neither. Name is `"first last".strip()`.
  - All touch `user`, `anonymous_applicant`, `form_progress`, so the viewset needs `select_related("user","anonymous_applicant","course","form_progress")`.
- `FormProgress(SiteAwareModel)` (`freedom_ls/form_engine/models.py:239`): `start_time` auto_now_add (258), `last_updated_time` auto_now (259), `completed_time` (260).
  No `updated_at`, no index. Related name for answers: `answers` (670).
- `QuestionAnswer(SiteAwareModel, TimestampedModel)` (667): `form_progress` FK related_name `answers`, `question` FK PROTECT, `selected_options` M2M,
  `text_answer`, unique (form_progress, question). `QuestionAnswerFile(SiteAwareModel, TimestampedModel)` (717): O2O `answer` related_name `answer_file`, `file`, `original_filename` (255).

## 3. The export and answer formatting (what to reuse)

`freedom_ls/course_applications/resources.py`
- `APPLICATION_EXPORT_FIELDS` (25): id, applicant_email, applicant_name, is_email_verified, course, is_submitted, submitted_time, created_at. Idea wants `course` replaced by course id + course title,
  plus `updated_at`. So the API serializer cannot reuse the tuple verbatim.
- `filter_export` (61-71) is the prefetch recipe to copy: `select_related("user","anonymous_applicant","course","form_progress")` and
  `prefetch_related("form_progress__form","form_progress__answers__question","form_progress__answers__selected_options","form_progress__answers__answer_file")`.
  Note `answer_file` is a reverse one-to-one: prefetching it works, but a missing one raises `RelatedObjectDoesNotExist`/`DoesNotExist` on access (hence `hasattr` in `answer_cell`).
  `form_progress__form` is only needed by the export for column layout; the API likely doesn't need it.
- The resource is `import_export` based and builds columns per question title; the API does not use `before_export`/`answer_columns`. The reusable part is the per-answer value logic.

`freedom_ls/form_engine/exports.py`
- `answer_cell(answer)` (115-131) returns a string: option questions -> `"; ".join(option.text)` sorted by `option.order` (reads `selected_options.all()`, so prefetched);
  FILE_UPLOAD -> `answer.answer_file.original_filename` (guarded with `hasattr`, "" if none); everything else -> `answer.text_answer` (dates/times are already stored as ISO text).
  `OPTION_QUESTION_TYPES` and `QuestionType` from `freedom_ls/form_engine/enums.py`.
- This is flat-text oriented ("; " joined, "" for none). The API needs a value that matches the idea: option answers "give the option text" (a string joined with "; " vs a list of strings is a spec decision;
  checkbox questions can have several options so a list is the unambiguous JSON shape, but `answer_cell` joins). Either extract a shared helper from `answer_cell` (e.g. a function returning the option texts/filename/text, with `answer_cell` joining) to avoid repeating logic (CLAUDE.md: avoid repeating code), or call `answer_cell` directly. Note `form_engine/exports.py` docstring: "The resource that exports applications lives in an app this one must not import", i.e. form_engine must not import course_applications; the API serializer in course_applications importing from form_engine is the allowed direction.
- Question text: `answer.question.question` (the same attribute used as export header at exports.py:74); question type `answer.question.type` (`QuestionType`). Question id `answer.question_id`.
- "Unanswered question has no entry": the data model already stores no row for unanswered questions (`save_answers` at form_engine/models.py:381-383 deletes the row for a blank submission, and a page with only optional questions leaves no rows), so "no entry" is the natural choice; a null value would require enumerating the form's questions (extra queries, off-page questions). A row can still exist with `text_answer == ""` (e.g. cleared file/answers are deleted, but text rows are created by `get_or_create` then set), so an entry with empty-string value is possible; the spec should say whether `""` becomes null.

## 4. The changed-since problem: what moves what

Applications are shown from four rows: `CourseApplication` (updated_at), `AnonymousApplicant` (updated_at), `FormProgress` (last_updated_time), `QuestionAnswer` (updated_at) / `QuestionAnswerFile` (updated_at), plus the `User` row for signed-in applicants (email, first/last name).

| Event | Code | Timestamp that moves |
| --- | --- | --- |
| Application created | `CourseApplication` auto_now/auto_now_add | application `updated_at` |
| Sitting submitted | `FormProgress.complete()` form_engine/models.py:403-412; called from course_applications/views.py:798 | `FormProgress.last_updated_time` (via `save()`, auto_now) and `completed_time`. NOT `CourseApplication.updated_at` |
| Page shown | `record_page_reached` form_engine/models.py:306-315 | `FormProgress.last_updated_time` only (so a bare page view "changes" a greatest-of rule) |
| Answer saved (text/options) | `save_answers` form_engine/models.py:393-400 (`answer.save()`) | `QuestionAnswer.updated_at` only. Not the sitting, not the application. `selected_options.set()` is M2M and does not touch the answer, but the following `answer.save()` does |
| Answer cleared (blank on resubmit of a page) | `self.answers.filter(question=question).delete()` form_engine/models.py:382 | NOTHING moves (queryset delete, no signal on remaining rows). The row just vanishes |
| File uploaded | form_engine/views.py:121-130: `get_or_create` answer, then `answer_file.file.save(..., save=True)` | `QuestionAnswerFile.updated_at`, and `QuestionAnswer.updated_at` only on first creation (get_or_create). A replacement of an existing file moves only the `QuestionAnswerFile.updated_at`. `original_filename` changes with it |
| File removed | form_engine/views.py:146 (`answers.filter(question=question).delete()`) | nothing moves |
| Anonymous applicant changes email/name | `claims.update_applicant_email` course_applications/claims.py:171-177 (`save(update_fields=[..., "updated_at"])`) | `AnonymousApplicant.updated_at` only |
| Claim / login attach | `claims.attach_to_user` claims.py:333-339 | application `updated_at` (explicit in update_fields), `FormProgress.last_updated_time` (explicit), applicant `updated_at`. `user` set, so `is_email_verified` flips and `applicant_email` may change source: this one is visible. Note each save lists the auto_now field explicitly because `update_fields` without it would skip auto_now |
| Signed-in user edits name/email | `User` save | `User.updated_at` only. `applicant_email`/`applicant_name` change but the application does not move |
| Application deleted | `post_delete` receiver course_applications/receivers.py:30-50 | row disappears; no feed (settled) |

Takeaways:
1. The sitting's `last_updated_time` is not bumped by answer edits, so "greatest of application, applicant, form progress" (the idea's example) MISSES answer edits. A complete rule needs `QuestionAnswer.updated_at` (and `QuestionAnswerFile.updated_at` for file replacement) as well.
2. Answer or file deletions move nothing anywhere, so cleared answers are not detectable by an `updated_since` poll unless the delete path also bumps a timestamp on the sitting/application. Those deletions are `QuerySet.delete()` calls in `form_engine/models.py:382` and `form_engine/views.py:146` (no per-instance signal on the parent). The idea guarantees "every submission and every answer change"; deletion of an answer is arguably an answer change, so the spec should decide (e.g. bump `FormProgress`/application on answer post_delete, or declare it out of scope consistent with "no deletion feed").
3. Submission is covered by `FormProgress.last_updated_time` (complete() calls full `save()`).
4. User name/email edits and anonymous applicant edits change the nested `applicant_*` fields; the Greatest rule would need `user__updated_at` and `anonymous_applicant__updated_at`, or the spec accepts that user-side changes are the users endpoint's concern. Existing precedent: `accounts/signals.py:12-20` `touch_user_updated_at` bumps `User.updated_at` with a queryset `.update(updated_at=timezone.now())` on `EmailAddress` post_save/post_delete because verification is not a User column. The same trick is available here.
5. `FormProgress` is site-aware and the application is the only thing that reaches it (O2O `course_application`). A sitting row can exist with `user` set from a claim; it is reachable from the application either way.

### Options for a single filterable/orderable `updated_at`

Constraint from section 1: pagination orders and filters on a model field named `updated_at`, and reads `row.updated_at` for the cursor. The filter is `field_name="updated_at"`. Site filtering `site_id=` is applied before ordering.

A. Annotated `Greatest()` (no schema change).
   - `queryset.annotate(api_updated_at=Greatest("updated_at","anonymous_applicant__updated_at","form_progress__last_updated_time", <max answer updated_at via Subquery/Max>, ...))`.
   - Name must differ from `updated_at` (field conflict). Needs: filter `field_name="api_updated_at"`, `ApiKeysetPagination` generalised to take the ordering field name from the view (it currently hard-codes `updated_at` in order_by, Q filter and `_next_link`), and the serializer's `updated_at` mapped via `source="api_updated_at"`. Child 1's pagination is shared, so a change there touches the foundation and its tests (`freedom_ls/api/tests/test_pagination.py`).
   - SQL `GREATEST` ignores NULLs in PostgreSQL (returns NULL only if all are NULL), so nullable joins (`anonymous_applicant`, `form_progress`) are safe on PostgreSQL 17, unlike `Greatest` on SQLite/MySQL (Django doc note). Max over answers needs a correlated subquery (`Subquery(QuestionAnswer.objects... .order_by("-updated_at").values("updated_at")[:1])`).
   - Cost: cannot use an index; every request evaluates joins/subqueries for all site rows before ORDER BY + LIMIT (the keyset filter is a WHERE on a computed expression), so it is a seq scan + sort of the site's applications per page. Fine for thousands of applications, degrades with growth; page 1000 times for a 100k-row sync is quadratic-ish. A functional index on a multi-table expression is not possible.
B. Denormalised `updated_at` on `CourseApplication`, bumped when children change.
   - `CourseApplication.updated_at` already exists as `auto_now`. Make it mean "last change to the application or anything the API shows". Bump with `CourseApplication._base_manager.filter(...).update(updated_at=timezone.now())` from: `FormProgress` post_save (covers submit, page reached, claim attach), `QuestionAnswer` post_save/post_delete, `QuestionAnswerFile` post_save/post_delete, `AnonymousApplicant` post_save, and `User` post_save (only for users with applications) if desired.
   - Wrinkle: `form_engine` must not import `course_applications` (exports.py docstring). Signal receivers therefore belong in `course_applications/receivers.py` (already connected in `apps.py` `ready()`, receivers.py:1-5), listening to `form_engine` models' signals; that is the allowed direction and the file already imports `FormProgress` from form_engine (26).
   - Follows the existing precedent (`accounts/signals.py`) and the `User` composite index precedent: add `Index(fields=["site","updated_at","id"], name="course_applications_site_updated_idx")` via a new migration (never edit existing ones). Keeps `ApiKeysetPagination` and `UpdatedSinceFilterSet` unchanged, so zero changes to child 1.
   - Risks: bulk paths bypass signals: `QuerySet.delete()` of answers fires `post_delete` per instance (Django collects and sends signals for cascade/queryset deletes unless fast-delete applies; fast delete is skipped when signals are connected, so a connected `post_delete` receiver makes this work). `QuerySet.update()` or `bulk_create` of answers would not fire; grep showed none for answers in views/claims, but import/erasure code (`course_applications/erasure.py`) and data migrations should be checked. The `updated_at` of existing rows needs a backfill migration (set to greatest of existing timestamps) or the first sync is already full anyway; the checkpoint minus 5 minutes margin plus upsert handles late commits.
   - A bump on an application whose `updated_at` already equals now is harmless. Many answer saves in one page POST means N small UPDATEs; could be reduced with one update after `save_answers`, but receivers per answer are simplest.
   - Pitfall: `CourseApplication.save()` with `update_fields` lacking `updated_at` does not bump it (see claims.py already adding it explicitly).
C. Denormalised field on `FormProgress` (e.g. add `updated_at`) and keep Greatest across two columns: more moving parts than B; rejected unless answers must be kept out of the application row.
D. Hybrid: a new nullable `last_activity_at` (or similar) column on `CourseApplication` bumped by signals, with `updated_at` left as is and `Greatest("updated_at","last_activity_at")` annotated. Same pagination collision as A, no benefit over B.

Observation: option B keeps the idea's phrase "single `updated_at`" literally true on the model and is the only option that gets an index, matching how child 1 treated users (a real column + site composite index + a signal for the one non-column change). Option A is the only one with no write-path side effects. This is a spec decision; both are viable.

## 5. Query cost and tests

- The nested answers need `prefetch_related("form_progress__answers__question","form_progress__answers__selected_options","form_progress__answers__answer_file")` plus `select_related("user","anonymous_applicant","course","form_progress")`. That is a fixed number of queries per page regardless of page size (1 main + 1 answers + 1 questions + 1 options + 1 answer files, approximately 5; the main select_related is one join query). The idea requires a test pinning the query count; use `django_assert_num_queries` / `django_assert_max_num_queries` (pytest-django) and check `freedom_ls/api/tests/test_viewsets.py` and `accounts/tests/test_api.py` for any existing pattern (no match for query-count helpers in test_viewsets.py; check accounts test).
- Ordering of nested answers: prefetched `.all()` has no guaranteed order; give the serializer a deterministic order (e.g. question `order`, then id, or sort in Python) so output is stable. `QuestionAnswer` has no Meta ordering.
- Applications with `form_progress is None` have no answers; serializer must return `[]`.
- Factories: `freedom_ls/course_applications/factories.py` (applications, anonymous applicants), `freedom_ls/api/factories.py` (API keys), `freedom_ls/api/tests/helpers.py`. Check form_engine factories for answers and file answers.
- Multi-tenant: `fls-dev:multi-tenant` skill; the viewset must use `_base_manager` (as users) so the key's site decides, not the request host, and a test should prove another site's application is not returned and 404 on detail. `form_progress`, answers, and user are site-aware but the answer prefetch uses the default manager of `QuestionAnswer`; a prefetch through a related manager may be host-filtered by `SiteAwareManager` (verify: `form_progress__answers` prefetch uses the related manager built from the default manager; if the request host differs from the key's site this could drop answers). The export avoids it because the admin request is on the site's own host. For the API, authentication already rejects a key used on another host, so host == key site and the filter is harmless, but the spec should say so or use `Prefetch(..., queryset=QuestionAnswer._base_manager...)`. Worth a test.

## 6. Conflicts and touch points to flag

- Do not add `course_applications` scope: already exists. Do touch: new `freedom_ls/course_applications/api.py` (serializers, filter, viewset, `router.register("course-applications", ..., basename="course_application")`).
  The router prefix must be kebab-case `course-applications`; basename snake_case.
- Cross-spec caution (roadmap 680-684): specs 3-6 also edit `docs/api.md` and `freedom_ls/api/` files; keep the docs change to a new `## Course applications` section, the API-scope note (line 48), line 7-8 intro, and an additional example, to minimise merge conflicts. Docs invariant test: `freedom_ls/api/tests/invariants/test_api_docs.py`.
- If option A: modifies `freedom_ls/api/pagination.py` and its tests (shared with specs 3-6). If option B: adds a migration in `freedom_ls/course_applications/migrations/` (existing latest is 0004; check for newer numbering with `Glob`), signal receivers in `course_applications/receivers.py`, and changes nothing in `api/`.
- Admin export unchanged (out of scope): do not alter `resources.py` behaviour; any helper extraction from `form_engine/exports.py:answer_cell` must leave its output identical (it has its own tests; check `freedom_ls/form_engine/tests/` for export tests).
- `CourseApplication.__str__` and the admin deliberately avoid PII; the API serializer is the first place that exposes email and name via JSON; `AnonymousApplicant` consent fields and claim state must be absent from the explicit field list (never `__all__`).
- Vocabulary: use "sitting" for `FormProgress` as the codebase does (docstrings in models.py) and "API scope" per docs/api.md.
- The app future change: review spec will add `state`/`submitted_at` to `CourseApplication` (models.py:90 NOTE). Serializer must read `is_submitted`/`submitted_time` via the properties, not duplicate the sitting logic, as the idea states.

## Sources
Local code only; no web research needed. Files read: freedom_ls/api/{scopes,viewsets,filters,pagination,routers,urls}.py, freedom_ls/accounts/{api,signals}.py, freedom_ls/course_applications/{models,resources,claims,receivers}.py, freedom_ls/form_engine/{models,exports,views}.py, freedom_ls/site_aware_models/models.py, docs/api.md, docs/product/security-and-data-handling.md, spec_dd/1. next/roadmap.md (Lead monitoring API section).

status: ok
