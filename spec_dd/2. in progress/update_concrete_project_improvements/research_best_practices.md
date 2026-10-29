# Research: best_practices

Method note: written from reasoning plus well-known public sources; URLs were not all re-fetched this session. Items marked (unverified) are from memory and should be checked before being quoted in the spec.

## 1. Upstream-driven downstream testing

- **Rust crater** runs a compiler change against (a large slice of) crates.io, builds and tests every crate with old and new compiler, and reports only the *regressions* (pass before, fail after). Results are triaged by humans; each regression is either a compiler bug (fixed upstream), a justified breakage (consumer is told, upstream PR to the crate), or flaky noise. The report is a public artefact linked from the PR. https://github.com/rust-lang/crater , https://rustc-dev-guide.rust-lang.org/tests/crater.html
- **R CRAN `revdepcheck`**: maintainers must check reverse dependencies before submitting and list any breakage in submission comments; the contract is "tell the affected maintainers, ideally with patches, before release". https://github.com/r-lib/revdepcheck , https://cran.r-project.org/web/packages/policies.html
- **Fedora/Debian mass rebuild**: rebuild every package against the new toolchain; failures become bugs filed against the package, tracked by a tracker bug/ticket per failure, with deadlines. https://fedoraproject.org/wiki/Mass_Rebuild
- **Google LSC / Rosie / TAP**: the owner of the API change runs the downstream tests (TAP), shards the change into per-owner commits, each independently tested and reviewed. The change author, not the consumer, carries the burden. https://abseil.io/resources/swe-book/html/ch22.html
- **linux-next / Chromium LKGR** (unverified detail): integration trees merge many changes daily so conflicts surface before mainline; LKGR marks the newest revision where the full waterfall is green so consumers pin to known-good. https://www.kernel.org/doc/html/latest/process/howto.html
- Common pattern: compare against a baseline (only *new* failures count), keep one record per breakage, and the fix lands on the side that owns the root cause, usually upstream first.

**Applies here:** adopt the baseline idea (run the downstream suite at the current pointer first; only failures introduced by a spec are attributed to it) and a per-run findings record (one table row per downstream x spec: result, root cause, fix commit or filed spec). Deliberately not: parallel mass runs; downstreams are few, so run sequentially.

## 2. "Fix upstream, never downstream"

- Fedora's "stay close to upstream" and upstream-first rules: patches carried in the distro are a maintenance cost that grows every release; fix in upstream, then (at most) backport the merged commit. https://docs.fedoraproject.org/en-US/package-maintainers/Staying_Close_to_Upstream_Projects/
- Patch debt: every local patch/workaround must be rebased on each upgrade, so cost scales with (patches x releases). Distros track the patch count as a health metric (unverified phrasing).
- Hyrum's Law: with enough consumers, any observable behaviour is depended on, so a downstream breakage is evidence about the upstream contract, not just about the downstream. https://www.hyrumslaw.com/
- Concrete rules that work: no workaround commits in the downstream during an upgrade run; if one is unavoidable to unblock, it must carry a marker (`# TEMP-WORKAROUND: <upstream spec/issue>`) and be listed in the run record; the run stops at the first unexplained failure rather than patching through it.

**Applies here:** the command must forbid downstream workaround edits beyond the flagged integration steps already in `update_fls.md` (settings, migrations, package.json mirror); any other downstream edit is a stop-and-ask. Fix location is always the FLS worktree first, then re-pull the fix into the downstream.

## 3. Upstreaming downstream code

- Heuristics maintainers use (Linux "upstream your drivers", Fedora/Debian upstreaming guides, Django ticket triage): (a) solves a problem others plausibly have; (b) no project-specific vocabulary, URLs, branding or data; (c) fits the existing architecture/extension points rather than bypassing them; (d) can be tested without the downstream; (e) the maintainer is willing to own it. "Used by 2+ consumers" is the strongest signal but is often unavailable with a handful of consumers, so judgement plus the other criteria stands in.
- Tracking: proposals are tracked as tickets/specs with a link back to the source commit; accepted ones are re-imported *from upstream* and the downstream copy deleted, so the downstream never keeps two copies.

**Applies here:** the command should only *propose* (list file/commit, one-line why, a generality verdict against the criteria above) and ask the operator; on yes, write an FLS idea/spec referencing the downstream path and commit; never copy code silently. After the spec ships, a later run removes the downstream copy.

## 4. Sequential migration vs jump to latest

- Django's guidance: upgrade one feature release at a time, fix every `RemovedInDjangoXXWarning` on each step, because deprecation shims exist for exactly one-step transitions. https://docs.djangoproject.com/en/stable/howto/upgrade-version/ , https://docs.djangoproject.com/en/stable/internals/release-process/
- Per-step is worth it when steps carry stateful or order-dependent changes (migrations, settings that fail system checks, template overrides); bisecting a failure across N specs is far costlier than across one. Batching is acceptable for steps with no integration work (pointer move only), which `update_fls.md` already allows as an exception.
- Per-step gives each failure a single culprit spec, which is what makes "fix upstream before continuing" actionable.

**Applies here:** keep one spec per step with a gate and a commit; keep the existing "combine trivial specs" exception, decided from `upgrade_notes.md` flags (all false and no template overlap).

## 5. Operating on a second repository safely

