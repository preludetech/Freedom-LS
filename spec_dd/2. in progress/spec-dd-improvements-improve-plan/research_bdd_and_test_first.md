# Research: BDD, ATDD, and behaviour-first planning for the FLS spec-driven workflow

Scope: Should the FLS SDD workflow generate the QA plan **before** the implementation plan, optionally fronted by a BDD-style given/when/then "behaviour" description? Researched 2026-04-27.

## 1. BDD essentials — what's authoritative

BDD was coined by Dan North in the early 2000s and formalised in his 2006 *Better Software* article, "Introducing BDD". The Cucumber team's history page credits him with inventing JBehave in 2003 and developing the Given/When/Then template "to capture a story's acceptance criteria in an executable form", explicitly inspired by Eric Evans' ubiquitous language ([Cucumber: History of BDD](https://cucumber.io/docs/bdd/history/)). Martin Fowler's bliki entry frames Given/When/Then as a way of "specifying a system's behavior using Specification by Example" and warns that the Given is a *command* that sets state, not just narrative description ([martinfowler.com/bliki/GivenWhenThen.html](https://martinfowler.com/bliki/GivenWhenThen.html)).

What the canonical sources agree makes a *good* scenario:

- **One behaviour per scenario.** Cucumber's "Writing Better Gherkin" and the widely-cited Automation Panda guide both call this the cardinal rule: "any single When-Then pair denotes an individual behavior" and multiple When-Thens should become separate scenarios ([Cucumber: Writing Better Gherkin](https://cucumber.io/docs/bdd/better-gherkin/); [Automation Panda: Writing Good Gherkin](https://automationpanda.com/2017/01/30/bdd-101-writing-good-gherkin/)).
- **Single-digit step count.** Same sources: "scenarios should have a single-digit step count (<10)"; longer scenarios "often indicate poor practices".
- **Declarative, not imperative.** Cucumber: "describe the intended behaviour of the system, not the implementation… what, not how." A scenario that says "click the button" is wrong; a scenario that says "the learner submits the form" is right.
- **Examples come from collaboration, not a writing room.** Gojko Adzic's *Specification by Example* (Manning, 2011) frames the practice as seven patterns where the central one is *specifying collaboratively* — examples are the artefact of a Three-Amigos / Example Mapping conversation, not a deliverable an analyst types up alone ([Specification by Example](https://gojko.net/books/specification-by-example/); [Cucumber: Example Mapping](https://cucumber.io/blog/bdd/example-mapping-introduction/)).

Granularity rule of thumb from Cucumber's Example Mapping post: a well-sized story maps in ~25 minutes and produces a handful of *rules* (acceptance criteria) each with a couple of *examples* (concrete cases). If you can't, the story is too big.

## 2. Does behaviour-first / QA-first actually pay off?

Mostly yes, but the wins come from **clarification**, not test reuse. Adzic's 10-year retrospective on *Specification by Example* reports that teams using examples-as-acceptance-criteria saw 22% "great" quality ratings vs 8% for non-adopters, but his bigger finding is bracing: **57% of teams ended up storing specs in Jira rather than version-controlled feature files, and "living documentation" largely failed**. His updated guidance: "conversations [are] more important than capturing conversations [are] more important than automating conversations" ([SbE 10 years later](https://gojko.net/2020/03/17/sbe-10-years.html)).

The classic failure modes when behaviour-first is done badly are well documented:

- **Tool obsession over conversation.** Cucumber's own "10 easy ways to fail at BDD" lists this first: "BDD is more about collaboration than tooling" ([10 easy ways to fail at BDD](https://cucumber.io/blog/bdd/10-easy-ways-to-fail-at-bdd/)).
- **Scenarios written solo by one role.** Liz Keogh: when BAs pre-write scenarios alone, "conversations about alternatives stop happening, it becomes harder for the business to change their mind because of all the scenarios, and innovation is stifled" ([Shallow and Deep BDD](https://lizkeogh.com/2013/07/01/behavior-driven-development-shallow-and-deep/)).
- **Premature concretion / double maintenance.** Field reports collected on the Ranorex blog describe teams asked repeatedly to migrate Cucumber suites *back* to plain code: "engineers ended up writing and maintaining complex regex files… stakeholders rarely engage with Gherkin files, and the extra abstraction layer added maintenance burden without delivering real value" ([Ranorex: You Don't Need Cucumber for BDD](https://www.ranorex.com/blog/dont-need-cucmber-bdd/)).

Net: writing the QA/behaviour view first **does** pull design decisions forward (every TDD source repeats this — see [Wikipedia: TDD](https://en.wikipedia.org/wiki/Test-driven_development)), but it backfires when the artefact is treated as a deliverable to be polished rather than a thinking tool.

## 3. Lightweight given/when/then vs full Cucumber/Gherkin

The honest answer from the field: most teams that say they "do BDD" do not run executable Gherkin. Adzic's survey: 71% adoption of Given-When-Then *as a writing format*, but a third of those teams never automate it. The Ranorex piece argues the four things that actually matter — collaboration, agreed behaviour before implementation, readable scenarios, GWT structure — are achievable in plain text or plain pytest.

For Python/pytest projects there *are* Gherkin runners (`pytest-bdd`, `behave`) but they buy you a step-definition layer and a regex-glue tax. In a small team where the same person writes the spec and the test, that tax is pure overhead. Liz Keogh's "shallow BDD" — conversations + plain-prose scenarios captured wherever, no automation runner — is explicitly endorsed by her as legitimate BDD ([What is BDD?](https://lizkeogh.com/2015/03/27/what-is-bdd/)).

The sweet spot for a project that already has hand-written Playwright walkthroughs is **plain-markdown given/when/then bullets**, sized to the Example Mapping rule (rule + 1–3 examples), no Cucumber runner.

## 4. How BDD scenarios map to manual Playwright walkthroughs

Done well, these are the same artefact at different zoom levels. A behaviour scenario says *"Given an enrolled learner, when they submit a quiz, then their progress updates"*; the Playwright walkthrough says *"navigate to /courses/x, click Start Quiz, fill answers, click Submit, expect progress = 100%"*. The first is the **rule**; the second is the **example trace**. testomat.io and Department of Product both note that well-written scenarios "are requirements, acceptance criteria, test cases, and test scripts all in one" ([Department of Product: Writing BDD Test Scenarios](https://www.departmentofproduct.com/blog/writing-bdd-test-scenarios/); [testomat.io: BDD test cases](https://testomat.io/blog/writing-bdd-test-cases-in-agile-software-development-examples-best-practices-test-case-templates/)).

Risk: if both artefacts are kept verbatim, you have duplication. The mitigation Cucumber recommends — Background steps and Scenario Outlines — only helps inside a Gherkin runner. In our setup the cleaner mitigation is to make the BDD layer **strictly declarative** (says *what*, never *which button*) and let the Playwright walkthrough be the only place mechanics live.

## 5. Recommendation for FLS

**Generate the QA plan before the implementation plan, yes. Front it with a short behaviour section, but keep it lightweight.** Specifically:

1. **Behaviour section first** in the QA-plan document — 3–8 plain-markdown bullets per feature in the form *"Given X, when Y, then Z"*, declarative, no UI mechanics. Source the wording directly from the spec's user-facing requirements; this is the "rule" layer from Example Mapping. Cap each scenario at single-digit steps. This is your acceptance-criteria contract with the user, and it forces the LLM to commit to *what done looks like* before it commits to *how*.

2. **Playwright walkthrough second**, in the same document — the existing hand-written trace, but explicitly tagged as *the example* for one or more behaviour rules above. One walkthrough may cover several rules; that's fine and reduces duplication.

3. **Do not introduce Gherkin tooling, pytest-bdd, or behave.** All three Cucumber/Adzic/Keogh sources converge on the warning that the tool is the smallest part of the value, and for a single-developer-plus-Claude project the regex-glue tax is pure cost. Plain markdown given/when/then is what 71% of "BDD" teams actually use anyway.

4. **The user reviews the behaviour bullets, not the walkthrough.** That's where misunderstandings get caught cheaply. The walkthrough is a derivable artefact — the planning agent regenerates it if the rules change, so it's not double-maintenance.

5. **The implementation plan, written next, must reference behaviour-rule IDs.** This gives the structure/security review subagents a stable contract to check against, and means the implementer can tick off rules as they go — exactly the design-feedback loop test-first proponents claim ([TDD overview](https://en.wikipedia.org/wiki/Test-driven_development)).

The thing this *does not do* and shouldn't try to do: replace conversation. Adzic and Keogh are unanimous that BDD without a real interlocutor degrades into ceremonial documentation. In an LLM-driven workflow the human review of the behaviour bullets is the conversation; protect that step and the rest works.

## Sources

- [Cucumber: History of BDD](https://cucumber.io/docs/bdd/history/)
- [Cucumber: Writing Better Gherkin](https://cucumber.io/docs/bdd/better-gherkin/)
- [Cucumber: Example Mapping](https://cucumber.io/blog/bdd/example-mapping-introduction/)
- [Cucumber: 10 easy ways to fail at BDD](https://cucumber.io/blog/bdd/10-easy-ways-to-fail-at-bdd/)
- [Martin Fowler: Given When Then](https://martinfowler.com/bliki/GivenWhenThen.html)
- [Gojko Adzic: Specification by Example, 10 years later](https://gojko.net/2020/03/17/sbe-10-years.html)
- [Gojko Adzic: Specification by Example (book page)](https://gojko.net/books/specification-by-example/)
- [Liz Keogh: Behavior-Driven Development – Shallow and Deep](https://lizkeogh.com/2013/07/01/behavior-driven-development-shallow-and-deep/)
- [Liz Keogh: What is BDD?](https://lizkeogh.com/2015/03/27/what-is-bdd/)
- [Automation Panda: BDD 101 — Writing Good Gherkin](https://automationpanda.com/2017/01/30/bdd-101-writing-good-gherkin/)
- [Ranorex: You Don't Need Cucumber for BDD](https://www.ranorex.com/blog/dont-need-cucmber-bdd/)
- [Department of Product: Writing BDD Test Scenarios](https://www.departmentofproduct.com/blog/writing-bdd-test-scenarios/)
- [testomat.io: BDD Testing — Best Practices and Examples](https://testomat.io/blog/writing-bdd-test-cases-in-agile-software-development-examples-best-practices-test-case-templates/)
- [Wikipedia: Test-driven development](https://en.wikipedia.org/wiki/Test-driven_development)
