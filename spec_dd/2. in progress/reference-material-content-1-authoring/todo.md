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
- [ ] (user) Review the code and the QA report
- [x] (user) Force-push the branch: it was rebased onto main and the auto-mode classifier blocked the push. Run `! git push origin reference-material-content-1-authoring --force-with-lease --force-if-includes`; until then origin holds the pre-rebase history
- [x] (user) Decide whether a `reference:` entry naming a path in `.fls-content.yaml`'s `ignore:` list should get its own validator error ("content_save skips this file: it is in the .fls-content.yaml ignore list"), as a `children:` entry does since the content-save-safety spec landed. Today it fails only at load time as "was not loaded". If yes, add the check to `validate_reference_lists` and its offline copy.

## 4. Documentation and pull request

- [x] (user) Force-push the branch again: `/sdd:document` rebased it onto main (which gained the content-save-safety spec) and the auto-mode classifier blocked the push. Run `! git push origin reference-material-content-1-authoring --force-with-lease --force-if-includes`, then `/sdd:make_pr_quickly`
- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [x] (cmd) Fix the three important PR review findings: a `reference:` part outside the loaded source path and one under a `_`/`.` folder are refused before any write; moving a part to `reference:` recalculates the course's stored progress percentages
- [ ] (user) Decide on the remaining PR review nits: the overlap error says "children:" for an auto-discovered child (`validate.py` `validate_reference_lists`), and moving a part to `reference:` leaves topic-level deadline overrides/extensions for that course in place (`content_save.py` `remove_part_placement`)
- [ ] (user) Decide whether `children:` should resolve across `content_save` sources: today a child in another source fails at load time with "names a child … that was not loaded" (pre-existing)
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
- [x] (user) Correct `claude_plugins/fls-dev/skills/admin-interface/SKILL.md`: it says inlines use `SiteAwareTabularInline`, which does not exist in `freedom_ls/site_aware_models/admin.py` (existing inlines use unfold `TabularInline`). Either add the class or fix the skill line.
