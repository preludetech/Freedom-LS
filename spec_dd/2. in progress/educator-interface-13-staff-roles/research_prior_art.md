# Prior art: staff roles per cohort (spec 13)

Question: what has been tried here or elsewhere, and what happened. Done specs live under
`spec_dd/3. done/<date>_<name>/` (date-prefixed folders).

## 1. Corrections to the idea and answers (read first)

1. **`StaffMember` already exists.** `freedom_ls/learner_management/models.py:211`
   (`unique_staff_member_per_organisation`, `is_active`, `created_at`). Its docstring: the
   counterpart of `Learner`; "the gate `can()` checks before an organisation- or cohort-level role
   assignment counts"; deactivating suspends every grant it covers without touching the
   assignments. (Spec 9 called this `OrganisationMember`; spec 12 renamed it.) So answers.md Q5/Q9
   ("a new model for staff membership independent of roles") collides with an existing model that
   is already independent of roles, row-wise. The spec must decide: reuse `StaffMember` (a
   staff member with no roles is then just a `StaffMember` row with no assignments) or justify a
   second model. Note the current list is built from assignments, not `StaffMember` rows (spec 9
   R4: "spec 5 shipped no backfill of member rows"), so a roleless staff member would not show up
   today. Also `ensure_staff_member` and a `post_save` receiver on `ObjectRoleAssignment` create
   an active row on any grant; `set_staff_member_active` (`role_assignment.py:162`) already
   deactivates with the last-org-admin lock and writes `staff_member.deactivated/reactivated`.
   Answer Q9 ("deactivate all roles, one audit entry per role") differs from the existing
   suspension semantic (roles untouched, restored on reactivation). Needs an explicit choice.
2. **`members_of` does not exist** in `freedom_ls/` (no definition anywhere). Only `educators_of`
   (`learner_management/queries.py:870`) and `cohorts_visible_to`, `site_level_admins`,
   `active_organisation_admins`. The idea's "through `members_of`" refers to something to be
   written or to a misremembered name. `members_of_cohort` in `learner_management/admin.py:58` is
   an unrelated admin scope constant.
3. **`AddMemberAction` is now `AddStaffMemberAction`** (`educator_interface/actions.py:1710`),
   with `AddStaffMemberToCohortAction` (2044), `StaffRoleAction` (2067), `DeactivateRoleAction`
   (2111), `ChangeCohortsAction` (2217), `DeactivateStaffMemberAction` (2365),
   `ReactivateStaffMemberAction` (2407). Dialog is a single action URL with `step` field
   (`lookup` vs submit), `StaffEmailForm` / `AddStaffMemberForm` in `forms.py:206/212`.
4. **Audit entries are written by the util layer, not by the actions.**
   `role_based_permissions/utils.py` calls `_record_role_change("role.assigned" ...)` (lines
   ~319, 388) and `"role.deactivated"` (349, 439) and `"role.removed"` (60, on cohort delete).
   So `assign_role` / `deactivate_role` already audit; Change role = two calls gives the two
   entries for free. No new verb. `fls-dev:domain-glossary` verb table confirms: `assigned`
   (opposite is `role.deactivated`), `deactivated`, `removed` only for deleted rows; `changed` is
   absent. Nouns include `role` and `staff_member`. Audit action labels are registered in
   `audit_log/actions.py` (group "Staff and roles", lines ~194-197).

## 2. What spec 9 (educator administration, done 2026-10-22) decided

Source: `spec_dd/3. done/2026-10-22_11:25_educator-interface-9-educator-administration/1. spec.md`.

- Decision 1: views call only the checked entry points `assign_role`, `remove_role` (now
  `deactivate_role`), `set_organisation_member_active` (now `set_staff_member_active`); the grant
  check, self check and last-admin lock live there and must not be duplicated.
- **Changing a role in place was explicitly Out of scope**: "Roles add up: to move someone from
  cohort viewer to cohort admin, add the new role and remove the old one." Spec 13's Change role
  as add + deactivate is consistent with this; it is a UI composition, not an in-place edit.
