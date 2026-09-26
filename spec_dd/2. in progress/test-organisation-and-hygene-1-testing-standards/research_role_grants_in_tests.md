# Research: how a test grants a role when its app doesn't depend on `role_based_permissions` at runtime

Settles the open question in `idea.md` ("How a test grants a role...") that specs 5, 8, 11, 13, 15
follow.

## 1. Grep: who calls `assign_object_role` (or other `role_based_permissions` imports) in tests

`grep -rn "assign_object_role(" freedom_ls --include=**/tests/**` (excluding
`role_based_permissions/tests/` itself, which owns the role→permission mapping and is out of
scope here):

| App | File | Calls | Role(s) used |
|---|---|---|---|
| `base` | `tests/test_header_bar_user_menu.py` | 3 | `organisation_staff`, `instructor` |
| `organisations` | `tests/test_models.py` | 1 | `organisation_staff` |
| `reports` | `tests/test_admin.py` | 1 | `organisation_staff` |
| `reports` | `tests/test_views.py` | 1 | `organisation_staff` |
| `learner_management` | `tests/test_queries.py` | 25 | `organisation_staff`, `instructor` |
| `learner_management` | `tests/test_context_processors.py` | 6 | `organisation_staff`, `instructor` |
| `educator_interface` | `tests/test_learner_section.py`, `test_organisation_isolation.py`, `test_organisation_switcher.py` (+2 playwright), `test_config_authorisation.py`, `test_document_title.py`, `test_interface_urls.py` | 20 across 7 files | `organisation_staff`, `instructor` |
| `learner_interface` | — | **0** | n/a — see §2.4 |

`learner_interface` is named in the idea's open question but has no `assign_object_role` call
anywhere in its tests. Its one `role_based_permissions` import is
`freedom_ls/learner_interface/tests/test_resume_and_redirect.py:33`:
`from freedom_ls.role_based_permissions.loader import clear_caches`, called once before a
query-count assertion (`test_player_page_query_count_is_bounded`). `clear_caches()` only clears
`role_based_permissions.loader._get_role_config_cached` and
`role_based_permissions.utils._get_valid_codenames_for_content_type`
(`freedom_ls/role_based_permissions/loader.py:31-36`) — both are read only from inside
`assign_object_role`/`sync_user_object_permissions` (role *assignment* time), never from
`has_perm`/`get_objects_for_user` (permission *check* time, confirmed by grepping
`get_role_config`/`_get_role_config_cached` usage: every call site sits inside
`role_based_permissions/utils.py`, `loader.py`, or its own management commands — nothing in the
`view_course_item` render path touches it). So this particular import has no effect on the query
count it guards and is not evidence of a real dependency at all — it reads as leftover defensive
boilerplate, not a role grant. Flag it separately from the main question; it needs deleting, not
reclassifying.

## 2. How each app's production code actually enforces access

### 2.1 `learner_management` — the common root

`freedom_ls/learner_management/queries.py` is where every other app's check ultimately lands.
`organisations_accessible_to`, `cohorts_visible_to`, `all_cohorts_visible_to`, `can_view_cohort`,
`learners_visible_to` (lines 170-287) call **only** `guardian.shortcuts.get_objects_for_user` and
`user.has_perm(...)` — no import of `role_based_permissions` anywhere in this file or elsewhere in
`learner_management`'s non-test code (confirmed by grep: zero hits for
`role_based_permissions`/`assign_object_role`/`sync_user_object_permissions` outside `tests/`).
The module's own docstring names the reason (`queries.py:202-210`, on `cohorts_visible_to`):

> "`sync_user_object_permissions` filters a role's permissions down to the ones matching the
> *target object's* content type (`role_based_permissions/utils.py`)... 'An organisation role
> grants every cohort inside it' is therefore performed here, in Python, rather than by widening
> what guardian syncs."

That is a design note about *why* the guardian rows exist, not an import — `learner_management`
depends on guardian's permission tables being populated, and is architecturally indifferent to
*how* they got populated.

`freedom_ls/learner_management/context_processors.py:can_access_educator_interface` calls only
`organisations_accessible_to` — again no `role_based_permissions` import.

### 2.2 `base`

`base` has no `role_based_permissions`, `learner_management`, or `organisations` import anywhere
in its non-test code (grep confirmed). `partials/header_bar_user_menu.html:21` gates the
"Educator Interface" link on `{% if can_access_educator_interface %}`, a context variable that
only exists because `config/settings_base.py:197` registers
`"freedom_ls.learner_management.context_processors.can_access_educator_interface"` as a
`TEMPLATES` context processor — a dotted-string setting, not a Python import anywhere in `base`.
This is the one case among the six where the app's *own* code has zero coupling, visible or
otherwise, to any of `learner_management`/`organisations`/`role_based_permissions`; the dependency
exists only at the settings layer.

### 2.3 `reports`

