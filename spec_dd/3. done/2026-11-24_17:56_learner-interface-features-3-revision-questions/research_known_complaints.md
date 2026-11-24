# Research: known complaints about spaced-repetition and quiz-revision features

Adds to section 2 ("what learners dislike") of `research_learner_features.md` and to `research_spaced_repetition.md`. Does not repeat them. Tags: [R] sourced, [I] my inference. Evidence is mostly forum threads and practitioner posts; I found no controlled studies for most items, and say so.

## 1. Review pile-up after a break

- [R] Anki forum threads show the same pattern repeatedly: a learner leaves for a holiday or exam block, cards keep falling due, they return to hundreds or thousands due and feel overwhelmed. Threads include a 4-week break leaving about 1,700 due, and a medical-student thread "I neglected anking over break and have 1000s of due cards. Feeling overwhelmed".
  - https://forums.ankiweb.net/t/anki-showing-too-many-cards-since-a-study-break/34967
  - https://forums.ankiweb.net/t/resume-learning-after-two-month-break-best-practices/64522
  - https://forums.ankiweb.net/t/review-pacing-after-returning-to-anki/38931
  - https://forums.studentdoctor.net/threads/i-neglected-anking-over-break-and-have-1000s-of-due-cards-feeling-overwhelmed.1473656
- [R] WaniKani users report the same ("How to manage a comeback with ~1200 open reviews", "I am so stuck, please help"). https://community.wanikani.com/t/how-to-manage-a-comeback-with-1200-open-reviews/69043 , https://community.wanikani.com/t/i-am-so-stuck-please-help/73289
- [R] A forum proposal asks for a "Backlog Recovery Planner" explicitly to prevent churn and burnout among returning users. https://forums.ankiweb.net/t/proposal-backlog-recovery-planner-to-prevent-user-churn-burnout/70487
- [R] Users' workaround tactics (lower the interval modifier, filtered decks, stop new cards) are manual and expert-level; a typical learner will not find them. Secondary guide: https://www.iatrox.com/blog/anki-backlog-overwhelm-in-medical-school-a-practical-review-of-what-to-keep-change-or-stop
- [I] The complaint is about the visible count and the sense of debt, more than the work itself. A fixed-size session with no overdue total addresses both. The existing backlog rule in `research_spaced_repetition.md` section 5 already fits; the new point is that learners also abandon the product at this moment, so the first session after a long gap matters most.

## 2. Streak guilt and anxiety

- [R] Evidence is thin and mostly commentary. No peer-reviewed Duolingo-anxiety study surfaced. Secondhand claims: streaks can make keeping the streak matter more than learning (attributed to a Journal of Consumer Research study; not verified directly), and a "what the hell" effect where one missed day triggers quitting. https://thedecisionlab.com/insights/consumer-insights/streak-creep-the-perils-of-too-much-gamification
- [R] Mobbin reports an unattributed Duolingo test: lowering the bar to keep a streak (one lesson instead of the full daily goal) gave over 40% more people a 7-day streak. https://mobbin.com/blog/streaks-are-about-losing-a-study-of-859-streak-designs
- [R] Opinion pieces propose reframes: forgiving or flexible streaks. https://uxdesign.cc/3-reframing-streaks-on-duolingo-5-ideas-for-a-more-healthy-and-flexible-approach-to-language-8fd89545771e
- [I] Streaks also push shallow "one easy question to keep it alive" behaviour, which defeats spacing. For a course-driven LMS with due-based review, a streak adds little and risks guilt; if any, count "weeks with some revision", not days.

## 3. Memorising answer positions and answers

- [R] Authoring-tool forums show authors fighting this: Captivate shuffles answers at launch but keeps the same order on each retake, so position memory persists. https://community.adobe.com/t/captivate-discussions/quiz-answer-shuffle-on-first-take/m-p/14313187
- [R] The opposite complaint also exists: shuffling breaks options like "All of the above" / "None of the above" / "Both A and B", and authors ask to pin certain options in place (Articulate Storyline, Canvas threads). Canvas's own guide says there is no built-in way to lock positions. https://community.articulate.com/discussions/discuss/shuffling-answers-in-storyline-questions-but-locking-certain-ones/764578/replies/764582 , https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php
- [R] Articulate threads on shuffle vs stationary also raise accessibility and referencing ("see option C above") concerns. https://community.articulate.com/discussions/rise/rise-quiz-shuffle-vs-stationary-answer-choices
- [I] FLS authors will hit the same cases: a per-question "do not shuffle" flag is needed from day one, and explanations must not refer to option letters or positions.

## 4. Repeated identical questions

- [R] Tools answer this with question banks that draw fresh items, so returning players do not see the same quiz. https://qzzr.com/help/content-creation/shuffle-answers
- [I] Revision schedules by definition show the same item again. The complaint is not repeating; it is repeating with no sign of change (same wording, same order, same stem) after the learner has learned the surface pattern, so correct answers stop measuring recall. Mitigations are cheap ones (shuffle, optional variant wording) rather than a pooled bank, which the question model cannot do today.

## 5. Unhelpful or absent feedback

- [R] Practitioner guidance repeatedly says a bare right/wrong is the most common gap; the fix educators suggest is to link the question to existing course content rather than write a long rationale. https://ideabook.wp.txstate.edu/?p=328 , https://teaching.ucla.edu/news/efficient-feedback-strategies/
- [I] Learners most dislike feedback that restates the answer ("The correct answer is B"). A pointer to the section plus one sentence is the minimum that is not a restatement.

## 6. Rating-button confusion

