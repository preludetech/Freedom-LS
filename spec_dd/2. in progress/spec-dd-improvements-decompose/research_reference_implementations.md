# Spec Decomposition: Reference Implementations

Survey of how other spec-driven development (SDD) workflows handle decomposing a single large spec into multiple coordinated specs/PRs. Conducted as input to improvements for the FLS `idea -> spec -> plan -> implement -> PR` workflow.

---

## 1. GitHub Spec Kit

**URL:** <https://github.com/github/spec-kit>

Spec Kit is single-spec-per-feature. Specs live at `.specify/specs/<feature-id>/{spec.md, plan.md, tasks.md, contracts/}`. `/speckit.tasks` decomposes a spec into a task list, but does **not** spawn child specs. No "spec splitter" command, no hierarchy on disk, no inter-spec dependency manifest. Splitting is manual: run `/speckit.specify` again per child feature.

**Decision point:** human, before `/speckit.specify`. **Tracking:** none built-in. Community extensions ("Feature Forge", "Worktree Isolation") add parallel work but don't shard specs.

---

## 2. Kiro (Amazon)

**URLs:** <https://kiro.dev/docs/specs/>, <https://kiro.dev/docs/specs/best-practices/>

Kiro produces specs in three phases: requirements (EARS-style) → design → tasks. Best-practice docs explicitly say: *"We recommend creating multiple specs for different features for your project rather than attempting to just have a single one."* Recommended pattern: a **Design-First spec** to validate feasibility, then separate **Requirements-First specs** for the actual feature work. Specs reference each other via the `#spec` context provider in chat (manual prose link).

No `split` command, no parent/child layout, no machine-readable dependency graph between specs. Sequencing lives inside each spec's task list, not across siblings. Decomposition heuristic: "align specs to bounded contexts/feature domains."

**Decision point:** human, at idea-capture time. **Tracking:** prose links via `#spec`.

---

## 3. BMAD-METHOD

**URLs:** <https://docs.bmad-method.org/tutorials/getting-started/>, <https://docs.bmad-method.org/how-to/shard-large-documents/>, <https://github.com/bmad-code-org/BMAD-METHOD/issues/1471>

The most concrete reference. BMAD's pipeline is `Analyst -> PM (PRD) -> Architect -> Scrum Master -> Dev -> QA`. The decomposition step is **epic sharding**, executed by the `/bmad-shard-doc` command. It splits a markdown document along `## level-2 headings` into a folder of child files:

```
prd.md  ->  prd/
              index.md            # auto-generated TOC
              overview.md
              user-requirements.md
              technical-requirements.md
              ...
```

A "dual discovery system" lets downstream agents look up either `name.md` or `name/index.md` and prefer whichever exists. After sharding, `create-epics-and-stories` turns each epic shard into a "hyper-detailed" story file with embedded architecture context.

Issue #1471 proposes a further split: when a story's task list exceeds a token threshold, auto-split into `Story-3.2a`, `Story-3.2b`, ... and execute sequentially. The only proposal found that explicitly defines a **token/complexity heuristic** plus a **suffix naming convention** for sub-specs.

**Decision point:** Sharding is explicit, post-PRD. Story-level decomposition is proposed to be threshold-driven. **Tracking:** disk hierarchy + the parent `index.md` TOC. No cross-epic dependency manifest.

---

## 4. CCPM (Claude Code Project Management)

**URL:** <https://github.com/automazeio/ccpm>

The most explicit dependency-tracking design I found. CCPM is a Claude Code skill that turns a PRD into an epic and then breaks the epic into task files (default cap **<=10 tasks per epic**). Disk layout:

```
.claude/epics/<feature>/
  epic.md
  001.md, 002.md, ...        # tasks; renamed to GitHub issue IDs after sync
  <issue-id>-analysis.md     # parallel work-stream analysis
  updates/
```

Each task file has frontmatter:

- `depends_on: [<task-id>, ...]` — prerequisites
- `parallel: true` — eligible for concurrent execution
- `conflicts_with: [...]` — incompatible parallel work

After GitHub sync, files are renamed to match issue numbers, and parent/child is enforced via the `gh-sub-issue` extension (with task-list fallback). The cleanest example of a **per-spec dependency manifest** found; `parallel: true` directly answers "can these ship as parallel PRs?".

**Decision point:** at the epic-decomposition step, agent-driven, with a hard task-count cap. **Tracking:** frontmatter + GitHub sub-issue graph.

---

## 5. Tessl

**URLs:** <https://docs.tessl.io/use/spec-driven-development-with-tessl>, <https://tessl.io/blog/spec-driven-development-10-things-you-need-to-know-about-specs/>

Tessl pushes a strong **1:1 mapping between spec file and code file** ("spec-anchored"). Decomposition is baked into the layout: large features fan out because each code file gets its own spec. The **Spec Registry** lets you install spec packages as project dependencies (npm-style), so cross-spec dependencies become a package-manager problem rather than a hand-rolled manifest. No "split this big spec" command; philosophy is to grow many small specs from the start.

**Decision point:** at file-creation time (one spec per intended file). **Tracking:** registry/package-manager metaphor.

---

## 6. Claude Code (native skills + Task tool)

**URLs:** <https://code.claude.com/docs/en/skills>, <https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>

Claude Code itself has no first-class "spec" object, but its conventions are relevant:

