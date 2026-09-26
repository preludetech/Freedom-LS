# Research: the current permission machinery

For `educator-interface-5-permissions`. Answers questions 1-7 from the brief, grounded in the code
as it stands on `main` today. Uses FLS vocabulary per `.claude/skills/domain-glossary/SKILL.md`:
"grant" means a role or object permission, course access is "registration".

## 1. `freedom_ls/role_based_permissions/` — what each file does

**`roles.py`** — `BASE_ROLES: SiteRolesConfig`, the default role table (`_BASE_MODULE` in
`loader.py`). Seven roles:

- `site_admin` (`roles.py:16-31`) — `assignment_scope=SCOPE_SITE`. Permissions: the four
  `freedom_ls_learner_management.{view,add,change,delete}_cohort` strings. Comment at `:28`:
  "FUTURE: add `freedom_ls_role_based_permissions.*` custom permissions as site admin features are
  built."
- `instructor` (`:32-44`) and `ta` (`:45-57`) — both `assignment_scope=SCOPE_OBJECT`, both carry
  only `freedom_ls_learner_management.view_cohort`. Today they are identical, which is exactly what
  `idea.md` says needs fixing.
- `organisation_staff` (`:58-71`) — `assignment_scope=SCOPE_OBJECT`, one permission:
  `freedom_ls_organisations.view_organisation`. The `FUTURE` comment at `:63-69` is the block this
  spec exists to remove, verbatim: "letting this role manage cohorts takes an object-aware
  permission check in panel_framework, not extra permission strings here. Two things block the
  string-only route: `CreateInstanceAction` checks `add_cohort` at model level with no object, and
  guardian's backend denies every objectless check; and permissions are filtered to the target
  object's content type as they sync into guardian, so a role assigned on an `Organisation` can only
  ever grant `freedom_ls_organisations.*` permissions."
- `system_admin`, `learner`, `observer` — placeholders, empty `permissions=frozenset()`, out of
  scope per `idea.md`.

**`types.py`** — `Role` (frozen dataclass: `display_name`, `permissions: frozenset[str]`,
`assignment_scope`, `lti_role`, `role_type`, `description`). `AssignmentScope` is a `Literal["system",
"site", "object"]` (`SCOPE_SYSTEM`/`SCOPE_SITE`/`SCOPE_OBJECT`). `SiteRolesConfig` is a `Mapping[str,
Role]` with `.extend(overrides)` supporting three override shapes (full `Role` replacement, an
`add_permissions`/`remove_permissions` dict, or an `inherits` dict) — this is the mechanism a
downstream project's module uses. `.all_permission_strings()` unions every role's permissions, used
by `sync_role_permissions` to pre-create `Permission` rows.

**`registry.py`** — `PERMISSIONS: dict[str, str]`, a permission-string → human label map, mostly
commented out ("uncomment as used"). Only three strings are active today:
`freedom_ls_organisations.view_organisation` and the four cohort strings (view/add/change/delete).
`validate_role_permissions` (below) rejects any role permission not present here — so **adding a
permission to a role requires uncommenting/adding it here first**, per the `README.md` note at
`:141`.

**`loader.py`** — `get_role_config(site_name=None) -> SiteRolesConfig`: resolves
`site_name` (defaulting to `Site.objects.get_current().name`), then calls the `@cache`d
`_get_role_config_cached(site_name)`, which looks `site_name` up in
`config.FREEDOMLS_PERMISSIONS_MODULES` (a `dict[str, str]` of site name → module path) and falls
back to `_BASE_MODULE` (`freedom_ls.role_based_permissions.roles`). `_load_module_config` imports
the named module and reads its `ROLES` attribute (or `BASE_ROLES` for the base module itself) — a
downstream override module must define `ROLES = BASE_ROLES.extend({...})`. `clear_caches()` clears
both the `functools.cache` on `_get_role_config_cached` and the `lru_cache` on
`_get_valid_codenames_for_content_type` (`utils.py`) — used by tests only.

**`utils.py`** — the assign/remove/sync layer:
- `get_object_roles(user, obj)` / `_get_active_roles_for_user_on_site(user, site)` — read active
  `ObjectRoleAssignment` / `SiteRoleAssignment` rows.
