# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `claude_plugins/sdd/commands/README.md` for the full workflow description.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/sdd:improve_idea` to research and refine the idea
- [ ] (user) Review the refined idea and edit as needed

## 2. Spec

- [x] (cmd) Run `/sdd:spec_from_idea` to generate the spec
- [ ] (user) Review the spec carefully and edit where needed
- [x] (cmd) Run `/sdd:spec_review` to sanity-check the spec
- [ ] (user) Address any issues raised by the review

## 3. Threat model

- [ ] (cmd) Run `/ds:threat-model` against the spec
- [ ] (user) Update the spec to close any security gaps surfaced

## 4. Plan

- [x] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 5. Plan security review

- [ ] (cmd) Run `/fls-dev:plan_security_review` to check the plan for insecure design choices before implementation
- [ ] (user) Address any concerns raised in the plan

## 6. Plan structure review

- [ ] (cmd) Run `/fls-dev:plan_structure_review` to check for new cross-app dependencies
- [ ] (user) Address any structure concerns raised in the plan

## 7. Implementation

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

## 8. Code security review

- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

- [x] (cmd) Run `/fls-dev:do_qa` to execute the QA plan (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues
- [x] (user + cmd) Fix QA bug: organisation logo replacement does not overwrite the stable organisations/{pk}{ext} key, leaving orphaned files (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: env_example claims freedom_ls_deployment.E001 catches a media alias that fell back to local disk, but it only catches collisions with the default bucket (TDD — failing test first, then fix)

## 10. Product documentation

- [x] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Upgrade notes

- [x] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes

## 12. Template repo

- [ ] (cmd) Run `/fls-dev:update_template_repo` to update the template repo for new projects
- [ ] (user) Review and commit the template repo changes (if any)

## 13. Author plugin sync

- [ ] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 14. Pull request

- [x] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [x] (user + cmd) Fix review finding: E001 misses a media alias that took the shared AWS_STORAGE_BUCKET_NAME while `default` named a bucket of its own — added freedom_ls_deployment.E003 (TDD)
- [x] (user + cmd) Fix review finding: an access key and its secret resolved independently, pairing a per-purpose key id with the shared secret — they now resolve together and a half-set pair raises (TDD)
- [x] (user + cmd) Fix review finding: `build_storages()` hardcoded the three alias names a setting owns, so renaming one crashed at model import — the settings now key both the dict and the builder (TDD)
- [x] (user + cmd) Fix review finding: E001's undeclared-alias branch is unreachable for a bound FileField — added `storage_for_alias()` so the import-time failure names the alias and its setting, and corrected the check's docstring (TDD)
- [x] (user + cmd) Fix review finding: replacing a logo at a different extension orphaned the old object in the public bucket — `Organisation.save()` deletes the superseded key (TDD)
- [x] (user + cmd) Fix review finding: `OverwritingFileSystemStorage.get_available_name` deleted before writing — replaced with Django's own `allow_overwrite` (TDD)
- [x] (user + cmd) Fix review finding: nothing caught a private alias resolving with querystring auth off — added freedom_ls_deployment.E004 (TDD)
- [ ] (user) Merge the PR once approved

## 15. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
