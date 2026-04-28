# Research: PR sizing and decomposing specs into reviewable chunks

Goal: heuristics an AI agent can use to decide whether a single FLS spec should ship
as one PR or be sliced into multiple PRs, and how to slice it.

---

## 1. PR size research — the empirical backbone

**Heuristic:** Aim for ~200 lines changed; never exceed ~400. Above 400 LOC,
defect-detection collapses.

**Evidence:**
- The SmartBear/Cisco study (10-month case study at Cisco MeetingPlace, 2006)
  found defect detection drops sharply once a review exceeds 200-400 LOC, and
  reviewers running faster than ~450 LOC/hr miss defects 87% of the time. The
  recommended sweet spot is 100-300 LOC, reviewed in 30-60 minutes.
- Google's internal data (Sadowski et al., ICSE 2018) shows the median
  changelist at Google is small enough to review in under an hour, and Google's
  public eng-practices guide explicitly tells reviewers to push back on CLs
  that are too large.
- Bacchelli & Bird (Microsoft, ICSE 2013) found "code/change understanding"
  is the bottleneck — large diffs exceed reviewer working memory, so review
  shifts from understanding to rubber-stamping.
- Aggregated industry data (Graphite, Propel, LinearB) shows review time
  grows non-linearly with PR size: each +100 LOC adds roughly 25 min, and
  PRs > 1000 LOC have 70% lower defect detection.

**Failure modes when ignored:** rubber-stamp approvals, defects merged to main,
reviewer burnout, week-long open PRs that conflict with everything else,
"big-bang" rollbacks instead of surgical reverts.

**Sources:**
- https://mikeconley.ca/blog/2009/09/14/smart-bear-cisco-and-the-largest-study-on-code-review-ever/
- https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf
- https://sback.it/publications/icse2018seip.pdf
- https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ICSE202013-codereview.pdf
- https://graphite.com/blog/the-ideal-pr-is-50-lines-long
- https://www.propelcode.ai/blog/pr-size-impact-code-review-quality-data-study

---

## 2. Stacked PRs — when a spec genuinely needs > 1 PR

**Heuristic:** If a change can't be cut below ~400 LOC without breaking
atomicity, ship it as a stack of dependent small PRs rather than one big PR or
one bloated branch.

**Why teams adopt it (Graphite, ghstack, Sapling, Gerrit chains):**
- Reviewers see one logical change per diff (e.g. "add model" → "add API"
  → "wire up UI") instead of a 2000-LOC mega-diff.
- Author isn't blocked: PR #2 builds on PR #1 while #1 is still in review.
- Conflict surface shrinks; rebases cascade automatically through the tooling.
- Each diff in the stack is independently revertable in trunk.

**When to adopt:** total scope > ~600 LOC, or scope spans > 2 architectural
layers, or work has clear dependency chain (model → API → view → template).

