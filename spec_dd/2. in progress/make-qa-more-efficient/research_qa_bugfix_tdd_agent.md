# Research: Automated QA → TDD Fixer → Re-verify Loop

## Intro

The SDD README marks "Command for reacting to QA-reported bugs" as a TODO. Currently `do_qa`
writes bugs into `qa_report.md` and adds todo items for a human to fix later (Step 11). The idea
is to close that gap: QA finds a bug, hands it to a fixer agent that writes a failing test then
fixes the code, then QA re-verifies — all within the same SDD run. This document evaluates how
to design that loop within the hard constraints of this project (depth-0-only fan-out, no MCP at
depth 1, TDD mandatory for every bugfix, security guard hook, pre-commit hooks running
ruff+mypy+pytest).

---

## 1. Triage: Which Bugs to Auto-Fix vs. Defer

### The Core Question

The idea says "make good decisions about what bugs to fix." In agentic systems, the established
rule of thumb is: automate triage aggressively, automate remediation cautiously. The blast radius
and reversibility of a fix determine the boundary. A bug fix in a feature branch that can be
reverted in one commit is lower-risk than a fix that touches shared infrastructure or requires a
product decision.

### Proposed Triage Rubric

**Auto-fix (green lane — fixer agent proceeds immediately):**

All five conditions must hold:

1. The failing test is clearly attributable to the feature under test (not a pre-existing failure
   in an unrelated area).
2. The bug is a functional regression — a thing that should work does not work — rather than a
   missing feature, a UX preference, or a design question.
3. The root cause is localised to one app / one module. The fix does not require touching multiple
   apps or changing shared base classes, middleware, or settings.
4. No product/UX decision is required to define the correct behaviour. The correct outcome is
   unambiguous from the spec/plan or the test plan.
5. A pytest-level test can reproduce it — the failure is observable without a browser.
   (Bugs that are visible only via HTMX partial swap timing, JavaScript animation, or a race
   condition in Playwright are harder to pin in a unit test; they do not clear condition 5.)

**Defer to human (red lane — add to todo and stop):**

- Bug requires a product decision ("should this redirect or show an error message?")
- Root cause spans multiple apps (blast radius: changing one breaks another)
- The fix requires a migration (schema change — risk of data loss on revert)
- The failure is visible only in the browser and cannot be reproduced by pytest alone
- The failing test was already failing before this branch (pre-existing failure — do not mask)
- The QA worker observed a security-adjacent problem (auth bypass, data exposure) — escalate
  to a human immediately, do not auto-patch
- Ambiguous error: the exception type is broad (e.g. bare `Exception`) or the stack trace lands
  in a third-party library

### The "Obvious Root Cause" Heuristic

Following the project memory note on "dumb TODOs": if the fix is obvious (wrong URL name, off-by-one
in a queryset annotation, missing `select_related` causing AttributeError), just fix it. Do not
add a "decide how to handle X" TODO. If it is not obvious within 30 seconds of reading the
traceback, it is deferred.

---

## 2. Fixer Agent Design

### New Spawnable Agent vs. New Command vs. Inline

**Option A — inline at depth 0 (depth-0 QA does the fix itself):**
Possible, but conflates QA and bugfix concerns. The QA agent runs on the session model (strong
model, expensive); keeping fix work there wastes tokens. It also breaks the single-responsibility
shape of the SDD workflow. Rejected.

**Option B — new `/fix_qa_bug` command (read-and-follow inline):**
A command read inline keeps the caller's model (the session model) — per the `claude-code-authoring`
skill, model frontmatter on inline-executed files is inert. The command would also need Bash
(to run pytest), Edit/Write (to write test + fix), and Git (to commit). That is a large tool
surface to grant the depth-0 QA session. More importantly, a command is the wrong abstraction
here: the operation is a discrete spawnable unit, not an interactive step.

**Option C — new `fls:qa-bugfixer` spawnable agent (recommended):**
Spawned from depth-0 `do_qa`. Gets its own model tier. Has Bash, Edit, Write, Read, Glob, Grep.
Runs non-interactively, reports via a structured output file. This fits the existing agent pattern
(mechanic + worker) cleanly.

### Recommended Agent Shape

```
name: qa-bugfixer
model: sonnet        # needs judgment to write a good test; haiku is too weak
tools: Bash, Read, Edit, Write, Glob, Grep
effort: normal
```

The agent is NOT opus because the work is bounded and mechanical enough once triage has already
approved it. Sonnet can write a correct pytest test and a minimal fix. If the fix turns out to
require design judgment the agent returns `status: blocked` — it does not guess.

The agent receives in its spawn prompt:
- The bug title and description (from `qa_report.md`)
- The test plan step that failed
- The specific error / traceback observed by Playwright
- The path to the spec/plan for context
- The path to write its fix report to (e.g. `.sdd-work/bugfix_<slug>.md`)

### What the Fixer Does (TDD Sequence)