- `_get_guardian_perms_as_full_strings(user, obj)` — current guardian `UserObjectPermission` rows
  for `(user, obj)` as `"app_label.codename"` strings.
- `_filter_perms_for_content_type(perms, ct)` (`:124-138`) — **the content-type filter**. For each
  permission string, splits on `.` into `app_label, codename`, and keeps it only if
  `app_label == ct.app_label` **and** `codename` is a valid codename for that content type (via the
  `lru_cache`d `_get_valid_codenames_for_content_type(ct.pk)`). This is a strict equality on
  `app_label`, not a lookup of which model the permission's codename belongs to.
- `sync_user_object_permissions(user, obj, dry_run=False, site_name=None)` (`:141-190`) — the core
  sync. Resolves `site_name` from `obj` when `obj` is a `Site`; loads that site's `SiteRolesConfig`;
  gathers the user's active roles on `obj` (`SiteRoleAssignment` if `obj` is a `Site`, else
  `ObjectRoleAssignment`); unions every role's `permissions` into `all_desired`; computes
  `ct = ContentType.objects.get_for_model(obj)` and **filters `all_desired` down to that one content
  type** via `_filter_perms_for_content_type`; diffs against current guardian perms; calls
  `assign_perm`/`remove_perm` for the delta (inside `transaction.atomic()` unless `dry_run`).
