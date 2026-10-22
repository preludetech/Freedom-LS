# Research: codebase (spec 9, educator administration)

Question: what in the existing codebase does this work touch, reuse or conflict with? All paths are
relative to the repo root. Read from the worktree at `ccd09a3a`. Specs 5, 6 and 7 are all landed.

## Headline findings

1. **The checked assign and remove entry points already exist.** Spec 5 built them:
   `freedom_ls/learner_management/role_assignment.py` has `assign_role(grantor, user, role, target)`,
   `remove_role(grantor, user, role, target)` and `set_organisation_member_active(actor, member, is_active)`.
   They raise `RoleChangeRefused(reason)` with a `RefusalReason` (`SELF`, `INACTIVE_USER`,
   `NOT_PERMITTED`, `LAST_SITE_ADMIN`, `LAST_ORGANISATION_ADMIN`; in
   `freedom_ls/role_based_permissions/exceptions.py`). The idea's "Why" says the raw utilities exist
   and nothing calls them. True of the raw ones; this spec should call the checked ones and never the raw
   `utils.assign_object_role` etc.
2. **There is no `can_assign` function.** "Who may assign what" is encoded as capability strings, not a
   table in code. `role_assignment.ASSIGN = "freedom_ls_role_based_permissions.assign_{role}"` and
   `_refuse_unless` calls `can(grantor, ASSIGN.format(role=role), target)`. The strings are Meta
   permissions: `assign_site_admin` on `SiteRoleAssignment`; `assign_organisation_admin`,
   `assign_cohort_admin`, `assign_cohort_viewer` on `ObjectRoleAssignment`
   (`role_based_permissions/models.py`). They are held per role in `BASE_ROLES`
   (`role_based_permissions/roles.py`): `site_admin` holds all four, `organisation_admin` holds the
   three object ones, the cohort roles hold none. The hand-written transcription is `MATRIX` in
   `freedom_ls/educator_interface/tests/invariants/test_permission_matrix.py`. To offer "a role from the
   ones the current user may grant", this spec must loop `can(user, ASSIGN.format(role=r), target)` over
   the four roles; the scope object is the `Site` for `site_admin`, the `Organisation` for
   `organisation_admin`, a `Cohort` for the cohort roles (organisation grants cover cohorts via `can`).
