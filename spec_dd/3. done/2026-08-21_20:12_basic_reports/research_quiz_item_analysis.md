# Quiz item and distractor analysis research

## Grounding in this codebase

Before recommending anything, it's worth being precise about what data actually exists, because it
constrains what the report can honestly show.

- A quiz is a `Form` (`freedom_ls/content_engine/models.py`) with `strategy = QUIZ`.
- Each attempt is a `FormProgress` row (`freedom_ls/student_progress/models.py`): one per
  `(user, form)` per attempt — students **can and do have multiple `FormProgress` rows for the same
  quiz** (retakes). `scores` is a JSON `{"score": n, "max_score": n}` set by `score_quiz()`.
- Each answer is a `QuestionAnswer` (`form_progress`, `question`, `selected_options` M2M to
  `QuestionOption`, `text_answer`). `unique_together = ["form_progress", "question"]` — i.e. one
  answer row per question **per attempt**, so re-attempts are fully independent answer sets, not
  edits of a previous answer.
- `FormQuestion.type` is one of `multiple_choice`, `checkboxes`, `short_text`, `long_text`
  (`QuestionType` in `content_engine/models.py`).
- `QuestionOption.correct` is a nullable boolean per option. `score_quiz()` currently treats a
  question as "correct" if **any** selected option has `correct=True` — this matters for
  `checkboxes` questions, see Q5 below, because it means the existing scoring logic does not
  currently do partial credit or penalise selecting extra wrong options alongside the right one.
- `FormProgress.get_incorrect_quiz_answers()` already exists and returns, per completed attempt, a
  list of `{question, student_selected: [QuestionOption], correct_options: [QuestionOption]}` for
  every question the student got wrong. This is almost exactly the primitive the per-student report
  section needs — it just needs to be run across all attempts and aggregated across students for the
  cohort-wide section.
- There is no existing "item statistics" or "distractor tally" model/service — this report is new
  build, not exposing something that already exists.

## Bottom line

Concrete recommendations for this report:

1. **Do not compute point-biserial / discrimination indices at all in v1.** With cohorts of 5-50 and
   individual quizzes typically having far fewer *attempts* than that once split by attempt, these
   statistics are unstable-to-meaningless (see Q2). Show **raw counts and percentages only**:
   facility (% correct), and per-distractor pick counts/percentages. This is honest, still highly
   informative, and matches what the user's idea.md actually asked for — nobody asked for
   discrimination indices.
