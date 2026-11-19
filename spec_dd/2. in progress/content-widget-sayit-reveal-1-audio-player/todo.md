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
- [x] (user) Force-push the rebased branch (git push origin HEAD --force-with-lease --force-if-includes): the branch was rebased onto main and the remote still holds the pre-rebase history, so later pushes fail until this runs
- [x] (user) Listen to the four demo recordings in demo_content/functionality_demo_content_widgets/2. media/audio/: bravo.mp3 is 2.8 s and the others about 0.5 s after silence trimming, so either Bravo kept noise or the others lost part of the word; re-run the conversion with a different threshold if one sounds wrong
- [ ] (user) Approve the c-audio card redesign (symbol tile, mono respelling with stressed syllable, round play button, primary border while playing)
- [ ] (cmd) Once the c-audio card design is approved: add tests for the `symbol` tile, the `respelling_parts` filter and the playing-state classes, and re-run the browser tests and `/sdd:do_qa` against the updated QA plan

## 4. Documentation and pull request

- [x] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [x] (cmd) Run `/sdd:document`: add `c-audio` to the widget list in `claude_plugins/fls-dev/resources/markdown_content.md`, and name the `content_engine` URLconf as the place a widget's endpoint lives (spec, Documentation and downstream)
- [x] (cmd) Run `/sdd:document`: add an `audioFile` row (`content_engine`, `cotton/audio.html`) to the component inventory in `claude_plugins/fls-dev/skills/alpine-js/SKILL.md` (spec, Documentation and downstream)
- [x] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [x] (cmd) Fix the PR #256 code-review findings (stale audio events, long-label wrapping, unique respelling ids, always-announced error line, replay without re-fetch, shared c-content-error box, test tidy-ups)

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
