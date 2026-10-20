# Research: UX patterns for the educators admin screen (spec 9)

Scope: member list, add flow, scope editing, revoke, escalation, own row, "also a learner" marker, role explanation, mobile, empty states. Recommendations are written against the settled content in `idea.md`. Source coverage is partial. NN/g, Atlassian, GitHub and Google Workspace pages were read. Slack, Notion, Linear, Moodle and Canvas were not successfully read, so nothing below is attributed to them. Material Design was not fetched either.

## 1. Patterns already in the repo (stay consistent)

- Spec 7 confirmations are modal fragments. `modal/deactivate_learner_confirmation.html` has a `c-modal-header`, then a body that says what is lost and what is kept. The footer is a right-aligned `c-button-group` with a Cancel button (autofocused) and a POST button using `loading_text="Deactivating..."`.
  - Reuse this shape for revoke, re-scope and escalation.
  - Cancel is autofocused, so the safe choice is the default.
- Status is shown with `c-panel-status-badge tone/label`, rendered through a template tag (`learner_status_badge`). Role badges should use the same component with a tag-computed tone and label.
- Row cells live in `data-table-cells/*.html`, with the existing list, search and filter conventions from spec 7. Add a role cell, a scope cell and an "also a learner" cell in the same directory.
- Voice (`brand-guidelines/voice.md`):
  - Direct, plain and specific. "Name the problem, suggest the fix, leave blame out." Routine actions end on a full stop.
  - Avoid SaaS phrasing.
  - Empty-state sample: "No courses yet. Drop some Markdown files ... [See the docs]". It says what is missing and the next step.
  - Terminology table says "learners", not "students". "Administrators" is the word for the person who deploys, but the idea.md role copy already uses "school administrator" as the audience. Keep the role copy as drafted.

## 2. Mockup layout reference (layout only)

- Screen 06 is a table with a header row. Columns are Role, Scope, Holders, Last changed, and an action cell.
  - There is a one-line intro above the table: "Roles apply to everyone in ...".
  - Locked system rows show a "Locked" label plus a lock icon in the action cell, not an empty cell.
  - This is a precedent for the own-row treatment in section 6.
- Screen 06 lists roles. Our screen lists people, so only the visual grammar carries over: header strip, 62px rows, mono dates, muted secondary line under the primary label. The "Create role", "Edit", "Duplicate" and "Holders" parts are out of scope.
- Mobile M09 exists, with a "Roles" label at lines 87 to 95 of `Educator Mobile Cohorts and Admin.dc.html`. Use it for card layout only.

## 3. List pattern