2. **Attempt-selection rule: use each student's *first* attempt per quiz for the cohort-wide
   "content is confusing" analysis (Q3).** First attempt is the least contaminated by
   answer-memorisation from a previous try and is what Moodle defaults to. State this explicitly as
   a caveat on the report page ("Cohort-wide question analysis uses each student's first attempt at
   each quiz, to avoid over- or under-counting practice effects from retakes.").
3. **For the per-student section, show every attempt** (that's explicitly requested), but roll the
   "questions got wrong / distractors chosen" tally up **across all of that student's attempts**, so
   a student who got Q3 wrong on attempts 1 and 2 but right on attempt 3 shows "wrong 2 of 3 times"
   — this is literally what idea.md asks for ("how many times they got it wrong").
4. **Suppress derived statistics below a minimum n; show raw counts always.** Recommend n ≥ 20
   distinct first-attempt students before showing anything framed as a rate/percentage without a
   loud caveat, and never show a computed discrimination/difficulty *label* (e.g. "too easy") below
   that threshold — just show "7 of 9 students got this wrong" as a plain sentence/count, not a
   percentage-with-implied-precision. (See Q2 for the exact reasoning and a workable graduated rule.)
5. **Rank cohort-wide questions worst-first, cap the list, and disclose the cap.** Show the top N
   (e.g. 10, or all if fewer) questions by error rate per quiz, with an explicit line stating how many
   total questions had ≥1 wrong answer and how many are hidden by the cap ("showing worst 10 of 23
   questions with at least one incorrect answer").
6. **Handle question types differently, not uniformly** (Q5): multiple_choice and checkboxes get a
   distractor table; free-text (`short_text`/`long_text`) questions get **no distractor table** —
   there is no "wrong option chosen" concept — instead show only aggregate correctness counts (if
   gradeable) or omit the question from confusion analysis entirely if it's ungraded/reflective.
7. **Always pair every count with its denominator and percentage**, and always show the correct
   option alongside the wrong ones so the table is self-contained on the page (no need to
   cross-reference the quiz elsewhere).
8. **Carry short interpretive-caution text on the report itself** (Q7): a question with a high error
   rate may be *hard-but-well-taught* rather than *badly written*, and small counts can look dramatic
   by percentage alone — the report should say so once, near the top of section 3, not require the
   reader to infer it.

---

## 1. Classical item analysis fundamentals

Classical Test Theory (CTT) item analysis has three components: difficulty, discrimination, and
distractor analysis. All three are computed per-question across a set of test-takers.

### Difficulty (facility index / p-value)

`p = (number of students who answered correctly) / (number of students who answered)`

- Range 0–1 (or reported as a percentage 0–100%). **Higher p = easier question** (this is
  counter-intuitive to the name "difficulty index" — it's really a facility/easiness index).
- Conventional bands (widely cited, e.g. Nevada assessment guidance, TMCC assessment tutorial,
  Assessment Systems / Iteman docs): p > 0.90 is "too easy" (little diagnostic value, everyone gets
  it right); p < 0.20–0.30 is "too hard" (may indicate a flawed item, ambiguous wording, or content
  not taught); the "sweet spot" most commonly cited for maximising discrimination is roughly
  **0.30–0.70** (some sources say up to 0.85 depending on item purpose — mastery-check items are
  deliberately easy).
- Moodle's "facility index" is exactly this p-value (mean score as % of max possible score, so it
  generalises beyond binary-correct items too) and its own docs state "maximum discrimination
  requires a facility index in the range 30%-70%."

### Discrimination

Two common ways to compute it:

**(a) Point-biserial correlation** — the correlation between "got this item right (1/0)" and
"total score on the rest of the test." Moodle's own "discrimination index" is a variant of this: the
Pearson correlation between the question score and either the whole-quiz score or the rest-of-quiz
score.

- Range −1 to +1. A **good item's right answer should correlate with overall ability**: students who
  do well on the quiz overall should be more likely to get this item right.
- Conventional interpretation bands (Assessment Systems / Iteman, widely echoed by university
  testing/assessment centres): ≥ 0.40 excellent, 0.30–0.39 good, 0.20–0.29 marginal (review), < 0.20
  poor/flag for revision, and **negative values mean higher scorers got the item wrong more often
  than lower scorers** — this is a strong signal the item is flawed (miskeyed, ambiguous, or
  measuring something unrelated to the rest of the test) and should always be flagged regardless of
  sample size caveats.

**(b) Discrimination index D from upper/lower groups** (simpler, doesn't need correlation, used in
many teaching-centre guides e.g. classic Kelley/ETS method): split students into a top group and a
bottom group by total score (classically the top 27% and bottom 27%, chosen historically because it
maximises the difference between normally-distributed group means while keeping enough people in
each group), then

`D = p_upper - p_lower`

where `p_upper`/`p_lower` are the proportion of each group who got the item right. Range −1 to +1.
Same interpretive bands as point-biserial are commonly (if loosely) reused: D ≥ 0.40 excellent,
0.30–0.39 good, 0.20–0.29 marginal, < 0.20 poor, negative = flag immediately.

### Distractor analysis

For each **incorrect** option on a multiple-choice item, count how many students chose it (and,
ideally, whether those students tended to be high or low scorers overall — "distractor
discrimination").

- A "functioning" distractor is chosen by a non-trivial fraction of test-takers — commonly cited
  threshold is **≥ 5%** of respondents (Assessment Systems / Iteman convention, echoed in medical-
  education item-analysis literature, e.g. Considine, Botti & Thomas 2005; Hingorjo & Jaleel 2012).
  A distractor chosen by 0% or near-0% of students isn't doing any work — it's not fooling anyone,
  so it isn't discriminating between "knows it" and "doesn't know it," and could be replaced with a
  more plausible wrong answer.
- A **well-functioning distractor should itself have a negative point-biserial** — i.e. it should be
  disproportionately chosen by students who scored lower overall, not by high scorers. If a
  distractor is chosen preferentially by your *strongest* students, that's a strong signal the
  "correct" answer key may actually be wrong, or the distractor is defensible/ambiguous.
- If **one single distractor absorbs most of the wrong answers** while the others get near-zero
  picks, that tells you specifically *what* misconception is common — this is the single most
  actionable output of distractor analysis for a teaching team, and is exactly what idea.md is
  asking for ("what incorrect answers they chose, how many times").

### Sources consulted for Q1
- Moodle: [Quiz statistics calculations](https://docs.moodle.org/dev/Quiz_statistics_calculations),
  [Quiz statistics report](https://docs.moodle.org/502/en/Quiz_statistics_report)
- Assessment Systems (psychometrics vendor, Iteman/CTT documentation):
  [Classical Test Theory: Item Statistics](https://assess.com/item-statistics-classical-test-theory/),
  [Point-biserial correlation for item discrimination](https://assess.com/the-point-biserial-item-discrimination/),
  [Distractor Analysis for Test Items](https://assess.com/distractor-analysis-test-items/)
- TMCC (Truckee Meadows Community College) Assessment tutorial:
  [Multiple-Choice Questions: Difficulty and Discrimination Indices](https://www.tmcc.edu/sites/default/files/documents/asmt-tutorial-difficulty-indices.pdf)
- BMC Medical Education: [Item analysis: the impact of distractor efficiency on the difficulty index
  and discrimination power of multiple-choice items](https://link.springer.com/article/10.1186/s12909-024-05433-y)
  (states the ≥5%-functioning-distractor convention and negative-discrimination expectation for
  distractors)
- Cogn-IQ Encyclopedia: [Item Discrimination — the Discrimination Index (D = pU − pL) & IRT](https://www.cogn-iq.org/learn/theory/item-discrimination/)

---

## 2. Minimum-sample-size caveats

This is the single most important honesty constraint on the report, given cohorts of 5–50 students.

- **Point-biserial / discrimination indices need real sample size to be stable.** General guidance
  from testing/psychometrics practice (Assessment Systems' Iteman documentation, and the classical
  Crocker & Algina rule) treats the standard error of a correlation as roughly `1/sqrt(n)`; a
  commonly cited rule of thumb is that discrimination statistics computed on **fewer than ~30
  respondents are unstable**, and with under ~10–15 they are close to meaningless — a single student
  flipping from right to wrong can swing the correlation dramatically. Upper/lower-27%-group
  splitting (the classical D-index) additionally needs enough students that a "top 27%" group isn't
  just 1–2 people, which for a 5–15-student cohort it usually will be.
- **Practical consequence for this report: do not compute or display item discrimination indices,
  point-biserial correlations, or D-index values at all.** These numbers require a stable
  "total-score ranking" to correlate against, and with 5–50 students split across multiple quizzes
  and multiple attempts, that condition essentially never holds cleanly. This isn't a UI/rounding
  problem — showing a computed "discrimination = 0.14" for an 8-student quiz claims a level of
  statistical validity the data cannot support, and risks the report being used to unfairly label a
  perfectly good but hard question as "bad."
- **What to show instead, always:** raw counts and simple percentages — "6 of 9 students (67%) chose
  option B" — with the denominator always visible next to the percentage. A percentage without its
  denominator implies more precision than exists; showing "67%" next to "(6 of 9)" lets the reader
  correctly discount it themselves.
- **Graduated presentation rule** for facility/error-rate framing specifically (not for raw counts,
  which should always show):
  - **n < 5 respondents on a question:** show only the raw fraction ("2 of 3 wrong"), no percentage
    at all (a percentage of 3 people is misleading precision), and no colour-coding/flagging as
    "high error."
  - **5 ≤ n < 20:** show fraction and percentage together, but suppress any "flagged as difficult /
    needs review" styling — let the reader see the number, don't editorialise on top of it.
  - **n ≥ 20:** percentage and count both shown; it's reasonable to sort/highlight the worst
    questions by error rate, since with n ≥ 20 a >50% error rate is a fairly robust signal even
    without formal discrimination stats.
  - This threshold is deliberately below the ~30 "stable point-biserial" threshold because the
    report never computes point-biserial — flagging "high error rate" from a plain proportion is a
    much lower bar than flagging "good/bad item" from a correlation, and remains defensible at
    smaller n.
- **State the n explicitly wherever a rate is shown**, and if a cohort/quiz combination has very few
  attempts overall, put a one-line note at the top of that quiz's section ("Only 6 students have
  attempted this quiz — treat patterns here as indicative, not conclusive.").

### Sources consulted for Q2
- Assessment Systems: [Iteman: Detailed Definitions of Output Statistics](https://assesshelp.zendesk.com/hc/en-us/articles/360031193071-Iteman-Detailed-Definitions-of-Output-Statistics),
  [Classical Statistics and their Interpretation](https://assesshelp.zendesk.com/hc/en-us/articles/360037560611-Classical-Statistics-and-their-Interpretation)
- ResearchGate discussion thread on the conventional 0.2 point-biserial threshold and its dependence
  on sample size: [Why is the threshold of Point biserial correlation ... 0.2?](https://www.researchgate.net/post/Why-is-the-threshold-of-Point-biserial-correlation-item-discrimination-in-item-analysis-02)
- OnDataSuite knowledge base: [Item Analysis (Technical)](https://kb.ondatasuite.com/knowledge-base/item-analysis-technical/)
  (notes small-n flags many item statistics as unreliable)

---

## 3. The multiple-attempts problem

Options, and their biases:

- **First attempt only.** Cleanest signal of "what does a student who hasn't seen the answers yet
  get confused by." Not contaminated by memorised answers or by having just been shown the correct
  answer (if `quiz_show_incorrect` is on) on a previous try. Downside: throws away information from
  students who retried, and for a student who never got it right on attempt 1 but mastered it by
  attempt 3, "first attempt" alone doesn't show that they eventually got there — but that's fine,
  because the cohort-wide question is specifically "where does the *content* trip people up when
  they first meet it," not "who eventually passes."
- **Latest/last attempt.** Biased toward *reduced* apparent difficulty and *reduced* apparent
  distractor variety, because by the last attempt students who retake have often either learned the
  content for real or partially memorised the correct answer from being shown it (if
  `quiz_show_incorrect=True`) or from familiarity with the question pool. This systematically
  under-counts confusion for exactly the students who struggled most (they're the ones who retook,
  and their later attempts look artificially clean) — the opposite of what a "where is the content
  confusing" report wants to surface.
- **Best attempt.** Same direction of bias as latest attempt but sharper — deliberately picks the
  attempt that looks best, hiding the confusion that a best-attempt-only view exists precisely to
  find. Not appropriate for this purpose (it's a good choice for *grading*, not for *diagnosing
  confusion*).
- **All attempts pooled.** Every attempt counts as an independent data point. Downside: a student who
  retries 5 times contributes 5x the "votes" of a student who only tried once, so the cohort-wide
  distractor counts get dominated by whichever few students retake the most — this isn't "where the
  cohort is confused," it's "where the most persistent retakers were confused," which is a different
  and less useful question. It also mixes early-naive answers with late-practiced answers in the same
  tally, blurring the signal.

**What Moodle does:** the Moodle quiz statistics report defaults to **first attempt only**, with an
explicit toggle to "include data from all attempts" if the instructor wants it, and even then treats
each attempt as a fully independent data point (Moodle's own docs flag this as a known limitation —
"for quizzes that allow multiple attempts, by default the report should only include data from the
first attempt by each student").

**Recommendation for this report:** use **first attempt only** for the cohort-wide "question X /
distractor Y" confusion tallies (research question 3's "content is confusing" purpose), matching
Moodle's default and the testing-literature rationale above (first attempt is least contaminated by
practice/memorisation effects, and weights every student equally regardless of how many times they
retried). For the **per-student** section, show *all* attempts individually (that data is explicitly
requested — "each quiz attempt: final score, when" — and is inherently about that one student's
journey, not the cohort), and roll up "how many times they got each question wrong" across all of
that student's own attempts (see Bottom line #3).

**Caveat text for the report:** near the top of the cohort-wide "Quiz confusions" section: *"Question
and answer-option counts below are based on each student's first attempt at each quiz only, so that
students who retook a quiz multiple times don't dominate the count and so that answers reflect a
student's first, unprompted understanding rather than answers influenced by seeing correct answers on
a previous try."*

### Sources consulted for Q3
- [Quiz statistics calculations — MoodleDocs](https://docs.moodle.org/dev/Quiz_statistics_calculations)
  (states the first-attempt default and all-attempts toggle)
- [Quiz statistics report — MoodleDocs](https://docs.moodle.org/502/en/Quiz_statistics_report)
- ETS Research Report Series: [Does Retest Effect Impact Test Performance of Repeaters in Different
  Subgroups?](https://onlinelibrary.wiley.com/doi/full/10.1002/ets2.12300) (retest/practice effect
  literature — meta-analytic effect size for score gains on retake, attributed partly to item
  memorisation and test-taking familiarity, not just true learning)
- SpeedExam: [Test Retake Policy Guide](https://www.speedexam.net/blog/test-retake-policies/) (industry
  discussion of cooling-off periods specifically to reduce memorisation contamination between
  attempts)

---

## 4. How existing tools present this

### Moodle — Quiz statistics report

Structure (per <https://docs.moodle.org/502/en/Quiz_statistics_report> and
<https://docs.moodle.org/dev/Quiz_statistics_calculations>):

- **Quiz-info block**: number of attempts, mean/median grade, standard deviation, skewness,
  kurtosis, Cronbach's Alpha (overall internal-consistency reliability), "Error ratio," "Standard
  Error."
- **"Statistics for question positions" table**: one row per question position, columns include: Q#
  and type icon, question name (links through to a per-question detail page with the full distractor
  breakdown), number of attempts on that question, **Facility index** (% who scored well on it —
  Moodle's difficulty measure, higher = easier), **Standard Deviation**, **Random guess score** (the
  score an examinee would get by pure random guessing — useful baseline: a facility index close to
  the random-guess score means the item isn't distinguishing knowledgeable students from guessers at
  all), **Intended weight / Effective weight** (how much the question was meant to contribute to
  total score variance vs. how much it actually did), **Discrimination index**, **Discriminative
  efficiency**. Low discrimination values are highlighted with a red background directly in the
  table.
- Clicking through to a question gives the full **per-option breakdown**: each answer option, how
  many/what % of students chose it, and whether it's marked correct — this is the actual distractor
  table.
- A toggle lets the instructor switch between "first attempt only" and "all attempts" for the whole
  report (see Q3).
- **What an educator can conclude:** which questions are mis-calibrated (too easy/too hard for this
  cohort), which questions fail to separate strong from weak students (low discrimination — may be
  ambiguous or miskeyed), and — via the per-question drill-down — exactly which wrong answer is
  the "popular" wrong answer, i.e. the actual misconception.

### Moodle — Quiz responses report

A raw response-list report: one row per attempt (or per student, configurable), with each question's
given answer as a column, state (finished/in progress), and score. It's the raw data grid underlying
the statistics report — good for spot-checking individual students' answers, not for aggregate
pattern-finding on its own. (Referenced via <https://docs.moodle.org/502/en/Quiz_statistics_report>
and Moodle's quiz reports family generally.)

### Canvas — Quiz/Item Analysis

Per Canvas Community docs (<https://community.instructure.com/en/kb/articles/387082-classic-quizzes-quiz-item-analysis>,
<https://community.canvaslms.com/t5/Instructor-Guide/Once-I-publish-a-quiz-what-kinds-of-quiz-statistics-are/ta-p/659>):

- **Quiz Statistics page**: per-question, a horizontal bar breakdown of each answer option —
  correct answer's bar shown in a distinct colour with a check mark, each distractor its own bar —
  with hover tooltips giving exact count and percentage per option. This is a direct, visual
  distractor-count display, essentially the same information Moodle's per-question drill-down gives
  but shown inline rather than requiring a click-through.
- **Item Analysis report (downloadable CSV/table)**: adds a **discrimination index** per objective
  question (Canvas explicitly limits this to questions with an objectively-gradeable answer — i.e.
  not essay/text questions), plus difficulty (% correct).
- **What an educator can conclude:** at a glance, which specific wrong option is pulling students
  away from the right one (visual bar comparison is very fast to scan), and — for objective questions
  only — whether the question discriminates well.

### Open edX — Problem/answer analytics

Per <https://docs.openedx.org/en/latest/educators/how-tos/data/view_answer_data.html> and the
Insights/Performance dashboard docs:

- **Answer Distribution CSV** (`{course_id}_answer_distribution.csv`) — one row per unique answer
  value given, with a count of how many students gave it, downloadable via Instructor > Data
  Download. This is a raw, ungrouped tally, closer to a database export than a designed report — it
  is explicitly recommended for spotting "common mistakes... learner misconceptions... and errors in
  problem components" (i.e. finding a distractor/misconception, and also finding cases where the
  "wrong" answer is actually a defensible alternate correct answer, revealing a badly-keyed
  question).
- **Analytics/Insights "Score Distribution"** — a histogram of scores achieved on a given problem
  (x = points scored, y = number of students), i.e. a difficulty visualisation without any
  discrimination statistic.
- **What an educator can conclude:** open edX deliberately stays close to raw counts rather than
  computing discrimination-style statistics, consistent with its use across enormous MOOC cohorts
  where distributions can be inspected directly; useful precedent for this report's "prefer raw
  counts over derived indices" approach, though our reason (small n) differs from theirs (huge n,
  wants raw fidelity).

### Sources consulted for Q4
- [Quiz statistics report — MoodleDocs](https://docs.moodle.org/502/en/Quiz_statistics_report)
- [Quiz statistics calculations — MoodleDocs](https://docs.moodle.org/dev/Quiz_statistics_calculations)
- [Classic Quizzes Quiz Item Analysis — Instructure Community](https://community.instructure.com/en/kb/articles/387082-classic-quizzes-quiz-item-analysis)
- [Once I publish a quiz, what kinds of quiz statistics are available? — Instructure Community](https://community.canvaslms.com/t5/Instructor-Guide/Once-I-publish-a-quiz-what-kinds-of-quiz-statistics-are/ta-p/659)
- [View Answer Data — Open edX docs](https://docs.openedx.org/en/latest/educators/how-tos/data/view_answer_data.html)
- [12.10. Answer Data — Building and Running an Open edX Course](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/running_course/course_answers.html)

---

## 5. Question-type handling

Mapped to this codebase's `QuestionType` choices (`multiple_choice`, `checkboxes`, `short_text`,
`long_text`):

- **`multiple_choice` (single answer).** Fully standard case — one selected option, either it's the
  correct one or it's a distractor. Build the distractor table directly: for each incorrect option,
  count of students who chose it. Simple and unambiguous.

- **`checkboxes` (multi-select).** Needs an explicit rule because "wrong" isn't binary once multiple
  boxes can be ticked. Concrete rule for this report:
  - Define **fully correct** = selected option set exactly equals the correct option set.
  - Define **wrong** = anything else (missing a correct option, including an incorrect option, or
    both). This matches the codebase's actual current scoring behaviour in `score_quiz()`, which
    treats a `checkboxes` question as correct only via "any selected option is correct" — worth
    flagging as a **pre-existing scoring gap** (a student who ticks one correct + one incorrect box
    is currently scored as correct by `score_quiz()`, which the report's "wrong answers" tally should
    not silently inherit without noting it — see Risks section).
  - For the distractor tally on a `checkboxes` question, count **each incorrect option ticked**,
    independently, across all "wrong" attempts — i.e. if 5 students got the question wrong and 3 of
    them ticked distractor B (whether or not they also ticked the correct option), distractor B's
    count is 3. Also separately show, as its own line, how many wrong attempts **omitted a correct
    option** entirely (a different kind of "wrong" — under-selecting rather than over-selecting) if
    that's easy to compute; if not feasible for v1, at minimum don't hide it silently — a footnote
    that "counts reflect any incorrect option selected; omitted correct options are not
    separately reported in this version" is honest and cheap.

- **`short_text` / `long_text` (free text).** **No distractor analysis is possible** — there's no
  fixed option set to tally. Concrete rule:
  - If the question isn't objectively auto-gradable (no `correct` flag path applies meaningfully to
    free text in the current schema), **omit it from both the per-student "wrong answers" list and
    the cohort-wide confusion tables entirely** — don't force a "correct/incorrect" framing onto
    open-ended text.
  - Optionally (out of scope unless requested), a future version could show a small anonymised sample
    of raw text responses per question purely for qualitative educator review, clearly labelled as
    "not scored, for context only" — but per the "don't build functionality not explicitly
    requested" project convention, this is a note for later, not a v1 recommendation.

### Sources consulted for Q5
Grounded in this repo's own model code rather than external sources — see
`freedom_ls/content_engine/models.py` (`QuestionType`, `QuestionOption.correct`) and
`freedom_ls/student_progress/models.py` (`FormProgress.score_quiz`, `get_incorrect_quiz_answers`,
`QuestionAnswer`).

---

## 6. Presentation

General PDF-table principles applied to this specific data:

- **Order questions worst-first** within each quiz (highest error rate at top), so an educator
  scanning a printed page sees the biggest problem immediately without hunting.
- **Cap the list per quiz** (e.g. top 10 worst questions) **only when the quiz has more questions
  than fit comfortably**, and say so explicitly in a caption line: *"Showing the 10 questions with
  the most incorrect answers, out of 23 questions with at least one incorrect answer (of 30 total
  questions)."* Never silently truncate.
- **Always show the correct option in the same table**, visually distinguished (e.g. bold / a ✓
  marker / a shaded cell), directly above or alongside the distractor rows, so the reader doesn't
  have to flip back to the quiz definition to know what the "right" answer was.
- **Always pair count with percentage and denominator**: "14 of 22 (64%)" rather than either alone.
- **Respect the small-n rule from Q2**: below the stated threshold, drop the percentage and/or the
  "worst-first" highlighting styling, per the graduated rule above.

### Sketch: cohort-wide question/distractor table (one block per quiz)

```
Quiz: "Photosynthesis Basics"  —  18 students attempted (first attempt), 6 questions had ≥1 wrong answer
Showing all 6 questions with at least one incorrect answer.

┌────┬──────────────────────────────────────┬────────────┬─────────────────────────────────────────────┐
│ Q# │ Question                              │ Wrong      │ Answers chosen (wrong attempts only)         │
├────┼──────────────────────────────────────┼────────────┼─────────────────────────────────────────────┤
│ 4  │ What pigment absorbs the most light   │ 12 of 18   │ ✓ Chlorophyll a — correct answer              │
│    │ in the red/blue spectrum?             │ (67%)      │   Chlorophyll b — chosen 8 times (44%)       │
│    │                                        │            │   Carotenoid    — chosen 3 times (17%)       │
│    │                                        │            │   Xanthophyll   — chosen 1 time (6%)         │
├────┼──────────────────────────────────────┼────────────┼─────────────────────────────────────────────┤
│ 2  │ Which gas is released during          │ 5 of 18    │ ✓ Oxygen — correct answer                    │
│    │ photosynthesis?                       │ (28%)      │   Carbon dioxide — chosen 5 times (28%)      │
├────┼──────────────────────────────────────┼────────────┼─────────────────────────────────────────────┤
│ …  │ …                                      │ …          │ …                                             │
└────┴──────────────────────────────────────┴────────────┴─────────────────────────────────────────────┘

Note: counts are based on each student's first attempt only (see report notes). With 18 first
attempts, treat these as indicative percentages, not precise statistics.
```

For a quiz with too few first-attempt students (n < 5), the same layout but with the "Wrong" column
showing only the fraction (no %), and no colour/ranking emphasis:

```
Quiz: "Advanced Genetics Quiz"  —  4 students attempted (too few for reliable percentages; raw counts only)

Q# │ Question                     │ Wrong  │ Answers chosen (wrong attempts only)
 3 │ What is a recessive allele?  │ 2 of 4 │ ✓ Correct: "..." — correct answer
   │                               │        │   "..." — chosen 2 times
```

### Sketch: per-student confusion table (within that student's detail section)

```
Jane Doe — Quiz: "Photosynthesis Basics"

Attempts:
  Attempt 1 — 2026-03-02 — Score: 3/6 (50%)
  Attempt 2 — 2026-03-04 — Score: 5/6 (83%)

Questions gotten wrong (any attempt), with how often and what was selected:

┌────┬─────────────────────────────────────┬──────────────┬────────────────────────────────────────┐
│ Q# │ Question                             │ Wrong        │ What Jane selected, and how often       │
├────┼─────────────────────────────────────┼──────────────┼────────────────────────────────────────┤
│ 4  │ What pigment absorbs the most light  │ 2 of 2       │ Chlorophyll b — 2 times                 │
│    │ in the red/blue spectrum?            │ attempts     │ (correct answer: Chlorophyll a)         │
├────┼─────────────────────────────────────┼──────────────┼────────────────────────────────────────┤
│ 2  │ Which gas is released during         │ 1 of 2       │ Carbon dioxide — 1 time                 │
│    │ photosynthesis?                      │ attempts     │ (correct answer: Oxygen)                │
└────┴─────────────────────────────────────┴──────────────┴────────────────────────────────────────┘
```

---

## 7. Pitfalls and misinterpretation risks

- **Hard-but-good vs. badly-written.** A question with a high error rate could be a genuinely
  discriminating, well-calibrated hard question (which is fine and often desirable), or it could be
  ambiguously worded, miskeyed, or covering something never actually taught. Raw error-rate data
  alone cannot distinguish these — that judgement requires a human who knows the content. **The
  report should not use language like "problem question" or "bad question"; it should use neutral
  framing like "questions with the most incorrect answers"** and let the educator interpret. Suggest
  a standing caption: *"A high error rate does not necessarily mean a question is flawed — it may
  simply be testing something genuinely difficult. Use this list to decide what to review, not as a
  verdict."*
- **Low-n spikes look like trends.** With small cohorts, one or two students choosing the same wrong
  answer can look like "the whole class is confused" once rendered as a bold percentage. The
  graduated small-n rule in Q2 (raw counts only below 5, no ranking/flagging below 20) is the direct
  mitigation; additionally a standing note wherever n is small: *"Based on very few attempts — a
  single student's answer can swing this percentage substantially."*
- **The report could function as a covert teacher/content-owner performance judgement.** Because this
  is a cohort-and-course-scoped internal report seen by educators/staff, there's a real risk it gets
  read as "which educator's content is bad" rather than "where might extra support or content
  revision help." Recommend a standing disclaimer near the cohort-wide section: *"This section is
  intended to help identify content that may benefit from revision or extra explanation — it is not
  a performance evaluation of any educator or cohort."* This is a text/framing decision for spec
  time, not a data decision, but it belongs in the spec because it affects wording throughout.
- **Privacy/ethics of showing individual wrong answers to staff.** The per-student section by design
  shows named students' specific wrong answers to educators/staff. Given this audience (internal
  educators managing that student's learning) that's plausibly within normal LMS use, similar to a
  teacher seeing a marked test paper — but it should not be assumed this same level of individual
  incorrect-answer detail is appropriate for any *other* audience (e.g. other students, external
  parties, or aggregate/public reporting) without separate consideration. Flag this explicitly as an
  open question for spec sign-off: confirm the report's distribution is staff-only, and that no
  student-identifiable version of the report is emailed/shared more broadly without this being
  revisited.
- **Retake gaming / apathy on first attempts.** If students know a first attempt "doesn't count" and
  can retake freely, some may guess/rush their first attempt, which would inflate the cohort-wide
  first-attempt error rate for reasons unrelated to actual confusion. Worth a light-touch mention in
  the caveat text rather than a data mitigation (there's no clean way to detect intentional
  rushing from this data), and something the product owner should be aware could shift behaviour if
  this report becomes visible/consequential to students later.

---

## Proposed tables

(See the concrete sketches under "6. Presentation" above — the two tables are:
per-student confusion table and cohort-wide question/distractor confusion table. Column summary:

**Per-student attempts table:** Attempt # | Date | Score (raw + %) | Pass/fail (if pass % configured)

**Per-student confusion table:** Question # + text | Wrong count / total attempts on that question |
Selected wrong option(s) with per-option count | Correct option (shown inline for reference)

**Cohort-wide confusion table (per quiz):** Question # + text | Wrong count / total first-attempt
students taking that question (+ % if n ≥ 5, ranking/highlight only if n ≥ 20) | Correct option
(marked) | Each distractor with count (+ % if n ≥ 5) | ordered distractors worst (most-picked) first

---

## Risks and open questions

- The `checkboxes` "correct" scoring in `score_quiz()` (any correct option selected = full credit,
  regardless of other selections) is a pre-existing behaviour this report should not silently
  reinterpret differently for "wrong answer" purposes without a spec decision — recommend the spec
  explicitly state the "wrong = selected set != correct set" rule for the *report's* distractor
  analysis even though it diverges slightly from current scoring, and call this out to the user as a
  known inconsistency rather than quietly fixing or ignoring it.
  ` @claude` note: if the team later wants strict-set scoring to also change actual quiz *scoring*
  behaviour (not just the report), that is a separate, larger decision outside this report's scope.
- Whether free-text questions should ever appear in this report (even just as an unscored sample of
  responses) is left open per Q5 — flag for the spec author to explicitly decide in/out for v1.
- The exact per-quiz "top N worst questions" cap value (10 was used illustratively) should be
  confirmed with the user; it doesn't need research, just a product decision.
- Small-n thresholds (5 and 20) proposed here are reasonable, defensible defaults grounded in the
  psychometric literature's own much stricter thresholds (~30 for correlation stability) scaled down
  for a "just show a plain proportion" use case — but they are a judgement call, not a hard
  citation-backed number, and should be treated as adjustable defaults, not immutable constants.

---

## References

- [Quiz statistics report — MoodleDocs](https://docs.moodle.org/502/en/Quiz_statistics_report)
- [Quiz statistics calculations — MoodleDocs](https://docs.moodle.org/dev/Quiz_statistics_calculations)
- [Quiz report statistics — MoodleDocs](https://docs.moodle.org/dev/Quiz_report_statistics)
- [What do Moodle quiz statistics mean? — Jason Hogan, UPEI TLC (Medium)](https://medium.com/upeielo/what-do-moodle-quiz-statistics-mean-bb740777dbfc)
- [Classic Quizzes Quiz Item Analysis — Instructure Community](https://community.instructure.com/en/kb/articles/387082-classic-quizzes-quiz-item-analysis)
- [Once I publish a quiz, what kinds of quiz statistics are available? — Instructure Community](https://community.canvaslms.com/t5/Instructor-Guide/Once-I-publish-a-quiz-what-kinds-of-quiz-statistics-are/ta-p/659)
- [View Answer Data — Open edX docs](https://docs.openedx.org/en/latest/educators/how-tos/data/view_answer_data.html)
- [12.10. Answer Data — Building and Running an Open edX Course](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/named-release-birch/running_course/course_answers.html)
- [Assessment Systems: Classical Test Theory: Item Statistics](https://assess.com/item-statistics-classical-test-theory/)
- [Assessment Systems: Point-biserial correlation for item discrimination](https://assess.com/the-point-biserial-item-discrimination/)
- [Assessment Systems: Distractor Analysis for Test Items](https://assess.com/distractor-analysis-test-items/)
- [Assessment Systems: Iteman Detailed Definitions of Output Statistics](https://assesshelp.zendesk.com/hc/en-us/articles/360031193071-Iteman-Detailed-Definitions-of-Output-Statistics)
- [Assessment Systems: Classical Statistics and their Interpretation](https://assesshelp.zendesk.com/hc/en-us/articles/360037560611-Classical-Statistics-and-their-Interpretation)
- [ResearchGate: Why is the threshold of point-biserial correlation (item discrimination) 0.2?](https://www.researchgate.net/post/Why-is-the-threshold-of-Point-biserial-correlation-item-discrimination-in-item-analysis-02)
- [OnDataSuite: Item Analysis (Technical)](https://kb.ondatasuite.com/knowledge-base/item-analysis-technical/)
- [TMCC: Multiple-Choice Questions: Difficulty and Discrimination Indices](https://www.tmcc.edu/sites/default/files/documents/asmt-tutorial-difficulty-indices.pdf)
- [BMC Medical Education: Item analysis: the impact of distractor efficiency on the difficulty index and discrimination power of multiple-choice items](https://link.springer.com/article/10.1186/s12909-024-05433-y)
- [Cogn-IQ Encyclopedia: Item Discrimination — Discrimination Index (D = pU − pL) & IRT](https://www.cogn-iq.org/learn/theory/item-discrimination/)
- [ETS Research Report Series: Does Retest Effect Impact Test Performance of Repeaters in Different Subgroups?](https://onlinelibrary.wiley.com/doi/full/10.1002/ets2.12300)
- [SpeedExam: Test Retake Policy Guide](https://www.speedexam.net/blog/test-retake-policies/)
- Repo source consulted directly: `freedom_ls/content_engine/models.py`, `freedom_ls/student_progress/models.py`

status: ok
