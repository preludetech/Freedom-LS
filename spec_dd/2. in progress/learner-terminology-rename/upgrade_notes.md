---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/learner_interface/templates/learner_interface/dashboard.html
  - freedom_ls/learner_interface/templates/learner_interface/all_courses.html
  - freedom_ls/learner_interface/templates/learner_interface/course_detail.html
  - freedom_ls/learner_interface/templates/learner_interface/course_finish.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html
  - freedom_ls/learner_interface/templates/learner_interface/course_form_page.html
  - freedom_ls/learner_interface/templates/learner_interface/course_topic.html
  - freedom_ls/learner_interface/templates/learner_interface/_course_base.html
  - freedom_ls/learner_interface/templates/learner_interface/_exam_runner_base.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/anonymous_hero.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/card_title_link.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_card.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_details_link.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_list.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_row_list.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_status_eyebrow.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/course_toc_header.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/exam_meta_grid.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/exam_previous_attempts.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/exam_score_ring.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/form_progress_scores.html
  - freedom_ls/learner_interface/templates/learner_interface/partials/player_breadcrumbs.html
  - freedom_ls/learner_interface/templates/cotton/course-card-shell.html
  - freedom_ls/learner_interface/templates/cotton/course-progress-bar.html
  - freedom_ls/learner_interface/templates/cotton/course-row-shell.html
  - freedom_ls/learner_interface/templates/cotton/player-nav.html
  - freedom_ls/base/templates/cotton/data-table.html
  - freedom_ls/course_applications/templates/course_applications/apply.html
  - freedom_ls/course_applications/templates/course_applications/application_status.html
  - freedom_ls/course_applications/templates/course_applications/partials/dashboard_applications.html
  - freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS   # freedom_ls.student_management -> freedom_ls.learner_management
  - INSTALLED_APPS   # freedom_ls.student_progress -> freedom_ls.learner_progress
  - INSTALLED_APPS   # freedom_ls.student_interface -> freedom_ls.learner_interface
  - TEMPLATES[0]["OPTIONS"]["context_processors"]   # freedom_ls.student_management.context_processors.can_access_educator_interface -> freedom_ls.learner_management.context_processors.can_access_educator_interface
  - ROOT_URLCONF include   # include("freedom_ls.student_interface.urls") -> include("freedom_ls.learner_interface.urls")
  - sitemaps   # config/sitemaps.py: "student_interface:courses"/"student_interface:course_detail" -> "learner_interface:..."
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: learner-terminology-rename

FLS has standardised on **learner**. The word "student" is gone from the codebase: three apps are
renamed, and with them every import path, app label, database table, permission string, URL name,
template path and static path they own.

**This is the most breaking change FLS has shipped.** There are no compatibility shims and there
will not be any — app labels and permission strings cannot be aliased in Django at all, and
partial shims for the rest would cover under half the surface while making the break quieter and
therefore worse. The break is deliberately loud everywhere it can be. Two places where it is
**silent** are called out below (theme overrides, and the conformance suite); read those two
sections even if you skim the rest.

| Old | New |
| --- | --- |
| `freedom_ls.student_management` | `freedom_ls.learner_management` |
| `freedom_ls.student_progress` | `freedom_ls.learner_progress` |
| `freedom_ls.student_interface` | `freedom_ls.learner_interface` |

**Before you go any further: does your project have a database you cannot throw away?**

If it does, stop and read "9. There is no safe simultaneous app-label rename for an already-migrated
database" and manual step 5 first. FLS ships **no** data migration for this, because none can be
written safely — Django has no `RenameApp` operation. What FLS ships instead is a recipe you run
yourself, once, at a moment you control.

If your database is disposable (dev/CI only, rebuilt from scratch), drop it, recreate it and
migrate. That is the supported path and the one FLS itself takes.

---

## Breaking changes

### 1. Find-and-replace table

This is the whole mechanical surface. Every row is a **case-sensitive** substring replacement.
Do the three cases as separate passes — `Student`→`Learner`, `student`→`learner`,
`STUDENT`→`LEARNER` — and **never** run a case-insensitive replace over your tree; it will eat
prose you meant to keep and it will not tell you.

