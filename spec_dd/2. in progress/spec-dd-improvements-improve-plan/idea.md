# Idea: Less-interactive plan phase

## Problem

The plan phase of the SDD workflow currently spans three slash commands (`/plan_from_spec`, `/plan_security_review`, `/plan_structure_review`) and asks the user to address callouts between each one. Three context-switches per spec is too much friction. The structural / security / testing-practice reviews don't need a user gate between them — they need to land their findings somewhere the user can act on at the end.

## Direction

Split the plan phase into **two commands**. Frontload *what we're building* (behaviour) before *how we'll build it* (mechanics), and let the dev-plan command run all reviews internally.

### `/plan_qa` — runs first

Generates the QA plan from the spec. The output is `3. frontend_qa.md` (same name and basic shape as today), with one addition:

- An optional **behaviour-rule section** at the top: 3–8 plain-markdown given/when/then bullets per feature, declarative ("the learner sees their progress update", not "click the Submit button"). Sourced from the spec's user-facing requirements.
- Beneath that, the existing **Playwright walkthrough**, explicitly tagged as the example trace for the rules above.
- **No Gherkin tooling.** No Cucumber, no pytest-bdd, no behave — plain markdown only. The tax isn't worth it. See `research_bdd_and_test_first.md`.
- The whole document is **skippable**: if the feature has no frontend and no useful manual QA path, no QA plan is generated (same rule as today).
- **Invisible side effects still get minimal QA**: if the frontend isn't visibly affected but a frontend interaction is meant to trigger backend behaviour (a side effect not visible to the user), include a minimal walkthrough that verifies the side effect happens as expected.

The user reviews this document. The behaviour bullets are where misunderstandings get caught cheaply — before the dev plan commits to mechanics.

### `/plan_dev` — runs second

Takes the spec and the QA plan (if there is one) and produces `2. plan.md`. Internally, no user gate between steps:

1. **First-pass plan** drafted by the orchestrator.
2. **Reviewer subagents run sequentially** in this order: **testing-practices → structure → security**. Order matters: testing changes task shape; structure looks at where code lives across those tasks; security audits the final shape. Sequential (not parallel) to avoid reviewers undoing each other's edits ("Logic Lock"). See `research_multi_agent_review.md`.
3. **Reviewers flag, the orchestrator edits.** Reviewers never edit `2. plan.md` directly — they emit findings, the orchestrator applies fixes that are mechanical and unambiguous, and turns judgement calls into callouts. (Same "architect / editor" split Aider and obra/superpowers use.)
4. The three reviewers are existing standalone commands (`/plan_security_review`, `/plan_structure_review`, plus a new `/plan_testing_review`), invoked as subagents. They stay runnable on their own so the user can re-review after editing the plan manually.
5. **Mid-flow user input only for blockers** — a reviewer finding that would invalidate downstream reviewers' work, or contradictions in the spec. Everything else batches to the end.

## Surfacing decisions and concerns

Two distinct things happen during planning: **decisions** get made, and **concerns** get raised. They're surfaced differently.

- **Decisions** (auto-decided judgement calls, user-confirmed answers, open questions) live as inline GitHub-alert callouts at the point they apply, with an auto-generated index at the top of `2. plan.md`:
  - `[!IMPORTANT]` — user-confirmed (skim past)
  - `[!WARNING]` — auto-decided (must eyeball)
  - `[!NOTE]` — open question (must answer before plan freeze)

  See `research_decision_logging.md`.

- **Concerns** from reviewers go in three buckets, named in human language: **Must address / Should consider / FYI**. Only "Must address" gets an inline callout in the plan; "Should consider" and "FYI" live in a `## Reviewer findings` section at the bottom. No P0/P1/P2 — numeric severity inflates. See `research_concern_triage_ux.md`.

- **End-of-flow terminal summary**: counts per bucket, a "what I changed already" block, a numbered "decisions needed from you" list with proposed answers, and a short "worth considering" tail. The user reads ~10 lines and knows exactly what's done, what blocks them, and what's optional.

## Out of scope

- **Replacing the conversation.** The QA-plan review checkpoint *is* the conversation BDD-without-tooling depends on. Protect that step; everything downstream relies on it.
- **Replacing the standalone review commands.** `/plan_dev` calls them as subagents, but they remain first-class commands the user can run on their own.
- **Living documentation / executable specs.** We're not adopting Gherkin runners or auto-syncing scenarios with code. Plain-text BDD as a *thinking tool*, not a deliverable.

## Research

- `research_bdd_and_test_first.md` — why lightweight BDD, why no Gherkin tooling.
- `research_multi_agent_review.md` — sequential reviewers, architect/editor split, Logic Lock.
- `research_decision_logging.md` — inline GitHub alerts + index, three callout kinds.
- `research_concern_triage_ux.md` — three buckets, end-of-flow summary, when to interrupt.
