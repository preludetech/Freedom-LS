# Spec-Driven Development (SDD)

A step-by-step workflow from a rough idea to a merged pull request. Each step produces an artifact that feeds the next, so you can pause, review and correct course between stages.

## The workflow at a glance

1. **Spec** → turn the idea into a researched, reviewed specification.
2. **Plan** → turn the spec into an implementation plan and a QA plan, and review the plan.
3. **Implementation and QA** → execute the plan, then run the QA plan.
4. **Documentation and pull request** → run the documentation hooks, open the PR, address review feedback.
5. **Cleanup** → finish the worktree, then remove the worktree and branch.

These are the five sections of the `todo.md` checklist. Capturing the idea comes before them.

> `/sdd:start` is the entry point: it creates the `todo.md` checklist next to the spec/idea **and** an isolated worktree, moves the session into the worktree, registers a design when `design_prompt.md` is present and writes the spec. When it ends, the session is already inside the worktree, so everything after it runs there.

> **One-time setup:** any setup a project's hooks need before the first SDD run (for example a diagram a plan review brief reads) is documented by that hook, not here.

---

## Step 0: The spec roadmap

`spec_dd/1. next/roadmap.md` is the spec roadmap: what is being built next. It opens with "Up next" (specs in progress, specs ready to start, specs that need work on main first, and a diagram of the next three levels of dependencies), then has one section per feature: every spec waiting or in flight with its state, an SVG dependency diagram and lean notes. Specs are always named by directory name, and finished work is left out. `docs/product/roadmap.md` is the product roadmap, a different file.

- `/sdd:roadmap` with no argument syncs the file with the directories: adds bullets for new directories, drops finished ones, and runs `scripts/roadmap.py` to set statuses, regenerate "Up next" and redraw the diagrams.
- `/sdd:roadmap <dir>` cuts an idea that is too big for one SDD run into ordered sibling specs, each with a decision-complete `idea.md` under `spec_dd/1. next/`, and adds them to the roadmap as a feature with its diagram and notes. The cut goes by user-visible outcome, never by line count.
- A spec whose bullet ends `Before starting:` has work to do on main first, such as a cut, and is listed under "Needs work on main first" instead of "Ready to start".
- `/sdd:start` warns when a spec has a precursor or unmet blockers, and the script marks it `in progress`. `/sdd:finish_worktree` removes its bullet and reruns the script, which unblocks whatever waited on it; when the last spec of a cut effort finishes, the feature's section is archived into the parent directory and the parent moves to done.

The format and the bullet grammar live in `claude_plugins/sdd/resources/roadmap_format.md`.

## Step 1: Capture the idea

1. Create an idea file manually (a markdown file describing what you want to build and why). If it is too big for one PR, run `/sdd:roadmap <dir>` first and continue with one of the specs it produces.
2. If the work has a design in Claude, run `/sdd:register_design [dir] <design artifact link>`. On a feature branch it registers the design on that branch's own spec directory and commits it to that branch; on `main` it takes the spec (or a cut effort's parent) you name. The command takes the link of a Design Artifact in Claude (or a handoff prompt holding one), reads the canvas with the `Artifact` tool and writes `design_prompt.md`, `design_source/`, `design_screenshots/` and `design.md`. `design.md` tells every later step how to read them. The design is a visual reference only: the specs and the existing functionality decide what gets built, and the project's own theme, tokens and icons style it. See **Registering a design** below.

## Step 2: Spec

1. Run `/sdd:spec_from_idea`. It researches the idea, writes the specification, runs the review wave and commits, all in one run.
2. Review the spec and edit it manually where needed.
3. After substantial hand edits, run `/sdd:spec_review` to run the review wave again. It is not needed otherwise.

## Step 3: Plan

Run `/sdd:plan_from_spec`. This produces:

- an implementation plan, and
- a QA plan.

