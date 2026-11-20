# Research: prior art for spaced-repetition revision of quiz questions

Topic `prior_art`. Tags: [R] sourced (path or URL), [I] my inference. Spec dirs below are under `spec_dd/`.
Method: read the listed idea/research files; Grep over all of `spec_dd/` and `docs/`; four standard web searches (2026-11-20). The search tool returns summaries, so outcome evidence is thin and is flagged where so.

## A. In this repo: nothing has been built or tried

- [R] No spec in `1. next`, `2. in progress` or `3. done` built a revision, spaced-repetition or retake-practice feature. Grep hits for "revision" in done specs are about content or report revision (e.g. `3. done/2026-08-21_20:12_basic_reports/research_quiz_item_analysis.md`: "flag for revision" on item-analysis output), not learner revision. `docs/` has no revision or spaced-repetition page; `docs/product/reports.md:48` only says cohort "most wrong" analysis uses each learner's first completed attempt, because retakes let learners remember answers.
- [R] No `compliance-form-randomization` directory exists any more (Glob found nothing). Its shuffle work lives in `2. in progress/sacaa-compliance-2-shuffle/`.
- [R] `3. done/2026-06-18_14:35_more_course_widgets/` shipped the static `c-flashcard` widget (research_flashcard_ux.md). It stores nothing and has no scheduling. Roadmap line 265 confirms: "until scheduled flashcards land, courses practise with the static `c-flashcard` widget". No Grep hit for spaced/Leitner/confidence in its spec.
- [I] So this spec is the first attempt in FLS. The only precedents are decisions in sibling specs, below.

## B. Decisions in sibling specs that constrain this one

### Done: `3. done/2026-11-18_15:43_learner-interface-features-1-question-sections/1. spec.md`
- [R] A section is a `CoursePart` or a `Topic` (Decision 1). A question may name several (2). Stored as two M2M through tables in `content_engine`, reached from `FormQuestion` by reverse accessors `topics` and `course_parts` (4). Nothing reads the link yet (Purpose); this spec is the first reader.
- [R] A question with no `sections:` inherits its form's; `sections: []` means it tests no section; each question stores its effective list (6). `sections:` is allowed on every form `strategy`, so a bank form need not be a `QUIZ` (9). A bank form must sit in a sibling directory of the courses, not in a course directory without `children:` (it would be auto-discovered and placed) and not under a `_` prefix (not loaded) (docs section).
- [R] `content_save` never deletes a question; `QuestionAnswer.question` is PROTECT, so a dropped question keeps its last-loaded sections and PROTECTs the Topic/CoursePart it names (Scope "Out", Decision 5). This partly answers the open "what the loader does with a dropped question": it stays in the DB. Whether revision keeps showing it is still open.
- [R] Explanations, pools, draw, shuffling and flashcards were left out explicitly (Scope Out).

