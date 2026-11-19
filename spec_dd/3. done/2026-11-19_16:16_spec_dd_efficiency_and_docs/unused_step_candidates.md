# Unused-step candidates

Found by the audit in `research_codebase.md` §8. This spec removes only `address_pr_review`. Each
line below needs a keep-or-remove decision from the user. A removal becomes its own spec or a todo
item.

- `/sdd:spec_review` as a standalone command. `spec_from_idea` runs the same review wave, and the
  standalone command was last ticked on 2026-10-22.  Decision: Keep
- `/sdd:make_pr_quickly` as a standalone command. `/sdd:document` Step 3b opens the PR. Decision: Keep (`document` follows it inline)
- `/sdd:commit_quickly`: used ad hoc, not on the checklist. Decision: Move out of sdd
- `/sdd:capture_feedback`: a 17-line wrapper over the `capture-feedback` skill. Decision: Keep (the manual trigger, and the only path that commits)
- `finish_worktree.md` "Step 5: Tidy Claude project settings". decision: Keep
- The upstream-change scan and review (`pre_step_rebase.md` Steps 3–5). Decision: Keep. Three
  done specs record `direction: changed`, each a real catch: `educator-interface-looks-good`,
  `educator-interface-6-cohort-administration`, `learner-facing-ux-refinements`.
