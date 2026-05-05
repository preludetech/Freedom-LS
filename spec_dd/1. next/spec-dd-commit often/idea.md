# Idea: Make the SDD workflow commit and push often

## Problem

The Spec-Driven Development (SDD) workflow currently commits at only three points:

1. When the worktree is first created (`protected/start_worktree.md`).
2. At the very end of `implement_plan.md`, after every batch is done.
3. Inside `finish_worktree.md`, just before the working tree is checked clean.

Nothing in the SDD flow runs `git push` at all.

Consequences:
- A long SDD session can produce a large diff before the first checkpoint, which is hard to review and expensive to revert if the agent drifts.
- If the worktree machine dies mid-session, work between checkpoints is lost — there's no remote backup.
- `git bisect` is useless on a branch where one commit covers an entire implementation.
- Stage transitions can run with leftover edits from the previous stage, silently mixing concerns.

## Desired outcome

The SDD workflow should treat each stage as an **atomic, reviewable unit**: one stage = one diff, committed and pushed before the next stage starts.

Specifically:

- **Commit at every stage transition.** Idea finalized → commit. Spec written → commit. Spec reviewed → commit. Plan written → commit. Each plan review → commit. Each implementation batch → commit. QA fixes → commit. App-map refresh → commit.
- **Working tree must be clean at stage boundaries.** Each SDD slash command should refuse to start (or refuse to declare itself done) if `git status --porcelain` is non-empty. The next stage's diff is then exactly `HEAD~1..HEAD`.
- **Push after every stage commit, automatically.** Worktrees are short-lived and single-author, so push-as-backup is safe and matches the "push often" intent. CI cost is not a current concern.
- **Hook bypass is forbidden, and the prohibition is enforced by tooling.** `uv run git commit` is mandatory; `--no-verify`, `-n`, and equivalents must be denied at the harness level (deny rules in `.claude/settings.json`), not relied on as guidance text. This responds to documented real-world incidents where agents bypassed hooks despite memory rules saying not to (see research notes).
- **`finish_worktree` squashes per-stage commits before rebasing onto main.** Conventional-commits stage prefixes (`spec:`, `plan:`, `impl(N):`, `qa:`, …) make the squash groups identifiable. The branch keeps a readable stage narrative on `main` without dragging every checkpoint commit through the rebase. Force-push after the squash uses `--force-with-lease --force-if-includes`; plain `--force` is forbidden.

## Why this is worth doing

- **Recoverable** — `git revert` or `git reset --hard HEAD` puts the workflow back at the last known-good stage boundary.
- **Reviewable** — each stage's output stands on its own; reviewers can read commits as a story of the workflow.
- **Bisectable** — `git bisect` can find the first stage that introduced a regression.
- **Backed up** — pushed work survives a dead machine.
- **Diff-able by stage** — the next slash command can rely on `git diff HEAD~1` to inspect what the previous stage produced.
- **Aligned with the wider ecosystem** — research surveyed Claude Code official guidance, Cursor, Aider, Devin, Codex, Sweep, OpenHands; per-stage commits and push-as-backup is the converged default.

## In scope

- Updating SDD slash commands to commit at every stage transition with conventional-commits stage prefixes.
- Adding pre- and post-stage clean-tree assertions to SDD commands.
- Adding `git push` after each stage commit.
- Updating `finish_worktree.md` to squash by stage prefix before rebasing, and to use safe force-push semantics.
- Adding harness-level deny rules in `.claude/settings.json` to block `--no-verify` and equivalents on `git commit`.
- Defining an explicit hook-failure protocol the agent follows when `uv run git commit` exits non-zero (re-stage rewritten files, never `--amend`, hard stop after N retries).

## Out of scope (for now)

- Server-side branch protection on `main` (a repo configuration concern, not the SDD workflow's job — but the spec should call it out as a recommended backstop).
- Secret-scanning hooks (gitleaks etc.) — a separate hardening initiative.
- Opening intermediate / draft PRs as the worktree progresses — none of the surveyed tools do this; PR creation stays at the `ship` step.
- Per-edit auto-commit (the Aider model). Surveyed users complain about it loudly; we explicitly reject it.

## Open questions to resolve at spec time

- **Sub-commits within a single implementation batch.** If a batch produces a very large diff (e.g., > ~300 LOC or many unrelated files), should the agent split it before advancing? Defer until we see whether real batches need this.
- **Mid-stage interruption.** When the agent is interrupted mid-stage, the right answer is `git stash`, not commit. Worth being explicit about in the spec so the agent doesn't paper over the interruption with a partial-state commit.
- **Conflict-resolution affordances during `finish_worktree`'s rebase.** Worth enabling `git rerere` in the worktree so that repeated rebases (e.g., main moves while the worktree is in flight) don't compound conflict-resolution work.

## Research

Three research notes accompany this idea in the same directory:

- `research_reference_implementations.md` — what Aider, Cursor, Claude Code, Devin, Codex, Sweep, OpenHands, etc. actually do.
- `research_commit_best_practices.md` — atomic commits, "commit often / publish once", Conventional Commits + 50/72, push-frequency tradeoffs.
- `research_pitfalls_and_ux.md` — auto-commit/push failure modes, hook-bypass incidents, force-push hazards, recommended UX choices.