`freedom_ls/reports/admin.py` (`GeneratedReportAdmin._visible_cohorts`,
`has_view_permission`, `has_delete_permission`) calls `learner_management.queries.can_view_cohort`
/ `all_cohorts_visible_to` exclusively. `reports` has no `role_based_permissions` import outside
tests. Its tests already mix the two approaches in the same file:
`reports/tests/test_admin.py:266-268` calls raw `guardian.shortcuts.assign_perm` for the
model-level `freedom_ls_reports.*` permissions right next to `assign_object_role(...,
"organisation_staff")` for the object-level one — i.e. the test file itself already demonstrates
that a raw guardian grant is an accepted, established pattern here, not something that needs
inventing.

### 2.4 `educator_interface`

`freedom_ls/educator_interface/views.py:52,1177,1206,1216` calls only
`learner_management.queries.organisations_accessible_to`. No `role_based_permissions` import
outside tests.

### 2.5 `organisations`

`organisations` has no permission-checking code of its own outside its tests (grep for
`has_perm`/`guardian` in `organisations/*.py` matched only `tests/test_models.py`). Its one
`assign_object_role` call (`test_models.py:297`,
`TestOrganisationStaffRole.test_role_holder_may_view_the_organisation`) asserts
`user.has_perm("freedom_ls_organisations.view_organisation", organisation)` after the grant — i.e.
this is a test of guardian's object-permission wiring for the `Organisation` model, filtered
through the `organisation_staff` role, and it is the only test in the whole suite that exercises
that exact role→permission pairing end to end. (`role_based_permissions/tests/test_utils.py` and
`test_models.py` exercise the generic role→permission sync mechanism against a *borrowed*
`learner_management.Cohort`, per spec 5's own open questions — they do not cover the
`organisation_staff` → `freedom_ls_organisations.view_organisation` pairing at all today.)

## 3. `docs/app_structure.md` and `generate_app_map.py`

The generator is `claude_plugins/django-stack/scripts/generate_app_map.py`. It works by
`ast.walk`-ing every `.py` file per app and collecting `ast.ImportFrom` nodes only
(`walk_app_imports`, lines 82-96); a file is classified test-only if its path contains `/tests/`
or `/test_`, or is named `conftest.py`/`factories.py` (`is_test_path`, lines 75-79); everything
else is a runtime edge (`compute_edges`, lines 99-118).

This means:

- Every `assign_object_role`/`assign_perm` import inside a `tests/` file **is already visible** to
  the tool and **is already recorded** as a dashed (test-only) edge in `docs/app_structure.md`:
  `base -.-> role_based_permissions` (line 171), `educator_interface -.-> role_based_permissions`
  (180), `learner_management -.-> role_based_permissions` (189), `reports -.-> role_based_permissions`
  (195), `organisations -.-> role_based_permissions` (194). Nothing is "missed" here — the graph
  correctly shows a test-only dependency for exactly the five apps that have one. The open question
  is not about visibility for these five; it is about whether that already-visible edge is the
  *right* one to have.
- `base`'s dependency on `learner_management` (via the `TEMPLATES` context-processor string in
  `config/settings_base.py`) is genuinely invisible to the tool: there is no `ast.ImportFrom` node
  anywhere in `base`'s source naming `learner_management`, because the wiring is a dotted string in
  a settings list, not a Python import. Rule 2 (spec 1, "What is settled") already has a named
  category for exactly this shape of miss — "A model relation declared by string label
  (`"content_engine.Course"`, `settings.AUTH_USER_MODEL`) is a runtime dependency on the app that
  owns the model" — and a settings-registered context processor is the same kind of string-based
  edge, just naming a callable instead of a model. `base -.-> learner_management` currently exists
  in the doc (line 169) only as a dashed test-only edge, sourced entirely from the test file's
  imports; there is no solid edge for it at all, dashed or otherwise capturing the settings wiring.

## 4. External practice

