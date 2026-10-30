# Spec-Driven Development (SDD)

A step-by-step workflow for taking a rough idea all the way to a merged pull request. Each step produces an artifact that feeds the next one, so you can pause, review, and correct course between stages.

## The workflow at a glance

1. **Spec** → turn the idea into a researched, reviewed specification.
2. **Plan** → turn the spec into an implementation plan and a QA plan, and review the plan.
3. **Implementation and QA** → execute the plan, then run the QA plan.
4. **Documentation and pull request** → run the documentation hooks, open the PR, address review feedback.
5. **Cleanup** → finish the worktree, then remove the worktree and branch.

These are the five sections of the `todo.md` checklist. Capturing the idea comes before them.

> `/sdd:start` is the entry point: it creates the `todo.md` checklist next to the spec/idea **and** sets up an isolated worktree for the work. Run it once, then do everything else inside the worktree.

> **One-time setup:** any setup a project's hooks need before the first SDD run (for example a diagram a plan review brief reads) is documented by that hook, not here.

---

## Step 0: The spec roadmap

`spec_dd/1. next/roadmap.md` is the spec roadmap: one row for every directory in `spec_dd/1. next/` and `spec_dd/2. in progress/`, with what it delivers, what it depends on and whether it is waiting or in flight. It is not `docs/product/roadmap.md`, which is the product roadmap.

- `/sdd:roadmap` with no argument syncs the file with the directories: adds rows for new directories, drops rows for finished ones, redraws the dependency graphs.
- `/sdd:roadmap <dir>` cuts an idea that is too big for one SDD run into ordered sibling specs, each with a decision-complete `idea.md` under `spec_dd/1. next/`, and adds the effort to the roadmap with its build order, its dependency graph and the decisions every child relies on. The cut goes by user-visible outcome, never by line count.
- "Ready to start" lists the waiting specs whose dependencies are done and that can go straight to `/sdd:start`. "Needs work on main first" lists the ones that can't yet, because something has to happen on main before a worktree branches off, such as a cut. The row's Notes cell says what, starting `Before starting:`.
- `/sdd:start` warns when a spec has a precursor or its dependencies are not done, flags its row `in progress` and takes it off both start lists. `/sdd:finish_worktree` removes the row, lands the result on `main` and adds any spec it unblocks to the right start list; when the last spec of a cut effort finishes, the effort's section is archived into the parent directory and the parent moves to done.

The format and the row grammar live in `claude_plugins/sdd/resources/roadmap_format.md`.

## Step 1: Capture the idea

1. Create an idea file manually (a markdown file describing what you want to build and why). If it is too big for one PR, run `/sdd:roadmap <dir>` first and continue with one of the specs it produces.
2. If the work has a design drawn in Claude Design, run `/sdd:register_design [dir] <handoff prompt or claude-design-url>`. On a feature branch it registers the design on that branch's own spec directory and commits it to that branch; on `main` it takes the spec (or a cut effort's parent) you name. It takes the handoff prompt Claude Design copies (or a bare link) and writes `design_prompt.md`, `design_source/` and `design_screenshots/` as well as `design.md`, which tells every later step how to read them. The design is a visual reference only: the specs and the existing functionality decide what gets built, and the project's own theme, tokens and icons style it.

## Step 2: Spec

1. Run `/sdd:spec_from_idea`. It researches the idea, writes the specification, runs the review wave and commits, all in one run. The review wave runs inside this command.
2. Review the spec and edit it manually where needed.
3. After substantial hand edits, run `/sdd:spec_review` to run the review wave again. It is not needed otherwise.

## Step 3: Plan

Run `/sdd:plan_from_spec`. This produces:

- an implementation plan, and
- a QA plan.

The plan review runs the built-in dimensions and the briefs listed under `## Plan Review Hooks` in `.claude/sdd/config.md`. It leaves every callout decided or recorded as an assumed default.

The plan is implementation only. Anything the spec asks for that the plan does not build and no documentation hook covers (a skill row, a roadmap note, a glossary term) becomes a `(user)` item in `todo.md`, placed right after the `/sdd:document` item, so it is done before the pull request opens.

An optional suffix argument (`/sdd:plan_from_spec <spec> 2b`) selects a second plan in the same spec directory: `2b. plan.md` and `3b. frontend_qa.md` instead of `2. plan.md` and `3. frontend_qa.md`.

## Step 4: Implementation and QA

### Implement

