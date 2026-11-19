# Research: reference implementations

Question: how do public spec-driven / agentic workflow tools and CI tools solve slow, repeated test runs, token-heavy instructions, unclear process docs, and rebase/merge/recovery? Findings come from the pages fetched on 2026-11-19. Where a page did not say, I mark it "not stated" instead of guessing.

## 1. Test selection and when tests run

### CI and test tools (the strongest evidence)

| Tool | Mechanism | Source |
|---|---|---|
| Nx affected | `git diff base..head` gives the changed files. The project graph maps each file to its owning project, and the set expands to dependents. In CI the recommended base is the latest successful commit on main, not "now". Lockfile or `nx.json` changes mark everything affected, which is a deliberate escape hatch. `nx graph --affected` shows why a project was selected. | https://nx.dev/docs/features/ci-features/affected |
| Turborepo | Content-hash cache. If the hash of the inputs is unchanged, the task is replayed from cache. A shallow checkout makes everything count as changed, and that is a fail-safe. | https://turborepo.dev/docs/crafting-your-repository/caching (redirect target only, not read; the shallow-clone claim comes via the Nx search summary) |
| Bazel | Hashes the inputs of each action. Unchanged inputs mean a cache hit, so the test is not re-run. This only works if the inputs are declared and hermetic. | https://bazel.build/basics/hermeticity |
| pytest-testmon | Coverage.py records which code each test executes, and that is compared against the changed code. It also tracks env vars such as `DJANGO_SETTINGS_MODULE`, the Python version and third-party package versions. The database lives in `.testmondata` and updates on each run, so it does not depend on VCS. Last-failed tests always re-run. `-k`, `-m` and explicit node ids switch off deselection. Static files and network services are not tracked. The first full run builds the DB. | https://testmon.org/ , https://pypi.org/project/pytest-testmon |
| GitHub Actions `paths-ignore` | The workflow is skipped only when all changed paths match the ignore patterns. One non-matching file runs it. Caveat: a skipped workflow leaves required checks "Pending", which blocks merge. It also always runs when the diff is huge (over 1000 commits) or the diff times out. | https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions |

Common design points across these tools:
1. The decision is a function of the diff (or input hash), not of "which step am I in".
2. There is always a fail-safe: unknown or global inputs (lockfile, settings, shallow history, huge diff) widen to everything.
3. The tool records a baseline (last green SHA, `.testmondata`, cache) so later runs compare against it.
4. The decision is explainable (`nx graph --affected`).

### Agentic workflow tools

- **Superpowers** (obra): the `using-git-worktrees` skill verifies a clean test baseline at the start, and `finishing-a-development-branch` verifies tests before offering merge / PR / keep / discard. Reviews between tasks are two-stage (spec compliance, then code quality). There is no per-task full-suite run; TDD gives per-task red/green on the new tests. https://github.com/obra/superpowers
- **Spec Kit**: one skill per stage (`constitution`, `specify`, `plan`, `tasks`, `implement`, `converge`). `converge` loops until it reports `Converged`. The bug flow ends in a verdict `verified | partial | failed`. The page does not describe test selection. https://github.com/github/spec-kit
- **Kiro**: `tasks.md` is run per task or all at once. With "run all", Kiro builds a dependency graph and runs independent tasks as parallel waves. Design docs carry a "testing strategy" section, and bugfix specs validate "nothing else breaks". https://kiro.dev/docs/specs/
- **Aider**: a user-configured `--test-cmd`, with an optional `--auto-test` after each edit. A non-zero exit means "try to fix". The command is whatever the user supplies, so it can be narrow. https://aider.chat/docs/usage/lint-test.html
- **BMAD**: scale-adaptive. Small changes skip planning, and a separate Test Architect add-on holds testing expertise. The page gave little detail. https://github.com/bmad-code-org/BMAD-METHOD
- Cline / Roo / OpenHands: not fetched. I have nothing verified to report.

## 2. Mechanisms that could be adopted (tests)