- [R] Anki forums have a long list of "which button do I press" threads: "I don't understand when to press Hard", "Am I hitting Hard too often?", "Misusing Easy as Good", "How to prevent users from misusing Hard? Ideas are welcome". A reported r/Anki survey put Hard misuse near 10% (survey not verified). Some users read Hard as "I failed". Proposed fixes: hide labels, first-run explanation that Again is the only fail button, a two-button mode (AnkiDroid).
  - https://forums.ankiweb.net/t/i-dont-understand-when-to-press-hard/57585
  - https://forums.ankiweb.net/t/how-to-prevent-users-from-misusing-hard-ideas-are-welcome/49092
  - https://forums.ankiweb.net/t/misusing-easy-as-good/70133
  - https://forums.ankiweb.net/t/am-i-hitting-hard-too-often/25348
- [R] Misrating has a concrete cost under FSRS: pressing Hard after forgetting gives unreasonably long intervals; guidance is to use Again whenever you forget. Same Anki threads.
- [I] For MCQs the rating should be derived by the system (right/wrong) and the learner should never see the words Again/Hard/Good/Easy. If an "I guessed" tap exists, label it in plain words and say what it does ("see it again sooner").

## 7. Losing progress when content changes

- [R] Anki users hit this on every content edit route: changing the first field on re-import makes new notes with no history; shared-deck updates are ignored if the field structure changed; "reset" does not clear history; people ask how to carry progress from a modified deck to the original. https://forums.ankiweb.net/t/updating-shared-deck/48602 , https://forums.ankiweb.net/t/how-to-transfer-progress-from-modified-deck-to-original-deck/51416 , https://docs.ankiweb.net/faqs/some-updates-were-ignored-because-the-note-type-has-changed , https://forums.ankiweb.net/t/changes-in-deck-with-python-without-losing-progress/46996
- [R] Advice that works in Anki: a stable unique ID per note, so identity survives edits. Same threads.
- [I] This matches FLS's `uuid`-keyed loader. Complaints arise when identity is by content or position. Guard: typo and wording fixes keep identity and history; only a deliberate author act (new uuid) resets. Learners should not see a question vanish from their due list without explanation.

## 8. Being pushed to review what they know; lack of control

- [R] Anki has no native skip; users ask for one and find bury/unbury clumsy (it can bury siblings). Anki's manual argues against overrides because they weaken the algorithm. https://forums.ankiweb.net/t/feature-request-native-skip-function-for-reviews/52968 , https://faqs.ankiweb.net/print.html
- [R] Other tools give control: Obsidian SR lets you skip a card with one key; StudySmarter lets learners add more cards in batches ("+15 Learn"); Mochi separates a learn phase for new cards. https://open-spaced-repetition.github.io/obsidian-spaced-repetition-recall/flashcards/reviewing , https://studysmarter.zendesk.com/hc/en-gb/articles/5617520656924 , https://mochi.cards/docs/reviewing/index_old
- [R] A separate-mode request for learning new cards shows demand for choosing between "new" and "review". https://forums.ankiweb.net/t/feature-request-a-separate-mode-for-learning-new-cards/70559
- [R] A long-running critique of flashcard practice says reviews skew to the hardest items and become boring ("boredom bias"). https://www.gwern.net/docs/www/howtoremember.biz/c15e99b0c25eadeab4f02152370dddae47bdf3c2.html
- [I] The cheapest control that preserves the schedule: "start a session on this section" (learner picks scope) plus a "this was too easy, don't show for a while" tap that behaves as a scheduling input, not a delete. Without any control, learners game the scheduler by rating dishonestly (see section 6).

## 9. Effort of writing explanations (authors)

- [R] No measurements of authoring time per option found. Practitioner sources say individual per-option feedback is the costly part, and cheaper routes are one overall note, reusable feedback for common mistakes, and mapping the question to existing content. https://community.d2l.com/brightspace/discussion/comment/7764 , https://ideabook.wp.txstate.edu/?p=328
- [R] Question writing in general is described as time-consuming, a cost that recurs when pools are updated each term. https://teaching.charlotte.edu/teaching-guides/online-learning/online-activity-examples/self-checks-quizzes-tests
- [R] Vendors now offer AI-drafted per-option explanations that the instructor edits (Teachfloor; marketing, not independent evidence). https://www.teachfloor.com/product-updates/introducing-ai-quiz-feedback
- [I] An explanation field must be optional, with a fallback (link to the section) so unexplained questions still work. Content validation should report coverage ("12 of 40 questions have an explanation") as information, not an error.

## What the spec should guard against

1. A visible overdue total or "you are N days behind" message. Show a capped session and "N ready".
2. New questions joining the bank while a large overdue set exists (already in the research; keep it).
3. Streak loss framing. If a streak exists, it must forgive gaps and never be the only entry point.
4. Showing Again/Hard/Good/Easy or equivalents to a learner answering a choice question. System derives the rating; any confidence tap uses plain words.
5. A shuffle that cannot be turned off per question, and explanations or stems that refer to option letters or positions ("see option B", "all of the above"). Shuffle must differ per presentation, not once per session.
6. Changing a question's identity on a wording edit. History survives edits keyed on `uuid`; the author-facing rule for "substantial rewrite" is explicit and does not rely on the learner noticing.
7. Marking history that re-flips when an author changes the `correct` flag (existing FLS fact); store the outcome at the time of answer on the revision log.
8. Feedback that only restates the correct answer. Minimum viable: link to the section plus any author text.
9. Making explanations mandatory, which blocks adoption by authors. Optional, with a coverage report.
10. No learner control at all. Provide at least scope choice (by section) and a way to say "too easy / not now" that is an input to scheduling, not a silent drop.
11. Sections or questions vanishing from the learner's bank without a message (author removed a question, loader dropped it).
12. Pretending evidence is stronger than it is: streak-anxiety and Hard-misuse figures above are anecdotal or secondhand; treat them as design caution, not measured effects.

status: ok