1. Read the traceback / error description. Identify the failing code path.
2. Locate the relevant test file (follow `freedom_ls/<app>/tests/test_<module>.py` convention).
3. Write a **failing test** that reproduces the bug. Run `uv run pytest <path/to/test>` and
   confirm it is RED. If the test passes immediately, the bug is not reproducible at unit level —
   return `status: blocked` with reason.
4. Implement the minimal fix. Re-run the specific test to confirm it turns GREEN.
5. Run the full suite: `uv run pytest` (or `uv run pytest -n auto` for speed). If this breaks
   other tests, revert the fix and return `status: failed` with the broken test names.
6. Commit with `uv run git commit -m "fix(<app>): <title> (TDD)"`. Pre-commit hook (ruff+mypy+pytest)
   runs automatically; if it fails the commit is rejected and the agent returns `status: failed`.
7. Write the fix report to the given path.

### Fix Report Contract

The output file at `.sdd-work/bugfix_<slug>.md` contains:

```
## Bug: <title>
status: ok | failed | blocked
reason: <one line>

### Failing test written
<file path and test function name>

### Root cause
<one paragraph>

### Fix
<file path(s) changed, what changed>

### Commit
<commit hash or "not committed">

### Suite result
PASS (<N> tests) | FAIL (see below)

### Failed tests (if any)
<list>
```

This structured artifact is what depth-0 QA reads to decide whether to proceed with
Playwright re-verification.

---

## 3. The Re-Verify Loop

### Two-Layer Verification

After the fixer reports `status: ok`:

**Layer 1 — pytest suite (cheap, run first):**
The fixer already ran this. Depth-0 QA reads the suite result from the fix report. If the fixer
reports PASS, layer 1 is already done — no need to re-run it at depth 0.

**Layer 2 — Playwright re-verification of the specific flow (depth 0 only, because MCP is
depth-0-only):**
Depth-0 QA re-navigates the exact test step that originally failed. This is focused: navigate
to the relevant URL, perform the specific action, check the specific outcome. It does NOT re-run
the full QA plan — that would cost as much as the original run.

Also guard against regressions in adjacent flows: if the fix touched a shared view or model,
re-check one related flow (e.g. if the student progress view was fixed, also spot-check the
educator progress view). Keep this to at most 2–3 spot-checks, not the full plan.

### Loop Guard

Bugs that fail the first fix attempt are NOT automatically retried. Autonomous repair systems
that loop freely are a known failure mode — they can regress other code, waste tokens, and produce
worse fixes on each attempt. The loop guard is:

- **Max 1 fix attempt per bug per QA run.** If the fixer returns `status: failed` or the
  Playwright re-check still fails, depth-0 QA records the bug as UNRESOLVED in `qa_report.md`
  and adds the original todo item (TDD fix for a human).
- Rationale: the fixer has access to the same information a human would have on a first look.
  If it failed, a second attempt with the same information is unlikely to succeed and may make
  things worse. Escalate.

### If the Fix Breaks Other Tests

The fixer's Step 6 runs the full suite before committing. If that run fails, the fixer does NOT
commit. It reverts its file changes with `git checkout -- .` (or the safe Edit equivalent),
writes `status: failed` with the broken test list, and returns. Depth-0 QA then adds the bug
to the todo for human resolution.

Important: do NOT use `git reset --hard` without explaining first (per memory note on destructive
git ops). `git checkout -- <changed files>` is the safe revert pattern.

---

## 4. Orchestration Shape Under Depth-0/No-Nesting

### The Constraint

Playwright MCP is only available at depth 0. The fixer agent is at depth 1 and cannot use it.
The fixer therefore works entirely with pytest + code changes. Re-verification of the browser
flow must return to depth 0.

### The Honest Control-Flow Sketch

```
depth-0: do_qa (Playwright MCP available)
  |
  +-- Steps 1-9: run test plan, collect qa_report.md
  |
  +-- Step 9.5: For each bug in qa_report.md:
  |     +-- Triage (inline at depth 0, takes ~5 seconds):
  |           +-- GREEN lane --> spawn fls:qa-bugfixer (depth 1)
  |           |     +-- write failing test (RED)
  |           |     +-- implement fix (GREEN)
  |           |     +-- run full pytest suite
  |           |     +-- uv run git commit (pre-commit hook fires)
  |           |     +-- write .sdd-work/bugfix_<slug>.md (status: ok|failed|blocked)
  |           +-- RED lane --> record as UNRESOLVED, add todo
  |
  +-- Step 9.6: For each bug where fixer returned status: ok:
  |     +-- Read fix report, confirm suite PASS
  |     +-- Playwright re-verification of the specific flow (depth 0)
  |           +-- PASS --> mark bug as FIXED in qa_report.md
  |           +-- FAIL --> mark bug as UNRESOLVED, add todo (no retry)
  |
  +-- Step 10: Kill dev server
  |
  +-- Step 11: Update todo.md
        - Tick QA step
        - Add todos only for UNRESOLVED bugs
        - For FIXED bugs: note "auto-fixed by fixer agent, commit <hash>"
```

