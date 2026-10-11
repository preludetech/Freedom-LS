# Research: where the pipeline stalls

Scope: every stop-for-a-human in the current SDD commands, and the evidence from real runs. Line
numbers are from the working tree on branch `sdd-improve`.

Headline findings:

1. `/sdd:next` runs exactly one `(cmd)` item per invocation, then ends the turn and tells the user to
   `/clear` and run it again (`claude_plugins/sdd/commands/next.md:93`). Every command boundary is a
   stall, before any `(user)` item is even reached.
2. The todo template has 18 `(user)` items against 16 `(cmd)` items. `/sdd:next` halts at each unticked
   `(user)` item (`next.md:43-46`).
3. In finished specs the owner does not use `/sdd:next` to walk the list. They run commands directly
   (each command ticks its own box) and almost never tick the `(user)` review gates. 516 of ~566
   review-gate items in the 59 specs finished since 2026-08-21 are still unticked.
4. Most of the questions inside commands are already front-loaded. The worst stalls are (a) the
   `(user)` gates, (b) QA, which writes `Decide ...` items after the work is done, and (c) the
   `user + cmd` marker, which `next.md` rejects.

## How /sdd:next dispatches and stops

Locate the todo (`next.md:10-16`): a named path, else the branch name matched to a directory under
`spec_dd/`, else it lists candidates and asks the user (`next.md:14`, a stall only when the branch name
does not match). If `todo.md` is missing it runs `/sdd:start` inline (`next.md:16`).

Pick the item (`next.md:20`): "Walk the checklist top-to-bottom and find the first line starting with
`- [ ]`." The marker in parentheses decides what happens (`next.md:22`: "`(user)` or `(cmd)`. Every item
should have exactly one of these"). Ticked boxes further down the list are ignored; the first unticked
box wins, even if later steps are done.

Stops, in the order they can occur:

| Stop | Rule | Line |
|---|---|---|
| `(user)` item | "Ask the user, in a single short message, whether they have completed it ... If the user says **no** or is unsure: stop." Even a "yes" ends in Step 4 (tick) and, if the next item is a `(cmd)`, carries on to run it. | `next.md:43-46`, `next.md:91` |
| Unrecognised marker | "If the marker is anything other than `(user)` or `(cmd)`, stop ... In particular, a combined `(user + cmd)` marker is not supported: ask the user to split the item into two." | `next.md:70` |
| Pre-step rebase not `ok` | "On any other status, stop without dispatching the `(cmd)` item." `paused` prints "Paused: read `<spec-dir>/upstream_change_review.md` ..." | `next.md:36-37`, `next.md:92` |
| Unresolvable command | prefix not `sdd` / `fls-dev` / `ds`, or file missing: "stop and tell the user" | `next.md:61` |
| Ambiguous spec directory | branch matches no directory: list and ask | `next.md:14` |
| End of every `(cmd)` | After the command's steps: "Ran `<command>` on the main thread. Result: ... Run `/clear` then `/sdd:next` again to continue." There is no loop back to Step 2. | `next.md:66`, `next.md:93` |

The one case that does continue without stopping: a `(user)` item the user confirms, followed by a
`(cmd)` item (`next.md:91`: "proceed straight into the `(cmd)` branch").

A `paused` status exists only in `pre_step_rebase.md`. It is raised when an unticked item names
`upstream_change_review.md` (`pre_step_rebase.md:27-36`) and returned after the rebase writes that
review and adds the item with `add_first:"user|Decide what to change after reading
upstream_change_review.md, ..."` (`pre_step_rebase.md:154-168`). The recorded `direction: changed`
verdict requires an app-boundary, shared-base, skill or finished-spec contradiction
(`pre_step_rebase.md:107-110`), so it is a genuine decision gate, but two of the six sampled specs
below carry the item.

`/sdd:next` is a main-thread command with `Agent` in its tools (`next.md:4`, `next.md:6`). Inlined
commands run under its tool grants, not their own frontmatter (`next.md:98`).

## Stop points per command

