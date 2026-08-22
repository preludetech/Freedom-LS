# Blast-radius audit: "student" → "learner"

Pure in-tree grep audit. Scope: `freedom_ls/`, `config/`, `docs/`, `demo_content/`, `claude_plugins/`,
`.claude/`, `spec_dd/2. in progress/` (reported separately), root config files. Excludes
`spec_dd/3. done/`, `.git/`, `.venv/`, `__pycache__/`, `node_modules/`. All greps are case-insensitive
`student` unless noted; `.venv` is a real subdirectory of this worktree and was explicitly excluded
throughout (it is third-party, not project code).

## Summary

- The idea's core file-count claims are **directionally right but off by roughly 2x** — actual counts
  (excluding `spec_dd/3. done/`) are **114 files** mention `student_management` (idea said ~198), **80**
  mention `student_progress` (idea said ~94), **76** mention `student_interface` (idea said ~253). See
  §Claim cross-check for the per-directory breakdown; the idea's numbers likely included
  `spec_dd/3. done/` or double-counted matches-per-file.
- **Biggest scope gap: `freedom_ls/contrib/conformance/`** — an opt-in, downstream-importable
  conformance/portability test suite — hardcodes `freedom_ls.student_interface`, the URL namespace
  `student_interface:*`, and the class name `StudentInterfaceConfig` in four files. This is the same
  class of "documented pluggable seam" risk the idea calls out for `course_access/backends.py`, but
  the idea never mentions `contrib/` at all. It belongs in scope §3/§9 alongside the backends.py note.
- **Second gap: `course_access/backends.py` imports `student_management` directly** (`from
  freedom_ls.student_management.queries import is_registered_for_course_expression` and `...utils
  import is_registered_for_course`), not just the URL names the idea calls out. This is a real
  cross-app Python import dependency, confirmed in `docs/app_structure.md`'s dependency graph
  (`course_access --> student_management`, `course_applications --> student_management`).
- **Third gap: the codebase already has an inconsistently-named QA command and doc/idea drift.**
  `freedom_ls/qa_helpers/management/commands/qa_create_incomplete_registration_learner.py` already
  uses "learner" while its ~15 siblings use "student" — evidence the naming is already half-migrated
  in an uncoordinated way. `docs/product/educator-interface.md` itself mixes "student"/"students" and
  "learners" for the same concept within one file (line 34 says "learners", the rest of the file says
  "students").
- **Fourth gap: `claude_plugins/fls-dev/` references are stale beyond `StudentFactory`.** The same
  files also reference URL names (`student_interface:topic_list`, `student_interface:enrol`,
  `student_interface:complete_topic`) that do not exist in the current `student_interface/urls.py` —
  pre-existing doc rot the idea's "worth fixing on the way past" note should be widened to cover.
- The idea's specific `path:line` claims for `StudentDeadline`, the `StudentManagementConfig`
  duplicate, `roles.py`/`registry.py`/`test_roles.py`, `course_access/backends.py` URL names, the
  educator_interface symbol list, and the QA `STUDENT_EMAIL` pattern are all **confirmed accurate**
  (see cross-check table) — the idea's prose research holds up; its aggregate counts don't.
- `freedom_ls/organisations/` has zero "student" hits but two "learner" hits already (`utils.py:16`,
  `signals.py:66`), and the in-flight `learners-associated-with-organisations` idea confirms its
  `Learner` model is planned to live inside `student_management` — this rename is a hard blocking
  prerequisite for that spec, exactly as claimed.

## Gaps in the idea's scope list

These are things the idea's §1–§9 scope list does not mention, found by direct sweep.

