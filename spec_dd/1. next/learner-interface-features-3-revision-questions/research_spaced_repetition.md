# Research: spaced repetition scheduler for revision questions and flashcards

Complements section 2 of `research_learner_features.md` (learning science not repeated). Tags: [R] sourced fact, [I] my inference.

## 1. py-fsrs (PyPI `fsrs`)

- [R] Latest 6.3.2, uploaded 2026-08-09. Earlier: 6.3.1 (2026-03-10), 6.3.0 (2025-10-13), 6.2.0 (2025-10-05), 6.1.1 (2025-08-05), 6.1.0 (2025-06-13). Roughly 3-6 releases a year; actively maintained under the open-spaced-repetition org. https://pypi.org/project/fsrs/ , https://github.com/open-spaced-repetition/py-fsrs
- [R] Licence MIT. Requires Python >= 3.10 (FLS needs >= 3.13, fine). Core dependency: `typing-extensions` only. `torch`, `numpy`, `pandas`, `tqdm` live behind the optional `optimizer` extra, which FLS would not install.
- [R] API: `Scheduler(parameters=21 weights, desired_retention=0.9, learning_steps, relearning_steps, maximum_interval, enable_fuzzing)`. `scheduler.review_card(card, rating)` returns `(card, review_log)`. `scheduler.get_card_retrievability(card)` gives the current recall probability. `Rating`: Again=1, Hard=2, Good=3, Easy=4. `State`: Learning=1, Review=2, Relearning=3. `ReviewLog` carries `rating` and `review_datetime`. New `Card()` is due immediately.
- [R] `Card` fields: `card_id` (int), `state`, `step` (int or None), `stability` (float or None), `difficulty` (float or None), `due` (datetime), `last_review` (datetime or None). https://raw.githubusercontent.com/open-spaced-repetition/py-fsrs/main/fsrs/card.py
- [R] Serialisation: `Card`, `Scheduler`, `ReviewLog` have `to_json()` / `from_json()`; `Card` also has `to_dict()` / `from_dict()` (state as int, datetimes as ISO strings).
- Fits model fields: yes. Six scalar columns per (learner, question): `state` (int), `step` (nullable int), `stability` and `difficulty` (nullable float), `due` and `last_review` (datetimes). `card_id` is not needed (use the row's pk). Rebuild with `Card.from_dict(...)`. Index on `(learner, due)`. A separate append-only review-log table (learner, question, rating, timestamp, correct) is worth keeping for analytics and for re-running the scheduler or optimiser later. [I] Use real columns, not a JSON blob, so "due now" and "weak" queries stay ORM-native.
- [I] Default parameters work without per-user training; the optimiser is not needed at FLS scale.

## 2. Mapping MCQ outcomes to FSRS ratings

- [R] No official open-spaced-repetition guidance for MCQs found. FSRS itself treats Again as fail and Hard/Good/Easy as pass. https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md
- [R] Apps using FSRS for MCQs: LearnKit auto-grades correct = Good, incorrect = Again (https://ctrlaltwill.github.io/LearnKit/Grading). Mochi records only remembered/forgot, mapping to Good/Again, and notes some information loss vs Hard/Easy (https://mochi.cards/docs/reviewing/fsrs/).
- [I] Proposed mapping:
  - Wrong: Again.
  - Right and learner says "I guessed" / "not sure": Hard. (The guess floor on a 4-option MCQ is 25%, so a bare "right" overstates memory.)
  - Right, normal: Good.
  - Right, "confident" and fast: Easy is optional; leave it out in a first cut. Easy pushes intervals out sharply, and an MCQ cannot prove recall.
  - Ask the confidence question only after answering and keep it one tap, otherwise it becomes friction. Skipping it defaults to Good.
- [I] Caveat already in section 2: learners memorise the answer or its position on repeated MCQs, so shuffle options and prefer application-style questions.

## 3. Leitner as the alternative

- Minimal implementation [I]: one integer `box` (1-5) and one `due` date per (learner, question). Box intervals are a settings constant, for example 1, 3, 7, 14, 30 days. Right: box+1. Wrong: box 1 (or box-1 for a gentler variant). Due = now + interval[box]. No library, about 20 lines, and no stored floats. Reference: https://www.brainscape.com/academy/leitner-method/
- Better when: the educator or learner wants to explain the schedule ("you are in box 3"); there is no review history to benefit from; the item pool is small; or the requirement is mastery/retire after N correct rather than long-term retention optimisation.
- Weaknesses [I]: the same schedule for every item, so easy and hard questions are treated alike; no retention target knob; no retrievability estimate for ranking a backlog.

## 4. One scheduler for MCQs and flashcards?

- [I] Yes with FSRS. The scheduler only needs a rating; the difference is where the rating comes from.
  - Flashcard: learner self-rates Again / Hard / Good / Easy after flipping the card (the native FSRS interaction).
  - MCQ: the rating is derived from correctness plus the optional confidence tap (section 2).
  - Brainscape-style 1-5 confidence collapses to FSRS as 1 = Again, 2-3 = Hard, 4 = Good, 5 = Easy (or offer 4 buttons and skip the 1-5 scale). Brainscape's own claims are vendor claims. https://www.brainscape.com/academy/comparing-spaced-repetition-algorithms/
  - Store an `item_type` (question or flashcard) on the progress row so analytics can separate them; scheduling code is shared.
- [R] Anki users report that "Hard" is misused; many press only Again/Good ("ease hell" threads, cited in section 2). Fewer buttons is a safe default for flashcards too: Again / Good / Easy, or Again / Hard / Good.

## 5. Backlog after a break

- [R] Anki guidance: stop adding new cards while overdue reviews exist; cap daily reviews. https://docs.ankiweb.net/deck-options.html
- [R] Anki 24.11 ships native Easy Days (lighter or no reviews on chosen weekdays) and load balancing, which nudges due dates off busy days. FSRS Helper add-on offers "Flatten" and postponement. Load balancing and easy days apply only at (re)scheduling time and not to cards in learning/relearning or with very short intervals. https://github.com/open-spaced-repetition/fsrs4anki-helper , https://forums.ankiweb.net/t/changing-easy-days-without-getting-a-backlog/65363/2
- [R] No authoritative recipe for resuming after a multi-day break. Community proposals for a "backlog recovery planner" exist. https://forums.ankiweb.net/t/proposal-backlog-recovery-planner-to-prevent-user-churn-burnout/70487
- [I] Simplest sensible session rule for FLS:
  1. A session is a fixed size (for example 10-20 items; an FLS setting).
  2. Select due items (due <= now), ordered by lowest retrievability first (`get_card_retrievability`), so the weakest come first and age alone does not decide. With Leitner, order by lowest box then oldest due.
  3. Never show more than the session size, however large the backlog; the remainder simply stays due. No "you have 400 reviews" counter; show "N ready, here are 15".
  4. Do not introduce newly unlocked items while overdue ones exceed one session's worth.
  5. No rescheduling pass, load balancer or easy days in v1. Because a session is capped and ordered by weakness, a backlog self-drains without mass edits.
  6. Fuzzing (`enable_fuzzing`) is on by default and spreads due dates slightly for free.

## 6. Recommendation

Use FSRS via `fsrs` (MIT, one pure-Python dependency, actively released, Python 3.10+). Store the card state as plain columns on a per-(learner, question) progress row plus an append-only review log. Map MCQ results to Again / Hard (right but guessed) / Good, and let flashcards use native self-rating, so one scheduler serves both. Choose Leitner only if the spec requires a schedule the learner can read at a glance; if so, keep the progress row shape (due + level) so swapping later is a data migration and not a redesign. Show learners Khan-style levels, not stability numbers.

status: ok