- `assign_object_role` / `remove_object_role` / `assign_site_role` / `remove_site_role` /
  `assign_system_role` / `remove_system_role` — create-or-reactivate (or deactivate) the assignment
  row, then call `sync_user_object_permissions` (system roles: no sync, "no guardian sync (system
  roles have no object to scope to)"). Each carries a `# TODO: AuditLog entry for ...` comment
  (spec 11's territory — do not delete these TODOs). `_check_assignment_scope` raises `ValueError`
  if a role's `assignment_scope` doesn't match the assignment function used (e.g. `assign_site_role`
  refuses an `assignment_scope="object"` role).
- `get_course_roles` / `get_cohort_roles` — thin aliases of `get_object_roles`.

**`config.py`** — `RoleBasedPermissionsConfig(AppSettings)` declares
`FREEDOMLS_PERMISSIONS_MODULES: dict[str, str]`, default `{}`, via FLS's own `app_settings`
mechanism (`freedom_ls.base.app_settings.AppSettings`/`Setting`). `config =
RoleBasedPermissionsConfig()` is the module-level singleton `loader.py` and the management commands
read.

**`FREEDOMLS_PERMISSIONS_MODULES` override mechanism** — a downstream project sets, in Django
settings, `FREEDOMLS_PERMISSIONS_MODULES = {"my-site": "myproject.permissions"}` (site *name*, not
domain, per `Site.objects.get_current().name`). `myproject.permissions` must define `ROLES =
BASE_ROLES.extend({...})` (three override shapes, see `types.py` above). Every entry point that
needs a role config — `get_role_config`, `sync_role_permissions`, `validate_role_permissions` — reads
this dict and falls back to `BASE_ROLES` for unlisted sites, so a project may override some sites and
leave others on the base config.

**Management commands** (`management/commands/`):
- `sync_role_permissions` (`sync_role_permissions.py`) — `--dry-run`, `--report-orphans`, `--site`.
  Phase 1 `_ensure_permissions_exist`: for every permission string in the resolved config, creates
  the `Permission` row if missing, guessing its `ContentType` from the codename's `action_modelname`
  convention with a fallback to "any content type in that app_label" (documented as unreliable for
  multi-word model names, `:71-76`). Phases 2-3 iterate every active `ObjectRoleAssignment` /
  `SiteRoleAssignment` and call `sync_user_object_permissions` on each target object (loaded via
  `model_class._base_manager.get(pk=...)`, bypassing `SiteAwareModel`'s default-manager site
  filter). Phase 4 validates `SystemRoleAssignment` role names against the union of all configs.
  `--report-orphans` flags any `UserObjectPermission`/`GroupObjectPermission` row not traceable to
  an active assignment whose role (in any config) actually grants that permission string — all
  `GroupObjectPermission` rows are always orphans, since the role system only manages user-level
  perms.
- `validate_role_permissions` (`validate_role_permissions.py`) — no args. Checks every role name is
  a valid Python identifier, every permission string exists in `registry.PERMISSIONS`, `role_type`
  and `assignment_scope` are valid enum values, and no active DB assignment references a role name
  absent from every known config (base + every `FREEDOMLS_PERMISSIONS_MODULES` entry). Meant for CI.

## 2. Does `site_admin`'s cohort permission set reach guardian when synced onto a `Site`?

**No.** Reasoning from `sync_user_object_permissions` (`utils.py:141-190`) and
`_filter_perms_for_content_type` (`:124-138`):

1. `assign_site_role(user, "site_admin")` calls `sync_user_object_permissions(user, site)` where
   `site` is a `django.contrib.sites.models.Site` instance.
2. Inside sync, `roles = _get_active_roles_for_user_on_site(user, site)` → `{"site_admin"}`, so
   `all_desired = config["site_admin"].permissions` = the four
   `freedom_ls_learner_management.{view,add,change,delete}_cohort` strings.
3. `ct = ContentType.objects.get_for_model(obj)` with `obj = site` → the content type for
   `django.contrib.sites.Site`, whose `app_label` is `"sites"` (Django's own contrib app label,
   registered in `INSTALLED_APPS` before `freedom_ls_learner_management` — `config/settings_base.py`
   does not remap it).
4. `_filter_perms_for_content_type` splits each permission string on `.`: `app_label =
   "freedom_ls_learner_management"`, `codename = "view_cohort"` (etc.). The filter keeps a
   permission only if `app_label == ct.app_label`. `"freedom_ls_learner_management" !=
   "sites"` for every one of the four strings, so **all four are dropped**. `desired` ends up the
   empty set, regardless of what `current` (existing guardian rows on the `Site`) contains, so the
   sync's only remaining effect on a fresh assignment is a no-op (`to_add = set()`), and on a
   pre-existing pollution it would actively `remove_perm` anything found (`to_remove = current -
   desired = current`).
5. So `assign_perm` is never called for any of `site_admin`'s cohort permissions on the `Site`
   object. `site_admin`'s guardian permission set on a `Site` is always empty, no matter how many
   cohort-permission strings the role carries — the content-type filter is a strict `app_label`
   equality against the *target object's* content type, and `Site`'s app label is never
   `freedom_ls_learner_management` (or any other non-`sites` label). This is a general property of
   the filter, not specific to `site_admin`: **any role's permission whose app_label differs from
   the assignment target's app_label is filtered out entirely**, so an `assignment_scope="site"`
   role can only ever carry `django.contrib.sites`-labelled permissions to have any effect through
   this sync path (and no such permissions are defined anywhere in the codebase — `registry.py`
   defines none).
6. This is exactly the ambiguity `idea.md` names ("it is unclear whether `site_admin`'s cohort
   permissions land anywhere when synced onto a Site") and the roadmap's "Unknown resolved inside a
   spec" row for spec 5 — the code confirms the answer is "they land nowhere," not merely "unclear."

**A throwaway test that would assert this** (not run, described only): under `mock_site_context`,
call `assign_site_role(user, "site_admin")`, then
`guardian.shortcuts.get_perms(user, Site.objects.get_current())` and assert the result is `[]` (or at
least contains none of the four cohort permission strings); also assert
`user.has_perm("freedom_ls_learner_management.view_cohort", some_cohort)` is `False` for a `Cohort`
the user has no direct grant on, even though the user holds `site_admin`. `role_based_permissions/
tests/test_utils.py`'s `TestSiteRoleFunctions` class (`:306-386`) currently only asserts on the
`SiteRoleAssignment` row itself (`is_active`, `role`, `site`, `assigned_by`) — it never inspects
`get_perms`/`has_perm` after a `site_admin` assignment, so this gap is untested today.

**What guardian does on an objectless `has_perm`, and whether FLS relies on it.**
`config/settings_base.py:319-324` registers `AUTHENTICATION_BACKENDS = (
"axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend",
"guardian.backends.ObjectPermissionBackend", "allauth.account.auth_backends.AuthenticationBackend")`.
Django's `has_perm(perm, obj=None)` tries every backend in order and returns `True` on the first
`True`; `ModelBackend` answers model-level (`obj=None`) checks from `Group`/`Permission` rows FLS
never populates for these roles (`assign_object_role`/`assign_site_role` only ever write guardian
object rows, never `user.user_permissions` or `Group` rows), so it returns `False`.
`guardian.backends.ObjectPermissionBackend.has_perm` returns `False` immediately whenever `obj is
None` (guardian's documented behaviour — "denies every objectless check", per `idea.md`'s own
wording and `research_scoped_capability_models.md`'s guardian section) — it never even queries.  So
an objectless `user.has_perm("freedom_ls_learner_management.add_cohort")` is `False` for every user
regardless of role.

FLS **does** rely on this today, and the reliance is exactly the gap `idea.md` flags:
`CreateInstanceAction.has_permission` (`panel_framework/actions.py:147-156`) calls
`request.user.has_perm(f"{app_label}.add_{model_name}")` with **no object** — used by
`CreateCohortAction` (`educator_interface/views.py:321-352`, a `CreateInstanceAction` subclass) to
gate the "Create Cohort" button/action. Since no role's guardian sync can ever populate an objectless
model-level permission (guardian only ever writes object-scoped rows), and `organisation_staff`'s
only permission is `freedom_ls_organisations.view_organisation` (not `add_cohort`) even before the
content-type problem, `organisation_staff.has_perm("freedom_ls_learner_management.add_cohort")` is
always `False` today — nobody but a superuser (bypassing all backends) can pass
`CreateCohortAction.has_permission`. This is the "object-aware creation" problem `idea.md` names:
"the framework hook from spec 1 receives the request and the scope object" is the fix shape, but
`CreateInstanceAction.has_permission`'s current signature takes `instance: Model | None = None` and
`CreateCohortAction` never overrides `has_permission` to pass the organisation, so today it silently
inherits the always-objectless, always-`False`-for-non-superusers base behaviour.
`EditAction.has_permission` and `DeleteAction.has_permission` (`actions.py:204-210`, `:340-347`) do
pass an object (`instance`), so guardian's per-object row check applies there and works as intended
for `instructor`/`ta` on a `Cohort` (their `view_cohort` grant, though `change_cohort`/
`delete_cohort` are not in their permission sets, so `EditAction`/`DeleteAction` would also currently
deny them — only `site_admin`'s permission set includes `change_cohort`/`delete_cohort`, and
`site_admin` is assigned at `SCOPE_SITE`, so per point 5 above those permissions are filtered out on
sync to the `Site` and never reach guardian as an object-scoped row on any individual `Cohort`
either — `site_admin` has none of these object rows and depends on superuser bypass in practice).

## 3. `freedom_ls/learner_management/queries.py` — the `_visible_to` helpers

All defined `queries.py:1-287`; none call `role_based_permissions` directly, all go through
guardian's `get_objects_for_user`/`user.has_perm` plus explicit Python joins — role assignments are
consulted only indirectly, through the guardian rows a role's sync has already produced.

- **`organisations_accessible_to(user)`** (`:170-192`) — union of two `get_objects_for_user` calls:
  organisations the user holds `freedom_ls_organisations.view_organisation` on directly (this is
  where `organisation_staff`'s one working permission takes effect, since it's assigned directly on
  the `Organisation` — `SCOPE_OBJECT`, so no content-type filtering problem), **or** organisations
  that own any `Cohort` the user holds a `view_cohort` guardian grant on (`granted_cohorts.values(
  "organisation_id")`). The docstring calls this second branch "load-bearing" — without it a
  cohort-only grant (`instructor`/`ta`) would have no path into the organisation-scoped interface at
  all.
- **`cohorts_visible_to(user, organisation)`** (`:195-225`) — **the explicit workaround for the
  content-type filter**, and its docstring says so directly (`:202-209`, quoting
  `sync_user_object_permissions`'s content-type restriction by name): if the user
  `has_perm("freedom_ls_organisations.view_organisation", organisation)` (an organisation-role
  holder), every cohort in that organisation is visible; otherwise only cohorts carrying a direct
  `view_cohort` guardian grant (`get_objects_for_user(user, "view_cohort", klass=Cohort)`) are
  visible. "An organisation role grants every cohort inside it" is performed here, in Python, not by
  guardian — exactly the gap this spec has to design around.
- **`all_cohorts_visible_to(user)`** (`:228-248`) — the organisation-unscoped sibling for the Django
  admin, same two-path shape without a passed-in `organisation`.
- **`can_view_cohort(user, cohort)`** (`:251-258`) — a per-object check re-expressed through
  `all_cohorts_visible_to(user).filter(pk=cohort.pk).exists()`, deliberately not re-implementing the
  two branches, "so a per-object check can never disagree with the queryset."
- **`learners_visible_to(user, organisation)`** (`:261-287`) — built on `cohorts_visible_to`, never
  re-deriving cohort visibility: members of visible cohorts, **plus**, only for an organisation-role
  holder (`has_perm("freedom_ls_organisations.view_organisation", organisation)`), every `Learner`
  row for that organisation regardless of cohort membership. A per-cohort grant alone (instructor/ta)
  never widens to the whole organisation's roster — "only an organisation-role holder sees both."
  `is_active=True` is applied outside both branches so a removed learner never reappears.

None of the four call `role_based_permissions.utils` functions or read `ObjectRoleAssignment` /
`SiteRoleAssignment` rows directly — they read guardian state (`has_perm`, `get_objects_for_user`)
that the sync functions produced, plus one Python-level "organisation role implies every cohort"
join that guardian's own row model cannot express. This is precisely "both" per the brief's framing:
role assignments indirectly (through what sync wrote to guardian) and guardian object permissions
directly.

## 4. The panel framework's permission hooks (spec 1) and their callers

**Hooks, from `freedom_ls/panel_framework/views.py` and `panels.py`:**

- `SectionConfigBase.check_request(request)` (`views.py:64-73`, classmethod) — the fail-closed
  prologue. 404s if `request.user` is missing/not authenticated, or if any name in
  `required_request_attrs: tuple[str, ...]` (class attr, default `()`) resolves to `None` on the
  request via `getattr(request, attr, None)`.
- `SectionConfigBase.check_access(request, instance)` (`:75-85`, classmethod, **not to be
  overridden** per its own docstring) — runs `check_request` then `authorise_instance`. This is the
  entry point every detail-view path goes through.
- `SectionConfigBase.authorise_instance(request, instance)` (`:87-95`, classmethod) — the hook a
  config overrides. Default: `raise Http404` unconditionally ("deny by default"). Receives the
  request and the resolved model instance (the object itself, not a container) — so this hook
  answers "may this request see this instance", never "may this request create something inside
  this container" (that question is `CreateInstanceAction.has_permission`, a different hook, see
  below).
- `Panel.has_permission(request) -> bool` (`panels.py:60-69`, instance method, default `True`) —
  per-panel visibility. Evaluated on every request before the panel renders or its URL resolves. A
  `False` panel is left out of its container (`is_shown()`, `panels.py:71-80`) and its own URL is a
  404 (via `_resolve_path`'s `if not root.is_shown(): raise Http404` — `views.py:319-320`, and
  `Panel.child()`'s `Http404` for a hidden/missing child — `panels.py:103-108`). Containers
  (`PanelStack`, `TabSet`) are hidden automatically once every child is hidden.
- `PanelAction.has_permission(request, instance=None) -> bool` (`actions.py:29-32`, default `True`)
  — gates one action button/submission. `_handle_action` (`views.py:352-363`) returns a bare `403`
  (`HttpResponse(status=403)`) when this is `False`, and both list-level and instance-level action
  lists are pre-filtered by it before rendering (`views.py:105-111`, `234-243`, `396-401`, `380-385`)
  — a denied action is not rendered as a button at all, only defended against a direct hand-made
  POST/GET to its URL.
  - `CreateInstanceAction.has_permission` (`actions.py:147-156`) — the concrete override used for
    creation: `request.user.has_perm(f"{app_label}.add_{model_name}")`, **objectless** (`instance`
    parameter accepted but never used, since the base `PanelAction.has_permission` signature is
    `(request, instance=None)` and this override doesn't touch it either — see §2 for why this is
    currently unworkable for `organisation_staff`/cohort creation).
  - `EditAction.has_permission` / `DeleteAction.has_permission` (`:204-210`, `:340-347`) — both
    object-aware: `request.user.has_perm(f"{app_label}.change_{model_name}", instance)` /
    `..delete_{model_name}", instance)`.

**404 vs 403, decided today:** `check_access`/`authorise_instance` (list/detail/object views) always
`raise Http404` on denial — there is no 403 path from this hook. `PanelAction.has_permission` denial
is a `403` (`_handle_action`, `views.py:357-358`) for a submitted action, but the *button itself* is
simply omitted from `get_actions()`'s filtered list when `has_permission` is `False` — so a 403 is
only ever seen by someone constructing the request by hand (a stale page, or a deliberate probe), not
a normal user. This matches `idea.md`'s "denied experience" split: 404 for organisation/instance
scope (unreachable object), 403-with-a-fragment for "an action they can see but may not perform,"
hidden-not-disabled for controls the role can't use at all. Today's code already implements the
*shape*, but the 403 path renders a bare empty `HttpResponse(status=403)` with no fragment/message —
`idea.md`'s "403 with a fragment saying what happened, why, and who to ask" is not yet built; this
spec has to add that content.

**The "every config authorises or declares an exemption" test:**
`freedom_ls/educator_interface/tests/test_config_authorisation.py`,
`TestProductionConfigsDeclareAuthorisation.test_config_overrides_authorise_instance_or_declares_an_exemption`
(`:187-196`), parametrized over `_authorised_sections()` (every section in `interface_config` that is
not a `BaseViewConfig`). Asserts `"authorise_instance" in config.__dict__` (a real override, not
inherited) **or** `config.check_access_exempt_reason is not None`. A sibling test in the same class
(`test_config_declares_the_organisation_as_a_required_request_attribute`, `:198-209`) asserts every
section's `required_request_attrs == ("organisation",)`. A third test class
(`TestEveryConfiguredSurface404sForAnInaccessibleOrganisation`, `:136-178`) walks every enumerable
path (list, detail, `__panels`, `__tabs`, `__actions`) behaviourally through the test client and
asserts every one 404s for a user with a role on a *different* organisation.

**The courses exemption:** `CourseConfig` (`educator_interface/views.py:617-638`) sets
`check_access_exempt_reason = ("Courses are shared across the Site and are not organisation-scoped "
"in this cut. The list is also currently unguarded entirely.")` and overrides `authorise_instance` to
an unconditional `return` (no denial at all), with an explicit `@claude:` comment (`:632-635`,
**do not delete**) spelling out the gap: `CourseDataTable.get_queryset` returns `Course.objects.all()`
with zero permission check, "the real check belongs to critical_security_fixes." `idea.md`'s "Tests"
section says this exemption "is expected to be gone by spec 6" — confirmed still present and
unchanged on `main` today.

## 5. Every current caller of the permission checks and role utilities

**Production code (non-test):**
- `freedom_ls/panel_framework/actions.py` — `CreateInstanceAction.has_permission`,
  `EditAction.has_permission`, `DeleteAction.has_permission` (all call `request.user.has_perm`, see
  §4).
- `freedom_ls/learner_management/queries.py` — `has_perm`/`get_objects_for_user` calls in
  `organisations_accessible_to`, `cohorts_visible_to`, `all_cohorts_visible_to`, `learners_visible_to`
  (§3).
- `freedom_ls/educator_interface/views.py` — consumes the `_visible_to` queries (`CohortDataTable`,
  `LearnerDataTable`, `CohortConfig.authorise_instance`, `LearnerConfig.authorise_instance`,
  `interface_root`/`interface` via `organisations_accessible_to`) and defines the only
  `authorise_instance` overrides and the one exemption in the codebase today (`CohortConfig`,
  `LearnerConfig`, `CourseConfig`).
- `freedom_ls/role_based_permissions/management/commands/sync_role_permissions.py` and
  `validate_role_permissions.py` — the only production callers of `assign_*_role`'s underlying
  `sync_user_object_permissions`, and of `get_role_config`/`load_base_config` outside `loader.py`
  itself.
- No other app calls `assign_object_role`/`assign_site_role`/`assign_system_role` in production code
  — confirmed by grep: every other hit is in a test file, a QA-helper management command, or
  documentation. `idea.md`'s "Nothing decides who may assign which role... called only from tests and
  QA helpers" is accurate.

**Tests:**
- `freedom_ls/role_based_permissions/tests/test_utils.py` — the unit tests for every
  assign/remove/sync function (see §2 for the coverage gap on `site_admin`'s guardian effect).
- `freedom_ls/panel_framework/tests/test_check_access.py` — exercises `check_access`/
  `authorise_instance`/`check_request` directly on stub configs (`DenyByDefaultConfig`,
  `PermissiveConfig`, `ScopedConfig`, `ScopeDereferencingConfig`); proves deny-by-default and the
  non-bypassable prologue.
- `freedom_ls/educator_interface/tests/test_config_authorisation.py` — the two test classes in §4.
- `freedom_ls/educator_interface/tests/test_learner_section.py`,
  `test_organisation_switcher.py`/`test_organisation_switcher_mobile.py` (Playwright),
  `test_interface_urls.py`, `test_dashboard.py`, `test_course_visibility_and_interest.py` — each
  calls `assign_object_role(user, organisation_or_cohort, role)` to set up an educator fixture before
  exercising a view.
- `freedom_ls/learner_management/tests/test_queries.py`,
  `freedom_ls/learner_management/tests/test_context_processors.py` — exercise the `_visible_to`
  helpers directly against various role/grant combinations.
- `freedom_ls/reports/tests/test_views.py`, `test_admin.py`,
  `freedom_ls/base/tests/test_header_bar_user_menu.py` — assign `organisation_staff`/`instructor`
  to test report and header-bar behaviour that depends on visible organisations/cohorts.

**QA helpers:**
- `freedom_ls/qa_helpers/management/commands/qa_create_organisation_scenarios.py` — builds demo
  educator scenarios via `assign_object_role(org_educator, rpas, "organisation_staff")`,
  `assign_object_role(single_org, rpas, "organisation_staff")`,
  `assign_object_role(legacy_educator, rpas_maths, "instructor")` (an `instructor` role on a
  `Course`, not a `Cohort` — note `get_course_roles` exists in `utils.py` for exactly this, though the
  role's permission set carries nothing course-specific today).
- `freedom_ls/qa_helpers/management/commands/qa_create_report_fixtures.py` — similarly assigns
  `organisation_staff` on organisations for report-fixture users.

## 6. The two course-detail row-visibility gaps — confirmed still present

Both gaps from `notes_from_spec_1_review.md` are unchanged on `main` today, in
`freedom_ls/educator_interface/views.py`:

- **`CourseLearnerRegistrationDataTable.get_queryset`** (`:547-558`) filters
  `LearnerCourseRegistration.objects...filter(learner__organisation=organisation)` — organisation
  only, no cohort-scope narrowing. The comment directly above it (`:550-552`) even names the
  asymmetry: "Courses themselves are not organisation-scoped (`CourseConfig` is exempt), but the
  individual registrations rendered here belong to one organisation each and must not leak across
  them" — narrowed to the organisation, but not to `learners_visible_to`. An instructor/ta whose only
  grant is on one cohort still sees every directly-registered learner in the whole organisation on
  this panel, because `CourseConfig.authorise_instance` is a no-op (§4) so any logged-in educator can
  open any course's detail page at all.
- **`CourseCohortRegistrationDataTable.get_queryset`** (`:505-513`) filters
  `CohortCourseRegistration.objects...filter(cohort__organisation=organisation)` — same shape, same
  gap: names and links every cohort in the organisation registered to the course, not just
  `cohorts_visible_to(request.user, organisation)`.

Neither call site uses `learners_visible_to`/`cohorts_visible_to` at all. The fix the review note
proposes (filter by the visibility helper instead of the raw `__organisation` lookup) is a one-line
change to each `get_queryset`, once this spec's matrix/tests exist to pin it down. `CoursePanelStack`
(`:605-610`) wires both tables into `CourseInstanceView` unchanged.

## 7. Option A vs option B — consequences, not a choice

`idea.md`'s own wording for the fork: "Either the sync learns that a role on an organisation implies
permissions on the things inside it, or the interface stops asking guardian about model permission
strings for organisation roles and asks a small capability layer instead, which consults the role
assignments directly." `research_scoped_capability_models.md` (same directory) already researches
this in depth from other systems' shapes (Moodle/Canvas context-walk, django-rules predicates,
Zanzibar/OpenFGA relation-inheritance, guardian's row-based model) and recommends option B; the
summary below is the FLS-code-specific consequences, not a re-derivation.

**Option A — sync learns container inheritance (materialise guardian rows onto contents).**
- Touches: `sync_user_object_permissions`/`_filter_perms_for_content_type` (`utils.py`) grow a
  container-walk (e.g., on an `Organisation` assignment, also `assign_perm` for every `Cohort` in
  that organisation, and for every `Learner` if `learner_management.*` roles ever apply there too);
  a new hook is needed at `Cohort.objects.create(organisation=...)` (and any other future
  child-of-a-container model) to re-run the sync for every user holding an organisation-level role,
  or newly-created objects silently have no rows until the next `sync_role_permissions` sweep.
  `cohorts_visible_to`/`learners_visible_to` (`queries.py`) could then simplify — `get_objects_for_
  user` alone would answer what they currently answer with a Python-level `has_perm(organisation)`
  branch — but only once every existing and future child object has been synced, so the simplification
  is not free either.
- `FREEDOMLS_PERMISSIONS_MODULES` override consequence: a downstream module that widens
  `organisation_staff`'s permissions (e.g. adds `learner_management.add_learner`) only takes effect
  for objects touched by a subsequent sync — `sync_role_permissions` re-run, or the assign/remove
  functions re-called — because the rows are materialised at sync time under whichever config was
  active then. An override deployed after objects already exist requires an explicit re-sync pass
  project-wide, or old and new permission sets coexist inconsistently across objects until one runs.

**Option B — a small capability layer consulting role assignments directly.**
- Touches: a new module/function (not existing today) — e.g. `can(user, capability, scope_obj) ->
  bool` — that reads `ObjectRoleAssignment`/`SiteRoleAssignment` rows directly (via
  `get_object_roles`/`_get_active_roles_for_user_on_site`, already in `utils.py`) and resolves a
  role's `permissions` against the requested capability without ever touching guardian for the
  container→child direction. Call sites that currently do
  `request.user.has_perm(f"{app_label}.add_{model_name}")` (`CreateInstanceAction.has_permission`,
  `actions.py:147-156`) would call the capability layer instead when the check needs a container
  object; `authorise_instance` overrides (`CohortConfig`, `LearnerConfig`) already delegate to
  `cohorts_visible_to`/`learners_visible_to`, which already perform the container→child join in
  Python (§3) — so option B is closer to "generalise what `queries.py` already does into one named
  function" than "build something new from nothing." Guardian is not removed: it stays exactly as-is
  for permissions genuinely assigned on the object being checked (`instructor`/`ta`'s `view_cohort`
  on a `Cohort` directly, which already works because the assignment and the check share a content
  type).
- `FREEDOMLS_PERMISSIONS_MODULES` override consequence: a downstream override takes effect
  immediately for every object — existing or future — the next time the capability function is
  called, because it reads `get_role_config(site_name)` live rather than reading a previously-
  materialised guardian row. No re-sync pass, no window where an old and a new permission set
  coexist across different objects.
- Cost is shifted from row storage/sync-staleness to a live per-check join (bounded — FLS's container
  depth today is at most site → organisation → cohort → learner, 2-3 hops), and it makes the
  eventual matrix test (already committed to in `idea.md`'s "Tests" section) the mechanism keeping a
  `can()`-style function and the `_visible_to` queryset helpers from drifting apart — a discipline the
  spec's own test plan already pays for regardless of which option is chosen, since both `authorise_
  instance` (a single-object check) and the `_visible_to` helpers (a queryset) must agree either way.

Both options must still solve the *objectless creation check* problem independently of this choice:
guardian denies every objectless check regardless of what rows exist, so "may this user create a
cohort in this organisation" is asked of the *organisation* either way (per `idea.md`'s "Object-aware
creation" — the framework hook receives the request and the scope object). Option A does not remove
that carve-out; it only affects whether *existing* container→child list/detail checks go through
guardian rows or a live capability call.
status: ok