3. **The role description strings already exist, and differ from the idea's.** `BASE_ROLES[...].description`
   (spec 5) reads: site_admin "Everything, in every organisation on the site."; organisation_admin
   "Everything in one organisation, including who else administers it."; cohort_admin "Manages who is in
   a cohort and what it is registered for."; cohort_viewer "Sees a cohort and its reports. Changes
   nothing." (`display_name` values: "Site admin", "Organisation admin", "Cohort admin", "Cohort viewer".)
   The same copy is in `docs/product/educator-interface.md` "Access Control" (with the cohort_admin line
   extended: "cannot rename or delete it"). The idea drafts new copy ("manage learners, cohorts, courses
   and educators in this organisation" etc.) and says the strings are "the same strings used in the audit
   log and the product docs". Conflict: the spec must decide whether to replace the `description` fields
   (and the doc) or reuse them. Note "manage ... courses" in the idea's organisation_admin copy is not
   backed by any permission today (the role's permissions are organisation, cohort, learner, member and
   assign strings; no course permissions). Also `placeholder` roles `system_admin`, `learner`, `observer`
   exist with their own descriptions and must not appear in the picker.
4. **The last-admin guards exist.** Last site admin: `utils.remove_site_role` (locks the `Site` row,
   raises `LAST_SITE_ADMIN`; it counts other active `site_admin` holders with `user__is_active`). Last
   organisation admin: `role_assignment.remove_role`, via `_lock_and_refuse_last_organisation_admin`,
   skipped when the grantor is a superuser or an active site admin (`_is_site_level_admin`). Counting uses
   `queries.active_organisation_admins(organisation)`. Nothing to build; the spec writes the messages for
   each `RefusalReason`.
5. **Cohort deletion does NOT clean up role rows.** `DeleteEmptyCohortAction` (`educator_interface/actions.py`,
   ~line 241) calls the framework `DeleteAction.handle_submit` (`panel_framework/actions.py` ~433), which
   is a plain `instance.delete()`. There is no `GenericRelation` from `Cohort` to `ObjectRoleAssignment`
   (the only `GenericRelation`s are in `content_engine/models/courses.py`), no `pre_delete`/`post_delete`
   receiver for `Cohort` (the only ones are in `course_applications/receivers.py` and
   `learner_progress/signals.py`), and `cohort_is_empty` only checks memberships and registrations. So
   deleting a cohort leaves active `ObjectRoleAssignment` rows (object_id as a string) and
   `guardian.UserObjectPermission` rows. The idea says "this spec adds the cleanup, or spec 6 does and
   this spec tests it; decide by who lands first." Spec 6 landed (`3. done/2026-10-11_06:57_...`) without
   it, so this spec owns it. `can()` ignores guardian and reads assignments, so an orphan is harmless to
   `can` for a missing cohort but `validate_role_permissions` and `sync_role_permissions` iterate
   `ObjectRoleAssignment` rows and will touch a target that no longer resolves
   (`sync_role_permissions.py` ~lines 98-110, 221). The spec 6 spec's educators line explicitly defers
   editing to spec 9.
6. **A role holder needs an `OrganisationMember`, and that gate is an extra axis the idea does not
   mention.** `learner_management/models.py` `OrganisationMember(user, organisation, is_active)`. A
   `post_save` receiver `ensure_member_for_active_grant` (`learner_management/signals.py`) creates it when
   an active organisation or cohort grant is saved. It never reactivates a deactivated one
   (`utils.ensure_organisation_member`). `can()` honours organisation and cohort grants only while the
   member row is active (`capabilities._member_organisations`). Consequences for spec 9: the list can show
   a person whose role assignments are active but who is suspended; adding a role to a suspended member
   will not give them access; there is no screen for `set_organisation_member_active` yet, and spec 5's
   matrix row "add and remove organisation members" (`view/add/change_organisationmember`) has no UI.
   The idea is silent on suspend and reactivate. Needs a decision (show a "suspended" state and an
   action, or show it read-only, or ignore).
7. **Site admins are not "in this organisation".** `site_admin` is a `SiteRoleAssignment`, site-wide,
   with no `OrganisationMember`. `can()` grants site grants without a member row. The idea's list is "one
   row per person with any role in this organisation". Decide whether site admins appear in every
   organisation's list (probably as a read-only "site admin, all organisations" row) and how the
   "grant site_admin" action fits an organisation-scoped screen (the target is the `Site`, so it is not an
   organisation action). Superusers (`is_superuser`) pass `can` with no role at all and appear nowhere.
8. **The shared account-creation path is `freedom_ls/accounts/account_setup.py`, not a learner
   function.** `match_or_create_user(site, email, first_name="", last_name="") -> (User, created)`
   matches case-insensitively across all sites (`email__iexact`), raises `EmailInUseOnAnotherSite` if the
   match is on another site, otherwise creates a pending user (unusable password, verified primary
   `EmailAddress`). `send_account_setup_email(user, organisation_name)` sends on commit and raises
   `AccountAlreadySetUp` if the user is not pending (`is_pending`); `resend_account_setup_email` adds the
   resend window guard (`SetupEmailRecentlySent`). The email template
   (`accounts/templates/account/email/account_setup_message.{txt,html}`) says only "An account was made for
   {{ user.email }} at {{ organisation_name }}" and is learner-neutral, so it works for an educator
   unchanged. Spec 7's orchestration is `learner_management/learner_actions.py` `_add_one` /
   `add_learners` (`LearnerEntry`, `AddOutcome`, `AddLearnerResult`). `_add_one` is learner-specific
   (`ensure_learner`, webhook events) and the idea's "email first" flow is not what spec 7 built: spec 7's
   `AddLearnersForm` (`educator_interface/forms.py`) is a pasted textarea of `email, first, last` lines,
   up to `MAX_ADD_LEARNERS = 50`. Spec 9 needs a single-address flow: reuse the two `account_setup`
   functions directly, and add its own small orchestrator that calls `match_or_create_user`,
   `assign_role`, and (when created) `send_account_setup_email`. A pending account for an educator
   cannot be assigned if it is inactive (`INACTIVE_USER`); a new account is active by default.
   Open: what happens when the new account's role grant is then refused (the account is already created
   inside the transaction; wrap in `transaction.atomic()` so a refusal rolls it back, as
   `send_account_setup_email` is on-commit).
9. **No audit log exists.** `grep AuditLog` finds only `# TODO: AuditLog entry ...` comments in
   `role_based_permissions/utils.py` (six of them, one per assign and remove function) and a commented
   future permission string. Spec 11 will add the model. The `removed_by` argument is already threaded
   through the remove functions for it. Do not delete those TODOs.

## role_based_permissions in detail