The plan review runs the built-in dimensions and the briefs listed under `## Plan Review Hooks` in `.claude/sdd/config.md`. It leaves every callout decided or recorded as an assumed default.

The plan is implementation only. Anything the spec asks for that the plan does not build and no documentation hook covers (a skill row, a roadmap note, a glossary term) becomes a `(cmd)` item in `todo.md`, placed right after the `/sdd:document` item; `/sdd:document` executes it before it opens the pull request, and lists it in its report if it could not.

An optional suffix argument (`/sdd:plan_from_spec <spec> 2b`) selects a second plan in the same spec directory: `2b. plan.md` and `3b. frontend_qa.md` instead of `2. plan.md` and `3. frontend_qa.md`.

## Step 4: Implementation and QA

### Implement

Run `/implement_plan` to execute the implementation plan. It runs batch waves: up to `Parallel batches` (the key in `.claude/sdd/config.md`) independent batches at a time, each in its own batch worktree. When the batches are done it continues into the QA command. An optional suffix argument (`/implement_plan 2b`) selects the plan `2b. plan.md`, commits its batches as `[batch 2b.N]` and resumes only from those commits. Without a suffix, it runs `2. plan.md` with `[batch N]` commits. After each slice that builds a designed screen, it runs the design check through the `Design check` hook in `.claude/sdd/config.md`, and sends any design misses (unmet lines of the plan's design checklist) to fix batches.

The project's own pre-commit checks and Claude Code's `/security-review` cover the code diff ad hoc; no SDD step runs a security review.

### QA

Run the project's QA command: the `QA command` key under `## QA Hooks` in `.claude/sdd/config.md`.
`/sdd:start` writes it into `todo.md` as the QA step. A project with no QA command runs the QA plan
by hand.

How the QA command handles skipped tests, missing test data or the bugs it finds is its own
business: read its documentation and check `qa_report.md` for the outcome.

### Decide and fix

Run `/sdd:qa_fix` when QA leaves `(user)` items in `todo.md`: a bug that turns on a decision, a fix
that failed, a file to keep or delete. It researches each item, asks you for one decision at a
time with a recommendation, then makes the fixes test-first, runs the full tier, ticks what it
closed and commits. An item you answer "Leave for later" stays unticked. A decision about how a
page looks, behaves or reads goes through `sdd:capture-feedback` on the way. A fix that changes
what a page shows counts as fixed only once a screenshot shows it; the screenshots land in
`<spec-dir>/screenshots/fixed/`. A fix that changes nothing on screen is proven by its test alone.

Feedback you give on the QA report, a screenshot or a page goes through `sdd:capture-feedback`
(`/sdd:capture_feedback` by hand) before the fix, so the rule lands in one of the files `## Rule
Files` in `.claude/sdd/config.md` names. It also rewrites the passages of the spec, plan and QA
plan that the feedback overrides. The next QA run reads those documents as the current design, so
it passes the changed page instead of flagging it or fixing it back.

## Step 5: Document

Run `/sdd:document`. It reads `## Documentation Hooks` in `.claude/sdd/config.md` and invokes each listed skill in order, committing per hook. A project that lists no hooks skips that part. It then executes the documentation items in `todo.md` and opens the pull request.

## Step 6: Pull request

1. `/sdd:document` opens the pull request itself; run `/sdd:make_pr_quickly` to open it on its own. It runs `gh pr create --head <branch> --base main --title <branch> --body ""`, falling back to `gh pr view` when the pull request exists; it reads nothing else.
2. Run `/sdd:address_pr_review` to work through review feedback. It fetches the comments through the `Fetch PR comments` script under `## PR Hooks` in `.claude/sdd/config.md`, or with `gh` directly when that key is blank.

## Step 7: Cleanup

Once the PR is approved (or already merged), run `/sdd:finish_worktree`. It rebases, archives the spec and its roadmap row, lands the close-out on `main` by fast-forward push and brings the main worktree up to date. It stops, changing nothing on `main`, if the main worktree has uncommitted work or an operation in progress. Nobody runs `git merge` in the main worktree by hand. Then remove the worktree and delete the branch.

`/sdd:commit_quickly` is the fast commit path for use during implementation: it stages the already-staged index if there is one, otherwise the files Claude touched this conversation (`mine`; `all` stages everything), and commits without running the test suite. When the commit is a checkpoint you have not verified, use a commit command that runs the targeted test tier first, if the project has one.

## Registering a design

1. The design is a Design Artifact in Claude: an Artifact made from the Design Artifact type, at a `claude.ai/artifact/<id>` link. Its owner moves a design still in standalone Claude Design into Claude before 14 December 2026. A project that cannot move is redrawn in Claude.
2. The person running the command can edit the design: they own it, or the owner shared it with edit access. A design shared for viewing only reads back as a summary, and the command stops.
3. Copy the design's link. A handoff prompt Claude generates for the design also works if it contains that link.
4. Either paste the link into `<spec-dir>/design_prompt.md` before `/sdd:start`, which registers it while it sets up the worktree, or run `/sdd:register_design <link> [notes]` on the feature branch.
5. Check the report: the canvas title, version, artboards, synced files and assets, any missing asset, the screenshots.
6. After the design changes in Claude, register it again. The same command re-syncs `design_source/` and rewrites `design.md`.

---

## How the workflow runs

2. **Model tiering & the override knob.** Defaults: mechanical work (test runs, commits, file moves, todo ticking) → the `sdd:sdd-mechanic` agent (Haiku); non-interactive fan-out (research topics, review dimensions, scans) → the `sdd:sdd-worker` agent (Sonnet); interactive authoring/review commands run at depth 0 on the **user's session model** (so run the session on a strong model). To change a step's model, **edit the agent file's `model:` frontmatter** (`claude_plugins/sdd/agents/sdd-mechanic.md`, `sdd-worker.md`). The env var `CLAUDE_CODE_SUBAGENT_MODEL` forces one model for **all** subagents, but it **overrides every per-agent `model:` frontmatter**, so leave it **unset (or `inherit`)** for normal tiered operation.

3. **Aliases vs pinned IDs.** The agents use aliases (`haiku`/`sonnet`). For frozen, reproducible automation, pin dated IDs (e.g. `claude-haiku-4-5`) in the agent files instead.

4. **Target Claude Code version.** These files target the **2.1.x** line: per-agent/per-command `model:` frontmatter, `AskUserQuestion`, non-nesting subagents, and "commands merged into skills" all hold here. No runtime version check enforces it.

5. **Every artifact command commits and pushes itself.** Any command that writes or edits an SDD artifact ends by delegating a commit and push to `sdd:sdd-mechanic`, following `claude_plugins/sdd/resources/commit_and_push.md`. A command run in hook mode keeps its commit; `/sdd:document` commits for a hook that has no commit step. The commit subject always leads with the spec directory name, so `git log` reads as a per-spec history. Nothing is committed on `main`/`master`, and nothing unrelated is staged. The one exception is `spec_dd/` bookkeeping that has no worktree yet (`/sdd:start`'s move to in progress, `/sdd:roadmap`'s edits): that is committed on `main` and not pushed.

6. **Why it runs this way.** The **`claude-code-authoring`** skill is the canonical reference for the mechanics behind all of the above: no subagent nesting or fan-out, no slash commands from subagents, no `AskUserQuestion` in subagents, model tiering, and file-based hand-off.

---

## The `todo.md` checklist

`/sdd:start` creates a `todo.md` checklist in the spec directory that tracks every step above, in five sections. Commands tick their own item (and add follow-up tasks where relevant) by invoking the protected helper at `claude_plugins/sdd/commands/protected/update_todo.md` as their final step; you never run it yourself. Commands tick their own item, including `/sdd:make_pr_quickly` through `/sdd:document`; the human ticks the `(user)` items. The commit-and-push step runs straight after it.
