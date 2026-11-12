# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [ ] (user) Review the code and the QA report, and act on any `Decide` items QA filed
- [x] (user) Decide what to do about QA bug: when the 'You can't change your own roles' note shows — resolved: anyone may change their own role of a type they may assign, so the note is gone
- [x] (user) Decide what to do about QA bug: a names-only staff viewer sees people's roles in the Add role dialog's 'Now' list — resolved: they see only the roles on cohorts they can give
- [x] (user) Decide what to do about QA bug: Deactivate role and Change cohorts are offered on role items held only on cohorts the viewer cannot give — resolved: both show only on a role item that includes a cohort the viewer can give, and are a 404 otherwise
- [x] (user) Decide what to do about QA bug: a cohort admin cannot open the cohort's History tab, so cannot see the role changes they made — resolved: cohort admins get History on cohorts they administer; a learner's History and the Audit log stay with organisation and site admins
- [x] (user) Decide what to do about QA bug: a names-only staff viewer is still offered a Role filter on Staff (an empty Role chip and Clear all; hiding the chip leaves Role under Add filter) — resolved: a filter with no choices is left off the toolbar, Add filter and the filter sheet
- [x] (user) Decide how the Staff table fits at 768 and with the quick view open (cards at 768 as the QA plan says, or a narrower table), then fix it so every button stays in view — resolved: cards wherever the table's container is too narrow (768, and 1280 beside the quick view)
- [x] (user) Decide whether a cohort viewer's forged Change role POST on a cohort Settings tab should answer 403 (QA plan) or 404 (current, tab hidden), then align the spec, QA plan and tests — resolved: 404 stays; spec, plan and QA plan say so
- [x] (user) Decide what to do about QA bug: on a phone the cohort tab strip opens scrolled away from the active Settings tab — resolved: the strip scrolls the active tab into view
- [ ] (user) Decide what to do about QA bug: Staff page stays on screen, stale, after you deactivate your own Organisation admin role; the first fix was reverted because it redirected cohort admins off the cohort Settings tab (TDD: failing test first, then fix)
- [ ] (user) Decide what to do about QA bug: the organisation's bare URL (/educator/organisations/<slug>/) renders an empty page (TDD: failing test first, then fix)
- [ ] (user) Decide how Deactivate role should read when the viewer is removing their own role ('They lose…', 'You can give the role again later'), then change the dialog copy (TDD: failing test first, then fix)
- [ ] (user) Decide whether deactivating a site admin's last role removes them from the staff list or the dialog stops saying it 'takes them off this organisation's staff list', then align the dialog and the behaviour (TDD: failing test first, then fix)
- [ ] (user) Decide how a Staff card ties each role to its Deactivate role and Change cohorts buttons when someone holds two roles, then build it and name the role in each button's accessible name (TDD: failing test first, then fix)
- [ ] (user) Decide how a conversation thread sits inside the learner Messages panel (second header and its rule, left edge, the 'Replies are closed' bar against the rounded card), then fix it (TDD: failing test first, then fix)
- [ ] (user) Fix the tests the full run after the QA fixes left failing: freedom_ls/educator_interface/tests/playwright/test_cohort_report_layout.py::test_generating_a_report_by_keyboard_keeps_focus_inside_the_downloads_card (fails under parallel runs, passes alone)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: add glossary rows to `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md` for `StaffMember`, `organisation_staff_viewer`, `organisation_staff_roles_viewer`, `staff_member.added`, visible staff, pickable staff, `target` of a role and may edit own roles, and the "Remove from cohort" exception in the "removed" row (spec: Documentation and downstream, Terminology)
- [x] (cmd) Run `/sdd:document`: in `.claude/skills/brand-guidelines/visual.md` "Placement", note that the cohort Settings tab is the Name, Staff and Status panels, the learner Settings tab the Name and Account panels, and the Staff row puts Add role in the Staff member actions column (spec: Documentation and downstream)
- [x] (cmd) Run `/sdd:document`: add `staff_member.added` to the action table in `freedom_ls/audit_log/README.md` (spec: Documentation and downstream)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
