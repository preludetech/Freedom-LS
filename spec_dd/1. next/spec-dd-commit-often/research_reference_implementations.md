# Reference Implementations: Commit/Push Patterns in AI-Assisted Dev Workflows

## Top-of-page summary (takeaways for "commit often")

- **Per-edit auto-commit (Aider) is the most aggressive end of the spectrum** and generates a steady stream of user complaints: noisy history, accidental commits of unrelated dirty work, verbose messages, and the `--no-auto-commits` flag itself being buggy. (https://aider.chat/docs/git.html, https://github.com/Aider-AI/aider/issues/4074, https://github.com/paul-gauthier/aider/issues/101)
- **None of the surveyed tools `git push` automatically by default.** Aider explicitly does not push. Devin pushes only as part of opening a PR. Codex cloud and OpenHands hand the user a PR to confirm. Push is consistently a human-controlled gate. (https://aider.chat/docs/git.html, https://docs.devin.ai/integrations/gh, https://github.com/OpenHands/OpenHands/issues/1281)
- **Per-task / per-prompt commits is the emerging middle ground.** Cursor 1.7 + GitButler, Claude Code's recommended workflow, and Sweep all commit "when a logical task completes," not per file edit. (https://blog.gitbutler.com/cursor-hooks-integration, https://code.claude.com/docs/en/best-practices)
- **Anthropic's official Claude Code guidance is "commit at the end of each step in a 4-phase loop"** (Explore → Plan → Implement → Commit), not per file. Already aligned with the FLS SDD model. (https://code.claude.com/docs/en/best-practices)
- **Commit messages are universally LLM-generated from the diff + recent context, usually Conventional Commits.** Aider uses a `--weak-model`. Cursor uses the prompt as the message basis. Devin uses a "concise imperative" style. (https://aider.chat/docs/git.html, https://blog.gitbutler.com/cursor-hooks-integration)
- **Attribution matters.** Aider appends `(aider)` to author/committer. Claude Code uses `Co-Authored-By` trailers. Devin uses a dedicated GitHub user with optional GPG signing. (https://aider.chat/docs/git.html, https://www.deployhq.com/blog/how-to-use-git-with-claude-code-understanding-the-co-authored-by-attribution, https://docs.devin.ai/integrations/gh)
- **PR creation, not push, is the universal "exit" event.** Sweep, Devin, OpenHands, Codex cloud, and GitHub Copilot Workspace all converge on "when work is done, open a PR." None of them open intermediate/draft PRs as the agent goes. (https://docs.openhands.dev/openhands/usage/cloud/github-installation, https://docs.devin.ai/integrations/gh, https://github.com/githubnext/copilot-workspace-user-manual/blob/main/overview.md)
- **Anthropic's `PreCommit`/`PostCommit` hooks request was closed "not planned"** — auto-commit in Claude Code stays a CLAUDE.md / `PostToolUse` workaround, not a first-class feature. FLS shouldn't wait for native hooks. (https://github.com/anthropics/claude-code/issues/4834)
- **Devin's hard lesson: anything not committed before session end disappears.** Sandboxed agents need explicit "checkpoint to remote" steps. Worth borrowing for FLS implement-batch boundaries. (https://docs.devin.ai/integrations/gh)
- **"Dirty commits" (committing pre-existing uncommitted changes before agent edits) is Aider's most-complained-about behavior.** FLS should never commit work the user didn't author without explicit consent. (https://github.com/paul-gauthier/aider/issues/5, https://github.com/paul-gauthier/aider/issues/314)

---

## Aider — https://aider.chat, https://aider.chat/docs/git.html

- **When**: Per LLM edit. "Whenever aider edits a file, it commits those changes with a descriptive commit message." Also commits any pre-existing dirty changes *before* applying its own edits, in a separate commit.
- **Push**: No. "Aider auto-commits, but git push is still your call." (https://www.deployhq.com/guides/aider)
- **Messages**: "Aider sends the `--weak-model` a copy of the diffs and the chat history and asks it to produce a commit message." Default Conventional Commits; customizable via `--commit-prompt`.
- **Confirmation**: None by default. Opt out with `--no-auto-commits` / `AIDER_AUTO_COMMITS=0`. Disable dirty commits with `--no-dirty-commits`. (https://aider.chat/docs/config/options.html)
- **Attribution**: `(aider)` appended to git author and committer; configurable via `--attribute-author`, `--attribute-committer`, `--attribute-co-authored-by`.
- **Complaints**:
  - "the autocommit feature can be a major nuisance / UX nightmare." (https://github.com/tninja/aider.el/issues/24)
  - False-positive dirty-commit detection: "Aider creates a commit when I add a file that was already in Git." (https://github.com/paul-gauthier/aider/issues/314)
  - Verbose messages embedding chat history. (https://github.com/paul-gauthier/aider/issues/392)
  - `--no-auto-commits` doesn't fully turn off auto-commits in all paths. (https://github.com/paul-gauthier/aider/issues/101)
  - `--no-auto-commits` also disables `--dirty-commits` despite docs. (https://github.com/Aider-AI/aider/issues/4074)
  - Dirty-workspace handling bricks aider on messy repos. (https://github.com/paul-gauthier/aider/issues/5)

## Cursor / Cursor Composer — https://docs.cursor.com/more/ai-commit-message, https://blog.gitbutler.com/cursor-hooks-integration

- **When (vanilla)**: Only when the user asks. Cursor has an AI-commit-message generator that fills a message from staged diff + repo history; user clicks commit. Composer does **not** auto-commit on accept. Open feature request since 2024. (https://forum.cursor.com/t/auto-ai-generated-git-commit-after-accepted-agent-changes/103095, https://forum.cursor.com/t/composer-create-a-git-commit-for-every-accept-all/25923)
- **When (Cursor 1.7 hooks + GitButler)**: `afterFileEdit` tags edited files to a virtual branch; `stop` hook commits with message based on the chat prompt. "Every new chat... will automatically be put in a new branch and every time the task is completed, a new commit will be made based off your prompt." Per-chat/per-task, not per-file.
- **Push**: No automatic push mentioned in any source.
- **Confirmation**: Vanilla flow requires user click; GitButler hook flow is unattended once configured.
- **Complaints**: Mostly *requests* for more automation. Forum threads note that without auto-commit, long Composer sessions produce one giant un-reviewable diff.

## GitHub Copilot Workspace / Coding Agent — https://github.com/githubnext/copilot-workspace-user-manual/blob/main/overview.md, https://docs.github.com/copilot/using-github-copilot/coding-agent/asking-copilot-to-create-a-pull-request

- **When**: At end of task. Workspace's terminal step is "Complete the task" — user picks Create PR / Create draft PR / Push to new branch / Push to current branch. Whole workspace session = unit of work. No per-edit commit.
- **Push**: Yes, but only at task completion and only if user picks a push option.
- **Messages**: Generated as part of PR creation; prompt template not exposed.
- **Confirmation**: Yes — explicit user action to publish.

## OpenAI Codex (cloud agent) — https://developers.openai.com/codex/cloud, https://developers.openai.com/codex/integrations/github

- **When**: At task end. Each cloud task in its own sandbox preloaded with the repo, produces a PR. "You can commit, push, and create pull requests for local and worktree tasks directly from within the Codex app."
- **Push**: Yes — push is part of "turn results into PRs." No evidence of intermediate pushes.
- **Confirmation**: Cloud → PR is the artifact you review. CLI/IDE → user invokes commit/push.
- **Throughput data point**: OpenAI's "Harness engineering" post — ~1,500 PRs merged in 5 months by 3 engineers driving Codex (~3.5 PRs/eng/day). Implies one PR per task. (https://openai.com/index/harness-engineering/)

## Claude Code (Anthropic, official) — https://code.claude.com/docs/en/best-practices

- **When**: 4-phase loop **Explore → Plan → Implement → Commit**. Commit is its own step at the end. Docs say: *"Ask Claude to commit with a descriptive message and create a PR."* No prescription to commit per file or per edit.
- **Push**: Only when user (or `/commit-push-pr`-style command) tells it to. Not in the default loop.
- **Messages**: LLM-generated from the diff. Anthropic's `/commit` plugin does staging + diff analysis + atomic-commit suggestions and adds `Co-Authored-By: Claude` trailers. (https://claude.com/plugins/commit-commands)
- **Confirmation**: Yes by default — bash `git` commands gated by permission system unless allowlisted.
- **Hooks**: Community pattern is `PostToolUse` with `Edit|Write` matcher running `git commit`. (https://www.morphllm.com/claude-code-hooks, https://bleepingswift.com/blog/claude-code-auto-commit) Dedicated `PreCommit`/`PostCommit` hooks request (#4834) **closed "not planned."** Reasons: existing workaround can't *block* a commit that fails pre-checks and requires brittle command-string parsing.
- **Third-party "commit often" guides** advocate ≥1 commit/hour, atomic, squash on merge. (https://github.com/awattar/claude-code-best-practices) — not Anthropic-official.

## Devin (Cognition AI) — https://docs.devin.ai/integrations/gh

- **When**: At task milestones. Plan → code → test → push → open PR. Intermediate work during long sessions is **not** auto-committed; docs explicitly tell users to instruct Devin to commit/push for exploratory tasks before session ends, since uncommitted work is lost when the sandbox tears down.
- **Push**: Yes — pushing is part of opening the PR. Not draft by default.
- **Messages**: "Concise, imperative style (e.g., `Fix API error handling`)."
- **Confirmation**: Devin runs as a regular GitHub contributor; branch-protection rules act as the safety net.
- **Attribution**: Dedicated GitHub user; optional GPG signing via persistent machine-image keys (mid-session-generated keys are lost).

## Sweep — https://docs.sweep.dev/, https://github.com/sweepai/sweep

- **When**: After plan approval. Trigger via issue label/title → Sweep posts plan as comment → user can edit → Sweep creates a branch and commits → opens PR. Multiple commits per task possible; unit shipped is a PR.
- **Push**: Yes, on the way to opening the PR.
- **Confirmation**: Plan comment is the gate. After approval, runs unattended. Reviewers comment on PR; Sweep pushes follow-ups.

## OpenHands (formerly OpenDevin) — https://docs.openhands.dev/openhands/usage/cloud/github-installation, https://github.com/OpenHands/OpenHands/issues/1281

- **When**: At task completion. "When OpenHands works on an issue, it will... open a pull request if it determines that the issue has been successfully resolved."
- **Push**: Yes now (cloud). Historically (issue #1281) early OpenDevin couldn't `git push` due to permission gaps; workaround was opening the GitHub PR page for the user to manually click submit.
- **Messages**: PR titles must follow Conventional Commits prefixes (`feat`, `fix`, `docs`, `style`, ...).
- **Confirmation**: PR is the gate. No per-edit confirmation.

## SWE-agent (Princeton/Stanford) — https://github.com/SWE-agent/SWE-agent

- **When**: Doesn't really commit. Research-oriented; produces a **patch file** that can be `git apply`-ed. Environment resets repos to specific commits between runs as part of evaluation. (https://github.com/princeton-nlp/SWE-agent/issues/41)
- **Push**: No — patch-centric, not commit-centric.
- **Relevance to FLS**: mostly tangential.

---

## Recommendations for FLS SDD

### Borrow

1. **Per-stage commit, not per-edit.** Match Anthropic's 4-phase guidance and Cursor-1.7-hooks per-task model: commit at the end of each SDD stage (idea → spec, spec → plan, plan → implement-batch, etc.), not per file edit. Avoids Aider's worst UX failure mode while still giving frequent rollback points.
2. **One commit per implement-batch.** Each batch is a logical unit; commit it with a descriptive message. Mirrors Devin's task-milestone cadence and matches Codex cloud's ~1 PR per task.
3. **LLM-generated Conventional-Commits messages with `Co-Authored-By: Claude` trailer.** Already established convention for Claude Code; the trailer keeps commits auditable. (Existing FLS commits already use this — see commit `36b9b6d`.)
4. **Add `git push` at well-defined gates, not continuously.** Suggested gates: end of plan-approval (push spec + plan as a checkpoint), end of each implement-batch (push the batch), and end of finish (push final state). Avoids Devin's "session ended, work lost" problem and gives QA reviewers a remote-visible state.
5. **Use a stage-completion hook, not a file-edit hook.** Mirror Cursor 1.7's `stop` hook + GitButler model. Use Claude Code `Stop` / `SubagentStop` to deterministically commit at stage boundaries even if the model forgets. (https://code.claude.com/docs/en/hooks-guide)
6. **Branch-per-worktree is already correct.** FLS already uses `fls:git-worktree-setup`. Devin's PR-as-final-artifact + branch-protection model maps cleanly onto this.
7. **Make commit messages reference the SDD stage and todo item.** Borrow from Cursor's "commit message based on the prompt" — for FLS, base it on the active todo.md item being ticked off. Gives readable history mirroring the spec.

### Avoid

1. **Per-edit auto-commit.** Aider's biggest source of user pain.
2. **Dirty-commits ("commit user's pending work before agent edits").** Aider's #1 complaint cluster. FLS should never silently commit work the developer didn't ask to commit. If the worktree is dirty at stage boundary, surface it and ask.
3. **Auto-push on every commit.** Nobody surveyed does this.
4. **Custom `PreCommit`/`PostCommit` Claude Code hooks.** Anthropic closed #4834 as "not planned." Use `Stop` / `PostToolUse(Bash(git commit:*))` patterns instead.
5. **Opening intermediate / draft PRs as the agent works.** None of the surveyed tools do this. Push to the branch, but defer PR creation until the `ship` stage.
6. **Verbose commit messages with chat history embedded.** Aider users complain about this loudly.

### Open questions

- **Sub-commits within an implement-batch?** No surveyed tool has a clear answer. Defer until we feel the pain.
- **Squash on merge or preserve commit history?** Third-party Claude Code guides recommend squash; not in Anthropic's official docs. Project-specific call.
- **Should `git push` require user confirmation?** Devin says no (branch protection gates it); Aider says yes. FLS likely fine auto-pushing on stage completion since worktrees are isolated.
