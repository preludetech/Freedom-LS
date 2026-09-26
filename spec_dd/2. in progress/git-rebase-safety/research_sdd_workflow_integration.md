# Where "rebase on main" fits in the SDD workflow

## 1. The worktree/branch model

`/sdd:start` creates the branch/worktree in three steps, only the last of which touches a new
branch:

- `commands/protected/move_spec_to_in_progress.md` moves the spec directory into
  `spec_dd/2. in progress/` and commits that move **on the current branch** (usually `main`),
  *before* any worktree exists — "This guarantees the move lands on the current branch … rather
  than on the feature branch."
- `commands/protected/start_worktree.md` then creates the worktree from the bare-repo parent
  (`cd .. && git worktree add <spec-folder-name>`), branching off that just-committed, clean
  `main`. This is the one point a feature branch is forked from `main`.

Everything from here on — `spec_from_idea`, `spec_review`, `plan_from_spec`, `implement_plan`,
`do_qa`, `address_pr_review`, `make_pr_quickly` — runs inside that worktree, on the feature branch.
This is the range where rebasing onto `main` makes sense: the branch can drift from `main` for the
whole lifetime of the spec (`spec_dd/2. in progress/` can sit there for days), and every one of
these steps is dispatched by `/sdd:next` as a `(cmd)` item once `todo.md` exists.

Two points run **on `main`, not on a feature branch**, where rebasing is meaningless or wrong:

- `/sdd:start` itself (before `todo.md` exists — `next.md` Step 1 falls through to it).
- `/sdd:roadmap` (edits `spec_dd/1. next/roadmap.md` directly on whatever branch is current,
  typically `main`).

`/sdd:finish_worktree` runs at the *end*, still on the feature branch, after the PR has been
merged (`todo.md` section 13 "Merge the PR once approved" precedes section 14
"Run `/sdd:finish_worktree`"). Its `git rebase main` (Step 1) is a local rebase — no `git fetch` —
so it depends on the user's local `main` already having the merge. Its purpose reads as tidy-up
(landing the spec-directory move cleanly, resolving `roadmap.md` conflicts when two specs finish
close together) rather than as a mid-implementation safety net.

Push points: nothing is pushed until `/sdd:make_pr_quickly`'s `git push -u origin HEAD`. Everything
before that (`plan_from_spec`, `implement_plan`, etc.) commits locally via
`claude_plugins/sdd/resources/commit_and_push.md` but the worktree isn't pushed until the PR is
opened, and again pushed (force, with confirmation) if `/ds:rebase_main` is run mid-flight.

## 2. Every existing place that already fetches/rebases/merges main

- **`claude_plugins/sdd/commands/finish_worktree.md`, Step 1**:
  ```
  git rebase main
  ```
  No fetch — assumes local `main` is current. "Fix any merge conflicts (this may need judgement —
  keep it on the main thread). A conflict in `spec_dd/1. next/roadmap.md` means two specs finished
  close together: it is one row per spec, so keep both sides' removals and status changes." Runs
  once, at worktree cleanup, after the PR merged.

