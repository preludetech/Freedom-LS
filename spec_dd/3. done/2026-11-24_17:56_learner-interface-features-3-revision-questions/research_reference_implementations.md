# Research: reference implementations of spaced-repetition quiz revision

Complements `research_spaced_repetition.md` (py-fsrs facts, rating mapping, Leitner, backlog are not repeated) and `answers.md` (explanation per question, per-course screen, "I guessed" = Hard, mixed with section filter). Tags: [R] sourced, [I] inference. Evidence base is thin: no Django app using py-fsrs was found, and several commercial products publish no internals.

## 1. Data model shapes seen in the wild

- [R] Anki (the reference design) keeps two tables. `cards`: id, nid (note), did (deck), ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data (JSON text; FSRS memory state lives here in newer versions). `revlog`: id (ms timestamp), cid, usn, ease (button pressed), ivl, lastIvl, factor, time (ms spent), type (learn/review/relearn/cram). https://github.com/ankitects/anki/blob/main/rslib/src/storage/schema11.sql
  - [I] Pattern: one mutable state row per item plus an append-only log row per answer, with button pressed, interval before and after, and time taken. Same split as proposed in the earlier research.
  - [I] Anki's `reps` and `lapses` counters on the state row are cheap, and they are exactly what "keeps getting it wrong" needs (lapses). FLS should keep `lapses` and `reps` as columns alongside the FSRS fields.
- [R] py-fsrs documents `Card`/`ReviewLog` JSON round-tripping (`to_dict` / `from_dict`) as the persistence hook, and uses UTC only. No Django model implementation was found in a search. https://open-spaced-repetition.github.io/py-fsrs/fsrs.html , https://github.com/open-spaced-repetition/awesome-fsrs
  - [I] FLS must hand-write the model. Django stores aware datetimes in UTC with `USE_TZ`, which matches.
- [R] LearnKit (Obsidian plugin, FSRS) auto-grades multiple-choice and ordered-question cards: correct = Good, incorrect = Again; a correct ordered sequence is Good and any mistake is Again. The page lists no per-card fields beyond difficulty, stability and interval. https://ctrlaltwill.github.io/LearnKit/Grading
- [R] Mochi maps only remembered/forgot to Good/Again, with acknowledged loss of Hard/Easy information. https://mochi.cards/docs/reviewing/fsrs/
- [I] Convergent finding: every FSRS app that auto-marks MCQs uses a two-way Good/Again mapping. FLS's third rating (Hard via "I guessed") goes beyond the references; it is a cheap, optional extension and the log must record the button used so it can be revisited.

## 2. Session building

- [R] Anki: due reviews first, new cards capped per day, stop adding new while overdue exist, cap on daily reviews. https://docs.ankiweb.net/deck-options.html (details already in `research_spaced_repetition.md` section 5).
- [R] Moodle has no spaced scheduling in core quiz; it re-serves questions only through a new attempt (random questions drawn from a question-bank category). Its closest analogue is "adaptive" behaviours that retry within one attempt. https://docs.moodle.org/en/Question_behaviours
- [I] Open edX and Canvas: no sourced evidence found of built-in spaced repetition of quiz questions in either; Open edX offers per-problem attempt limits and "show answer" settings, Canvas offers question groups drawing randomly from a bank. Treat both as "random draw from a bank", not as scheduling. Not verified from docs in this pass.
- [I] Pattern across references: session = ORM filter `due <= now` ordered by a priority key, capped at N. FLS's per-learner state row makes this one query: `ProgressRow.objects.filter(learner=, course=, due__lte=now).order_by(...)[:N]`, with the optional section filter an extra `question__section=` clause. Retrievability is computed in Python, so ordering by "weakest first" either orders in Python over the due set (fine at a few hundred rows) or approximates with SQL `order_by("due")`.
- [I] A "new" (never reviewed) item is just a row created on section completion with `due = now`. Anki-style separate new/review queues are unnecessary; use `last_review IS NULL` to hold new items back while many reviews are overdue.

## 3. Feedback and explanation display

