# Research: Assessment Randomization UX, Exam Integrity, and Keep-Together Grouping

Scope: randomization only (question/page order, option shuffle, stimulus grouping, per-attempt
reproducibility, integrity rationale, pitfalls). Remediation is a separate spec and is excluded here.

---

## 1. What Gets Randomized, Independently

### 1.1 Question/Page Order

Shuffling the sequence of pages or individual questions across the whole quiz so each learner (or
each attempt) sees them in a different order.

**Industry norms.**
- Moodle: a "Shuffle questions" checkbox on the quiz edit screen; questions are drawn in a random
  order for each student. A second mechanism is "Random question from category" — the quiz draws N
  questions out of a larger bank, so not only the order but the selection varies.
- Canvas New Quizzes: "Shuffle Questions" toggle in Quiz Settings, combined with Question Banks
  (pools) from which N of M questions are drawn.
- D2L Brightspace: "Shuffle questions in this section" per section and "Shuffle questions and
  sections within the quiz" at quiz level; also a "Question Pool" per section.
- QTI: the `<ordering shuffle="true"/>` child of `<assessmentSection>` controls shuffling of
  items within that section.

**Pros.** Dramatically reduces direct answer copying between neighbouring learners. Different
learners seeing the same question at different serial positions reduces primacy/recency bias effects.

**Cons.** Questions that contain phrases like "building on your previous answer" or "referring back
to question 3" break when reordered. The fix is to eliminate cross-question references before
enabling shuffle.

### 1.2 Answer-Option Order (Shuffle Within Questions)

Shuffling the order of `QuestionOption`s within a single multiple-choice or checkbox question.

**Industry norms.**
- Moodle: per-question "Shuffle the choices" checkbox; annotated in documentation as "Shuffle
  within questions". Only affects question types that have multiple parts.
- Canvas Classic Quizzes: quiz-level "Shuffle Answers" toggle. Canvas New Quizzes: same toggle,
  plus per-option position locking.
- QTI: `shuffle="true"` on `<choiceInteraction>` (or equivalent interaction type); individual
  options carry `fixed="true"` to prevent them from being moved.
- Open edX: `shuffle="true"` on `<choicegroup>`; individual `<choice fixed="true">` (or the `@`
  sigil in the simple editor) keeps that option anchored.

**Pros.** Even if learners share question order information, they cannot share "option B is
correct" because B is a different option for each person.

**Cons.** See Section 5 (Pitfalls) for the "All of the above" problem and related issues. Option
shuffle must be authoring-opt-in because it is only safe on well-formed questions.

### 1.3 Drawing a Random Subset from a Bank

Selecting N questions from a larger pool of M (N < M) so learners receive different questions
entirely.

**Industry norms.** Canvas Question Banks/Groups, Moodle "Random question" from a category,
D2L Question Pools. This is orthogonal to order shuffle: you can do one, both, or neither.

**Pros.** Highest variation; item bank rotation limits item exposure over time (important for
compliance-exam reuse). Each attempt can draw a fresh subset, making repeated attempts genuinely
different.

**Cons.** Authors must maintain a large enough bank for the drawn subset to be representative;
content auditing becomes more complex. Stimulus-grouped items (Section 2) need special handling
so a whole group is either included or excluded together — a question that depends on a diagram
cannot appear without its diagram.

---

## 2. Keeping Stimulus Groups Together — The Key Concern

### 2.1 What Is a Stimulus Group?

A stimulus group is a block of content (text, diagram, passage, chart, audio) plus one or more
questions that refer specifically to that content. The questions are only answerable in the
context of the stimulus. Examples:

- A SACAA-style question: a diagram of an aircraft system is shown, followed by three questions
  about it.
- A comprehension passage followed by five reading questions.
- A circuit diagram followed by four calculation questions.

When the rest of the quiz is shuffled, the stimulus and all of its dependent questions must travel
as an indivisible unit and must preserve their internal order (stimulus first, then its questions
in their authored sequence).

### 2.2 How QTI Models This