- Models (`role_based_permissions/models.py`):
  - `SystemRoleAssignment`: not site-aware, `BigAutoField`; unique `(user, role)`.
  - `SiteRoleAssignment(SiteAwareModel)`: unique `(user, site, role)`.
  - `ObjectRoleAssignment(SiteAwareModel)`: `content_type` + `object_id` (CharField, stringified UUID)
    + `target` GenericForeignKey; unique `(user, content_type, object_id, role)`; index on
    `(content_type, object_id, role, is_active)`.
  - All three carry `role` (CharField 50), `is_active`, `assigned_by` (FK User, SET_NULL, `related_name="+"`),
    `assigned_at` (auto_now_add), `updated_at` (auto_now). "Added by" and "added on" for the list map to
    `assigned_by` and `assigned_at`. Caveat: reactivation overwrites `assigned_by` but `assigned_at` stays
    the original creation time (`assign_object_role` only updates `is_active` and `assigned_by`), so
    "added on" is first-ever grant, not the latest re-add. A scope change that adds a cohort creates a new
    row per cohort, so one person's "added by/on" can differ per cohort row; the list needs a rule.
- Utilities (`utils.py`): `assign_object_role`, `remove_object_role`, `assign_site_role`,
  `remove_site_role`, `assign_system_role`, `remove_system_role`, `sync_user_object_permissions`,
  `get_object_roles`, `get_cohort_roles`. Assign is `get_or_create` plus reactivate, then guardian sync.
  Remove is `.update(is_active=False)` (nothing deleted) then guardian sync. Guardian sync is
  per `(user, target)` and filters permissions to the target's content type, so for `Organisation` and
  `Cohort` targets only same-app permissions are written; this is why `can()` reads assignments rather
  than guardian. The "drops the guardian permissions through the existing sync" line in the idea is true
  but not load-bearing for access in the educator interface.
- Remove has no "role does not exist" refusal; removing a role the user does not hold silently updates
  zero rows. The checked `remove_role` does not check existence either, and `_holds_organisation_admin`
  gates only the last-admin lock. The spec should check the holder state before offering the action.
- `is_active` on `User`: assigning to an inactive user is refused; removal is allowed.
- Role registry: `loader.get_role_config(site_name)` returns a per-site `SiteRolesConfig`;
  `BASE_ROLES` in `roles.py`; each `Role` has `display_name`, `assignment_scope`
  (`SCOPE_SITE` / `SCOPE_OBJECT` / `SCOPE_SYSTEM`), `description`, `lti_role`, `permissions`.
  `organisation_admin`, `cohort_admin` and `cohort_viewer` are all `SCOPE_OBJECT`; `site_admin` is
  `SCOPE_SITE`. A downstream site may add roles (the matrix and `assign_` check leave them admin-only),
  so any list of "roles" must use the four named keys, not "every role in the config".
- Role names, exactly: `site_admin`, `organisation_admin`, `cohort_admin`, `cohort_viewer`. (The old
  names `organisation_staff`, `instructor`, `ta` were migrated by `0002_rename_educator_roles`.)
  `docs/` and the roadmap sometimes say `org_admin`; no such key exists.
- Factories (`role_based_permissions/factories.py`): `SystemRoleAssignmentFactory`,
  `SiteRoleAssignmentFactory` (default role `cohort_admin`, which is wrong for a site assignment:
  pass `role="site_admin"`), `ObjectRoleAssignmentFactory(target_object=...)` (default `cohort_admin`).
  Other factories: `learner_management/factories.py` `OrganisationMemberFactory`, `CohortFactory`,
  `LearnerFactory`, `CohortMembershipFactory`; `organisations/factories.py` `OrganisationFactory`;
  `accounts/factories.py` `UserFactory`.

## Organisations

- `Organisation` (`organisations/models.py`): "a client inside a site"; a grouping, not an isolation
  boundary (the glossary and `docs/product/multi-tenancy-and-isolation.md`). `organisation.site` is the
  site. `Cohort.organisation`, `Learner.organisation`, `OrganisationMember.organisation` (PROTECT).
- Organisation scope is resolved once per request in `educator_interface/views.py` `interface()`: it 404s
  for an unknown or inaccessible slug via `organisations_accessible_to(request.user)` and sets
  `request.organisation`. All sections subclass `OrganisationSectionConfig` (same module): `get_scope`
  returns the organisation, `has_capability` is `can`, `get_denied_context` gives "who to ask".
