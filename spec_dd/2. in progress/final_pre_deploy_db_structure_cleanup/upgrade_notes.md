---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/data-table.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/cohort_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/data-table-cells/learner_courses.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS  # hard: add "freedom_ls.course_recommendations", drop "freedom_ls.app_authentication"
  - SILENCED_SYSTEM_CHECKS  # hard if you silence any icons check: the ids were renumbered
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: final_pre_deploy_db_structure_cleanup

This is the last cut that treats FLS's database structure as changeable. Every migration in the
repo was deleted and regenerated as a single `0001_initial` per app, four tables were renamed by an
app-label change, one model moved to a new app, and three fields were renamed. **No data survives
this upgrade.** It rests on the repo owner's confirmation that no downstream project has run a
`migrate` it intends to keep. If yours has, stop and talk to us before pulling.

Once you have migrated against this version, the usual rule is back: only ordinary forward
migrations from here.

## Breaking changes

### Migration history is replaced wholesale

Every app that owns migrations now has exactly one file, `0001_initial`, regenerated from current
model state. Your `django_migrations` table records files that no longer exist, so `migrate` cannot
move forward from it. The recovery is to drop the tables and the history rows and migrate again. See
Manual steps.

### Four tables are renamed by app-label changes

| Was | Now |
| --- | --- |
| `webhooks_webhookendpoint` | `freedom_ls_webhooks_webhookendpoint` |
| `webhooks_webhookevent` | `freedom_ls_webhooks_webhookevent` |
| `webhooks_webhookdelivery` | `freedom_ls_webhooks_webhookdelivery` |
| `webhooks_webhooksecret` | `freedom_ls_webhooks_webhooksecret` |

`freedom_ls.webhooks` now declares `label = "freedom_ls_webhooks"` and `freedom_ls.health` declares
`label = "freedom_ls_health"` (no models, no tables). Every FLS app label is now prefixed
`freedom_ls_` except `icons`, which stays bare because it is on its way out of the repo as
`django_semantic_iconify`. The rules are written up in `docs/app_conventions.md`.

If you reference a webhook model by label, in a `ContentType` lookup, a permission codename, a
`makemigrations` dependency or raw SQL, update the string. Stale `django_content_type` and
`auth_permission` rows for the old labels have to go too, along with any `guardian` object
permissions that point at them.

### `RecommendedCourse` moved to its own app

It is now `freedom_ls.course_recommendations`, label `freedom_ls_course_recommendations`, table
`freedom_ls_course_recommendations_recommendedcourse`. Add `"freedom_ls.course_recommendations"` to
`INSTALLED_APPS`. Import paths:

| Was | Now |
| --- | --- |
| `freedom_ls.learner_management.models.RecommendedCourse` | `freedom_ls.course_recommendations.models.RecommendedCourse` |
| `freedom_ls.learner_management.factories.RecommendedCourseFactory` | `freedom_ls.course_recommendations.factories.RecommendedCourseFactory` |
| `freedom_ls.learner_interface.utils.get_recommended_courses` | `freedom_ls.course_recommendations.queries.get_recommended_courses` |

### `app_authentication` is deleted

`freedom_ls/app_authentication/` and its `Client` model are gone. It was never installed and owned no
tables, so nothing to migrate. Remove the `INSTALLED_APPS` line if you uncommented it. Its `api_key`
was a plaintext unique `CharField`; if you built on it, `webhooks.WebhookSecret` and its
`EncryptedTextField` are the pattern to copy instead.

### `collection` is now `course` on three models

`LearnerCourseRegistration`, `CohortCourseRegistration` and `RecommendedCourse` each had a
`collection` FK to `Course`. It is `course` now, on the column, the attribute, the ORM lookup and the
constraint field lists. Reverse accessors (`learner_registrations`, `cohort_registrations`,
`recommendations`) are unchanged.

`ContentCollectionItem.collection` did not change. It is the generic FK over `Course`/`CoursePart`
and is the only thing the word `collection` names now. The two spellings are identical in source, so
a blind find-and-replace will break your content code. Triage per call site by what the receiver is.