QTI's structural model (versions 2.1, 2.2, 3) uses nested `<assessmentSection>` elements.

**`<assessmentSection>` with `<ordering shuffle="false"/>`.**
A section whose ordering is not shuffled will always appear as a block in the position it
occupies in its parent section. If the parent section is shuffled, the child section is treated
as a single atomic unit and shuffled as a whole, but its internal items stay in their authored
order. This is the primary mechanism for stimulus grouping.

**`keepTogether` attribute.**
`<assessmentSection>` carries a `keepTogether` boolean (default `true`). When `true`, the
section's items must not be split across separately administered chunks (e.g., if a delivery
engine pages items). This enforces the "show the stimulus and all its questions before moving
on" contract.

**Invisible sections.**
An `<assessmentSection>` can be marked non-visible to the candidate (no heading rendered). Its
items are mixed into the outer shuffled pool while the section itself is still the atomic shuffle
unit. This allows "silent grouping" — the learner sees a seamless sequence with no visible
section boundary.

**`<assessmentStimulus>` / shared stimulus.**
QTI 3 formalises shared stimulus via a standalone `qti-assessment-stimulus-ref` element. A
stimulus file is authored once and referenced by N items. The delivery engine renders the stimulus
alongside each item (or once for an item set). This avoids duplication and supports the reference
pattern cleanly.

**`fixed="true"` on individual choice options.**
Within a `<choiceInteraction>`, marking a `<simpleChoice fixed="true">` prevents that option
from moving when `shuffle="true"` is applied to the interaction. This is the mechanism for
pinning "None of the above" to the bottom while shuffling the other options.

### 2.3 How Moodle and Canvas Handle Stimulus Grouping

**Moodle.**
Moodle has no first-class "item set" / stimulus-group concept in its standard question types. The
community workaround is to place stimulus-dependent questions in their own named quiz section and
not enable random questions for that section, while other sections use random questions. However,
there is a known feature request for "quiz groups" to allow grouped questions to appear together
while the group as a whole is shuffled. [Uncertain: the feature request is ongoing as of the
research date; consult MoodleDocs for current status.]

**Canvas New Quizzes.**
Canvas New Quizzes introduces a dedicated "Stimulus" question type. A stimulus block (text,
image, file) is associated with multiple sub-questions. When the quiz shuffles question order,
the stimulus and its sub-questions travel together as a unit. This is the most direct LMS
equivalent of QTI's sectioned stimulus model.

**Gradescope.**
Gradescope supports "subquestion groups" — a parent question with sub-questions. Shuffle applies
to the parent-question level; subquestions within a parent keep their relative order.

**D2L Brightspace.**
Brightspace sections allow per-section shuffle control. A section containing a stimulus and its
questions can have "Shuffle questions in this section" disabled while the quiz-level shuffle is
enabled. The section is presented as an atomic block.

### 2.4 Recommended Data-Model Approach for FLS

Currently, FLS has:
- `Form` → `FormPage` (ordered by `order`) → mixed `FormContent` + `FormQuestion` (both ordered
  by `order` within the page).
- The link between a `FormContent` block and the question(s) it contextualises is purely
  positional — there is no explicit FK.

The recommended approach is to introduce a new `FormGroup` model that sits between `FormPage` and
`{FormContent, FormQuestion}`. This is the FLS equivalent of QTI's nested `assessmentSection`.

Conceptual fields for `FormGroup`:
- FK to `FormPage`
- `order` (position of this group within its page)
- `shuffle_within` boolean: whether the group's own items can be shuffled (almost always `False`
  for stimulus groups)
- `lockable` or `is_stimulus_group` boolean: a hint that this group must travel atomically when
  its parent page is shuffled

`FormContent` and `FormQuestion` items that belong to the group get a FK to `FormGroup` instead
of (or in addition to) `FormPage`. Items not in any group remain directly on the page.

At shuffle time, the page-level shuffle operates on two kinds of atoms: bare `FormQuestion` items
and `FormGroup` blocks. Stimulus groups shuffle as a block; their internal order is always
preserved.