- **`claude_plugins/django-stack/commands/rebase_main.md`** (`/ds:rebase_main`) — a complete,
  generic, standalone rebase command, already built to the shape the idea asks for minus the
  frontend check and the judgment step:
  ```
  git fetch origin main
  git rebase origin/main
  ```
  followed by autonomous conflict resolution ("Only ask the user if a conflict is genuinely
  ambiguous"), `uv run pytest -x -q` until green, `uv run pre-commit run --all-files` until clean,
  a summary, then `git push --force-with-lease` only after asking. This is the only existing place
  that both fetches `origin/main` and gates on tests before continuing. Nothing currently calls it
  automatically from `/sdd:next` or any SDD command.

- **`claude_plugins/fls-dev/commands/concrete/update_fls.md`** — a different scenario entirely: a
  *downstream* concrete project pulling completed specs out of the FLS submodule
  (`cd submodules/Freedom-LS && git fetch origin main`, later `git checkout origin/main`). This is
  submodule-pointer advancement, not worktree-branch rebasing, and not relevant to this idea beyond
  showing another place `origin/main` is fetched.

- **`claude_plugins/django-stack/commands/periodic/dependabot_prs.md`** — mentions rebase only as
  an action to take on *someone else's* PR (`gh pr comment <number> --body "@dependabot rebase"`)
  when it has conflicts. Unrelated to this project's own feature branches.

No command currently rebases automatically before running an SDD step. `/ds:rebase_main` exists
but is invoked manually.

## 3. Where a rebase step would hook in

`/sdd:next` (`claude_plugins/sdd/commands/next.md`) is the only choke point every `(cmd)` item
passes through: Step 1 already resolves which spec directory and branch we're on (matching branch
name against `spec_dd/2. in progress/`), and Step 3 dispatches exactly one `(cmd)` item per
invocation via the keep-prefix map (`sdd` / `fls-dev` / `ds`). Hooking a rebase check in here, right
before Step 3 acts, covers `implement_plan`, `plan_from_spec`, `do_qa`, `address_pr_review`,
`make_pr_quickly` uniformly without touching each command file — one call to the mechanics command
(reusing or extending `/ds:rebase_main`) guarded by "only if Step 1 resolved a feature-branch spec
directory, not when we fell through to `/sdd:start` or are on `main`/`master`." This matches
`implement_plan.md`'s existing "Branch Safety" rule ("Never start implementation on main/master
branch without explicit user consent") and reuses machinery `next.md` already has (`Bash`, and the
branch/spec resolution from Step 1).

The alternative of putting the rebase in *each* command file duplicates the same git mechanics
across `implement_plan.md`, `plan_from_spec.md`, `do_qa.md`, etc., and fights the project's own
DRY convention ("Avoid repeating code" — `CLAUDE.md`). It would also mean the rebase runs
differently depending on whether a command is invoked directly by a human or read-and-followed
inline by `/sdd:next` (the "Inline-execution note" in `next.md`: a command's own frontmatter is
inert when it is inlined, so its steps run under `next.md`'s grants regardless of where the
rebase call textually sits) — putting it in `next.md` once sidesteps that split entirely.

Putting it only in `finish_worktree.md` (its current single home) does not address the incident
that motivated this idea: that rebase broke front-end functionality *mid-implementation*, not at
final cleanup, and by the time `finish_worktree` runs the PR is already merged.

The one real cost of hooking into `next.md`'s dispatcher is that it fires on every single
`/sdd:next` call, not once per work session — worth gating (e.g. skip the fetch+check if
`origin/main` hasn't moved since the branch's merge-base, which `git merge-base --is-ancestor
origin/main HEAD` or a cached "last rebased at commit X" marker can answer cheaply) rather than
re-running pytest/Playwright on every step.

## 4. Command vs skill vs protected helper, and plugin placement

The project's existing "callable by both Claude and a human" precedent is exactly `/ds:rebase_main`
— a plain top-level slash command, not a skill and not a `commands/protected/` helper. Per the
`claude-code-authoring` skill, skills are for auto-triggered background knowledge a command or
subagent *reads* (`git-worktree-setup`, `use-playwright`, `claude-code-authoring` itself); protected
helpers are internal-only, "not advertised as slash commands," invoked by other commands or by
`sdd:sdd-mechanic` (`update_todo.md`, `update_roadmap.md`, `start_worktree.md`). A rebase is a
multi-step action with judgment calls and git side effects, invoked directly by name by both a
human and `/sdd:next` — that shape is a command, matching `rebase_main.md`, `finish_worktree.md`,
and `do_qa.md`, all of which are commands rather than skills.

