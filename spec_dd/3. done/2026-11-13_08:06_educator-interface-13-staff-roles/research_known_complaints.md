# Known complaints: staff and role management

Sourcing is thin: three web searches (Moodle, Canvas, GitHub). Open edX and Google Workspace were not
covered. Items marked (inference) are reasoning, not sourced.

## 1. Inherited access nobody can see
Moodle: a Teacher role assigned at category level applies to every course in it. Removing someone from
one course does not remove inherited access; admins must open the user's "role assignments" page to
find the leftover assignment. Multiple roles merge, so a remaining role elsewhere keeps access alive.
Sources: https://docs.moodle.org/503/en/Assign_roles
**Spec should:** show org-wide role holders in the cohort Staff section read-only with their org role
(already decided), and say plainly that Remove from cohort does not remove org-wide access. After a
removal, the Staff table should still show any remaining role lines for that person.

## 2. Cannot downgrade without losing access
Canvas: downgrading a root-level admin means adding a lower role at sub-account level and removing the
root role, and users are unsure how it works. Sub-account admins also complain about broad
all-or-nothing permissions ("Account-level settings - manage" is too coarse).
Sources: https://community.canvaslms.com/t5/Canvas-Question-Forum/Prevent-sub-account-admins-from-acting-as-specific-user-top/m-p/590127 ,
https://community.canvaslms.com/t5/Question-Forum/The-quot-Account-level-settings-manage-quot-permission-is-to/m-p/468129
**Spec should:** make the downgrade one flow: Add role (cohort role) first, then deactivate the
org role, so the person is never left with no access mid-way (inference). Keep roles narrow: the new
organisation staff viewer role should grant only the staff list, nothing else.

## 3. Pickers that leak other users, versus exact-email pain
GitHub: org invites moved to exact-email match after privacy (GDPR) concerns about names being returned
in search; users complained but the exact-email rule stands. This is one forum account, not official.
Source: https://community.sonarsource.com/t/unable-to-manually-add-github-members-anymore/124975
**Spec should:** keep the planned split: as-you-type search limited to the organisation's own people
(and, for a cohort admin without the staff viewer role, to their own cohorts' staff); a full email for
anyone else, with the result never revealing the name of a person outside the organisation. Cap at
eight results and require two characters so it cannot be used to list everyone.

## 4. Scoped admins granting beyond their own level (inference, from Canvas "act as" thread)
Canvas sub-account admins could act as a higher admin who had added themselves to every sub-account.
Source: same Canvas thread as section 2.
**Spec should:** enforce on the server, not only by hiding buttons, that a cohort admin can grant only
viewer or admin inside their own cohorts, and cannot promote a learner to staff. Test the forbidden paths.

## 5. Stale access after removal (inference, with Moodle source above)
Removing someone from the organisation but leaving cohort roles active is the classic leftover.
**Spec should:** removing organisation staff membership deactivates every role and writes one audit
entry per role (already decided). Cover with a test that no active role survives.

## 6. Audit history hard to read (inference; no source found)
A swap shown as two entries can read as two unrelated events.
**Spec should:** make the two entries (`role.deactivated`, `role.assigned`) carry the same actor, the
same timestamp window, the person and the cohort, so History reads as a pair; name the cohort and role
in each entry's text, not just IDs.

status: ok · reason: web sourcing partial (Moodle, Canvas, GitHub only); Open edX and Google Workspace not covered