Every derived form needs the rename too: `collection_id`, `collection=` keyword arguments,
`collection__` traversals, and the field named as a string in `select_related`, `prefetch_related`,
`values`, `only` and `order_by`.

### `UserCohortDeadlineOverride` is now `LearnerCohortDeadlineOverride`

Its only person-identifying field is `learner`, so the class name was wrong. The constraint
`unique_user_cohort_override_per_item` is now `unique_learner_cohort_override_per_item`, the factory
is `LearnerCohortDeadlineOverrideFactory`, and the table is
`freedom_ls_learner_management_learnercohortdeadlineoverride`.

### Deletion is now blocked in places it used to cascade

| Field | Was | Now |
| --- | --- | --- |
| `QuestionAnswer.question` | CASCADE | PROTECT |
| `LearnerCourseRegistration.course` | CASCADE | PROTECT |
| `CohortCourseRegistration.course` | CASCADE | PROTECT |
| `CohortDeadline.content_type` | CASCADE | SET_NULL |
| `LearnerDeadline.content_type` | CASCADE | SET_NULL |
| `LearnerCohortDeadlineOverride.content_type` | CASCADE | SET_NULL |
| `WebhookDelivery.endpoint` | CASCADE | SET_NULL, `null=True` |

Deleting a `FormQuestion` that has any answer raises `ProtectedError`, as does deleting a `Course`
that has any registration. Code that deletes questions, forms or courses needs to handle
`ProtectedError` or clear the dependent rows first. `manage.py danger_content_delete` already does
the latter in the right order.

`SET_NULL` on the deadline generic FKs leaves `object_id` populated while `content_type` goes null.
That half-nulled row reads as a whole-course deadline: `clean()` now keys on `content_type is None`
alone, and `content_item` resolves to `None`. If you subclassed a deadline model or wrote your own
`clean()`, match that.

`WebhookDelivery.endpoint` can be null, so `delivery.endpoint.url` is no longer safe. The new
non-null `endpoint_url` field records where the send was aimed and survives the endpoint's deletion.
Anything creating a `WebhookDelivery` directly must pass `endpoint_url`; `dispatch_event` fills it
from `WebhookEndpoint.url`. A delivery whose endpoint is gone is marked `permanent_failure` with
"Endpoint no longer exists." rather than crashing.

### Content models cannot be deleted through the Django admin

`has_delete_permission` returns `False` on `TopicAdmin`, `ActivityAdmin`, `CourseAdmin`,
`CoursePartAdmin`, `ContentCollectionItemAdmin`, `FileAdmin`, `FormAdmin`, `FormPageAdmin`,
`FormContentAdmin`, `FormQuestionAdmin` and `QuestionOptionAdmin`, and `can_delete = False` on every
content inline. Add and change still work. The reachable route was
`QuestionAnswer.selected_options`, whose auto-generated through table drops join rows silently when a
`QuestionOption` goes; no `on_delete` closes that. If your project relied on admin deletion of
content, use `manage.py danger_content_delete` or override `has_delete_permission` back on your own
subclass.

### `tags` is a Postgres array, not JSON

`content_base.BaseContent.tags` is now
`ArrayField(models.CharField(max_length=255), blank=True, default=list)`, reaching `Topic`,
`Activity`, `Course`, `CoursePart`, `Form`, `FormPage`, `FormContent` and `FormQuestion`. It is
non-nullable, so `tags` is never `None` and `tags__isnull` checks are dead. `tags__contains` now
takes a list, not a JSON value. There is no data migration: PostgreSQL has no implicit `jsonb` to
`text[]` cast, so the migration drops the column and adds it back.

The front matter schema follows. `tags` defaults to `[]` instead of `None`, and a bare `tags:` key
that YAML parses as `None` is coerced to `[]`.

The content admins swapped `list_filter = ("tags",)` for `ContentTagListFilter` from
`freedom_ls.content_base.admin_filters`, which lists individual tags instead of whole array values.

### `QuestionAnswer.last_updated_time` is gone

| Was | Now |
| --- | --- |
| `QuestionAnswer.last_updated_time` | `QuestionAnswer.updated_at` |