| Gap | Where | Why it matters |
|---|---|---|
| `freedom_ls/contrib/conformance/` hardcodes the app path, URL namespace and `AppConfig` class name | `contrib/conformance/__init__.py:9`, `test_settings.py:17`, `test_urls.py:29-48`, `tests/test_conformance_meta.py:60-104` | This package is explicitly documented as "downstreams import from here" (`__init__.py:1-10`) — a public, versioned seam identical in kind to `course_access/backends.py`'s URL names, but never named in §3 or §9. It also embeds `StudentInterfaceConfig` as a literal string (`test_conformance_meta.py:82`), so the `AppConfig` class rename breaks it too. |
| `course_access/backends.py` imports `student_management.queries` and `student_management.utils` directly | `course_access/backends.py:20-23` | The idea's §3 only discusses `course_access/backends.py` returning URL *names*; it does not mention this file also has a hard Python import dependency on the `student_management` package path, which moves in §1. |
| `course_applications/backends.py`, `course_applications/queries.py`, `course_applications/views.py` also import/reference `student_management` | confirmed via `docs/app_structure.md:54` (`course_applications --> student_management`) and grep hits in those files | Same class of cross-app import risk as course_access, one level further out; not named anywhere in the idea. |
| `freedom_ls/qa_helpers/management/commands/qa_create_incomplete_registration_learner.py` already says "learner" | filename itself | Evidence of terminology drift already underway — worth confirming during the rename that this command's *content* doesn't also need alignment (e.g. does it now become inconsistent in the other direction, or was it already correct?). |
| Stale URL names in `claude_plugins/fls-dev/` beyond `StudentFactory` | `resources/testing.md:27` references `student_interface:topic_list`, `student_interface:enrol`, `student_interface:complete_topic` — none exist in current `student_interface/urls.py` | The idea flags `StudentFactory` as stale but not the accompanying stale URL names in the same doc lines — same fix, wider net. |
| `docs/product/educator-interface.md` mixes "learner" and "student" for the same concept in one file | line 34 ("learners") vs. lines 9, 10, 22, 23, 42, 64, 82-86 ("student(s)") | This is the exact vague/wrong-word problem §7 asks to "audit for while passing through" — it already exists in shipped product docs, not just code. |
| `docs/product/webhooks.md`, `multi-tenancy-and-isolation.md`, `README.md` already say "learner" | `docs/product/` grep for `Learner` | Five product docs already use "learner" prose while the code says "student" — the semantic decision is already made in docs; this spec is catching the code up, not the other way round. Worth confirming none of these docs need *simplification* now that the words converge (e.g. removing a footnote explaining the student/learner distinction, if one exists). |
| `config/urls.py:37` has commented-out dead code naming `student_interface` | `# api.add_router("student/", "student_interface.apis.router")` | Dead code, but a naive `sed` will still touch it; harmless but worth a mention so nobody is surprised the diff includes a comment line. |
| `freedom_ls/icons/render.py` matches the substring "learner" search (false positive) | grep noise — confirm before editing | Flagging so implementers don't assume every "learner" grep hit is real prose; at least one hit in the sweep is a substring coincidence in an unrelated word — verify each hit before any scripted replace. |

## Bucket inventory

Counts are **files**, not occurrences, and are the union across `freedom_ls/`, `config/`, `docs/`,
`demo_content/`, `claude_plugins/`, `.claude/` (i.e. excluding `spec_dd/` entirely — see the separate
in-flight-specs section below).

| Bucket | File count (approx) | Representative `path:line` |
|---|---|---|
| App package path / import statement | ~90 (subset of the 114/80/76 below) | `freedom_ls/course_access/backends.py:20` `from freedom_ls.student_management.queries import ...` |
| App label string (`freedom_ls_student_*`) | 4 | `freedom_ls/student_management/apps.py:7`, `freedom_ls/student_progress/apps.py:7`, `freedom_ls/student_interface/apps.py:7`, `freedom_ls/role_based_permissions/registry.py:51-121` (permission-string prefixes) |
| URL namespace / `reverse()` / `{% url %}` | ~15 | `freedom_ls/student_interface/urls.py:5` `app_name = "student_interface"`; `freedom_ls/course_access/backends.py:202,215`; `freedom_ls/contrib/conformance/test_urls.py:29-48` |
| Template path string (`render()`, `{% extends %}`, `{% include %}`) | ~20 | `freedom_ls/student_interface/templates/student_interface/dashboard.html`; all files under `student_interface/templates/student_interface/` |
| Static asset path | 2 | `freedom_ls/student_interface/static/student_interface/js/alpine-components.js` |
| Model / field / constraint / index / related_name | 1 model, 3 sub-symbols | `freedom_ls/student_management/models.py:182` `class StudentDeadline`; `:185` `student_course_registration`; `:205` `unique_student_deadline_per_item` |
| Permission codename or role key | 2 files, ~9 codenames + 1 role key | `freedom_ls/role_based_permissions/roles.py:26-33,93-94`; `registry.py:53-89` |
| Factory / fixture / test name / test data | ~50 test files + `factories.py`×3 | `freedom_ls/student_management/factories.py:99` `class StudentDeadlineFactory`; `freedom_ls/student_management/tests/test_student_deadline.py` |
| Management command name or output copy | 21 files | `freedom_ls/qa_helpers/management/commands/qa_create_*_student.py` (4), `qa_create_educator_modal_target.py`, `qa_create_course_visibility.py`, + 10 more mentioning "student" incidentally |
| User-visible UI copy | 3 files | `freedom_ls/educator_interface/templates/educator_interface/partials/course_progress_panel.html:74,173,184`; `freedom_ls/base/templates/cotton/data-table.html:125,138` |
| Docs / markdown prose | 8 files (docs/) + 12 (claude_plugins/) | `docs/app_structure.md`, `docs/product/educator-interface.md`, `docs/how tos/theme-fls.md` |
| Claude plugin / skill / agent-memory / `.claude/` config | 12 (`claude_plugins/`) + 22 (`.claude/`) | `claude_plugins/fls-dev/resources/factory_boy.md:27,45`; `.claude/agent-memory/fls-dev-qa-data-helper/reference_*_student_*.md` (multiple) |
| Migration file (filename vs. content) | 15 (`student_management`) + 5 (`student_progress`) + 0 (`student_interface`) | `freedom_ls/student_management/migrations/0006_validate_no_duplicate_students.py` |
| Other / unclassifiable | 2 | `freedom_ls/contrib/conformance/*` (see Gaps table — genuinely its own category: downstream-facing test infrastructure); `config/urls.py:37` (dead commented code) |

