# Research: Git Commit Best Practices for SDD Workflow

## Summary — Key Takeaways for SDD Design

1. **One artifact = one commit.** Each stage in the workflow (idea, spec, plan, batch implementation, review fix, QA pass) produces a distinct, reviewable artifact. That maps naturally onto the atomic-commit principle from the Linux kernel: "a single, self-contained, logical change."
2. **"Commit often, perfect later, publish once"** is the consensus pattern (Seth Robertson, Pro Git, Aider). Commit aggressively while working; clean up with interactive rebase only *before* the branch becomes shared/merged.
3. **Push after each stage commit.** For an SDD workflow with one author per worktree and short-lived branches, push frequency should mirror commit frequency. Pushes are backups, they unblock review, and force-push risk is contained because nobody else is on the branch.
4. **Use Conventional Commits + 50/72 body wrap.** Both are machine- and human-friendly, both compose well with pre-commit hooks (`uv run git commit`), and both fit Tim Pope / cbeams / Torvalds guidance.
5. **Working tree clean = stage gate.** Don't let the next slash-command run with uncommitted changes from the previous stage. This is the same discipline GitOps uses for declarative-state workflows: the repo *is* the state.
6. **Agentic code needs *more* checkpoints than human code, not fewer.** AI-assisted edits can drift fast; per-task commits make `git bisect` and rollback cheap (Osmani 2026; Aider design).

---

## 1. Atomic Commit Principles

An atomic commit is a single self-contained logical change: it builds, it passes tests on its own, and reverting it removes exactly that one concern with no collateral damage.

