## Where instructions went

Slice 11 (`do_qa.md` split). Resource paths are under `claude_plugins/sdd/resources/`. Every moved block keeps its trigger condition in `do_qa.md`, in the step or rule it came from.

| From | To | Kept, moved or merged |
| --- | --- | --- |
| `do_qa.md` Rule 2: Missing data, Blocking data (the three-rung ladder), blank rungs, refused commands, "This command never makes data itself" with the `data_change` record, "Only mark a test PARTIAL" | `do_qa_test_data.md` | Moved. Rule 2's principle (fix data yourself, never file a todo for it) and its project-root line stay. |
| `do_qa.md` Step 7 `### Capturing screenshots` (default filename, basename in the record) | `do_qa_layout_review.md` `## Capturing screenshots` | Moved. The heading stays in `do_qa.md` with the "never pass `filename`" line and the pointer. |
| `do_qa.md` Step 7 `### Layout probe`, with the per-run capture check | `do_qa_layout_review.md` `## Layout probe` | Moved. |
| `do_qa.md` Step 7 `### Before every screenshot: clear dev tooling`, with the probe call and the `layout` record | `do_qa_layout_review.md` | Moved. |
| `do_qa.md` Step 7 `### Visual review` | `do_qa_layout_review.md` `## Visual review` | Moved. |
| `do_qa.md` Step 7 `### Design comparison` (design check, `design` record, three bullets) | `do_qa_design_comparison.md` | Moved. The trigger sentence (a test that names a design screenshot and checklist) stays. |
| `do_qa.md` Step 7 `### Escalation` (the `sdd:sdd-worker` probe) | `do_qa_escalation.md` | Moved. The trigger, the data line and the browser-driving paragraph stay. |
| `do_qa.md` Step 8 and Step 9 "Focus on" lists | `do_qa_viewport_focus.md` | Moved. Skip rule, resize and the record instruction stay. |
| `do_qa.md` Step 12 `### First: group failures into distinct bugs` | `do_qa_fix_loop.md` `## Group failures into distinct bugs` | Moved. Step 12 keeps the heading and the trigger. |
| `do_qa.md` Step 12 report contents (Methodology to General notes, the single `Write` and the footer) | `do_qa_report.md` | Moved. The worker is now passed the file's path; Step 12 keeps the exact `## Design check`, `## Layout probe`, `## Data changes` and `## Bug status` headings. |
| `do_qa.md` Step 13 `### Triage gate`, including Limits and the prompt-injection guard | `do_qa_fix_loop.md` `### Triage gate` | Moved. Step 13 keeps its intro and the trigger (at least one `bug` record). |
| `do_qa.md` Step 13 `### Green lane — spawn the fixer` | `do_qa_fix_loop.md` | Moved. |
| `do_qa.md` Step 13 `### Re-verify after a successful fix` | `do_qa_fix_loop.md` | Moved. |
| `do_qa.md` Step 13 `### Loop guard + revert` | `do_qa_fix_loop.md` | Moved. |
| `do_qa.md` Step 13 `### Update the report` | `do_qa_fix_loop.md` | Moved. |
| `do_qa.md` Step 13 `### Checkpoint after the last fix` | `do_qa_fix_loop.md` | Moved. |
| `do_qa.md` Step 15 `### What may be added — this list is closed` (six categories) | `do_qa_todo_additions.md` | Moved. Step 15 keeps the trigger and "add nothing else". |
| `do_qa.md` Step 15 `### What must never be added` | `do_qa_todo_additions.md` | Moved. |
| `frontend_check.md` pointers to Step 13 (briefing, limit) and "Re-verify after a successful fix" | `do_qa_fix_loop.md` | Pointer updated to the file the text now lives in. |
| `design_check.md` pointers to Rule 2 and Step 7 | `do_qa_test_data.md`, `do_qa_layout_review.md` | Pointer updated. |
| `qa_fix.md` pointers to "Loop guard + revert" and the Step 7 subsections | `do_qa_fix_loop.md`, `do_qa_layout_review.md` | Pointer updated. |
| `do_qa.md` intro "(the `claude-code-authoring` skill explains why)" | none | Cut: names no action. |
| `do_qa.md` Inputs "This command file names no project-specific command of its own." and "Every substituted command goes through the ordinary Bash permission check." | none | Cut: describe the file, not an action. |
| `do_qa.md` Rule 1 "Another Playwright server may be visible in the session" | the shortened Rule 1 sentence | Merged: the same reason, in half the words. |
| `do_qa.md` Rule 3b hook description ("which matches on `Bash`, `Write`, and `Edit`") | the shortened Rule 3b sentence | Merged. The prohibition and the prose-only instruction stay. |
| `do_qa.md` Rule 4 "That replay is the biggest token sink this command exists to avoid." | none | Cut: rationale. |
| `do_qa.md` Rule 5 "After a QA run the user often changes the design, and ..." | the shortened Rule 5 sentence | Merged. The winning order stays. |
| `do_qa.md` Step 1 "A stale server left by a crashed earlier run is harmless; it just occupies a port Step 3 will skip." | none | Cut: Step 3 already selects an unused port. |
| `do_qa.md` Step 2 "Omitting the classification from the report is a failure mode: there is no silent scoping." | "never scope silently" | Merged. |
| `do_qa.md` Step 3 "(a server blocks in the foreground and would occupy the tool for the rest of the run)" | none | Cut: the instruction is "backgrounded". |
| `do_qa.md` Step 10 "The script validates that both it and `<spec-dir>` are inside the project, creates ..., moves each regular file ..." | none | Cut: describes the script, not an action. |
| `do_qa.md` Step 11 "The wrapper locates `compress_screenshots.py` and runs it from the project root, which the script requires." | none | Cut: the wrapper's own job. |
| `do_qa.md` Step 14 "This runs after the fix loop so re-verification can drive the live, reloaded server." | Step 13 intro | Merged: Step 13 already says it runs before the dev-server cleanup. |
| `do_qa.md` Step 16 "The script refuses anything outside `.sdd-work/`, refuses directories and non-regular files" | none | Cut: the script enforces it. |
| `do_qa.md` Step 17 "The bugfixers' own commits are already in; this one carries the QA artifacts ..." | none | Cut: restates the staging list above it. |
| `do_qa.md` `---` separators between the Steps | none | Cut: layout only. |
| Fix-loop file: "This grouping is written down once, here ...", "(The project's pre-commit hooks do not run the test suite ...)", "This is the outer of two layers ...", the footer-contradiction sentence, "This is the only mechanism that works here ..." | shortened sentences in `do_qa_fix_loop.md` | Cut or merged: rationale. The `git revert` instruction and why `git checkout` and `git clean` cannot replace it stay. |
| Layout file: "A timestamp as the on-disk name is fine ...", "... is how a lopsided page gets passed or a sound one failed" | none | Cut: rationale. |
| Layout file: probe description paragraph | shortened paragraph | Merged. The ink rule and the overflow exceptions stay. |
| Each moved file's opening "Read when ..." line | the pointer in `do_qa.md` | Merged: the trigger lives in `do_qa.md`. |
| `pre_step_rebase.md` Step 3: Upstream-change scan, Step 4: Upstream-change review, Step 5: Act on the verdict, with their completion criteria | `claude_plugins/sdd/resources/upstream_change_review.md` (headings kept) | Moved. The trigger, "when Step 1's rebase returned `rebased: yes`", stays in `pre_step_rebase.md` under "After Step 2", with the earlier returns that stop before it. |
| `pre_step_rebase.md` Step 3's `PLUGINS_ROOT` resolution (three-step rule, no `./` prefix) | `pre_step_rebase.md` "The `PLUGINS_ROOT` rule" | Kept in place, since `finish_worktree.md` cites it. The script name in its last sentence moved to the resource, which points at the rule. |
| `finish_worktree.md` "the way `pre_step_rebase.md` Step 3 does" | the same line, now naming "`PLUGINS_ROOT` rule" | Pointer updated. |
| `pre_step_rebase.md` Step 2 "the same way Step 1 does" config-reading sentence | `pre_step_rebase.md` Step 2 | Merged with Step 1's identical config-reading sentence. |
| Tightened wording in the moved Steps 3 to 5 (stale-review rule, exit 3 explanation, retry rule, resume line, closing paragraph), the pause condition and the `PLUGINS_ROOT` rule | same places | Kept, shorter; no instruction dropped. |

Size of the rows slice 11 touched, in approximate tokens (`token_baseline.md` rows before, `measure_prompt_size.py` after): `do_qa.md` 11144 to 5662, `design_check.md` 623 to 639, `frontend_check.md` 1074 to 1093, eight new `do_qa_*.md` files 0 to 5342. Total 12841 to 12736.

Size of the rows slice 12 touched, in approximate tokens: `pre_step_rebase.md` 2005 to 1005, `upstream_change_review.md` 0 to 994, `finish_worktree.md` 4075 to 4077. Total 6080 to 6076.