### Not covered by the idea's scope list — explicit hunt results

| Directory | "student" hit? | What kind |
|---|---|---|
| `freedom_ls/organisations/` | **No** | Zero hits. But has 2 "learner" hits (`utils.py:16`, `signals.py:66`) — prose only, no code identifiers. |
| `freedom_ls/course_access/` | **Yes** — 6 files | Import of `student_management.queries`/`.utils` (`backends.py:20-23`); URL-name strings `student_interface:course_home`/`initiate_course_access` (`backends.py:202,215`); tests. |
| `freedom_ls/course_applications/` | **Yes** — 9 files | `student_management` import (via `docs/app_structure.md` edge), `views.py`, `queries.py`, `backends.py`, 3 templates with UI copy, 2 test files. |
| `freedom_ls/course_interest/` | **Yes** — 1 file | `tests/test_views.py` only — test-data/fixture reference, not production code. |
| `freedom_ls/xapi_learning_record_store/` | **No** | Zero hits. |
| `freedom_ls/panel_framework/` | **Yes** — 2 files | `tests/test_instance_dropdown.py`, `tests/test_menu_items.py` — test fixtures only. |
| `freedom_ls/webhooks/` | **Yes** — 1 file | `tests/test_integration.py` — test fixture only. |
| `freedom_ls/themes/` | **Directory does not exist** at this path | No dedicated `freedom_ls/themes/` package was found; theming lives elsewhere (e.g. `content_engine/templates/cotton/`, `base/static`). Confirms the idea's claim "no theme in-tree currently carries a student-named directory" by absence of the whole directory, not just absence of a subdirectory. |
| `freedom_ls/accounts/` | **Yes** — 1 file | `tests/test_deferred_login.py` — test fixture only. |
| `freedom_ls/content_engine/` | **No** direct "student" hit in production code; **has 1 "learner" hit** | `templates/cotton/accordion.html` — prose, likely a worked example. |
| `freedom_ls/qa_helpers/` | **Yes** — 16 files | See management-command bucket above; also has the outlier `qa_create_incomplete_registration_learner.py` (already "learner"). |
| `freedom_ls/deployment/` | **No** | Zero hits. |
| `freedom_ls/health/` | **No** | Zero hits. |
| `freedom_ls/contrib/` | **Yes** — 4 files, all in `contrib/conformance/` | See Gaps table — the most important omission in the idea. |
| `freedom_ls/base/` | **Yes** — 3 files | `templates/cotton/data-table.html` (worked-example UI copy, §7), `static/base/js/alpine-components.js`, `tests/test_header_bar_user_menu.py`. |
| `demo_content/` | **No** | Zero hits (checked case-insensitively across the whole tree). |
| `config/` | **Yes** — 4 files | `settings_base.py` (INSTALLED_APPS ×3, context processor path), `urls.py` (include + dead comment), `sitemaps.py` (2 URL-name strings), `role_based_permissions/demodev.py`. |
| root config files (`pyproject.toml`, `pytest.ini`/`setup.cfg`, `Makefile`, `package.json`, `tailwind.config.*`, `.pre-commit-config.yaml`, `.github/workflows/*.yml`) | **No** | Zero hits anywhere in root config or CI — confirms the idea's implicit assumption that no build/CI tooling hardcodes these names. |
| `README.md` (project root) | **No** | Zero hits. |

