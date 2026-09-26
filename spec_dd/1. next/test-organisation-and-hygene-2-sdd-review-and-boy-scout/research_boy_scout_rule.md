# Research: the boy scout rule for opportunistic cleanup (starting with test organisation)

Scope: how to bound "clean up as you go" so an AI agent (Claude Code) tidies test
organisation it touches while implementing a feature, without ever doing a
big-bang cleanup, and without breaking parallel feature branches/worktrees that
get rebased onto `main`.

## 1. What the rule means in practice

- **Uncle Bob's Boy Scout Rule** (from *Clean Code*): "Always check a module in
  cleaner than when you checked it out." The improvement doesn't need to be
  big — rename one variable, split one function, remove one duplication. The
  point is a steady, incremental ratchet, not a project. [Step 8: The Boy
  Scout Rule (Medium)](https://biratkirat.medium.com/step-8-the-boy-scout-rule-robert-c-martin-uncle-bob-9ac839778385),
  [DeviQ: Boy Scout Rule](https://deviq.com/principles/boy-scout-rule/)

- **Fowler's "Opportunistic Refactoring"**: refactoring isn't a separate
  scheduled activity — it happens as a natural part of adding a feature or
  fixing a bug, focused only on the code you are actively touching. Fowler
  names two opportunistic sub-workflows relevant here:
  - **Litter-Pickup Refactoring** — you understand the code, see it's done
    badly, and clean the specific mess in front of you (the "leave the
    campsite cleaner" case).
  - **Comprehension Refactoring** — you refactor to make code you don't yet
    understand easier to understand, as a side effect of reading it.
  - Fowler also names **Preparatory Refactoring** (tidy the code so the
    feature is easy to add) and **Planned/Long-Term Refactoring** for larger,
    scheduled restructuring — explicitly *not* something opportunistic
    cleanup should absorb.
  [Workflows of Refactoring — martinfowler.com](https://martinfowler.com/articles/workflowsOfRefactoring/fallback.html),
  [Opportunistic Refactoring — Roman Imankulov](https://roman.pt/posts/opportunistic-refactoring/)

- **Kent Beck, *Tidy First?***: separate **structural changes** (tidying —
  behaviour-preserving) from **behavioural changes** (features/fixes).
  Within a change sequence you can interleave them (e.g. `S S S S B B S B`),
  but *each commit should be one category only*. Beck also frames *when*:
  tidy **first** (if it makes the feature easier), tidy **after** (if the
  mess only became obvious once the feature was in), tidy **later** (record
  it, don't do it now), or **never** (not worth it). This "First, After,
  Later, Never" framing is a direct model for a "defer to a backlog item"
  decision. [Henrik Warne's summary](https://henrikwarne.com/2024/01/10/tidy-first/),
  [Dan Lebrero's book notes](https://danlebrero.com/2024/08/07/tidy-first-summary/),
  [First, After, Later, Never — Kent Beck's newsletter](https://newsletter.kentbeck.com/p/first-after-later-never)

- **Google engineering practices ("Small CLs")**: refactors and functional
  changes normally belong in **separate CLs** — "moving and renaming a class
  should be in a different CL from fixing a bug in that class" — because a
  pure-refactor review is mechanical and a feature review is conceptual;
  mixing them doubles reviewer effort and **hides bugs in the noise**. The
  one explicit exception: "small cleanups such as fixing a local variable
  name can be included inside of a feature change," with the "how small is
  small" judgment call left to author + reviewer.
  [Small CLs — google/eng-practices](https://google.github.io/eng-practices/review/developer/small-cls.html)

## 2. How teams bound opportunistic cleanup

Recurring bounding rules across sources:

- **Only files already touched by the feature.** The rule is triggered by
  contact with the code, not by "I noticed this elsewhere while grepping."
  Fowler's opportunistic workflows are explicitly scoped to code you are
  reading/editing for the primary task.
- **Only mechanical, behaviour-preserving changes** (Beck's "structural"
  category) — renames, moves, extracting a function with identical logic,
  deleting dead code, deduplication. Anything that changes observable
  behaviour is not tidying; it's a feature/fix and must be scoped as one.
- **Size/impact caps, then defer.** Philippe Bourgau argues the rule is
  "insufficient" for anything beyond small, local smells: "large scale
  refactorings ... require sharing the goal with the team and tracking
  progress" — i.e. once the fix would touch many files or restructure
  architecture, stop and log it instead of doing it inline. He recommends
  ROI-based prioritization of a backlog rather than ad hoc absorption.
  [When the Boy Scout Rule Fails](https://philippe.bourgau.net/when-the-boy-scout-rule-fails/)
  A concrete AI-agent-oriented version of this cap: the `large-scale-refactor`
  skill pattern sets explicit **file budgets per session** (e.g. 20 files for
  high-risk changes, 50 for medium, 200 for low-risk) and a **net-new-code
  threshold** (stop and re-scope if a single refactor step needs >50 lines of
  new code), with a mandatory pilot batch and periodic drift/self-audit
  checkpoints. [Stop Letting AI Agents Go Rogue — large-scale-refactor skill](https://dev.to/opensite/stop-letting-ai-agents-go-rogue-on-large-codebases-the-large-scale-refactor-skill-5gc)
- **Separate commits, marked for filtering.** The Schneide Blog's git-practice
  writeup for the boy scout rule recommends committing the feature first,
  then applying the cleanup as its **own commit with a distinguishing prefix**
  (their example: `BSR: more consistent function signatures`), so reviewers
  (or tooling) can filter pure-tidy commits out of the feature diff, or a
  maintainer can cherry-pick just the cleanup commit. This only holds for
  small refactors — "large cleanups should follow the traditional separate
  PR workflow." [The boy scout rule and git in practice — Schneide Blog](https://schneide.blog/2022/01/13/the-boy-scout-rule-and-git-in-practice/)
- **Separate PRs are the fallback**, not the default, when a cleanup is too
  large to be a same-branch trailing commit but still smaller than a planned
  initiative — i.e. there's a three-tier ladder: (1) tiny mechanical tidy →
  same commit as the feature is acceptable per Google's exception; (2) small
  but distinct tidy → separate commit on the same branch/PR; (3) anything
  bigger → its own PR/ticket, or a backlog item if there's no immediate
  driver.

## 3. Pitfalls

- **Noisy diffs hide the actual change.** Every source above converges on
  this: mixing refactor and feature "blows up the diff," makes it hard for a
  reviewer to see what actually changed, and can hide bugs introduced by
  either half. This is the primary reason to keep tidy commits separate even
  when they're allowed to live in the same branch/PR.
  [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html),
  [The Boy Scout Rule: Leave Code Better Than You Found It — dev.to](https://dev.to/maximeshr/the-boy-scout-rule-leave-code-better-than-you-found-it-5e68)
- **Merge/rebase conflicts from file moves.** Git's rename detection is
  heuristic (similarity-based, not tracked identity) and works differently
  across `merge`/`cherry-pick`/`rebase`. Renaming or moving a test file on one
  branch while another branch edits the *content* of that same file
  concurrently is a classic source of confusing conflicts — git may fail to
  detect the rename at all if the diff is large enough, producing a
  delete+add pair instead of a clean rename, which then produces baffling
  conflict output. Git 2.18+ added "implicit directory rename" detection for
  the case where a whole directory's contents moved, but this is still
  heuristic and can be "turned off" per-path if paths collide.
  Practically: **the more branches/worktrees are in flight rebasing onto
  `main`, the more a file-move done as opportunistic cleanup can produce
  rename/edit conflicts for every other branch that touched the same file**,
  even if the actual code changes don't conflict.
  [git-rebase docs](https://git-scm.com/docs/git-rebase/2.19.2),
  [Implicit directory rename handling — Bitbucket issue](https://jira.atlassian.com/browse/BSERV-11727),
  [Resolving git conflicts on renamed files (TIL)](https://til.codeinthehole.com/posts/how-to-resolve-git-conflicts-on-renamed-files/),
  [rebase/merge of renamed vs added file — libgit2 issue](https://github.com/libgit2/libgit2/issues/4921)
- **Scope creep / "while I was here."** For AI agents specifically, several
  sources flag that agents "don't have a scope reflex" — the longer/bigger a
  task, the more likely unrelated formatting, refactors, generated tests, or
  dependency touches creep into the diff alongside the requested change,
  and the default recommended fix is: **no opportunistic cleanup on the
  first pass** for anything not required to make the target change work; a
  useful self-check ("substitution test") is *if I removed this change,
  would the task still succeed?* — if yes, it doesn't belong in this diff.
  [Why AI Coding Agents Go Off Scope — Syncfusion](https://www.syncfusion.com/blogs/post/ai-guardrails-coding-agents),
  [Stop Letting AI Agents Go Rogue — large-scale-refactor skill](https://dev.to/opensite/stop-letting-ai-agents-go-rogue-on-large-codebases-the-large-scale-refactor-skill-5gc)
- **Breaking behaviour under the banner of "tidying."** Beck's whole framing
  depends on tidying being strictly behaviour-preserving; the risk is an
  agent (or human) rationalizing a behaviour change as "just a cleanup"
  because it's bundled with a legitimate refactor, which escapes the
  scrutiny a standalone behaviour change would get.
- **The rule doesn't scale to architectural debt.** Bourgau's critique: boy
  scouting is local-only, depends on the actor recognising the smell (junior
  agents/developers may not), and can't address debt caused by external
  shifts (new Django/Python versions, new conventions) — those need a
  tracked backlog item and, if big, a dedicated spec, not opportunistic
  fixes. [When the Boy Scout Rule Fails](https://philippe.bourgau.net/when-the-boy-scout-rule-fails/)

## 4. AI-agent-specific guardrails found

- **Spec/approval gate before wide changes**: don't start executing a
  refactor beyond the immediate touch-scope without it being an explicit,
  approved unit of work (maps directly onto this project's SDD spec
  workflow — a bigger test-organisation cleanup should become its own
  spec/idea, not something absorbed silently into an unrelated feature spec).
- **File/line budgets by risk tier**, with a hard stop and hand-back to the
  human/spec once exceeded, rather than the agent judging "just a bit more"
  is fine.
- **"Leave a note rather than fix" pattern**: when a cleanup opportunity is
  spotted outside the size/scope budget, agents are expected to *log it*
  (e.g. a TODO/backlog entry, an idea file) instead of performing it — this
  is the direct AI-agent analogue of Beck's "Later" and Bourgau's
  backlog-item alternative, and matches this project's existing convention
  of never deleting TODO/`@claude` comments.
- **Drift/self-audit checkpoints** on longer tasks, re-reading the original
  scope periodically and re-validating that every changed file is
  justified by it.
[Stop Letting AI Agents Go Rogue — large-scale-refactor skill](https://dev.to/opensite/stop-letting-ai-agents-go-rogue-on-large-codebases-the-large-scale-refactor-skill-5gc),
[Why AI Coding Agents Go Off Scope and How Guardrails Fix It](https://www.syncfusion.com/blogs/post/ai-guardrails-coding-agents)

## 5. Concrete guardrail recommendations for this workflow

Given: tests should mirror the app file hierarchy, an app's tests should only
depend on apps it depends on, several worktrees/branches run in parallel and
rebase onto `main`, and the explicit instruction is "never big-bang unless
asked."

1. **What counts as "touched."** Only apply boy-scout cleanup to test
   files/modules that the current feature change directly adds to, edits, or
   whose app the feature edits. Do not walk the tree looking for other
   violations "while you're in there." A test file counts as touched if the
   feature spec requires writing/editing a test in it or its direct
   neighbour test module for the same source file.

2. **What's allowed as "tidy" (mechanical, behaviour-preserving only).**
   - Move/rename a touched test file to mirror the app's file hierarchy
     (matching source module path).
   - Remove an inappropriate cross-app test dependency that the touched
     test itself introduces or extends, by moving/duplicating fixtures
     rather than by changing what is asserted.
   - Split an over-grown touched test module along the lines the hierarchy
     rule implies.
   - Delete dead/duplicate test helpers directly superseded by the change.
   Not allowed as "tidy": changing assertions, adding new test coverage
   beyond the feature, altering fixtures used by other apps' tests, or
   restructuring test files the current feature does not touch.

3. **Size threshold — when to defer to a backlog item instead of fixing.**
   Cap opportunistic test-hygiene changes at a small, explicit budget per
   feature branch, e.g.:
   - **≤3 test files moved/split, and ≤1 cross-app dependency removed** →
     do it inline as part of this change.
   - Anything larger (a whole app's tests need reorganising, or more than a
     handful of cross-app dependencies exist) → **do not touch it**. Instead
     record a follow-up idea (an `idea.md`/backlog entry under
     `spec_dd/1. next/` naming the app/module and the specific violation)
     and leave a short inline comment (`# TODO: test organisation —
     see spec_dd/... `) pointing at it, per the project's "never delete
     TODO/@claude comments" rule.

4. **Commit shape.** Never mix tidy and behaviour changes in one commit.
   - Commit 1 (or first N commits): the feature/fix itself.
   - A separate, clearly labelled commit for the test-hygiene tidy, e.g.
     `chore(tests): mirror hierarchy for <app> (boy-scout)` — analogous to
     the Schneide Blog's `BSR:` prefix — so it is trivially filterable out
     of the feature diff and revertable/cherry-pickable independently.
   - Both commits still land in the same PR/branch for a same-touched-file
     tidy (Google's "small cleanup" exception); a tidy big enough to need
     its own PR has, by definition, exceeded the size threshold in (3) and
     should become its own spec/idea instead.

5. **Rebase/parallel-branch safety for moves/renames.** Because git's rename
   detection is heuristic and can fail or conflict across parallel branches
   rebasing onto `main`:
   - Prefer `git mv`-equivalent moves (rename without also rewriting
     content in the same commit) so rename detection has the best chance of
     matching cleanly; do content edits in a following commit if both are
     needed.
   - Keep test moves small and rare (per the budget above) specifically
     because every file move is a latent rebase conflict for every other
     open worktree touching that file — this is an added cost the size cap
     must account for, not just review noise.
   - If a move is done, note it in the PR description explicitly (see next
     point) so sibling branches rebasing later know to expect it and can
     resolve quickly rather than being surprised.

6. **How to report it in the PR/change description.** Every PR that includes
   a boy-scout tidy commit should have an explicit line, e.g.:
   `Boy-scout cleanup: moved tests/<app>/test_x.py to mirror
   <app>/models/x.py; removed <app> tests' dependency on <other_app>
   fixtures.` If a violation was found but deferred, report that too:
   `Deferred (too large for boy-scout): <app>'s tests still depend on
   <other_app> — logged as spec_dd/1. next/<slug>/idea.md.` This keeps the
   reviewer/human aware of both what was tidied and what was consciously
   left dirty, without requiring them to diff-archaeology it out.

---

status: ok
