# Research: known complaints about quiz shuffling

Topic: what learners, educators and course authors complain about with quiz shuffling in LMSs, and
what `sacaa-compliance-2-shuffle` should do about each. The spec decisions in `idea.md` and
`answers.md` are taken as given (opt-in knobs, `locked` option, `group:` key, shuffle-at-attempt-start
stored in the served-paper record, no page lock, no page-level override).

Evidence quality: search snippets, not full-thread reads. Complaints marked "(inferred)" rest on one
post or on a tool-vendor tip. Open edX produced no shuffle-specific complaint; accessibility evidence
comes from Articulate Storyline, which is a different product but the same failure mode.

## Summary table

| # | Complaint | Where seen | Spec response |
|---|-----------|-----------|---------------|
| 1 | Positional options ("All of the above", "A and B") break | Moodle, Canvas, Google Forms, Articulate | Locked option (already settled); add validator and authoring guidance for positional wording |
| 2 | Shuffle is all-or-nothing, no per-item control | Moodle, Canvas Ideas, Google Forms | Lock plus group already cover it; keep per-question option shuffle out of scope but document the trade-off |
| 3 | Learners and educators cannot say "question 5" | Moodle, Canvas | Numbers follow served order; document; surface served position in review |
| 4 | Review and feedback show a different order from the attempt | Moodle forum | Review reads the served paper, never authored order |
| 5 | Educators cannot see or export what each learner saw | Canvas (787 quizzes), SpeedGrader asks | Out of scope here (spec 4) but the stored record must be complete and readable |
| 6 | Grading in served order is painful | Canvas SpeedGrader ideas | Educator answer-key lists keep authored order (already settled); flag for spec 4 |
| 7 | Order changes on reload or resume | Articulate Rise; Moodle double-shuffle settings | Shuffle once at start, store, never re-derive (already settled); test it |
| 8 | Stimulus separated from its questions | Moodle forum, Canvas groups | Keep-together group (already settled); validator and docs |
| 9 | Cross-question references ("your previous answer") | Research file section 5.2 | Authoring guidance; group is the escape hatch |
| 10 | Screen reader and tab order disagree with visual order | Articulate Storyline | DOM order equals served order (already settled); add tests |
| 11 | Shuffled answers sometimes give the same order, so weak deterrent | Canvas (BC guidance) | Authoring docs: not proctoring; small option counts shuffle weakly |
| 12 | Matching, ordering and drag items shuffle unexpectedly or from two settings | Moodle MDL-85090 and forum | Not applicable (only radio, checkbox, dropdown); one knob, one place |
| 13 | Shuffling groups or sections reshuffles unexpectedly in "master" quizzes | Canvas community | Group is contiguous and atomic; validator rejects ambiguity |

## Detail

### 1. Positional options ("All of the above", "A and B", "None of these")

Complaint: the commonest one by far. Moodle's shuffle setting is quiz-wide; guidance for Moodle
tells authors to turn shuffling off for questions with "All of the above" or "Answers A and B", or to
reword. Canvas Classic users report the same all-or-nothing limit and say many questions with
"Answers A and B" responses are a barrier to shuffling; New Quizzes later added a per-option lock.
Google Forms teacher guidance says not to shuffle options like "b and c". Articulate users ask
for a "shuffle answer exception".

Spec response:
- Keep the `locked` flag (matches QTI `fixed`, Open edX `fixed`, Canvas New Quizzes lock).
- A lock is only meaningful at the authored position. State in the authoring docs that "All of the
  above" must be locked last, and that a locked option is the only safe home for a positional
  option. Prefer wording that has no positional reference ("All of the listed statements") or a
  checkbox question.
- Consider a validator warning (not error) when an option text on a shuffling form matches a small
  set of patterns (`all of the above`, `none of the above`, `both A and B`, option letters) and is
  not locked. This is cheap and catches the most common authoring mistake. Present as a
  suggestion in the plan; do not build speculative pattern lists beyond a few phrases.
- Learners are shown no option letters from the system, so "A and B" cannot be satisfied by a
  shuffled label. The authoring docs should say this plainly: do not refer to options by letter.