Legend. Timing: **front** = asked at depth 0 in a batch while workers run; **late** = asked after work
was done or at a gate; **n/a** = not a human stop (returns a status to the caller). "Default" = what
could replace the stop.

### sdd commands

| Command | Where it can stop for a human | Timing | Resolvable without a human? Default |
|---|---|---|---|
| `next` | `(user)` item `next.md:43-46`; `user + cmd` `next.md:70`; ambiguous dir `next.md:14`; stop after each cmd `next.md:93`; rebase non-ok `next.md:36` | late (gates) | The per-command stop is a design choice, not a need. Loop back to Step 2 after a `(cmd)` and stop only at a genuine gate. Accept `user + cmd` as "run the cmd". |
| `start` | roadmap precursor `AskUserQuestion` `start.md:16-17`; unmet dependency `start.md:22-24`; mechanic `blocked` `start.md:31,37,43` | front (start of run) | Already first. Precursor: cut/precursor work belongs on main so keep. Dependency warning: default "stop" is safe, "start anyway" needs the owner. |
| `protected/setup_todo_list` | existing todo: "Ask the caller whether to overwrite" `setup_todo_list.md:25`; ambiguous dir `:16` | front | Default: leave alone, never overwrite. |
| `protected/update_todo` | missing input / ambiguous tick: "stop and ask the caller" `update_todo.md:9,22,41,53,62` | n/a (caller-facing) | Mechanical; fails fast. |
| `protected/move_spec_to_in_progress` | ambiguous dir `move_spec_to_in_progress.md:22`, dirty tree `:57` -> `blocked` | n/a | Resolved by `start` from the branch name. |
| `protected/start_worktree` | preconditions fail -> `blocked` `start_worktree.md:24` | n/a | Genuine environment problem. |
| `protected/pre_step_rebase` | `paused` `pre_step_rebase.md:32,167`; `failed`/`blocked` from the rebase hook `:50`; scan failure `:93`, review failure `:136` | late (after upstream change) | Pause only when `direction: changed`. `direction: unchanged` (the common case) continues. Could apply the review's "What to change" bullets automatically for artifacts not yet implemented. |
| `protected/run_test_tier` | no human stop; failure handling is in its own tier text | n/a | n/a |
| `protected/update_roadmap` | ambiguous -> `blocked` `update_roadmap.md:24,40` | n/a | Mechanical. |
| `improve_idea` | blocked workers: ask only if idea/code/other topic cannot answer `improve_idea.md:16,35`; owner-only questions `improve_idea.md:37`; late questions `improve_idea.md:43` ("Anything new that surfaces here gets asked now, in one batch") | front (Step 2) plus one late batch (Step 3) | Already front-loaded. Late batch could instead record defaults in the idea's open questions. |
| `spec_from_idea` | questions while research runs `spec_from_idea.md:41-46`; blocked worker `:22` | front | Already front-loaded and already carries the "take the default, list under Open questions" rule (`:46`). No design-screenshot questions (`:72`). |
| `spec_review` | "Clearly describe the contradiction, ask for input" `spec_review.md:23`; problems "ask for input if the solution is needed" `:43`; unresolved questions become `add:"Spec|user|Decide how to handle ..."` `:85` | **late** (after the spec exists, one contradiction at a time) | Mostly resolvable: the idea, vocabulary and project resources settle contradictions. Default: pick the reading that matches the idea, record under Open questions. Ask the owner only for contradictions inside the idea itself. |
| `plan_from_spec` | contradictions the code cannot resolve, batched, "carry on with Step 2 while you wait" `plan_from_spec.md:50`; blocked worker `:33`; design-drawn extras never asked `:48` | front (Step 1) | Already front-loaded. Default: take the code's answer, fix the spec. `allowed-tools` includes `AskUserQuestion` (`:3`). |
| `implement_plan` | plan review "raise them with the user before starting" `implement_plan.md:31`; batch `blocked` -> `AskUserQuestion` `:66`; design miss after two fix batches -> `blocked` `:81`; "When to Stop and Ask ... Don't force through blockers" `:96-104`; main-branch consent `:108` | late (mid-run) | Step 1 plan sanity check duplicates `plan_from_spec` Step 6 review; skip human unless a step is truly missing. Blocked batch: supply from spec/plan first (recipe rule). Design miss after 2 fixes: record and continue to QA rather than end the run. |
| `commit_quickly` | `mine` or `all` `AskUserQuestion` `commit_quickly.md:79-80`; main branch `:54`; unrelated pre-existing breakage `:122`; real secret `:121` | late | `mine` or `all`: default to `mine` (files edited this conversation). The rest are genuine. |
| `make_pr_quickly` | none ("ask the user anything" is forbidden, `make_pr_quickly.md:18`) | n/a | Already fully automatic. |
| `address_pr_review` | no PR found `address_pr_review.md:16`; "explain why and ask the user for confirmation before skipping" `:47` | late | Default: address or defer-with-reason in the summary (`:68` already lists skipped issues). |
| `finish_worktree` | main worktree dirty `finish_worktree.md:17`; front-end QA re-run confirmation `:66-71`; squash-merged PR conflicts, human fix `:37-39`; PR `CHANGES_REQUESTED` `:134`; exit 3/6/8 and persistent exit 7 `:154-158` | late | `:71`: default "do not re-run QA" unless the rebase touched files the QA plan covers; no question. Others are genuine. |
| `register_design` | no directory matches branch / user names none `register_design.md:38-42`; `/design-login` authorisation `:79,114` | front | Genuine (authorisation is a human act). |
| `roadmap` | one `AskUserQuestion` apply/stop `roadmap.md:104`; cut: batch owner questions `:188`, accept/adjust/stop `:228`, confirm superseded drafts `:221,255` | front plus late confirm | Confirms are the owner's roadmap decisions; out of scope for the idea's pipeline. |
| `init` | tells user to fill in paths `init.md:190` | n/a | One-off setup. |

