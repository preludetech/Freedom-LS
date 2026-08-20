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

- [x] (cmd) Run `/fls-dev:plan_structure_review` to check for new cross-app dependencies
- [ ] (user) Address any structure concerns raised in the plan
- [ ] (user) Resolve structure concern: whether `reports --> base` (base.app_settings import) should be recorded in docs/app_structure.md

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
- [x] (user + cmd) Fix QA bug: quiz with no pass mark 500s the student results page, course player and dashboard (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: free-text questions listed under "Review incorrect answers" with empty answer blocks (TDD — failing test first, then fix)
- [x] (cmd) Use the `fls-dev:qa-data-helper` agent to create missing data for demo content (QA 13 — no demo content is loaded in the dev database), then re-run `/fls-dev:do_qa`
- [x] (cmd) Use the `fls-dev:qa-data-helper` agent to create missing data for a multi-item course whose quiz is not the last item (QA 12.1 progression blocking), then re-run `/fls-dev:do_qa`
- [x] (cmd) Re-run `/fls-dev:do_qa` for QA 0–10.4 once Phase 5 (tasks/views/admin) is implemented — the entire report generation, PDF, permissions and failure-branch suite was unexecutable this run, and QA 7's column-budget sign-off is still outstanding
- [x] (user + cmd) Fix QA bug: landscape summary table is clipped instead of splitting once quiz columns exceed the budget — real cap is 11 quiz columns / 14 total (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: completion bars never fill, so 0% and 100% render identically (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: restricted staff user sees every cohort's reports in the changelist and can open their detail pages (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: student detail sections do not start on a fresh page, bleeding portrait content onto the landscape summary page (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: running page header shows a student's name on the summary table and cohort confusions pages (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: PDF bookmarks/outline does not mirror the contents — one student missing, three duplicated (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: results page announces "Quiz passed!" for a quiz with no pass mark (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: report title page attributes every report to "the system" instead of the requesting user (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: empty-cohort and no-registrations reports render bare headings instead of stating the situation (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: summary table rows are not ordered alphabetically by surname (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: completion column content overflows its table cell (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: radio and checkbox options are visually indistinguishable in the quiz runner (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: per-student "Wrong answers" blocks are repeated with no quiz name, and options are redundantly suffixed "(correct)" (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: `GeneratedReport.__str__` prints the raw cohort UUID on delete confirmation screens (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: orphaned "Summary tables" heading left on an otherwise blank page (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: quiz column abbreviations truncate the quiz number ("Voltage Quiz 01" → "VQ0") (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: large-n confusion percentages omit the denominator (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: empty report directories left on disk after a report is deleted (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: required-question validation is not enforced on form submit (TDD — failing test first, then fix)
- [x] (user) Decide QA 7 sign-off: adjust the landscape column constant to the measured 11-quiz / 14-column budget, or implement table splitting
- [x] (user) Decide whether a failed quiz should count toward course completion percentage (observation 2 in the QA report) — decided: a learner must pass to complete, so a failed quiz does not count
- [x] (user + cmd) Redesign the report to the design in `design/`, and update the QA plan where the design deviates
- [x] (cmd) Split `3. frontend_qa.md` into two independently-runnable plans with separate screenshot/report directories: `3a. report_generation_qa/` and `3b. quiz_marking_qa/`
- [x] (cmd) Re-run `/fls-dev:do_qa` on `3a. report_generation_qa/frontend_qa_report_generation.md` for the redesigned report — QA 2, 3, 4, 5 and 6 all changed, and QA 2.1, 2.9, 2.10, 2.11, 5.3 and 10.7 are new
- [x] (cmd) Re-run `/fls-dev:do_qa` on `3b. quiz_marking_qa/frontend_qa_quiz_marking.md` for the multi-select scoring fix — QA 11–13, now including the mobile and tablet passes that the combined admin-oriented plan skipped
- [x] (user + cmd) Fix QA bug: a learner who opened items but completed none renders an empty detail section instead of the "No activity recorded." line (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: the completion bar's empty track is invisible on banded summary-table rows because it shares the zebra stripe's colour token (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: landscape column budget is 10, not 11 — at 11 quiz columns "Last item completed" overflows into the "When" column, so `REPORTS_MAX_QUIZ_COLUMNS` must drop from 11 to 10 (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: an unanswered optional question is scored wrong but omitted from "Review incorrect answers", so a failed learner is shown no feedback at all (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: a pre-fix checkbox attempt shows "100% — 2 / 2 correct — Quiz passed!" directly above an incorrect-answer listing, with nothing on the page explaining the discrepancy (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: "Your answer" marks correctly-ticked multi-select options with a red error glyph, contradicting the "Correct answer" block two lines below (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: the form runner fires a spurious "Leave site?" prompt when the learner has changed nothing (TDD — failing test first, then fix)
- [x] (user + cmd) Fix QA bug: a never-marked survey tells the learner "marking is in progress" on completion (TDD — failing test first, then fix)
- [ ] (cmd) Call out free-text questions inside a `strategy: QUIZ` form as an authoring anti-pattern in the upgrade notes — they count toward `max_score` but can never be scored correct, capping the achievable score below 100%
- [x] (user + cmd) Fix QA bug: the "Generate cohort report" admin page renders with no admin styling — `admin/reports/generate_form.html` extends `admin/base.html` instead of an unfold layout, so the page loses the sidebar, breadcrumbs and CSS, the Generate button renders as plain unstyled text, and a duplicate `<h1>` is emitted (TDD — failing test first, then fix)
- [ ] (user + cmd) Fix QA bug: the report's per-learner "Incorrect answers" table paints every option the learner ticked as an error, so on a checkbox question the correctly-ticked options are red under "Answers given" and green under "Correct answer" on the same row — `wrong_selected_counts` in `reports/gather.py` never filters on `option.correct`, and `student_detail.html:106` renders them all as `chip-error`; the cohort confusions path already does this correctly via `.exclude(correct=True)`, and the student results page is the reference implementation (TDD — failing test first, then fix)
- [ ] (user + cmd) Fix QA bug: a course item shown as "Locked" in the course index is not enforced server-side — `view_course_item` gates only on hidden-course, `can_access_content` and deadline locks, so a learner who fails a gating quiz can open the locked item by URL and get its full content; the visit also writes `last_accessed_item`, permanently flipping the index entry from "Locked" to "In progress" with a live link (TDD — failing test first, then fix)

## 10. Product documentation

- [ ] (cmd) Run `/fls-dev:update_product_docs` to update docs/product/ for this feature
- [ ] (user) Review the updated documentation

## 11. Upgrade notes

- [ ] (cmd) Run `/fls-dev:update_upgrade_notes` to author the structured upgrade_notes.md for downstream projects
- [ ] (user) Review the upgrade notes — they must cover the required `manage.py recalculate_progress_percentages` backfill (a failed quiz no longer counts toward course completion, so stored `progress_percentage` values are stale), and the new reports settings (`REPORTS_FONT_FACES` and the three font stacks), how a project rebrands the report's typography, and the fact that at-risk rules are a plain list in `freedom_ls/reports/at_risk.py` with no settings hook — a project that needs its own rule forks until `report-upgrades` moves rule selection into the database, and the moved `student_progress` import paths (`is_quiz_answer_correct`/`evaluate_quiz_answers` → `student_progress.scoring`; `submitted_option_ids`/`submitted_text_answer`/`has_submitted_answer` → `student_progress.submissions`; `attempt_completes_form`/`completed_form_ids_by_user` → `student_progress.queries`; `update_course_progress_on_completion` → `student_progress.signals`, where it is now driven by a `post_save` receiver rather than a `save()` override — a downstream `CourseItemProgress` subclass needs its own `@receiver` line)

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