- **Skill decomposition (progressive disclosure):** keep `SKILL.md` under ~500 lines; when it grows, split into a `references/` directory and link out. Same heuristic — "fits in context" — that BMAD applies to PRDs.
- **Task tool (Jan 2025 update):** stores tasks on disk as a DAG with parent-child task hierarchies, `addBlockedBy` dependencies, and statuses. Used at task level, not spec level, but the data model (DAG + blockedBy) is the obvious shape for tracking spec sequencing too.

**Decision point:** prose-rule "if approaching 500 lines, split." **Tracking:** filesystem links (skills) or task DAG.

---

## 7. Cursor / Windsurf

**URLs:** <https://skywork.ai/blog/vibecoding/cursor-2-0-vs-windsurf/>

Neither has a public spec-decomposition feature. Cursor 2.0 / 2.4 added Background Agents and Subagents that can run concurrently across separate branches and open separate PRs, and "Mission Control" to view them — but the splitting is at execution time, driven by the user delegating to N agents, not at spec-authoring time. Windsurf's roadmap mentions a multi-agent "Cascade 2.0" with similar shape. **Looked at; no spec-splitting model.**

---

## 8. OpenAI Codex / Devin / Aider

**URLs:** <https://developers.openai.com/codex/subagents>, <https://cookbook.openai.com/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk>

Codex documents a multi-agent pattern (PM -> Designer -> Frontend -> Backend -> Tester) where the PM agent breaks a task list into sub-tasks and gates handoffs. This is **task** decomposition, not spec decomposition — no persisted spec artifact, no parent/child folder, no formal dependency file. Aider has no spec lifecycle at all (operates on diffs). **Looked at; not relevant beyond the multi-agent metaphor.**

---

## 9. EARS / classical RE

**URLs:** <https://alistairmavin.com/ears/>, <https://www.iaria.org/conferences2013/filesICCGI13/ICCGI_2013_Tutorial_Terzakis.pdf>

EARS is a syntax for individual requirements (`While <pre>, when <trigger>, the <system> shall <response>`), not a decomposition methodology. "Complex requirements" combine multiple EARS keywords, but EARS itself doesn't mandate hierarchy. Relevance: EARS-formatted requirements are mechanically easier for an agent to peel apart into independently testable units, feeding whatever splitter you build on top. **Not a workflow; a useful upstream constraint.**

---

## 10. Arcturus Labs / Thoughtworks commentary

**URLs:** <http://arcturus-labs.com/blog/2025/10/17/why-spec-driven-development-breaks-at-scale-and-how-to-fix-it/>, <https://thoughtworks.medium.com/spec-driven-development-d85995a81387>

Arcturus argues for a **hierarchical, file-rolled-up** layout: one spec per code file, then a rolled-up spec per directory, all the way to a global spec. No tooling, no automation — but it's a coherent on-disk shape for parent/child specs. Thoughtworks' guidance is the recurring "meaningful decomposition" rule: each child spec should deliver standalone user value, not just be an arbitrary technical slice.

---

## Patterns observed

1. **Two timing camps.** (a) *Up-front, at idea/spec-writing time* — Kiro, Tessl, Spec Kit, Arcturus. The human decides "this is multiple specs" before writing them. (b) *Mid-pipeline, automatic* — BMAD's `/bmad-shard-doc` after the PRD is drafted; CCPM when an epic exceeds 10 tasks; BMAD issue #1471 when story tasks exceed a token threshold. **No tool splits during the implementation phase** — by then it's too late.

2. **The dominant heuristic is "fits in the agent's context window."** BMAD shards by `##` headings; Claude skills cap at ~500 lines; CCPM caps at 10 tasks; issue #1471 proposes token thresholds. Secondary heuristic is "delivers standalone user value" (Thoughtworks, Kiro's bounded-context advice). These two combined are probably what FLS wants: split if the spec is too big for one PR review *and* the parts are independently valuable.

3. **Disk shape: parent folder with `index.md`** is the most common convention (BMAD, CCPM). The parent file becomes a TOC/manifest; children sit beside it. Tessl's flatter spec-per-file is the alternative.

4. **Dependency tracking — frontmatter wins.** CCPM's `depends_on` / `parallel` / `conflicts_with` keys in YAML frontmatter is the cleanest model found, and directly answers "can these ship as parallel PRs?". Kiro and Spec Kit use prose references with no machine-readable graph. A separate `sequence.md` / `manifest.yml` (as the FLS idea suggests) is plausible but rarer in the wild — most tools push the metadata into each child rather than a sidecar file. Either works; co-locating with each child spec makes it harder to drift out of sync, while a single sidecar makes the order easier to read at a glance.

5. **Naming conventions for siblings.** BMAD issue #1471's `Story-3.2a, Story-3.2b` suffixes; CCPM's numeric `001.md, 002.md` (then renamed to GitHub issue IDs). Numbering implies order; suffixes imply siblings of one parent.

6. **Almost no one auto-detects "this should be split."** It's either a human gut call or a hard cap (token count, task count, line count). For an FLS-shaped workflow, the cheapest first cut is probably a `/spec_review`-time check — a human-in-the-loop step asking "is this one PR or many?" — backed by a soft heuristic on spec length and a small structured manifest (CCPM-style frontmatter, in either each child spec or a single `sequence.md`).

7. **Decomposition step lives between spec and plan.** Kiro/BMAD/CCPM all put it after requirements/PRD are stable but before per-task planning. That maps cleanly onto inserting a "split?" decision after `spec_from_idea` and before `plan_from_spec` in the FLS pipeline, rather than during idea capture or planning.