- `grantable_roles(grantor, organisation)` returns frozen `GrantableRole(role, cohorts|None)`;
  source of every form choice and POST validation; cached on the request (now
  `grantable_roles_for(ctx.request)`). Cohort roles carry only cohorts where the
  `assign_<role>` capability passes, built from `_granted_cohorts` and the `cohorts_visible_to`
  pattern, never a `can()` call per cohort. Answer Q11 ("viewer or admin, own level and below,
  inside own scope") is what this already does; verify before building anything new.
- Self rule: grantor cannot change own roles (`RefusalReason.SELF`); own row shows lock icon and
  "You can't change your own roles. Ask another organisation admin."
- Last-org-admin lock (`LAST_ORGANISATION_ADMIN`) with site-level admins exempt but warned.
- Site-level admins (superuser, `site_admin`) are listed only through a role held in the
  organisation (Decision 3). This matters for "org-wide role people read-only in the Settings
  Staff section" (answer Q4).
- Account-enumeration stance (R6, research_best_practices lines 51-52): lookup matches
  **case-insensitive exact email only**, "not a prefix search, so the form cannot be used to
  browse the user base"; "Do not offer autocomplete of users from other organisations." Spec 13
  deliberately reverses this for the organisation's own people only; the other-site/other-org
  rule (full email only) is kept. The spec should say so explicitly and keep the other-site
  message (`OTHER_SITE_MESSAGE`, `EmailInUseOnAnotherSite`) free of the other account's name.
- Lookup helper `lookup_user(site, email)` (`accounts/account_setup.py:50`): strips, normalizes,
  `User._base_manager.filter(email__iexact=...)`, spans every site on purpose, raises
  `EmailInUseOnAnotherSite` for a match on another site. Search-as-you-type must be a separate
  path; do not loosen `lookup_user`.
- Confirmation step restates role description and scope; for an existing holder shows current
  roles next to after; duplicates answer 422 ("<name> already holds this role on these
  cohorts"). Add-role-for-a-person reuses this step.
- Cohort-checklist research: search box, selected count, and the note that choosing every
  cohort is not the same as organisation admin (research_known_complaints line 71).
- R9: cohort deletion deletes (not deactivates) role assignments and guardian rows, via
  `pre_delete`; this is why `role.removed` exists.
- QA (spec 9 qa_report): all pass; section 11 isolation and enumeration passed
  (cross-organisation `remove_role` / `change_cohorts` POSTs answer 404, other-site message never
  names the account). Known quirk noted in QA line 281: searching "Eve" matched "Vee" by
  substring. Mobile: Add member bottom sheet fits at 375; on the cohort-checklist step Cancel/Add
  sit below the fold until scrolled.

## 3. Spec 12 (docs and polish, done 2026-11-06)

- `deliberately_left.md` row 11 is the origin of spec 13: three missing capabilities (different
  roles on different cohorts, Change role / Remove on the cohort Settings Staff list, as-you-type
  email search), left because they change the Add-staff flow and the Staff table together.
- qa_report B6 (UNRESOLVED at close): Staff Roles cell reads "Added <date> by Not recorded" when
  `assigned_by` is null. Copy decision pending: drop the "by" clause. The Roles cell is being
  reworked here (one line per role per scope), so settle B6 in the same change.
- qa_report 9.9 passed: Add staff role step, Move and Change cohorts sheets at 375 keep Cancel
  and the action visible; long emails wrap. B11: the layout probe flags `.truncate` and sr-only
  text; do not "fix" those. A mobile overflow was flagged on the Staff page from a long email in a
  `.truncate` span (probe artefact, `scrollWidth` 390).
- QA 3-staff: Deactivate role / Deactivate staff member / Reactivate staff member dialogs use
  question titles, Cancel focused, primary confirm. New Change role and Remove from cohort
  dialogs should follow.

## 4. Rules from skills that constrain spec 13

`.claude/skills/brand-guidelines/visual.md`:
- Placement table: "A cohort's Settings tab | The name field, the Staff list with Add staff
  member, Deactivate, Delete". A control that changes a thing sits where the thing is shown; a
  Settings tab holds only actions with no home of their own. So Change role / Remove from cohort
  on each person in the cohort's Settings Staff list is the mandated place (and the table row on
  the Staff page for Add role / Change cohorts). The Placement table needs a row update for
  Change role and Remove from cohort.
- Every button label on one line at 375, 768 and 1280 px. A person is linked with the
  avatar-and-name person link. Status badges carry one of five tones; a non-status label is a chip
  (the search results should be "person chips", per the idea).
- Separate outcomes get separate panels.

`.claude/skills/brand-guidelines/voice.md`:
- "Deactivate role" and, at the bottom of the cell, "Deactivate staff member" (never "Deactivate"
  twice in a row). "staff member" is the noun on every button and dialog about a `StaffMember`:
  "Deactivate staff member", "Reactivate staff member", "Add staff member".
- A Staff page opens with heading, search and filters, not an explanatory paragraph.
- Empty states state the fact and the next step; disabled-with-reason beats enabled-then-error.

`claude_plugins/fls-dev/skills/domain-glossary`:
- "Deactivate/Reactivate" for `is_active` flips, state word "Inactive", never "Removed",
  "Suspended", "revoked". "Remove from cohort" in the idea means a deactivation of the role on
  this cohort (an `is_active` flip), which strictly makes "Remove" a mismatch with the glossary
  (`removed` = row deleted). Either label it "Deactivate role" there or record a deliberate
  exception; the idea and answers both use "Remove from cohort". Flag for the spec.
- `role` as an identifier is a permission role; a bare "title" is reserved. A new "organisation
  staff viewer" role needs a name that fits `organisation_*` / `cohort_*` and `STAFF_ROLES`
  (`learner_management/queries.py`), plus a `Role` entry with `description` in
  `role_based_permissions/roles.py` (spec 9 R1 made descriptions the single source of truth) and
  a capability that passes `invariants/test_config_authorisation.py` and
  `invariants/test_permission_matrix.py`.
- Other relevant skills: `panel-framework` (actions, dialogs, `view_capability`,
  `refresh_events`; 422 for validation errors via the HTMX conventions in CLAUDE.md),
  `multi-tenant`, `template`, `testing`, `frontend-styling`, `playwright-tests`.

## 5. Precedent for the search UI (comms recipient picker)

- `comms/messaging.py:576 search_recipients(sender, site, term, include_email, candidates,
  scope)`: narrows an already-authorised `candidates` queryset, so "a name the sender may not
  message looks the same as a name that does not exist"; min term length `PICKER_MIN_TERM_LENGTH`
  (2); results capped (`PICKER_RESULT_LIMIT`, 20, with `truncated`); every word must match some
  of first/last/email (`icontains`), ordered by name. `messaging_views.py:685
  partial_recipient_search`, `_offered_recipients` (566). Spec 13's 8-match cap and org-scoped
  candidate queryset fit this shape; candidates must come from a server-side scope function
  (never from request input) and `site` filtered explicitly.
- `site` must be filtered explicitly in helper code: the site-aware manager narrows only inside a
  request (note in `search_recipients` docstring).
- Spec 9 QA saw substring matches ("Eve" matches "Vee"); `icontains` per word is the same
  behaviour, expected.

## 6. Open design risks surfaced by the history

- Answer Q3 changes who may add staff: "Only organisation admins can add *new* staff members"
  (creating a `StaffMember`/account with no role) vs cohort admins adding *existing visible*
  staff to their cohorts. Today `AddStaffMemberAction` capability is
  `freedom_ls_learner_management.add_staffmember` on the organisation and `is_offered` follows
  `grantable_roles`; the cohort variant uses `assign_cohort_viewer` on the cohort. Splitting
  "create staff" from "assign existing staff" needs separate capabilities.
- "Don't allow someone to make a learner into a staff member if they have cohort edit access":
  an existing `Learner` is also visible in the picker (idea item 3 says learners and staff are
  searched). Cohort admins searching must exclude learners who are not staff, or the add must be
  refused server-side; the check belongs in the checked entry point, not only in the form.
- Last-admin lock and self rule apply to Change role (deactivate then assign): do the pair in one
  `transaction.atomic()`, assign first or lock-aware order so a failed second step does not leave
  the person with neither role (spec 9 used one atomic block for Change cohorts). Downgrading an
  organisation admin by deactivating the org role must still trip `LAST_ORGANISATION_ADMIN`.
- Role-less staff members and `StaffMember` list: today's Staff table is built from assignments;
  roleless people need a list source (the `StaffMember` rows) and a visible "no roles" state.
- Settings Staff section currently also lists org-wide-role people (answer Q4: read-only).
  Site-level admins stay listed only through a role held (spec 9 Decision 3).
- Mid-session removal and stale submissions: every action re-reads the assignment and answers
  `action_unavailable` when inactive (spec 9 R8 / spec 5). Change role needs the same.

## 7. Elsewhere (brief)

From spec 9's own web research (`research_known_complaints.md`, `research_best_practices.md`,
indicative, vendor pages via search summaries): LMS role UIs commonly fail on per-course/cohort
scoping (a single role per user), hidden last-admin lockouts, and silent privilege widening;
Moodle, Canvas and Google Workspace per-scope role assignment show the "add role and remove old"
pattern. OWASP account-enumeration guidance targets public flows; for authenticated staff-only
forms the practical stance is exact-match lookup and no autocomplete across organisations, which
spec 13 honours by scoping search to the organisation's own people.

status: ok · reason: complete; key finding is that StaffMember and the audit hooks already exist and `members_of` does not
