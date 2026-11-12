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

## 4. Documentation and pull request

- [ ] (cmd) Run `/sdd:document` to run the project's documentation hooks
- [ ] (cmd) In `claude_plugins/fls-dev/skills/file-storage/SKILL.md`, add the `profile_pictures` alias row (user-data bucket, prefix `profile_pictures/`, no overwrite, signed, consumer `User.profile_picture`), change "six aliases" to seven, extend the per-user prefix rule to `profile_pictures/`, and correct the `user_uploads` consumer to `QuestionAnswerFile.file` (spec "File-storage skill and deployment docs")
- [ ] (cmd) In `claude_plugins/fls-dev/skills/panel-framework/SKILL.md`, document the `picture_url` attribute of `panel-avatar-chip` and `panel-person-link`: a plain URL the caller resolves and passes bound, empty means initials (spec "Avatars")
- [ ] (cmd) In `docs/deployment-security-checklist.md` and `.env.example`, add `PROFILE_PICTURES` to the purpose lists; say `AWS_S3_PROFILE_PICTURES_BUCKET_NAME` is required, names the private user-data bucket shared with `USER_UPLOADS` and `GENERATED`, and that `check --deploy` E003 reports it when it falls back to `AWS_STORAGE_BUCKET_NAME`; say a reverse proxy must allow a 10 MB request body on the account page (spec "File-storage skill and deployment docs")
- [ ] (cmd) Run `/sdd:make_pr_quickly` to open the pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Confirm the PR is approved; `/sdd:finish_worktree` lands it on main by fast-forward

## 5. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to close out the worktree and land it on main
- [ ] (user) Remove the worktree and delete the branch once main has it