### In progress: `2. in progress/sacaa-compliance-2-shuffle/1. spec.md`
- [R] Shuffling is opt-in per form (`shuffle_pages`, `shuffle_questions`, `shuffle_options`, default False), only on `QUIZ` strategy, applied once per sitting inside `build_served_paper` and stored in `FormProgress.served_paper`. Option `locked: true` pins an option such as "All of the above". Keep-together `group` string marks runs that move as one unit.
- [R] `shuffle_with_locks` and `shuffle_units` are pure functions that take an RNG and touch no DB or global random state; the spec says question pools "will import" them. They are a ready tool for per-showing option shuffling in revision. [I] Revision shows are not a sitting, so the served paper is not used; the pure functions are reusable, the seed scheme is not.
- [R] `locked` and `shuffle_options` validator rules reject a lock when `shuffle_options` is off. [I] A revision shuffle that ignores `shuffle_options` should still honour `locked`, or it will reorder "All of the above" options; this needs a deliberate choice.
- [R] Its authoring docs say shuffled forms must avoid "see question 3" and option-letter references (Documentation section). The same applies to revision options.
- [R] Results page "Question N" now shows the served number (spec's Results page). Cohort reports keep authored numbers.

### Next: `1. next/sacaa-compliance-3-question-pools/`
- [R] Pools draw "units" (shuffle_units); a retake is a new attempt and draws afresh (idea.md lines 12, 28). Retake waiting periods are out of scope there.
- [I] Its bank concept is assessment-side (fresh paper per sitting to resist rehearsal); revision is the opposite goal (deliberate re-exposure). Keep the two banks separate: a revision question is a `FormQuestion` row, not a draw from a pool.

### Next: `1. next/educator-revision-analytics/idea.md`
- [R] Reads this spec's append-only review log and per-learner/per-question schedule; revision answers must stay out of `QuestionAnswer` so quiz reports and exports are unaffected. Open there: how an edited or removed question shows in history.
- [R] `answers.md` (this spec): analytics are out; explanation per question, optional, after each answer; revision per course; "I guessed" tap (right+guessed=Hard, right=Good, wrong=Again); mixed sections with an optional one-section filter.

### Next: `1. next/learner-interface-features-4-flashcards/idea.md`
- [R] Reuses this spec's schedule, per-learner record and session; "does not reopen" them. Flashcard has no `correct`; rating must not go in `QuestionAnswer`. Open: new `QuestionType` vs separate model; how history survives card edits (same problem as here).
- [R] Roadmap line 239: test-out and this spec collide on "section completed"; whichever lands second makes test-out completion add the section's questions to the bank.
- [R] `1. next/content-widget-sayit-reveal-3-audio-on-revision-flashcards` depends on flashcards, which depends on this spec; audio is not this spec's concern.

### Standing facts (idea.md of this spec)
- [R] Right/wrong is recomputed from current `correct` flags, not stored; editing an option re-marks history. [I] The review log must store the outcome at answer time (and probably the question's content hash) or edits will silently rewrite weakness signals.

## C. Elsewhere: what was tried and what happened

Evidence quality is low: vendor posts, help pages, forums. Where nothing was found, it says so.

- **Anki: SM-2 then FSRS.** [R] SM-2 produced "ease hell" (cards stuck at short intervals); Anki now ships FSRS, claiming fewer reviews for the same retention. A community benchmark favouring FSRS-5 is not independent. Backlog after a break makes people quit; the fix in use is capping reviews and not adding new cards while overdue. Easy Days and load balancing were added in 24.11. https://docs.ankiweb.net/faqs/what-spaced-repetition-algorithm , https://forums.ankiweb.net/t/proposal-backlog-recovery-planner-to-prevent-user-churn-burnout/70487 , https://forums.ankiweb.net/t/fsrs-one-of-my-decks-is-stuck-in-ease-hell/70644 (all cited in `research_learner_features.md` section 2 and `research_spaced_repetition.md`).
- **Duolingo.** [R] Practice hub has a "Mistakes" section plus a daily targeted review of due items; AI "Explain My Answer" was added (https://blog.duolingo.com/guide-to-duolingo-practice-hub/). Streaks cause documented guilt and apprehension (https://arxiv.org/pdf/2203.16175). A web search this session found no report of the practice hub or Mistakes review being removed or redesigned; the backlash found concerns the 2023 single-path redesign and 2026 course shuffles, not revision. Gap: no outcome data on practice-hub changes.
- **Quizlet.** [R] The 2017 Learn mode was "answer each term, repeat the ones you got wrong until all correct" (a mastery loop, no spacing). Spaced repetition came later as a separate feature, currently website-only, with learners rating recall and an "Okay" card returning in about a day (https://help.quizlet.com/hc/en-au/articles/48324742264077-Studying-with-Spaced-Repetition , https://campustechnology.com/articles/2017/03/09/quizlet-debuts-study-feature-that-helps-students-study-efficiently.aspx). Learn and Test went behind the Plus paywall in Dec 2022 (one G2 reviewer; https://www.g2.com/products/Quizlet/reviews). No official source for "Memory Score" changes found.
- **Khan Academy.** [R] Five levels (Not started, Attempted, Familiar, Proficient, Mastered) that move up and down with practice. The Sept 2018 mechanics change demoted a Proficient learner to Familiar on a below-perfect score and Mastered to Proficient or Familiar by score band (older, may be outdated). Mastery percentage now counts only Proficient or Mastered; the change could lower existing percentages. Course-level mastery % was removed from "Reimagined". https://support.khanacademy.org/hc/en-us/articles/48431088309645 , https://support.khanacademy.org/hc/de/community/posts/360023249611/comments/360003019811 . [I] Levels that can drop, and redefined percentages that make progress fall, are a trust risk; if FLS shows levels, define them once and avoid retroactive redefinition.
- **Moodle adaptive mode and interactive-with-multiple-tries.** [R] Adaptive mode lets a student retry a question with feedback; Moodle's own developer plans call one of its states "confusing", hints do not fit it well, and tries are tied to the hint count (minimum three). Proposed caps on tries are unconfirmed shipped. https://docs.moodle.org/dev/Plans_for_adaptive_mode , https://blogs.nottingham.ac.uk/learningtechnology/?p=2791 . No usage data. [I] Moodle has no scheduling over time; it is within-sitting retry only, so it does not cover this spec's need.
- **Medical qbanks (UWorld, AMBOSS).** [R] Praised for explanations, not for scheduling; one source (Osmosis/Elsevier, vendor) advises against spacing long clinical MCQs because learners memorise the answer; use flashcards for recall and questions for application (`research_learner_features.md` section 2).
- **Qstream (corporate).** [R] Retires a question after two correct answers or three attempts (VENDOR); a mastery-and-retire pattern, not long-term spacing.
- **Moodle quiz statistics.** [R] Facility, discrimination and per-option counts are what educators use to find bad questions; fed this spec's split-out analytics idea.
- Gap: no evidence found of a product that tried spacing for LMS course quiz questions and withdrew it. No data on authors' time to write explanations.

## Constraints for this spec

1. Build new: no prior FLS revision code to reuse or migrate. Read the section link through `FormQuestion.topics` and `.course_parts`; a question inherits its form's sections unless it overrides, and `[]` means it belongs to no section and so can never be banked or highlighted.
2. A bank form is a `FormQuestion` set in a sibling directory of the courses, any `strategy`. Revision draws from `FormQuestion` rows via the section link, not from a pool.
3. Revision records live in new tables, never `QuestionAnswer` or `FormProgress`; keep an append-only review log (also needed by `educator-revision-analytics` and flashcards) and store the outcome at answer time, because correctness is otherwise recomputed from current `correct` flags.
4. Reuse `shuffle_with_locks` from `sacaa-compliance-2-shuffle` for option order, with its own per-showing RNG (no served paper). Decide whether `locked` and `shuffle_options` are honoured. Do not depend on that spec merging first without checking its status (still in progress).
5. Do not couple to `sacaa-compliance-3-question-pools`; that spec is unwritten and assessment-focused.
6. Section completion trigger: test-out completion must also add questions; the spec must say which side owns the shared hook, and the later-landing spec wires it.
7. Dropped questions: `content_save` never deletes them and they keep their sections. Decide whether revision hides a question absent from its source file (needs a flag the loader does not set today) or keeps showing it.
8. Edited questions: the loader keeps a question's row while its `uuid` stays, so an edit keeps the same row id. A hash or version of the question on the log row is the only way to tell a substantial rewrite from a typo fix.
9. Design for the known failure modes elsewhere: cap session size and order by weakness (Anki backlog); avoid streaks or make them forgiving (Duolingo); offer at most Again/Hard/Good (Anki misuse of Hard; matches `answers.md`); do not redefine level thresholds retroactively (Khan).
10. Keep scheduler choice flashcard-compatible: store item type and the FSRS columns (or box and due), so flashcards reuse them (`research_spaced_repetition.md` section 4).
11. Explanation is per question, optional, shown after each answer (`answers.md`), so no per-option field. Add one optional key to the question schema; the form schema forbids extra keys today.
12. No competitor evidence reverses `research_spaced_repetition.md`'s recommendation; the evidence on outcomes is mostly vendor claims, so do not cite effect sizes for the product itself.

status: ok
