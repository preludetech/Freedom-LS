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

**FLS has already decided, in writing, and only the code disagrees.** The in-tree brand-guidelines
skill (`.claude/skills/brand-guidelines/SKILL.md`) has a terminology table listing `learners` under
"Use This" and `students` under "Not This", reasoned as "works across corporate, self-paced, and
academic contexts". Five product docs already say "learner" in prose. This spec is the code catching
up to FLS's own documented voice, not a fresh stylistic call.

**The wider industry settled it the same way.** SCORM 2004 deliberately renamed
`cmi.core.student_id` → `cmi.learner_id` between spec versions — the same organisation renaming the
same concept for the same reason. xAPI and LTI/1EdTech both use "Learner" as the canonical role term,
and South Africa's skills-development regime (SETA/QCTO, "learnership") makes it the regionally
natural word too.

**It is as cheap as it will ever be.** FLS has no live installs, and there is no production data
anywhere — only development data, and the dev database is rebuilt from scratch rather than migrated
forward. App labels feed default table names — no model in the three apps sets `db_table` (verified
repo-wide) — so renaming a label renames every table it owns. With no data to protect, that is a
non-event. Every month FLS stays unshipped-but-growing, this gets more expensive; once there are
downstream installs, it gets much more expensive.

**There is precedent in-tree.** `student_management/migrations/0011_rename_models.py` already did
`StudentCourseRegistration → UserCourseRegistration` and
`StudentCohortDeadlineOverride → UserCohortDeadlineOverride`. That is the same move for a *model*.
Note the limit of the precedent: Django automates `RenameModel` but ships **no** operation that
renames an app *label* — see "Decisions taken" below.

## Decisions taken

The two open questions this idea originally carried are now closed, and a third has been decided.
Full reasoning lives in the `research_*.md` files alongside this one.

### 1. Migrations: regenerate a fresh `0001_initial` per renamed app

Delete the existing migration files in the two renamed apps that have them (15 in
`student_management`, 5 in `student_progress`; `student_interface` has none) and regenerate a single
`0001_initial.py` each, under the new label.

The deciding factor was not tidiness. `0006_validate_no_duplicate_students` and
`0008_populate_user_from_student` **hardcode raw-SQL table names built from the old app label**
(e.g. `FROM freedom_ls_student_management_student`). Rewriting in place therefore means hand-editing
SQL string literals, not just `dependencies` tuples and `to=` references — a trap a naive sweep
misses and a reviewer has to take on trust. Regenerating removes the trap by construction and retires
the four dead-`Student` migrations (`0006`, `0008`, `0009`, `0010`) for free, since the model they
service will not exist.

`squashmigrations`/`replaces` was considered and rejected: `replaces` exists to reconcile
*already-applied* history under the *same* app label across deployed databases, and that value is
nullified the moment the label itself changes. Full complexity, no benefit.

**This is safe only because there is no production data.** If that premise ever stops holding before
this ships, the choice flips to in-place rewrite plus a manual cutover script.

Migration **filenames stay historical** for anything that survives — but under this decision, the
numbered files above do not survive at all.

### 2. Persisted "student" strings: no data migration here, a documented recipe for downstream

The `"student"` role key is a defined-but-unused placeholder (`roles.py:93-101`, `permissions=frozenset()`).
No shipped code ever calls `assign_*_role(..., "student")`, no factory defaults to it, nothing
literal-compares against it, and no migration or `post_migrate` hook seeds it. FLS's own database has
nothing to migrate, and it is being rebuilt regardless.

