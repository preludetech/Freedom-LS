# Research: prior art for shuffling quiz pages, questions and options

Question: what has already been tried for this, here or elsewhere, and what happened?

Labels: (c) read from this repo's files or code; (w) web-sourced and cited; (w-search) known only from a
search-result summary because the page blocked a direct fetch (403, 404 or login wall), so treat it as
unverified; (i) inference. Builds on `research_randomization_ux_integrity.md` and the research files
of `sacaa-compliance-1-served-paper-record`; it does not repeat them.

## 1. In this repo

### 1.1 Nothing shuffles today (c)

- `grep -i "shuffl|randomi"` over `freedom_ls/` finds only unrelated code (webhook retry jitter, mail
  retry, test image helpers, a QA seeder). There is no shuffle, ordering knob, option lock or group in
  the form engine. `git log` is not available here; the earlier spec's own search
  (`3. done/.../sacaa-compliance-1-served-paper-record/research_prior_art.md` section 1) states
  `git log --all -S shuffle -- freedom_ls` found nothing related and no branch has code beyond specs.
- Earlier attempts at the surrounding feature, all spec-only, none reached code (c, same file):
  `compliance-form-randomization` (2026-06-30, all four knobs in one idea, moved to in progress
  2026-07-01, never specced, cut into the four `sacaa-compliance-*` specs on 2026-11-17); the April
  `00. sacaa-exam-audit-log` frozen-copy design (deleted next day); `content_snapshots` (paused).
  Lesson: the single-idea "all four knobs plus a record" scope stalled. Spec 1 shipped by taking the
  record alone, and spec 2 should stay as narrow: the shuffle function and the author controls only.

### 1.2 Spec 1 built the seam this spec fills (c)

`freedom_ls/form_engine/served_paper.py` is shipped. `build_served_paper(form)` is "the one place
`sacaa-compliance-2-shuffle` will change" (spec 1, "Building and writing the served paper"). Today it
walks `form.pages.all()`, `page.children()` and `child.options.all()` in authored order and stamps a
`secrets.randbits(63)` seed. What is already settled and working:

- Shape: `{"seed", "pages": [{"id", "children": [...]}], "options": {question_uuid: [option_uuid...]}}`;
  order stored explicitly, seed is provenance only, nothing re-derives from it.
- Written lazily on the first page-serving request, write-once by conditional `UPDATE ... WHERE
  served_paper IS NULL` then re-read. QUIZ strategy only. Missing items skipped on read, ids never
  dropped from the stored paper.
- `served_path`, `SittingPath` (served order for `numbered_pages()`, `questions()`,
  `question_positions()`, next/previous/landing by served position), `SittingPath.options_of(question)`
  and the three input templates reading option order from the path. `furthest_page_reached` stays an
  authored number and is translated to a served position wherever compared. URLs carry authored page
  numbers.
- Already tested with an injected non-authored order (spec 1 "Injected order, navigation").

Lesson: spec 2 has no new storage, navigation, resume or scoring work. Its testable surface is (i) the
new pure shuffle function inside `build_served_paper`, (ii) schema/validator/`content_save` for the new
fields, (iii) the places spec 1 explicitly left authored (below).

### 1.3 Gaps spec 1 left for this spec (c)

- **Results page labels.** Spec 1 "Scoring and results": "Results page incorrect-answer labels stay as
  they are (`question.question_number`). They only differ from served positions once
  `sacaa-compliance-2-shuffle` lands." Live code still has `Question {{ item.question.question_number }}`
  at `learner_interface/templates/learner_interface/course_form_complete.html:105`, and
  `FormQuestion.question_number()` (`form_engine/models.py:236`) walks the authored form. Spec 1's own
  UX research (`research_ux_patterns.md` lines 68-71) flags that under an injected order "Question 3"
  on the results page names a different question from the "Question 3" the learner answered. Under a
  real shuffle that is the visible "review shows a different order" bug (section 2.1). Spec 2 must
  switch this label to the served position, and the incorrect-answers list to served order.
- **`question.html`.** `question.html:13` and `:19` build `data-testid="question-number-{{
  question.question_number }}"` and `required-indicator-...` from the authored number while the visible
  `{{ position }}` comes from the path. Test ids stay unique either way, but any new test asserting
  numbers must use the visible served position. (i)