**Failure modes:** "fake stacks" where each PR isn't independently meaningful
(reviewers can't review #2 without re-reading #1); abandoning the stack midway
and merging only the bottom; no tooling, so authors hand-rebase and corrupt
history.

**Sources:**
- https://graphite.com/blog/stacked-prs
- https://graphite.com/guides/stacked-diffs
- https://www.awesomecodereviews.com/best-practices/stacked-prs/

---

## 3. Vertical vs. horizontal slicing — INVEST

**Heuristic:** Slice vertically (each PR cuts through model + API + UI for one
narrow capability), not horizontally (PR1 = all models, PR2 = all views). Apply
INVEST: Independent, Negotiable, Valuable, Estimatable, Small, Testable.

**Reasoning:** A horizontal slice ("add 5 models") can't be tested as user
behaviour and provides no business value until the next layer lands. A vertical
slice ("user can mark one topic complete") can be merged, deployed, demoed, and
reverted on its own.

**Failure modes:** half-built schema sitting in production for weeks; merged
models with no consumers (dead code risk); reviewers can't tell what "done"
means; QA can't test a horizontal slice.

**Sources:**
- https://agilealliance.org/glossary/invest/
- https://www.thoughtworks.com/en-us/insights/blog/user-stories-tale-epic-confusion

---

## 4. Story-splitting patterns — Cohn (SPIDR), Lawrence (10 patterns)

**Heuristic:** Before declaring a spec "too big", try these splits in order:
1. **Workflow steps** (Lawrence) — split by happy-path step (register → confirm
   email → first login).
2. **Paths** (SPIDR-P) — alternate flows (card vs. Apple Pay) become separate PRs.
3. **Data variations** (SPIDR-D) — start with one data type/format, extend later
   (one cohort → all cohorts; MP4 only → all formats).
4. **Rules** (SPIDR-R) — implement the simple rule first, edge cases later.
5. **Interface variations** (SPIDR-I) — basic UI now, polished/responsive later.
6. **Spike** (SPIDR-S) — if uncertainty is high, learn-only PR before build PR.
7. **Simple/complex** (Lawrence) — get a thin happy path in, then add complexity.

**Failure modes:** splitting by activity ("design", "code", "test") instead of
behaviour — produces PRs nobody can ship.

**Sources:**
- https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories
- https://www.humanizingwork.com/the-humanizing-work-guide-to-splitting-user-stories/
- https://www.lagerweij.com/2010/10/20/patterns-for-splitting-user-stories-%E2%80%94-richard-lawrence/

---

## 5. Walking skeleton / thin vertical slice

**Heuristic:** First PR of a multi-PR spec should be the thinnest end-to-end
slice that exercises every layer (model → migration → URL → view → template
→ test) — even if it only handles one trivial case. Subsequent PRs flesh it out.

**Reasoning (Cockburn, Thomas "tracer bullet"):** the skeleton de-risks
integration, proves the architectural seams hold, and gives QA something to
exercise. Subsequent PRs become small additions instead of an integration
gamble at the end.

**Failure modes:** skipping the skeleton and building horizontally; building a
"perfect" first slice that's too thick; skeleton with no automated test, so
later PRs silently break it.

**Sources:**
- https://wiki.c2.com/?WalkingSkeleton=
- https://www.mattblodgett.com/2020/09/start-with-walking-skeleton.html

---

## 6. Architecture-driven decomposition

**Heuristic:** Natural seams in an FLS spec become PR boundaries:
- Data model + migration is its own PR (highest-risk, easiest to revert alone).
- Site-aware manager / permissions wiring is its own PR if non-trivial.
- API/view layer follows, importing the new models.
- Templates/HTMX/Alpine UI follows, importing the views.
- Cross-app glue (e.g. a new dependency between `student_progress` and
  `content_engine`) is called out and reviewed independently.

**Reasoning:** Each layer has a different reviewer mindset (DBA vs. domain vs.
frontend). One PR per seam respects that and keeps blast radius narrow.

**Failure modes:** mixing migration + UI in one PR — reviewer either rubber-
stamps the migration or holds up UI work for a schema concern.

**Sources:**
- https://medium.com/@razkevich8/the-art-of-drawing-boundaries-mastering-decomposition-in-software-architecture-5f01a4148033

---

## 7. Risk-based splitting

**Heuristic:** Isolate risky bytes from boilerplate. Migrations, security/auth
code, multi-tenant filtering, anything irreversible → its own small PR. Renames,
codegen, formatting, fixture additions → separate "trivial" PR that reviewers
can scan in 60 seconds.

**Reasoning:** Mixing 10 risky lines into 500 boilerplate lines hides the risky
lines. Splitting lets reviewers spend their attention where defects actually
live, and lets risky changes ship behind a feature flag while boilerplate ships
freely.

**Failure modes:** "while I'm here" cleanups merged with the risky core change;
auto-generated diffs masking real edits; reverts that take everything down,
including the safe parts.

**Sources:**
- https://martinfowler.com/articles/feature-toggles.html
- https://launchdarkly.com/blog/what-are-feature-flags/

---

## 8. Independent mergeability and shippability

**Heuristic:** Every PR in a split must be (a) independently mergeable to main,
(b) leave the system green, (c) be shippable — even if dark-launched behind a
flag. If PR-N relies on PR-(N+1) to be valid, the split is wrong.

**Reasoning:** Half-built features in main are tolerable only if invisible.
Feature flags decouple deploy from release; without them, vertical slices must
be user-visible-correct on their own.

**Failure modes:** PR #1 introduces a model that nothing reads — so it's dead
code if PR #2 is delayed; UI shipped before backend, leaving broken buttons in
production; tests in PR #3 covering code merged in PR #1.

**Sources:**
- https://martinfowler.com/articles/feature-toggles.html
- https://www.harness.io/harness-devops-academy/feature-flags-in-production-safe-releases

---

## Candidate heuristics for FLS SDD (automated signals)

An automated check scanning a spec / plan can flag "split this" when:

1. **Estimated diff > 400 LOC.** Use plan task count × rough average per task,
   or a heuristic like `(new_models * 80) + (new_views * 60) + (new_templates *
   40) + (new_tests * 60)`. Above 400 → suggest split; above 800 → require split.

2. **More than one FLS app touched in a non-trivial way.** Touching
   `content_engine` + `student_progress` + `student_interface` is three apps;
   any spec hitting >= 3 apps should be sliced along app boundaries unless the
   change is genuinely a single thin vertical slice.

3. **Two or more new models OR a model with a new migration plus a new model.**
   Each new `models.py` addition is its own risk surface; pair with the migration
   alone unless it's truly atomic. Threshold: >= 2 new model classes → suggest
   model PR + behaviour PR.

4. **Both backend (models/views) AND frontend (templates/HTMX/Alpine) changes
   are present, with > 200 LOC on each side.** Split along the architectural
   seam: data/API PR, then UI PR (wired behind a feature flag if needed).

5. **Spec contains a new cross-app dependency.** If `plan_structure_review`
   would flag a new import edge between apps, that edge should be its own small,
   well-justified PR rather than buried in a feature PR.

6. **Spec mixes multiple INVEST-sized stories.** If the spec contains more than
   one user-visible verb ("educator can X", "student can Y"), each verb is its
   own vertical slice → its own PR.

7. **Risky change present alongside boilerplate.** Signals: edits to
   `accounts`, `app_authentication`, `site_aware_models`, any `auth`/`permission`
   files, OR any data migration that mutates rows (not just schema) — separate
   from any cosmetic/refactor work in the same spec.

8. **Spec's todo.md has > ~8 substantive tasks** (excluding QA/docs/cleanup).
   Each cluster of related tasks is a candidate PR; suggest a stack.

When >= 2 of these fire, recommend a split and propose the slice (skeleton →
behaviour → polish, or model → API → UI). When only 1 fires, single PR is
usually fine but call out the signal so the author can confirm.

---

## Sources (consolidated)

- [SmartBear/Cisco code review study](https://mikeconley.ca/blog/2009/09/14/smart-bear-cisco-and-the-largest-study-on-code-review-ever/)
- [Cisco code review case study (PDF)](https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf)
- [Modern Code Review at Google (Sadowski et al., ICSE 2018)](https://sback.it/publications/icse2018seip.pdf)
- [Expectations, Outcomes, and Challenges of Modern Code Review (Bacchelli & Bird, Microsoft, ICSE 2013)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/ICSE202013-codereview.pdf)
- [Google eng-practices: code review standard](https://google.github.io/eng-practices/review/reviewer/standard.html)
- [Graphite: ideal PR is 50 lines](https://graphite.com/blog/the-ideal-pr-is-50-lines-long)
- [Graphite: stacked PRs](https://graphite.com/blog/stacked-prs)
- [Graphite: stacked diffs guide](https://graphite.com/guides/stacked-diffs)
- [Awesome Code Reviews: stacked PRs](https://www.awesomecodereviews.com/best-practices/stacked-prs/)
- [Propel: PR size vs. review quality](https://www.propelcode.ai/blog/pr-size-impact-code-review-quality-data-study)
- [Agile Alliance: INVEST](https://agilealliance.org/glossary/invest/)
- [Mountain Goat Software: SPIDR](https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories)
- [Humanizing Work: guide to splitting user stories (Lawrence)](https://www.humanizingwork.com/the-humanizing-work-guide-to-splitting-user-stories/)
- [Lawrence: 10 patterns for splitting user stories](https://www.lagerweij.com/2010/10/20/patterns-for-splitting-user-stories-%E2%80%94-richard-lawrence/)
- [c2 wiki: Walking Skeleton](https://wiki.c2.com/?WalkingSkeleton=)
- [Matt Blodgett: Start with a Walking Skeleton](https://www.mattblodgett.com/2020/09/start-with-walking-skeleton.html)
- [Razkevich: drawing architectural boundaries](https://medium.com/@razkevich8/the-art-of-drawing-boundaries-mastering-decomposition-in-software-architecture-5f01a4148033)
- [Martin Fowler: Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)
- [LaunchDarkly: feature flags 101](https://launchdarkly.com/blog/what-are-feature-flags/)