Run `/implement_plan` to execute the implementation plan. An optional suffix argument (`/implement_plan 2b`) selects the plan `2b. plan.md`, commits its batches as `[batch 2b.N]` and resumes only from those commits. Without a suffix, it runs `2. plan.md` with `[batch N]` commits. After each slice that builds a designed screen, it runs the design check through the `Design check` hook in `.claude/sdd/config.md`, and sends any design misses (unmet lines of the plan's design checklist) to fix batches.

The project's own pre-commit checks and Claude Code's `/security-review` cover the code diff ad hoc; no SDD step runs a security review.

### QA

Run the project's QA command: the `QA command` key under `## QA Hooks` in `.claude/sdd/config.md`.
`/sdd:start` writes it into `todo.md` as the QA step. A project with no QA command runs the QA plan
by hand.

How the QA command handles skipped tests, missing test data or the bugs it finds is its own
business: read its documentation, and check `qa_report.md` for the outcome.

## Step 5: Document

Run `/sdd:document`. It reads `## Documentation Hooks` in `.claude/sdd/config.md` and invokes each listed skill in order, committing per hook. A project that lists no hooks gets a no-op.

## Step 6: Pull request

1. Run `/sdd:make_pr_quickly` to open the pull request. It uses `gh pr create --fill`, building the title and body from the commits; it reads nothing else.
2. Run `/sdd:address_pr_review` to work through review feedback. It fetches the comments through the `Fetch PR comments` script under `## PR Hooks` in `.claude/sdd/config.md`, or with `gh` directly when that key is blank.

## Step 7: Cleanup

Once the PR is approved (or already merged), run `/sdd:finish_worktree`. It rebases, archives the spec and its roadmap row, lands the close-out on `main` by fast-forward push and brings the main worktree up to date. It stops, changing nothing on `main`, if the main worktree has uncommitted work or an operation in progress. Nobody runs `git merge` in the main worktree by hand. Then remove the worktree and delete the branch.

`/sdd:commit_quickly` is the fast commit path for use during implementation: it stages the already-staged index if there is one, otherwise the files Claude touched this conversation (`mine`; `all` stages everything), and commits without running the test suite. When the commit is a checkpoint you have not verified, use a commit command that runs the targeted test tier first, if the project has one.

---

## How the workflow runs

2. **Model tiering & the override knob.** Defaults: mechanical work (test runs, commits, file moves, todo ticking) → the `sdd:sdd-mechanic` agent (Haiku); non-interactive fan-out (research topics, review dimensions, scans) → the `sdd:sdd-worker` agent (Sonnet); interactive authoring/review commands run at depth 0 on the **user's session model** (so run the session on a strong model). To change a step's model, **edit the relevant agent file's `model:` frontmatter** (`claude_plugins/sdd/agents/sdd-mechanic.md`, `sdd-worker.md`). The env var `CLAUDE_CODE_SUBAGENT_MODEL` can force one model for **all** subagents in a pinch — but it **overrides every per-agent `model:` frontmatter**, so it must be left **unset (or `inherit`)** for normal tiered operation.

3. **Aliases vs pinned IDs.** The agents use aliases (`haiku`/`sonnet`) for readability. A user who wants frozen, reproducible automation can pin dated IDs (e.g. `claude-haiku-4-5`) in the agent files instead.

4. **Target Claude Code version.** These files target the current **2.1.x** line — per-agent/per-command `model:` frontmatter, `AskUserQuestion`, non-nesting subagents, and "commands merged into skills" all hold here. There is no runtime version check; this is a documented target, not enforced.

5. **Every artifact command commits and pushes itself.** Any command that writes or edits an SDD artifact ends by delegating a commit and push to `sdd:sdd-mechanic`, following `claude_plugins/sdd/resources/commit_and_push.md`. A command run in hook mode keeps its commit; `/sdd:document` commits for a hook that has no commit step. The commit subject always leads with the spec directory name, so `git log` reads as a per-spec history. Nothing is committed on `main`/`master`, and nothing unrelated is staged. The one exception is `spec_dd/` bookkeeping that has no worktree yet (`/sdd:start`'s move to in progress, `/sdd:roadmap`'s edits): that is committed on `main` and not pushed.

6. **Why it runs this way.** See the **`claude-code-authoring`** skill for the canonical reference on the Claude Code mechanics behind all of the above: no subagent nesting or fan-out, no slash commands from subagents, no `AskUserQuestion` in subagents, model tiering, and file-based hand-off.

---

## The `todo.md` checklist

`/sdd:start` creates a `todo.md` checklist in the spec directory that tracks every step above, in five sections. Commands tick their own item (and add follow-up tasks where relevant) by invoking the protected helper at `claude_plugins/sdd/commands/protected/update_todo.md` as their final step. You don't run this helper yourself. The human ticks the `(user)` items and the two PR commands with the approval item. The commit-and-push step runs straight after it.
