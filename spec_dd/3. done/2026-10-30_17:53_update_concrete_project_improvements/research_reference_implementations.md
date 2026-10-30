# Research: reference_implementations

Question: how do existing tools solve "an upstream project sweeps a list of local downstream checkouts, integrates changes, classifies results, and decides fix-upstream vs workaround"?

Provenance: items marked (fetched) were read from the cited page in this session. Items marked (recalled) come from prior knowledge and were not re-verified, so treat them as leads.

## 1. Reverse-dependency sweeps

### R `revdepcheck` (fetched)
- URL: https://github.com/r-lib/revdepcheck
- What: `revdep_check()` runs `R CMD check` on every reverse dependency twice, once against the released package and once against the local development version. It reports the difference. Runs are parallel, with a 10 minute limit per check. It is resumable: re-running picks up where it stopped. `revdep_reset()` clears everything.
- Artefact per downstream: raw results under `revdep/`. `revdep_report()` writes `revdep/README.md` (summary, partial while running), `problems.md` and `failures.md`. `revdep_details(".", "<pkg>")` shows one downstream.
- Failure taxonomy: status flags separate newly broken from already broken. `i-` install newly fails, `i+` install still fails, `t-` newly times out, `t+` still times out, `+` no new failures, `-` some new failures. "Newly" is a regression caused by the dev version. "Still" is pre-existing, so not our fault.
- Manifest: the todo list is edited with `revdep_add()`, `revdep_rm()`, `revdep_add_broken()`, `revdep_add_new()` and viewed with `revdep_todo()`. No hand-written file. Convention (recalled): problems are fixed upstream or the maintainer is emailed, and the README is committed as the audit trail.
- **Borrow:** run baseline-vs-candidate for each downstream, label results "new" vs "still failing", make runs resumable, and write a committed per-downstream summary plus a problems file.

### Rust `crater` (fetched, shallow)
- URL: https://github.com/rust-lang/crater (triage doc: docs/report-triage.md, not read)
- What: builds and tests a huge set of crates on two toolchains inside Docker and publishes an HTML report with logs. The README does not list per-crate fields or categories. From memory it uses regressed / fixed / broken / test-pass / spurious (recalled, unverified).
- Failure taxonomy: results are compared between a "before" and "after" toolchain. Only a pass-to-fail transition counts as a regression. A human triages each regression as real, spurious or flaky, and re-runs the flaky ones.
- Manifest: the crate list is auto-discovered from crates.io and GitHub, so there is no hand-curated file.
- **Borrow:** a pass-to-fail transition against a baseline is the regression definition, and flaky or spurious results need a re-run step before being blamed on FLS.

### pip / pytest / bundler / hex (recalled, not verified)
- pip and pytest have no formal sweep. Both rely on CI jobs that run downstream suites ("downstream tests" jobs, as in numpy, pandas and Django ecosystem checks). Django's `djangoci` / "third-party package test" practice is similar.
- Bundler and RubyGems "compact index" tests are about index format and are not a downstream sweep. Hex shows reverse dependencies as a listing only, with no test run.
- **Borrow:** nothing beyond the CI-job idea. These are weaker analogues than revdepcheck.

## 2. Multi-repo orchestration

- `mani` (recalled; the github.com/mani/mani URL returned 404, correct repo is github.com/alajmo/mani). Manifest is `mani.yaml`:
  ```yaml
  projects:
    api:
      path: ../api
      url: git@github.com:org/api.git
      tags: [backend]
  tasks:
    status: {cmd: git status --short}
  ```
  Tasks run across projects, filtered by tag. A missing path is reported with a sync prompt.