#### Python dotted paths

| Old | New |
| --- | --- |
| `freedom_ls.student_management` | `freedom_ls.learner_management` |
| `freedom_ls.student_progress` | `freedom_ls.learner_progress` |
| `freedom_ls.student_interface` | `freedom_ls.learner_interface` |
| `freedom_ls.student_interface.urls` | `freedom_ls.learner_interface.urls` |
| `freedom_ls.student_interface.apps.StudentInterfaceConfig` | `freedom_ls.learner_interface.apps.LearnerInterfaceConfig` |
| `freedom_ls.student_management.config` | `freedom_ls.learner_management.config` |
| `freedom_ls.student_management.context_processors.can_access_educator_interface` | `freedom_ls.learner_management.context_processors.can_access_educator_interface` |
| `freedom_ls.student_management.utils` | `freedom_ls.learner_management.utils` |
| `freedom_ls.student_management.queries` | `freedom_ls.learner_management.queries` |
| `freedom_ls.student_management.factories` | `freedom_ls.learner_management.factories` |
| `freedom_ls.student_management.deadline_utils` | `freedom_ls.learner_management.deadline_utils` |
| `freedom_ls.student_progress.models` | `freedom_ls.learner_progress.models` |

Submodule names inside the three apps are otherwise unchanged — only the package segment moves.

#### App labels

| Old | New |
| --- | --- |
| `freedom_ls_student_management` | `freedom_ls_learner_management` |
| `freedom_ls_student_progress` | `freedom_ls_learner_progress` |
| `freedom_ls_student_interface` | `freedom_ls_learner_interface` |

These appear in permission strings, `ContentType.app_label`, migration dependencies, admin URL
names (`admin:freedom_ls_student_management_cohort_changelist` and friends) and every default
table name.

#### `AppConfig` and `AppSettings` class names

| Old | New | File |
| --- | --- | --- |
| `StudentManagementConfig(AppConfig)` | `LearnerManagementConfig` | `learner_management/apps.py` |
| `StudentProgressConfig(AppConfig)` | `LearnerProgressConfig` | `learner_progress/apps.py` |
| `StudentInterfaceConfig(AppConfig)` | `LearnerInterfaceConfig` | `learner_interface/apps.py` |
| `StudentManagementConfig(AppSettings)` | `LearnerManagementConfig` | `learner_management/config.py` |

Note the name collision is genuine and pre-existing: the app defined `StudentManagementConfig`
twice, for unrelated purposes. Both renamed. See section 7 for the `config.py` one.

#### Models, fields, constraints, factories, admin

| Old | New |
| --- | --- |
| `StudentDeadline` | `LearnerDeadline` |
| `StudentDeadline.student_course_registration` | `LearnerDeadline.learner_course_registration` |
| constraint `unique_student_deadline_per_item` | `unique_learner_deadline_per_item` |
| `StudentDeadlineFactory` | `LearnerDeadlineFactory` |
| `StudentDeadlineInline` | `LearnerDeadlineInline` |
| `StudentDeadlineAdmin` | `LearnerDeadlineAdmin` |
| `_resolve_student_deadline` | `_resolve_learner_deadline` |
| `_resolve_student_deadline_from_index` | `_resolve_learner_deadline_from_index` |

Any queryset traversal through the FK moves with it:
`student_course_registration__user` → `learner_course_registration__user`, and so on.

#### URL names

`app_name` moved from `student_interface` to `learner_interface`. Every name under it is
otherwise unchanged:

| Old | New |
| --- | --- |
| `student_interface:dashboard` | `learner_interface:dashboard` |
| `student_interface:courses` | `learner_interface:courses` |
| `student_interface:course_detail` | `learner_interface:course_detail` |
| `student_interface:course_home` | `learner_interface:course_home` |
| `student_interface:initiate_course_access` | `learner_interface:initiate_course_access` |
| `student_interface:view_course_item` | `learner_interface:view_course_item` |
| `student_interface:form_start` | `learner_interface:form_start` |
| `student_interface:form_fill_page` | `learner_interface:form_fill_page` |
| `student_interface:course_form_complete` | `learner_interface:course_form_complete` |
| `student_interface:form_submit_and_exit` | `learner_interface:form_submit_and_exit` |
| `student_interface:course_finish` | `learner_interface:course_finish` |

A missed `reverse()` or `{% url %}` raises `NoReverseMatch`. That is the loud, easy half.

**Learner-facing URL *paths* are byte-identical.** No path segment ever contained the word — only
the namespace did. Bookmarks, external links, sitemaps entries and analytics paths for the learner
interface all still resolve to the same URLs. Exactly one URL in the whole rename is requested
differently by a browser; see section 3.

#### Template paths

| Old | New |
| --- | --- |
| `student_interface/<name>.html` | `learner_interface/<name>.html` |
| `student_interface/partials/<name>.html` | `learner_interface/partials/<name>.html` |

Full list of moved files in `changed_template_paths` above. Cotton component **names** are
unchanged (`<c-course-card-shell>`, `<c-course-progress-bar>`, `<c-course-row-shell>`,
`<c-player-nav>`) — only the directory they live in moved, from
`freedom_ls/student_interface/templates/cotton/` to
`freedom_ls/learner_interface/templates/cotton/`.

#### Static paths

| Old | New |
| --- | --- |
| `student_interface/js/alpine-components.js` | `learner_interface/js/alpine-components.js` |

i.e. `{% static 'student_interface/js/alpine-components.js' %}` →
`{% static 'learner_interface/js/alpine-components.js' %}`.

#### Permission strings

| Old prefix | New prefix |
| --- | --- |
| `freedom_ls_student_management.*` | `freedom_ls_learner_management.*` |
| `freedom_ls_student_progress.*` | `freedom_ls_learner_progress.*` |

Four codenames are **deleted, not renamed** — see section 6.

#### Role key

| Old | New |
| --- | --- |
| role key `"student"` | `"learner"` |
| `display_name="Student"` | `display_name="Learner"` |

#### Database table names

| Old | New |
| --- | --- |
| `freedom_ls_student_management_cohort` | `freedom_ls_learner_management_cohort` |
| `freedom_ls_student_management_cohortmembership` | `freedom_ls_learner_management_cohortmembership` |
| `freedom_ls_student_management_usercourseregistration` | `freedom_ls_learner_management_usercourseregistration` |
| `freedom_ls_student_management_cohortcourseregistration` | `freedom_ls_learner_management_cohortcourseregistration` |
| `freedom_ls_student_management_cohortdeadline` | `freedom_ls_learner_management_cohortdeadline` |
| `freedom_ls_student_management_studentdeadline` | `freedom_ls_learner_management_learnerdeadline` |
| `freedom_ls_student_management_usercohortdeadlineoverride` | `freedom_ls_learner_management_usercohortdeadlineoverride` |
| `freedom_ls_student_management_recommendedcourse` | `freedom_ls_learner_management_recommendedcourse` |
| `freedom_ls_student_progress_formprogress` | `freedom_ls_learner_progress_formprogress` |
| `freedom_ls_student_progress_topicprogress` | `freedom_ls_learner_progress_topicprogress` |
| `freedom_ls_student_progress_courseprogress` | `freedom_ls_learner_progress_courseprogress` |
| `freedom_ls_student_progress_questionanswer` | `freedom_ls_learner_progress_questionanswer` |
| `freedom_ls_student_progress_questionanswer_selected_options` | `freedom_ls_learner_progress_questionanswer_selected_options` |

Note the double rename on `studentdeadline` → `learnerdeadline`: the app label *and* the model
name moved.

#### Template-context and DOM keys

| Old | New |
| --- | --- |
| `student_selected` (key in `FormProgress.get_incorrect_quiz_answers()` dicts) | `learner_selected` |
| `data-testid="student-answer-<id>"` | `data-testid="learner-answer-<id>"` |

