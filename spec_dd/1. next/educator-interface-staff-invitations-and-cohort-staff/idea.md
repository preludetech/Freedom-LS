# Staff invitations and cohort staff

## What

1. **Pending invitations.** When a staff member is added and a new account is created, FLS sends a setup email. The Staff page (`/educator/organisations/<org>/staff`) shows who has not yet set up their account, with the date the invitation was last sent.
2. **Resend.** A staff admin can resend the invitation to someone who has not accepted it. Learners already have `ResendSetupEmailAction`; staff get the same.
3. **Cohort Staff tab.** A cohort's staff move out of the Settings tab into their own Staff tab. Anyone who can see the cohort can see who is assigned to it. Adding, changing and removing staff still needs the permissions it needs today (`CHANGE_COHORT` or `ASSIGN_COHORT_VIEWER`).

## Why

Admins cannot tell whether a new colleague ever got in, and have no way to send the email again. People who teach a cohort cannot see who else is on it, because the staff list sits behind settings permissions.

## What is settled

- "Not yet accepted" means the account has not been set up through the setup email.
- A resend is written to the audit log, as the learner resend is.
- The cohort tabs become Overview, Learners, Staff, Courses, Report, Settings and History. Settings keeps the Name and Status panels.
- Who can see the Staff page does not change. `organisation_staff_viewer` and `organisation_staff_roles_viewer` already can.

## Open until the spec

- Whether a resend is rate-limited.
- Whether "sent" records only the first email or every resend.
- Whether a cohort viewer sees staff roles on the Staff tab, or names only, matching `organisation_staff_viewer`.

## Out of scope

- Messaging a staff member from the Staff tab or the staff quick view: `educator-interface-message-from-anywhere`.
- Invitation expiry.

## Resources

- Staff page on a phone: `spec_dd/3. done/2026-11-06_08:20_educator-interface-12-docs-and-polish/screenshots/phone-staff.png`.
- `fls-dev:educator-interface` skill and `research_comparable_systems.md` section 6 in `educator-interface-page-polish`.
- Designs needed: the pending state on the Staff page and the cohort Staff tab.
