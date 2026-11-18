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
- [ ] (cmd) Run `/sdd:qa_fix` to decide and fix what QA left open
- [ ] (user) Review the code and the QA report
- [ ] (user) Force-push the rebased branch (git push origin HEAD --force-with-lease --force-if-includes): the branch was rebased onto main and the remote still holds the pre-rebase history, so later pushes fail until this runs
- [ ] (user) Listen to the four demo recordings in demo_content/functionality_demo_content_widgets/2. media/audio/: bravo.mp3 is 2.8 s and the others about 0.5 s after silence trimming, so either Bravo kept noise or the others lost part of the word; re-run the conversion with a different threshold if one sounds wrong
- [ ] (user) Run QA Test 8 in `3. frontend_qa.md` on real devices: Test 2 steps 1–3 on an iPhone in Safari with the silent switch on and off, and on an Android phone in Chrome, then the VoiceOver or NVDA checks. The automated run had no hardware or screen reader; note the results in `qa_report.md`

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: add `c-audio` to the widget list in `claude_plugins/fls-dev/resources/markdown_content.md`, and name the `content_engine` URLconf as the place a widget's endpoint lives (spec, Documentation and downstream)
- [x] (cmd) Run `/sdd:document`: add an `audioFile` row (`content_engine`, `cotton/audio.html`) to the component inventory in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` (spec, Documentation and downstream)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
