# Answers: educator-interface-13-staff-roles

Asked by `/sdd:start` before the spec was written.

- Q: Once each Roles line on the Staff table names its cohorts, does "Change cohorts" stay for a role held on several cohorts? → A: Keep it. (asked up front)
- Q: When Change role swaps admin↔viewer on one cohort, how many audit entries does History show? → A: Two entries, `role.deactivated` then `role.assigned`; no new verb. (asked up front)
- Q: A cohort admin adding a viewer to their own cohort: what does the as-you-type email search show them? → A: Maybe make another role/permission for an organisation-staff viewer. Someone can add any staff member they can see. Don't allow someone to make a learner into a staff member if they have cohort edit access. Only organisation admins can add new staff members. When an org admin adds a new staff member, they don't need to give them roles immediately if they don't want to. (asked up front)
- Q: The cohort Settings Staff section also lists people whose access comes from an organisation-wide role. Do they get Change role / Remove from cohort there? → A: Read-only there, shown with their org role and no cohort controls. (asked up front)
- Q: Someone counts as staff today only because they hold a role. If an org admin adds a staff member with no roles yet, how is that stored? → A: A separate staff membership (a new model recording organisation staff membership, independent of roles). (asked up front)
- Q: What does the new "organisation staff viewer" role allow? → A: Its holder sees the organisation's whole staff list, so a cohort admin who holds it can add any of them to their own cohorts. Without it, they see only their own cohorts' staff. (asked up front)
- Q: When a cohort admin adds staff to their own cohort, which roles may they grant there? → A: Viewer or admin (own level and below, inside own scope). (asked up front)
- Q: The answers add a staff-membership model, an organisation staff viewer role and add-staff rules. Keep it all in one spec? → A: One spec. (asked up front)
- Q: When someone's organisation staff membership is removed, what happens to their cohort roles? → A: Deactivate all their roles, one audit entry per role. (asked up front)
- Q: On a cohort's Settings tab, may a cohort admin change or remove their own role on that cohort? → A: No; the controls are hidden on their own row. An org admin or another cohort admin makes the change. (asked while research ran)
- Q: Who may grant the organisation staff viewer role? → A: Org admins only (and site admins). (asked while research ran)
- Q: A `StaffMember` model already exists (one row per user and organisation, with `is_active`). Use it for a staff member with no roles? → A: Reuse `StaffMember`; it replaces the "separate staff membership" answer above. No new model. (asked while research ran)
- Q: Deactivating a `StaffMember` today suspends them: roles stay untouched and come back on reactivation. Keep that, or deactivate every role? → A: Keep suspend. This replaces the "deactivate all their roles" answer above. (asked while research ran)
- Q: The glossary reserves "removed" for deleted rows. What does the per-person button on the cohort Settings Staff list say? → A: "Remove from cohort", a deliberate copy exception; the audit verb stays `role.deactivated`. (asked while research ran)
- Q: May Change role or Remove from cohort leave a cohort with no cohort admin? → A: Allow it; org admins can always manage every cohort. (asked while research ran)