## Claim cross-check

| Claim | Verdict | Evidence |
|---|---|---|
| "~198 files mention `student_management`, ~94 `student_progress`, ~253 `student_interface`" (excl. `spec_dd/3. done/`) | **Wrong** (roughly 2x high) | Actual, excluding `spec_dd/3. done/`: `student_management` = 114 files (102 `freedom_ls/` + 2 `config/` + 1 `docs/` + 2 `claude_plugins/` + 7 `.claude/`); `student_progress` = 80 files (76+1+1+1+1); `student_interface` = 76 files (60+3+2+5+6). If `spec_dd/2. in progress/` (other in-flight specs) is added, add 19/19/19 more files respectively (see below) — still well short of the idea's numbers. The idea's counts most likely included `spec_dd/3. done/` or counted occurrences rather than files. |
| `StudentDeadline` at `student_management/models.py:182` | **Confirmed** | `models.py:182` `class StudentDeadline(SiteAwareModel):` |
| Field `student_course_registration` | **Confirmed** | `models.py:185` |
| Constraint `unique_student_deadline_per_item` | **Confirmed** | `models.py:205` |
| `StudentDeadlineFactory`, `StudentDeadlineInline`, `StudentDeadlineAdmin`, admin `search_fields`/`list_select_related`/`autocomplete_fields` traversing `student_course_registration__…` | **Confirmed** | `factories.py:99`; `admin.py:54` (`StudentDeadlineInline`), `admin.py:168` (`StudentDeadlineAdmin`), `admin.py:177-189` (`list_select_related`, `search_fields`, `autocomplete_fields` all reference `student_course_registration__…`) |
| Test module `tests/test_student_deadline.py` | **Confirmed** | `freedom_ls/student_management/tests/test_student_deadline.py` exists |
| `StudentManagementConfig` defined twice (`apps.py` AppConfig, `config.py` AppSettings subclass) | **Confirmed** | `apps.py:4` `class StudentManagementConfig(AppConfig)`; `config.py:20` `class StudentManagementConfig(AppSettings)` — same name, different base class, different purpose, both in the same package. |
| Permission codenames `view_student`/`add_student`/`change_student`/`delete_student` in `roles.py` and `registry.py` | **Confirmed** | `roles.py:30-33` (site_admin), `:47-48` (instructor), `:62` (ta); `registry.py:57-60` |
| Role key `"student"`, `display_name="Student"` at `roles.py:93-94` | **Confirmed exactly** | `roles.py:93` `"student": Role(`, `:94` `display_name="Student",` |
| TODO at `roles.py:13` | **Confirmed** | `roles.py:13` `# TODO: update these so there is no mention of rights over students, only rights over users` |
| Assertion at `tests/test_roles.py:57` | **Confirmed exactly** | `test_roles.py:57` `assert BASE_ROLES["student"].display_name == "Student"` |
| `course_access/backends.py` returns URL names `student_interface:course_home` and `student_interface:initiate_course_access` | **Confirmed**, plus an unclaimed extra | `backends.py:202` and `:215`. Additionally (not claimed) `backends.py:20-23` directly imports `freedom_ls.student_management.queries`/`.utils` — a Python-level dependency, not just URL-name strings. |
| educator_interface symbols: `student_count`, `STUDENT_PAGE_SIZE`, `_paginate_students`, `student_paginator`, `student_page`, `student_override_map`, `student_url` | **Confirmed, and incomplete** | All seven confirmed in `views.py` (lines 122, 304, 357, 379, 429, 466, 629) and `course_progress_panel.html` (74, 97, 173, 174, 184). Additional un-listed symbols exist in the same file: `direct_student_count` (882), `_annotate_total_student_count` (898), `total_student_count` (916), and dict keys `"students": CohortStudentsPanel` (771) / `"students": CourseStudentRegistrationsPanel` (1119) — the idea's symbol list is a representative sample, not exhaustive, within this one file. |
| `qa_helpers/management/commands/qa_create_*_student.py` (4 files?) | **Confirmed, 4 files** | `qa_create_course_player_student.py`, `qa_create_empty_student_cohort.py`, `qa_create_password_reset_student.py`, `qa_create_rich_dashboard_student.py` |
| `STUDENT_EMAIL` constants across ~16 QA commands | **Imprecise** | `STUDENT_EMAIL` the constant is defined in only **5** files (`qa_create_rich_dashboard_student.py`, `qa_create_educator_modal_target.py`, `qa_create_course_player_student.py`, `qa_create_course_visibility.py`, `qa_create_password_reset_student.py` — 21 total occurrences). **16** is the count of `qa_helpers` files that mention "student" *anywhere* (case-insensitive), which includes files with no `STUDENT_EMAIL` constant at all (e.g. `qa_complete_form.py`, `qa_create_large_cohort.py`). The idea conflates the two counts. |
| No theme in-tree carries a student-named directory | **Confirmed by stronger fact** | There is no `freedom_ls/themes/` directory at all in this tree — the claim holds trivially. |
| `docs/app_structure.md`, `docs/product/educator-interface.md` mention "student" | **Confirmed** | Both in the docs hit list; `app_structure.md` lists `student_interface`, `student_management`, `student_progress` as graph nodes with edges `course_access --> student_management`, `course_applications --> student_management`. |
| `.claude/agent-memory/fls-dev-qa-data-helper/reference_*_student_*.md` | **Confirmed, 5 matching files** | `reference_course_player_student_command.md`, `reference_password_reset_student_command.md`, `reference_rich_dashboard_student_command.md`, `reference_verified_student_setup.md`, plus `reference_learner_visible_deadlines.md` (already "learner" — a naming-drift precedent inside the same directory). 22 `.claude/` files total mention "student" somewhere. |
| `claude_plugins/fls-dev/` references a `StudentFactory` that no longer exists | **Confirmed, and the rot is wider** | `StudentFactory` has zero hits anywhere in `freedom_ls/` (confirmed absent). Stale references: `resources/testing.md:27`, `resources/factory_boy.md:27,45`, `skills/testing/SKILL.md:25` — the same lines also reference non-existent URL names `student_interface:topic_list`, `student_interface:enrol`, `student_interface:complete_topic` (current `urls.py` has no such names). |