- **Page URL identity.** Spec 1 UX research (lines 125-129) says authored page numbers in URLs let two
  learners line up `.../page/3/` across papers, partly undoing the anti-collusion point of a page
  shuffle, and asks spec 2 to record it as an accepted risk. Questions and options carry no URL
  identity.
- **`QuestionOption` and `FormQuestion.order`.** The qa_helpers commands read `question.options.order_by
  ("order")` for their own seeding; they are authored-order readers and need no change. The cohort
  report column header `Q{{ question.question_number }}` (`cohort_report_body_region.html:134`) is
  an authored-order aggregate and should stay authored (idea: "answer-key lists keep their authored
  order"). (c, i)

### 1.4 Branch logic precedent (c)

`form-engine-branch-logic` (done) ruled out `when` on QUIZ forms in `validate.py` (spec 1 cites it at
`validate.py:1042`). `research_form_engine_seams.md` section 4 analysed the other direction: a page
shuffle could place a condition source after the gated page and silently drop it. This spec's rule
"knobs only on QUIZ, so no condition conflict" relies on that existing validator rule, not on a new
one. Lesson: add a test that a QUIZ form with `when` is still rejected so the guarantee is not an
accident of an unrelated rule. (i)

### 1.5 Where earlier research and the idea disagree (c)

- `research_randomization_ux_integrity.md` section 6.2 recommends a `FormGroup` model with a FK from
  members; `answers.md` decides a `group: <name>` string key per member and a contiguous run. The
  QTI model the research cites (nested `assessmentSection`, which is a real container) is closer to
  the model the answers rejected. The string key is cheaper but gives up an enforced container, so
  contiguity, single-page and no-nesting must all be validator rules (the idea already lists them).
  `sacaa-compliance-3-question-pools` needs "a clean indivisible draw unit"; a name-keyed contiguous
  run on one page is derivable, but pools must not assume group names are unique across pages unless
  the validator enforces that. (i)
- The same research sections 6.1 and 6.3 propose `shuffle_questions_within_page` and
  `position_locked`; the idea proposes `shuffle_questions` and `locked`. Naming is still open in the
  idea.
- The research recommends storing `shuffle_seed` (a UUID with a default) and `realized_order`. Spec 1
  rejected a defaulted UUID because it would label old attempts as shuffled
  (`3. done/.../research_prior_art.md` lines 30-32). Not applicable here; do not reintroduce it.
- Seed algorithm: spec 1 already stores a 63-bit `secrets` seed per paper. A seeded `random.Random(seed)`
  inside `build_served_paper` would make the stored seed an honest provenance value, but the stored
  explicit order, not the seed, is the record. A reproducible-from-seed shuffle is still worth keeping
  for tests, not for audit. (i)

## 2. Elsewhere: what happened, and the lesson

### 2.1 Review and regrade show a different order from the one sat

- Moodle: a forum thread reports that answer order on the feedback page differed from the attempt;
  a developer replied it was "by design" (1.x era) (w-search,
  <https://moodle.org/mod/forum/discuss.php?d=6706>). A college guide still warns that shuffle within
  questions reorders answers each time the quiz is opened, so a review can differ (w-search,
  <https://selkirkcollege.atlassian.net/wiki/spaces/KB/pages/6928010/Layout+Question+Behaviour+Moodle+Quiz>,
  now a 404). MDL-13073 (fixed in 1.8): regrading printed the same attempt with the same checked boxes
  but a different answer order, so the student's marked answers appeared to change (w-search,
  <https://tracker-old.moodle.org/browse/MDL-13073>, 404 on direct fetch).
  Moodle's eventual fix was to persist the order per attempt: multichoice writes the answer-id order to
  step data as `_order` and reads it back on every load (c, spec 1
  `research_reference_implementations.md` line 12; <https://moodle.org/dev> style source cited there:
  <https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/question/type/multichoice/question.php>).
- Lesson: every reader of options must read the stored order: the learner inputs, the results page,
  the incorrect-answers list and any print or review view. Spec 1 covered the three inputs and the
  dropdown answer key; this spec must make sure the results page label and list follow too, and add
  a test that a real shuffled paper renders the same on first load, reload, resume and results.

### 2.2 Resume redraws or reshuffles

- Articulate Rise/Storyline: threads report a resumed quiz with randomised question order shows a
  different question at the same position (w-search,
  <https://community.articulate.com/discussions/discuss/rise-quiz---resume-problem-when-randomize-question-order/1225289>,
  403 on direct fetch). Root cause as reported: order derived per session, not stored.
- Open edX stores a per-student integer `seed` in user state and re-derives the choice shuffle from it
  (w-search of code mirrors; `seed = Integer(... scope=Scope.user_state)` and "seed from problem state
  first, then constructor"), <https://git.andalsoftware.com/Andal.LND/edx-platform/src/branch/master/xmodule/capa/capa_problem.py>.
  The docs note shuffle is switched on per `choicegroup` and per-choice `fixed="true"` keeps one in place
  (w, <https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-koa.master/exercises_tools/multiple_choice.html>,
  later docs show `fixed="true"` on "All of the above": <https://docs.openedx.org/en/latest/educators/how-tos/course_development/exercise_tools/award_partial_credit_multiple_choice.html>).
  I found no public bug report about the seed changing on reload or rescore; a seed-derived shuffle
  is only reproducible while the shuffle code and the option list are unchanged (i).
- Lesson: this spec's design (shuffle once at start, store the explicit order, `ensure_served_paper`
  is write-once) already avoids both failure modes. Do not add any code path that shuffles outside
  `build_served_paper`, and do not let a later tweak to the shuffle function change how old papers
  render (old papers store ids, so this holds). Keep spec 1's "Reload, back-navigation and resume show
  the same order" as an explicit success criterion with a test on a shuffled paper.

### 2.3 "All of the above" and positional options

- Moodle: the shuffle-within-questions help says that for questions with "All of the above" or
  "Answers A and B" you "will probably want to set this to No". Moodle has no per-option pin; the
  quiz setting only takes effect when the question's own shuffle is also on (w-search,
  <https://svnlliurexnet.gva.es/leia/mods-backports/trunk/moodle/lang/en_utf8/help/quiz/shufflewithin.html>).
  Moodle also does not shuffle certain types (matching handling reported in MDL-85090, closed
  "Not a bug"; w-search <https://tracker-old.moodle.org/browse/MDL-85090>).
- Canvas Classic Quizzes: shuffle answers is quiz-wide and all-or-nothing, with no lock, so authors
  reword or turn it off (w-search,
  <https://community.canvaslms.com/t5/Canvas-Question-Forum/selective-shuffling-of-answer-options-in-a-quiz/m-p/579562>).
  Canvas New Quizzes adds a lock icon beside a question's answer once "Shuffle Choices" is on (w,
  <https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php>).
  An archived thread reports the lock "doesn't work" and that the quiz-level setting overrides it
  (w-search, <https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-New-Quizzes-Multiple-Choice-lock-answer-option-doesn-t/td-p/240524>;
  could not be read). The sources disagree, so do not rely on Canvas as proof that the lock is
  trouble-free.
- Articulate Quizmaker/Rise: users ask for an anchor on "All of the above"; the answer given is to
  reword to "All of these answers" (w-search,
  <https://community.articulate.com/discussions/articulate-quizmaker/multiple-choice-questions-anchoring-shuffled-answers>,
  <https://community.articulate.com/discussions/rise-360/quiz-randomize-question-order-with-all-of-the-above>).
  SurveyMonkey has a "Do Not Randomize the Last Choice" anchor for "Other" and "None of the above"
  (w-search, <https://help.surveymonkey.com/da/surveymonkey/create/randomizing-answers/>).
- QTI `fixed="true"` on a `simpleChoice` is the standard (c, spec 1 research
  `research_reference_implementations.md` line 31, <https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html>).
- Lesson: every mature system either lacks the lock (and tells authors to reword) or has a boolean
  per option. The idea's `locked` flag matches QTI, Open edX and Canvas New Quizzes. The "All of the
  above" problem has a second half the lock does not solve: a locked option must keep its absolute
  authored position (the idea says so), and an option that refers to another by letter ("Both A and
  B") still breaks when A and B move. The authoring doc must say that a lock fixes where an option sits,
  not what "A" means, and recommend wording that does not name letters. A shuffled form with a lock on
  a checkbox question is allowed by the idea; the spec should check the lock applies to all three input
  types the same way (dropdown included). (i)

### 2.4 Stimulus and keep-together

- QTI: nested `assessmentSection` with `shuffle="false"` is the grouping model (c, existing research
  section 2.2).
- Moodle has no stimulus container. The Description (information) question is itself a "question" and
  is shuffled away from the questions that follow; workarounds are separate sections or putting the
  real questions into a category pulled by a random slot, and shuffling only applies within a section
  (w-search, <https://moodle.org/mod/forum/discuss.php?d=446740>; Moodle docs state the Description
  type is useful as a preface only when shuffle is off,
  <https://docs.moodle.org/403/en/Description_question_type>). The feature request for grouped shuffle
  in <https://moodle.org/mod/forum/discuss.php?d=398912> (403, search-only) is the same gap.
- Canvas New Quizzes: the Stimulus type keeps a stimulus with its attached questions (w,
  <https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php>).
  However, a Canvas community thread says shuffling stimuli with their questions is "not currently
  possible" and links open feature requests; and item banks do not carry a stimulus's attached
  questions with it (w-search, <https://community.canvaslms.com/t5/Canvas-Question-Forum/Shuffling-the-stimulus-and-its-associated-questions/m-p/509493>,
  <https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas>). The earlier research's
  claim that Canvas shuffles stimulus plus sub-questions as a unit is therefore contested; treat Canvas
  as keep-together-in-order-but-not-shuffle-proven.
- Lesson: the keep-together group is a gap in the major LMSs (Moodle has none; Canvas only partly), so
  there is no tried-and-fixed behaviour to copy except QTI. Group handling is the part of this spec
  most likely to need its own tests: stimulus plus questions never separate, group internal order never
  changes, and a group's atom is placed at one position in the page-level shuffle. The explicit
  decision in `answers.md` to allow groups on an unshuffled page (for question pools) is untested prior
  art; QTI allows it (invisible section).

### 2.5 Pages and sections: limits and pinning

- Microsoft Forms: "If your form or quiz has multiple sections or pages, you will not be able to shuffle
  questions" (w, <https://support.microsoft.com/forms/adjust-your-form-or-quiz-settings-in-microsoft-forms>).
  Its "Lock questions" option shuffles all questions "except those you designate (e.g. questions 3-5)",
  i.e. a contiguous range pinned; community threads from 2018 to 2024 report that locking a range made
  nothing shuffle ("none of them are shuffled, everyone is locked") with no resolution in the thread
  (w, <https://techcommunity.microsoft.com/discussions/microsoftforms/shuffle--lock-questions-broken/165781>).
- Google Forms: "Shuffle question order" is one form-level switch and "Shuffle option order" is a
  per-question switch; I found no official statement of how it treats "Other" or sections, and no way to
  pin an option (w-search, <https://support.google.com/docs/answer/2839737>). Do not cite Google Forms as
  precedent for a lock.
- Moodle shuffles questions only within a section; sections are the way to keep some questions fixed
  (w-search, same Moodle thread as 2.4). Brightspace has per-section shuffle (existing research 2.3).
- Lesson: pages-as-shuffle-units is unusual. Among the surveyed systems only Moodle/D2L shuffle sections,
  and Microsoft Forms disables shuffle when a form has more than one page. The decision in `answers.md`
  (no page lock; all pages shuffle, or leave `shuffle_pages` off) is consistent with Moodle's
  whole-section model, and unlike Microsoft's range-lock which has a history of bugs. A page shuffle with
  a form-body instructions page (the intro) still means the instruction page itself moves, so authors
  must be told to keep instructions in the form body (the answer already says so).

### 2.6 Other documented hazards worth carrying over

- Numbered cross-references ("see question 3", "as in the previous question") break under question
  shuffle; every system's guidance says remove them (existing research 5.2, plus the Moodle and Canvas
  guides listed there). The validator cannot detect this; the authoring doc must say so. (i)
- Hints, feedback and explanations that name an option letter break under option shuffle for the same
  reason. (i)
- Shuffle is not proctoring; a Learnosity/Moodle guide set already supports that wording (existing
  research section 4.2).

## 3. What this changes in the spec

1. Keep the diff narrow: `build_served_paper` gains the shuffle; spec 1's storage, path, navigation,
   resume, scoring and option templates are reused. Do not add a new field on `FormProgress`.
2. Fix the results page: replace `question.question_number` with the served position on the
   incorrect-answers list in `course_form_complete.html` (spec 1 deferred this explicitly), keep the list
   in served order, and test it with a shuffled paper. Leave the cohort report and answer-key lists
   authored.
3. Test reload, back, resume and results with a real shuffled paper, not only an injected one; assert
   option order equality across all four, including the dropdown.
4. Validate: knobs only on QUIZ; lock only when options are shuffled; group contiguous, single-page,
   not nested; a still-rejected `when` on QUIZ. Also decide group name uniqueness per page versus
   per form, because question pools will treat the group as a draw unit (section 1.5).
5. Authoring doc must state: lock fixes position, not meaning ("Both A and B" still breaks); no
   cross-question or option-letter references in shuffled forms; keep instructions in the form body when
   `shuffle_pages` is on; shuffle is not proctoring; and the accepted risk that authored page numbers
   appear in URLs (spec 1 UX research).
6. Do not copy Microsoft Forms' range lock; do not claim Canvas shuffles stimulus groups as a unit.
7. Add a user todo: the earlier research's claim that Canvas New Quizzes shuffles stimulus plus
   sub-questions as a unit is contested by Canvas community reports; verify against Canvas
   documentation before citing it in the spec.

## Reference URLs

- <https://tracker-old.moodle.org/browse/MDL-13073> (search summary only; 404 on direct fetch)
- <https://tracker-old.moodle.org/browse/MDL-85090> (search summary only)
- <https://moodle.org/mod/forum/discuss.php?d=6706> (403; search summary only)
- <https://moodle.org/mod/forum/discuss.php?d=446740> and <https://moodle.org/mod/forum/discuss.php?d=398912> (403; search summaries)
- <https://docs.moodle.org/403/en/Description_question_type>
- <https://svnlliurexnet.gva.es/leia/mods-backports/trunk/moodle/lang/en_utf8/help/quiz/shufflewithin.html>
- <https://raw.githubusercontent.com/moodle/moodle/MOODLE_405_STABLE/question/type/multichoice/question.php>
- <https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php>
- <https://community.canvaslms.com/t5/Canvas-Question-Forum/selective-shuffling-of-answer-options-in-a-quiz/m-p/579562>
- <https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-New-Quizzes-Multiple-Choice-lock-answer-option-doesn-t/td-p/240524>
- <https://community.canvaslms.com/t5/Canvas-Question-Forum/Shuffling-the-stimulus-and-its-associated-questions/m-p/509493>
- <https://celt.iastate.edu/learning-teaching-technology/new-quizzes-canvas>
- <https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-koa.master/exercises_tools/multiple_choice.html>
- <https://docs.openedx.org/en/latest/educators/how-tos/course_development/exercise_tools/award_partial_credit_multiple_choice.html>
- <https://git.andalsoftware.com/Andal.LND/edx-platform/src/branch/master/xmodule/capa/capa_problem.py>
- <https://support.microsoft.com/forms/adjust-your-form-or-quiz-settings-in-microsoft-forms>
- <https://techcommunity.microsoft.com/discussions/microsoftforms/shuffle--lock-questions-broken/165781>
- <https://support.google.com/docs/answer/2839737>
- <https://community.articulate.com/discussions/discuss/rise-quiz---resume-problem-when-randomize-question-order/1225289>
- <https://community.articulate.com/discussions/articulate-quizmaker/multiple-choice-questions-anchoring-shuffled-answers>
- <https://community.articulate.com/discussions/rise-360/quiz-randomize-question-order-with-all-of-the-above>
- <https://help.surveymonkey.com/da/surveymonkey/create/randomizing-answers/>
- <https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html>
- Repo: `spec_dd/3. done/2026-11-20_10:30_sacaa-compliance-1-served-paper-record/` (`1. spec.md`, `research_prior_art.md`, `research_known_complaints.md`, `research_ux_patterns.md`), `freedom_ls/form_engine/served_paper.py`, `spec_dd/1. next/sacaa-compliance/research_form_engine_seams.md`.

status: ok