- `mr` / myrepos (recalled): `~/.mrconfig` with `[path/to/repo]` sections and `checkout = git clone ...`. `mr -d` limits the run to one repo. Per-repo command failures are summarised at the end.
- `gita` (recalled): keeps a registry of local paths (`gita add <path>`), `gita ll` shows branch and dirty state, and `gita super <repo> <git cmd>` runs a command in a subset.
- `repo` (Android) and `west` (Zephyr) (recalled): XML manifest (`default.xml`) or `west.yml` pinning a revision per project path. `repo sync` / `west update` check out the pinned revisions, and both refuse or warn on local changes (`repo sync` has `--force-sync`, west warns about a dirty tree).
- `vcstool` / `wstool` (recalled): a `.repos` YAML, `repositories: {name: {type: git, url:, version:}}`, with `vcs status`, `vcs pull` and `vcs export --exact` to snapshot SHAs.
- `copybara`, `git subrepo/subtree`, `meta`, `rush` (recalled): copybara is a stateless transform pipeline between repos (origin and destination, with a "last imported revision" label in the commit message). The others are about monorepo-like layouts and are not a close fit.
- Common handling: a registry of local paths, a status view showing branch and dirty state, and commands that skip or refuse dirty trees. Few do an automatic rollback.
- **Borrow:** a plain YAML or TOML list of paths with an optional per-entry `branch` and `tags`, plus a read-only preflight view (exists, is git, clean, expected branch, submodule SHA) in the style of `gita ll`.

## 3. Dependency-update bots

