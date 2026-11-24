# Research: best practices for revision questions in an LMS

Adds to `research_spaced_repetition.md` (py-fsrs facts, Again/Hard/Good mapping, session-capped backlog, FSRS vs Leitner) and `answers.md` (per-question optional explanation shown after each answer; per-course revision page; mixed with section filter; "I guessed" = Hard). Not repeated. Tags: [R] sourced, [I] inference. Web search was thin (one search); items without a URL are [I] from general practice, not verified.

## 1. Feedback timing (settles little; supports answers.md)

- [R] Feedback after an MCQ raises later correct answers and cuts repeated wrong "lure" answers versus no feedback; both immediate and delayed feedback did this. https://pubmed.ncbi.nlm.nih.gov/18491500/
- [R] Timing evidence is mixed. A review summary says delayed feedback can retain better, but immediate feedback helps initial acquisition and weaker learners; a 2023 medical-education study found no timing difference. (Search summary, individual studies; no MCQ+spacing meta-analysis found.) https://profiles.wustl.edu/en/publications/timings-not-everything-immediate-and-delayed-feedback-are-equally/
- [I] In a spaced revision loop the next review is itself a delayed re-test, so "show after each answer" (already decided) is safe. Whether it is shown on right answers too: show the explanation after a wrong answer always; after a right answer only on request or when "I guessed" was tapped. Feedback should name the correct option, not just say "wrong".
- [I] Show feedback only after the learner commits to an answer (no peeking), and lock the answer once submitted.

## 2. Rating mapping: remaining details

- [I] Keep four-button Easy out of v1 (agreed in the earlier research). Wrong stays Again regardless of any "I guessed" tap; the guess tap is only offered after a right answer, so no wrong+guessed combination exists.
- [I] Do not reward speed. Response time is noisy on mobile; ignore it.
- [I] Multi-select (if it qualifies): count right only if the full set is exactly right (as `scoring.is_quiz_answer_correct` does today); do not give partial credit to the scheduler.

## 3. Scheduler choice

- [I] FSRS via `fsrs` remains the fit: the flashcards spec reuses it and it gives a retrievability ordering for the backlog. Configure `desired_retention` as one site setting (default 0.9); consider a lower value (about 0.85) for MCQ items, since recognition is easier than recall and fewer reviews suit a course-bound LMS. No per-learner tuning.
- [I] Keep short learning steps off for MCQs: a new question wrong in the session does not need same-day re-asks beyond one re-queue at the end of the session. Simpler: first exposure sets the card and the next due is the scheduler's result; do not loop within a session.
- [I] Store the scheduler version/parameters name on the review log row so a later parameter change or py-fsrs major bump does not make old logs ambiguous.
- [R] py-fsrs ships a tested `Card`/`ReviewLog` JSON round trip, so persisting a snapshot and rebuilding is supported (see `research_spaced_repetition.md` section 1).

## 4. Backlog and new items (beyond the session cap)

- [I] Two different caps: (a) session size (per sitting); (b) a daily cap on new questions entering practice. Because a finished section adds many questions at once (a section can add 10+), release them gradually: introduce at most N new per day, and zero while overdue count exceeds one session. Without (b) every section finish creates a spike.
- [I] "Session" ends with a clear finish screen and an offer ("Practise 10 more"), not an endless queue; completion feels like a goal and reduces burnout.
- [I] An empty state matters: if nothing is due, say when the next item is due and offer to practise a chosen section anyway, with extra practice still logged but scheduled normally (FSRS handles early reviews through elapsed time).
- [R] Anki's guidance on stopping new cards during backlog and capping reviews is already in the earlier research; no authoritative break-recovery recipe exists.

## 5. Streaks

- [R] Large-scale evidence on streaks is mixed; Duolingo-style streaks drive habit but create loss-aversion anxiety for some learners. (General knowledge; no source fetched.)
- [I] Prefer a forgiving, low-stakes form: count "days with a completed session this week" (a weekly target, for example 3 of 7) rather than a consecutive-day streak that resets to zero. A missed day never zeroes anything. Defer entirely if the spec wants minimum scope: "Don't build functionality that is not explicitly requested" and the idea lists streaks as open, not required. Recommend none in v1.

## 6. Option shuffling

- [I] Shuffle option order on each presentation for revision (the bank is repeated by design, so position memorisation is a known failure). Keep authored order for the course quiz itself so existing behaviour does not change.
- [I] Exception: options like "All of the above", "None of the above", "Both A and B", or options that refer to others by letter. Either do not shuffle those questions or give authors an opt-out flag. Detect by flag, not by text matching. The same flag answers the paused `compliance-form-randomization` question later.
- [I] Make the shuffle deterministic per (question, review attempt) (seed stored on the revision attempt or derived from the review-log id), so a page reload or HTMX re-render never reshuffles an in-progress question, and a stored answer can be rechecked against the displayed order. Store the chosen option by id, never by position.
- [I] A shuffled option's explanation must not say "option B"; authoring guidance should say to refer to option text.

