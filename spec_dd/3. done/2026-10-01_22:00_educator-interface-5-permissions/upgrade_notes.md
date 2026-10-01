---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/base/templates/cotton/modal.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_denied.html
  - freedom_ls/panel_framework/templates/panel_framework/partials/action_unavailable.html
requires_settings_change: false
changed_settings: []
requires_package_upgrade: false
changed_packages: []
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: false
---

# Upgrade notes: educator-interface-5-permissions

## Breaking changes

### Role keys renamed

Three built-in role keys in `freedom_ls.role_based_permissions.roles.BASE_ROLES` are renamed.
`site_admin` keeps its key. Display names and descriptions of all four changed.

| Old key | New key | Display name |
|---|---|---|
| `organisation_staff` | `organisation_admin` | Organisation admin |
| `instructor` | `cohort_admin` | Cohort admin |
| `ta` | `cohort_viewer` | Cohort viewer |

There is no alias for the old keys. A per-site role config module listed in
`FREEDOMLS_PERMISSIONS_MODULES` that `inherits` from, or overrides, an old key fails at import,
because `SiteRolesConfig.extend` raises `ValueError` on an unknown parent. Any code, fixture, QA
command or test that passes an old key to `assign_object_role`, `assign_site_role`,
`remove_object_role` or `remove_site_role` now fails `check_role_name_in_config`.

Existing `SiteRoleAssignment` and `ObjectRoleAssignment` rows are rewritten by the data migration
`freedom_ls_role_based_permissions.0002_rename_educator_roles`. Rows with any other role key,
including custom downstream roles, are untouched.

### Every role's permission set changed