Plugin placement follows the existing generic/product split (`sdd` README: "`sdd` is not yet fully
standalone… FLS-specific steps… live in the separate `fls-dev` plugin"; `ds` README: "carries zero
product-specific domain knowledge"):

- The **generic mechanics** — fetch, rebase, autonomous conflict resolution, `pytest`,
  `pre-commit`, force-push-with-confirmation — already exist as `/ds:rebase_main` and belong in
  `ds`, since they depend on nothing but the stack (any `ds` project has `pytest` and
  `pre-commit`).
- The **judgment layer** the idea adds on top — deciding whether upstream `main` changed enough to
  warrant a short research pass, and flagging an architecture-direction change — is SDD process
  judgment, not stack mechanics or product mechanics. It belongs in `sdd`, as the layer that calls
  `/ds:rebase_main` (or reads-and-follows it) and then does the judgment call, the same way
  `finish_worktree.md` already keeps its own conflict-resolution judgment "on the main thread"
  rather than delegating it.
- The **frontend check** (Playwright) is FLS-specific: it needs `.claude/fls-dev/config.md`
  credentials and the `mcp__plugin_ds_playwright__*` server, both wired through the `fls-dev`
  overlay skills (`claude_plugins/fls-dev/skills/use-playwright/SKILL.md`, which says "Read
  `Skill(ds:use-playwright)` first… This overlay adds **only** the FreedomLS credentials-file
  path"). It belongs in `fls-dev`, following the same overlay shape as
  `claude_plugins/fls-dev/skills/git-worktree-setup/SKILL.md` ("FreedomLS-specific extension of
  the sdd:git-worktree-setup skill").

The existing config-hook idiom for exactly this kind of generic/product split is the **Worktree
Scripts** section of `.claude/sdd/config.md` (`Setup script`, `Teardown script` — read by
`start_worktree.md` and `finish_worktree.md`, left blank when a project has no such step). The same
shape — an `sdd`-owned config key naming a project-supplied script/command, blank by default — is
how a generic `sdd` rebase-safety step would reach into `fls-dev`'s Playwright check without `sdd`
depending on Playwright at all: `sdd` runs the generic rebase+test gate itself (or via `/ds:rebase_main`),
then, only if a config key is non-blank and the diff touched front-end paths, runs the configured
project check.

## 5. Reusing `/fls-dev:do_qa` for the post-rebase front-end check

`/fls-dev:do_qa` (`claude_plugins/fls-dev/commands/do_qa.md`) is the full QA-plan executor — desktop
+ mobile + tablet passes, bug triage, auto-fix via `fls-dev:qa-bugfixer`, a written `qa_report.md`
— far heavier than "a quick Playwright MCP check." Two pieces of it are exactly reusable at the
scope this idea wants, without re-running the whole command:

- **Step 2, the diff-scoping gate**, is already the rule for "was front-end functionality touched":
  it classifies `git diff main...HEAD --name-only` into `FULL` (any `templates/`, `static/`,
  `.html`, `.css`, `.js` path changed) / `ADMIN_ONLY` / `BACKEND_ONLY`. The post-rebase check can
  reuse this classification verbatim instead of re-deriving "did this touch the front end."
- **Step 6, the smoke gate**, is already the "quick Playwright MCP check": load the site home page
  and the primary affected page as the logged-in user, snapshot each, and fail on an HTTP 500/404,
  a visible traceback, or a missing critical element. This is the right granularity for a
  post-rebase sanity check — not the full desktop/mobile/tablet matrix.

`finish_worktree.md` Step 2 already establishes the judgment pattern this idea wants generalized:
"If there is a `frontend_qa.md` file… summarise any changes made, and say whether you think it
would be useful to run the frontend_qa again or not… only if you think [it] should be run, ask the
user for confirmation." A post-rebase hook can apply that same judgment at every `/sdd:next`
dispatch, not only at final cleanup: reuse the diff-scoping rule to decide *if* a frontend check is
warranted, run a smoke-gate-sized Playwright pass (not the full `do_qa` matrix) if so, and only
escalate to a full `/fls-dev:do_qa` re-run against the spec's own `3. frontend_qa.md` when the
rebase pulled in enough upstream change that the existing test plan's assumptions might no longer
hold — which is itself the "judgment call" the idea asks for.

status: ok
reason: read every file the brief named plus /ds:rebase_main and the fls-dev overlay skills it led to; answered all five questions with file-path citations