1. **Last-green SHA marker (Nx "latest successful commit" idea).** Record the SHA of the last full-suite pass (and of the last QA pass) in the spec folder, for example in `todo.md` or a small state file. Every later gate computes `git diff --name-only <marker>..HEAD` instead of re-running by habit.
2. **Path classifier with a fail-safe (paths-ignore idea).** If every changed path is under `spec_dd/`, `*.md`, docs, or `claude_plugins/**` that is not imported by tests, skip tests entirely. This directly fixes "rebase on main triggers a full run for spec-only changes". Anything unclassified, or any change to lockfile, settings, migrations, or conftest, widens to the full suite (the Nx lockfile rule). Beware the required-check "Pending" caveat if this is mirrored in CI.
3. **Rebase delta, not branch delta.** After a rebase, compare what main brought in (`<old-base>..<new-base>`) against what the branch touches. If the incoming main changes are disjoint from the branch's files and are not global inputs, run targeted tests for the intersection only. A full run is only needed on incompatible change, which matches the idea ("keep going every time main moves unless incompatible").
4. **Test-to-code selection for targeted runs.** Either pytest-testmon (`pytest --testmon`, `.testmondata` gitignored; works with Django if `DJANGO_SETTINGS_MODULE` is stable, with xdist noted as supported) or a cheap path-based mapping (app directory to its tests, e.g. `freedom_ls/<app>/tests`). Testmon is the more accurate option but adds a dependency and a first full run to build the DB, and it ignores templates and static files, so template changes need a path rule.
5. **Named checkpoints.** Full suite only at: spec baseline (optional), end of implementation (all batches merged), after the final rebase if the classifier says "code changed", and before push/PR in finish_worktree. Per-batch subagents run only the tests for the files they touched (Superpowers per-task TDD model). The answers.md decision matches this.
6. **Wave parallelism (Kiro).** Group independent plan tasks into waves and run them concurrently, with a targeted test run per task. This saves time, not tokens.
7. **Explainability.** Have each gate print "full suite skipped/required because: <rule>" so the decision is auditable (like `nx graph --affected`).
8. **Last-failed first.** Both testmon and pytest (`--lf`) re-run previous failures first, which is useful for flaky-test diagnosis loops in finish_worktree.

## 3. Keeping instruction files small

Anthropic's skill docs (https://code.claude.com/docs/en/skills) give the concrete rules:
- Three loading layers: `name` and `description` always in context, the SKILL.md body when invoked (and it stays in the conversation afterwards), and supporting files only on demand. Scripts are executed, not loaded.
- Keep SKILL.md under 500 lines and move reference material to linked files. "Every line is a recurring token cost once the skill loads. State what to do rather than narrating how or why."
- The description plus `when_to_use` is truncated at 1,536 characters, so put the key use first.
- `disable-model-invocation: true` removes a skill's description from context entirely and leaves it manual-only (`/name`). This suits rarely used, side-effecting commands such as address_pr_review (if kept) and finish steps.
- `context: fork` runs a skill in an isolated subagent with its own context, so the main context only receives the result. The skill text must be self-contained.
- CLAUDE.md is always loaded, whereas skills are lazy. Move rules that only matter in one step out of CLAUDE.md and into the step's skill.

Other tools: Spec Kit splits one skill per stage and passes state via files (`.specify/...`) rather than conversation; BMAD advertises "durable context" so decisions are not re-explained; Superpowers keeps SKILL.md as navigation and puts deep material in side files (for example testing anti-patterns, a writing-skills guide). Spec Kit also layers presets and overlays so customisation does not copy whole files.

Adoptable here:
- Audit every `claude_plugins/sdd` skill/command body against the 500-line cap, and measure each (wc -l, or approximate tokens) to find the heaviest. Move rationale and examples into reference files linked from the skill.
- Hand-off through files (spec folder artifacts), not by re-pasting plan text into every subagent prompt. Subagents are told which file to read.
- Return contract of one line per subagent (already used by this worker pattern) to keep the orchestrator context small.
- Mark rarely used commands `disable-model-invocation: true` to cut always-loaded description tokens.
- Keep human-readable prose in the diagrams/docs (not in skill bodies), so skills can stay terse without hurting human readability. This resolves the idea's "clear to read for a human but token-efficient" tension: put narrative in docs, put imperative steps in skills.