Each built-in role's `permissions` set is now exactly the capability strings its column of the
permission matrix allows (see the spec's "The matrix"). Custom roles that `inherits` from a renamed
role pick up the new set. New permission strings were added to the registry in
`freedom_ls/role_based_permissions/registry.py`, with new custom `Meta.permissions` on `Learner`
(`bulk_manage_learners`), `Cohort` (`download_cohort_report`), `SiteRoleAssignment`
(`assign_site_admin`) and `ObjectRoleAssignment` (`assign_organisation_admin`,
`assign_cohort_admin`, `assign_cohort_viewer`). Run `manage.py validate_role_permissions` after
updating a custom config.

### Guardian rows no longer decide educator visibility

`freedom_ls.learner_management.capabilities.can(user, capability, scope)` is the single permission
check for the educator interface. It reads role assignments and the role config only, never
guardian object permissions. The visibility helpers in `freedom_ls/learner_management/queries.py`
(`organisations_accessible_to`, `cohorts_visible_to`, `all_cohorts_visible_to`, `can_view_cohort`,
`learners_visible_to`) are rebuilt on the same queryset builders and keep their signatures.

A guardian grant made with `assign_perm` (for example `view_cohort` on a cohort) no longer makes
that cohort visible in the educator interface or the reports. Grant access through a role
assignment instead: `assign_object_role(user, cohort, "cohort_viewer")` replaces a raw
`view_cohort` grant, and `assign_object_role(user, organisation, "organisation_admin")` is the
only role below `site_admin` that may delete a cohort. Guardian sync itself is unchanged, and the
Django admin's `GuardedSiteAwareModelAdmin` still reads guardian rows.

### The `OrganisationMember` gate

New model `freedom_ls.learner_management.models.OrganisationMember` (a `(site, user, organisation,
is_active)` row). An `organisation_admin`, `cohort_admin` or `cohort_viewer` grant counts only
while the user has an active `OrganisationMember` for that organisation. `site_admin` and superusers
need no row.

A `post_save` receiver on `ObjectRoleAssignment` (`freedom_ls/learner_management/signals.py`)
creates the row for every new or re-saved active grant on an organisation or cohort, so new
grants need nothing extra. **No migration backfills rows for grants that already exist.** See the
manual steps below. `freedom_ls.learner_management.utils.ensure_organisation_member(user,
organisation)` creates the row idempotently and never reactivates an inactive one.

### Panel framework permission contract

Any downstream section config, panel or action built on `freedom_ls.panel_framework` is affected:

- `PanelAction.has_permission(self, ctx: PanelContext) -> bool` replaces
  `has_permission(self, request, instance=None)`. Overrides with the old signature break. The
  default now resolves `get_capability(ctx)` (returns the new `capability` attribute) against
  `permission_object(ctx)` (default `ctx.scope_object()`) by calling
  `ctx.config.has_capability(...)`. An action with no capability is allowed; one with a capability
  but no permission object is denied.
- `CreateInstanceAction`, `EditAction` and `DeleteAction` no longer call `request.user.has_perm`.
  They derive `add_`, `change_` and `delete_` capabilities of their model and ask the section
  config. Nothing in the framework calls `has_perm` any more.
- `SectionConfigBase` gains three classmethods. `get_scope(request)` returns `None` by default.
  `has_capability(request, capability, scope)` returns `False` by default, so **a section config
  that does not override it denies every built-in create, edit and delete action.** Override it to
  grant anything (the educator interface delegates to `can`). `get_denied_context(request,
  capability, scope)` returns `{"who_to_ask": "Ask an administrator."}` by default.
- `PanelContext` gains a required `config: type[SectionConfigBase]` field with no default, and
  `scope: Model | None = None`. Code that constructs `PanelContext` directly (tests included) must
  pass `config`. `scope_object()` returns `instance`, or `scope` when there is none.
- `Panel` gains `capability: str | None = None`. The default `has_permission(request)` asks the
  section config when `capability` is set. A denied panel is left out of its container and its URL
  is a 404.
- A denied action answers an htmx request with the 403 fragment
  `panel_framework/partials/action_denied.html` rendered into the action's target, and raises
  `PermissionDenied` for a plain request. Previously it returned a bare `HttpResponse(status=403)`.
- An htmx request to an action whose object no longer resolves (a stale delete after the grant
  went) answers a 404 with the fragment `panel_framework/partials/action_unavailable.html` instead
  of the full 404 page.

### Reports check `download_cohort_report`

`generate_report_view` and `download_report_view` in `freedom_ls/reports/views.py` now require
`can(user, "freedom_ls_learner_management.download_cohort_report", cohort)` instead of
`can_view_cohort`. All four built-in roles that see a cohort hold it. A custom role with
`view_cohort` but not `download_cohort_report` can see a cohort but not generate or download its
report.

### `remove_site_role` refuses to remove the last site admin

`freedom_ls.role_based_permissions.utils.remove_site_role` raises
`RoleChangeRefused(RefusalReason.LAST_SITE_ADMIN)` (both in
`freedom_ls/role_based_permissions/exceptions.py`) when the user holds the only active
`site_admin` assignment on the site held by an active user. Code and tests that remove a sole site
admin must add another first or catch the exception.

### `htmx:beforeSwap` listener in `alpine-components.js`

`freedom_ls/base/static/base/js/alpine-components.js` now also swaps a 403 or 404 response whose
body contains `data-htmx-swap-error`, with `isError = false`, the way it already treats 422. A
403 or 404 without that marker is still not swapped. A downstream project that replaced this
script needs the same rule, or the denial modals never appear.

### `<c-modal>` passes extra attributes through

`freedom_ls/base/templates/cotton/modal.html` renders `{{ attrs }}` on its root `div` instead of
`{{ c.attrs }}`, so attributes such as `data-htmx-swap-error` reach the element. A project that
shadows this template must carry the change across or the denial fragments are not swapped in.

## Manual steps

1. **Update role configs and code that names a role.** In every module listed in
   `FREEDOMLS_PERMISSIONS_MODULES`, and in any code, fixture or test, replace `organisation_staff`,
   `instructor` and `ta` with `organisation_admin`, `cohort_admin` and `cohort_viewer`. Then run:

   ```
   uv run manage.py validate_role_permissions
   ```

2. **Run the migrations:**

   ```
   uv run manage.py migrate
   ```

   This applies `freedom_ls_role_based_permissions` `0002_rename_educator_roles` (data) and
   `0003_alter_objectroleassignment_options_and_more` (custom permissions), and
   `freedom_ls_learner_management` `0003_organisationmember` (new table) and
   `0004_alter_cohort_options_alter_learner_options` (custom permissions). Run `manage.py
   sync_role_permissions` afterwards if your project relies on guardian rows mirroring the new
   permission sets.

3. **Create `OrganisationMember` rows for existing grant holders.** Until this is done, every
   existing `organisation_admin`, `cohort_admin` and `cohort_viewer` loses access to their
   organisation. Site admins and superusers are unaffected. Run this once in `manage.py shell`:

   ```python
   from freedom_ls.learner_management.models import Cohort
   from freedom_ls.learner_management.utils import ensure_organisation_member
   from freedom_ls.organisations.models import Organisation
   from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

   for assignment in ObjectRoleAssignment._base_manager.filter(is_active=True).select_related("user"):
       target = assignment.target
       if isinstance(target, Organisation):
           ensure_organisation_member(assignment.user, target)
       elif isinstance(target, Cohort):
           ensure_organisation_member(assignment.user, target.organisation)
   ```

   It is idempotent and never reactivates a row someone has deactivated.

4. **Replace guardian grants with role assignments.** Anywhere your project grants educator access
   with `guardian.shortcuts.assign_perm` (fixtures, QA commands, tests, onboarding code), switch to
   `assign_object_role` or `assign_site_role` from `freedom_ls.role_based_permissions.utils`. See
   "Guardian rows no longer decide educator visibility".

5. **Update downstream panel framework consumers.** For every section config of your own:
   override `get_scope` and `has_capability` (or built-in actions deny everything), update any
   `PanelAction.has_permission` override to the `(self, ctx)` signature, and pass `config=` wherever
   you construct `PanelContext` directly. Optionally override `get_denied_context` to name who to
   ask, and set `capability` on panels you want hidden by role.

6. **Review template overrides.** If your project shadows `cotton/modal.html`, apply the
   `{{ attrs }}` change. The two new partials, `panel_framework/partials/action_denied.html` and
   `panel_framework/partials/action_unavailable.html`, can be shadowed to change the denial copy;
   keep `data-htmx-swap-error="true"` on the root `<c-modal>` so the listener swaps them in.

7. **If you replaced `alpine-components.js`,** add the 403/404 `data-htmx-swap-error` branch to
   your `htmx:beforeSwap` listener.

8. **Handle `RoleChangeRefused`** anywhere your code calls `remove_site_role` on a user who may be
   the last active site admin.