**Linus Torvalds / Linux kernel practice** (per the Subsurface README excerpt Torvalds wrote):
- Header line: imperative mood, single-line summary.
- Body: explain *why* and the reasoning, not *what* the diff already shows.
- Wrap body around ~74 chars so `git log` indents cleanly.
- Footer tags (`Reported-by:`, `Signed-off-by:`) for provenance.
- Core principle quoted from Torvalds: *"explain your solution and why you're doing what you're doing, as opposed to describing what you're doing."* ([gist mirror](https://gist.github.com/matthewhudson/1475276))

**Why atomic matters** ([Pull Checklist](https://www.pullchecklist.com/posts/git-commit-best-practices), [tarrsalah gist "every commit should be a perfect, atomic unit of change"](https://gist.github.com/tarrsalah/4e8936652fa6dfc13c71e866f6f3f768)):
- **Reviewable** — reviewers focus on one concern.
- **Revertable** — `git revert <sha>` undoes one thing cleanly.
- **Bisectable** — `git bisect` only works if each commit builds.
- **Searchable history** — `git log -S` and `git blame` point at meaningful changes, not "WIP".

**Rule of thumb from cbeams** ([cbea.ms/git-commit](https://cbea.ms/git-commit/)): *"If you're having a hard time summarizing, you might be committing too many changes at once."* If the subject line needs an "and", split the commit.

---

## 2. "Commit Often" vs. "Commit Clean"

The tension is real but resolved by treating local and shared history differently.

**Commit-often side** ([Seth Robertson, "Commit Often, Perfect Later, Publish Once"](https://sethrobertson.github.io/GitBestPractices/)):
- Git only protects committed data. Frequent commits are checkpoints.
- "Once you `git push`… you should ideally consider those commits etched in diamond for all eternity."
- The cleanup window is *between* committing locally and pushing/merging.

**Commit-clean side** ([thoughtbot autosquashing](https://thoughtbot.com/blog/autosquashing-git-commits), [git-init blog](https://blog.git-init.com/how-to-tidy-up-a-dirty-commit-history/)):
- A linear, logical history makes reviewers' lives easier and makes future archaeology (blame/bisect/revert) tractable.
- Tools: `git commit --fixup=<sha>`, then `git rebase -i --autosquash <base>`.
- `fixup` reuses the parent message; `squash` lets you edit. Use `fixup` for "oops, typo" and `squash` for "merge two related changes."

**Hybrid (the practical answer):**
1. Work in messy WIP commits locally.
2. Before opening a PR (or before the next stage in SDD), interactively rebase to one logical-step-per-commit.
3. After push/merge, history is immutable.

**Conventional Commits** ([conventionalcommits.org](https://www.conventionalcommits.org/en/v1.0.0/)) is orthogonal — it shapes the *message*, not the granularity. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `style`. Scope in parens: `feat(student_progress): add scoring strategy`. `BREAKING CHANGE:` footer or `feat!:` for major bumps. Plays well with semver tooling and changelog generators.

---

## 3. Commit Message Conventions

**Tim Pope's 50/72 rule** ([tbaggery.com/2008/04/19/a-note-about-git-commit-messages](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html)):
- Subject: ≤50 chars, imperative mood, capitalized, no trailing period.
- Blank line.
- Body: wrap at 72 chars. Explain *what* and *why*, not *how*.

**cbeams' seven rules** ([cbea.ms/git-commit](https://cbea.ms/git-commit/)) — restate the same rules and add the imperative-mood test: *"If applied, this commit will _____"*. Subject must complete that sentence.

**When a body matters:**
- The change isn't obvious from the diff (architectural decision, non-local consequence).
- There's a tradeoff or a rejected alternative worth recording.
- The change references a spec, ADR, or external ticket.
- For trivial commits (typo, format, dependency bump) the subject alone is fine.

**Conventional Commits + 50/72 compose cleanly:**
```
feat(student_progress): add weighted scoring strategy

The default strategy averaged scores; the spec at spec_dd/.../weighting
calls for instructor-configurable weights per topic. Implements the
ScoringStrategy protocol on Cohort and threads weights through
StudentProgress.recalculate().

Refs: spec_dd/active/weighted-scoring/spec.md
```

Subject is 49 chars, body wraps at 72, imperative mood, type+scope prefix.

**FLS-specific note:** the project uses pre-commit hooks via `uv run git commit`. Hooks may reject commits on lint/format failures, which is fine — but it means `--amend` after a hook failure is a footgun (CLAUDE.md and project commit-safety guidance both call this out). If a hook fails, fix and create a *new* commit.

---

## 4. Push Frequency

**The default modern advice** ([Brian Blankenship, "Commit frequently, push often"](https://medium.com/nerd-for-tech/commit-frequently-push-often-2ba996307a3f), [Seth Robertson](https://sethrobertson.github.io/GitBestPractices/)): push at the end of every meaningful unit of work on a feature branch. Branches are cheap; remote storage is backup.

**Tradeoffs:**

| Push cadence | Pros | Cons |
|---|---|---|
| After every commit | Maximum backup, easy collaboration, CI runs early | CI cost; noisy notifications; force-push risk if you rebase |
| After each milestone | Cleaner CI signal, fewer notifications | Risk of losing work if local disk dies |
| Only when ready for review | Cleanest history, no CI churn | Big-bang reviews; no backup; lonely branch may diverge from main |

**For SDD with one-author-per-worktree branches, push-after-every-stage is the right default:**
- Worktree branches are short-lived and not collaborated-on, so force-push (after a rebase cleanup) is safe.
- Pushes are backups in case the worktree is lost.
- CI on each push catches breakage at the stage boundary, not at PR time.
- Anthropic SDK / agent contexts often run unattended overnight — pushes preserve work even if the machine sleeps.

**Avoid:** force-push to `main`/`master` ever; `--no-verify` to skip hooks (project rule); pushing broken code to long-lived shared branches.

---

## 5. Working Tree Cleanliness as a Checkpoint

**GitOps philosophy** ([gitops.tech](https://www.gitops.tech/), [Red Hat — Git Workflows for GitOps](https://developers.redhat.com/articles/2022/07/20/git-workflows-best-practices-gitops-deployments)): the Git repo is the *single source of truth* for desired state. Any drift between working tree and committed state is, by definition, undeclared state.

**Applied to a multi-stage SDD workflow:** treat "working tree is clean" as the precondition for advancing to the next stage. Why this is useful:
- The next slash-command can `git diff HEAD~1 HEAD` to see exactly what the previous stage produced.
- Recovery is trivial: `git reset --hard HEAD` puts you back at the last known-good stage boundary.
- Reviewers see one stage = one commit = one diff.
- Stops "spec edits leaking into plan stage" silently.

**When it's annoying (and how to mitigate):**
- Mid-stage interruption: stash with a clear name (`git stash push -m "wip: spec section 3"`) rather than committing junk.
- Tiny tweaks across stages: allow a `chore:` commit before stage advance.
- Don't enforce so strictly that authors invent fake commits to satisfy the gate; the gate exists so each stage's diff is reviewable, not as bureaucracy.

Release engineering uses the same pattern: tag-then-build, where the tag is the immutable checkpoint and any deviation requires a new tag.

---

## 6. Commit Frequency in Agentic / AI-Generated Code

The emerging consensus is **smaller, more frequent commits than human-written code**.

**Addy Osmani, "My LLM coding workflow going into 2026"** ([Medium](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e)):
- Commits are *"save points in a game"*. AI sessions can drift fast; checkpoints are cheap insurance.
- Disciplined cycle: **finish task → run tests → commit**.
- *"If an AI agent made five changes in one go and something broke, having those changes in separate commits makes it easier to pinpoint which commit caused the issue."*
- Use worktrees to isolate parallel AI sessions (FLS already does this).
- Core rule: *"Never commit code you can't explain."*

**Aider's design** ([referenced in MindStudio 2026 review](https://www.mindstudio.ai/blog/best-open-source-llms-agentic-coding-2026)): *"Every edit is a commit. Every session is a branch you can review, revert, or cherry-pick."* The tool bakes per-edit commits into the workflow because reverts are otherwise expensive when an LLM goes sideways.

**Globy AI workflow guide 2026** ([gogloby.com](https://gogloby.com/insights/ai-coding-workflow-optimization/)): *"Plan before generating. Ship in small diffs. Verify with tests that protect behavior. Keep rollback paths documented."*

**Why agentic code is different:**
- Diffs are larger per "session" because the model can edit many files at once.
- Failures are less local — a model "fixing" one thing may regress another.
- Bisect is therefore *more* valuable, not less, but only works if commits are atomic.
- Reviewers (human or AI) review smaller diffs faster and more accurately.

**Suggested heuristic for FLS SDD:** if a stage produces more than ~300 lines of generated code or more than ~5 files of unrelated changes, split into multiple commits within that stage *before* advancing.

---

## Recommendations for FLS SDD

### Concrete commit points

The current 7-stage flow (idea → spec → plan → implement-in-batches → review → QA → ship) should produce **at minimum** these commits:

| Stage | Commit | Type prefix |
|---|---|---|
| idea captured | `idea.md` finalized | `docs(sdd): capture idea for <slug>` |
| spec written | `spec.md` + `todo.md` | `docs(sdd): add spec for <slug>` |
| spec reviewed | review fixes to spec | `docs(sdd): apply spec review for <slug>` (squash into spec commit before merge) |
| plan written | `plan.md` | `docs(sdd): add implementation plan for <slug>` |
| security/structure review | review fixes to plan | `docs(sdd): apply plan review for <slug>` |
| implementation batch N | one commit per batch (more if batch is large) | `feat(<app>): <what the batch did>` |
| code review fixes | fixes per review pass | `fix(<app>): address review for <slug>` |
| QA pass | any test/UX fixes | `fix(<app>): qa fixes for <slug>` |
| ship | finish_worktree cleanup, todo.md tick-off | `chore(sdd): finalize <slug>` |

That's roughly **8–12 commits** per workflow instead of 3, with a hard floor of "one commit per artifact."

### Push points

- **After every stage commit.** Worktree branches are single-author and short-lived, so the cost of force-pushing after a pre-merge rebase is low and the backup value is high.
- **Never push directly to `main`** — always go through the worktree branch.
- **CI runs on push** — accept the cost; broken stages should be caught at the boundary, not at PR time.

### Working-tree-clean gate

Each `fls:sdd:*` slash command should refuse to run if `git status --porcelain` is non-empty (or prompt the user to commit/stash). This makes every stage diffable as `HEAD~1..HEAD` and gives the next stage a clean starting point.

### Message style

- **Conventional Commits** prefix (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`).
- **Scope** is the FLS app name (`student_progress`, `educator_interface`, etc.) for code, or `sdd` for workflow artifacts.
- **Subject** ≤50 chars, imperative, no period.
- **Body** wrapped at 72 chars, explains *why*, references the spec path (`Refs: spec_dd/active/<slug>/spec.md`).
- **Don't `--amend`** after a pre-commit hook failure — fix and create a new commit. CLAUDE.md and the harness commit-safety rules both require this.
- **Don't `--no-verify`** to skip hooks unless the user explicitly asks.
- All commits go through `uv run git commit` so pre-commit hooks run.

### Cleanup before merge

Optional but recommended: at the `finish_worktree` step, offer an interactive rebase (`git rebase -i --autosquash main`) to collapse "review fix" commits into their parent stage commits using `--fixup`. This keeps the merged history one-commit-per-stage without losing the in-flight checkpoint commits.

### Sample commit for SDD artifacts

```
docs(sdd): add spec for weighted scoring

Captures the requirement for instructor-configurable per-topic weights
in cohort progress calculations. Pulls in idea.md notes and resolves
the open question about default weights (uniform 1.0).

Refs: spec_dd/active/weighted-scoring/idea.md
```

### Sample commit for an implementation batch

```
feat(student_progress): add WeightedScoringStrategy

Implements the strategy from plan.md batch 2. Threads cohort.weights
through StudentProgress.recalculate() and falls back to uniform
weights when not configured. Migration adds Cohort.weights JSONField
with default {}.

Refs: spec_dd/active/weighted-scoring/plan.md (batch 2)
```

---

## Sources

- [cbea.ms — How to Write a Git Commit Message](https://cbea.ms/git-commit/)
- [Tim Pope — A Note About Git Commit Messages](https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html)
- [Seth Robertson — Commit Often, Perfect Later, Publish Once](https://sethrobertson.github.io/GitBestPractices/)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [Linus Torvalds on commit messages (Subsurface README, gist mirror)](https://gist.github.com/matthewhudson/1475276)
- [Pull Checklist — Git Commit Best Practices](https://www.pullchecklist.com/posts/git-commit-best-practices)
- [tarrsalah gist — every commit should be a perfect, atomic unit](https://gist.github.com/tarrsalah/4e8936652fa6dfc13c71e866f6f3f768)
- [thoughtbot — Autosquashing Git Commits](https://thoughtbot.com/blog/autosquashing-git-commits)
- [git-init — How to Tidy up a Dirty Commit History](https://blog.git-init.com/how-to-tidy-up-a-dirty-commit-history/)
- [Brian Blankenship — Commit frequently, push often](https://medium.com/nerd-for-tech/commit-frequently-push-often-2ba996307a3f)
- [GitOps.tech](https://www.gitops.tech/)
- [Red Hat — Git Workflows for GitOps Deployments](https://developers.redhat.com/articles/2022/07/20/git-workflows-best-practices-gitops-deployments)
- [Addy Osmani — My LLM coding workflow going into 2026](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e)
- [Globy — AI Coding Workflow Optimization 2026](https://gogloby.com/insights/ai-coding-workflow-optimization/)
- [MindStudio — Best Open-Source LLMs for Agentic Coding 2026](https://www.mindstudio.ai/blog/best-open-source-llms-agentic-coding-2026)
