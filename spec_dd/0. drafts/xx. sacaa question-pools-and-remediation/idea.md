# SACAA question pools: randomisation + active remediation

Two quiz-related SACAA-driven needs that share a common primitive and should be built together.

## Problem

1. **Randomisation.** For some quizzes, the author should define a *bank* of questions; each learner attempt should see a random subset, not the full set in fixed order.
2. **Remediation.** When a learner gets a question wrong, the current behaviour (optionally reveal the correct answer) is not sufficient. Learners skim it, memorise the reveal, and learn little. We want an *active* remediation loop that explains *why* and supports a meaningful retry.

Both features depend on the same missing primitive in the content model: grouping questions into **pools**. Building them as one initiative avoids defining that primitive twice.

## Regulatory framing (honest)

- SACAA does **not** publish a clause that literally says "LMSs must implement active remediation after a wrong formative-quiz answer". The regulatory hook is indirect:
  - SA-CAR Part 141 / SA-CATS 141 govern ATOs and the training they deliver.
  - SACAA (as an ICAO contracting State) inherits **Competency-Based Training and Assessment** from ICAO Doc 9868 (PANS-TRG) and Doc 9941, which treats formative feedback that "identifies gaps as learning opportunities" as a required property of the training system.
- For **randomisation**, the expectation that examination items be drawn from a bank is SACAA/ICAO-standard examination practice; the same pattern is reasonable for ATO-delivered formative assessments.
- **Do not** claim "SACAA mandates active remediation" in product copy or compliance conversations — the honest framing is "aligns with ICAO CBTA principles and prepares learners for SACAA Part 61 examinations."
- Primary SACAA text (SA-CAR 141 / SA-CATS 141, 2021 replacements) was not text-extractable during research. A human should read those directly before any regulator-facing claim is finalised.

See `research_sacaa_requirements.md` for the full, tagged version (`[Verified] / [Reported] / [Unverified]`).

## Shared primitive: the question pool

The mental model both features plug into:

- A **question pool** is an authored group of questions that test the same concept / knowledge item. Questions in a pool are *isomorphic* — structurally equivalent, different surface details.
- A quiz is authored as a sequence (or set) of pool references, not a flat list of questions.
- At attempt time:
  - **Randomisation**: pick one question from each pool (and/or pick N pools from a larger set).
  - **Remediation retry**: when the learner gets a question wrong, pick a *different* question from the same pool for the retry — never the same item, to prevent rote memorisation of the reveal.

This is consistent with how Moodle, Articulate, and aviation CBTs (Gleim, King, Sporty's) structure their banks. It is also what makes remediation retries pedagogically honest.

## V1 scope

### In scope

1. **Question pools** as a content-authoring primitive. Existing quizzes keep working; pools are opt-in.
2. **Randomised selection** from a pool at quiz-attempt time. Per-learner-stable selection (re-loading does not reshuffle mid-attempt).
3. **Per-option elaborative feedback** — authors write a short explanation per answer option (wrong and correct) saying *why*. Rendered inline at the wrong-answer moment, not at end-of-quiz only.
4. **Source-content link** — each question (or pool) can link to the relevant topic/section in the course. Aviation learners specifically expect citation to the governing regulation / source.
5. **Forced re-engagement before retry** — learner must acknowledge the explanation (cheap: a "Continue" click), not silently skip.
6. **Retry with a different question from the same pool** (isomorphic variant).
7. **Configurable mastery gating** (opt-in per quiz). Two modes:
   - *Legacy*: `quiz_pass_percentage` gates the form (current behaviour).
   - *Mastery-per-pool*: learner must eventually get each pool correct to pass. Attempt caps and escalation behaviour need spec decisions.
8. **Educator visibility** — basic surface so educators can see learners stuck in repeated-failure on a pool. (Scope of this surface to be nailed down in the spec.)

### Explicitly deferred (later iterations)

- Prerequisite-content branching on second failure.
- Spaced re-test / cross-session mistakes review hub (Duolingo-style).
- AI-generated "Explain My Answer" fallback when an author hasn't written per-option feedback.
- Adaptive difficulty.
- Exam-level proctoring integration (lives in other specs).

## Design directions (to be firmed up in the spec)

Flagging choices that affect the model layer so the spec author picks deliberately:

- **Pool granularity.** Is a pool a flat list of questions, or does it carry metadata (concept name, source link, mastery threshold)? Lean: metadata on the pool, not duplicated on each question.
- **Authoring in markdown.** Current quizzes live as cotton components in markdown (`demo_content/...`). Pool authoring needs a markdown-friendly syntax that doesn't explode a file.
- **Per-attempt records.** Currently `QuestionAnswer` has no attempt counter. Mastery gating and educator surfacing both need attempt-level data. Model change required.
- **Randomisation seeding.** Probably seeded by `(FormProgress, pool)` so reloads are stable. Decide whether a retry re-seeds or draws "next unseen variant".
- **Retry question ordering.** Does the failed pool re-appear immediately, at end of attempt (Duolingo), or next session? Lean: end of attempt for V1.
- **Attempt caps.** Mastery mode needs a cap (or the loop is infinite). Spec should propose a default + an author-overridable setting.

## Anti-goals (informed by UX research)

- No patronising or punitive tone ("Wrong! Try again!").
- No wall-of-text feedback; cap the authored explanation to a few sentences with optional expansion.
- No verbatim re-ask of the same question (defeats the purpose).
- No infinite answer-until-correct loop — always have an escape hatch and an escalation path.
- No heart-style punishment mechanics.

## Research pointers

- `research_sacaa_requirements.md` — what SACAA / ICAO actually require vs what is industry best practice. Claims are tagged `[Verified] / [Reported] / [Unverified]`.
- `research_pedagogy.md` — evidence base for remediation design (Hattie, Shute, Van der Kleij, Roediger & Karpicke).
- `research_ux_patterns.md` — Khan Academy, Duolingo, Moodle, Articulate, and aviation-CBT (Gleim/King/Sporty's) remediation UX patterns, plus documented learner complaints.

## Open items for the spec phase

1. Exact markdown authoring syntax for pools.
2. Data-model decisions (new `QuestionPool` model? `FormQuestion.pool` FK? attempt records?).
3. Educator-interface surface scope: dashboard vs. per-cohort report vs. just a flag on existing progress views.
4. Mastery-gating defaults: attempt cap, what "pass" means when some pools are never mastered.
5. Interaction with existing `quiz_show_incorrect` flag — keep, deprecate, or replace.
6. Upgrade claims in `research_sacaa_requirements.md` by reading SA-CAR 141 / SA-CATS 141 primary text.