## 4. Documenting the workflow (diagrams)

- Spec Kit's README documents the flow as a command list with no diagram (the fetched page had none). https://github.com/github/spec-kit
- BMAD's README has a "delivery loop" graphic with entry points by work size (vague idea, big clear idea, small change). https://github.com/bmad-code-org/BMAD-METHOD
- Superpowers lists the seven-step sequence as a numbered list. https://github.com/obra/superpowers
- Kiro documents three phases, each with one file, and a task-wave graph. https://kiro.dev/docs/specs/

So the sector norm is a lightweight loop or sequence picture plus a per-stage artifact. The user's request for per-command draw.io diagrams with hooks and rebase call sites goes beyond what these tools do, so there is no template to copy. Suggested shape: one overview diagram (spec to finish), one per major command (implement: orchestrator reads plan, batches, subagents, targeted tests, checkpoint), and a swimlane marking where hooks fire and where the rebase workflow is called. Add a "test decision" legend on each diagram (targeted / classifier-gated / full). I did not verify GitHub's inline rendering of `.drawio.svg`; the answers.md decision assumes it works.

## 5. Rebase, merge and recovery

Findings from the tools are thin. None of the fetched agent tools documents a rebase or recovery loop. What the CI tools give is the mechanism to make the rebase loop cheap:
- Nx's "compare against the last successful base" and testmon's "database independent of VCS" both let a run resume from known-good state after history changes.
- GitHub's merge queue (`merge_group` event, `checks_requested`) re-validates a PR against the up-to-date base automatically, so humans do not babysit "main moved". https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions (merge-queue path filtering is not documented on the page I read).
- Superpowers' finish skill offers merge / PR / keep / discard rather than stopping, which is a menu of ways forward. Spec Kit's `converge` and the bug flow's `partial`/`failed` verdicts are explicit loop states with a next action.

Adoptable for finish_worktree (from the idea):
1. A fix-it-yourself ladder: each blocker maps to an automatic remedy, then to a stop only if the remedy fails. Examples: main not pushed means push main; main moved means fetch and rebase and loop; a flaky test means spawn a diagnosis subagent that fixes it on the current branch (answers.md).
2. A loop with an explicit bounded retry count, so "keep going every time main moves" cannot spin forever. A stop reason must name the failed remedy.
3. After each rebase, run the classifier from section 2 (item 3). Spec-only or disjoint changes continue straight to push. Only an incompatible change (overlapping files, global inputs, or a conflict) triggers a new test and QA run. Record the last QA SHA to decide this.
4. Convergence-style states, `done | retry | blocked(reason)`, for each gate so the orchestrator can branch without reading prose.

## 6. Candidate list for the "unused steps" audit

Only address_pr_review is known from the idea. No reference tool offers a feature to copy for the audit. A practical method: count invocations in session transcripts or git history, and mark rarely used skills `disable-model-invocation: true` before deleting them. This is a suggestion; I did not inspect `claude_plugins/sdd` in this research.

## Sources

- https://github.com/github/spec-kit
- https://github.com/obra/superpowers
- https://kiro.dev/docs/specs/
- https://github.com/bmad-code-org/BMAD-METHOD
- https://aider.chat/docs/usage/lint-test.html
- https://code.claude.com/docs/en/skills
- https://testmon.org/
- https://pypi.org/project/pytest-testmon
- https://nx.dev/docs/features/ci-features/affected
- https://bazel.build/basics/hermeticity
- https://turborepo.dev/docs/crafting-your-repository/caching
- https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions

Not covered: Cline, Roo, OpenHands (not fetched), Anthropic's official plugins repo (not fetched), Turborepo cache page content (redirect only).

status: ok