---

## 3. Per-Attempt Stability and Reproducibility

### 3.1 The Problem with Naive Runtime Shuffle

If the question order is computed fresh on every page load using `random.shuffle()`, a learner
who navigates back and forth (or whose session is interrupted) will see a different order each
time. This breaks the user experience and makes audit review impossible.

### 3.2 Seed-Per-Attempt Pattern

The correct approach is to generate one random seed at the start of each attempt and persist it.
All shuffle operations for that attempt derive from this seed. This ensures:

- **Stability within an attempt.** Any page load, back-navigation, or session resume shows the
  same order.
- **Reproducibility for review.** An educator or auditor can reconstruct exactly what the learner
  saw by re-running the shuffle algorithm with the stored seed.
- **Variation across attempts.** Different attempts (different seeds) produce different orders,
  limiting the benefit of memorising a previous sequence.

**Implementation.** Python's `random` module is seeded with `random.seed(seed_value)` and
`random.shuffle()` or Fisher-Yates is applied. The seed can be any string or integer; a UUID is
convenient. Learnosity uses the session ID as the implicit seed (each session is a different seed,
so every student sees a different order; a fixed seed can be set to make all students see the
same order).

**What to store in FLS.**
Add a `shuffle_seed` field (e.g., `UUIDField`, generated at `FormProgress` creation) and a
`realized_order` field (JSONField) on `FormProgress`. The `realized_order` stores the actual
sequence of page IDs and question IDs the learner saw, plus the option order for each question.

Example structure:
```json
{
  "pages": [
    {
      "page_id": "<uuid>",
      "items": [
        {"type": "group", "group_id": "<uuid>", "questions": ["<q_uuid_1>", "<q_uuid_2>"]},
        {"type": "question", "question_id": "<uuid>",
         "option_order": ["<opt_uuid_a>", "<opt_uuid_c>", "<opt_uuid_b>"]}
      ]
    }
  ]
}
```

This JSON becomes the authoritative "what the learner saw" record. Scoring and educator review
read from this record rather than re-deriving the order, which avoids any race condition if quiz
content is later edited.

### 3.3 Audit Trail Value

For compliance contexts (aviation licensing, professional certification), the ability to
demonstrate exactly what questions appeared on a specific attempt, in what order, for a specific
learner, is a hard audit requirement. Storing `realized_order` in `FormProgress` satisfies this
directly. A system that only stores the seed and re-derives is also acceptable but slightly more
fragile (requires the shuffle algorithm to be stable and the content not to have been edited
since the attempt). Storing the explicit realized order is unambiguous and preferred.

---

## 4. Exam-Integrity Rationale

### 4.1 Why Randomization Is Standard Examination Practice

Assessment randomization is a standard defence against two related threats:

**Collusion (peer copying during examination).**
If two candidates sitting near each other (or taking the exam simultaneously online) have the same
question-and-answer order, a glance at a neighbour's screen or a brief message exchange conveys
a directly usable answer. Shuffled question order means the same message ("Q3 is B") maps to
different questions for different learners.

**Item exposure and pre-sharing.**
If every attempt is identical, learners can collaborate post-attempt to reconstruct the full
question set, publish it, and subsequent cohorts memorise answers rather than knowledge. Drawing
from a large bank, or shuffling options, degrades the value of shared answers.

**Research note.** Academic literature on the effect of question order on scores is mixed (some
studies find a small order effect, some find none). For compliance examination the primary driver
is integrity, not eliminating order effects.

### 4.2 Limits: What Randomization Is Not

Randomization is not proctoring. It reduces casual copying but does not prevent a determined
learner from recording questions during an attempt or using external aids. Stronger controls
(time limits, one question at a time, browser lockdown, live proctoring) address different threat
vectors. The FLS feature should be presented accurately: randomization improves integrity at low
implementation cost, but is not a substitute for proctoring requirements in formally regulated
examinations.

---

## 5. Accessibility and Correctness Pitfalls of Shuffling

### 5.1 Positional Option References ("All of the Above")

