# UX patterns research: staff roles per cohort

Scope: patterns for showing several scoped roles per person, adding a role to an existing member, per-cohort change/remove, read-only inherited access, adding a member with no roles, and an as-you-type people picker. Fitted to `panel-framework` and `brand-guidelines` conventions. Terms for other systems are theirs (attributed); FLS terms follow the project vocabulary (cohort, organisation, staff, role).

Evidence quality: Google, Linear, Notion and WAI-ARIA findings are from fetched or searched docs. GitHub and Slack pages did not yield detail (GitHub page did not describe inherited-access display; no Slack results). Where a point is my judgement, it says so.

## 1. Several scoped roles in one table cell

What other systems do:
- Google Workspace: a user can hold several admin roles and each role is restricted to chosen organizational units (an "All organizational units" scope with Edit). Role and scope are two attributes of one assignment. https://knowledge.workspace.google.com/admin/users/assign-specific-admin-roles
- Linear: guests are scoped to specific teams (one or several), and the scope is part of the member's identity in the list. https://linear.app/docs/members-roles
- Notion: guests are scoped to individual pages/teamspaces. https://www.notion.com/help/add-members-admins-guests-and-groups

Recommended shape (fits panel-framework "list of records in a panel": same fields in the same places, no dash-joined sentences):
- One line per (role, scope) pair. Role name in `font-medium` (or a `c-chip`, since a role is a label and not a status), scope under it in `text-sm text-muted` using the single relation word the framework mandates: "via Cohort A" for a cohort, "Whole organisation" for an org-wide role.
- A role held on several cohorts: either one line with the cohort names listed (and "Change cohorts" beside it, as the answers keep it) or one line per cohort. With more than about three cohorts, collapse to "Cohort A, Cohort B and 4 more" plus the Change cohorts control; do not let the cell grow unbounded. (Judgement.)
- Keep the order stable: organisation-wide roles first, then cohort roles, alphabetically by cohort. Stable order lets a reader scan a column.
- Per-item buttons (Change cohorts, Deactivate role) come first inside `<c-data-table-actions>`; the row's own action (Deactivate staff member) last. "Add role" is a row-level button, small size. Distinct verbs: "Deactivate role" must not sit beside a bare "Deactivate". Panel-framework skill, "Triggers and buttons".
- Empty roles (a staff member with no roles yet, see section 6): show muted "No roles yet" in the cell, never a blank cell, so the row does not look broken.

## 2. Adding a role to an existing member

- Linear and Notion both change/convert a member from the member row (overflow menu, "Convert to member"), not via a separate invite flow. Google starts either from the role (Assign admin, then Assign members) or from the user. https://linear.app/docs/members-roles , https://www.notion.com/help/add-members-admins-guests-and-groups
- Recommended: "Add role" on the member row opens the existing Add-staff dialog at the role step with the person shown as a fixed, non-editable line (`<c-panel-person-link>` avatar and name, plus email in muted text), so the admin sees who they are acting on. Do not render a disabled email input; show the person as text. The dialog title names the person ("Add a role for Sam Lee"). (Judgement, consistent with panel-framework "confirm dialog states what is true now".)
- Show the person's current roles in the dialog ("Currently: Cohort admin on Cohort A") so the admin can see what the new role adds to. Already-held role+cohort combinations should be unavailable, with the reason beside the control and `aria-describedby` linking it (panel-framework: disabled action shows its reason).
- Downgrade flow from the idea (organisation admin to cohort role): the dialog should not do two things silently. Either say plainly that the org role stays until deactivated ("Their organisation admin role is unchanged. Deactivate it from the list.") or offer an explicit second step. Avoid a hidden compound action.
- Dialog footer: Cancel left, "Add role" primary right, via `<c-modal-footer>`.

## 3. Per-cohort Change role and Remove in the cohort's Settings tab

What other systems do:
- Linear: role change is an item in the row's overflow menu on the Members page. https://linear.app/docs/members-roles
- GitHub: repo access is changed or removed from the repo's own settings people list; removal is a distinct action that states consequences (loss of read/write; private forks deleted). https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/managing-an-individuals-access-to-an-organization-repository

Recommended (placement rule in `visual.md`: Staff list and Add staff member on the cohort Settings tab):
- Each row: person (`<c-panel-attention-row>` shape, name `text-sm font-semibold`, `size="sm"` chip), role under it in muted text, then `<c-data-table-actions>` with "Change role" and, last, "Remove from cohort". Both small. Names are specific because there may be a table-level "Deactivate" nearby.
- Change role: a small dialog (not inline select that fires on change; a role downgrade of oneself or the last admin is consequential). Radio group of the two roles with the current one preselected; confirm text states before and after: "Current role: Cohort admin on Cohort A. Sam will become Cohort viewer on Cohort A only." Say the change is on this cohort only, since that is the surprising scope.
- Remove from cohort: confirm dialog stating what is true now and what changes ("Sam will lose access to Cohort A. Their other access is unchanged."). `variant="error"` is reserved for irreversible actions; a role removal is reversible by re-adding, so use the standard confirm variant (judgement).
- Guard rails worth specifying: warn when the actor changes or removes their own role; block or warn when removing the last cohort admin of a cohort (judgement; not in the answers, flag for the spec).
- Because a swap is two audit entries (answers), the dialog success message can say "Sam is now a cohort viewer on Cohort A", while History shows deactivated then assigned. Make the two entries adjacent (same timestamp, same actor) so they read as one change.

