# Research: UX patterns for a chained, mostly unattended SDD run

Grounded in: `claude_plugins/sdd/commands/README.md`, `start.md` (Steps 0-4: asks via `AskUserQuestion` for precursor and dependency, ends with "cd into the worktree and run `/sdd:spec_from_idea`"), `spec_from_idea.md` (Step 2 question batch while workers run, Step 7 end-of-run batch), `fanout_recipe.md` ("When a question comes late": default taken and recorded under `## Open questions` as `- Q: ... -> A: ... (assumed default: ... Overrule by editing ...)`, in a plan as `> **Assumed default:** ...`), `do_qa.md` (files `add:"<section>|user|Decide ..."` items in `todo.md`). Web evidence is thin and mostly from community copies of spec-kit; treat it as supporting, not authoritative.

Web sources:
- https://github.com/github/spec-kit/issues/1147 (clarify: one question per turn, recommended option first with reason)
- https://smithery.ai/skills/dceoy/speckit-clarify (cap of about 5 questions; multiple choice 2-5 options or a short answer; reply "yes"/"recommended" accepts the recommendation; answers written to a Clarifications section)
- Terraform plan/apply, installer `-y` modes, and Claude Code plan mode are cited from general knowledge, not fetched.

## 1. Front-loaded interview, then unattended

- Pattern: ask everything in one batch at the start, each question with a recommended default and a reason. spec-kit clarify caps questions (about 5) and lets "yes" accept the recommendation. Installers' `-y` accepts all defaults. Terraform separates "plan" (show everything) from "apply" (run it).
- Fit: strong. SDD already does this (up to 4 per `AskUserQuestion`, a recommended answer and one clause why). The gap is that the batch is per command, so a chain would ask 3 times (start, register_design, spec_from_idea) with idle gaps.
- Shape: `/sdd:start` builds one **chain question batch** at depth 0 before any long work. It reads `design_prompt.md` presence, the idea, and the roadmap precursor/dependency checks. It pre-asks the questions the downstream commands would ask, in up to 4 per call, and chains calls only while workers run. The answers go into a small file in the spec dir (for example `chain_answers.md`: question, answer, source). Downstream commands run in a mode (like the existing `mode: hook`) that reads that file instead of asking. A question not in the file takes its recommended default (pattern 4). "Accept all defaults" is the first option of the first call, so one keystroke ends the interview. Never let a question's wording depend on research not yet run; those stay in the spec_from_idea window while workers run.
- Rule of thumb from spec-kit: one decision per question, the recommended option first, short options.

## 2. Progress visibility on a long chained run