Options such as:
- "All of the above"
- "Both A and B"
- "None of the above" / "None of these"
- "Options 1 and 3"
- "C only"

...contain implicit references to the absolute position or label of other options. When options
are shuffled, these references become wrong or nonsensical. "All of the above" may no longer be
last; "Both A and B" refers to different options in the shuffled order.

**Solutions used by established systems:**

1. **Per-option position lock (`fixed`).** QTI's `fixed="true"` on a `<simpleChoice>`, Open
   edX's `fixed="true"` on `<choice>` (or `@` in simple editor), Canvas New Quizzes' per-option
   position lock. The option stays where it was authored even when shuffle is on.
2. **Author guidance / validation warning.** Tell authors that option shuffle is unsafe if any
   option contains a positional reference; flag these during authoring.
3. **Redesign the question.** Replace "All of the above" with "All of the listed statements are
   correct" (which remains true regardless of order) or use a multi-select (checkboxes) question
   type instead.

**Recommended for FLS.** Add a `position_locked` boolean on `QuestionOption` (default `False`).
When option shuffle is applied, locked options stay in their authored position; only non-locked
options are shuffled among themselves. Educator documentation should advise authors to lock any
option that contains a positional reference, or better yet, redesign the question to eliminate
such options.

### 5.2 Cross-Question References ("Refer to Your Previous Answer")

Questions that say "building on Q4" or "recall the diagram you described earlier" break when
question order is shuffled. The solution is:

- The author must eliminate such references before enabling shuffle, or
- Use a stimulus group (Section 2) to keep the related questions together in their authored
  order, so relative references within the group remain valid.

### 5.3 "The Diagram Above" / "The Passage You Just Read"

If a `FormContent` block (e.g., a diagram rendered via `<c-picture>`) and its dependent
questions are not in a keep-together group, shuffle can separate the diagram from the questions.
The question now says "refer to the diagram above" but no diagram is visible.

**This is the core motivation for stimulus grouping** (Section 2). The grouping model directly
prevents this failure mode.

### 5.4 Screen-Reader and Keyboard Order

WCAG 2.x requires that the DOM reading order matches the visual presentation order (Success
Criterion 1.3.2 Meaningful Sequence; 2.4.3 Focus Order). When options are shuffled, the shuffled
order must be reflected in the DOM — the template must render options in their shuffled sequence,
not in the original database order with CSS repositioning. CSS `order` or `flex` tricks that
visually reorder without reordering the DOM violate WCAG.

**Practical implication for FLS.** The view/template must receive the shuffled option list and
render `<li>` or `<label>` elements in that order. The shuffled list (from `realized_order`) must
be used as the render sequence, not re-queried from the database (which would return `order`-
sorted results).

### 5.5 Stability Within a Single Page Render

If a quiz page shows multiple questions and each question's options are shuffled independently,
the shuffle must be stable within a single HTTP response. It must not re-shuffle on HTMX partial
refreshes unless the user has explicitly started a new attempt. Using the seeded shuffle
(Section 3) addresses this automatically.

---

## 6. Concrete Recommendations for FLS

### 6.1 Randomization Knobs to Expose (Opt-In per Form)

Add the following fields to the `Form` model:

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `shuffle_pages` | BooleanField | False | Shuffle the order of `FormPage`s for each attempt |
| `shuffle_questions_within_page` | BooleanField | False | Shuffle the order of question-atoms within each page |
| `shuffle_options` | BooleanField | False | Shuffle the order of `QuestionOption`s within each question |

All three default to `False` so existing behaviour is unchanged. Authors opt in explicitly. A
compliance exam might enable all three; a formative quiz might enable only `shuffle_questions_within_page`.

Note: random-subset-from-bank (draw N of M) is a separate, more complex feature; it is not
recommended for the initial implementation because it requires a bank-management UI and changes
the scoring surface area.

### 6.2 How to Model the Keep-Together Stimulus Group

Introduce a `FormGroup` model in `content_engine`:

```
FormGroup
  - form_page (FK → FormPage)
  - order (PositiveIntegerField)
  - shuffle_internal (BooleanField, default=False)
    # True: items within this group can be reordered among themselves.
    # False (usual for stimulus groups): items keep their authored order.
  - title (CharField, blank=True)  # optional, for educator tooling

FormContent / FormQuestion
  - group (FK → FormGroup, null=True, blank=True)
    # Null = item belongs directly to the page (not in any group)
```

When building the page's item sequence for rendering:
1. Collect all `FormGroup`s on the page plus all "ungrouped" `FormContent`/`FormQuestion` items.
2. Treat each `FormGroup` as an atomic unit whose position is one element in the page-level shuffle.
3. When a group is placed, render its `FormContent` and `FormQuestion` members in their `order`-
   sorted sequence (or shuffled if `shuffle_internal=True`).
4. Ungrouped items participate in the page-level shuffle individually.

This exactly mirrors QTI's nested `assessmentSection` pattern and Canvas New Quizzes' Stimulus
type.

### 6.3 How to Pin Non-Shufflable Options

Add to `QuestionOption`:

```
position_locked (BooleanField, default=False)
```

When `Form.shuffle_options` is `True`, the shuffle algorithm:
1. Separates locked options (keeping their relative authored order among themselves).
2. Shuffles the remaining unlocked options.
3. Inserts locked options back at their original absolute positions.

This matches QTI `fixed="true"` and Open edX `fixed="true"` semantics.

### 6.4 How to Persist the Per-Attempt Realized Order

Add to `FormProgress`:

```
shuffle_seed (UUIDField, default=uuid.uuid4, editable=False)
  # Generated once at attempt creation; drives all shuffle operations for this attempt.

realized_order (JSONField, null=True, blank=True)
  # Populated on first access (lazy) or at attempt creation.
  # Stores the exact sequence the learner will see (see structure in Section 3.2).
  # Once written, treated as immutable for the life of the attempt.
```

The `realized_order` JSON is written exactly once, at the moment the learner first loads the
quiz (or when `FormProgress` is created, if eager generation is preferred). All subsequent page
renders for this attempt read from `realized_order` rather than re-deriving.

Scoring (in `score_quiz`) must iterate questions in `realized_order` sequence when the order
matters for audit, and must look up each `QuestionAnswer` by `question_id`. The current
`score_quiz` logic iterates `form.pages.all()` then `page.children()` — this already uses
database `order`, not a shuffled order; for scoring correctness the order of iteration does not
affect the score (each question is scored independently). The `realized_order` matters for
display, review, and audit, not for correctness of the score sum.

### 6.5 Educator/Audit Review Requirement

The educator view of a completed attempt must show questions in the `realized_order` sequence
(i.e., the order the learner actually saw), not the canonical database order. This is essential
for:
- Reviewing whether a question made sense in context (did the stimulus appear before its
  dependent questions?).
- Compliance audit: demonstrating that the question set and sequence shown was valid.

The `realized_order` JSON provides everything needed for this. The educator interface should
display a "learner's view" reconstruction using this data.

---

## 7. Summary of Key Decisions

| Concern | Recommended approach |
|---------|----------------------|
| When to shuffle | Opt-in per Form (three independent flags) |
| Stimulus grouping | `FormGroup` model; atomic shuffle unit at page level |
| Option pinning | `position_locked` on `QuestionOption` |
| Per-attempt seed | `shuffle_seed` UUID on `FormProgress` |
| Audit record | `realized_order` JSONField on `FormProgress`, immutable after first write |
| DOM order for accessibility | Template renders from `realized_order` list, not DB `order` |
| "All of the above" hazard | `position_locked` + author guidance; default shuffle=False keeps existing forms safe |

---

## Reference URLs