`FormProgress.last_updated_time` is a different model and is unchanged.

### Timestamps everywhere, from a new mixin

`freedom_ls.site_aware_models.models.TimestampedModel` is a new abstract model carrying
`created_at` (`auto_now_add`) and `updated_at` (`auto_now`). It is now mixed into `accounts.User`,
`accounts.SiteSignupPolicy`, `content_base.BaseContent`, `content_engine.File`,
`content_engine.ContentCollectionItem`, `form_engine.QuestionOption`, `form_engine.QuestionAnswer`,
`organisations.Organisation`, `learner_management.Cohort`, `CohortMembership`, `CohortDeadline`,
`LearnerDeadline`, `LearnerCohortDeadlineOverride` and `learner_progress.CourseFormAttempt`.

`SystemRoleAssignment`, `SiteRoleAssignment` and `ObjectRoleAssignment` keep `assigned_at` and gain a
bare `updated_at`. `auto_now` does not fire on `QuerySet.update()`, so the three deactivation helpers
in `role_based_permissions/utils.py` now pass `updated_at=timezone.now()` explicitly. Any code of
yours that deactivates roles with `.update()` needs the same.

Mixing in `TimestampedModel` adds two columns to models you may have subclassed. If you already
declared `created_at` or `updated_at` on a subclass, Django will now raise a clash.

### Uniqueness is site-scoped on `Learner` and `CourseInterest`

| Constraint | Was | Now |
| --- | --- | --- |
| `unique_learner_per_organisation` | `(user, organisation)` | `(site, user, organisation)` |
| `unique_course_interest` | `(user, course)` | `(site, user, course)` |
| `unique_cohort_name_per_site` on `Cohort` | `(site_id, organisation, name)` | renamed `unique_cohort_name_per_organisation`, fields `(site, organisation, name)` |

Both scopings are looser than before, so nothing that validated previously stops validating. The
`Cohort` rename matters if you reference the constraint by name.

All eight `unique_together` blocks became named `UniqueConstraint`s. Constraint names, in case you
reference them: `unique_topic_slug_per_site`, `unique_activity_slug_per_site`,
`unique_course_slug_per_site`, `unique_course_part_slug_per_site`, `unique_file_path_per_site`,
`unique_form_slug_per_site`, `one_answer_per_question_per_form_progress`,
`unique_webhook_secret_name_per_site`.

`"site"` is now the house spelling in every `Meta.constraints` entry; `"site_id"` appears nowhere.
That spelling has a consequence worth knowing if you write your own site-scoped constraints:
`SiteAwareModelAdmin` excludes `site` from admin forms, and `UniqueConstraint.validate()` abandons a
constraint the moment one of its fields is excluded. So a constraint spelled `"site"` is *not*
checked in the admin unless the form subclasses
`freedom_ls.site_aware_models.forms.ConstraintValidationFormMixin` and names `site` in
`constraint_fields`. FLS wired that onto the `Cohort`, `Learner`, `LearnerCourseRegistration`,
`CohortCourseRegistration`, `CourseInterest`, `File` and `WebhookSecret` admins, and onto
`educator_interface.forms.CohortForm`. Do the same on any admin form of yours over these models, or a
duplicate submits as a 500 instead of a field error.

`WebhookSecretForm` lost its hand-rolled `clean_name`; the constraint plus the mixin now do that
work.

### System check ids under `icons` were renumbered

| Was | Now |
| --- | --- |
| `freedom_ls.E001` … `freedom_ls.E007` | `icons.E001` … `icons.E007` |
| `freedom_ls.W001` | `icons.W001` |

The house rule is that a check id's label segment equals the registering app's own `AppConfig.label`,
and the `icons` app's label is `icons`. If you have any of the old ids in `SILENCED_SYSTEM_CHECKS`,
that entry now silences nothing and the check will fire. This is the quiet one: silencing a
non-existent id is not an error, so nothing tells you.

### Python API moves

| Was | Now |
| --- | --- |
| `freedom_ls.learner_management.utils.calculate_course_progress_percentage` | `freedom_ls.learner_progress.utils.calculate_course_progress_percentage` |