**But the research surfaced a bigger issue this idea had not flagged.** Django's automatic
content-type rename machinery only fires for `migrations.RenameModel` operations — it has **no
mechanism for `AppConfig.label` changes at all** (verified against Django's installed source).
Renaming the labels will not touch existing `django_content_type` rows: it leaves them stale and
`create_contenttypes` inserts fresh rows under the new label, silently orphaning anything FK'd to the
old ones — `ObjectRoleAssignment.content_type`, `CourseProgress.last_accessed_content_type`, guardian
object permissions, `auth_permission`, `django_admin_log`. `sync_role_permissions._ensure_permissions_exist`
would then *create duplicate* permissions rather than find the existing ones.

None of that can bite a rebuilt-from-scratch database. All of it would bite a downstream install with
real data. So: ship no data migration, and put a runnable recipe in the upgrade notes instead
(rename `django_content_type.app_label` rows, backfill `role='student'` → `'learner'` on the three
assignment tables, then run `validate_role_permissions` as a smoke test).

### 3. Downstream: hard break, no compatibility shims

Of the six things this rename moves, only import paths and default table names can be cleanly shimmed
in Django. **App labels and permission strings cannot be aliased at all**; URL-namespace and
template-path shims are partial and costly. A shim would cost real code to cover under half the
breakage, and there are no live installs to protect. Ship the break cleanly, backed by upgrade notes
precise enough to double as a downstream find-and-replace recipe.

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
`config/urls.py` (including one commented-out dead `api.add_router` line), `config/sitemaps.py`.

Blast radius, excluding `spec_dd/3. done/` and counting **files, not occurrences**: 114 mention
`student_management`, 80 mention `student_progress`, 76 mention `student_interface`. (The earlier
~198/~94/~253 estimates in this idea were roughly 2x high — they counted occurrences or included
shipped specs.) Most are imports and URL names. The target namespace is clear: no `Learner` class,
`learner_*` package, or `freedom_ls_learner_*` label exists in-tree today.

### 2. Migrations

No app outside these three has a migration depending on their labels — verified by grepping every
`freedom_ls/*/migrations/*.py`; matches occur only as self-references inside the two apps' own
migrations. The `organisations` dependency runs one way (`student_management` depends on
`organisations`, not the reverse). The rewrite is local.

Strategy is settled — see "Decisions taken" §1.

### 3. URL namespace and Python-level cross-app imports

`app_name = "student_interface"` → `"learner_interface"`, and every `{% url %}` / `reverse()` call
site with it.

Two seams need more than find-and-replace:

- `course_access/backends.py` returns URL *names* (`student_interface:course_home`,
  `student_interface:initiate_course_access`) across the documented pluggable-backend seam
  (`COURSE_ACCESS_BACKEND`) — downstream projects implement that interface. It **also directly imports
  `student_management.queries` and `student_management.utils`**, a hard Python dependency this idea
  originally missed.
- `course_applications/backends.py`, `queries.py` and `views.py` import `student_management` too —
  the same class of risk, one hop further out.

### 4. The conformance suite — `freedom_ls/contrib/conformance/`

**Not previously in scope, and the highest-risk omission the research found.** This is an opt-in,
downstream-importable conformance/portability test suite, documented as an API downstream projects
import into their own test suites. It hardcodes the app path `freedom_ls.student_interface`, the URL
namespace (`student_interface:dashboard`, `:course_detail`, `:course_home`,
`:initiate_course_access`, `:courses`), and the literal class name `StudentInterfaceConfig`, across
four files.

It is the same class of public seam as `course_access/backends.py` and needs the same treatment: the
rename ships in the same release, and the upgrade notes say so explicitly. A downstream project
running this suite gets import errors and false conformance failures the moment `student_interface`
disappears.

### 5. Template and static directories

`student_interface/templates/student_interface/` → `learner_interface/templates/learner_interface/`,
and the same for `static/`. Every template path string in `render()`, `{% extends %}` and
`{% include %}` moves with it.

Themes shadow templates *by path*. Neither in-tree theme carries a student-named directory, but
downstream themes will — and note that `docs/how tos/theme-fls.md`'s own canonical worked example of
a Tier-3 override is literally `themes/my-theme/templates/student_interface/partials/course_card_registered.html`.
Any downstream theme that followed FLS's own documentation has that directory. Fix the doc; call it
out in the upgrade notes.

### 6. Models, fields, constraints

One live model still carries the word: **`StudentDeadline` → `LearnerDeadline`**
(`student_management/models.py:182`). With it:

- field `student_course_registration` → `learner_course_registration`
- constraint `unique_student_deadline_per_item` → `unique_learner_deadline_per_item`
- `StudentDeadlineFactory`, `StudentDeadlineInline`, `StudentDeadlineAdmin`, and the admin's
  `search_fields` / `list_select_related` / `autocomplete_fields` strings that traverse
  `student_course_registration__…`
- test module `tests/test_student_deadline.py`

`StudentManagementConfig` is defined **twice** in the app, for unrelated purposes: the `AppConfig` in
`apps.py` and an `AppSettings` subclass in `config.py`. Both rename. The `config.py` one is a
documented downstream seam (`from freedom_ls.student_management.config import config`, controlling
`DEADLINES_ACTIVE`).

### 7. Permissions and roles

- The `freedom_ls_student_management.*` permission strings in `role_based_permissions/roles.py` and
  `registry.py` follow the app label. Note these strings are *not* stored on `auth_permission` — they
  are reconstructed at runtime from `Permission.content_type.app_label`, which is why the
  content-type issue in "Decisions taken" §2 matters downstream.
- **Delete rather than rename** `view_student`, `add_student`, `change_student`, `delete_student`.
  They name the `Student` model deleted in `0010_delete_student` and grant nothing today — confirmed:
  `_filter_perms_for_content_type` excludes them from every guardian sync because they never match a
  real object's content type. Deleting them also removes a latent mis-binding bug in
  `sync_role_permissions._ensure_permissions_exist`'s content-type fallback. The remaining codenames
  (`view_cohort`, …) track model names that are already correct — "user", not "learner" — and are not
  part of this rename.
- Role key `"student"` → `"learner"` and `display_name="Student"` → `"Learner"`
  (`roles.py:93-94`, asserted in `tests/test_roles.py:57`). The role's own `description` already
  reads "Standard learner role."
- This closes the standing TODO at `roles.py:13`: *"update these so there is no mention of rights
  over students, only rights over users"*.

### 8. Educator-interface internals and visible copy

Python and template symbols: `student_count`, `STUDENT_PAGE_SIZE`, `_paginate_students`,
`student_paginator`, `student_page`, `student_override_map`, `student_url` — in
`educator_interface/views.py` and `templates/educator_interface/partials/course_progress_panel.html`.
That list is a representative sample, not exhaustive: the same file also has `direct_student_count`,
`_annotate_total_student_count`, `total_student_count`, and panel dict keys `"students"`. Grep, don't
work from the list.

Visible copy is a short, known set: the "Student" column header, "Students X–Y of Z", "No students
are currently enrolled in this cohort.", the worked examples in `base/templates/cotton/data-table.html`,
and a `data-testid="student-answer-…"` selector in `student_interface/course_form_complete.html`
(check the Playwright suite for that string before renaming it). No other template in-tree contains
"student" as rendered prose.

While passing through, **audit for "user" leaking through where "learner" is meant**. Mechanical
renaming fixes the wrong word; it does not fix the vague one. The decision rule: "user" for
account/identity/auth/audit-trail contexts and anything true of a person regardless of role
(`User`, `UserCourseRegistration`, `CohortMembership`, webhook payload keys — the last also being an
external contract); "learner" for course-taking contexts — progress, deadlines, enrolment rosters. A
`User` can hold `instructor` on one course and `learner` on another, so the account layer must stay
role-neutral. The real risk is not the "student" hits a grep finds; it is the places the code already,
incorrectly, says "user".

### 9. QA helpers, tests, docs, plugin

- `qa_helpers/management/commands/qa_create_*_student.py` (4 files), plus `STUDENT_EMAIL` constants
  (defined in 5 files, 21 occurrences — not 16; 16 is the count of `qa_helpers` files mentioning
  "student" at all) and output copy across the app. Note `qa_create_incomplete_registration_learner.py`
  already says "learner" — terminology drift is already underway uncoordinated.
- Test fixture emails (`student_a@example.com`, `student_{i:02d}@example.com`) and test names in
  `educator_interface/tests/`
- `docs/app_structure.md` — regenerate with `/ds:app_map` rather than hand-editing;
  `docs/product/educator-interface.md`, which currently mixes "learner" (line 34) and "student"
  (everywhere else) for the same concept — decide house style, don't just substitute;
  `docs/how tos/theme-fls.md` (see §5).
- `claude_plugins/fls-dev/` skills and resources. Several reference a `StudentFactory` that no longer
  exists — and the *same lines* also reference URL names (`student_interface:topic_list`, `:enrol`,
  `:complete_topic`) that do not exist either. Stale docs, worth fixing on the way past; widen the net
  beyond `StudentFactory`.
- `.claude/agent-memory/fls-dev-qa-data-helper/reference_*_student_*.md` (5 files, alongside a sibling
  already named `reference_learner_visible_deadlines.md`)

### 10. Upgrade notes

This is the most breaking change FLS has shipped: every downstream import path, URL name, template
override path, permission string and table name moves at once. Run
`/fls-dev:update_upgrade_notes`. Beyond the usual, the notes must carry:

- a full old-string → new-string find-and-replace table (import paths, app labels, URL names,
  template paths, static paths, permission strings, role keys, table names)
- the `django_content_type` / role-key data-migration recipe from "Decisions taken" §2 — the one part
  of this that is genuinely not find-and-replace
- the conformance-suite and theme-override call-outs (§4, §5)
- a note that no option makes a simultaneous app-label rename safe for an already-migrated database,
  because Django has no `RenameApp` operation

Also check whether the concrete-project template repo hardcodes any of these
(`/fls-dev:update_template_repo`). It does: `claude_plugins/fls-dev/resources/template_repo_manifest.md`
shows the template's `config/settings_base.py` and `urls.py` carry all three old import paths.

## Out of scope

- **Renaming any other app.** `educator_interface` and the rest keep their names.
- **`User`, `UserCourseRegistration`, `CohortMembership`.** "User" is the right word there; this
  spec only removes "student".
- **Per-tenant configurable role labels.** Several LMS products let each tenant relabel roles, and
  FLS is multi-tenant, so it is a fair question — but FLS has no i18n infrastructure today (no
  `locale/`, no `LocaleMiddleware`, `gettext_lazy` used in 5 files for `verbose_name`s only), and a
  naive `LEARNER_LABEL` substitution breaks on plurals, possessives, capitalisation and sentence
  position. If wanted, it is its own spec built on real Django i18n.
- **Behaviour changes of any kind.** Anything broken that surfaces during the rename becomes its
  own spec. The one exception is deleting the four dead permission codenames, which is removal of
  something already inert. The "No students are currently enrolled" empty state gets a mechanical
  word swap, not a copy upgrade with a call-to-action.
- **Rewriting `spec_dd/3. done/`.** Shipped specs are history and stay as written. Other in-flight
  specs under `spec_dd/2. in progress/` mention these app names in prose only — no edits needed, but
  `learners-associated-with-organisations` and `fls-test-portability-part-2` should be told this spec
  is a hard prerequisite.

## Verification

- `grep -rin "student" freedom_ls/ config/ docs/ claude_plugins/` returns only intentional
  historical references.
- `uv run manage.py makemigrations --check --dry-run` clean, and `uv run manage.py check` passes.
- Full test suite green, including the Playwright suite.
- Dev database rebuilt from scratch and re-migrated cleanly; QA seed commands run end to end.
- No `freedom_ls_student_*` rows and no duplicates in `django_content_type` after a fresh migrate;
  `sqlmigrate` spot-check shows `CREATE TABLE freedom_ls_learner_management_…` names.
- `docs/app_structure.md` regenerated and showing `learner_*` nodes with the same edges as before —
  a rename must not change the dependency graph.

## Research

Background for the decisions above, in this directory:

| File | Covers |
|---|---|
| `research_django_app_rename_mechanics.md` | What Django derives from an app label; why there is no `RenameApp`; verification recipe |
| `research_migration_strategy.md` | The six migration-file options, full inventory of all 20 files, why fresh-initial won |
| `research_blast_radius.md` | Exhaustive in-tree inventory, corrected counts, the `contrib/conformance/` gap |
| `research_persisted_strings.md` | Role keys, `django_content_type` orphaning, the dead permission codenames |
| `research_downstream_upgrade_path.md` | What can and cannot be shimmed, precedent survey, upgrade-note skeleton |
| `research_terminology_ux.md` | Standards and product survey, the user-vs-learner decision rule, copy inventory |
