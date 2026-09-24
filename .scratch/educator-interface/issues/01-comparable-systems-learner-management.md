# Comparable systems: learner-management actions

Type: research
Status: resolved

## Question

What do comparable systems (Moodle, Canvas, Open edX, TalentLMS, Docebo, LearnDash, Google Classroom) let school or organisation staff do to administer learners, cohorts/groups, course enrolment and other staff? Which of those actions are common versus long-tail? Which are bulk-only? What audit and reversibility do users expect (deactivate vs delete, undo, history)? Which gaps do users complain about?

Compare the findings against the capability list in the map's Notes and report:

- actions on that list the comparable systems handle in a notably better way, and
- common actions missing from the list.

Exclude deadlines, communications, application review and retakes (out of scope).

Prior material: `spec_dd/1. next/educator-interface-full-polish/learner-management-actions/idea.md` (its "TODO: research" section), `01. educator interface critical functionality/research_lms_educator_ux.md` and `research_permission_ux_patterns.md`. Don't redo what they already cover; extend them.

## Answer

All seven systems separate a reversible "off" state from delete, and that is the pattern to copy. Deactivate keeps everything and flips back. Delete is harder to reach and usually blocked or restorable. Nobody has a general undo button. Reversibility comes from flags in the data model. FLS already has the flags (`Learner.is_active`, registration `is_active`) and already keeps progress through removal, which puts it ahead of Moodle's off-by-default "recover grades" checkbox.

Common actions missing from the capability list (candidates only, scope is the human's call):

1. Reactivate learners, cohorts and registrations. Every system with deactivate has the way back, and bulk activate sits beside bulk deactivate.
2. A staff-readable audit log: actor, action, target, organisation, time, optional reason on removals. Five of seven have one; Open edX makes staff give a reason to unenrol. FLS has no audit model.
3. Pending-invitation state and revoking an invite, to go with "resend invite".
4. Roster export (cohort learners plus educators as CSV). Probably inside "downloadable reports", but name it.
5. Edit a learner's name or email. `User` is shared across organisations, so this is `site_admin`-only or stays in the Django admin.
6. Registration access start and end dates. Five systems have them, but they sit close to deadlines (out of scope), so flagged rather than recommended.

Not worth adding: account merge, log in as a learner, rule-based auto-registration, self-join codes. They are long-tail, risky, or already covered by cohort registration.

Actions on the list others do notably better:

- CSV import: Moodle's explicit modes plus preview. FLS should label every row in the preview (new account, existing account joined, already a member, reactivated, error) and never overwrite an existing `User`'s details by default.
- Unregistration: Canvas separates deactivate from delete. In the educator interface, "unregister" should mean `is_active=False` and read as reversible. No hard delete.
- Cohort delete: Canvas refuses to delete a group with members, Google requires archive first, Open edX forbids it. Allow delete only for an empty cohort, otherwise offer deactivate.
- Learner "remove" should be deactivate. Hard `User` deletion stays in the Django admin.
- Bulk: every bulk add needs a bulk remove (Moodle's MDL-61007 complaint). Run big batches in the background with a result summary (Docebo does this over 250 users).
- Move: FLS is ahead. Moodle has none and gets complaints about it.

**Context.** [research/comparable-systems-learner-management.md](../research/comparable-systems-learner-management.md): per-system source notes with a URL for every claim are in its appendices. Claims resting on community sources are marked unverified; TalentLMS and Docebo help pages were read via search extracts (direct fetches returned 403).