Signature unchanged. `is_registered_for_course` and `ensure_learner` stay in
`learner_management.utils`.

### Templates

The five templates in `changed_template_paths` changed only where they read a registration's or
recommendation's course: `registration.collection` is `registration.course`, `reg.collection` is
`reg.course`, `recommendation.collection` is `recommendation.course`. No markup or Tailwind classes
changed, so there is no CSS rebuild. If you have overridden any of them, apply the same rename.

### New indexes

`ContentCollectionItem` gains `cci_collection_idx` on `(collection_type, collection_id)` and
`cci_child_idx` on `(child_type, child_id)`. `WebhookEndpoint` gains `webhook_event_types_gin`, a
`jsonb_path_ops` GIN index on `event_types`, for the containment lookup every outbound event runs.
Both are created by the initial migration. Nothing to do.

### Admin section headings

Every FLS `AppConfig` now sets `verbose_name`, so the admin index reads "Webhooks" and "Course
recommendations" rather than "Freedom_Ls_Webhooks" and "Freedom_Ls_Course_Recommendations". If you
set `verbose_name` on an FLS app config yourself as a workaround, yours still wins; you can drop it.

## Manual steps

1. **Update `INSTALLED_APPS`.** Add `"freedom_ls.course_recommendations"`. Remove
   `"freedom_ls.app_authentication"` if it is there, commented or not.
2. **Check `SILENCED_SYSTEM_CHECKS`** for `freedom_ls.E001` to `E007` or `freedom_ls.W001` and
   rewrite them as `icons.*`. Then run `uv run manage.py check` and confirm nothing new fires.
3. **Rebuild the database.** On a development database, dropping it and running
   `uv run manage.py migrate` from scratch is the shortest path. On a database you want to keep the
   non-FLS parts of:
   - drop every `freedom_ls_*` table, plus the old `webhooks_*` tables;
   - `DELETE FROM django_migrations WHERE app LIKE 'freedom_ls_%' OR app = 'webhooks';`
   - clear the rows that point at the old content types before the content types themselves, or the
     foreign keys will refuse the delete: any `guardian` object-permission rows first, then
     `DELETE FROM auth_permission WHERE content_type_id IN (SELECT id FROM django_content_type WHERE
     app_label LIKE 'freedom_ls_%' OR app_label = 'webhooks');`, then the same `WHERE` against
     `django_content_type`;
   - run `uv run manage.py migrate`.
4. **Rename `collection` to `course`** everywhere it refers to a registration's or recommendation's
   course: attributes, `collection_id`, `collection=` kwargs, `collection__` lookups, and the field
   named as a string in `select_related`, `prefetch_related`, `values`, `only` and `order_by`. Leave
   `ContentCollectionItem.collection` alone.
5. **Rename `UserCohortDeadlineOverride`** to `LearnerCohortDeadlineOverride`, and the factory and
   constraint name with it.
6. **Update the moved imports** in the two tables above: `RecommendedCourse`, its factory,
   `get_recommended_courses`, and `calculate_course_progress_percentage`.
7. **Re-apply your customisations** to the templates in `changed_template_paths`.
8. **Handle `ProtectedError`** anywhere you delete a `FormQuestion`, a `Form` or a `Course`, or clear
   the dependent answers and registrations first.
9. **Update webhook code** that reads `delivery.endpoint` without a null check, and pass
   `endpoint_url` anywhere you build a `WebhookDelivery` yourself.
10. **Update `tags` code.** Drop `is None` and `__isnull` handling, and pass a list to
    `tags__contains`.
11. **Update code that reads `QuestionAnswer.last_updated_time`** to `updated_at`.
12. **Update role deactivation done with `.update()`** to pass `updated_at=timezone.now()`.
13. **Add `ConstraintValidationFormMixin`** with `constraint_fields = ("site",)` to any admin form of
    your own over `Cohort`, `Learner`, `LearnerCourseRegistration`, `CohortCourseRegistration`,
    `CourseInterest`, `File` or `WebhookSecret`.
14. **Update label strings** in any `ContentType` lookup, permission codename or raw SQL naming
    `webhooks` or `health`.
