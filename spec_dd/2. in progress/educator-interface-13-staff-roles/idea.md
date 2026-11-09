# Staff roles per cohort

Spec 13 of 13 in the Educator interface rebuild effort. Read that effort's section of
`spec_dd/1. next/roadmap.md` before starting; this idea assumes you have.

**What:** three changes to how staff are added and how their roles are shown and changed, all on
the Staff section and the cohort Settings tab that `educator-interface-9-educator-administration`
and `educator-interface-12-docs-and-polish` built.

1. **One person, several roles, each on its own cohorts.** The data model already allows it:
   `ObjectRoleAssignment` is unique per user, target and role, so a person can be `cohort_admin`
   on Cohort A and `cohort_viewer` on Cohort B today. The interface does not show it that way or
   let an admin get there. The Staff table's Roles cell lists one line per role per scope. Each
   member row gets **Add role**, which opens the Add-staff dialog at its role step with the person
   preset (no email step), so an organisation admin can be downgraded by deactivating that role
   and adding a cohort role, and a viewer on one cohort can be made admin of another. "Change
   cohorts" stays for a role held on several cohorts.
2. **Roles are viewed and changed from the cohort's Settings tab.** Spec 12 moved the Educators
   list into the Settings panel as a read-only Staff section with Add staff member. Each person
   in it gets **Change role** (admin to viewer or back, on this cohort only) and **Remove from
   cohort** (deactivate their role on this cohort). Both reuse `assign_role` and
   `deactivate_role` from `learner_management/role_assignment.py` and record the same audit
   entries `DeactivateRoleAction` and `AddMemberAction` write, so the History tab shows them.
3. **The email field searches as you type.** In the Add-staff dialog's email step, typing two or
   more characters searches the organisation's own people (its learners and staff, through
   `members_of` and the organisation's active `Learner` rows) by email and name, and shows up to
   eight matches as person chips; picking one fills the email and moves to the role step. The
   model is `comms/templates/comms/partials/recipient_picker.html` with its
   `partial_recipient_search` view (`hx-trigger="input changed delay:300ms"`, `hx-sync`, a
   `{% partialdef results %}` list). Anyone on the site is still found by typing their full
   email, as `lookup_user` does today, so a person from another organisation can be added without
   being searchable. The search never widens to every account on the site: that would let an
   organisation admin enumerate the site's users name by name.

**Why:** the product owner's walk of 5 Nov 2026. "When adding a new staff member, I need to
remember their exact email address." "They can either be a cohort admin or a cohort viewer. There
is no way to allow them to view some cohorts, and admin some others. We need flexibility! Also, if
someone was an admin and we wanted to downgrade them and give them cohort access we can't." "We
should be able to configure staff for the cohort from this page." The cohesion rule captured
that day (`.claude/skills/brand-guidelines/visual.md`, "Placement") says the controls that change
a cohort's staff sit on the cohort's Settings tab beside the list.

**Open questions:**

- Whether "Change cohorts" survives once each role line names its cohorts, or Add role plus
  per-cohort Remove covers every case.
- Whether a role swap on one cohort is one audit entry (`role.changed`) or the two it is made of
  (`role.deactivated` then `role.assigned`). The glossary's verb table in
  `fls-dev:domain-glossary` has no `changed`; two entries need no new vocabulary.
- Whether a cohort admin may search when adding a viewer to their own cohort, and what they may
  see: their cohorts' learners only, or the organisation's people.