- `User` is site-aware with a globally unique email (`match_or_create_user` comments). An educator from
  another site cannot be added (`EmailInUseOnAnotherSite`); the add form needs a message for that.

## Educator interface: reusable pieces

- Section registration: `interface_config = [NavGroup("Teaching", [DashboardConfig, CohortConfig,
  LearnerConfig, CourseConfig])]` in `educator_interface/views.py`. Add an `EducatorConfig` (a
  `OrganisationSectionConfig` + `ListViewConfig`) here, probably in a new `NavGroup` or the same one.
  Any new section must pass `test_config_authorisation.py`: `authorise_instance` override or a
  `check_access_exempt_reason`, plus `required_request_attrs` including `organisation`.
- `ListViewConfig` (`panel_framework/views.py`): `model`, `list_view` (a `DataTable`), `instance_view`,
  `table_key`, `refresh_events`, `quick_view`, `get_actions(request)` for top-level actions,
  `get_bulk_actions`. It needs a `model`; the educators list's natural row is a `User` (or a per-user
  aggregate), not a model with a detail page. Does it need an `instance_view` at all? A list with only
  actions (and per-row actions) may need a framework allowance, or a minimal instance view. Check
  `get_instance_view`, `get_instance_label` and the `check_access` machinery before deciding.
- `DataTable` (`panel_framework/tables.py`): static `get_queryset(request)`, `get_columns()` (`Column`
  with `template`, `attr`, `sortable`, `card` primary/secondary), `get_filters()` (`TableFilter` in
  `panel_framework/filters.py`; examples in `educator_interface/filters.py`: `LearnerStatusFilter`,
  `LearnerCohortFilter`, `ShowInactiveFilter`), `search_fields` (spec 7 uses `user__first_name`,
  `user__last_name`, `user__email`), `get_row_label`, `page_size = 10`. Per-row cell templates live in
  `educator_interface/templates/educator_interface/data-table-cells/` (for example
  `membership_actions.html`, `cohort_member_actions.html`, `unregister.html`). One row per person across
  several assignment rows (organisation grant plus several cohort grants) means the queryset must be a
  `User` queryset annotated or prefetched with their assignments, not an `ObjectRoleAssignment` queryset;
  search and the role filter must then be written against that shape. `LearnerDataTable.get_queryset`
  is the closest worked example of select_related and Prefetch for a multi-row cell.
- Role filter: nothing in `filters.py` filters by a stored role value; model it on `LearnerStatusFilter`.
- Actions (`panel_framework/actions.py`): `PanelAction` (class attrs `label`, `variant`, `action_name`,
  `capability`, `trigger_template_name`, `template_name`, `success_events`; methods `permission_object`,
  `has_permission`, `is_offered`, `get_context_data`, `handle_submit`), `FormPanelAction` (ModelForm
  oriented), `CreateInstanceAction`, `EditAction`, `DeleteAction`, `form_fragment_context`,
  `denied_response`. The multi-step add (email, then role, then cohorts, then confirmation) does not fit
  `FormPanelAction`'s ModelForm contract; spec 7's `AddLearnersAction(PanelAction)` and its subclass
  `AddLearnersToCohortAction` show the plain-`PanelAction` pattern with a `forms.Form`, a preset hidden
  cohort field, `render_to_string(...)` at 422 for invalid, and
  `build_hx_trigger({EVENT: [ids]}, close_modal=...)`. Confirmation modals: `DeleteAction`'s
  `panel_framework/modal/delete_confirmation.html`, and learner-section examples under
  `educator_interface/templates/educator_interface/modal/` (`deactivate_confirmation.html`,
  `remove_from_cohort_confirmation.html`, `move_confirmation.html`,
  `resend_setup_email_confirmation.html`, `account_already_set_up.html`, `setup_email_recently_sent.html`).
  Error and outcome modals at 422 follow the HTMX convention in CLAUDE.md.
- Domain events: `educator_interface/events.py` already declares `EDUCATOR_CHANGED = "educatorChanged"`
  ("including ones nothing listens for yet"). `CohortEducatorsPanel.refresh_events = (COHORT_CHANGED,
  EDUCATOR_CHANGED)` already refetches on it. Spec 9 actions should fire it.