### Should This Live Inside `do_qa` or a Separate Command?

**Inside `do_qa` (recommended):** The loop is a natural extension of Steps 9–11. The entire
QA → fix → re-verify cycle happens in one `do_qa` invocation. The user gets a fully resolved
`qa_report.md` (bugs either FIXED or UNRESOLVED with todos) at the end. This matches the
workflow's "each step produces a complete artifact that feeds the next" philosophy.

**Separate `/fix_qa_bugs` command (alternative):** A human reviews `qa_report.md` first, then
runs `/fix_qa_bugs`. This adds a review gate — good for high-stakes changes, but defeats the
efficiency goal for simple regressions. This is better suited to a future refinement: a
`--manual-fix-review` flag on `do_qa` that pauses after collecting the report.

For the initial implementation, the loop inside `do_qa` is the right default. It is consistent
with how `fls:qa-data-helper` is already spawned mid-run to unblock missing data — the fixer
agent is the same pattern applied to bugs.

---

## 5. Concrete Recommendations for FLS

**What to build:**

- New spawnable agent file: `fls-claude-plugin/agents/qa-bugfixer.md`
  (model: sonnet, tools: Bash, Read, Edit, Write, Glob, Grep, skills: unit-tests).
- Extend `do_qa.md` with two new steps (9.5 and 9.6) between the current Step 9 (report) and
  Step 10 (kill server): triage loop + spawn fixer per green-lane bug + Playwright re-check +
  update report with FIXED/UNRESOLVED status.
- Update Step 11 (todo update) to only add todos for UNRESOLVED bugs, and to note auto-fixes
  with commit hashes.

**Triage rules (encode directly in `do_qa.md` Step 9.5):**
  Green if: regression in tested feature + unit-testable + root cause in one app + no product
  decision + no schema change + not security-adjacent.
  Red if: any of those conditions fails.

**Fix report contract:**
  `.sdd-work/bugfix_<slug>.md` with status/reason/test-written/root-cause/fix/commit/suite-result.
  The slug is the kebab-case bug title from `qa_report.md`. The orchestrator reads status and
  suite-result to decide whether to proceed to Playwright re-check.

**Loop guard:**
  Max 1 attempt per bug. On fixer failure or Playwright re-check failure: escalate to todo.
  No second attempt. Clean up `.sdd-work/` only on fully successful runs.

**Re-verification scope:**
  Re-drive the specific failing Playwright flow + at most 2–3 adjacent spot-checks. Do not
  re-run the full test plan.

**Model choice:**
  Fixer agent: sonnet (needs judgment for test authorship and root-cause analysis). Triage
  decision: inline at depth 0 (session model). Mechanic-level chores (tick todo): sdd-mechanic
  (haiku). This keeps cost proportional to task complexity.

**Pre-commit hook interaction:**
  The fixer's commit triggers ruff+mypy+pytest automatically. If the hook rejects the commit,
  the fixer treats it as `status: failed` and reverts its changes. Do not suppress the hook.

**Security guard interaction:**
  The existing hook blocks dangerous patterns in source code. The fixer agent's instructions
  must state: "If your fix would require bypassing security-sensitive ORM patterns or unsafe
  template rendering, return status: blocked for human review." The guard operates at the code
  level; the fixer's instructions operate at the agent level. Both layers are needed.

---

## References

- [LLM-based Agents for Automated Bug Fixing: How Far Are We? (arXiv 2411.10213)](https://arxiv.org/html/2411.10213v2)
- [TDFlow: Agentic Workflows for Test Driven Software Engineering (arXiv 2510.23761)](https://arxiv.org/html/2510.23761v1)
- [RepairAgent: An Autonomous, LLM-Based Agent for Program Repair (arXiv 2403.17134)](https://arxiv.org/pdf/2403.17134)
- [LLMLOOP: Improving LLM-Generated Code and Tests through Automated Iterative Feedback Loops (arXiv 2603.23613)](https://arxiv.org/pdf/2603.23613)
- [Agentic Program Repair from Test Failures at Scale (arXiv 2507.18755)](https://arxiv.org/pdf/2507.18755)
- [When Should a DevOps Agent Act Without Human Approval? (DevOps.com)](https://devops.com/when-should-a-devops-agent-act-without-human-approval/)
- [What is autonomous remediation? (Firetiger)](https://www.firetiger.com/learning/ai-agents-for-operations/what-is-autonomous-remediation)
- [Building Self-Healing CI/CD Pipelines for Agentic AI Systems (Optimum Partners)](https://optimumpartners.com/insight/how-to-architect-self-healing-ci/cd-for-agentic-ai/)
- [Beyond Accuracy: Behavioral Dynamics of Agentic Multi-Hunk Repair (arXiv 2511.11012)](https://arxiv.org/pdf/2511.11012)

---

status: ok
reason: all five sections researched and concrete FLS recommendations written; grounded in project constraints and external literature