### fls-dev commands

| Command | Where it can stop for a human | Timing | Resolvable? Default |
|---|---|---|---|
| `plan_security_review` | missing spec/plan "stop and ask" `plan_security_review.md:45`; judgement call -> `> **Security concern:**` callout "and ask the user for input" `:35,107`; summary "whether the user must resolve flagged concerns first" `:112` | late (after scan) | Owner says it is not wanted (idea line 13). Merge the scan into `plan_from_spec` review dimensions; write findings into the plan as edits, concerns as plan notes, no stop. |
| `plan_structure_review` | `docs/app_structure.md` missing `plan_structure_review.md:43`; missing spec/plan `:47`; new-edge judgement call -> callout + `add:"Plan structure review|user|Resolve structure concern: ..."` `:89,122` | late | Default: when the edge is a runtime edge not in the diagram, choose "Restructure" if a shared app already exists, else "Accept and document" and add the line to the plan. Note the callout text already offers both options (`:91-93`). |
| `do_qa` | which test plan when several `do_qa.md:16-18`; Playwright MCP unavailable `:44-46`; red-lane bugs filed as `user` items; `add:` categories (closed list) `:617-631`: UNRESOLVED bug as `user + cmd` `:622`, smoke-gate failure `:627`, "Decide ..." `:629`, full-run failure `:631`; screenshot path failure "stop and report" `:286`; revert path `:541-559` | late (everything after QA ran) | Green lane already auto-fixes (`:476-487`). Red-lane "Decide" items are the genuine product calls. Smoke-gate failure and full-run failure could instead re-enter a fixer. The `user + cmd` marker is wrong (rejected by `next.md:70`); use `cmd`. |
| `update_product_docs` | ambiguous feature dir `AskUserQuestion` `update_product_docs.md:64`; blocked worker `:53` | front | Resolve from the branch name (as `next.md` Step 1 does). |
| `update_upgrade_notes` | ambiguous dir `AskUserQuestion` `update_upgrade_notes.md:66` | front | Same: branch name. |
| `update_claude_plugin_fls_content` | blocked worker `AskUserQuestion` `update_claude_plugin_fls_content.md:41` | front | Fast no-op when no authoring file changed (`:22`); no stop in that case. |
| `init` | tells user to review dev credentials `init.md:265` | n/a | One-off setup. |
| `protected/design_check`, `protected/frontend_check` | `failed` returns only (`design_check.md:32`) | n/a | Not human stops. |
| `concrete/update_fls` | operator confirms the preview before the pointer moves `update_fls.md:33`; dirty migration state `:53` | late | Outside the SDD feature pipeline (downstream operator). |

