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
- [ ] (user) Decide the seek bar's played-part fill: it uses `accent-primary` only, and the `--played` style it binds is read by nothing. Either add the track gradient (WebKit `::-webkit-slider-runnable-track`, Firefox `::-moz-range-progress`) in `freedom_ls/content_engine/templates/cotton/audio-clip.html` for browsers that don't fill the track, or drop the unused `playedStyle` binding
- [ ] (user) Listen to `demo_content/functionality_demo_content_widgets/2. media/audio/gettysburg.mp3` and confirm the transcript in `2. media/content.md` matches the words spoken; it was copied from the Wikisource text (Everett copy), not checked against the audio
- [x] (user) Force-push the rebased branch, which was refused here: run `! git push origin content-widget-longer-audio --force-with-lease --force-if-includes`
- [ ] (user) Repeat Test 3 steps 1–4 (seeking) of `3. frontend_qa.md` in Safari; no Safari was available to the QA run, which passed them in Chromium
- [ ] (user) Decide: should the dev server's `/media/` handler honour Range requests? Without it Chrome can't seek on a clip's first (uncached) load, so the `c-audio-clip` bar goes back to the sound's real position. Production storage honours Range. (QA B1's earlier fix only froze the bar; the widget now follows the sound instead.)

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/resources/markdown_content.md`: add the `c-audio-clip` widget beside `c-audio` (spec: Documentation and downstream)
- [ ] (cmd) In `claude_plugins/fls-dev/skills/alpine-js/SKILL.md`: add an `audioClip` row to the Alpine components table and note the page-level active audio handle shared with `audioFile` (spec: Documentation and downstream)
- [ ] (cmd) In `claude_plugins/fls-dev/skills/icon-usage/` (SKILL.md and resources that list semantic names): add `media_play` and `media_pause` (spec: Documentation and downstream)
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
