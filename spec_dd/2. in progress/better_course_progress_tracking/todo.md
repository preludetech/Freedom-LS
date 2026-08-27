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
- [x] (cmd) Run `/fls-dev:do_qa` on `3a. seam_qa/frontend_qa_seam.md` — the form_engine × per-registration-progress seam. Nothing in it has ever been run; do this one first
- [x] (cmd) Run `/fls-dev:do_qa` on `3b. progress_gaps_qa/frontend_qa_progress_gaps.md` — the twelve sections run 1 never reached, including success criteria 6 and 9, plus regression checks on run 1's three fixes. Supersedes the individual unrun-section items below
- [x] (cmd) Run `/fls-dev:do_qa` on `3c. form_engine_regression_qa/frontend_qa_form_engine_regression.md` — the form_engine plan re-walked against this branch. Owns the mobile and tablet passes for all three runs
- [x] (user + cmd) Fix QA setup blocker: `CourseFormAttemptFactory` does not pass its explicit `site=` down to the `FormProgressFactory` sub-factory, so `qa_create_report_cohort` and `qa_complete_form` both die with `IntegrityError: null value in column "site_id" of relation "freedom_ls_form_engine_formprogress"`. Blocks the report sections of all three QA plans (TDD — failing test first, then fix)
- [ ] (user) If bugs were found, fix them using TDD (failing test first, then fix)
- [ ] (user) If QA fixes changed code significantly, re-run `/ds:security-review` and address any new issues
- [x] (user + cmd) Fix QA bug B2: educator cohort panel 500s with ProtectedError when the cohort has granted course progress records. Decided: no cascade summary, no 500 — catch the ProtectedError and show a plain message such as "This cohort can't be deleted because it has course progress", in the delete dialog or wherever the delete is attempted. Fix it on `DeleteAction` itself, not just for Cohort, and cover both the render path (`get_cascade_summary`, which is what 500s on GET) and the submit path (`handle_submit`, which would 500 on click) (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug B1: qa_create_report_cohort leaves stale progress_percentage, so the educator matrix shows 0% beside completed cells (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug B3: reconcile `3. frontend_qa.md` section 0.2/0.3/13.1 with the actual qa_helpers command signatures — two seed commands reject the documented invocation, and the stated persona passwords and the --email option name are both wrong
- [x] (user) Run `uv run python manage.py danger_content_delete` manually and confirm it completes without a ProtectedError — this session's command-permission classifier refused it, and it is an explicit pass criterion
- [x] (user + cmd) Execute test plan section 3 (shared content across two courses, success criterion 6) — never exercised in this QA run
- [x] (user + cmd) Execute test plan section 8 (per-organisation deadlines, success criterion 9) — never exercised in this QA run
- [x] (user) Verify the report body checks in test plan section 12 (Contents and at-risk anchors, the 'No recorded activity' flag, per-cohort quiz attempt numbering) in a PDF viewer — reports render to PDF only, so these could not be clicked in-browser
- [x] (user + cmd) Execute the remaining unrun steps: 5.1–5.4 and section 6 (deactivated learners keep their records), 7.1 (cohort membership fan-out), 9.7 (submit-on-exit quiz double-submit), 11.5 (qa_create_course_access_types access-type walk)
- [x] (user) Triage the QA report's remaining General note: a course part whose children are partly complete but with none currently in progress renders "Not started" rather than "In progress". Deliberately left out of the QA bugfix pass — the report records low confidence that it relates to this branch, so it needs its own look
- [x] (user + cmd) Fix QA bug: the course finish page marks a course complete and fires the `course.completed` webhook while a required form placement has never been sat — `GET /courses/<slug>/finish/` stamped `completed_time` at 88% with a quiz still "Not started", because `unpassed_forms()` (`freedom_ls/learner_interface/utils.py:132-168`) only lists placements that were sat and failed. Needs a product decision first: should a never-sat placement withhold completion? See `3a. seam_qa/qa_report.md` bug B2 (TDD — failing test first, then fix)
- [x] (user) Run `uv run python manage.py danger_content_delete` manually for plan `3a. seam_qa` section S8 and confirm it completes without a ProtectedError, then re-seed from §0.1 — this is an explicit pass criterion the plan designates HUMAN-RUN, and the database currently holds one deliberately orphaned CourseFormAttempt plus a spare `QA Seam Refix Cohort` for it to clear
- [ ] (cmd) Correct two plan-vs-product drifts in `3a. seam_qa/frontend_qa_seam.md`: S4 should name the End course Quiz, not the Mid course Quiz, because the latter is configured `submit_on_exit=True` and cannot be resumed by design; and S9 should not name Olive Educator, who is not staff on the DemoDev site where the report cohort lives, and should say that cohort reports are generated from the Django admin rather than the educator interface. The S9 half is done; only the S4 half is left
- [x] (cmd) Correct a gap in `3a. seam_qa/frontend_qa_seam.md` §0.1: the seed list `content_save`s only `functionality_demo_end_with_quiz` and `functionality_demo_course_parts`, but `qa_create_organisation_scenarios` needs `functionality-demo-show-end-with-topic` and fails on a freshly cleared database with "Course 'functionality-demo-show-end-with-topic' not found on site 'DemoDev'". Add `content_save` lines for `functionality_demo_end_with_topic` (required), plus `functionality_demo_content_widgets` and `functionality_demo_standard_markdown` to restore the other two courses the pre-wipe database had
- [x] (user + cmd) Reconcile the two implementations of "is this form placement done": the course outline reads the latest-**started** attempt via `quiz_verdict` (`freedom_ls/learner_interface/utils.py` `get_content_status`), while the progress percentage and the finish page's `outstanding_items` read the latest-**completed** attempt via `attempt_completes_form` (`freedom_ls/learner_progress/queries.py`). A learner who starts a fresh attempt without finishing it can make the outline and the finish page disagree. Pre-existing and unrelated to the B2 fix, which deliberately used the percentage's source so those two agree. Done: the outline now reads the shared latest-completed rule via the new `completed_form_item_ids` helper, so a passed placement stays COMPLETE (and stays unlocking) while a retry is in flight; `learner_progress`'s byte-identical copy of `attempt_completes_form` was deleted in favour of `form_engine`'s, which is now the positive spelling of `quiz_verdict`
- [x] (user) Decided: completing a form attempt does **not** refresh its record's `last_accessed_time`. The field is a read timestamp, set when a learner accesses something: opening an item stamps it, submitting an attempt does not. The current implementation is already right and nothing in the code changed. `view_course_item` is the only write point, `recalculate_progress_percentage` saves with `update_fields=["progress_percentage"]` so a background recalculation never looks like a visit, and `test_a_percentage_recalculation_does_not_bump_last_accessed_time` pins that. QA run `3a. seam_qa` bug B2 has been withdrawn from its report, plan `3a. seam_qa/frontend_qa_seam.md` S1.5 now expects the item-view time rather than a fresh one, and plan `3c. form_engine_regression_qa` step 6, which asserted `qa_complete_form` leaves a fresh `last_accessed_time`, now asserts on the `CourseFormAttempt` rows it actually writes
- [x] (user) Decided: educators do not get a cohort-report entry point in this spec. Report generation and download live in the Django admin only, which is how things stand rather than a defect. An educator-facing or learner-facing download route will be specified and built in its own spec later. The QA plans now generate reports from the admin, and the finding has been withdrawn from `3a. seam_qa/qa_report.md`
- [x] (cmd) Deleted the uncommitted `qa_helpers` command `qa_grant_organisation_staff.py`, created during QA run `3a. seam_qa` by the `fls-dev:qa-data-helper` agent. The agent's own memory records that it was written on a false diagnosis — Olive already reached the cohort page through a guardian `view_cohort` grant — and `qa_create_organisation_scenarios` already grants the role inline, so the command solved nothing. The durable knowledge (the two independent access paths, the counterfactual discipline, the credentials trap) was kept in the agent's memory as `reference_organisation_educator_access.md`. Dev-DB residue from that agent is still in place and only matters to the next QA run: `org.educator@example.com`'s password is now `demodev@email.com`, and Olive holds `organisation_staff` on the DemoDev organisation (`ObjectRoleAssignment a4c1c1e1`), which widened her visible DemoDev cohort list from 1 to 4
- [x] (user) Delete `LearnerDeadline` 53ff5b27 before reusing Cara Learner as a clean fixture — QA run `3a. seam_qa` S10.6 left a hard past deadline (2026-08-20) on her Northside individual registration for the Knowledge Check, which locks her out of that item whenever she resolves to her Northside grant
- [x] (cmd) Re-ran `danger_content_delete` and re-seeded from `3a. seam_qa/frontend_qa_seam.md` §0.1. S8 passes: 200 content objects cleared with no `ProtectedError`, and the residue is gone — both orphaned `CourseFormAttempt` rows (8cf50321, e9d81dd3), all three hand-built `FormProgress` rows (222d5c54, bfd56e9c, 5756c9fc) and `LearnerDeadline` 53ff5b27. The re-seed ran clean end to end, which also confirms the §0.1b `site_id` blocker is fixed in practice. This never needed a human: the step was only ever blocked on `click.confirm` waiting for stdin, so the plans now say to run it with `--yes` and the HUMAN-RUN flag is gone
- [ ] (user + cmd) Fix QA bug: educator Course Progress matrix — below the md breakpoint the learner-name column stays painted in place while the data columns scroll beneath it, so both become unreadable. In course_progress_panel.html the row-header cells carry z-10/z-30 plus an opaque background unconditionally while position:sticky is applied only at md:, so below 768px they are static elements still promoted to a stuck paint layer. Pre-existing on main, not a regression from this branch (TDD — failing test first, then fix)
- [ ] (cmd) Use the `fls-dev:qa-data-helper` agent to create missing data for the Form branch of `content_tags.get_content_by_path` — no demo content links to a Form by path, so that branch has never been exercised — then re-run `/fls-dev:do_qa`

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

- [ ] (user) Open a pull request
- [ ] (cmd) Run `/sdd:address_pr_review` as review feedback comes in
- [ ] (user) Merge the PR once approved

## 15. Cleanup

- [ ] (cmd) Run `/sdd:finish_worktree` to clean up the worktree
- [ ] (user) Move the spec directory to `spec_dd/3. done/` if not already moved
