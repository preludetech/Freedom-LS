# Research: ux_patterns

Scope: operator experience of a long-running, multi-repository slash command run from the FLS repo. Surface = terminal transcript, questions, files, commits. External URLs are cited from background knowledge of well-known docs and were not re-fetched this session; treat them as pointers. Local facts (roadmap exists at `spec_dd/1. next/roadmap.md`; `update_fls.md` content; `do_qa.md` Inputs) were read directly.

## 1. Preview-then-apply

**Pattern:** Terraform `plan` then `apply` (https://developer.hashicorp.com/terraform/cli/commands/plan): a diff-style summary with a one-line total ("N to add, M to change, K to destroy"), then one confirmation. `cargo upgrade --dry-run` (cargo-edit) prints a per-dependency "old -> new" table and writes nothing. Renovate's Dependency Dashboard (https://docs.renovatebot.com/key-concepts/dashboard/) lists pending updates as checkboxes the human ticks to approve, grouped by state (pending approval, rate-limited, awaiting schedule). `revdepcheck` (https://github.com/r-lib/revdepcheck) summarises "N reverse deps: X new problems, Y unchanged" before the detailed run. Good previews: one row per unit of work, risk flags as columns, a totals line, and a single confirm gate before any mutation; per-step confirmations only for steps that cannot be previewed or are irreversible (push, delete).

**Here:** `update_fls` already previews per spec (flags from `upgrade_notes.md`, "no notes" marker) then confirms. Multi-downstream makes it a matrix. Suggested preview, shown once up front:
- Rows = specs (chronological, as in Step 1 of `update_fls`); one block per downstream, or a matrix with downstreams as columns.
- Per downstream header: path, current FLS commit, branch, dirty/clean tree, `migrate --check` baseline, tests green at baseline (yes/no), N specs pending.
- Per spec columns: name, completion date, notes flags (migrations, settings, packages, npm, tailwind, template-review), "no notes", and a downstream-specific flag: "overrides N changed templates".
- Totals line: "3 downstreams x 5 specs = 15 integrations; 4 need migrations; 2 lack notes".
- Downstreams that cannot start (dirty tree, red baseline, path missing) are listed as SKIP with a reason and excluded from the confirm, not silently dropped.
- Confirm once (batched with other up-front questions, see section 4). No per-spec confirm; the stop conditions in section 3 do the per-step gating. Preview writes nothing to any downstream (`update_fls` Step 2 rule).

## 2. Progress and resumability

**Pattern:** `git rebase` keeps state in `.git/rebase-merge/` and prints "Successfully rebased" or a stop message naming the commit and the three exits `--continue / --skip / --abort` (https://git-scm.com/docs/git-rebase). Terraform state records what exists, so re-running `plan` computes only the remaining diff (idempotent by design). Ansible writes `.retry` files with failed hosts, and `--start-at-task` resumes mid-playbook. `pre-commit autoupdate` is stateless: it rewrites the config in place, so the git diff is the progress record. Common rules: (a) state derived from the real world beats a separate counter; (b) every stop message tells the operator the exact command to resume; (c) the tool tolerates the operator having fixed something by hand.

**Here:** Derive progress from truth, not a counter. Each downstream's position is its submodule pointer plus the `Update FLS: <spec>` commits (already the unit of "last good" in `update_fls` Rollback). Re-running the command recomputes the pending list from `git fetch` and skips anything already integrated, so resume is just "run it again". Add a thin manifest for what git cannot say: per-downstream status per spec (`done / blocked-on-FLS-fix / blocked-on-spec <name> / skipped`). Fit existing patterns: the downstream list lives as a tracked config file (`.claude/fls-dev/config.md` is the existing per-project config channel, so the plugin stays generic); per-downstream worker returns use `.sdd-work/` files with a `status:` footer (a missing footer = incomplete = re-run, per the worker contract); `todo.md` in the spec dir is the human-readable manifest of the run (one checkbox per downstream x spec); `integration_report.md` is the durable result. After a manual fix the operator re-runs; the command re-verifies the downstream's tree/tests rather than trusting any marker. A blocked downstream is parked, not abandoned, with the line "to resume: fix X, then re-run `/update_downstreams`".

## 3. Stop conditions and escalation

**Pattern:** Google's Large-Scale Changes (Software Engineering at Google, ch. 22, https://abseil.io/resources/swe-book/html/ch22.html) shards a change, tests each shard, and reverts/skips shards that fail rather than blocking the rest. Renovate holds risky updates with `minimumReleaseAge` ("stability days", https://docs.renovatebot.com/configuration-options/#minimumreleaseage) and `dependencyDashboardApproval`. `revdepcheck` records every new failure in `revdep/problems.md` and `failures.md` with the check output, for the maintainer to triage (CRAN submissions also require contacting the downstream maintainers). Rule of thumb: stop on anything that makes later results untrustworthy (red baseline, failed migration, corrupt state); carry on past anything isolated to one target.

**Here:**
- Hard stop for the whole run: FLS bug found. Per the idea, fix FLS before the next spec. A downstream failure may be (a) FLS bug, (b) downstream workaround/override drift, (c) environment. Classify it before fixing.
- Triage: small fix (one file, obvious, existing test can cover it, ~under 30 lines) -> fix in FLS now, add a regression test, commit, re-run the spec in that downstream. Larger -> write a new spec idea in `spec_dd/1. next/`, mark the spec x downstream cell `blocked-on-spec`, and carry on with the *other* downstreams that do not hit it. Ask the operator only when the size call is borderline (recommended option first).
- Isolated stop (carry on with other downstreams): dirty tree, red baseline, unreconciled template override flagged for human review.
- Capture at every stop (so the decision takes seconds): downstream name and path; spec name and FLS commit; step that failed (pre-flight, uv sync, settings, migrate, check, tests, QA); failing test node IDs or command and last ~30 lines of output; `git diff --stat` of the in-progress integration; classification guess (FLS bug / override drift / env) with reasoning; suggested next action and size estimate; the exact resume line. After a stop, roll back the downstream to its last good commit (existing Rollback section) so a parked downstream is never left half-migrated.

## 4. Asking the right questions

**Pattern:** House rule (`claude-code-authoring` SKILL, `fanout_recipe.md`): `AskUserQuestion` only at depth 0, batched at most 4, recommended option first, unasked decisions recorded as assumed defaults. Elsewhere: Renovate/Dependabot ask nothing in-band and surface choices as PR comments and dashboard checkboxes; PR templates (GitHub `PULL_REQUEST_TEMPLATE`) and RFC templates (Rust RFCs https://github.com/rust-lang/rfcs/blob/master/0000-template.md; Python PEPs) make a proposal decidable with fixed sections: Summary, Motivation, Detailed design, Drawbacks, Alternatives, Unresolved questions.

**Here:** Ask once up front (batch 1): which downstreams (default all listed), confirm the preview, stop-on-first-FLS-bug vs park-and-continue (recommended: park and continue with other downstreams), push policy. Mid-run questions only for decisions that need the evidence found (small-vs-large fix; pull-upstream proposals). Everything not asked is written to the report under "Assumed defaults". Pull-upstream proposal card, <=10 lines, one per candidate, batched up to 4 per question round, otherwise queued to the end of the downstream so it does not interrupt the integration:
- What: one sentence of behaviour.
- Where: downstream file paths and the FLS app it would join.
- Evidence of generality: not brand/domain-specific; would another downstream or the demo content use it; does FLS already have a near-duplicate.
- Cost: estimated size (S/M/L), migrations, whether downstream must delete its copy afterwards.
- Options: (recommended) "make a spec idea", "not general, keep downstream", "ask me later (record in report)".
Declining is recorded so it is not re-asked next run (a list of declined candidates in the report/config).

## 5. Reports

**Pattern:** `revdep/README.md` (summary: platform, packages checked, counts) + `problems.md` (only new problems, with output) + `failures.md`/`cran.md`. Renovate dashboard: a single living issue, sections by state. Dependabot PR body: what changed, release notes, compatibility. Crater (https://github.com/rust-lang/crater) reports a table bucketed regressed / fixed / unchanged / spurious-failure with log links, regressions first. Lessons: lead with the verdict and counts; put the actionable items first; bury unchanged/passing detail; link to evidence rather than inlining it; separate "new" from "pre-existing" failures.

**Here:** One `integration_report.md` per downstream per run, plus a short run-level index in the spec dir. See Report skeleton below.

## 6. Interplay with SDD artefacts

**Pattern:** `do_qa` writes `qa_report.md` and `screenshots/` into the *spec dir that holds the test plan* (`do_qa.md` Inputs: "`qa_report.md` and `screenshots/` are written there"). `spec_dd/1. next/roadmap.md` exists and tracks upcoming work; ideas live in `spec_dd/1. next/`.

**Here:** Do not reuse the completed spec's dir (`3. done/<spec>/`): that would overwrite or confuse the FLS-side `qa_report.md`, and done dirs should stay immutable. Put downstream QA under this feature's own spec dir (the one that implements `update_concrete_project_improvements`, or, for each run, a run dir): `.../integration/<run-date>/<downstream>/<spec-name>/{qa_report.md, screenshots/}` with the summary `integration_report.md` at `<downstream>/`. That makes the collision-free key (run, downstream, spec) and keeps `do_qa`'s "spec-dir" semantic by passing that leaf dir as the spec-dir. Caveat: `do_qa` finds its test plan from the in-progress spec; for downstream QA the adapted plan (idea: "the QA plan might need to be adapted") should be copied/derived into the leaf dir as `test_plan.md` so `do_qa` is invoked with an explicit path. Any spec created for a large fix is a normal idea in `spec_dd/1. next/`; add it to `roadmap.md` only if the operator agrees (record as assumed default otherwise). Note: per CLAUDE.md the generic `sdd` plugin must not hardcode FLS paths; the base location comes from config. Downstream repos should receive only code commits (`Update FLS: <spec>`), not reports.

## 7. Multi-target feedback

**Pattern:** Crater and revdepcheck are breadth-first per change: one candidate change is run against all targets, so a regression is seen across the whole ecosystem quickly and counted ("regressed in 12 of 3000"). Depth-first (all changes into one target) gives a clean per-target story and a committable history, and is what `update_fls` does.

**Here:** Trade-off: an upstream bug is confirmed faster, and its blast radius known, by breadth-first (spec 1 into A and B, then spec 2). Per-downstream git history is identical either way, since commits are per downstream. Breadth-first costs more context switching (multiple dev servers/DBs) and a bug fix in FLS must be re-verified on every downstream already past that spec. Recommendation: breadth-first by spec, with the matrix as the work unit and one worker per cell, because (a) an FLS fix is made once and benefits all downstreams before they diverge further, (b) repeated failure across downstreams distinguishes FLS bugs from local drift, a strong triage signal. A downstream blocked on a spec is parked for the remaining specs (later specs may depend on it); other downstreams continue. Operator option: `--depth-first` as a non-default if one downstream is the priority (first one listed is integrated first either way).

## Proposed operator flow

1. Operator runs the command in FLS. It reads the downstream list from project config, fetches each, and computes pending specs per downstream.
2. Preflight table (section 1): per-downstream status, SKIP reasons, matrix of specs x flags, totals line. Nothing written.
3. One batched question (<=4): downstreams to include, confirm plan, park-vs-stop policy, push policy; recommended first. Unasked choices noted as assumed defaults.
4. Spec dir gets `todo.md` (matrix checklist) and `integration/<run>/` skeleton.
5. For spec 1, one worker per downstream integrates it (pointer, sync, flagged steps, check, tests, commit) and returns a `status:` file; transcript shows one line per cell: `A spec-1 ok`, `B spec-1 FAILED tests`.
6. Browser QA for specs with front-end changes, using an adapted plan; `qa_report.md` and screenshots land in the leaf dir.
7. On failure: the tool classifies and shows the stop card (failing test, diff stat, spec, downstream, guess), rolls back that downstream.
8. Small FLS fix: tool fixes it in FLS with a regression test, commits, retries the cell. Large: writes an idea in `spec_dd/1. next/`, marks the cell blocked-on-spec, continues other downstreams.
9. Repeat for each spec; the transcript ends each round with the matrix redrawn.
10. Pull-upstream candidates spotted (downstream-only code that looks general) are queued and asked together at the end of the round, as proposal cards.
11. Final sync and test gate per downstream; push only clean downstreams (existing Step 5 rules).
12. Operator sees the final matrix, the list of new specs, accepted/declined upstream candidates, and the report paths; next morning they read `integration_report.md`.
13. After hand-fixing a parked downstream, they re-run the command; progress is recomputed from the git state and only remaining cells run.

## Report skeleton

`integration_report.md` (one per downstream per run; a run index lists them with one verdict line each):

1. `# Integration report: <downstream> (<run date>)`
2. Verdict and counts: integrated N/M, blocked K, FLS fixes made, new specs, pushed yes/no. Resume line if not complete.
3. Needs your attention (first): blocked cells with stop cards, flagged template overrides, pending upstream proposals.
4. Spec matrix: spec, FLS commit, flags, result (integrated / blocked-on-fix / blocked-on-spec / skipped), downstream commit, test counts, QA result link.
5. Regressions vs fixed vs unchanged (Crater-style): tests newly failing, newly passing, pre-existing failures at baseline.
6. FLS-side changes made during this run: commit, why, regression test, which downstreams re-verified.
7. New specs created (path, size, which downstream blocks on it).
8. Upstream candidates: proposed, accepted, declined (with the proposal card text).
9. Workarounds found in the downstream that can now be removed (the pain point in the idea).
10. Assumed defaults (decisions not asked).
11. Baseline and environment: starting/ending FLS commit, tool versions, baseline test status, commands run.
12. Evidence links: QA reports, screenshots, test logs.

status: ok · reason: research complete; external URLs from background knowledge, not re-fetched