If you override `learner_interface/course_form_complete.html`, or select on that test id in your
own browser tests, both must change.

---

### 2. `INSTALLED_APPS`, context processors, URLconf and sitemaps

If you maintain your own `config/settings_base.py` and `config/urls.py` (the concrete-project
template does), these are the four edits:

```python
# config/settings_base.py — OLD
INSTALLED_APPS = [
    ...
    "freedom_ls.student_management",
    "freedom_ls.student_progress",
    ...
    "freedom_ls.student_interface",
]
TEMPLATES = [{
    "OPTIONS": {"context_processors": [
        ...
        "freedom_ls.student_management.context_processors.can_access_educator_interface",
    ]},
}]
```

```python
# config/settings_base.py — NEW
INSTALLED_APPS = [
    ...
    "freedom_ls.learner_management",
    "freedom_ls.learner_progress",
    ...
    "freedom_ls.learner_interface",
]
TEMPLATES = [{
    "OPTIONS": {"context_processors": [
        ...
        "freedom_ls.learner_management.context_processors.can_access_educator_interface",
    ]},
}]
```

```python
# config/urls.py — OLD
path("", include("freedom_ls.student_interface.urls")),

# config/urls.py — NEW
path("", include("freedom_ls.learner_interface.urls")),
```

```python
# config/sitemaps.py — OLD
return ["student_interface:courses"]
reverse("student_interface:course_detail", kwargs={"course_slug": obj.slug})

# config/sitemaps.py — NEW
return ["learner_interface:courses"]
reverse("learner_interface:course_detail", kwargs={"course_slug": obj.slug})
```

The `learner_interface` include must stay **after** `robots.txt` and `sitemap.xml`, as before — it
is still the catch-all.

---

### 3. One educator URL segment changes; learner URLs do not

The educator interface's panel key `students` became `learners`. Because panel keys are URL
segments, the HTMX endpoints move:

```
OLD  …/educator/organisations/<slug>/cohorts/<pk>/__tabs/details/__panels/students
NEW  …/educator/organisations/<slug>/cohorts/<pk>/__tabs/details/__panels/learners

OLD  …/educator/organisations/<slug>/courses/<pk>/__panels/students
NEW  …/educator/organisations/<slug>/courses/<pk>/__panels/learners
```

**This is the only URL in the entire rename that a browser actually requests differently.**
Everything else that moved is a URL *name*, resolved server-side. If you have hard-coded either of
those panel URLs — in a template, a test, or a monitoring check — update it. If you registered your
own panel under the key `students` on a cohort or course config, rename the key to match or your
panel and FLS's will collide.

To repeat the other half plainly: **every learner-facing URL path is byte-identical after this
upgrade.** `/`, `/courses/`, `/courses/<slug>/`, `/courses/<slug>/detail/`, `/courses/<slug>/<n>/`
and the rest are unchanged. Only their `reverse()` names moved.

---

### 4. Template and static paths moved — theme overrides fail **silently**

Everything else in this document fails loudly. This one does not.

FLS themes shadow templates **by path**: a theme file wins whenever it exists at the matching
relative path, and otherwise falls through to the app's own template. There is no registry, no
declaration, and no validation. So a theme directory that no longer matches any FLS template path
is not an error — it is simply never consulted.

FLS's own theming documentation used a `student_interface` path as its canonical Tier-3 worked
example:

```
themes/my-theme/templates/student_interface/partials/course_card_registered.html
```

**Any downstream theme that followed FLS's documentation has a `templates/student_interface/`
directory.** After this upgrade that directory stops being found. Nothing raises, nothing logs,
no check fails — the base FLS template renders instead and your customisation quietly disappears.

```
OLD  themes/<your-theme>/templates/student_interface/...
NEW  themes/<your-theme>/templates/learner_interface/...
```

The same applies to project-level `templates/student_interface/` overrides and to
`static/student_interface/` asset overrides.

