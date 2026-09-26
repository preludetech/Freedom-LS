# Research: safe, agent-driven `git rebase` onto main

## 1. Rebase mechanics — what "safe" actually means

**Before touching anything**
- `git fetch` (not `git pull`) so local `main`/`origin/main` refs are current without touching the working tree.
- Take a **safety ref** before rewriting history: `git branch backup/<branch>-$(date +%s) HEAD` (or just rely on the reflog — `HEAD@{n}` — but an explicit branch is easier for an agent to reference and for a human to inspect/restore from later; the reflog expires and is per-clone, so it doesn't help if the agent is working from a fresh worktree).
- If the working tree is dirty, either refuse and hand back to the human, or use `git rebase --autostash`. Autostash is safe for the common case but its own re-apply step *can* itself conflict — treat a conflicted autostash pop as a stop condition, not something to auto-resolve. (Adam Johnson: https://adamj.eu/tech/2022/11/05/git-automatically-stash-rebase-merge/)

**During**
- `git config rebase.rerere true` (or repo-wide `rerere.enabled true`) so a conflict resolved once in this branch's lifetime is replayed instead of re-litigated — but note rerere silently *replays a bad resolution* just as readily as a good one, so it's a productivity aid, not a substitute for verification (see §2).
- `--update-refs` (Git ≥2.38) keeps any stacked branches pointing at the rebased branch in sync automatically — relevant only if the SDD workflow ever stacks spec branches on each other; can be defaulted via `git config rebase.updateRefs true`.
- `--onto` is for surgical cases (splicing a branch onto a new base, or dropping an already-merged range) — not needed for the common "replay my branch onto latest main" case, which is just `git rebase main`.
- Abort cleanly on the first sign of trouble: `git rebase --abort` restores the branch to its pre-rebase tip exactly; there is no reason for an agent to ever "push through" a rebase it doesn't understand.

**After, before force-pushing**
- Force-pushing a rewritten branch requires `--force-with-lease` at minimum — it only overwrites the remote if the remote-tracking ref (as of your last fetch) still matches what's actually on the remote, i.e. it protects against a teammate having pushed to the branch in the meantime.
- `--force-with-lease` alone has a gap: a bare `git fetch` (e.g. run by CI, an IDE, or an earlier step in the same agent session) updates the local remote-tracking ref *without* those commits being incorporated into your rewritten branch, silently defeating the lease. `--force-if-includes` (Git ≥2.30) closes that gap by additionally requiring that the remote's current tip is actually reachable/integrated into what you're pushing. Use both together: `git push --force-with-lease --force-if-includes`. (https://adamj.eu/tech/2023/10/31/git-force-push-safely/, https://www.vladimirzdrazil.com/til/git/git-force-if-includes/)

**Rebase vs merge for this workflow**
- Rebase gives a linear history and a clean `git log main..branch` per spec step, which matches the SDD model of "one branch per spec, rebase before each step." The cost is that conflicts are resolved commit-by-commit, against code you may not have touched recently, which is exactly the failure mode this task exists to prevent (Aviator, Atlassian, Jonathan Hall write-ups converge on this).
- Merge resolves the whole delta once, with full context, but produces merge commits and non-linear history that's harder for later spec steps (and later rebases) to reason about; it also doesn't compose well with `git range-diff` verification (below).
- General industry consensus: the risk of rebase (misresolved conflicts) grows with how long-lived and diverged the branch is. Given this project's model — short-lived, one-branch-per-spec, rebased *before every step* rather than once at the end — branches should rarely be far behind `main`, which is the condition under which rebase is safest. If a branch has drifted far (many upstream commits, or the human flags "major changes"), that's the trigger for the research-step/judgment-call already described in `idea.md`, and possibly a case to prefer merge or human review over an automated rebase.
- Sources: https://www.aviator.co/blog/rebase-vs-merge-pros-and-cons/, https://jhall.io/archive/2024/01/11/when-i-dont-rebase/, https://www.atlassian.com/git/tutorials/merging-vs-rebasing

## 2. Conflict handling by an AI agent — what goes wrong, and how to catch it

**Known failure modes**
- **Wholesale `--ours`/`--theirs`.** During a rebase these flags are *inverted* relative to a merge: `--ours` means "the commit you're rebasing onto" (typically `main`), `--theirs` means "your commit". An agent (or human) using intuition from `merge` semantics will pick the wrong side. Any blanket `checkout --ours <file>` / `--theirs <file>` on a conflicted file should be treated as suspect — it means "discard one side's changes to this file entirely," which is very rarely correct for anything except pure lockfiles/generated output.
- **Clean-but-wrong textual merges.** The dangerous case isn't the conflict marker — it's the hunk that applies without a marker at all but is semantically wrong (e.g. two independent edits to the same function that both apply but no longer agree on a signature, a JS event handler removed on one side because a duplicate-looking handler exists on the other, etc.). Git's line-based 3-way merge has no idea about semantics; it only flags conflicts where line ranges literally overlap.
- **Merge commits inside the branch being rebased.** If the branch being rebased contains a merge commit itself, standard `git rebase` (without `--rebase-merges`) replays each side of that merge as if the content only existed via the first-parent line — content that was only introduced via the merge's second parent can be **silently dropped with no conflict reported at all**, because from the rebase machinery's point of view that content doesn't exist. This is the single scariest failure mode because it produces no conflict markers to review. (https://github.com/markmhendrickson/ateles/issues/1081)
- **Rerere replaying a bad resolution.** Once a conflict is resolved (well or badly) and recorded, rerere will reapply that same resolution automatically on every future rebase that hits the same hunk, with no further prompt — a bad early resolution becomes permanent and invisible.

**Verification techniques (to run *after* every agent-resolved rebase, before it's considered done)**
- `git range-diff <upstream-before> <branch-before> <branch-after>` (or the shorthand `git range-diff branch@{u} branch@{1} branch`) diffs the diffs: it shows, commit by commit, whether the actual content each commit introduces changed across the rebase. If a conflict was "resolved" by dropping upstream-conflicting code, range-diff shows it as a `-`/`+` pair inside a commit that should otherwise be near-identical. Cosmetic-only changes (context line shifts, SHA changes) are the expected/benign case; substantive `-`/`+` content in a commit that didn't intend to touch that code is the signal to stop and investigate. (https://andrewlock.net/verifiying-tricky-git-rebases-with-range-diffs/, https://git-scm.com/docs/git-range-diff)
- Compare `git diff main...branch` (the branch's total delta over its merge-base with main) **before** rebasing against the same computation **after**. The two diffs should be equivalent modulo the intentional resolution of the conflicting hunks — anything that disappeared from the post-rebase diff and isn't accounted for by an upstream change to the same lines is a dropped change.
- Confirm the pre-rebase upstream delta (`git diff <old-main>..<new-main>` for any file the branch also touches) is still fully present post-rebase — i.e. the rebase didn't accidentally *revert* main's own changes while resolving a conflict against them.
- Treat a clean, no-conflict rebase as *not* automatically safe if the branch is old/wide-touching — clean rebases can still be semantically wrong (the "clean but wrong" case above); this is why the project's existing idea (`idea.md`) already says: run the test suite, and if front-end code was touched, do a Playwright MCP smoke check regardless of whether the rebase reported conflicts.

**When an agent should stop and hand back to a human**
- Any hunk requiring `--ours`/`--theirs` on non-generated files.
- Any commit in the branch being rebased that is itself a merge commit (check with `git log --merges <merge-base>..branch` before starting).
- `range-diff` (or the before/after `diff main...branch` comparison) shows content loss not explained by an upstream change to the same region.
- More than a small, agent-judged number of conflicting hunks in a single file, or conflicts touching files the branch's own commits never intended to change.
- Migration conflicts that require *choosing* which app state is correct rather than mechanically renumbering (see §3).

## 3. Project-specific conflict hotspots (checked against this repo)

| Path / mechanism | Tracked in git? | Notes |
|---|---|---|
| `freedom_ls/*/migrations/*.py` | Yes | **Already happened here**: `freedom_ls/content_engine/migrations/0003_merge_20260910_0459.py` is a real Django-generated merge migration in this repo's history, proof that two branches independently added a migration at the same number for `content_engine` and had to be merged. Rebasing (vs merging) a branch whose migrations conflict with new migrations on `main` requires **renumbering the unmerged branch's migrations** to stack after `main`'s latest, not creating a merge migration — `makemigrations --merge` is a *merge*-workflow fix and produces an extra migration file mid-rebase that doesn't make sense once the branch is linearised onto main. After any rebase touching migrations, run `uv run manage.py makemigrations --check --dry-run` to confirm there's exactly one leaf per app and no undeclared model changes. |
| `uv.lock` | Yes (not in `.gitignore`) | Lockfile conflicts should never be hand-resolved line-by-line; regenerate with `uv lock` (or `uv sync`) after resolving `pyproject.toml`, then diff the result against both parents' dependency sets to confirm nothing was silently downgraded/removed. |
| `package-lock.json` | Yes (not in `.gitignore`; `node_modules/` is ignored but the lockfile is not) | Same rule as `uv.lock`: never hand-merge, regenerate with `npm install` from the resolved `package.json` and re-verify. |
| Compiled Tailwind CSS (`static/vendor/tailwind.output.css`, `tailwind.active_theme.css`) | **No** — `.gitignore` has `static/vendor/` and `tailwind.active_theme.css` explicitly | This is a strong lead for "conflicts silently broke front-end functionality" *without it being a git conflict at all*: the compiled CSS is a per-worktree build artifact, not tracked. If a rebase brings in new/changed Tailwind class usage (templates, Cotton components) but `npm run tailwind_build` isn't re-run afterward in that worktree, the on-disk CSS goes stale silently — no conflict marker, no diff, just visibly "broken" front-end behaviour that looks like a bad merge but is actually a stale build. **The rebase skill should always rebuild Tailwind after a rebase that touches any template/CSS-affecting file**, not only rely on git's conflict resolution being correct. |
| `spec_dd/` files (idea.md, todo.md, roadmap.md, research_*.md) | Yes | These are prose/plan files, most likely to hit *textual* conflicts that git resolves "cleanly" but wrong (e.g. two branches both append a new spec entry to `roadmap.md` in the same location — line-based merge can silently reorder or drop one). Since these files aren't executable, no test will catch a bad resolution — an agent should specifically re-read the post-rebase `roadmap.md`/`idea.md` and eyeball it against both parent versions rather than trust a clean apply. |
| Django app `migrations/__init__.py` | Yes, but empty/inert | Not a real hotspot; just noise in a migrations glob. |

General principle validated by this table: this repo already separates "must be identical byte-for-byte across environments" (lockfiles) from "compiled and gitignored, must be regenerated" (Tailwind CSS) from "structurally mergeable but needing a Django-aware tool" (migrations) from "prose that git will merge textually but not always correctly" (spec_dd files). Each category needs a different post-rebase check, not one generic "run the tests" step.

## 4. Reference implementations / prior art (short notes)

- **git-town `sync`** — a CLI that automates "update this branch from its parent and push," handling the fetch/rebase-or-merge/push sequence and stacked-branch updates as one command; configurable to merge or rebase. Useful precedent for wrapping the whole sequence (fetch → rebase → verify → push) behind one command, matching what this project wants.
- **Graphite `restack` / `sync` / merge queue** — for stacked PRs, automatically rebases dependent branches when a parent branch changes, and its merge queue rebases a PR onto the latest trunk immediately before merging and runs checks before allowing the merge. The "rebase immediately before merge, checks must pass, otherwise it doesn't land" pattern is directly analogous to "rebase onto main before every SDD step, and don't proceed if tests/Playwright fail." (https://graphite.com/guides/rebasing-and-updating-refs, https://graphite.com/docs/restack-branches)
- **GitHub "Update branch" button** — performs either a merge or (with the "Update with rebase" option) a rebase of a PR branch onto its base, essentially the same mechanics discussed above, offered as a single human-triggered action with no built-in post-rebase verification — i.e. it solves the mechanics but not the "did we silently drop something" problem this task is really about.
- **Aider / Cursor** — no public rebase-specific automation was found in general documentation; these tools' conflict handling is generally scoped to single-file edits rather than repo-wide history rewriting, so there isn't a directly reusable "agent resolves a rebase conflict safely" pattern from them to cite here.

## Conclusions and trade-offs (no checklist — see below for the tone this informs, not a procedure)

- Mechanically, the safe primitives all exist and are well documented: fetch-first, an explicit backup ref (reflog is not durable enough to be the only safety net), `--autostash` (but treat its own conflicts as a stop condition), `rerere` (productivity, not correctness), `--update-refs` if stacking is ever used, clean `--abort` on any doubt, and `--force-with-lease --force-if-includes` on push.
- The real risk in this task is not "the rebase mechanics fail" — it's "the rebase mechanics succeed, either automatically or via a resolution an agent chose, and the result is *quietly* wrong." The two verification techniques that actually catch that — `git range-diff` and a before/after `git diff main...branch` comparison — are cheap to run and should be treated as load-bearing, not optional, on every agent-driven rebase, independent of whether git reported conflicts.
- Migration conflicts, lockfiles, and (in this repo specifically) the gitignored compiled Tailwind CSS need three genuinely different remedies (renumber + `makemigrations --check`, regenerate-from-manifest, rebuild-and-visually-check) — a single generic "run tests" step will not surface all three failure classes, especially the stale-CSS one which produces no diff at all to inspect.
- Rebase is the right default for this project's short-lived, rebase-before-every-step branch model (branches should rarely be far diverged), but "the branch has drifted a lot" or "main has moved in ways that look architecturally significant" is exactly the condition under which the idea.md's own "judgment call" escape hatch (research step, flag architecture drift, possibly fall back to merge or a human) should fire — rebase safety and "is this still the right direction" are separate concerns that happen to be triggered by the same signal (a large/complex diff to reconcile).
- Any conflict resolution that amounts to a blanket `--ours`/`--theirs` on a non-generated file, or a branch containing its own merge commits, should be a hard stop for an autonomous agent rather than something it tries to push through.

## References

- https://adamj.eu/tech/2022/11/05/git-automatically-stash-rebase-merge/
- https://git-scm.com/docs/git-rebase
- https://andrewlock.net/verifiying-tricky-git-rebases-with-range-diffs/
- https://git-scm.com/docs/git-range-diff
- https://github.com/markmhendrickson/ateles/issues/1081
- https://adamj.eu/tech/2023/10/31/git-force-push-safely/
- https://www.vladimirzdrazil.com/til/git/git-force-if-includes/
- https://www.aviator.co/blog/rebase-vs-merge-pros-and-cons/
- https://jhall.io/archive/2024/01/11/when-i-dont-rebase/
- https://www.atlassian.com/git/tutorials/merging-vs-rebasing
- https://code.djangoproject.com/ticket/28535
- https://adamj.eu/tech/2020/12/10/introducing-django-linear-migrations/
- https://www.codestudy.net/blog/django-migrations-conflict-multiple-leaf-nodes-in-the-migration-graph/
- https://graphite.com/guides/rebasing-and-updating-refs
- https://graphite.com/docs/restack-branches
- Repo evidence: `freedom_ls/content_engine/migrations/0003_merge_20260910_0459.py`, `.gitignore` (lines for `static/vendor/`, `tailwind.active_theme.css`), `claude_plugins/sdd/skills/git-worktree-setup/SKILL.md`, `spec_dd/1. next/git-rebase-safety/idea.md`

status: ok
reason: completed web + repo research; no blockers