- Dependabot / Renovate (partly fetched, https://docs.renovatebot.com/configuration-options/): one PR per update by default. Renovate can group via `groupName` and caps open PRs with `prConcurrentLimit` (default 10). `automerge` defaults to `false`. Branch names identify earlier updates, so a closed or ignored PR is not recreated. The dependency dashboard issue lists pending, ignored and rate-limited updates (recalled). Failing CI leaves the PR open with a red status, and it is never auto-merged.
- Artefact per consumer: a PR (branch plus body with changelog and release notes) and a dashboard checklist.
- Failure taxonomy: CI red means "needs human". Closed without merging means "ignore this version" (Dependabot: `@dependabot ignore this version`).
- Manifest: `renovate.json` with `packageRules`, `ignoreDeps` (recalled). `dependabot.yml` has `updates:` entries (recalled).
- `pre-commit autoupdate` (recalled): rewrites `rev:` pins in `.pre-commit-config.yaml`, with no test gate.
- Google Rosie (recalled): splits a large change into per-owner shards that are reviewed and submitted separately, and each shard is tested on its own.
- **Borrow:** one change per integration unit, a failed gate leaves a visible "blocked" record rather than a silent revert, and a recorded "declined" decision stops the same proposal being repeated.

## 4. Submodule-bump automation

- `git submodule update --remote` followed by committing the gitlink (recalled). Renovate and Dependabot both support `gitmodules`/submodule updates.
- Zephyr `west update` and Yocto layer updates (recalled): the revision is pinned in a manifest file, and a bump is a commit that edits the pin, so the bump and its reason sit in one reviewable commit.
- Conventions (recalled): subject like `Update <submodule> to <short-sha>` or `Bump Freedom-LS to <spec-name>`, and the body is the `git shortlog old..new` of the submodule, or the changelog entries between the two SHAs.
- **Borrow:** one commit per spec in the downstream, with the commit body listing the FLS commits between old and new SHAs plus the spec name.

## 5. Upstreaming and drift detection

- `cruft` (fetched). URL: https://cruft.github.io/cruft/
  - `cruft check` exits 1 when the project is behind its template (for CI).
  - `cruft diff` shows how local files differ from the template and takes `--exit-code`, which together with `skip` can enforce that improvements are submitted upstream.
  - `cruft update` shows the changes for review before applying them.
  - Artefact: `.cruft.json` holding `template`, `commit`, the template variables and `skip` patterns. The skip list can also live in `[tool.cruft]` in `pyproject.toml`. The docs do not describe dirty-tree handling.
- `copier` (recalled): `.copier-answers.yml` stores `_src_path`, `_commit` and answers. `copier update` does a three-way merge with conflict markers, and `copier recopy` regenerates.
- `git cherry -v upstream branch` (recalled) lists commits not present upstream. This is useful where a downstream edited vendored FLS, but it cannot see new downstream-only code.
- Chromium/Android "upstream first" trackers (recalled): they rely on tags or bug links in downstream commit messages. Nothing automatic detects "generally useful" code.
- Gap: none of these tools judge whether code is general. Detection is mechanical (diff against a base, a path list, or an explicit tag), and the "is it generally useful" judgement is human, or here an LLM plus a question to the user.
- **Borrow:** `cruft`'s model of a recorded base (FLS SHA) plus a `skip` list, and a diff of the downstream's own extension code (not the submodule) shown as candidates for the user to accept or decline.

## 6. Claude Code multi-directory work

- Permissions doc (fetched). URL: https://code.claude.com/docs/en/permissions
  - Read-only tools need no approval "within the working directory and additional directories".
  - `acceptEdits` auto-accepts edits and common filesystem commands for paths in the working directory or `additionalDirectories`.
  - `cd` into an additional directory is treated as read-only. A compound `cd packages/api && ls` runs without a prompt if each part qualifies.
  - `cd` plus `git` prompts when the `cd` changes into a different directory, because git there "can execute that directory's hooks". This matters for running `git` in a downstream.
  - Output redirects, `tee` and input redirects are checked against the working directories. Targets outside them need approval unless an allow rule covers them.
  - Path rules: `/path` is relative to the settings source, so `Edit(/src/**)` in project settings means `<primary working directory>/src/**`. Absolute paths need the `//` form (recalled).
- Implication: a downstream path outside the FLS worktree either goes in `additionalDirectories` (or `--add-dir`, or `/add-dir`, recalled) in settings, or the user approves each prompt. A non-interactive worker cannot answer prompts, so the command must tell the user to configure this up front.
- Bash `cwd` resets between calls in this agent environment, so every command must use absolute paths or `git -C <path>`. This is stated in the environment notes for this run, not in the docs.
- Existing repo guidance: grep of `/home/sheena/workspace/lms/freedom-ls-worktrees/update_concrete_project_improvements/claude_plugins/sdd/skills/claude-code-authoring/` for add-dir, additional directories, cross-repo and working directory found no matches. The skill says nothing about this, so any spec needs to add or reference it.
- **Borrow:** list downstream paths in `additionalDirectories` (project settings) and use `git -C <abs path>` throughout.

## Synthesis: the shape to borrow

1. Manifest: a short committed-or-local YAML/TOML list of absolute paths (`gita` registry plus `mani` `path`/`tags`), each with optional `branch` and notes. Record per downstream the last integrated FLS SHA (`cruft`'s `commit`).
2. Preflight (read-only, per entry, `gita ll` style): path exists, is a git repo, clean tree, expected branch, submodule SHA vs the SHA the manifest says. Skip and report a bad entry. Never stash or reset someone else's work.
3. Baseline (revdepcheck): run the downstream's tests and QA once before integrating, so pre-existing failures are known.
4. Integrate one spec at a time (Rosie shards plus the existing `update_fls` loop): bump the submodule, apply the spec's `upgrade_notes.md` actions, run tests and QA, make one commit whose body lists the FLS commits in old..new.
5. Classify against the baseline: `new` failure (regression, ours), `still` failing (pre-existing, report only), `flaky` (re-run once, as crater does), `pass`.
6. Record: write a per-downstream, per-spec results file (revdepcheck `README.md` / `problems.md` equivalent) and advance the recorded SHA only on pass.
7. Fix-upstream decision on each `new` failure: small means fix in FLS now, then re-run the same spec in the downstream. Large means write a new FLS spec, mark this downstream "blocked on spec X" (Renovate keeps the PR open, red) and move on to other downstreams. Workarounds in the downstream are not allowed.
8. After the sweep, run a `cruft diff`-style candidate scan of each downstream's own extension code and ask the user per candidate. Store accept and decline answers so declined ones are not asked again (Renovate ignore).
9. Authority: set up `additionalDirectories` for the paths so the run does not stall on prompts, and use `git -C` with absolute paths.

status: ok · reason: web-verified for revdepcheck, cruft, Renovate (partial) and Claude permissions docs; crater categories, mani, west/repo, copier, Rosie and Dependabot details are recalled and flagged as unverified