Rename the directory, then **look at the pages**. This failure mode cannot be caught by
`manage.py check`, by `pytest`, or by any grep of your Python.

---

### 5. The conformance suite — the one exception to its "inert" promise

`freedom_ls/contrib/conformance/` shipped with this promise, verbatim:

> Nothing new is auto-activated: the suite is an importable module, not a pytest plugin, so it
> stays inert until a downstream explicitly imports it.

**This rename is that promise's one exception.** If you import the conformance suite, this change
reaches into it and you must act.

The suite hardcodes the app path `freedom_ls.student_interface`, the class name
`StudentInterfaceConfig`, and a `FLS_NAMESPACE_PROBES` table of `student_interface:` URL names.
FLS's copies are all updated. Yours are not, if you pinned, copied or extended them:

```python
# OLD
_Probe("freedom_ls.student_interface", "student_interface:dashboard", True)
_Probe("freedom_ls.student_interface", "student_interface:courses", False)
conformance.drop("student_interface:courses")

# NEW
_Probe("freedom_ls.learner_interface", "learner_interface:dashboard", True)
_Probe("freedom_ls.learner_interface", "learner_interface:courses", False)
conformance.drop("learner_interface:courses")
```

The two halves of that fail differently, and the dangerous half is the app path:

- A stale **URL namespace** string fails loudly — `NoReverseMatch`.
- A stale **app path** string fails **silently**. `probe_namespace_reverses` skips when its app is
  not installed, and `freedom_ls.student_interface` is no longer installed. So the whole probe
  table self-disarms: the suite reports green, with skips, having tested nothing. In the one
  package whose entire job is catching drift.

**Verify by skip count, not exit code:**

```bash
uv run pytest <your conformance tests> -rs
```

Read the skip report. Every FLS namespace probe must **run**. A probe skipped for "app not
installed" is a failure wearing a pass.

The contract-tier probes — the ones you cannot prune — are `learner_interface:dashboard`,
`learner_interface:course_detail`, `learner_interface:course_home` and
`learner_interface:initiate_course_access`.

---

### 6. Four permission codenames are deleted, not renamed

These four named a model that has never existed (there is no `Student` model; there never was):

- `freedom_ls_student_management.view_student`
- `freedom_ls_student_management.add_student`
- `freedom_ls_student_management.change_student`
- `freedom_ls_student_management.delete_student`

They are **removed**, not renamed. Do not translate them to
`freedom_ls_learner_management.view_learner` — that names a model that does not exist either, and
`sync_role_permissions` will not create it.

If your own role config references any of the four, you get a **`validate_role_permissions`
failure, not a silent no-op**. That is the intended behaviour: the strings were always inert, and
this is the first time anything says so out loud.

The replacement in every FLS role is the cohort permission set, which is real:

```python
# OLD — freedom_ls/role_based_permissions/roles.py, "site_admin"
permissions=frozenset({
    "freedom_ls_student_management.view_cohort",
    "freedom_ls_student_management.add_cohort",
    "freedom_ls_student_management.change_cohort",
    "freedom_ls_student_management.delete_cohort",
    "freedom_ls_student_management.view_student",
    "freedom_ls_student_management.add_student",
    "freedom_ls_student_management.change_student",
    "freedom_ls_student_management.delete_student",
})

# NEW
permissions=frozenset({
    "freedom_ls_learner_management.view_cohort",
    "freedom_ls_learner_management.add_cohort",
    "freedom_ls_learner_management.change_cohort",
    "freedom_ls_learner_management.delete_cohort",
})
```

One consequence worth knowing before you notice it yourself: with the dead codenames gone, the
built-in `instructor` and `ta` roles are now permission-identical. Both are kept — deleting one is
a separate decision, not a side effect of a rename.

The `student` role key is likewise now `learner`, with `display_name` `"Learner"`. It was a
placeholder with an empty permission set and nothing in FLS assigned it, so for most projects this
is a no-op — but if *you* assigned it, see manual step 5.

---

### 7. The `AppSettings` seam moved

`DEADLINES_ACTIVE` is read through a documented per-app settings object. Its import path and its
class name both changed:

```python
# OLD
from freedom_ls.student_management.config import config

if config.DEADLINES_ACTIVE:
    ...
```

```python
# NEW
from freedom_ls.learner_management.config import config

if config.DEADLINES_ACTIVE:
    ...
```

The class behind `config` is now `LearnerManagementConfig(AppSettings)` rather than
`StudentManagementConfig(AppSettings)`. The setting **key** `DEADLINES_ACTIVE` is unchanged, and so
is the way you override it in your own settings module. Only the import breaks — loudly, which is
the point.

---

### 8. `StudentDeadline` → `LearnerDeadline`

```python
# OLD
from freedom_ls.student_management.models import StudentDeadline

StudentDeadline.objects.filter(
    student_course_registration__user=user,
)
```

```python
# NEW
from freedom_ls.learner_management.models import LearnerDeadline

LearnerDeadline.objects.filter(
    learner_course_registration__user=user,
)
```

The unique constraint is renamed with it: `unique_student_deadline_per_item` →
`unique_learner_deadline_per_item`. If you have referenced that constraint by name — in a
`RemoveConstraint`, a `SeparateDatabaseAndState`, or your own health check — update the name.

`StudentDeadlineFactory` → `LearnerDeadlineFactory` for anyone using FLS's factories in tests.

**Admin lookups are not import-time validated.** `list_select_related`, `search_fields`,
`autocomplete_fields` and `list_filter` on `LearnerDeadlineAdmin` all traverse
`learner_course_registration__…`. If you subclassed or reconfigured that admin, a missed rename
returns wrong or empty results rather than raising, and `manage.py check` will not catch it. Open
the changelist and use the search box.

---

### 9. There is no safe simultaneous app-label rename for an already-migrated database

State this plainly, because it is the question everyone asks first:

**No option — none — makes a simultaneous app-label rename safe for a database that has already
been migrated. Django ships no `RenameApp` operation.** There is nothing to add to a migration
file that would do this correctly, which is why FLS ships no migration for it.

What Django *does* have is `migrations.RenameModel`, and its content-type-fixing machinery
(`contenttypes.RenameContentType`) fires **only** for that operation. It has **no mechanism for
`AppConfig.label` changes at all**. So renaming the labels will not touch your existing
`django_content_type` rows. It leaves them stale, and `create_contenttypes` inserts fresh rows
under the new labels alongside them.

That silently orphans everything pointing at the old rows:

- `ObjectRoleAssignment.content_type`
- `CourseProgress.last_accessed_content_type`
- guardian object permissions (`guardian_userobjectpermission`, `guardian_groupobjectpermission`)
- `auth_permission`
- `django_admin_log`

And it has a second-order effect that is easy to miss:
`sync_role_permissions._ensure_permissions_exist` resolves permissions through the content type,
so against a stale table it does not find the existing permissions — it **creates duplicates**.
You end up with two `view_cohort` permissions, and role assignments pointing at whichever one
happened to be found first.

FLS's own databases are rebuilt from scratch, so none of this bites here. All of it bites a
downstream install with real data. The recipe is manual step 5.

Also renamed, and therefore also affected: FLS deleted its old migration files and regenerated a
fresh `0001_initial` per app. Migration **history** for the three apps does not carry over. This is
another reason the fresh-database path is the supported one.

---

### 10. QA management commands renamed, and one CLI flag changed

Renaming a management-command *file* renames the command. Four moved:

| Old command | New command |
| --- | --- |
| `qa_create_course_player_student` | `qa_create_course_player_learner` |
| `qa_create_empty_student_cohort` | `qa_create_empty_learner_cohort` |
| `qa_create_password_reset_student` | `qa_create_password_reset_learner` |
| `qa_create_rich_dashboard_student` | `qa_create_rich_dashboard_learner` |

And one flag:

```bash
# OLD
uv run manage.py qa_create_deadline_overrides --student-email demodev_s1@email.com

# NEW
uv run manage.py qa_create_deadline_overrides --learner-email demodev_s1@email.com
```

