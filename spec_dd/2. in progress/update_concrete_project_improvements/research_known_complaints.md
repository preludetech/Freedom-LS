# Research: known_complaints

Provenance note: repo findings (items 4-local, 5, 6) were read from files this session. Web findings (items 1-4) are from well-known public sources recalled from prior knowledge and **not re-fetched this session**. Treat the URLs as pointers to verify, not as quotes.

Starting point, from `idea.md`: (a) integration issues found downstream "have to be described in the concrete implementation and handed back"; (b) the downstream "ends up building a bunch of workarounds that need to get rolled back"; (c) it is "confusing and error-prone and time consuming".

## 1. Git submodule vendoring of a framework

- **Detached HEAD in the submodule; work or `git checkout <sha>` leaves it floating** — widespread (Pro Git, https://git-scm.com/book/en/v2/Git-Tools-Submodules) — **Mitigation here:** `update_fls.md` 3c/Step 4 deliberately uses `git checkout <hash>`; the spec should state detached is expected and forbid editing under `submodules/` (the downstream `CLAUDE.md` already does).
- **Forgotten `git submodule update --init`, so teammates/CI build the wrong FLS** — Pro Git, many blog posts — **Mitigation here:** rollback step 2 uses it; the new command should run it at start and end and verify `git submodule status` has no `+`/`-` prefix.
- **Pointer commits nobody understands (a bare SHA diff)** — Pro Git — **Mitigation here:** one `Update FLS: <spec-name>` commit per spec (3j); keep this, and put the FLS SHA and spec dir in the commit body.
- **Unpushed submodule commits make the pointer unresolvable for others** — Pro Git — **Mitigation here:** Step 5 already notes every pointer commit is on FLS `origin/main`. Running from upstream makes it better: the spec should check the SHA is reachable from `origin/main` before committing.
- **CI `uv sync --locked` fails because `uv.lock` drifted** — uv docs, https://docs.astral.sh/uv/concepts/projects/sync/ — **Mitigation here:** 3d runs `uv sync` and commits `uv.lock`. Add a final `uv lock --check`.
- **Lockfile churn (`uv.lock`, `package-lock.json`) buries the real change** — common PR-review complaint — **Mitigation here:** 3e mirrors npm deps by hand and commits the lock. Keep lock changes in the same per-spec commit and never run an unscoped `uv lock --upgrade` or `npm update`.
- **Template override drift (override silently stale)** — Django docs on overriding templates, https://docs.djangoproject.com/en/stable/howto/overriding-templates/ — **Mitigation here:** 3f flags overrides but does not merge. Running from upstream lets the agent show the upstream diff next to the override, and the spec must say who edits the override.
- **Migrations generated in the wrong repo** — recurring pattern when `makemigrations` runs in a project that vendors an app — **Mitigation here:** 3e/3h run `makemigrations` in the concrete project. For FLS-owned models a new migration must come from FLS, never from the downstream. The spec must require `makemigrations --check` to report no diff for FLS apps before and after.
- **Running from upstream: worse** — one agent now holds N projects' state (venvs, DBs, ports, settings modules) and each project's `CLAUDE.md` differs. **Mitigation here:** the spec should require, per target, a pre-flight that prints path, branch, HEAD, dirty status and settings module, and `cd` into the target only through absolute paths.
- **Running from upstream: better** — a bug found in integration can be fixed in FLS before the next spec instead of being round-tripped (the idea's core point). **Mitigation here:** the spec should fix FLS first, then re-run the failed spec's integration from the clean last-good commit.

## 2. Upstream-driven downstream testing (revdepcheck, crater, ecosystem CI)

- **Pre-existing downstream failures blamed on the change** — Rust crater triage, https://github.com/rust-lang/crater and https://forge.rust-lang.org/compiler/proposals-and-stabilization.html (crater runs compare baseline vs. candidate precisely for this reason); R `revdepcheck`, https://github.com/r-lib/revdepcheck, which also runs old vs. new — **Mitigation here:** run the downstream gate at its baseline (the previous pointer) first, record failures, and report only the delta.
- **Flaky tests produce noise** — crater's "spurious failure" retry discussion — **Mitigation here:** on a gate failure, re-run only the failing node IDs once on the baseline and once on the candidate before filing anything.
- **Long runtimes** — crater runs take many hours — **Mitigation here:** the gate is already restricted by markers (3i). Keep it, and run the full gate once per spec, not per step.
- **Unclear ownership of fixes (upstream bug, downstream override, or test assumption?)** — commonly raised in crater/revdepcheck threads — **Mitigation here:** the spec should require a classification per failure (FLS bug / FLS test assumes dev config / downstream override stale / downstream pre-existing), with an action for each. This repo already has the downstream-side evidence: see section 6.
- **Downstream not on a clean branch** — **Mitigation here:** refuse to start on a dirty tree or on the default branch. Create the integration branch from the current HEAD before step one.
- **Inverse: upstream pushes into downstream repos (surprise commits, PRs on the default branch, style mismatch)** — Dependabot/Renovate maintainers' threads and corporate monorepo bots — **Mitigation here:** `update_fls.md` Step 5 already pushes only a branch and opens a PR if on the default branch. Keep that, add a per-project config of `branch prefix`, `push: yes/no` and the PR template, and follow the downstream's own commit conventions (read its `CLAUDE.md`).
- **Downstream `CLAUDE.md` says never edit `submodules/`** — First-Class `CLAUDE.md` lines 5-15 — **Mitigation here:** the upstream-side agent edits FLS in its own worktree, never through the downstream's `submodules/Freedom-LS` path.

## 3. Automated dependency bumpers

- **PR flood** — Renovate docs on grouping and rate limits, https://docs.renovatebot.com/configuration-options/#prconcurrentlimit; GitHub Dependabot docs, https://docs.github.com/en/code-security/dependabot — **Mitigation here:** one commit per spec is the right unit, but one PR per run, not one per spec. The PR body is the preview table from Step 2.
- **Bumps pass CI but break manually tested flows** — widely reported — **Mitigation here:** the portable gate excludes Playwright and FLS-internal tests, so passing it proves little about UI. The spec should require the adapted QA for any spec with a front-end change and record the result in the PR.
- **Merged without review / rubber-stamped** — widely reported — **Mitigation here:** the PR must list per spec the flags set, the overrides flagged, the workarounds NOT made, and the QA result. Never auto-merge.
- **"We just ignore them" (ignored noise)** — widely reported — **Mitigation here:** each commit must say what changed for this project, with "no action needed" stated explicitly. Hand-back items must be few, actionable and each carry an owner.
- **Silent skipping of a spec** — **Mitigation here:** the final report must list every spec as integrated / skipped / blocked and why, so none vanishes.

## 4. Agentic code-migration tooling

Sources: Amazon Q Code Transformation, https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/transform.html; Google, "How is Google using AI for internal code migrations?", https://arxiv.org/abs/2501.06972 (reports that humans must still review and that verification is the bottleneck); Claude Code issue tracker, https://github.com/anthropics/claude-code/issues (reports of destructive git commands and edits outside scope). Not re-read this session.

- **Fixes the symptom in the wrong repo** — typical in cross-repo work — **Mitigation here:** a hard rule: any failure caused by FLS code is fixed in FLS (this worktree), never worked around in the downstream. The downstream only changes its own overrides, settings and config.
- **Invents workarounds that later need rollback** — idea.md's own complaint — **Mitigation here:** workarounds are banned by default. If one is unavoidable it is a clearly marked commit with a TODO naming the FLS fix, recorded in a ledger so it gets rolled back.
- **Deletes TODOs / `@claude` comments** — `CLAUDE.md` forbids it — **Mitigation here:** the spec must restate the rule for downstream edits, and add a post-step diff check for removed `TODO`/`@claude` lines.
- **Over-asks or under-asks** — common — **Mitigation here:** ask only at defined gates (plan preview, pulling a downstream feature into FLS, a destructive step); otherwise proceed and decide small fixes alone per the idea's "small problems, just fix them" rule.
- **Loses track across repos** — **Mitigation here:** keep a state file per run (target, last-good SHA, spec index, open hand-backs) so a session restart resumes rather than restarts.
- **Pushes without permission** — **Mitigation here:** `git push` stays a per-target opt-in from config, never default.
- **Destructive git on a tree with uncommitted work** — `update_fls.md` Rollback uses `git checkout -- .` and `git clean -fd`; if the downstream tree was dirty before the run, that destroys the operator's own work — **Mitigation here:** require a clean tree at start (else stop), record the start SHA, and roll back with `git reset --hard <start-or-last-good-sha>` only after confirming the tree is clean as of the last commit. Prefer `git stash -u` or a temp branch. Never `git clean -fd` without `-n` preview.
- **Runs the wrong project's tests or DB** — **Mitigation here:** every command runs with an absolute target path and the target's own settings module; print the `DATABASES` name before any `migrate`.
- **`--deploy` check skipped when production settings are unavailable** — already handled in 3g; keep.

## 5. Manual browser QA plans reused across deployments

- **Plan assumes a theme, URL, brand or fixture** — `do_qa.md` takes the plan as written by the FLS spec and reads project config only from `.claude/fls-dev/config.md` (`## QA Dev Data`); admin credentials come from there too (lines 26-29). The plan's `§0` seed is the only data contract. A downstream with a different seed, theme or login template breaks it. Evidence: `spec_dd/3. done/2026-09-27_07:08_more-prominent-signup-button/upgrade_notes.md:25` (a downstream login override with another button label breaks the Playwright login). — **Mitigation here:** the spec should have the runner map each plan step to "applies / N/A (overridden) / adapt" before running.
- **Steps are N/A for an overriding project** — **Mitigation here:** record N/A with the reason, never a silent PASS or a false FAIL. A `FAIL` on an overridden template is a downstream-review item.
- **Screenshots drift** — `3. done/.../qa_report.md` carry stale-step notes (e.g. `2026-09-01_17:04_bug-interested-login-405/qa_report.md:366` "The step wording is stale") — **Mitigation here:** write downstream QA output into the target's or run's own directory, not the FLS spec dir, and label each screenshot with target and SHA.
- **QA data collides with real dev data** — `do_qa.md` Rule 2 allows wiping and re-seeding the dev DB (rung 3: DB drop/create) — **Mitigation here:** in a downstream, that is only safe when the DB is per-branch and disposable. The spec must verify that before any reset, and otherwise stop and ask.
- **Port and server collisions across several projects** — **Mitigation here:** reuse do_qa's Step 3 unused-PORT logic per target; run targets one at a time.
- **Batched Bash and MCP calls cancel each other** — `do_qa.md` Rule 3 — **Mitigation here:** keep these rules when the QA runs in a foreign project.

## 6. Complaints already written down in this repo and downstream

FLS repo:
- **Downstream login overrides break Playwright logins** — `spec_dd/3. done/2026-09-27_07:08_more-prominent-signup-button/upgrade_notes.md:25` — **Mitigation here:** conformance and upgrade-notes flow into the downstream gate.
- **Stale rows after upgrade need manual steps** — `3. done/2026-08-21_20:12_basic_reports/upgrade_notes.md:66` ("Existing `CourseProgress` rows are stale after this upgrade", manual steps) — **Mitigation here:** surface manual steps in the preview and the final report.
- **Subclasses lose inherited behaviour** — same file, line 102 (downstream `CourseItemProgress` subclass no longer inherits it) — **Mitigation here:** the preview should flag specs that change base-class contracts.
- **A downstream ignoring W001 publishes learners' names** — `3. done/2026-08-21_20:12_basic_reports/3a. report_generation_qa/qa_report.md:104` — **Mitigation here:** keep `check --deploy` (3g).
- **Country TLDs listed by hand** — `3. done/2026-09-23_11:31_google-analytics-setup/upgrade_notes.md:83` — **Mitigation here:** manual per-project settings go in the hand-back list.
- **Test helpers consumed by downstream tests change** — `3. done/2026-10-25_11:29_test-organisation-and-hygene-4-shared-test-infrastructure/upgrade_notes.md:17` — **Mitigation here:** flagged in the preview.
- **A notify-downstream workflow was removed** — `3. done/2026-08-31_08:32_deploy_prep_2/idea.md:19` ("FLS-09 notify-downstream.yml: Remove this") — **Mitigation here:** the old push-to-downstream notification is gone, so this command replaces it; do not reintroduce a bot.

Downstream (read-only, `/home/sheena/workspace/first_class/First-Class-LMS.git/main/spec_dd/for_freedom_ls/`, 28 items; sampled six). Each carries a "Source: `uv run pytest` in this downstream project, integrating the ... spec" line, and several a "Downstream workaround in place" section:
- **FLS test asserts dev config, fails in any downstream** — `sidebar-sections-test-assumes-messaging-is-enabled/idea.md:31,65` (downstream turned messaging on in `config/settings_base.py` as a workaround) — **Mitigation here:** classify as "FLS test assumes dev config" and fix in FLS.
- **FLS test assumes the default icon set** — `icon-intrinsic-size-test-assumes-the-default-icon-set/idea.md:54` — **Mitigation here:** same.
- **Tests fail when a downstream shadows `partials/header_bar.html`** — `sidebar-sections-...:61` — **Mitigation here:** conformance probes, not rendering tests.
- **Test leaks a mock site request** (pytest-randomly) — `registration-signal-test-leaks-a-mock-site-request/idea.md:5,86` — **Mitigation here:** run the downstream gate with its own plugin set and treat order-dependent failures as upstream bugs.
- **Playwright tests escape the "not installed" gate** — `registration-rules-playwright-tests-escape-the-not-installed-gate/idea.md:53` (workaround recorded) — **Mitigation here:** the marker set in 3i must stay current.
- **Test depends on `BASE_DIR/node_modules`** — `error-page-render-depends-on-base-dir-node-modules/idea.md` — **Mitigation here:** see the `npm install` ordering in 3e.
- Other items (`allauth-pages-use-stock-templates-and-copy`, `settings-defaults-tests-assert-against-the-downstream-config-package`) show the same shape: found in downstream, written as an idea, handed back by hand. The hand-back ledger the new command keeps is that pattern made automatic.
- Downstream `CLAUDE.md` lines 3-15: never edit `submodules/`; update recipe is `git -C submodules/Freedom-LS pull && git add ... && git commit -m "Update FLS submodule"` — it disagrees with `update_fls.md` (one commit per spec, `uv sync`, etc.). **Mitigation here:** the spec should say which wins and update the downstream's recipe on first run.

## Top 10 to design against

1. **Wrong-repo fixes and downstream workarounds** — require "fix in FLS first, then re-integrate", ban workarounds, and keep a ledger of any unavoidable ones with a rollback owner.
2. **Dirty or default-branch targets** — require a clean-tree and branch pre-flight and record the start SHA; refuse otherwise.
3. **Destructive rollback (`checkout -- .`, `clean -fd`) on unknown state** — replace with reset to a recorded last-good SHA after a clean-at-start check, previewing any clean first.
4. **Baseline-vs-candidate attribution** — run the gate at baseline first and report only new failures; re-run flaky nodes once.
5. **Failure classification and ownership** — FLS bug / FLS test assumes dev config / stale override / pre-existing, with a fixed action for each.
6. **Pushing and PR hygiene** — push is opt-in per target, branch plus one PR per run, with a per-spec summary table; never push to the default branch.
7. **QA plan adaptation** — map each step to applies / N/A / adapt, and verify the dev DB is disposable before any wipe; write output per target.
8. **Cross-repo state loss** — a resumable run-state file (target, last-good SHA, spec index, open hand-backs) plus a printed project/branch/DB/settings banner before each command.
9. **Lockfile and submodule hygiene** — `submodule status` clean, SHA reachable from FLS `origin/main`, `uv lock --check`, lock changes only within the per-spec commit.
10. **Ignorable noise** — every commit and PR says what changed for this project, explicit "no action", few owned hand-backs, an explicit integrated/skipped/blocked list, and no auto-merge. Also check no `TODO`/`@claude` lines were removed in downstream edits.

status: ok · reason: repo findings verified by reading; web sources cited from prior knowledge and not re-fetched