- Row content: name, with email as the muted secondary line (the mockup's two-line cell). Role badge or badges. Scope line. Added by and added on, as a muted third zone.
- Scope wording. Scope is the organisation for `organisation_admin` and `site_admin`, and the named cohorts for the cohort roles.
  - Show "Whole organisation" text for the first group.
  - For cohort roles, show up to 2 cohort names, then "+N more", with the full list in the tooltip or detail.
  - This avoids unbounded row height. It is a design judgement, not sourced.
- A person with several roles gets one row with several badge and scope pairs. `idea.md` already says one row per person.
- Search by name or email (single input, debounced HTMX GET) plus a role filter as a select. Both follow spec 7.
  - Keep filters in the query string so the list is linkable and the back button works.
- Sort by name by default. Show the total count as "N educators".

## 4. Add flow

Sequence from `idea.md`: email, then role, then scope (cohort roles only), then confirmation. Evidence:

- Atlassian modal guidance says avoid multi-step flows inside a modal, avoid complex interactions, and never open one dialog from another. Source: https://atlassian.design/components/modal-dialog/usage
  - Recommendation: make "Add educator" a full page (or a page-level panel) with one form that reveals sections progressively, not a modal wizard.
  - Reserve modals for the short confirmations.
  - The confirmation step in the flow should be an inline summary on the same page ("Priya Naidoo will be able to: ...") with a submit button. Do not open a second dialog from the form.
- Email first, with an existing-user match shown inline before the role step. This is a design judgement and was not verified against a source.
  - If the address matches an existing user, show their name ("Found: Priya Naidoo").
  - If it is new, say "No account yet. We will create one and send a setup email."
  - This makes the "existing user or new account" fork visible without asking the person to choose it.
- Role picker as radio cards, one card per grantable role.
  - Title plus the one-sentence description from `idea.md` under it.
  - Show only roles the current user may grant. Do not show greyed-out roles. This matches the house hide rule.
  - Radio cards beat a select here because the description is the point.
  - Do not preselect a role. NN/g advises against defaulting to the consequential choice (https://www.nngroup.com/articles/confirmation-dialog/).
- Scope picker appears only after a cohort role is selected, listing active cohorts of this organisation.
  - Use a searchable multi-select of checkboxes, with a count ("3 cohorts selected").
  - Require at least one cohort. A cohort role with no cohorts grants nothing and confuses the list.
  - Say so in an inline message, not only on submit.
- Use verb button labels that match the page title: "Add educator". Atlassian says the primary action should match the modal title and use action verbs. Source: https://atlassian.design/components/modal-dialog/usage
- On validation errors return HTTP 422 with the form fragment (project convention).
- Google Workspace's pattern for reference: a super admin opens the user, switches to "Admin roles and privileges", and can assign specific roles rather than full access. The user page also lists their privileges. Source: https://knowledge.workspace.google.com/admin/users/make-a-user-an-admin
  - It starts from the person, then offers the role. That supports the email-first order.

## 5. Revoke, re-scope and escalation confirmations

- NN/g, "Confirmation Dialogs Can Prevent User Errors (If Not Overused)". Source: https://www.nngroup.com/articles/confirmation-dialog/
  - Reserve confirmation for serious actions.
  - Be specific, not "Are you sure?".
  - Label buttons with the outcome ("Remove role" and "Keep role"), not Yes and No.
  - Do not default to "Yes".
  - Use nonstandard actions such as typing a word only for rare, most-dangerous cases.
  - Provide undo wherever possible.
- Applied to this screen:
  - Revoke gets a confirmation, because it is access loss (idea.md requires it). Name the person, the role, the scope, and what they lose. Example: "Priya Naidoo loses access to learners and progress in Grade 8A and Grade 8B. Their account and any learner record are kept. You can add the role again later."
  - Say what is kept (spec 7's modal does the same: "kept and return when you reactivate").
  - Cancel is autofocused and visually secondary. The destructive button uses the verb ("Remove role").
  - Removing a single cohort from a scope gets a lighter confirmation of the same shape. Do not make the user confirm adding a cohort that narrows nothing.
  - Escalation (add a cohort, or change role to a higher one) names the widening: "Adding Grade 9C lets Priya Naidoo manage 41 more learners." This is the spec's explicit confirmation. Prefer a count of learners affected, since concrete numbers make the stakes clear.
  - Do not require typed confirmation, even for organisation admin grants. It is routine for this audience and would train click-through. Reserve it for nothing in this spec.
  - Undo: after revoke, show a flash with the removal and a link back to the add form prefilled with the same person and role. This approximates undo without building new state. Because the models deactivate rather than delete, true undo (reactivate the assignment) is feasible if the spec wants it. Flag this as a decision for the spec.
- GitHub removal is a useful reference for naming consequences. It lists exactly what the member loses, what is cancelled, and that membership data is kept for three months so reinstatement restores it. Source: https://docs.github.com/en/organizations/managing-membership-in-your-organization/removing-a-member-from-your-organization
  - Copy the structure: "loses X", "kept: Y", "can be restored by Z".
- Modal mechanics from Atlassian: close button in the header, Esc and outside-click dismiss, footer buttons right-aligned with the primary on the right. Source: https://atlassian.design/components/modal-dialog/usage
  - NN/g's secondary-source note about not placing the confirm button where the trigger was is unverified. Spec 7's modal already avoids it by being a separate dialog.

## 6. The current user's own row

Three options:

1. Hide the row. Confusing, since the person looks themselves up to check their own access.
2. Show the row with disabled, greyed action buttons and no explanation. Looks like a bug.
3. Show the row, replace actions with a short muted explanation.

Recommendation: option 3.

- The mockup's locked system role uses "Locked" text plus a lock icon in the action cell (screen 06). That is the same grammar.
- Cell copy: "You" next to the name, and in the action cell a lock icon and "You cannot change your own role. Ask another administrator."
- On mobile, put the same line under the row's summary.
- The same treatment applies to rows the current user may not change for other reasons. Examples are a site admin when the viewer is only an organisation admin, and the last site admin.
  - Use a specific reason each time: "Only site admins can change this role."
  - Reasons are cheap to render because the permission check can return the reason string.
- This resolves the idea.md open question and the house hide rule: hide actions the person has no concept of using, show a reason where the row itself is meaningful. The server must still enforce the rule, not only the template.
- Google Workspace guards the last super admin by requiring a transfer: assign the new admin first, then they remove the original. Source: https://knowledge.workspace.google.com/admin/users/make-a-user-an-admin
  - For the "last site admin" and "last organisation admin" rules, explain the way out in the reason text: "Add another organisation admin first."

## 7. "Also a learner" marker

- No sourced precedent was found. A design judgement: a small neutral (non-status) badge or an icon with text "Also a learner", placed beside the name.
- It is neutral because it is not a warning. Do not use a warning tone.
- Link it to the learner page when the viewer may open it. A plain label otherwise.
- Do not show it as a role badge, because it is not a role the educator administers here.

## 8. Role explanation

- Inline one-sentence descriptions in the add form's radio cards, plus a one-paragraph help text above the list (idea.md default). This fits the evidence:
  - The mockup's dedicated page exists because custom roles need an editor. With four fixed roles, a page would be mostly static text duplicated from the cards.
- Show the same strings in the role-change confirmation and the revoke confirmation, so one string source feeds the form, confirmations, audit log and docs (idea.md already requires this).
- Put the role description as a tooltip or a muted line on the role badge in the list. On desktop use a tooltip. On mobile show nothing extra (no hover), and rely on the help paragraph.
- Optional escape hatch if reviewers want a roles page: a read-only page that renders the same strings from the same constants. It costs one template and no new data.
- Google Workspace shows a user's privileges list on their admin-role page, so people can check what a role grants. Source: https://knowledge.workspace.google.com/admin/users/make-a-user-an-admin
  - Equivalent here: a row's expanded detail ("What this person can do") using the role description.

## 9. Mobile layout

- Replace the table with stacked cards below the table breakpoint, as the mockup M09 does (layout reference only).
- Card contents, in order:
  - Name and email.
  - Role badge or badges.
  - Scope line.
  - "Added by X on date" in muted text.
  - Actions: one primary "Change scope" and an overflow menu for "Remove role".
- Keep tap targets at least 44px.
- Search above, role filter as a full-width select under it.
- The add flow is already a single page, so it works on mobile unchanged.
  - Radio cards stack vertically.
  - The cohort multi-select becomes a full-width checkbox list with a sticky "N selected" bar. This sticky bar is a design judgement.
- Confirmation modals: Atlassian's modal guidance does not cover mobile. Spec 7's modal already uses `flex-wrap` in the footer, so reuse it.

## 10. Empty states

- Voice sample: say what is missing and the next step.
- No educators matched the search or filter: "No educators match 'priya' as Cohort admin. Clear the search or choose another role." Include a clear-filters link.
- Org has no educators other than the viewer: show the viewer's row (so the list is never blank) plus a hint, "You are the only educator here. Add someone to share the work."
- Cohort picker has no active cohorts: "This organisation has no active cohorts yet. Create a cohort first." Link to cohorts.
  - Disable the cohort roles in the role cards when it is true, and say why. This is the one case where showing a disabled option is justified, because the reason is not about permission.
- Viewer may not add educators: hide the "Add educator" button. The list stays visible if view is allowed.

## 11. Open questions this research leaves for the spec

1. Undo after revoke: a "Restore" link on the flash message, or a plain re-add?
2. Is the cohort-count line on the escalation confirmation affordable query-wise, since it needs a learner count per added cohort?
3. Whether the cohort-page "add" action opens this same page with the cohort preselected (recommended, to avoid a second implementation).

## Sources

- NN/g, Confirmation Dialogs Can Prevent User Errors: https://www.nngroup.com/articles/confirmation-dialog/
- Atlassian Design System, Modal dialog usage: https://atlassian.design/components/modal-dialog/usage
- GitHub Docs, Removing a member from your organization: https://docs.github.com/en/organizations/managing-membership-in-your-organization/removing-a-member-from-your-organization
- Google Workspace, Make a user an admin: https://knowledge.workspace.google.com/admin/users/make-a-user-an-admin
- Local: `freedom_ls/educator_interface/templates/educator_interface/modal/deactivate_learner_confirmation.html`, `data-table-cells/learner_status.html`, `.claude/skills/brand-guidelines/voice.md`, mockups `Educator Cohorts and Admin.dc.html` (screen 06) and `Educator Mobile Cohorts and Admin.dc.html` (M09).

status: ok