These only affect you if you run FLS's `qa_helpers` app (it is normally dev-only and absent from
production settings), but any script, CI job, runbook or agent memory that invokes them needs the
new spelling — an old name gives you `Unknown command`.

**Login credentials are unchanged.** `demodev_s1@email.com` and every other seeded QA account keep
their existing email and password. Those values never contained the word, so nothing about your
recorded QA steps changes except the command names above.

---

### 11. What deliberately does **not** change

Do not let a global find-and-replace touch these. Renaming them downstream will break you against
an FLS that did not rename them.

| Stays exactly as it is | Why |
| --- | --- |
| `UserCourseRegistration` | "User" is the right word; the model was already renamed in an earlier pass |
| `UserCohortDeadlineOverride` | same |
| `CohortMembership` | never carried the word |
| `Cohort`, `CohortCourseRegistration`, `CohortDeadline`, `RecommendedCourse` | unchanged |
| `FormProgress`, `TopicProgress`, `CourseProgress`, `QuestionAnswer`, `CourseItemProgress` | model names unchanged (their app label and tables moved) |
| Webhook payload keys `user_id`, `user_email` | payload contract; already correct |
| `educator_interface` and every other FLS app name | out of scope; only the three apps moved |
| Permission codenames tracking real models (`view_cohort`, …) | only the app-label prefix moved |
| Cotton component names (`<c-course-card-shell>` etc.) | unchanged; only their directory moved |
| The `DEADLINES_ACTIVE` setting key | only its import path moved |
| Learner-facing URL paths | byte-identical (see section 3) |
| Seeded QA account emails and passwords | unchanged (see section 10) |

---

## Manual steps

### 1. Update your settings and URLconf

Apply the four edits in breaking change 2. Do this before anything else — until
`INSTALLED_APPS` names the new packages, nothing else in this list will run.

### 2. Sweep your own code

Three **case-sensitive** passes over your project, using the table in breaking change 1. Scope it
to an explicit file list; do not run it blind over your whole tree, and do not use a
case-insensitive flag.

```bash
git grep -lIz 'student\|Student\|STUDENT' -- <your paths> \
  | xargs -0 -r sed -i \
      -e 's/Student/Learner/g' \
      -e 's/student/learner/g' \
      -e 's/STUDENT/LEARNER/g'
```

The `-z` / `-0` pairing is load-bearing: plain `xargs` splits on whitespace, so any path containing
a space is silently skipped while `sed` errors on the fragments.

Then read back the residuals and fix by hand the ones the table says are exceptions:

```bash
git grep -nI -i student -- <your paths>
```

Expect hits you must **not** change: prose about students in your own copy is your decision, and
the "does not change" list in breaking change 11 must survive the sweep. Check especially that
your sweep did not turn `UserCourseRegistration` or `UserCohortDeadlineOverride` into something
else, and did not rewrite `user_id` / `user_email` webhook keys.

### 3. Rename your theme and template override directories

```bash
git mv themes/<your-theme>/templates/student_interface \
       themes/<your-theme>/templates/learner_interface
git mv static/student_interface static/learner_interface     # if you have one
```

Then **look at the affected pages in a browser**. This is the one part of the upgrade with no
automated proof — see breaking change 4.

### 4. Migrate

**If your database is disposable** (dev/CI, or a fresh install): drop it, recreate it, and

```bash
uv run manage.py migrate
```

**If you have data you care about:** do step 5 instead, in the order given there. Do not run
`migrate` first and figure it out afterwards.

### 5. The `django_content_type` / role-key recipe — only for an already-migrated database

Run this **in one transaction**, with the new code deployed and *before* anything calls
`sync_role_permissions`. Take a backup first; there is no rollback for getting this wrong other
than restoring it.