- Error-handling pattern for refusals: `RoleChangeRefused` is a new exception for the interface; there is
  no existing translation to a 422/403 modal. The three-part denied experience (spec 5): 404 for
  out-of-scope, 403 `panel_framework/partials/action_denied.html` for "visible but no longer permitted"
  (via `denied_response` in `panel_framework/actions.py` and `SectionConfigBase.get_denied_context`),
  controls hidden not disabled. The `htmx:beforeSwap` listener in
  `freedom_ls/base/static/base/js/alpine-components.js` swaps 403s. Tests: `educator_interface/tests/test_denied_experience.py`.
  Mapping each `RefusalReason` to user copy is new work. `SELF` and `LAST_*` are ones the UI should
  prevent by hiding or explaining, with the refusal as the backstop for races.
- "Your own row": the checked utilities refuse `SELF`. The idea's open question (show without actions
  vs hide) is therefore a pure UI choice; `request.user == row user` is enough.

## Cohort overview educators block (spec 6)

- View: `CohortEducatorsPanel(Panel)` in `educator_interface/views.py` (~line 860):
  `capability = "freedom_ls_learner_management.view_organisationmember"`, `refresh_events =
  (COHORT_CHANGED, EDUCATOR_CHANGED)`, `get_actions()` returns `[]` (the explicit hook for spec 9),
  `get_context_data` sets `educators = cohort_educators(cohort)`. Mounted in `CohortOverviewStack.children["educators"]`.
- Template: `educator_interface/templates/educator_interface/panels/cohort_educators.html` (a
  `c-panel-definition-list` of `c-panel-definition-row`, label the display name, value the role display
  name; empty state "No educators assigned to this cohort.").
- Query: `learner_management/queries.py` `cohort_educators(cohort) -> list[tuple[User, str]]` returns
  active users with an active assignment on that cohort of any role granting `view_cohort`, gated on an
  active member row, ordered by name then role. It returns `(user, role display name)` only; spec 9's
  add and remove actions on the block need the role key and the assignment (the tuple drops the key).
  Also: organisation admins and site admins do not appear in this block (it reads `Cohort` grants only).
  The idea says the "add" action is for "those allowed": capability for adding is `assign_cohort_admin` /
  `assign_cohort_viewer` on the cohort, while the panel itself needs `view_organisationmember`, which a
  cohort admin lacks (so the panel is already hidden from them).

## Learner marker ("also a learner")

- `Learner` (`learner_management/models.py`): `(user, organisation, is_active)`, unique per
  `(user, organisation)`, created through `utils.ensure_learner`. The glossary note: a user holding both
  `Learner` and `OrganisationMember` rows in one organisation is explicitly allowed (the
  `OrganisationMember` docstring says so). The marker is therefore
  `Learner.objects.filter(user=..., organisation=..., is_active=True).exists()` or a prefetch /
  `Exists` annotation. Decide whether a deactivated `Learner` counts (probably not).
  `Learner._base_manager` is used in actions to see inactive rows; plain `Learner.objects` is site-aware.

## Documentation, glossary, tests

- `docs/product/educator-interface.md` sections: Summary, Panel Interface (Cohorts, Learners, Courses),
  Organisation Scope, Access Control, Limits. The Access Control section already carries the four role
  descriptions and says "**Not yet built.** There is no screen ... for assigning roles or deactivating a
  member". The new "Educators and roles" section replaces that sentence, and the Limits section needs
  checking. Product docs changes go through `/fls-dev:update_product_docs`. Spec 7's upgrade notes
  (`3. done/2026-10-20_13:37_educator-interface-7-learner-administration/upgrade_notes.md`) and spec 6's
  are the format to follow.
- Glossary (`.claude/skills/domain-glossary/SKILL.md`): `role` and a bare `title` are "reserved, not in
  use" and mean a permission role (`assign_object_role`). `grant` means a role or object permission
  (and for course access the preferred word is registration). `educator of a learner` is coined
  (`educators_of`). There is no glossary entry for "educator" as a person-in-an-organisation, for
  "role assignment" in the interface sense, or for `OrganisationMember`'s plain-English name; the spec
  should propose them (candidates: "educator" = a person holding an active role assignment in an
  organisation, "role assignment", "scope" = organisation or the assigned cohorts). `learner` as an
  identifier means the model. `Organisation` is "a client inside a site". `is_active` is documented as
  overloaded; any sentence naming it must name the model.