- Pattern: a printed step list with per-step status (running, done, skipped, failed), one line per step, one final summary. Task-list tools (Claude Code's own todo display, CI step logs) tick as they go.
- Fit: strong, and `todo.md` already is the durable form.
- Shape: at chain start print the planned chain as a numbered list (`1 setup, 2 move, 3 worktree, 4 register_design (skipped: no design_prompt.md), 5 spec_from_idea`). After each step print one line: `[done] step name - artifact path - commit sha`. Each command still ticks its own `todo.md` item via `update_todo.md`, so the file on disk and the terminal agree and survive a closed terminal. Final summary, fixed fields: steps run and skipped; artifacts with paths; the worktree path; assumed defaults count and where to grep for them (`## Open questions`, `Assumed default`); `Decide` items filed; the next command or human step; failures. Keep it under about 15 lines; details live in files.

## 3. Pause/resume and "stop here"

- Pattern: a chain ends by saying where it stopped and the exact next command. Opt-out is explicit, either a flag on the entry command (`--no-chain`/`--stop-after=<step>`), a config value, or an answer to the batch. Resume is idempotent: re-running skips what is already done.
- Fit: needed. Every step must stay runnable alone (the idea says QA must stay independently runnable).
- Shape: each command has two entry modes, standalone (today's behaviour: asks its own questions, ends with "next: /sdd:..." ) and chained (told by the caller, reads the answers file, does not call the next step itself unless it is the orchestrator). Make `start.md` and `implement_plan.md` the only orchestrators; the others never invoke the next command, they only print "next". Opt-out: an argument on the entry command (`/sdd:start --stop-after=worktree`, `/sdd:implement_plan --no-qa`) plus an optional `.claude/sdd/config.md` key for a project default. Resume: detect completion from artifacts and `todo.md` ticks and commits (the existing `[batch N]` commit resume is the model). On any stop, print: what finished, why it stopped (blocked on a question, failure, opt-out), and the single next command. Slash commands cannot be invoked from subagents, so chaining has to be depth-0 inline reading or the `Skill` tool, and the chain stops are natural at depth 0.

## 4. Deferred decisions

- Pattern: record "assumed X, change if wrong" in the artifact itself so one grep finds every unconfirmed decision; humans triage later (open questions sections, ADR "proposed" status, PR review comments, spec-kit's Clarifications section).
- Fit: already built; extend it.
- Shape: keep the two existing formats unchanged (spec `- Q: ... -> A: ... (assumed default ...)`, plan `> **Assumed default:** ...`). Add: QA findings that need a human go to `todo.md` as `Decide ...` `(user)` items (already how `do_qa.md` does it). A chain has one catch-up point: the final summary lists counts and the grep commands, and the end-of-run batch in spec_from_idea Step 7 stays the place the human confirms or overrules. Not to be added: a new decisions file, since a second location defeats one-grep discovery. A chained run's pre-batch answers are recorded with source "asked up front", so a reviewer can tell asked from assumed.

## 5. Parallel workers and worktrees in a terminal

- Pattern: label every output line with the worker or slice (prefix, like `docker compose` or `turbo` logs), print only start and finish lines per worker, collect failures into the summary rather than interleaving logs, and show a table at the end.
- Fit: good, because subagents are fire-and-forget and return one result each, so there is no stream to interleave. The main risk is a failed slice hiding in a long summary.
- Shape: before dispatch print a table `slice | worktree path | branch | files owned`. Each worker writes its output to a file and returns a one-line `status=... path=... reason=...` (the existing worker contract). The orchestrator prints one line per worker as it returns, failures marked first and in full (reason plus the log path), successes as one line. Merge: short-lived worktrees get a predictable name (`<spec>-slice-<n>`), merge back in plan order, and the summary reports per slice: merged, conflict (files), or skipped; on a conflict stop the chain and name the slice and files. Remove short-lived worktrees on success; keep and name a failed one so the human can inspect. Slices are only parallel when the plan says they touch disjoint files; otherwise run serially (a conflicting merge is worse than a slower run).

## 6. Opting into the chain

- Pattern: tools that run multi-step flows (installers, `npm init -y`, Terraform `-auto-approve`) default to interactive with an explicit unattended flag, because the unattended mode is irreversible or costly. Where steps are cheap and reversible and every output is a reviewable artifact, "run it all, stop at the human gates" is the better default.
- Fit: here the artifacts are committed, in a worktree, and reviewable, and the idea says the human should not have to drive each step. Default to chaining, with an opt-out.
- Shape: default **chain**, with the single up-front batch as the "ask once" moment. First question of the batch offers: "Run the whole chain with recommended defaults (Recommended)" / "Answer the questions, then run the chain" / "Stop after setup (no chain)". Opt-out also by the argument or config key in pattern 3. Hard stops regardless of mode: a `blocked` return, a failed review or QA gate, a merge conflict, and the human-only `(user)` items in `todo.md`. Do not chain past the PR: opening the PR and `/sdd:finish_worktree` stay manual, as they publish work and land on main.

## Cross-cutting recommendations

1. One answers file per spec run, read by every chained step; commands never re-ask what it holds.
2. One orchestrator per chain (start, implement_plan); other commands only print "next".
3. A fixed final-summary shape shared by both chains.
4. Failures stop the chain with a named next command; assumptions never stop it.

status: ok · reason: seven spec-grounded patterns written; web evidence limited to spec-kit clarify sources, the rest reasoned from SDD files and general knowledge