Sources: https://www.safaribooksonline.com/library/view/moodle-3-e-learning/9781788472197/0e8001bf-f07a-4745-8fb5-ef9399c8d02f.xhtml ;
https://blogs.chapman.edu/academics/?p=6813 ;
https://community.canvaslms.com/t5/Canvas-Ideas/Shuffle-answers-at-the-question-level/idi-p/329667 ;
https://community.canvaslms.com/t5/Canvas-Ideas/Option-to-set-or-turn-off-shuffle-answers-at-question-level-in-a/m-p/312774 ;
https://community.articulate.com/discussions/discuss/shuffle-answer-exception/456593/replies/456594 ;
https://community.articulate.com/discussions/rise-360/quiz-randomize-question-order-with-all-of-the-above ;
https://teachingaheadofthecurve.blogspot.kr/2015/03/tips-for-customizing-and-improving-your.html

### 2. All-or-nothing scope

Complaint: authors want shuffle on for most questions and off for a few; the platform only offers a
quiz-wide switch (Moodle, Canvas Classic, Google Forms question shuffle cannot pin one question). Canvas
Ideas threads ask for a question-level switch. Workarounds are ugly: split into sections, put pinned
items on a separate page.

Spec response: the settled design (form-level knobs, per-option lock, group) is already better than
Moodle and Google. Per-question overrides are explicitly out of scope; record in the spec's
rationale that a question with unshuffleable options is handled by locking all its options (a form
where every option is locked is valid) or by placing it in a group. Make sure the validator accepts
"every option locked". Note that no page lock exists (answers.md), so an "instructions" page that
must stay first has to live in the form body; docs should say this up front because it is the
page-level analogue of this complaint.

Sources: https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions ;
https://formswrite.com/blog/google-forms-shuffle-questions ;
https://community.canvaslms.com/t5/Canvas-Ideas/Option-to-set-or-turn-off-shuffle-answers-at-question-level-in-a/idc-p/312782

### 3. Numbering and talking about "question 5"