- Tests: educator interface tests are in `freedom_ls/educator_interface/tests/` (`test_learner_section.py`,
  `test_actions.py`, `test_denied_experience.py`, `test_filters.py`, `test_views.py`, `test_sidebar.py`,
  `invariants/test_permission_matrix.py`, `invariants/test_organisation_isolation.py`,
  `invariants/test_config_authorisation.py`, `invariants/test_system_checks.py`, and `playwright/` flows
  like `test_learners_list_flow.py`, using `helpers.py` and `conftest.py`). `educator_interface/tests/conftest.py`
  has the `panel_request` fixture. Role tests: `freedom_ls/role_based_permissions/tests/` (`test_utils.py`
  covers `LAST_SITE_ADMIN`; `test_models.py`, `test_registry.py`, `test_loader.py`) and
  `freedom_ls/learner_management/tests/test_role_assignment.py` (one test per `RefusalReason`, including
  `LAST_ORGANISATION_ADMIN`). The permission-matrix invariants require every capability reachable from
  an action to be in `MATRIX` (`test_every_capability_reachable_from_the_interface_is_in_matrix`), so
  new actions must declare capabilities that already exist (`assign_*`, `view_organisationmember`),
  not invent strings. Read `claude_plugins/fls-dev` testing skill before writing the plan.
- Other things referencing roles that spec 9 must not break: `messaging_policy/policy.py`
  (`offered_roles_for`, `educators_of`), `qa_helpers/management/commands/qa_create_*` (many call raw
  `assign_object_role`), and `learner_management/queries.py` (`educators_of`, `colleagues_of`,
  `cohort_educators`).

## Conflicts and gaps (decide in the spec)

| # | Item | Where it bites |
|---|---|---|
| 1 | Role descriptions already exist (spec 5, `roles.py` and the product doc) and differ from the idea's draft. The idea's organisation_admin copy mentions "courses", which no permission backs. | Copy, product doc, spec 11 |
| 2 | Cohort delete leaves `ObjectRoleAssignment` and guardian rows behind; nobody owns it yet. | Spec 9 must add it (delete path in `DeleteEmptyCohortAction`, or a `pre_delete` receiver on `Cohort`, calling `remove_object_role` per active holder or deleting the rows) and test it. Hard-deleting the rows contradicts "nothing is deleted" for removal, but the target is gone; deactivate-and-sync is safer for the audit trail and still leaves dangling `object_id`. |
| 3 | `OrganisationMember` suspend and reactivate has checked code but no screen, and the idea omits it. A suspended holder looks like an active educator with no access. | List state column, add flow, docs |
| 4 | Site admins and superusers: not scoped to an organisation, so "role holders in this organisation" is ambiguous; granting `site_admin` needs a `Site` target. | List, role picker |
| 5 | No `can_assign` helper: the picker must compose `can(user, ASSIGN.format(role=...), target)`. For cohort roles the capability is checked per cohort, so "may grant cohort_admin" is true on an organisation grant, but a hypothetical future cohort-scoped granter would get a subset of cohorts. | Form design |
| 6 | One person has many assignment rows (one per cohort), each with its own `assigned_by`, `assigned_at`, `is_active`. The list's "one row per person" needs aggregation rules, and "change scope" is add-or-deactivate of rows. Removing the last cohort of a role does not remove "the role" because there is no row left; the dialog should say so, or removal of the last cohort should be refused or become "remove role". | List queryset, scope-change action |
| 7 | `assigned_at` is the first grant, not the last re-add; `assigned_by` is overwritten on reactivation. | "Added on" column accuracy |
| 8 | Spec 7's add path is bulk and learner-specific; the idea's email-first single add reuses `account_setup.match_or_create_user` and `send_account_setup_email`, not `add_learners`. The setup email is learner-neutral already. | Add action |
| 9 | `ListViewConfig` assumes a model and an instance view; an educators list keyed by user may not want a detail page. | Framework fit; may need a small framework change, which the roadmap says specs 6 to 9 should avoid |
| 10 | `FormPanelAction` is ModelForm-shaped; the multi-step add and a "confirm escalation" step will be a plain `PanelAction` with a form, like `AddLearnersAction`. | Add and scope actions |
| 11 | No existing mapping from `RoleChangeRefused` / `RefusalReason` to user-facing copy or HTTP status. | New |
| 12 | `cohort_educators` drops the role key; the cohort block's add and remove need it. | Cohort page "add" action |
| 13 | Removal of a role not held, or a repeat submit after another admin removed it, silently no-ops. Concurrent edits need a stale-page answer (cf. `DeleteEmptyCohortAction` locking and the "unavailable" fragment). | Remove action |
| 14 | Role-name drift in docs: the roadmap says "org_admin" in places; the key is `organisation_admin`. | Prose |
| 15 | Audit log does not exist; six `# TODO: AuditLog ...` comments sit in `role_based_permissions/utils.py` and must stay. Spec 9's strings are consumed by spec 11. | Keep TODOs |

status: ok
