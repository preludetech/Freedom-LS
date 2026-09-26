# Git rebase safety

Every SDD step that runs on a feature branch first rebases the branch onto `main`, then proves the
rebase broke nothing before the step does its work. The same rebase is available as a command that a
human can run by hand.

## Why

A rebase once broke a lot of front-end functionality and nobody noticed. The dangerous rebase is not
the one that fails loudly. It is the one that succeeds and is quietly wrong:

- a conflict resolved by dropping one side;
- a hunk that applies cleanly but no longer agrees with the code around it;
- a template or JS helper that `main` changed underneath the branch without any conflict;
- a stale Tailwind build. The compiled CSS (`static/vendor/`, `tailwind.active_theme.css`) is
  gitignored, so a rebase that changes class usage leaves the worktree rendering old CSS, and there
  is no diff to inspect.

Branches also sit in `spec_dd/2. in progress/` for days while `main` moves. A spec or plan written
against last week's `main` can be heading somewhere that `main` has since turned away from.

## What happens on a rebase

1. **Commit, then rebase.** If the worktree has uncommitted changes, commit them first and carry on.
   Fetch `origin/main` and keep a backup ref of the branch's tip before rewriting it. If
   `origin/main` is already in the branch's history there is nothing to do, which keeps the check
   cheap enough to run before every step.
2. **Resolve conflicts, then prove nothing was lost.** Claude resolves conflicts itself. Every
   rebase then gets a lost-change check, whether or not git reported conflicts. The branch's own
   changes must survive, which `git range-diff` and a before/after comparison of the branch's
   `main...HEAD` diff show. `main`'s changes must not have been reverted. Lockfiles (`uv.lock`,
   `package-lock.json`) are regenerated rather than hand-merged. A branch migration that collides
   with a new one on `main` is renumbered to follow it, not merged, and the migration graph has to
   come out with one leaf per app. `research_rebase_mechanics_and_safety.md` covers the failure
   modes and the `--ours`/`--theirs` inversion during a rebase.
3. **Verify.** Rebuild Tailwind and apply migrations, then the full test suite and pre-commit must
   pass. A plain `uv run pytest` already includes the pytest-playwright browser tests. If front-end
   code changed, whether on the branch or in pages the branch uses that `main` changed, a quick
   Playwright MCP check follows. It reuses the spec's own QA plan where one exists and otherwise
   does a smoke-sized pass over the affected pages at the three `/fls-dev:do_qa` viewports. It is
   never the full QA run. `research_post_rebase_verification.md` covers what counts as front-end
   here and how changed files map to pages.
4. **Fix breakage on the branch.** If tests or the front-end check fail after the rebase, Claude fixes
   them on the branch (test first, as `fls-dev:qa-bugfixer` does) before the SDD step continues.
5. **Push.** Once verification passes and the branch has a remote, force-push with
   `--force-with-lease --force-if-includes` without asking.
6. **Review upstream changes when they matter.** A cheap mechanical scan of what `main` gained decides
   whether a short research pass is needed. The research covers only those code changes. The scan
   looks at overlap with the spec's apps and files, model and migration changes to shared bases,
   changed skills, `CLAUDE.md` or `docs/app_structure.md`, and specs newly in `spec_dd/3. done/`. Size
   alone is a weak signal. Changed skills and conventions count as architecture signals because the
   documentation is the source of truth. If the changes imply a different architectural direction,
   Claude writes the finding to a sibling file next to the spec and **the workflow pauses** until the
   human decides what to change. `research_upstream_change_impact.md` covers the signals and what
   "addressed" means at each stage.

## Where it lives

This builds on the existing `/ds:rebase_main`, with each concern in the plugin it belongs to.

- **`ds`**: `/ds:rebase_main` gets the generic hardening: commit-then-rebase, the backup ref,
  lost-change checks, lockfile and migration handling, and the automatic force-push. It stays the
  command a human runs by hand.
- **`sdd`**: runs the rebase before every feature-branch command. That covers dispatch through
  `/sdd:next` and also each command invoked directly. It owns the upstream-change review and the
  pause. It does not run on `main` (`/sdd:start`, `/sdd:roadmap`). `/sdd:finish_worktree` keeps its
  existing post-merge rebase.
- **`fls-dev`**: supplies the Tailwind rebuild and the Playwright MCP check through a project hook
  in `.claude/sdd/config.md`, the way `## Worktree Scripts` already lets `sdd` reach
  project-specific setup. `sdd` stays free of Playwright.

`research_sdd_workflow_integration.md` maps the branch model, every existing rebase, and the
command/skill/plugin precedents behind this split.
