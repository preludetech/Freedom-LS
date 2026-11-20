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
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Decide whether the learner import upload and result pages count as panel-framework pages: `educator_interface/learner_import_upload.html` and `partials/import_error_block.html` still use `<c-callout>` because they extend `standalone_page.html`, outside the panel dispatch, yet they use `c-panel-card` and `c-panel-page-header`; if they count, switch them to `<c-panel-callout>` and drop the `import_error_block.html` exemption in `test_no_fls_panel_template_calls_the_site_callout`
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether the panel framework should offer a built-in 'close the dialog and toast, swap nothing' response: RemoveProfilePictureAction.handle_submit (accounts/panels/personal_details/actions.py) sets HX-Retarget: body and HX-Reswap: none by hand, because an empty 200 swapped into #app-modal-body reopened the dialog; keep it, or file a framework idea
- [x] (user) Check the plan deviations and fix the plan text if wanted: account actions live at personal-details/__panels/<panel>/__actions/<action> (not personal-details/__actions/<action>); test_organisation/import_contracts.toml gained an allowance for base/tests/components/test_header_avatar.py importing accounts.factories; test_organisation/mirroring_exemptions.txt gained a line for accounts/tests/test_allauth_pages.py
- [x] (user) Delete the stray migration 0008_learnerimport_learnerimportrow.py moved to /tmp/claude-1000/-home-sheena-workspace-lms-freedom-ls-worktrees-learner-profile-use-panels-framework-3-account-page/22d6ba45-d894-4bbe-b3fd-e9c4ef9695b3/scratchpad/ (an accidental stash pop restored it from stash@{0}, 'partial batch 9 from crashed implement_plan run' on educator-interface-8-bulk-operations, which is still in the stash list)
- [x] (user) Decide whether framework modal triggers should work with JavaScript off: `cotton/modal-trigger.html` is an `hx-get` button only, so 'Remove picture' on Personal details (and every other dialog trigger) does nothing without JavaScript. The inline name and picture forms now post plainly; this is what remains of code-review finding 3 on PR 263
- [x] (user) Decide what to do about QA bug: layout probe flags /accounts/password/set/ because the allauth page's grey canvas comes from an ancestor, not its own full-width element as on the educator panel pages (no visible misalignment); restructure the page so the probe passes, or accept the flag (TDD: failing test first, then fix)
- [x] (user) Fix the tests the targeted run after the QA fixes left failing: freedom_ls/base/tests/invariants/test_app_templates_use_app_components.py::test_app_templates_use_no_content_widget_or_callout_level[accounts/templates/accounts/partials/profile_picture_form.html] (the template uses c-panel-notice where the invariant expects <c-callout>)

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) In `claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, add "account area" and say "Personal details" is the private page, distinct from the public profile (spec: Documentation and downstream)
- [x] (cmd) In `spec_dd/1. next/learner-public-profile/idea.md` line 8, replace the open question about using the panel framework with a pointer to the roadmap decision (spec: Documentation and downstream)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
