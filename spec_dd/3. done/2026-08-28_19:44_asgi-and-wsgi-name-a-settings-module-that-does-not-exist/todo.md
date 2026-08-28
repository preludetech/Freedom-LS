# SDD Todo

Checklist for taking this spec from idea to merged PR. Tick items as they are completed. See `claude_plugins/sdd/commands/README.md` for the full workflow description.

> Most SDD stages were skipped by request: this is a two-line deletion, so the run covered
> implementation, testing and docs only. Skipped sections are marked below and left unticked.

## 1. Idea

- [x] (user) Write the idea file in this directory
- [x] (cmd) Optionally run `/sdd:improve_idea` to research and refine the idea
- [x] (user) Review the refined idea and edit as needed

## 2. Spec

> Skipped: small task — implementation, testing and docs only. The idea file carried the design decision.

- [ ] (cmd) Run `/sdd:spec_from_idea` to generate the spec
- [ ] (user) Review the spec carefully and edit where needed
- [ ] (cmd) Run `/sdd:spec_review` to sanity-check the spec
- [ ] (user) Address any issues raised by the review

## 3. Threat model

> Skipped: small task — implementation, testing and docs only.

- [ ] (cmd) Run `/ds:threat-model` against the spec
- [ ] (user) Update the spec to close any security gaps surfaced

## 4. Plan

> Skipped: small task — implementation, testing and docs only.

- [ ] (cmd) Run `/sdd:plan_from_spec` to generate the implementation plan and QA plan
- [ ] (user) Review both plans and edit where needed

## 5. Plan security review

> Skipped: small task — implementation, testing and docs only.

- [ ] (cmd) Run `/fls-dev:plan_security_review` to check the plan for insecure design choices before implementation
- [ ] (user) Address any concerns raised in the plan

## 6. Plan structure review

> Skipped: small task — implementation, testing and docs only. No cross-app dependencies: the change touches `config/` and `tests/` only.

- [ ] (cmd) Run `/fls-dev:plan_structure_review` to check for new cross-app dependencies
- [ ] (user) Address any structure concerns raised in the plan

## 7. Implementation

- [x] (cmd) Run `/sdd:implement_plan` to execute the implementation plan
- [ ] (user) Spot-check the changes

Done: the `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")` line and the
then-unused `import os` are gone from `config/wsgi.py` and `config/asgi.py`, each replaced by a
comment recording that the omission is deliberate. New `tests/test_entrypoints.py` covers both
entry points: two tests import each module and assert it yields a callable application, and two
spawn a fresh interpreter with `DJANGO_SETTINGS_MODULE` unset and assert the import fails with
Django's own message naming the variable. Those two failed before the fix and pass after it.

## 8. Code security review

> Skipped: small task — implementation, testing and docs only. The change removes a line and adds tests; it introduces no new input handling, no new dependency and no new surface.

- [ ] (cmd) Run `/ds:security-review` on the pending changes
- [ ] (user) Address any issues raised

## 9. QA

> Skipped: small task — implementation, testing and docs only. No user-visible behaviour changed, so there is nothing to exercise in a browser.

- [ ] (cmd) Run `/fls-dev:do_qa` to execute the QA plan (missing test data will be created automatically via the `fls-dev:qa-data-helper` agent)
- [ ] (user) Review the QA report
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues

## 10. Product documentation

- [x] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

Assessed, no change needed. The only WSGI mention in `docs/product/` is the architecture diagram
line in `deployment.md`, which names no module path. Removing dead boilerplate changes no
capability, no configuration surface and no stated limitation, so it fails the relevance gate;
the actionable content is upgrade-notes content and lives in `upgrade_notes.md`.

## 11. Upgrade notes

- [x] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes

## 12. Template repo

- [x] (cmd) Run `/fls-dev:update_template_repo` to update the template repo for new projects
- [ ] (user) Review and commit the template repo changes (if any)

Not applied — no local template repo checkout is configured (`.claude/fls-dev/config.local.md`
does not exist in this worktree). The template repo ships its own `config/wsgi.py` and
`config/asgi.py` with the identical broken default and needs the identical deletion; the
`## Template repo` section of `upgrade_notes.md` records exactly what to change, for whoever next
syncs the template.

## 13. Author plugin sync

> Skipped: not applicable — nothing about course authoring changed.

- [ ] (cmd) Run `/fls-dev:update_claude_plugin_fls_content` to sync the course-author plugin if authoring functionality changed

## 14. Pull request

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 15. Cleanup

- [x] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