- [QTI v2.2 Assessment, Section and Item Information Model — IMS Global](https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-ASI-InformationModelv1p0/imsqtiv2p2_asi_v1p0_InfoModelv1p0.html)
- [QTI v2.2.4 ASI Information Model — IMS Global](https://www.imsglobal.org/question/qtiv2p2p4/QTIv2p2p4-ASI-InformationModelv1p0/imsqtiv2p2p4_asi_v1p0_InfoModelv1p0.html)
- [QTI v2.2 Implementation Guide — IMS Global](https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html)
- [QTI v2.1 Implementation Guide — IMS Global](https://www.imsglobal.org/question/qtiv2p1/imsqti_implv2p1.html)
- [QTI v2.1 ASI Information Model — IMS Global](https://www.imsglobal.org/question/qtiv2p1/imsqti_infov2p1.html)
- [QTI v3 Best Practices and Implementation Guide — 1EdTech](https://www.imsglobal.org/spec/qti/v3p0/impl)
- [QTI v3 Beginner's Guide — 1EdTech](https://www.imsglobal.org/spec/qti/v3p0/guide)
- [Complete Guide to QTI — GetMarked](https://digitaliser.getmarked.ai/blog/complete-guide-to-qti/)
- [Moodle: Promoting Academic Integrity in Quizzes — NC State Delta](https://teaching-resources.delta.ncsu.edu/quiz-academic-integrity/)
- [Moodle: Shuffle Quiz Questions — University of Waikato](https://www.waikato.ac.nz/students/eresources/moodle/quizzes/shuffle-quiz-questions/)
- [Moodle: Randomise Groups of Questions Forum — Moodle.org](https://moodle.org/mod/forum/discuss.php?d=398912)
- [Moodle: Random Question Type — MoodleDocs](https://docs.moodle.org/502/en/Random_question_type)
- [Randomising Questions and Variables with Moodle Quiz — UCL Digital Education Blog](https://blogs.ucl.ac.uk/digital-education/2020/12/08/randomising-questions-and-variables-with-moodle-quiz/)
- [Canvas: Shuffling Questions and Answer Options — University of Saskatchewan](https://teaching.usask.ca/articles/2025-03-04-shuffling-questions-and-answer-options-in-canvas-quizzes.php)
- [Canvas: Tips for Quiz Integrity — University of Delaware](https://sites.udel.edu/canvas/2024/10/tips-for-canvas-quiz-integrit/)
- [Canvas: Best Practices — FSU Canvas Support](https://support.canvas.fsu.edu/kb/article/1111-canvas-quizzes-best-practices/)
- [D2L Brightspace: Randomization Options — Arizona Instructional Technology Help](https://help.d2l.arizona.edu/content/instructor-randomization-options)
- [D2L Brightspace: Shuffling Questions in a Section — Community](https://community.d2l.com/brightspace/discussion/4751/shuffling-questions-in-a-section)
- [Open edX: Multiple Choice Problem / Shuffle and Fixed Options](https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-olive.master/exercises_tools/multiple_choice.html)
- [Learnosity: Randomizing Content in Assessments](https://help.learnosity.com/hc/en-us/articles/4402358284049-Randomizing-content-in-Learnosity-assessments)
- [Learnosity: Testing Security Best Practices](https://help.learnosity.com/hc/en-us/articles/360001679477-Testing-Security-Best-Practices)
- [Qualtrics: Choice Randomization](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/choice-randomization/)
- [YouTestMe: Exam Security with Question Randomization](https://www.youtestme.com/maximize-exam-security-using-question-randomization-feature-in-online-exam-software/)
- [WebAIM: Keyboard Accessibility](https://webaim.org/techniques/keyboard/)
- [ATI Testing: Stimulus Questions](https://nextgen.atitesting.com/Product%20Help/Student%20Help/reading_passage_questions.html)
- [Research: To Randomize or Not — ResearchGate](https://www.researchgate.net/publication/326435248_To_randomize_or_not_Examining_effects_of_exam_item_order)
- [Multiple-Choice Randomization — Journal of Statistics Education, 2003](https://www.tandfonline.com/doi/full/10.1080/10691898.2003.11910695)

---

status: ok
reason: comprehensive research on randomization UX, exam integrity, stimulus grouping, per-attempt seed/audit, pitfalls, and concrete FLS recommendations; all major claims cited