- Practices: explicit allowlist of repos (from config, never from model-supplied paths), verify each path is a git repo with the expected remote, refuse on a dirty tree, record starting HEAD, work on a dedicated branch, dry-run preview before any write, one commit per step, rollback to the last good commit via the recorded SHA (prefer `git switch`/`git reset --hard <sha>` only on the tool-created branch), never push (or force-push) the downstream default branch, and prefer opening a PR/leaving the push to the operator. Git worktrees are a cleaner way to isolate the downstream run (https://git-scm.com/docs/git-worktree), but a submodule-based downstream is simpler to run in place on a branch.
- Machine-local paths: keep them out of version control via an untracked `config.local.md` (this project's `.claude/sdd/config.local.md` convention, see `claude_plugins/sdd/commands/protected/pre_step_rebase.md`), gitignored; a committed file may hold only a documented example/template. Environment variables are the fallback.
- Existing `update_fls.md` rollback uses `git checkout -- .` and `git clean -fd`; those are destructive against a tree the tool did not create. Given the clean-tree precondition they only discard the tool's own edits, but record the starting SHA and use it instead.

**Applies here:** list of downstream paths lives in a gitignored `.claude/fls-dev/config.local.md` (or the project's equivalent), validated each run: exists, is a git repo, clean, not on its default branch (create `fls-update/<date>` branch), push only that branch and only on operator approval.

## 6. Adapting QA to a customised downstream

- Practices: tag each QA step with the capability it covers (feature flag / overridable surface); derive applicability from the downstream's override inventory (templates, views, URLs, theme) and mark steps N/A with the reason rather than silently dropping them; keep a small "golden path" subset that must pass everywhere (login, course view, progress, one form); compare against downstream-specific expectations (branding strings) by checking structure not text; record N/A decisions in the run record so they are reviewable.
- The existing conformance probes (`freedom_ls.contrib.conformance`) are the automated analogue of a golden path.

**Applies here:** the agent reads the FLS QA plan for the spec, intersects it with the downstream's overrides (already detected by template-drift check), presents the adapted plan (run / adapted / N/A with reason) to the operator before running Playwright, and reports N/A counts at the end. Do not edit the FLS QA plan itself for a downstream's quirks; if a step fails only because of a downstream customisation the contract does not cover, treat it as a possible upstream extension-point gap.

## 7. Agentic / LLM-driven migrations

- Google's paper on LLM-driven code migrations (int32 to int64, JUnit3 to 4, etc.): LLM edits are produced per location, validated by builds/tests, then human-reviewed in normal per-owner changelists; success rates were high where a deterministic validation existed. https://arxiv.org/abs/2501.06972
- Amazon Q Code Transformation (Java upgrades) (unverified detail): produces a transformation plan the user reviews, works in a branch/diff, builds and tests between steps, and writes a summary of changes and unresolved items. https://aws.amazon.com/q/developer/transform/
- Shared guardrails: human-visible plan before edits; small reviewable diffs (one change per commit); build/test gate between steps; stop on ambiguity or repeated failure instead of looping; a final summary of what changed and what still needs a human; bounded retries.

**Applies here:** keep the dry-run preview as a mandatory confirmation; add a bounded retry (e.g. one fix attempt per failure class before escalating); stop-on-ambiguity for QA adaptation, upstream-vs-spec triage and upstreaming; end with a written run summary.

## Recommended rules for the new command

1. Read downstream checkout paths only from a gitignored local config file, never from committed files or model-guessed paths, and validate each is a git repo with the expected remote.
2. Refuse to touch a downstream with a dirty tree or a mid-rebase/merge state, record its starting HEAD, and do all work on a fresh branch, never its default branch.
3. Run the downstream's test suite at its current pointer first to establish a baseline, and attribute only new failures to the spec being integrated.
4. Show a full dry-run plan (specs, upgrade-notes flags, adapted QA) per downstream and require operator confirmation before any write.
5. Integrate one completed spec per step (pointer, sync, flagged steps, checks, tests, QA), one commit per step, with the combine-trivial-specs exception driven by the notes flags.
6. On any failure, stop and diagnose in the FLS worktree first; downstream edits are limited to the flagged integration steps, and any other downstream workaround needs explicit operator approval and a `TEMP-WORKAROUND` marker.
7. Triage each upstream defect as small (fix now in FLS, commit, then re-pull into the downstream and re-run the step) or large (write a new spec in FLS and pause that downstream at the last good spec).
8. Roll back to the recorded last-good SHA rather than using blanket `git clean`/`checkout` and allow no more than one fix attempt per failure class before escalating to the operator.
9. Adapt the FLS QA plan to each downstream's overrides, marking each step run, adapted, or N/A with a stated reason, and confirm the adapted plan with the operator before browser QA.
10. Treat a QA failure caused only by a downstream customisation as a possible missing FLS extension point and triage it like any upstream defect.
11. Scan the downstream for general-purpose code (no project vocabulary, usable by other consumers, fits FLS extension points, testable alone), propose it to the operator with a verdict, and write an FLS idea/spec only on approval.
12. Never push the downstream's default branch; push only the update branch and only with operator approval, then write a run record (per downstream x spec: result, root cause, fix commit or filed spec, N/A QA steps) for review.

status: ok · reason: complete; some URLs and details flagged unverified (not re-fetched)