- django-guardian's own docs teach exactly the "assign the permission directly, then assert
  `has_perm`" pattern as the baseline usage example for setting up permission state — see
  [Assign object permissions](https://django-guardian.readthedocs.io/en/stable/userguide/assign/)
  and the [shortcuts API](https://django-guardian.readthedocs.io/en/v1.4.3/api/guardian.shortcuts.html)
  (`assign_perm(perm, user, obj)`). A role-management layer on top of guardian is this project's own
  addition; guardian itself expects callers (including tests) to reach it directly.
- `role_based_permissions/README.md`, "Key design decisions" (lines 187-193), states the
  architecture explicitly: *"Guardian as the enforcement layer — the role system is an abstraction
  over guardian. It manages what permissions a user should have; guardian enforces them"* and
  *"Application code checks permissions through Django/guardian's standard API. The role system is
  transparent at check time."* This is the project's own documented boundary: every one of the
  five checking apps (`learner_management`, `reports`, `educator_interface`, `base` via the context
  processor, and arguably `organisations`) is designed to be indifferent to *how* a guardian
  permission was populated. Testing "through the public contract" here means testing against
  guardian's permission state, not against the role layer that happens to be today's only producer
  of it.

## 5. Recommendation

**Primary answer: (c), for five of the six apps.** `learner_management`, `reports`,
`educator_interface`, `base`, and `organisations` (for the general "a user who may see this cohort
/ organisation" case) do not have an intrinsic runtime dependency on `role_based_permissions`.
Their production code checks `guardian` permissions directly (`has_perm`,
`get_objects_for_user`), and per the app's own README, is designed to be transparent to how those
permissions were populated. A local, lower-layer fixture/helper that calls
`guardian.shortcuts.assign_perm(codename, user, obj)` directly gives these tests everything they
need — a user who holds `freedom_ls_organisations.view_organisation` on an organisation, or
`view_cohort` on a cohort — without importing `role_based_permissions` at all. This is not a novel
proposal: `reports/tests/test_admin.py:266-268` already does exactly this for the app's own
model-level permissions in the same file that also calls `assign_object_role`, and it is
guardian's own documented usage pattern (§4). Where a fixture is worth naming, it belongs at the
lowest layer common to the apps that need it — a `grant_permission(user, obj, codename)` helper
next to `site_aware_models` or in a shared test module, not duplicated per app.

Two exceptions to state explicitly, since "the standard differs" is exactly what specs 5/8/11/13/15
need flagged:

- **`base` is case (b), not (c), for the *edge itself*** (though its concrete test can still use
  the (c) fixture, or simpler still, inject the boolean straight into the render context, per spec
  5's own "open until the spec" note). `base`'s coupling to `learner_management` is a real runtime
  edge — the `TEMPLATES` context-processor registration in `config/settings_base.py` — that
  `generate_app_map.py`'s AST-only import scan cannot see at all, dashed or solid. Record it in
  `docs/app_structure.md` alongside the string-model-relation exception rule 2 already states,
  rather than leaving it implied only by the test's (now-removable) imports.
- **`organisations/tests/test_models.py::test_role_holder_may_view_the_organisation` is closer to
  case (a), intrinsic, but arguably misplaced rather than wrong.** It is the only test anywhere
  that proves the `organisation_staff` role actually syncs
  `freedom_ls_organisations.view_organisation` end to end — a `role_based_permissions` concern
  (role→permission mapping) applied to a concrete `organisations` model, not an `organisations`
  concern about its own guardian wiring (which a raw `assign_perm` would cover just as well). Spec
  5's own open questions (bullets 2 and 3) already flag the sibling case of `role_based_permissions`
  borrowing `learner_management.Cohort` for the reverse reason. The two should be resolved the same
  way: either this coverage moves into `role_based_permissions`'s own suite against a stub model
  (matching spec 5's stub-model technique), or, if `organisations` wants to keep asserting its own
  object supports guardian correctly, it drops to a one-line `assign_perm` and stops importing
  `role_based_permissions` — either way it is not a reason to keep the cross-app import.
- **`learner_interface`'s one `role_based_permissions` import is neither (a), (b), nor (c) — it is
  dead.** `clear_caches()` in `tests/test_resume_and_redirect.py:454,504` clears caches that are
  only read from inside `assign_object_role`/`sync_user_object_permissions`, never from the
  `has_perm`/`get_objects_for_user` path the player page actually exercises. Delete the import and
  the calls; they are not evidence for any of the three options.

## Files cited

- `freedom_ls/learner_management/queries.py`
- `freedom_ls/learner_management/context_processors.py`
- `freedom_ls/reports/admin.py`, `freedom_ls/reports/tests/test_admin.py`, `test_views.py`
- `freedom_ls/educator_interface/views.py`, `tests/test_organisation_isolation.py`,
  `tests/test_config_authorisation.py`
- `freedom_ls/organisations/tests/test_models.py`
- `freedom_ls/base/templates/partials/header_bar_user_menu.html`,
  `freedom_ls/base/tests/test_header_bar_user_menu.py`, `config/settings_base.py:197`
- `freedom_ls/learner_interface/tests/test_resume_and_redirect.py`
- `freedom_ls/role_based_permissions/utils.py`, `loader.py`, `roles.py`, `README.md`
- `claude_plugins/django-stack/scripts/generate_app_map.py`
- `docs/app_structure.md`
- `spec_dd/1. next/test-organisation-and-hygene-5-foundational-apps/idea.md` (its own open
  questions on the mirror-image case)

## References

- [django-guardian: Assign object permissions](https://django-guardian.readthedocs.io/en/stable/userguide/assign/)
- [django-guardian: guardian.shortcuts API](https://django-guardian.readthedocs.io/en/v1.4.3/api/guardian.shortcuts.html)

status: ok
reason: All six named apps traced; per-app classification given with a stated recommendation (c
for five, with base's settings edge as (b) and organisations'/learner_interface's cases noted as
distinct exceptions) and in-repo evidence for each.
