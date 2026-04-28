# Research: When to decide "should this be split into multiple PRs?"

Context: SDD workflow stages are idea -> spec -> plan -> implement -> PR. The
question is where the split-check belongs.

## Background from the literature

- **INVEST / Mike Cohn**: stories must be "small enough" — ~6-10 per sprint —
  but Cohn warns that one of the top three reported pains for agile teams is
  "spending too much time trying to split stories in a meaningful way at the
  cost of building something." Splitting is expected to happen *iteratively*
  via SPIDR (Spike, Path, Interface, Data, Rules) as teams learn more, not as
  a single up-front act.
  ([Mountain Goat — SPIDR](https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories),
  [Mountain Goat — five mistakes](https://www.mountaingoatsoftware.com/blog/five-story-splitting-mistakes-and-how-to-stop-making-them))

- **Patton (User Story Mapping)**: the map exposes "logical and releasable
  slices" only after the user journey is laid out — slicing is downstream of
  understanding the whole story. Release lines are drawn on the map, not on
  the raw idea.
  ([Open Practice Library](https://openpracticelibrary.com/practice/user-story-mapping/),
  [jpattonassociates](https://jpattonassociates.com/the-new-backlog/))

- **Kanban / Lean**: "right-sizing" matches item size to cadence, but
  ProKanban argues sizing should be probabilistic from historical data rather
  than something you obsess over up front. Splitting is a continuous flow
  concern, not a milestone gate.
  ([ProKanban](https://www.prokanban.org/blog/https-prokanban-org-p-8115),
  [Kanban University](https://edu.kanban.university/blog/estimating-kanban))

- **Cagan / Torres (Discovery vs. Delivery)**: discovery answers WHY/WHAT and
  decomposes *risk* (value, usability, feasibility, viability); delivery
  decomposes *implementation*. They are different decompositions over the
  same idea — confusing them is a known anti-pattern.
  ([SVPG](https://www.svpg.com/discovery-vs-delivery/))

- **Spec Kit & Kiro (real SDD workflows)**: both decompose *late*. Spec Kit
  has six stages (Initialize -> Constitution -> Specify -> Plan -> Tasks ->
  Implement); the split into discrete tasks happens at "Tasks", after
  Specify and Plan. Kiro likewise produces "an implementation plan with
  discrete tasks, sequenced based on dependencies" only after requirements
  and design are stable.
  ([Spec Kit](https://github.com/github/spec-kit/blob/main/spec-driven.md),
  [Kiro](https://kiro.dev/))

- **Google eng-practices on small CLs**: explicitly recommends splitting
  *during implementation* via either layered (proto / service / client) or
  vertical (full-stack feature) cuts. ~100 lines is "reasonable", >1000 is
  "usually too large".
  ([eng-practices/small-cls](https://google.github.io/eng-practices/review/developer/small-cls.html))

- **Amazon Working Backwards / PR-FAQ**: the PR-FAQ is intentionally fuzzy
  about delivery shape; only after it stabilises does the team draft epics,
  user stories and a roadmap.
  ([workingbackwards.com](https://workingbackwards.com/concepts/working-backwards-pr-faq-process/))

- **Cost asymmetry**: a Cambridge study found ~13x more activities to fix a
  *concept-phase* defect after system test than to fix it in concept. By
  contrast, premature micro-decomposition is the classic
  premature-optimisation trap — cheap to defer, expensive only when wrong.
  ([Cambridge — early vs late design decisions](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/10B13C6901E51E7F6337250A9CA36E17/S2053470117000130a.pdf/relative_impact_of_early_versus_late_design_decisions_in_systems_development.pdf),
  [Ubiquity — premature optimisation](https://ubiquity.acm.org/article.cfm?id=1513451))

- **PR-size data**: PRs <200 LOC merge ~3x faster; PRs >1000 LOC have ~70%
  lower defect detection. The bar for "must split" is empirically low.
  ([Propel — PR size study](https://www.propelcode.ai/blog/pr-size-impact-code-review-quality-data-study),
  [Graphite](https://graphite.com/guides/best-practices-managing-pr-size))

## The three candidate moments

### 1. Idea time

- **Artifacts available**: a rough problem statement, maybe a user. No
  acceptance criteria, no architecture, no file list.
- **Pros**: cheapest possible kill — "this is two ideas in a trench coat"
  catches multi-product framings before any spec work is wasted. Encourages
  Patton-style release-vs-development thinking early.
- **Cons**: nothing concrete to size against. Splits decided here often
  recombine after the spec, or fragment into specs that don't compose. Cohn
  explicitly flags "spending time splitting at the cost of building" as a
  top-three pain.
- **Confidence in a decomposition decision**: low. Good for *gut* checks
  ("is this one outcome or many?"), bad for boundaries.
- **Quote**: Cagan — discovery decomposes *risk*, not implementation; doing
  delivery-style splits at idea time mixes the two.

### 2. Spec time

- **Artifacts available**: user stories / acceptance criteria, scope, edge
  cases, sometimes data shape. No architecture or task list.
- **Pros**: this is where Patton's story-mapping and Cohn's SPIDR are
  designed to operate. "Smallest releasable slice" becomes answerable. You
  can spot multi-actor, multi-path or multi-data-type stories that should be
  separate specs.
- **Cons**: implementation-shaped splits (refactor-then-feature; migration
  before code; touches three apps) aren't yet visible. A spec-time split can
  miss a hidden cross-cutting refactor that *must* land separately.
- **Confidence in a decomposition decision**: medium-high for *user-visible*
  slicing; low for *PR-shape* slicing.
- **Quote**: Patton — "find the smallest successful release… the least that
  could be released that people could use and find really useful." That is a
  spec-time question, not an idea-time one.

### 3. Plan time

- **Artifacts available**: architecture, file/module list, dependency order,
  migration steps, test surface, sometimes a phase breakdown.
- **Pros**: this is the only stage where Google-style layered (proto ->
  service -> client) and vertical (full-stack feature) splits are visible.
  Spec Kit and Kiro both *defer task decomposition to here* deliberately.
  A 5-phase plan is a near-mechanical signal of 5 PRs.
- **Cons**: late. If the right answer is "this should have been two specs",
  unwinding spec/plan work is expensive — Cambridge's 13x figure is the
  worst case of leaving structural splits this late.
- **Confidence in a decomposition decision**: highest for PR boundaries;
  weak for "is this the wrong scope entirely?" (that ship sailed at spec).
- **Quote**: Google — "split up your code into smaller, full-stack, vertical
  features… each of these features can be independent parallel
  implementation tracks." That is a *plan-time* observation about code, not
  an idea-time one about scope.

## Recommendation: split-check at all three stages, but ask different
questions

The literature converges on a single pattern: **decomposition happens
multiple times, with different questions each time.** No serious workflow
(Spec Kit, Kiro, Patton, Working Backwards) does it only once.

Concretely for FLS's SDD pipeline:

1. **Idea time — cheap heuristic only.** Single question: "is this one
   outcome or several distinct outcomes?" If several, fork into separate
   ideas *now* — don't wait. Do not attempt PR-shape decisions. This is
   Cagan's "is this even one bet?" gate.

2. **Spec time — releasable-slice check (the substantive one).** Use Patton
   / Cohn SPIDR. Question: "what is the smallest user-visible slice that's
   independently valuable?" Output may be: split into multiple specs, mark a
   later spec as a follow-up, or confirm one spec. This is where most
   *scope* splits should land, because the cost of fixing scope here is
   roughly an order of magnitude lower than fixing it at plan or
   implement time.

3. **Plan time — PR-shape check (mechanical).** Question: "does the plan
   show distinct phases / layers / migrations that should land in separate
   PRs?" Signals only visible here: (a) plan has >N phases; (b) a refactor
   precedes the feature; (c) a data migration is independent; (d) the
   change touches >1 app boundary; (e) estimated diff exceeds the team's
   PR-size threshold (the data says ~400 LOC is the inflection point).
   Splits here produce *PR-level* not spec-level boundaries.

### Caveats

- The cheap idea-time check is *only* worth its cost if it's seconds, not
  minutes. Make it a single yes/no prompt, not a discovery exercise — Cohn's
  warning about over-splitting applies most strongly here.
- The spec-time check should defer PR-mechanics ("this will be a 600-line
  diff") because that information genuinely doesn't exist yet; trying to
  answer it at spec time is BDUF in miniature.
- Plan-time splits sometimes reveal a *spec-level* problem ("this plan can't
  hang together as one feature"). Treat that as a signal to loop back to
  spec, not to push through. The 13x cost figure is the cost of *not*
  looping back.
- For trivial work (one app, one model, <200 LOC estimate), all three checks
  should short-circuit to "no". Right-sizing is not the same as
  same-sizing — ProKanban's distinction matters here.

### Signals only visible late

These should explicitly belong to plan time, not earlier:

- "the plan shows N distinct phases" -> N PRs
- "step 1 is a refactor with no user-visible behaviour change" -> separate
  PR (Graphite/Codacy: detach refactor from feature)
- "step 2 is a data migration" -> separate PR
- "this touches `accounts` *and* `student_management` *and* `content_engine`"
  -> consider layered split
- "estimated diff >400 LOC" -> mandatory split per the empirical PR-size
  data

Sources are inline above.
