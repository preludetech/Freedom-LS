# Standardise on "learner": rename student → learner across the codebase

## Goal

FLS uses "student" and "learner" for the same person, more or less at random. Settle it: **the word
is "learner"**, in models, apps, permissions, URLs, docs and UI copy alike.

This is a pure rename. No behaviour changes, no new features.

## Why it is worth doing now

**It blocks a cut already in progress.**
`spec_dd/2. in progress/learners-associated-with-organisations` introduces a model called `Learner`
and, without this, would file it inside an app called `student_management`. That idea originally
listed terminology as its one open question; the answer is this spec, and it must merge first.

**It is as cheap as it will ever be.** FLS has no live installs and the dev database is rebuilt from
scratch rather than migrated forward. App labels feed default table names — no model in the three
apps sets `db_table` — so renaming a label renames every table it owns. With no data to protect,
that is a non-event. Every month FLS stays unshipped-but-growing, this gets more expensive; once
there are downstream installs, it gets much more expensive.

**There is precedent in-tree.** `student_management/migrations/0011_rename_models.py` already did
`StudentCourseRegistration → UserCourseRegistration` and
`StudentCohortDeadlineOverride → UserCohortDeadlineOverride`. This is the same move, finished.

## Scope

### 1. The three app packages

| Today | New |
|---|---|
| `freedom_ls/student_management` | `freedom_ls/learner_management` |
| `freedom_ls/student_progress` | `freedom_ls/learner_progress` |
| `freedom_ls/student_interface` | `freedom_ls/learner_interface` |

Each carries three names that all move together: the package path, the `AppConfig.label`
(`freedom_ls_student_management` → `freedom_ls_learner_management`), and the `AppConfig` class name
(`StudentManagementConfig` → `LearnerManagementConfig`).

Config entry points: `config/settings_base.py` (three `INSTALLED_APPS` entries plus the
`student_management.context_processors.can_access_educator_interface` template context processor),
`config/urls.py`, `config/sitemaps.py`.

Rough blast radius, excluding `spec_dd/3. done/`: ~198 files mention `student_management`, ~94
mention `student_progress`, ~253 mention `student_interface`. Most are imports and URL names.

### 2. Migrations

No app outside these three has a migration depending on their labels — verified — so the dependency
graph is self-contained and the rewrite is local.

**Open question for the spec:** rewrite the app-label strings inside the existing migration files
and keep them (15 in `student_management`, 5 in `student_progress`, 0 in `student_interface`), or
squash each app to a fresh `0001_initial` now that there is no data to preserve? Squashing would
also retire migrations that only exist to service a `Student` model that no longer exists —
`0006_validate_no_duplicate_students`, `0008_populate_user_from_student`,
`0009_remove_student_fk_make_user_non_nullable`, `0010_delete_student`. Rewriting in place is the
lower-risk option and keeps intent legible; squashing is the cleaner endpoint and is only available
because of the no-data window. Pick one deliberately.

Either way, **migration filenames stay historical** — a file called
`0006_validate_no_duplicate_students.py` keeps that name if it survives at all.

### 3. URL namespace

`app_name = "student_interface"` → `"learner_interface"`, and every `{% url %}` / `reverse()` call
site with it. Note `course_access/backends.py` returns URL *names* (`student_interface:course_home`,
`student_interface:initiate_course_access`) across a documented pluggable-backend seam — downstream
projects implement that interface, so this one is an upgrade-note item, not just a find-and-replace.

### 4. Template and static directories

`student_interface/templates/student_interface/` → `learner_interface/templates/learner_interface/`,
and the same for `static/`. Every template path string in `render()`, `{% extends %}` and
`{% include %}` moves with it.

Themes shadow templates *by path*. No theme in-tree currently carries a student-named directory, but
downstream themes will — call it out in the upgrade notes.

### 5. Models, fields, constraints

One live model still carries the word: **`StudentDeadline` → `LearnerDeadline`**
(`student_management/models.py:182`). With it:

- field `student_course_registration` → `learner_course_registration`
- constraint `unique_student_deadline_per_item` → `unique_learner_deadline_per_item`
- `StudentDeadlineFactory`, `StudentDeadlineInline`, `StudentDeadlineAdmin`, and the admin's
  `search_fields` / `list_select_related` / `autocomplete_fields` strings that traverse
  `student_course_registration__…`
- test module `tests/test_student_deadline.py`

`StudentManagementConfig` is defined **twice** in the app, for unrelated purposes: the `AppConfig` in
`apps.py` and an `AppSettings` subclass in `config.py`. Both rename.

### 6. Permissions and roles

- The `freedom_ls_student_management.*` permission strings in `role_based_permissions/roles.py` and
  `registry.py` follow the app label.
- **Delete rather than rename** `view_student`, `add_student`, `change_student`, `delete_student`.
  They name the `Student` model deleted in `0010_delete_student` and grant nothing today. The
  remaining codenames (`view_cohort`, …) track model names that are already correct — "user", not
  "learner" — and are not part of this rename.
- Role key `"student"` → `"learner"` and `display_name="Student"` → `"Learner"`
  (`roles.py:93-94`, asserted in `tests/test_roles.py:57`).
- This closes the standing TODO at `roles.py:13`: *"update these so there is no mention of rights
  over students, only rights over users"*.

**Second open question:** role keys are persisted as plain `CharField` values on
`SystemRoleAssignment`, `SiteRoleAssignment` and `ObjectRoleAssignment`. Existing `"student"` rows
need either a data migration or an explicit "the dev DB is rebuilt, so don't bother" decision.
Decide, don't leave it implicit.

### 7. Educator-interface internals and visible copy

Python and template symbols: `student_count`, `STUDENT_PAGE_SIZE`, `_paginate_students`,
`student_paginator`, `student_page`, `student_override_map`, `student_url` — in
`educator_interface/views.py` and `templates/educator_interface/partials/course_progress_panel.html`.

Visible copy: the "Student" column header, "Students X–Y of Z", "No students are currently enrolled
in this cohort.", and the worked examples in `base/templates/cotton/data-table.html`.

While passing through, **audit for "user" leaking through where "learner" is meant**. Mechanical
renaming fixes the wrong word; it does not fix the vague one.

### 8. QA helpers, tests, docs, plugin

- `qa_helpers/management/commands/qa_create_*_student.py` (4 files), plus `STUDENT_EMAIL` constants
  and output copy across ~16 QA commands
- Test fixture emails (`student_a@example.com`, `student_{i:02d}@example.com`) and test names in
  `educator_interface/tests/`
- `docs/app_structure.md` — regenerate with `/ds:app_map` rather than hand-editing;
  `docs/product/educator-interface.md`
- `claude_plugins/fls-dev/` skills and resources. Several reference a `StudentFactory` that no
  longer exists — stale docs, worth fixing on the way past.
- `.claude/agent-memory/fls-dev-qa-data-helper/reference_*_student_*.md`

### 9. Upgrade notes

This is the most breaking change FLS has shipped: every downstream import path, URL name, template
override path, permission string and table name moves at once. Run
`/fls-dev:update_upgrade_notes`, and check whether the concrete-project template repo hardcodes any
of them (`/fls-dev:update_template_repo`).

## Out of scope

- **Renaming any other app.** `educator_interface` and the rest keep their names.
- **`User`, `UserCourseRegistration`, `CohortMembership`.** "User" is the right word there; this
  spec only removes "student".
- **Behaviour changes of any kind.** Anything broken that surfaces during the rename becomes its
  own spec. The one exception is deleting the four dead permission codenames, which is removal of
  something already inert.
- **Rewriting `spec_dd/3. done/`.** Shipped specs are history and stay as written.
- **Historical migration filenames.**

## Verification

- `grep -rin "student" freedom_ls/ config/ docs/ claude_plugins/` returns only intentional
  historical references (migration filenames, if any survive).
- Full test suite green, including the Playwright suite, and `uv run manage.py check`.
- Dev database rebuilt from scratch and re-migrated cleanly; QA seed commands run end to end.
- `docs/app_structure.md` regenerated and showing `learner_*` nodes with the same edges as before —
  a rename must not change the dependency graph.