### ds commands

| Command | Where it can stop | Timing | Resolvable? |
|---|---|---|---|
| `rebase_main` | "runs to completion without asking for confirmation" `rebase_main.md:7`; `blocked` on real secret `:50-54`, merge commit in range `:79`, checked-out worktree `:89`, incompatible both-sides change `:130` | n/a (returns status) | Genuine conflicts only. |
| `app_map` | script failure `app_map.md:29`; reminder only `:39-45` | n/a | No question. Output is advisory. |
| `threat-model` | none; 6-line prompt `threat-model.md:1-8` | n/a | The stall is the surrounding `(user)` item "Update the spec to close any security gaps surfaced" (`setup_todo_list.md:77`). |
| `security-review` | none; 7-line prompt `security-review.md:1-9` | n/a | The stall is the `(user)` item "Address any issues raised" (`setup_todo_list.md:102`). |

## The (user) items in the todo template

The template (`claude_plugins/sdd/commands/protected/setup_todo_list.md:56-136`) has 18 `(user)`
items and 16 `(cmd)` items. `/sdd:next` stops at every unticked `(user)` item (`next.md:43-46`), so
each one is a stall even when the human has nothing to say.

| # | Item (line) | Class | Reason |
|---|---|---|---|
| 1 | Write the idea file (`:63`) | Gate (pre-ticked) | Pre-ticked when `idea.md` exists (`setup_todo_list.md:34`). Not a stall. |
| 2 | Review the refined idea and edit as needed (`:65`) | Gate, often a rubber stamp | The only point where the owner shapes scope before the spec is written. Keep as the one front gate. |
| 3 | Review the spec carefully and edit where needed (`:70`) | Gate, rubber-stamped in practice | Overlaps #2 and #4; the spec derives from the idea. |
| 4 | Address any issues raised by the review (`:72`) | Mechanical | `spec_review` already edits the spec to fix its findings (`spec_review.md:10`); the item is only needed for the questions it adds (`spec_review.md:85`). Make it conditional. |
| 5 | Update the spec to close any security gaps surfaced (`:77`) | Mechanical / unwanted | Owner says threat-model is not used (idea line 13). Remove. |
| 6 | Review both plans and edit where needed (`:82`) | Gate, rubber-stamped | Plan is reviewed by 8 review workers already (`plan_from_spec.md:127-136`). Candidate to drop or merge into one "approve plan" gate. |
| 7 | Address any concerns raised in the plan (`:87`) | Mechanical / unwanted | `plan_security_review` item. Remove with it. |
| 8 | Address any structure concerns raised in the plan (`:92`) | Mechanical | Only exists to resolve callouts; the command already adds a specific `user` item per callout (`plan_structure_review.md:122`). |
| 9 | Spot-check the changes (`:97`) | Rubber stamp | Each batch is tested and committed (`implement_plan.md:49-50`) and the full tier runs at the end (`:91`). Nothing for the human to type. |
| 10 | Address any issues raised (code security review) (`:102`) | Mechanical / unwanted | Owner says security-review is unused. Remove. |
| 11 | Review the QA report (`:107`) | Gate in principle, rubber stamp in practice | `do_qa` already files every actionable thing as its own item (`do_qa.md:617-631`). |
| 12 | If bugs were found, fix them using TDD (`:108`) | Mechanical | `do_qa` Step 13 auto-fixes green-lane bugs with `fls-dev:qa-bugfixer` (`do_qa.md:476-537`); only red-lane bugs need a human, and those are filed separately. |
| 13 | If QA fixes changed code significantly, re-run `/ds:security-review` (`:109`) | Mechanical / unwanted | Remove with security-review. |
| 14 | Review the updated documentation (`:114`) | Gate, rubber stamp | Docs are generated from spec, plan and code. |
| 15 | Review the upgrade notes (`:119`) | Gate, rubber stamp | Notes are fact-checked by the command (`update_upgrade_notes.md:118-124`) and re-verified after review (`setup_todo_list.md:129`). |
| 16 | Open a pull request (`:127`) | Mechanical | `/sdd:make_pr_quickly` exists and forbids asking anything (`make_pr_quickly.md:18`). |
| 17 | Confirm the PR is approved (`:130`) | Genuine gate | Approval of the PR on GitHub is the human decision; `finish_worktree` also guards `CHANGES_REQUESTED` (`finish_worktree.md:134`). |
| 18 | Remove the worktree and delete the branch once main has it (`:136`) | Mechanical in principle | The command cannot remove the worktree it is running in (`finish_worktree.md:175-176`). A human or a different-cwd step has to do it. |