## Naming collisions and existing "learner" occurrences

Existing `learner`/`Learner` hits in `freedom_ls/` (44 files, case-insensitive), none of which are
code identifiers today — all are prose/comments, so no rename target collides with an existing
Python/Django symbol:

- `freedom_ls/organisations/utils.py:16` — "...silently repaired on a **learner**-facing path."
- `freedom_ls/organisations/signals.py:66` — "...raise DoesNotExist on a **learner**-facing path."
- `freedom_ls/student_progress/models.py:586,589` — comments: "the **learner** last visited", "freshly-registered (0-progress) **learners**"
- `freedom_ls/course_access/backends.py:78,136,164,326` — docstring/comment prose: "the **learner** dashboard", "a **learner** genuinely cannot reach", "a registered **learner** keeps full access"
- `freedom_ls/role_based_permissions/roles.py:97` — `description="Standard learner role."` (on the `"student"` role definition itself — the role's own description already calls the person a "learner")
- `freedom_ls/qa_helpers/management/commands/qa_create_incomplete_registration_learner.py` — entire filename
- `freedom_ls/icons/render.py` — flagged by grep but likely a substring false-positive; verify before any scripted replace.
- `docs/product/{webhooks,learner-experience,learner-tracking,multi-tenancy-and-isolation,README}.md` — prose already committed to "learner".
- `.claude/agent-memory/fls-dev-qa-data-helper/reference_learner_visible_deadlines.md` — filename already "learner" alongside 5 sibling files still named "*_student_*".

**No collision risk found**: nowhere in-tree does a `Learner` class, `learner_management`/
`learner_progress`/`learner_interface` package, or `freedom_ls_learner_*` app label already exist —
the rename target namespace is clear. The one true collision-in-waiting is the in-flight
`spec_dd/2. in progress/learners-associated-with-organisations/idea.md`, which explicitly designs a
`Learner` model to live inside `student_management` (idea.md:11, :50 — "`Learner`, a `SiteAwareModel`,
living in **`student_management`**") — this spec's rename to `learner_management` must land first, or
that spec will need to file `Learner` into a package literally named `student_management`, which is
the exact naming absurdity both specs exist to avoid.

**Mixed-meaning-in-one-file risk** (both words for the same concept, needing human judgement not
mechanical substitution): `docs/product/educator-interface.md` (line 34 "learners" vs. the rest of the
file "student(s)"); `course_access/backends.py` (docstrings already say "learner" while the URL names
and imports say "student" — see above).

## In-flight specs referencing "student"/"learner" (`spec_dd/2. in progress/`, excluded from the main
sweep, reported separately per the task brief)

19 files across other in-progress specs mention `student_management`/`student_progress`/
`student_interface` as plain prose (research and idea docs, not code), concentrated in:
`learners-associated-with-organisations/` (idea.md, research_codebase_impact.md,
research_migration_and_autocreation.md — all discuss the same `student_management` dependency this
spec resolves), `better_course_progress_tracking/` (5 files), `more-testing-skills/` (6 files),
`fls-test-portability-part-2/` (4 files, likely exercising the same `contrib/conformance/` package
flagged above as the biggest gap), and one line each in `spec-dd-improvements-decompose/`,
`spec-dd-commit-often/`, `test_portability_3_system_checks/`, `in-app-feedback/`. None of these are in
scope to edit (they're prose about the current state, not code), but `learners-associated-with-organisations`
and `fls-test-portability-part-2` should be told this spec is a hard prerequisite before they proceed,
and this spec's plan/upgrade-notes should double-check `fls-test-portability-part-2`'s research against
the `contrib/conformance` findings above once that spec's own research is read.

## Risk ranking

**Pure mechanical string swap (safe for scripted find-and-replace, verify with `manage.py check` +
full test suite after):**
- Package directory renames (`student_management` → `learner_management`, etc.) and every import
  statement following them (~90 files).
- `AppConfig.label`/`name`/class name (`apps.py` ×3).
- `StudentDeadline` model/field/constraint renames and the admin/factory/inline symbols that follow
  it mechanically (`models.py`, `admin.py`, `factories.py`).
- Template/static directory moves and the `{% extends %}`/`{% include %}`/`render()` strings that
  reference them (~20 files) — mechanical *if* every reference is grepped, not assumed.
- `qa_helpers` `STUDENT_EMAIL` constant names and the 4 `qa_create_*_student.py` command names/filenames.
- Dead permission codenames (`view_student`/`add_student`/`change_student`/`delete_student`) — deletion,
  not rename, per the idea's own out-of-scope carve-out; mechanically safe since they're already inert.

**Needs human judgement (semantics, not syntax):**
- UI copy in `course_progress_panel.html` and `base/templates/cotton/data-table.html` — "Student"
  column header, "Students X–Y of Z", empty-state copy. Also §7's explicit ask to audit for "user"
  leaking through where "learner" is meant — this is not grep-able.
- `docs/product/educator-interface.md`'s internal "learner"/"student" inconsistency — decide the
  house style, don't just substitute.
- Role key `"student"` → `"learner"` and its `display_name` — plus the **data-migration-or-not**
  decision for existing `SystemRoleAssignment`/`SiteRoleAssignment`/`ObjectRoleAssignment` rows the
  idea flags as its second open question (unchanged by this research — still open).
- Migration rewrite-in-place vs. squash decision (the idea's first open question) — unchanged, still
  open; this research doesn't newly bear on it beyond confirming the 15/5/0 file counts.

**Load-bearing across a documented/downstream-facing public seam (highest blast radius per line
changed — needs its own upgrade-note entry, not just a code diff):**
- `course_access/backends.py` — both the URL-name strings *and* the direct `student_management`
  import (the latter not previously flagged).
- `course_applications/backends.py`/`queries.py`/`views.py` — same class of risk, one hop further.
- **`freedom_ls/contrib/conformance/`** — the single highest-risk item found in this audit and not
  mentioned by the idea at all. It is explicitly documented as an API downstream projects import
  (`__init__.py:1-10`), and it hardcodes the app path, URL namespace, and `AppConfig` class name in
  four files. A downstream project that has imported and is running this conformance suite against
  its own concrete-project settings will get import errors and false conformance failures the moment
  `student_interface` disappears, unless the suite ships the rename in the same release with clear
  upgrade-note guidance (e.g. "re-run `conformance.drop(...)` calls now name `learner_interface:...`").
- `qa_helpers`/`.claude` agent-memory files — lower production risk, but breaking these breaks the
  QA-data-helper agent's own reference docs silently (no test catches stale agent-memory prose).

status: ok