Complaint: shuffling exists precisely so students cannot say "question 3 is B". The side effect is
that educators cannot refer to a question number in class, and learners queries ("I got question 5
wrong") mean different questions. Canvas threads indicate numbers follow each student's displayed
order (inferred from one post).

Spec response:
- Numbers follow the served order (already settled). Keep it: numbers that jump around would be
  worse.
- Docs for educators: refer to questions by content or by identifier, not number. Spec 4's educator
  view should show authored identity beside served position (flag to that spec; here, make sure the
  served-paper record carries the question identity, not only a position).
- Do not render the authored position to learners.

Sources: https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Quizzes-Linking-to-question-bank-but-keeping-the-point/m-p/525123 ;
https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions

### 4. Review and feedback in a different order from the attempt

Complaint: a Moodle forum poster says the feedback page lists questions in authored order, not the
random order seen during the attempt, so learners are confused by the order changing between attempt
and review.

Spec response: review reads the served paper (already settled). Add an acceptance test that the
learner's post-submission result view lists questions and options in the served order, including
after content is later edited (the record, not the live form, is the source).

Sources: https://moodle.org/mod/forum/discuss.php?d=6706 (Moodle forum, "Random multichoice quiz ->
non-random feedback"; thread is old and may be outdated)

### 5. Educators cannot see what a learner was served

Complaint: a Canvas poster opened 787 quizzes one at a time to find one student's served order and
called the missing export a serious gap. This matters doubly for an ATO audit.

Spec response: spec 4 owns the view and export. For this spec: the shuffled order is stored
explicitly (not seed only), complete (pages, children, options), and in a documented shape so spec 4
can read it without calling the shuffle function again. Do not make the seed the only record.

Sources: https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Can-I-see-the-order-of-the-shuffled-questions-presented/td-p/207335

### 6. Grading and review in served order

Complaint: in Canvas New Quizzes SpeedGrader, questions appear in each student's served order, so
grading one question across the class means hunting. Instructors ask for a de-randomised view.

Spec response: the answer-key lists and educator preview stay in authored order (already settled).
Spec 4 should offer a per-learner view in served order and any aggregate view in authored order.
Nothing to build here beyond not breaking authored-order ordering of those lists.

Sources: https://community.canvaslms.com/t5/Idea-Conversations/New-Quizzes-Provide-option-to-sort-order-of-shuffled-quiz/idi-p/380177 ;
https://community.canvaslms.com/t5/Canvas-Ideas/SpeedGrader-Derandomize-questions-in-Speedgrader/idi-p/645796

### 7. Order changes on reload, resume or back-navigation

Complaint: Articulate Rise reports a resumed randomised quiz shows another question under the same
number. Moodle forum threads show two interacting shuffle settings (quiz-level "shuffle within
questions" and a question-level "shuffle each time attempted") producing options that move between
views. Both are examples of re-deriving rather than storing.

Spec response: settled design (shuffle once at attempt start, store, never re-derive) is the fix.
Add tests: reload, back, resume, and HTMX partial refresh all return the same order; a retake
differs (statistically; test with a seeded or injected shuffler, not randomness). Also: exactly one
place decides option order, so no second shuffle setting can exist (see 12).

Sources: https://community.articulate.com/discussions/discuss/rise-quiz---resume-problem-when-randomize-question-order/1225289 ;
https://moodle.org/mod/forum/discuss.php?d=404181

### 8. Stimulus separated from its questions

Complaint: Moodle has no stimulus-group concept, only workarounds (own section, not randomised) and
a long-standing request to randomise groups of questions; Canvas Classic question groups reshuffle
in surprising ways in "master" quizzes. Moodle quiz sections force new pages.

Spec response: keep-together group (settled). Validator: group is contiguous, one page, no nesting;
error wording should name the group key and the page. Docs: group every stimulus with its questions;
an ungrouped content block shuffles like any other child and will drift away (the idea already
says so; give it a worked example and a validator warning if an ungrouped content block precedes
a question and shuffle_questions is on, if the plan judges the heuristic cheap and low false-positive;
otherwise docs only).

Sources: https://moodle.org/mod/forum/discuss.php?d=398912 (cited in the existing research file) ;
https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Why-does-canvas-quiz-shuffle-questions-in-groups-in-my/m-p/460258 ;
https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions

### 9. Cross-question references

"Refer to your answer to the previous question" breaks under shuffle. No platform solves it other
than author discipline or grouping.

Spec response: docs only: remove cross-references or put the dependent questions in one group (group
internal order is preserved so relative references inside the group stay valid). Do not try to detect
them.

### 10. Screen reader and keyboard order

Complaint (Articulate Storyline): with answer shuffle on, screen readers announce the unshuffled
order, JAWS reads answers out of order, tab order is randomised or fixed relative to the visual
order. Vendor advice is to turn shuffle off, which defeats the integrity purpose.

Spec response: DOM order equals served order, no CSS reordering (settled). Add an automated
test per input template (radio, checkbox, dropdown) that the rendered DOM order equals the served
order and that no `order` CSS class is present. Also check `id`/`for`/`aria` associations and the
`name` attribute do not encode position in a way that assumes authored order. Manual screen reader
pass during frontend QA is worthwhile, since no automated check proves announcements.

Sources: https://community.articulate.com/discussions/discuss/accessibility-issue-screen-reader-answer-text-does-not-update-when-shuffle-is-se/939008 ;
https://community.articulate.com/discussions/articulate-storyline/tabbing-through-shuffled-mutliple-choice-answers ;
https://community.articulate.com/discussions/articulate-storyline/accessibility-tab-order-for-multiple-choice-quiz ;
https://docs.openedx.org/en/ulmo/developers/references/a11y-ref.html (general only; no shuffle content found)

### 11. Weak deterrent for small option counts

Complaint (Boston College guidance on Canvas): shuffled answers do not guarantee a difference,
because some students get the same answer order, more so with few options. Option shuffle with two or
three options gives little protection.

Spec response: the authoring docs already say shuffle is not proctoring; add that option shuffle
gives little with two or three options and page/question shuffle contributes more. No code
response.

Sources: https://cteresources.bc.edu/documentation/assignments-and-grades/get-started-with-new-quizzes/new-quizzes-support-for-academic-integrity/

### 12. Matching, ordering and drag items; duplicated shuffle settings

Complaint: Moodle matching and drag questions shuffle even when the quiz's "shuffle within questions"
is No (MDL-85090, closed "Not a bug") and the question-level setting interacts with the quiz-level
one; authors cannot tell which setting wins.

Spec response: FLS has only radio, checkbox and dropdown inputs, so no matching or ordering shuffle
exists; leave it out and say so in the docs. One form-level knob, no per-question override, no
page override (answers.md) already avoids the "which setting wins" confusion. Keep it that way:
the spec should not add any second place that influences option order.

Sources: https://tracker-old.moodle.org/browse/MDL-85090 ;
https://moodle.org/mod/forum/discuss.php?d=404181

### 13. Dropdown specifics (inferred)

A dropdown with a shuffled order and a locked "Select an option" placeholder: the placeholder must
not be shuffled or counted as an option. Spec response: confirm in the plan how the dropdown template
adds its empty option, and keep it outside the shuffle.

## Further items the spec should carry

- Authoring guide (`fls-content`): a "before you shuffle" checklist built from items 1, 3, 8, 9, 11
  (no letters, no "above/previous", group stimuli, lock positional options, shuffle is not proctoring).
- Validator messages should say what to do, not just what is wrong (for example, name the option
  and say "lock it or reword it").
- Retake: a fresh order each attempt is a feature learners can notice ("the questions moved");
  mention it in learner-facing wording only if the plan decides to tell learners the order may vary.
  Not needed by default.

## Reference URLs (all)

- https://www.safaribooksonline.com/library/view/moodle-3-e-learning/9781788472197/0e8001bf-f07a-4745-8fb5-ef9399c8d02f.xhtml
- https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions
- https://moodle.org/mod/forum/discuss.php?d=6706
- https://moodle.org/mod/forum/discuss.php?d=398912
- https://moodle.org/mod/forum/discuss.php?d=404181
- https://tracker-old.moodle.org/browse/MDL-85090
- https://blogs.chapman.edu/academics/?p=6813
- https://cteresources.bc.edu/documentation/assignments-and-grades/get-started-with-new-quizzes/new-quizzes-support-for-academic-integrity/
- https://community.canvaslms.com/t5/Canvas-Ideas/Shuffle-answers-at-the-question-level/idi-p/329667
- https://community.canvaslms.com/t5/Canvas-Ideas/Option-to-set-or-turn-off-shuffle-answers-at-question-level-in-a/m-p/312774
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Can-I-see-the-order-of-the-shuffled-questions-presented/td-p/207335
- https://community.canvaslms.com/t5/Idea-Conversations/New-Quizzes-Provide-option-to-sort-order-of-shuffled-quiz/idi-p/380177
- https://community.canvaslms.com/t5/Canvas-Ideas/SpeedGrader-Derandomize-questions-in-Speedgrader/idi-p/645796
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Why-does-canvas-quiz-shuffle-questions-in-groups-in-my/m-p/460258
- https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Quizzes-Linking-to-question-bank-but-keeping-the-point/m-p/525123
- https://community.articulate.com/discussions/discuss/shuffle-answer-exception/456593/replies/456594
- https://community.articulate.com/discussions/rise-360/quiz-randomize-question-order-with-all-of-the-above
- https://community.articulate.com/discussions/discuss/rise-quiz---resume-problem-when-randomize-question-order/1225289
- https://community.articulate.com/discussions/discuss/accessibility-issue-screen-reader-answer-text-does-not-update-when-shuffle-is-se/939008
- https://community.articulate.com/discussions/articulate-storyline/tabbing-through-shuffled-mutliple-choice-answers
- https://community.articulate.com/discussions/articulate-storyline/accessibility-tab-order-for-multiple-choice-quiz
- https://docs.openedx.org/en/ulmo/developers/references/a11y-ref.html
- https://teachingaheadofthecurve.blogspot.kr/2015/03/tips-for-customizing-and-improving-your.html
- https://formswrite.com/blog/google-forms-shuffle-questions

status: ok
reason: complaints gathered from Moodle, Canvas, Articulate and Google Forms sources with spec responses; Open edX and Reddit yielded no shuffle-specific complaints
