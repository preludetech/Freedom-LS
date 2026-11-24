# Answers: learner-interface-features-3-revision-questions

Asked by `/sdd:start` before the spec was written.

- Q: Where should authors write the "why it's wrong" explanation, and when do learners see it? → A: Per question, optional, shown after each answer (asked up front)
- Q: Are educator analytics (most-missed questions, per-option counts, a learner's weak sections) part of this spec? → A: No; create a new spec idea for them. Written as `spec_dd/1. next/educator-revision-analytics/idea.md` (asked up front)
- Q: Where does the revision screen live in the learner interface? → A: Per course, linked from the course; it draws only that course's bank (asked up front)
- Q: After a right answer, should learners get a one-tap "I guessed" to mark it as shaky? → A: Yes, an optional one tap; right + "I guessed" is Hard, a plain right is Good, wrong is Again (asked up front)
- Q: Within a course's revision page, are due questions mixed across sections, or can learners pick one section? → A: Mixed by default, with an optional filter to one section (asked up front)

Asked by `/sdd:spec_from_idea` while the research ran.

- Q: This branch carries 9 unmerged `sacaa-compliance-2-shuffle` commits; what does the pre-step rebase do? → A: Keep the shuffle commits and rebase onto main (revision can reuse `shuffle_options`; this branch merges after the shuffle spec)
- Q: Where do a section's revision questions come from? → A: Both: the section's existing scored quiz questions by default, plus an optional separate bank form
- Q: What happens to a learner's revision history when an author edits a question? → A: Editing keeps the schedule and past answers; a question removed from the source file loses its revision rows with it
- Q: `content_save` never deletes a dropped question (`QuestionAnswer.question` is PROTECT); how does the loader handle one? → A: Each load marks the questions missing from the file; revision leaves them out of the bank and deletes their revision rows; quiz history is untouched
- Q: Where do the revision models live? → A: A new `revision` app (schedule, review log, scheduler wrapper, its own `config.py`)