```python
# uv run manage.py shell
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

LABEL_MAP = {
    "freedom_ls_student_management": "freedom_ls_learner_management",
    "freedom_ls_student_progress": "freedom_ls_learner_progress",
    "freedom_ls_student_interface": "freedom_ls_learner_interface",
}

with transaction.atomic():
    # 1. Move the content types to the new labels, in place.
    #    This keeps every FK — role assignments, guardian rows, auth_permission,
    #    django_admin_log — pointing at the same rows it always did.
    for old_label, new_label in LABEL_MAP.items():
        ContentType.objects.filter(app_label=old_label).update(app_label=new_label)

    # 2. The one model that also changed name.
    ContentType.objects.filter(
        app_label="freedom_ls_learner_management", model="studentdeadline"
    ).update(model="learnerdeadline")

    # 3. Backfill the role key on the three assignment tables.
    from freedom_ls.role_based_permissions.models import (
        ObjectRoleAssignment,
        SiteRoleAssignment,
        SystemRoleAssignment,
    )
    for model in (SystemRoleAssignment, SiteRoleAssignment, ObjectRoleAssignment):
        model.objects.filter(role="student").update(role="learner")

ContentType.objects.clear_cache()
```

Two notes on step 1. It is an `UPDATE`, not a delete-and-recreate, and that is the whole point:
the row identity is preserved, so nothing FK'd to it is orphaned. And it must happen **before**
`create_contenttypes` runs — which `post_migrate` triggers — or you will have both the stale rows
and fresh duplicates, and a much longer afternoon.

The equivalent in SQL, if you would rather do it in `psql`:

```sql
BEGIN;
UPDATE django_content_type SET app_label = 'freedom_ls_learner_management'
  WHERE app_label = 'freedom_ls_student_management';
UPDATE django_content_type SET app_label = 'freedom_ls_learner_progress'
  WHERE app_label = 'freedom_ls_student_progress';
UPDATE django_content_type SET app_label = 'freedom_ls_learner_interface'
  WHERE app_label = 'freedom_ls_student_interface';
UPDATE django_content_type SET model = 'learnerdeadline'
  WHERE app_label = 'freedom_ls_learner_management' AND model = 'studentdeadline';
COMMIT;
```

Your **tables** still need renaming too — `ALTER TABLE freedom_ls_student_management_cohort RENAME
TO freedom_ls_learner_management_cohort`, and so on down the table in breaking change 1 — and
those renames are not covered by any FLS migration either. This is what "there is no safe
simultaneous app-label rename" means in practice: you are hand-writing a cutover, and FLS cannot
write it for you because it cannot see your schema drift. If that sentence worries you, the honest
advice is to rebuild the database instead.

Smoke test, immediately afterwards:

```bash
uv run manage.py validate_role_permissions
```

It must exit clean. A failure here names the exact role and permission string still pointing at
something that no longer exists.

### 6. Re-sync roles and permissions

```bash
uv run manage.py sync_role_permissions
uv run manage.py validate_role_permissions
```

Run them in that order. On a fresh database this is routine. On a migrated one, running
`sync_role_permissions` **before** step 5 is what creates the duplicate permissions described in
breaking change 9 — so do not.

### 7. Check the conformance suite actually ran

If you import `freedom_ls/contrib/conformance/`:

```bash
uv run pytest <your conformance tests> -rs
```

Read the skip report. Every FLS namespace probe must appear as **run**, not skipped. See breaking
change 5 for why the exit code will not tell you.

### 8. Update your QA scripts and runbooks

New command names and the `--learner-email` flag, per breaking change 10.

### 9. Sanity check the whole thing

```bash
uv run manage.py check
uv run manage.py makemigrations --check --dry-run   # must be empty
uv run pytest
git grep -nI -i student -- <your paths>             # every remaining hit deliberate
```

The grep is last on purpose: it is the only one of the four that catches a stale *string*. The
other three cannot see permission strings, URL names or template paths — those are untyped `str`
to Python and invisible to `mypy`, `check` and the migration autodetector alike.

**No Tailwind rebuild and no package changes are needed.** The Tailwind source globs are
path-agnostic (`./freedom_ls/**/templates/**/*.html`), no utility classes changed, and no Python
or npm dependency moved.