## 4. Read-only display of inherited (organisation-wide) access

- Pattern across systems (Google "All organizational units" scope; GitHub org-level or team-derived access; Linear workspace-level roles vs team membership): inherited access is shown with its source and is not editable at the lower level. The GitHub page fetched did not document the display, so I rely on the general pattern, not a citation. https://knowledge.workspace.google.com/admin/users/assign-specific-admin-roles
- Recommended: same row shape as editable staff, with the role detail line reading "Organisation admin, whole organisation" (or "via Organisation" using the framework's single relation word), no Change role or Remove buttons, and an explanation in place of the buttons: muted text "Set for the whole organisation. Change it in Staff." with that in a text-action link `<c-button variant="link">` to the Staff section. This answers "why can't I edit?" at the point of need.
- Group the list in two labelled sections or order inherited rows after editable rows, so the controls column is not ragged. Do not use a disabled button as the only signal: disabled controls need the reason beside them and `aria-describedby`. Replacing the buttons with text sidesteps that.
- A person with both an org role and a cohort role appears once with both lines (cohort controls act only on the cohort line).

## 5. As-you-type people picker

### Behaviour
- Minimum 2 characters, 300 ms debounce, cap 8 results (from the idea; matches `recipient_picker.html`). Below 2 characters show a hint in the listbox area: "Type at least 2 characters to search, or enter a full email." Do not search or show an empty list.
- Result row: avatar chip, name (`font-medium`), email under it (`text-sm text-muted`). Show a role/status hint if the person is already staff ("Already staff"), and mark people who cannot be picked (e.g. a learner a cohort-edit-only actor may not promote, per answers) as unavailable with the reason beside, not hidden silently. (Judgement.)
- Cap message: if exactly 8 come back, add a final non-selectable line "Showing the first 8. Keep typing to narrow." so the cap is not mistaken for the full set.
- No match: "No one in your organisation matches 'jo'. To add someone else, type their full email address." Distinct from the loading state.
- Full-email fallback: when the typed text is a syntactically complete email and no listed match has that exact address, offer a final option "Use sam@example.com" (keyboard-reachable like any option) that goes to the lookup step. This keeps enumeration closed (no widening of the search; it only confirms an address the admin already typed) and makes the fallback discoverable instead of relying on submit. Note: do not reveal in the dialog copy whether the address belongs to an account on another organisation beyond what `lookup_user` already does.
- Selection: picking fills the email and moves to the role step. If chips are used (the idea says "person chips"), a chosen person shows as a removable chip with a labelled remove button (`aria-label="Remove Sam Lee"`); for a single-person step, one chip with "Change" is enough. Multi-select is not requested, so do not build it (project rule: do not build unrequested functionality).
- Races: `hx-sync` on the input (as the model does) so only the latest request wins; show a lightweight loading indicator after a short delay, not on every keystroke.
- 422 for validation errors per project HTMX convention.

### Accessibility (WAI-ARIA APG combobox, list autocomplete)
Source: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/
- Input: `role="combobox"`, `aria-autocomplete="list"`, `aria-controls` the listbox id, `aria-expanded` true/false, `aria-activedescendant` pointing at the highlighted option, a real `<label for>`. DOM focus stays in the input; visual focus moves through options.
- Popup: `role="listbox"` with an accessible name; each result `role="option"` with a stable `id`; `aria-selected="true"` only on the option referenced by `aria-activedescendant`.
- Keys: Down Arrow opens and/or moves to the first option, Up Arrow to the last (wrapping); Enter picks the highlighted option; Escape closes the list, and a second Escape clears the input; Alt+Down opens without moving; Home/End/Left/Right return focus to editing in the input; typing continues to filter. Tab leaves the field and does not select.
- Status announcements: the APG page itself gives no live-region guidance. Practitioner guidance is a polite, atomic live region (`role="status"`) announcing "3 results available", "No results" and a loading message, because without it screen reader users get no feedback after typing. Sources: https://a11y-guidelines.orange.com/en/articles/autocomplete-component/ , https://ezud.com/accessible-search-autocomplete-design/ , example https://webkit.googlesource.com/WebKit/+/031545c904ac108f0063861f58a3e4e2a299b0c0/Websites/webkit.org/blog-files/aria1.0/combobox_with_live_region_status.html . Support varies (VoiceOver quirks reported at https://89597-bug-18039-attachments.webkit.org/show_bug.cgi?id=212471), so QA with more than one screen reader.
- HTMX fit: render the live region outside the swapped results fragment (or swap with OOB) so it persists; the `{% partialdef results %}` should carry the `role="option"` rows and the count text. Keep the listbox element and its `id` stable across swaps so `aria-controls` stays valid; update `aria-expanded` when results are non-empty. (Judgement.)
- Plain `<a>` elements are not options: options are not links. Panel-framework's "every anchor is a control" invariant means use `<li role="option">` with a button-like handler or hx-post, not an anchor.
- Colour: highlighted option needs more than colour change (outline or background plus focus ring token `focus-ring`); contrast pairings per `visual.md` (Midnight on Chalk 14.3:1 in default theme).
- Touch: options at least 44 px tall on a phone; the dialog stays inside 375px (panel-framework).
- Panel-framework already states the rule "Entering an email for a person who may already exist searches as you type and offers the matches", so this is the sanctioned pattern, not a new one.

## 6. Adding a staff member with no roles yet

- Notion separates "member" from what they can access (pages/teamspaces), and Linear has member and guest types independent of team membership, so membership without scoped access is a normal state. https://www.notion.com/help/add-members-admins-guests-and-groups , https://linear.app/docs/members-roles
- Recommended: the role step has an explicit first option, "No roles yet (add later)", not a skipped step or an empty selection. Button label changes to "Add staff member" (verb and noun, one line at 375px) rather than "Add role". After adding, the Staff row shows muted "No roles yet" and the row has "Add role" as its first action.
- Make clear in the dialog what no role means: "They will appear in Staff but cannot see any cohort until you add a role." (Voice: say what happens.)
- "Add and add another" is the panel-framework shape for adding records by hand (`submit_buttons`); fits an org admin adding several people one at a time.
- Removing the staff membership (answers: deactivates all roles, one audit entry per role) needs a confirm dialog listing the roles that will end ("Sam will lose: Cohort admin on Cohort A, Cohort viewer on Cohort B"). Label it distinctly from "Deactivate role" ("Remove from staff" or the existing "Deactivate staff member").

## 7. Visibility rules the interface should make legible

From `answers.md`: cohort admin sees only own cohorts' staff unless they hold the organisation staff viewer role; only organisation admins create new staff; cohort admins grant viewer or admin only within their scope.
- Show a one-line scope note above the picker results when the search is narrowed ("Searching staff of your cohorts"), so an empty result is not read as "that person doesn't exist". Do not name hidden people or hint at their existence.
- Role choices in the dialog list only what the actor may grant; do not show greyed-out options that reveal higher roles unless needed (judgement). If greyed, give a reason.
- Cohort-edit users cannot promote a learner to staff: in the picker, learner results are either excluded for them or marked with the reason. Prefer excluding silently only if the empty state's copy covers it; otherwise mark.

## 8. Brand and framework checklist for the spec

- Components: `<c-panel-person-link>`, `<c-panel-attention-row>`, `<c-panel-avatar-chip size="sm">`, `<c-chip>` for roles (not `c-panel-status-badge`, which is for record state), `<c-data-table-actions>`, `<c-modal-footer>`, `<c-panel-empty-state>` for an empty Staff list, `<c-callout level="info">` for scope notes.
- All triggers `size="small"`; no bare-verb pairs; no hand-styled anchors; dialogs end in the modal footer; Settings tab holds Staff list and Add staff member per the Placement table. Run `freedom_ls/panel_framework/tests/invariants/test_templates.py` after template changes.
- Copy per `voice.md` (not re-read in full for this note; check before writing strings).
- Token colours only, no raw colours in panel components.

## Open design choices to hand to the spec (not decided here)
1. Chip versus plain text for roles in the cell.
2. Self-change and last-admin guards.
3. Whether "Use <email>" fallback is an option row or a button under the input.
4. Learner results for cohort-edit actors: exclude or mark.
5. Whether Add role warns about an org role staying in force during a downgrade.

## References
- WAI-ARIA APG combobox, list autocomplete: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/
- Orange accessibility guidelines, autocomplete: https://a11y-guidelines.orange.com/en/articles/autocomplete-component/
- ezud, accessible autocomplete: https://ezud.com/accessible-search-autocomplete-design/
- WebKit live-region status combobox example: https://webkit.googlesource.com/WebKit/+/031545c904ac108f0063861f58a3e4e2a299b0c0/Websites/webkit.org/blog-files/aria1.0/combobox_with_live_region_status.html
- Google Workspace, assign specific admin roles: https://knowledge.workspace.google.com/admin/users/assign-specific-admin-roles
- Linear, members and roles: https://linear.app/docs/members-roles
- Notion, manage members and guests: https://www.notion.com/help/add-members-admins-guests-and-groups
- GitHub, individual access to an organisation repository: https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/managing-an-individuals-access-to-an-organization-repository
- Project: `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, `.claude/skills/brand-guidelines/visual.md`

status: ok · reason: complete; Slack and GitHub inherited-access display not found in sources
