# SDD Todo

Checklist for taking this spec from idea to merged PR. Commands tick their own item; you tick
`(user)` items. See `claude_plugins/sdd/commands/README.md`.

## 1. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to research the idea and write the spec
- [ ] (user) Review the spec and edit where needed; after substantial hand edits, run `/sdd:spec_review`
- [x] (user) This branch was cut from `sacaa-compliance-2-shuffle`, not main, and carries 9 of its commits; decide whether to rebase onto main (dropping them) before the spec is written
- [ ] (user) Run `/sdd:roadmap` on main to add a bullet for the new idea `educator-revision-analytics`
- [x] (user) Force-push the rebased branch (the permission system refused it): `git push origin learner-interface-features-3-revision-questions --force-with-lease --force-if-includes`
- [x] (user) The pre-step rebase stopped before its front-end check and upstream-change review because the push was refused; after pushing, let the next SDD step's pre-step rebase run them

## 2. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 3. Implementation and QA

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [x] (cmd) Run `/sdd:do_qa` to execute the QA plan
- [x] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [x] (user) Decide whether the demo bank form `demo_content/functionality_demo_revision_bank/form.md` may stay `strategy: QUIZ` (the plan said `UNSCORED`, but the validator only allows a `locked` option on a shuffled QUIZ form); if UNSCORED matters more, drop the locked "All of the above" option and switch the strategy
- [x] (user) Decide how a learner gets back to the revision start screen and its section list once a session has ended (today every visit to /courses/<course>/revision/ re-shows the finished session's end screen): clear the finished state on the next visit, or add a 'Back to revision' control to the end screen; then fix QA bug B5 test first
- [x] (cmd) Re-run `/sdd:do_qa`: the QA plan `3. frontend_qa.md` was rewritten for the UX revamp (revision inside the course player, outline entry, dashboard, tinted feedback, Revision done card) and has not been run in full
- [x] (user) Review the revamped revision screens in the course player and the rewritten QA plan
- [x] (user) Decide whether `revision.queries.bank_sections`, `weak_sections`, `last_reviewed_at`, `next_ready_at`, `course_has_revision_questions` and the `section` filter stay: no screen calls them since the section list was removed; they were kept for the later revision dashboard spec
- [x] (user) Write the idea for the revision dashboard spec (sections, weak areas); `partials/revision_dashboard.html` is a placeholder with a TODO
- [x] (user) Decide what to do about QA bug: the Revision done count tiles (Knew it, Hard, Forgot) are bordered boxes inside the bordered card, against the brand rule 'no box inside a box'; choose the tiles' look (for example tint only, or plain figures with no box), then fix `partials/revision_end.html` (TDD: failing test first, then fix)
- [x] (cmd) Fix QA bug B1: render the Revision done counts (Knew it, Hard, Forgot) in `partials/revision_end.html` as plain figures, with no border and no fill on each, in three columns separated by space (decided: plain figures; spec, plan and QA plan updated). TDD: failing test first, then fix.

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) Add the `revisionFeedback` Alpine component (focuses the revision feedback when it is swapped in) to the inventory table in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`, from the spec's "Feedback" requirement (focus moves to the feedback after submit)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward
- [ ] (cmd) Add the `revision` semantic icon to any icon inventory the docs keep, when `/sdd:document` runs

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