## 7. Edits to a question that has review history

- [I] Classify an edit by effect on correctness, not wording:
  - Typo or explanation edit, new explanation text, reordering options: keep history and schedule.
  - Change to which options are correct (`correct` flags), or removal/replacement of a correct option, or a changed stem meaning: reset (start the card as new) and keep the old log rows marked as belonging to an earlier version.
  - Question removed from the source file: archive (keep rows, exclude from the due queue and from weakness counts), do not cascade-delete the learner's log.
- [I] Detecting "substantial" automatically is unreliable; a cheap deterministic rule is a content hash of (stem text + sorted correct option texts) stored on the progress row at review time. If the hash differs from the current question's, treat the next review as a first exposure. Authors get no extra field to maintain. Wording-only changes to the stem would also reset; accept this as conservative, or allow an author-set "keep history" opt-out if it proves noisy.
- [I] Because right/wrong is recomputed today from current flags (idea), revision must store `was_correct` and the chosen option id on each review-log row at answer time; history must not be re-marked. This protects the learner's records from edits.
- [I] Loader: a dropped uuid currently deletes the row. Learner history keyed on the question row will then disappear or break a foreign key; the spec must choose `SET_NULL` plus archived marker, or a soft-delete in the loader. Check the loader behaviour before deciding (unconfirmed in the idea).

## 8. Which question types qualify

- [I] v1: only the choice types that score automatically (single and multi-select), as the idea says free text cannot be marked. Free text must not enter the bank.
- [I] Exclude questions without a defined correct answer (surveys, unmarked/opinion, anything not counted in `scoring.is_quiz_answer_correct`). Exclude questions from forms that are not quizzes.
- [I] Questions with a lot of dependent context (case stems shared across questions, images) are better in later versions; flag as a future limit.
- [I] Flashcards use their own item type, so this decision does not constrain spec 4.

## 9. Measuring and showing weak sections

- [I] Measure from the review log, not from the schedule: for each section, over the learner's last K reviews (for example 10, or the last 14 days), the fraction wrong. Use a minimum sample size (for example 5 reviews) before showing any signal, so one miss does not label a section weak.
- [I] Alternatively use average FSRS retrievability across the section's cards (low = weak). It already accounts for time elapsed and needs no extra window logic, but is harder to explain. Recommend the simple recent-miss rate for v1 because learners and authors can read it.
- [I] Show a simple three-state chip per section (Needs work / Getting there / Strong), a flag not a percentage, plus a "Practise this section" link. Show the label in terms of effort ("revise this section") rather than a score. Link wrong answers to the section (already requested).
- [I] A lapse count (times Again after being Good or better) is a stronger "keeps getting it wrong" signal than a raw miss rate; consider it when defining the flag: weak = at least 2 lapses or miss rate over 40% across at least 5 recent reviews. Thresholds are settings constants, not a decision to freeze.
- [I] Per-learner view only; educator analytics belong to `educator-revision-analytics` (settled).

## 10. Authoring and rollout practicalities

- [I] Optional explanations mean most questions launch without one. Fall back to: "The correct answer is X. Review section Y" so every wrong answer still points somewhere. A `content_validate` warning (not an error) for questions with no explanation helps authors track the gap.
- [I] Count a question as "in the bank" only when its section completion event has fired; backfill existing completions once, via a data migration or a management command, with the new-per-day cap so existing learners do not meet hundreds of items.

## Recommendations

1. FSRS, default parameters, one site `desired_retention` (0.9, maybe 0.85 for MCQs); snapshot columns plus an append-only review log that stores `was_correct`, chosen option id, rating, scheduler version.
2. Show an explanation after every wrong answer, after right answers only on request or after "I guessed"; always name the correct option and link the section.
3. Session size cap, weakest (lowest retrievability) first, plus a daily new-item cap and no new items while overdue exceeds one session; clear finish screen.
4. No streaks in v1; if wanted later, a weekly-target form that never resets to zero.
5. Shuffle on every revision presentation (seeded per attempt, stored by option id), with an opt-out flag for positional options; keep authored order in the normal quiz.
6. Edits: keep history for typo/explanation/order edits; reset when correct answers or the stem's meaning change (hash of stem + correct option texts); archive on removal; never re-mark history.
7. Qualifying types: single and multi-select that score automatically; free text excluded.
8. Weak sections: recent miss rate with minimum sample size (lapses as a secondary trigger), shown as a three-state chip per section.
9. Backfill existing finished sections with the new-per-day cap.

status: ok