- [R] Moodle exposes feedback timing as a per-quiz "question behaviour": deferred (all feedback after submit), immediate (after each answer), interactive with multiple tries (check, try again, hints, final feedback), adaptive (several tries within the attempt), plus optional certainty-based marking where the student states how sure they are and the mark is adjusted. https://docs.moodle.org/en/Question_behaviours
  - [I] Moodle's certainty-based marking is the closest published precedent for FLS's "I guessed" tap; it is applied at answering time, however, not after the answer. FLS puts it after the answer, which avoids changing what the learner picks.
  - [I] Moodle has per-option feedback plus general feedback and "feedback for any correct/partially correct/incorrect response" fields per question. FLS answer fixed it per question, optional; Moodle shows that a per-question general feedback field is a normal minimum.
- [R] Anki shows the answer side, with an optional "Extra" field authors fill in for explanations; there is no per-wrong-option explanation. (Common practice, no single doc source fetched.)
- [I] Quizlet Learn, Duolingo, Khan Academy, Brainscape, RemNote: I could not fetch primary documentation. Khan's mastery page returned 403. Treat remarks about their behaviour in this section as recollection, not evidence.
  - Khan Academy: levels (attempted, familiar, proficient, mastered), mastery challenge re-checks decayed skills. Recollection only.
  - Duolingo: strength/practice-hub weak-skill practice. Recollection only.
  - Brainscape: 1-5 confidence rating drives intervals (vendor claim, see `research_spaced_repetition.md` section 4).

## 4. Weak-topic surfacing

- [R] Anki ships "leeches": a card with many lapses (default 8) is tagged and suspended. https://docs.ankiweb.net/leeches.html (not re-fetched in this pass; widely documented default).
  - [I] The lapses counter per question gives a direct "weak" signal. Aggregating per section: share of the section's questions with `lapses >= k` or low current retrievability gives a section weakness flag with no extra tables, one `GROUP BY`.
- [I] Khan-style levels give learners a readable per-section state without exposing stability numbers (consistent with section 6 of the earlier research). Derive from the rows, do not store.
- [I] "Point to the section to revise": needs the question's section link from spec 1; the revision screen's wrong-answer panel is a link to that section's course-player URL.

## 5. Django/Python-specific notes

- [I] No Django reference app using py-fsrs was found. Any pure-Python implementation shares the same three jobs: build a `Card` from the row, call `scheduler.review_card`, copy fields back plus write a log row, in one `transaction.atomic()` with `select_for_update()` on the row so a double HTMX submit cannot review twice.
- [I] Make the log idempotent per submitted question instance (a presented-question token in the form) so a retry or double-click does not log twice.
- [I] Because the loader drops a question's row when its `uuid` leaves the source file, FK `on_delete` on the state and log rows decides the history outcome: `CASCADE` deletes history, `SET_NULL` plus a snapshot of question text in the log keeps analytics. A reference like Anki keeps the log row (`cid`) even if the card is deleted.

## 6. What FLS should borrow

1. Anki's two-table split: mutable per-(learner, question) state row plus append-only log row. Add `reps` and `lapses` on the state row and a duration (ms) on the log row.
2. LearnKit and Mochi's auto-grade: wrong = Again, right = Good. Hard from the optional "I guessed" tap is an FLS extension; record the tap on the log row.
3. Moodle's feedback vocabulary: FLS's choice (optional per-question explanation, shown immediately) matches Moodle's "immediate feedback"; keep the explanation field independent of the option marking so it can later grow to per-option, as Moodle has.
4. Anki's rules: new cards held back while overdue, a capped session, weakest first.
5. Anki leeches idea: lapse count per question as the weakness signal, aggregated per section by a query. No separate weakness table.
6. Keep the log row independent of the live `correct` flags: store `correct` at answer time so editing an option does not re-mark history (the problem noted in `idea.md`).
7. Keep scheduling state as columns, not a JSON blob: Anki's `data` text column is the minority use; the hot columns (`due`, `ivl`) are real columns, which is why queues are fast.

## 7. Gaps

- No verified primary source for Quizlet Learn, Duolingo, Brainscape, RemNote, Open edX, Canvas or Khan internals; they are described here only as recollection or not at all.
- No Django app using py-fsrs found; shapes are inferred.

status: ok
