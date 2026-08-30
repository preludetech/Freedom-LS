# Research: field-level hardening

## Executive summary

Timestamps are the only genuinely time-sensitive item in this unit. `auto_now_add=True` records
insertion time; adding it after rows exist means every pre-existing row gets either the migration's
run time or an arbitrary backfill, and nothing in the row can later distinguish a real value from a
fabricated one. FLS has no production rows yet, so every `created_at` added now is accurate from its
first row. `accounts.User` (`freedom_ls/accounts/models.py:67-134`) has no timestamp of any kind, not
even a signup date, and is the flagship case. `content_base.BaseContent` and its eight concrete
subclasses across `content_engine` and `form_engine` are the second: one abstract-base fix reaches all
eight, but three sibling models (`File`, `ContentCollectionItem`, `form_engine.QuestionOption`) sit
outside that base and need the same fix applied individually. `updated_at` is a different question:
its semantics survive a late addition honestly ("last touched since we started tracking"), so it is
do-later everywhere it is missing, with one real trap: role assignments in `role_based_permissions`
are deactivated through `QuerySet.update()`, which never runs `auto_now`, so an `updated_at` added
there would need those call sites fixed in the same change or it would silently go stale.

Constraints and indexes are all do-later. A Postgres column, index or constraint rename is
catalog-only (`ALTER TABLE ... RENAME COLUMN` / `RENAME CONSTRAINT`) at any table size, so
`Cohort`'s misnamed `unique_cohort_name_per_site` and the `"site"` vs `"site_id"` spelling
inconsistency in `Meta.constraints` cost the same now or later. `CourseInterest`'s constraint omits
`site` where `CourseApplication`'s includes it, and the newer `Learner` model omits it too, so the
asymmetry is now three-way, not two, and none of the three is reachable in practice because `user`,
`course` and `organisation` are all themselves site-scoped. Every index gap found (`ContentCollectionItem`'s
missing composite indexes, `WebhookEndpoint.event_types`'s un-indexed JSON containment lookup) closes
later with `CREATE INDEX CONCURRENTLY` without meaningful lock contention, so none of them are pre-deploy
items.

Field types are mostly sound. `BaseContent.tags` (`freedom_ls/content_base/models.py:22`) is a JSON list
used as an admin `list_filter`, which filters by exact-list-value rather than "contains this tag,"
one field away from `Course.learning_outcomes`, which already uses the correct `ArrayField` for the
same shape. `access_config` and `scores` are genuinely schemaless/polymorphic by design and hold up.
`default_auto_field` is declared in 19 `apps.py` files but is consulted in exactly two: `accounts`
(`accounts.User`'s `id` is a bare, undeclared pk, so Django fills it in from `AccountsConfig.default_auto_field`)
and `role_based_permissions` (`SystemRoleAssignment`, a plain `models.Model`). Every other app's concrete
models extend `SiteAwareModel`, which declares its own UUID `id` explicitly, so the setting is dead
weight everywhere else.

## 1. Timestamps

### Current inventory

| Model | Path | Timestamp fields | Base |
|---|---|---|---|
| `accounts.User` | `accounts/models.py:67` | none | `SiteAwareModelBase` (bare `id`, filled by `default_auto_field`) |
| `accounts.SiteSignupPolicy` | `accounts/models.py:137` | none | `SiteAwareModel` |
| `accounts.LegalConsent` | `accounts/models.py:161` | `timestamp` (`auto_now_add`, `:182`) | `SiteAwareModel` |
| `organisations.Organisation` | `organisations/models.py:58` | none | `SiteAwareModel` |
| `learner_management.Cohort` | `learner_management/models.py:32` | none | `SiteAwareModel` |
| `learner_management.Learner` | `learner_management/models.py:51` | `created_at` (`auto_now_add`, `:70`) | `SiteAwareModel` |
| `learner_management.CohortMembership` | `learner_management/models.py:83` | none | `SiteAwareModel` |
| `learner_management.LearnerCourseRegistration` | `learner_management/models.py:108` | `registered_at` (`auto_now_add`, `:118`) | `SiteAwareModel` |
| `learner_management.CohortCourseRegistration` | `learner_management/models.py:132` | `registered_at` (`auto_now_add`, `:144`) | `SiteAwareModel` |
| `learner_management.CohortDeadline` | `learner_management/models.py:158` | none | `SiteAwareModel` |
| `learner_management.LearnerDeadline` | `learner_management/models.py:205` | none | `SiteAwareModel` |
| `learner_management.UserCohortDeadlineOverride` | `learner_management/models.py:252` | none | `SiteAwareModel` |
| `learner_management.RecommendedCourse` | `learner_management/models.py:319` | `created_at` (`auto_now_add`, `:338`) | `SiteAwareModel` |
| `learner_progress.TopicProgress` | `learner_progress/models.py:59` | `start_time` (`auto_now_add`, `:87`), `last_accessed_time` (`auto_now`, `:88`), `complete_time` (`:89`) | `SiteAwareModel` |
| `learner_progress.CourseProgress` | `learner_progress/models.py:106` | `created_at` (`auto_now_add`, `:138`), `started_at` (`:139`), `last_accessed_time` (`:140`), `completed_time` (`:141`) | `SiteAwareModel` |
| `learner_progress.CourseFormAttempt` | `learner_progress/models.py:242` | none | `SiteAwareModel` |
| `content_base.BaseContent` / `TitledContent` / `MarkdownContent` (→ `content_engine.Topic`, `Activity`, `Course`, `CoursePart`; `form_engine.Form`, `FormPage`, `FormContent`, `FormQuestion`) | `content_base/models.py:10,59,79` | none, on all eight concrete subclasses | `SiteAwareModel` |
| `content_engine.File` | `content_engine/models/files.py:30` | none | `SiteAwareModel` (direct, not via `BaseContent`) |
| `content_engine.ContentCollectionItem` | `content_engine/models/courses.py:270` | none | `SiteAwareModel` (direct) |
| `form_engine.QuestionOption` | `form_engine/models.py:172` | none | `SiteAwareModel` (direct) |
| `form_engine.FormProgress` | `form_engine/models.py:193` | `start_time` (`auto_now_add`, `:204`), `last_updated_time` (`auto_now`, `:205`), `completed_time` (`:206`) | `SiteAwareModel` |
| `form_engine.QuestionAnswer` | `form_engine/models.py:568` | `last_updated_time` (`auto_now`, `:579`) only, no `created_at` | `SiteAwareModel` |
| `role_based_permissions.SystemRoleAssignment` | `role_based_permissions/models.py:9` | `assigned_at` (`auto_now_add`, `:30`) | plain `models.Model` |
| `role_based_permissions.SiteRoleAssignment` | `role_based_permissions/models.py:46` | `assigned_at` (`auto_now_add`, `:63`) | `SiteAwareModel` |
| `role_based_permissions.ObjectRoleAssignment` | `role_based_permissions/models.py:80` | `assigned_at` (`auto_now_add`, `:103`) | `SiteAwareModel` |
| `course_interest.CourseInterest` | `course_interest/models.py:17` | `created_at` (`auto_now_add`, `:38`) | `SiteAwareModel` |
| `course_applications.CourseApplication` | `course_applications/models.py:17` | `created_at` + `updated_at` (`:42-43`) | `SiteAwareModel` |
| `app_authentication.Client` | `app_authentication/models.py:8` | `created_at` + `updated_at` (`:24-25`) | `SiteAwareModel` |
| `webhooks.WebhookEndpoint` | `webhooks/models.py:48` | `created_at` + `updated_at` (`:73-74`) | `SiteAwareModel` |
| `webhooks.WebhookEvent` | `webhooks/models.py:366` | `created_at` (`:369`) only (immutable event record, no update expected) | `SiteAwareModel` |
| `webhooks.WebhookDelivery` | `webhooks/models.py:375` | `created_at` (`:392`) only, mutated repeatedly by retries with no `updated_at` | `SiteAwareModel` |
| `webhooks.WebhookSecret` | `webhooks/models.py:415` | `created_at` + `updated_at` (`:422-423`) | `SiteAwareModel` |
| `reports.GeneratedReport` | `reports/models.py:42` | `requested_at` (`auto_now_add`, `:67`), `started_at`, `finished_at` (`:68-69`) | `SiteAwareModel` |

### The backfill-honesty argument

A `created_at` added by migration after rows exist forces a choice for every pre-existing row: a
one-off default at migration time, or a nullable backfill with nothing in the row to backfill from.
Either way the column reads as a real historical fact but is not one, and there is no way to tell
which values are genuine from the data alone. `updated_at` does not have this problem: its contract is
"last touched," and a value stamped at the moment the column was added honestly means "not known to
have changed since." Nobody reads an `updated_at` as a claim about the distant past the way a
`created_at` implies row age. So a missing `created_at` is do-now wherever it can still be added before
real rows exist; a missing `updated_at` is do-later, with one condition below.

`ALTER TABLE ... RENAME COLUMN` and `RENAME CONSTRAINT` are catalog-only operations in Postgres: they
update `pg_attribute`/`pg_constraint` and take a brief lock, without rewriting table data, regardless of
row count. Renaming `registered_at` to `created_at`, or `unique_cohort_name_per_site` to something
accurate, costs the same today as after a million rows exist.

### Ranked: genuinely zero timestamp coverage today (do now)

Ranked by how much the absence costs, most severe first.

| Model | Why it ranks here | Judgement |
|---|---|---|
| `accounts.User` (`accounts/models.py:67-134`) | The most-referenced row in the schema (every FK in the system eventually points here) has no signup date, no way to answer "how old is this account." Nothing else in the row proxies for it. | Do now: add `created_at` |
| `content_base.BaseContent` subclasses (`Topic`, `Activity`, `Course`, `CoursePart`, `Form`, `FormPage`, `FormContent`, `FormQuestion`) | One field on one abstract base reaches all eight. Content is edited and re-imported via `content_engine/management/commands/content_save.py`, so "when was this last changed" is currently unanswerable and stays that way for anything imported before the field exists. | Do now: add to `BaseContent` |
| `content_engine.File`, `content_engine.ContentCollectionItem`, `form_engine.QuestionOption` | Same content-type family as above, but they extend `SiteAwareModel` directly, not `BaseContent`, so the fix above does not reach them. Easy to assume coverage is complete and miss these three. | Do now: add individually |
| `organisations.Organisation` | Small table, cheap, and "when was this org onboarded" is a real, low-effort question to be able to answer later. | Do now: add `created_at` |
| `learner_management.Cohort`, `CohortMembership` | Long-lived administrative objects with no creation record at all. | Do now: add `created_at` |
| `learner_management.CohortDeadline`, `LearnerDeadline`, `UserCohortDeadlineOverride` | Deadlines are disputable admin actions. "Was this deadline changed after it passed" needs `updated_at` specifically, not just `created_at`, since these rows are edited in place. | Do now: add `created_at` and `updated_at` |
| `accounts.SiteSignupPolicy` | Free and cheap, but low value: one row per site, rarely touched. Lowest priority in this list. | Do now, no urgency attached |
| `learner_progress.CourseFormAttempt` | Zero timestamps, but the sitting's real timestamp (`start_time`/`completed_time`) already lives one hop away on `form_progress` (`freedom_ls/form_engine/models.py:204,206`). The row itself is a pure join, so a `created_at` here would duplicate information already reachable, not recover lost information. | Lowest priority of the zero-coverage group; cheap to add, not clearly needed |

### An existing timestamp that is not what it looks like

`form_engine.QuestionAnswer.last_updated_time` (`form_engine/models.py:579`) is `auto_now=True` with no
paired `created_at`. `save_answers()` (`form_engine/models.py:286-307`) calls
`get_or_create()` then overwrites `text_answer`/`selected_options` and saves again on every visit to a
form page, so `last_updated_time` is rewritten on every edit and the original submission time is lost
the moment a learner revisits a page and changes an answer. This is not yet a backfill problem (no rows
exist), but it will become the same "unrecoverable once overwritten" shape as `created_at` the first
time a real answer gets edited twice. Cheap to fix now (add `created_at = models.DateTimeField(auto_now_add=True)`)
while there is nothing to lose.

### Where an existing domain name is correct and should not become `created_at`

| Model.field | Why it earns a name of its own |
|---|---|
| `LearnerCourseRegistration.registered_at`, `CohortCourseRegistration.registered_at` | Names "access granted," a domain event, not "row created." |
| `role_based_permissions.*.assigned_at` | Names "role assigned." For these models assignment and creation are the same instant, but the name still carries intent a bare `created_at` would not. |
| `accounts.LegalConsent.timestamp` | An append-only compliance record; "timestamp" reads correctly as "when this consent was recorded." |
| `learner_progress.TopicProgress.start_time`, `.last_accessed_time`, `.complete_time`; `CourseProgress.started_at`, `.last_accessed_time`, `.completed_time` | Attempt/registration-lifecycle semantics a bare created/updated pair would duplicate, not replace. `CourseProgress.created_at` and `.started_at` are already split and documented as non-interchangeable (`learner_progress/models.py:134-138`): `created_at` is the registration date, `started_at` is first content access. |
| `reports.GeneratedReport.requested_at` | Row-creation genuinely is the request event here, so this is closer to `created_at` wearing a label than the others above. Still a metadata-only rename if it ever moves. |

### Where the convention already reads right

`webhooks.WebhookEndpoint`/`WebhookSecret`, `course_applications.CourseApplication`,
`app_authentication.Client` (all `created_at` + `updated_at`), and `course_interest.CourseInterest`,
`learner_management.Learner`, `learner_management.RecommendedCourse` (all bare `created_at`) are the
pattern: use `created_at`/`updated_at` unless a domain name earns its keep, per the table above.

### Mixin placement

No abstract base in FLS carries timestamps today. `SiteAwareModel` (`site_aware_models/models.py:79-84`)
adds a UUID `id` on top of `SiteAwareModelBase`'s site FK, and every concrete model in the system
extends one of these two except `accounts.User` (extends the lower `SiteAwareModelBase` directly, no
UUID pk) and `role_based_permissions.SystemRoleAssignment` (a plain `models.Model`, deliberately not
site-aware, per its own docstring at `role_based_permissions/models.py:10-14`). Those two are exactly
the models with the least timestamp coverage.

Folding timestamps into `SiteAwareModel` itself would miss both, and would also force generic
`created_at`/`updated_at` onto models that already carry a correct domain-named timestamp
(`LegalConsent.timestamp`, `GeneratedReport.requested_at`), producing two fields that say the same thing.
The shape that reaches everything is a small standalone abstract mixin,
`class TimestampedModel(models.Model): created_at = ...; updated_at = ...; class Meta: abstract = True`,
with no site dependency, applied explicitly per model alongside whichever of `SiteAwareModel`,
`SiteAwareModelBase` or `models.Model` that model already uses. Django supports multiple abstract-base
inheritance without conflict, so `class User(SiteAwareModelBase, TimestampedModel, AbstractBaseUser, PermissionsMixin)`
and `class SystemRoleAssignment(TimestampedModel, models.Model)` both work. This is a one-time decision:
cheap now, and expensive to unwind once a dozen models have each grown their own copy-pasted pair of
fields.

### Does `updated_at` need backfilling?

No, for the reason given above: its semantics survive a late addition. But one FLS-specific trap makes
"add it whenever" not quite free. Role deactivation in `role_based_permissions` goes through
`QuerySet.update()`, not `.save()`:

```
role_based_permissions/utils.py:246,314,365   .update(is_active=False)
```

`auto_now=True` only fires on `.save()`. An `updated_at` added to `SystemRoleAssignment`,
`SiteRoleAssignment` or `ObjectRoleAssignment` would silently stop reflecting reality the first time a
role is deactivated through these call sites, unless they are changed to pass `updated_at=timezone.now()`
explicitly in the same `.update()` call. This is not a reason to defer adding the field. It is a reason
to land the field and the call-site fix in the same change, not the field alone. Every other reactivation
path checked (`learner_management.ensure_learner`, `learner_management/utils.py:96-101`) goes through
`update_or_create()`, which calls `.save()` and so would not have this problem.

## 2. Constraints

### `Cohort`'s constraint name

`Cohort`'s only constraint is `unique_cohort_name_per_site` (`learner_management/models.py:40-44`), but
its fields are `["site_id", "organisation", "name"]`. It scopes uniqueness to an organisation, not to a
site: two organisations in the same site can already have a cohort of the same name. The name should
read `unique_cohort_name_per_organisation`. Since `organisation` is itself a `SiteAwareModel`
(`organisations/models.py:58`) and already pins exactly one site, the `site_id` column in the constraint
is also redundant, though harmless. Renaming a constraint is catalog-only in Postgres at any table size:
do-later, no deadline attached.

### Which models scope their uniqueness by site, and which do not

Three models pair `user`/`learner` with `course`/`organisation` under a `UniqueConstraint`, and only one
of the three includes `site`:

| Model | Fields | Includes `site`? | Path |
|---|---|---|---|
| `course_applications.CourseApplication` | `site, user, course` | Yes | `course_applications/models.py:46-50` |
| `course_interest.CourseInterest` | `user, course` | No | `course_interest/models.py:41-44` |
| `learner_management.Learner` | `user, organisation` | No | `learner_management/models.py:73-76` |

The asymmetry is not reachable in practice for either omission. `accounts.User` is itself site-scoped
(`SiteAwareModelBase`), `content_engine.Course` is site-scoped (`SiteAwareModel`), and
`organisations.Organisation` is site-scoped, so a `CourseInterest` or `Learner` row can never legitimately
pair a user from one site with a course or organisation from another: the dropdowns and managers that
populate these rows are already site-filtered upstream. Adding `site` to `CourseInterest`'s and
`Learner`'s constraints would be belt-and-braces, not load-bearing. Worth doing for consistency the next
time either model's migration is touched anyway; not a reason to schedule one. Do-later.

### Three spellings of "the site field," one behaviour

`Meta.constraints` field lists reference `site` two different ways in FLS today, and once by omission:

| Spelling | Where | Example |
|---|---|---|
| `"site_id"` (the attname) | `learner_management` | `Cohort` (`:42`), `LearnerCourseRegistration` (`:123`), `CohortCourseRegistration` (`:149`) |
| `"site"` (the field name) | `course_applications`, `organisations`, `accounts.SiteSignupPolicy` | `CourseApplication` (`:48`), `Organisation` (`:97-101`), `SiteSignupPolicy` (`:152-153`) |
| omitted entirely | `course_interest`, `learner_management.Learner` | see table above |

`"site_id"` and `"site"` behave identically. Django's `Options._forward_fields_map`
(`django/db/models/options.py:634-660` in the installed package) indexes every field by both its `.name`
and its `.attname`, so `models.UniqueConstraint(fields=["site_id", ...])` resolves to the same `site`
field, and generates the same SQL, as `fields=["site", ...])`. The `0001_initial.py` migrations for
`learner_management` confirm this: Django accepted `"site_id"` in `fields=(...)` without complaint and
produced a normal constraint. This is not a bug, only an inconsistency in how the field is spelled at
the point of writing. The house rule should be to spell it `"site"`, the field name, since that is what
every other field reference in a constraint's field list already uses (nobody writes `"organisation_id"`
or `"cohort_id"` elsewhere in these same `Meta.constraints` blocks). Fixing the three existing
`"site_id"` usages is a docs-only, zero-risk rewrite of the migration state and does not require a
database migration at all, since the generated SQL does not change. Do-now as a house rule, do-whenever
for updating the three existing usages to match it.

### `unique_together` inventory

Eight model `Meta` blocks still use the legacy `unique_together` API where the rest of the codebase has
moved to named `Meta.constraints = [models.UniqueConstraint(...)]`:

| Model | Fields | Path |
|---|---|---|
| `content_engine.Topic` | `site, slug` | `content_engine/models/topics.py:16` |
| `content_engine.Activity` | `site, slug` | `content_engine/models/topics.py:31` |
| `content_engine.Course` | `site, slug` | `content_engine/models/courses.py:99` |
| `content_engine.CoursePart` | `site, slug` | `content_engine/models/courses.py:241` |
| `content_engine.File` | `site, file_path` | `content_engine/models/files.py:54` |
| `form_engine.Form` | `site, slug` | `form_engine/models.py:72` |
| `form_engine.QuestionAnswer` | `form_progress, question` | `form_engine/models.py:582` |
| `webhooks.WebhookSecret` | `site, name` | `webhooks/models.py:426` |

Functionally identical to `UniqueConstraint`, just unnamed, which means the database picks an
autogenerated constraint name instead of one under FLS's control. Converting these to named
`UniqueConstraint`s is a metadata-only migration (Postgres does not need to rebuild the underlying index
just because the constraint gained an explicit name via `ALTER TABLE ... RENAME CONSTRAINT`-style
handling in the migration). Do-later, batched with whatever else eventually touches these models: no
functional gain to converting them in isolation, and `content_engine`'s and `form_engine`'s content
models are exactly the models the timestamp mixin work above will touch anyway.

## 3. Indexes

Two real gaps were found by walking the query paths in `learner_progress/queries.py`,
`learner_management/queries.py`, `reports/indexes.py` and `educator_interface/views.py`. Every other
query checked in those paths is already covered:

- `learner_progress.TopicProgress` and `CourseFormAttempt` are queried by
  `(course_progress, collection_item)` (`educator_interface/views.py:432-436,444-448`), and both already
  carry that exact composite via a `UniqueConstraint`/`Index` (`learner_progress/models.py:94-98,275`).
  `CourseProgress` is queried by `(cohort_registration, learner)` / `(learner_registration, learner)`
  (`learner_management/queries.py:241-245`), which is exactly its own uniqueness constraint
  (`learner_progress/models.py:163-170`), and by `(learner, course)`, which has its own `Index`
  (`learner_progress/models.py:185`).
- `CohortDeadline`/`LearnerDeadline`/`UserCohortDeadlineOverride` lookups are always additionally scoped
  by an already-indexed FK first (`cohort_course_registration=selected_reg`,
  `educator_interface/views.py:497-499,515-518`).
- `reports.GeneratedReport.status` already carries `db_index=True` (`reports/models.py:61-66`).
- `role_based_permissions.ObjectRoleAssignment` already has the composite index its GFK lookups need
  (`role_based_permissions/models.py:112-115`).

| Gap | Where it's hot | Why it's harmless today | Judgement |
|---|---|---|---|
| `content_engine.ContentCollectionItem` has no composite index on `(collection_type, collection_id)` or `(child_type, child_id)`. Only `collection_type`/`child_type` are auto-indexed as FKs; `collection_id`/`child_id` are plain `UUIDField`s with no `db_index` (`content_engine/models/courses.py:274-292`) | `Course.children()` / `CoursePart.children()` (`content_engine/models/courses.py:192-221,254-264`), called on every course/part page render, and reused by the educator progress panel | The `content_type` half of the pair already narrows the scan; the table is one row per content placement, currently small | Do-later. `CREATE INDEX CONCURRENTLY` closes this against a populated table without meaningful lock contention |
| `webhooks.WebhookEndpoint.event_types__contains=[...]` (`webhooks/events.py:71`) is a JSON containment lookup on an un-indexed `JSONField(default=list)` (`webhooks/models.py:52`) | Runs on every outbound webhook event, matching subscribers by event type | Per-site endpoint counts are small (a handful of configured webhooks, not thousands) | Do-later. A GIN index add via `CREATE INDEX CONCURRENTLY` is the standard fix if this ever gets slow, and does not need to happen before deploy |

No index gap found in this unit's query paths rises to "materially cheaper before deploy than after."
Say so plainly rather than invent urgency: this section has no do-now items.

## 4. Field types

### `tags` should be an `ArrayField`, not a `JSONField`

`content_base.BaseContent.tags` (`content_base/models.py:22`) is a `JSONField` holding a list of
freeform strings, and it is used as an admin `list_filter` in four places:
`content_engine/admin.py:19,31,75,103`. Django's `list_filter` on a `JSONField` filters by exact value
of the whole field, not "contains this element," so filtering by tag in the admin today does not do what
a tag filter should. `Course.learning_outcomes`, in the same file family
(`content_engine/models/courses.py:69-76`), is already the correct type for exactly this shape:
`ArrayField(models.CharField(max_length=255), ...)`. Matching that precedent (`ArrayField(models.CharField(...))`,
or a real `Tag` model plus M2M if cross-content tag browsing is ever wanted) fixes the filter. The
field is otherwise unused outside the admin (checked repo-wide), so this is a pre-existing minor bug,
not a data-loss risk. Cheap to fix at either time since the field holds no real data yet. Do-later.

### JSONField inventory

| Field | Path | Genuinely schemaless, or a shape waiting to be a table? | Judgement |
|---|---|---|---|
| `content_engine.Course.access_config` | `content_engine/models/courses.py:41-49` | Genuinely schemaless by design. The field's own docstring says no view, template or utility may read it directly; the shape is owned entirely by whichever `COURSE_ACCESS_BACKEND` is configured, validated per-backend by a dedicated system check (`freedom_ls/course_access/checks.py`). Normalising this into columns would force one backend's shape to be canonical, defeating the pluggability the field exists for. | Won't-do |
| `form_engine.FormProgress.scores` | `form_engine/models.py:207-209` | Genuinely polymorphic. Shape depends on `Form.strategy`: a flat `{score, max_score}` for `QUIZ` (`compute_quiz_scores`, `:448-482`) vs. a nested category tree for `CATEGORY_VALUE_SUM` (`score_category_value_sum`, `:320-446`). Never queried at the database level, checked repo-wide; always read as `fp.scores.get(...)` in Python and always recomputed from `QuestionAnswer` rows, so it is derived/cache data, not a system of record. | Won't-do |
| `content_base.BaseContent.meta` | `content_base/models.py:19-21` | Optional freeform metadata. No read site anywhere outside the admin form (`content_engine/admin.py`), checked repo-wide. Currently write-only. | Won't-do; revisit only once something reads it |
| `content_base.BaseContent.tags` | `content_base/models.py:22` | See above: a fixed shape (list of short strings) that already has the correct precedent field one line away. | Do-later, convert to `ArrayField` |
| `content_engine.ContentCollectionItem.overrides` | `content_engine/models/courses.py:296-300` | Written by the content-import pipeline (`content_engine/management/commands/content_save.py:687`) but never read anywhere. An unimplemented placeholder for per-placement overrides. | Won't-do; nothing to normalise until a reader exists |
| `accounts.SiteSignupPolicy.additional_registration_forms` | `accounts/models.py:148` | An ordered list of dotted import paths to `Form` subclasses, actively used across `middleware.py`, `views.py`, `registration_forms.py`. Small, ordered, always read/written whole. Genuine configuration, not data. | Won't-do |
| `webhooks.WebhookEndpoint.event_types` | `webhooks/models.py:52` | A small, bounded list of event-type strings per endpoint, queried via `__contains` (see §3). Right-sized for JSON; a GIN index, not a schema change, is the fix if it ever needs one. | Won't-do |
| `webhooks.WebhookEvent.payload` | `webhooks/models.py:368` | The event payload itself, inherently variable shape across event types, read/replayed whole, never queried into. | Won't-do |

### `default_auto_field` is consulted in exactly two of nineteen apps

`default_auto_field = "django.db.models.BigAutoField"` is set in 19 `apps.py` files. It only takes
effect for a model that declares no explicit primary key. Every concrete model in FLS extends
`site_aware_models.SiteAwareModel`, which declares its own `id = models.UUIDField(primary_key=True, ...)`
(`site_aware_models/models.py:80`), except two:

- `accounts.User` extends the lower `SiteAwareModelBase`, which has no pk field of its own
  (`site_aware_models/models.py:53-76`), and declares no `id` field itself
  (`accounts/models.py:67-134`). Django fills in `id` using `AccountsConfig.default_auto_field`
  (`accounts/apps.py:5`), confirmed by the generated migration:
  `accounts/migrations/0001_initial.py:21` shows `models.BigAutoField(...)` for `User.id`.
- `role_based_permissions.SystemRoleAssignment` is a plain `models.Model` with no explicit pk
  (`role_based_permissions/models.py:9-43`). Django fills in `id` from
  `RoleBasedPermissionsConfig.default_auto_field` (`role_based_permissions/apps.py:5`).

Every other `apps.py` carrying the setting (`app_authentication`, `base`, `content_base`,
`content_engine`, `educator_interface`, `form_engine`, `learner_interface`, `learner_management`,
`learner_progress`, `markdown_rendering`, `organisations`, `panel_framework`, `qa_helpers`, `reports`,
`site_aware_models`, `webhooks`, `xapi_learning_record_store`) either has no concrete models at all, or
every concrete model extends `SiteAwareModel` with its explicit UUID pk, so the setting is never read.
The house rule: `default_auto_field` only matters for a model that does not extend `SiteAwareModel`
(directly or via `SiteAwareModelBase` with its own explicit pk). Do not add or "fix" this setting out of
habit; it does nothing on a `SiteAwareModel`-rooted app.

status: ok