Tally: 2 genuine gates (#2, #17), 4 conditional gates that only matter when a review raised something
(#4, #8, #11, #15), 5 reviews that are rubber stamps in the data (#3, #6, #9, #14, plus #11),
4 tied to commands the owner wants removed (#5, #7, #10, #13), 2 mechanical (#12, #16), and 1 not
removable by a command (#18). Counts overlap; the point is that at most 2 of 18 need a person every
time.

Items added by commands at run time, which also stop `/sdd:next`:

- `add_first:"user|Decide what to change after reading upstream_change_review.md ..."`
  (`pre_step_rebase.md:159-160`).
- `add:"Spec|user|Decide how to handle <question>"` (`spec_review.md:85`).
- `add:"QA|user|No QA needed — feature has no frontend changes"` (`plan_from_spec.md:153`). This is an
  observation with no action; it jams `/sdd:next` and is left unticked in `make-sdd-more-efficient`.
- `add:"Plan structure review|user|Resolve structure concern: ..."` (`plan_structure_review.md:122`).
- `do_qa` Step 15's closed list: `user + cmd` bug items, smoke-gate failure, `Decide ...`, full-run
  failure (`do_qa.md:617-631`).

## Evidence from finished specs

Method: read 6 recent finished `todo.md` files in full, then counted across all 59 specs finished
2026-08-21 onward (`spec_dd/3. done/2026-{08,09,10}*`). The three in-progress specs checked
(`educator-interface-10-reporting-dashboards`, `user-communication-4-direct-messaging`,
`content_snapshots`) still have the full unticked template; `content_snapshots` is on an old template
(bare `/improve_idea` names, `todo.md:8`, `:68`) and should be ignored for patterns.

### Per-spec sample

All items not named below are unticked. "Gate" = `(user)` review items.

| Spec | Ticked `(cmd)` | Ticked `(user)` | Unticked of interest | Added items |
|---|---|---|---|---|
| `2026-10-11_06:57_educator-interface-6-cohort-administration` | spec_from_idea, spec_review, plan_from_spec, implement_plan, do_qa, update_product_docs, update_upgrade_notes, finish_worktree | write idea; Decide (upstream review); Decide (nameless learner link); `user + cmd` fix | improve_idea cmd (`todo.md:9`), threat-model (`:21`), plan_security_review (`:31`), plan_structure_review (`:36`), security-review (`:46`), plugin sync (`:70`), PR items (`:74-77`); every review gate | `:8` upstream decision, `:55` Decide, `:56` `user + cmd` |
| `2026-10-10_09:58_corporate-job-course-recommendations-1-hr-attributes` | improve_idea, spec_from_idea, spec_review, plan_from_spec, implement_plan, do_qa, product_docs, upgrade_notes, finish_worktree | write idea only | same five threat/security/structure items unticked (`todo.md:20-46`); all gates unticked | none |
| `2026-10-10_08:57_user-communication-3-messaging-policy` | same 9 cmds | write idea; Decide (mobile clipping); `user + cmd` fix | five security items unticked; "Write docs/product/messaging.md" deferred item unticked (`:61`) | `:54` `user + cmd`, `:55` Decide, `:61` deferred doc |
| `2026-10-09_09:03_make-sdd-more-efficient` | plan_from_spec, implement_plan, product_docs, upgrade_notes, finish_worktree | write idea only | `spec_from_idea` and `improve_idea` unticked although a spec evidently existed; do_qa unticked; "No QA needed" unticked (`:54`) | `:54` "No QA needed" |
| `2026-10-08_09:35_course-applications-admin` | improve_idea, spec_from_idea, spec_review, plan_from_spec, implement_plan, do_qa, product_docs, upgrade_notes, finish_worktree | write idea; Decide; `user + cmd`; **Open a PR**; **Confirm PR approved** | five security items unticked | `:54` Decide, `:55` `user + cmd` |
| `2026-10-08_06:54_educator-interface-looks-good` | improve_idea, plan_from_spec, implement_plan, do_qa, product_docs, upgrade_notes, re-run upgrade_notes, finish_worktree | write idea; 3 Decide; 22 `user + cmd`; "fix bugs using TDD" (`:53`) | `spec_from_idea` and `spec_review` unticked (`:14-16`); five security items unticked | 21 `user + cmd` items (`:55-78`) incl. 7 titled "Human design review" |
| `2026-09-08_17:31_better-form-start-page` | n/a (read via grep) | Decide B3 (`:55`) | two later "Decide" items unticked at completion (`:56`, `:58`), both contradicting earlier ticked items | `:55-58` |
| `2026-09-12_17:33_referral-links` | n/a (read via grep) | 3 Decide ticked (`:55`, `:57`, `:64`) | five security items unticked | 9 `user + cmd` |

### Counts (59 specs finished 2026-08-21 or later)

- The five security-flavoured items (`threat-model` cmd and its `user` follow-up, `plan_security_review`,
  `plan_structure_review`, `security-review`) appear as unticked in 57 of 59 of those specs' files
  (Grep matched `- [ ]` lines containing those names in 103 done files, 417 total). Ticked matches
  (148 occurrences) sit in 44 files; since 2026-08-22 the only ticked matches are 1 line each in
  `2026-08-24_20:56_extract_forms_into_seperate_app` and `2026-09-06_11:53_error-pages`. Confirms the
  idea's claim (`idea.md:13`): these commands are not run.
- Eleven named review gates (refined idea, spec, spec issues, plans, spot-check, QA report, docs,
  upgrade notes, open PR, confirm PR, remove worktree) across those 59 specs: 50 ticked, 516 unticked
  (about 9% ticked). The ticked ones are mostly 1 per spec ("Open a pull request" or "Confirm the PR is
  approved", i.e. a PR actually happened). `Review the spec carefully` is not ticked in the 6 full
  reads at all.
- `user + cmd` marker: 168 occurrences in 35 of 59 specs. Every one is written by `do_qa` Step 15
  (`do_qa.md:622`) and every one is rejected by `next.md:70`. They get ticked by hand, in a batch.
- `Decide ...` `(user)` items: about 45 across those specs; nearly all ticked, so the owner does act
  on genuine product questions. A handful stay unticked at completion (e.g. `2026-08-21_20:12_basic_reports`
  `todo.md:106`, `2026-09-08_17:31_better-form-start-page` `:56,:58`, `2026-08-21_09:09_organisations` `:56`).
- `update_claude_plugin_fls_content` item: unticked in all six full reads. When nothing authoring
  related changed the command is a no-op that ticks its own box (`update_claude_plugin_fls_content.md:22`),
  so the box simply was never run.
- `(cmd)` items run in practice: spec_from_idea, spec_review, plan_from_spec, implement_plan, do_qa,
  update_product_docs, update_upgrade_notes, finish_worktree. Never run: threat-model,
  plan_security_review, plan_structure_review, security-review, plugin sync, address_pr_review (always
  unticked in the six full reads).

### Patterns

1. The owner bypasses `/sdd:next`'s gate walk. Commands tick their own boxes, so unticked `(user)`
   review boxes above ticked `(cmd)` boxes are normal. If `/sdd:next` were used, it would stop at "Review
   the refined idea" first (`next.md:20`), which no sampled spec ever ticked.
2. Routinely skipped steps: threat-model, plan_security_review, plan_structure_review, security-review,
   plugin sync, address_pr_review (ticked only where a PR review happened).
3. Routinely rubber-stamped or ignored gates: every "Review ..." item and "Spot-check".
4. Gates that do get human attention: product `Decide ...` items written by `do_qa`, the upstream-change
   decision, "Open a pull request", "Confirm the PR is approved".
5. QA is where most late questions appear (`do_qa.md:617-631`). 21 items in one spec shows a human
   design-review loop feeding `user + cmd` items back into the todo.

## Avoidable vs necessary stops

### Avoidable

1. **Stop after every `(cmd)`** (`next.md:93`). Loop back to Step 2 after a successful command and
   continue until a genuine gate. Context: the "`/clear` then `/sdd:next`" advice is about context
   size; a loop would need a context-budget rule or a handoff via `todo.md` (already the single source
   of truth).
2. **Rubber-stamp `(user)` review items** (#3, #4, #6, #9, #11, #14, #15 above). Remove them, or tick them
   automatically when the preceding command reports no open questions, and make the one human gate per
   phase explicit (idea, PR approval).
3. **Threat-model, plan_security_review, security-review and their four `(user)` follow-ups**
   (`setup_todo_list.md:74-77, 84-87, 99-102, 109`). Never run; remove the commands, template items and
   the closing references (`plan_security_review.md:8-12` cross-references). The idea authorises this
   (`idea.md:13`).
4. **`plan_structure_review`'s separate stop.** Fold into `plan_from_spec` Step 6 as a review worker
   (`plan_from_spec.md:127`). Judgement calls: default per `plan_structure_review.md:91-93`
   (Restructure if a shared app exists, else Accept and document), written into the plan; no `user` item.
5. **`spec_review`'s one-at-a-time asking** (`spec_review.md:23,43`). Ask the owner only for
   contradictions inside the idea itself; resolve all others from the idea, vocabulary and resources and
   list the decisions taken under "Open questions". Today it asks late, after the spec is drafted, which
   is the opposite of the idea's point 1.
6. **`implement_plan` Step 1 raising plan issues with the user** (`implement_plan.md:31`). The plan was
   already reviewed by workers; default to proceeding and noting the issue, stop only when no
   reasonable reading exists.
7. **`implement_plan` design miss ending the run** (`implement_plan.md:81`). Record the miss for QA
   instead of ending the run with `blocked`.
8. **`finish_worktree` QA re-run confirmation** (`finish_worktree.md:66-71`). Default: do not ask, run
   the full tier (`:73-78`) and let the existing full-run guard stop on failure.
9. **`commit_quickly` mine-or-all** (`commit_quickly.md:79-80`). Default `mine`.
10. **Ambiguous directory questions** in `update_product_docs.md:64`, `update_upgrade_notes.md:66`,
    `setup_todo_list.md:16`, `plan_security_review.md:45`, `plan_structure_review.md:47`: resolve from the
    branch name, the same logic `next.md:10-14` uses.
11. **"Open a pull request"**: make it `(cmd)` `/sdd:make_pr_quickly`.
12. **`do_qa` writing observation items** and `"No QA needed"` (`plan_from_spec.md:153`): the latter is
    not an action. Drop it (the QA item can simply stay out of the list).
13. **`user + cmd` marker** (`do_qa.md:622`). Either `next.md` accepts it or `do_qa` writes `cmd`. As is,
    168 items in 35 specs fail `/sdd:next` by construction.
14. **`do_qa` smoke-gate and full-run failure as `user` items** (`do_qa.md:627,631`). Re-enter a fix
    batch, as the green lane already does (`do_qa.md:476-537`).
15. **`address_pr_review` skip confirmation** (`address_pr_review.md:47`). Default: skip with the reason in
    the summary (already required, `:68`).

### Must stay

- Idea review (the one scope-shaping moment). Move questions that belong there to the front of the
  pipeline (`improve_idea`/`spec_from_idea`) as the idea's point 1 asks; the existing fan-out recipe
  already does so (`spec_from_idea.md:41-46`, `improve_idea.md:37`).
- PR approval (`setup_todo_list.md:130`) and `finish_worktree`'s `CHANGES_REQUESTED` guard
  (`finish_worktree.md:134`).
- Product/UX `Decide ...` items from QA red-lane bugs (`do_qa.md:483-492`, `:629`).
- Upstream-change `paused` when `direction: changed` (`pre_step_rebase.md:154-168`).
- Genuine environment or safety stops: real secrets (`commit_quickly.md:121`, `rebase_main.md:50`),
  rebase conflicts that are incompatible (`rebase_main.md:130`), dirty main worktree
  (`finish_worktree.md:17`), design-login authorisation (`register_design.md:79`), roadmap
  precursor and dependency warnings (`start.md:16-24`).
- Removing the worktree (`setup_todo_list.md:136`): the command cannot delete the directory it runs in.

### Constraints that shape any redesign

- `AskUserQuestion` is orchestrator-only; subagents fail-fast with `status: blocked` + `needs`
  (`claude_plugins/sdd/skills/claude-code-authoring/SKILL.md:37,75-76`; `resources/interactive_cli.md:3-8`).
- Fan-out only at depth 0, no subagent nesting (`SKILL.md:28`). `/sdd:next` runs commands inline on the
  main thread so their fan-out stays legal (`next.md:6,50`). Anything merged into a bigger command stays
  at depth 0 and its workers return `blocked`.
- The fan-out recipe's question test already exists: the answer changes the spec, nothing on disk answers
  it, and there is no obvious default; otherwise take the default and list it
  (`resources/fanout_recipe.md:17`, `spec_from_idea.md:46`). Spreading that test to `spec_review`,
  `implement_plan` and `plan_*_review` is the lowest-cost route to "front-load or don't ask".
- Inlined commands run under `/sdd:next`'s tool grants, not their own frontmatter (`next.md:98`). Merging
  steps into one command needs `AskUserQuestion` only if that command can still ask (`next.md:4` lists no
  `AskUserQuestion`; `implement_plan.md:4` and `plan_from_spec.md:3` do).
- `claude_plugins/sdd/resources/launcher_editing.md` is irrelevant here: it is the `claude.sh` edit
  procedure, with a STOP only for launchers that need hand-editing (L0).
- Plugin rules from `CLAUDE.md`: `sdd` and `ds` stay generic; `plan_security_review` and
  `plan_structure_review` live in `fls-dev`, but `/ds:threat-model` and `/ds:security-review` are in the
  generic plugin, so removing them from the sdd template is a template change and a docs change, not
  an FLS-specific one. Todo template lines reference `/fls-dev:` and `/ds:` prefixes from the generic
  `sdd` plugin (`setup_todo_list.md:76,86,91,101,106,113,118,123`); that is an existing coupling.

## Open questions for the owner

1. Should `/sdd:next` loop through several `(cmd)` items in one invocation (the context cost of that is
   the only reason I can find for the "`/clear` then `/sdd:next`" instruction, `next.md:93`)? Or is the
   goal a new, longer-running driver command?
2. After the cuts, which `(user)` items remain as stops? The data suggests: review idea, approve PR,
   `Decide ...` items from QA, upstream-change decision. Is "review the spec" meant to disappear once
   `spec_from_idea` and the review run in one step (idea lines 8-9), or should it stay as a gate?
3. Should the existing `/ds:threat-model` and `/ds:security-review` commands (generic plugin) be deleted,
   or only removed from the todo template? The idea says "can be removed" (`idea.md:13`).
4. For judgement calls the owner currently answers in `Decide ...` items (QA red lane), is a default
   plus a note in the report acceptable, with the item filed only for the genuinely security-adjacent or
   product-visible ones?
5. Should the sampled specs where `improve_idea`, `spec_from_idea` or `plan_from_spec` ran but
   weren't ticked (`make-sdd-more-efficient` `todo.md:13`, `educator-interface-looks-good` `todo.md:14-16`)
   be read as the owner hand-editing the spec, running another path, or the command failing to tick?
   The answer decides whether auto-ticking needs a check against artifacts (`setup_todo_list.md:32-39`
   does that only at creation).

status: ok
