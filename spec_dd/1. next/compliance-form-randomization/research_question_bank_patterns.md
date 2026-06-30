# Research: Question-Bank / Pool Randomization Patterns in LMSs

**Scope:** How established systems model question banks/pools, implement random selection, record the served set per attempt, handle scoring fairness, and support authoring ergonomics. This informs the FLS "question pool randomization" idea only — remediation, feedback loops, and retry pedagogy are out of scope.

**FLS context snapshot (for grounding):** A `Form(strategy=QUIZ)` holds ordered `FormPage`s; each page holds ordered `FormContent` (markdown) and `FormQuestion`s (with `QuestionOption`s, `correct` flag). `score_quiz()` iterates `form.pages.all()` and counts every question toward `max_score`. `FormProgress` stores `scores = {"score": N, "max_score": M}` in a JSON field. `QuestionAnswer` is keyed `(form_progress, question)` — no "which questions were served" set exists today.

---

## 1. Reference Implementations

### 1.1 Moodle — Question Bank + Random Question Type

Moodle's quiz module uses a two-layer architecture:

**Question bank (content layer):** Questions are authored once and organised into *categories* (and sub-categories). Categories are site- or course-level containers. The `question_bank_entries` table links each question to a `questioncategoryid`. Tags can additionally be applied for cross-category filtering.

**Quiz slot (assembly layer):** A quiz is built from *slots*. A slot can reference either a specific question (static) or act as a *random question placeholder*. In Moodle 4.x, a random slot is described by a row in `question_set_references` where `component = 'mod_quiz'`, `questionarea = 'quiz_slot'`, and `itemid = quiz_slots.id`. The selection criteria are stored as JSON in the `filtercondition` column — e.g., `{"questioncategoryid": 42, "includingsubcategories": true}` (legacy format) or `{"filter": {...}}` (newer format with tag support).

**Per-attempt resolution:** When a learner starts an attempt, Moodle resolves each random slot by querying the bank for eligible questions (latest "Ready" version in the category, excluding questions already used by other slots in the same attempt, excluding essay/description types). The chosen question ID is attached to the `question_attempts` row for that slot. Internally, the random question type stores the actual drawn question ID as `_realquestionid` in `question_attempt_step_data` (underscore prefix = engine-internal data). On resume, the same `question_attempts` row is re-used, so the student sees the same question — redraw happens only on a *new* attempt.

**Scoring:** Moodle always adds random questions as worth 1 mark regardless of the source question's configured marks — a documented limitation. The quiz's `sumgrades` for the attempt is computed from the marks earned across all resolved question attempts.

**Key tables:** `quiz_slots`, `question_set_references`, `question_attempts` (one per slot per attempt), `question_attempt_steps`, `question_attempt_step_data`.

Sources: [Random question type — MoodleDocs](https://docs.moodle.org/502/en/Random_question_type), [Question banks — MoodleDocs](https://docs.moodle.org/502/en/Question_banks), [Moodle forum: where are random questions stored in 4.x?](https://moodle.org/mod/forum/discuss.php?d=444993), [Quiz attempts table — Zoola schema](https://moodleschema.zoola.io/tables/quiz_attempts.html), [Question engine overview — MoodleDocs](https://docs.moodle.org/dev/Overview_of_the_Moodle_question_engine)

---

### 1.2 Canvas — Classic Quizzes Question Banks + Question Groups; New Quizzes Item Banks

**Classic Quizzes:**
Questions live in a *Question Bank* (course- or account-level). A quiz is built from *question groups*. A group has: (a) a link to a bank, (b) `pick_count` (draw N), (c) `question_points` (points per drawn question, uniform). At attempt start, the engine randomly draws exactly `pick_count` questions from the linked bank. The point total for the group is therefore always `pick_count × question_points`, keeping max_score constant regardless of which questions were drawn.

**New Quizzes (Item Banks):**
The newer engine uses *Item Banks*. A quiz can contain a `BankEntry` item type, which specifies a `sample_num` — the count to randomly draw from the bank. All drawn items use the quiz's per-item point value. The API exposes `BankEntry` and `BankItem` types; drawn items are `BankItem` entries only retrievable via API. Stimulus questions (passage-linked question groups) cannot be placed in an Item Bank and must be inline.

**Scoring:** Both systems use a fixed-draw-count approach — the author specifies exactly how many to draw, so `max_score = draw_count × points_per_question`. Different learners see different questions but the denominator is identical.

Sources: [How to create random quizzes in Canvas — Pitt](https://teaching.pitt.edu/resources/how-to-create-random-quizzes-in-canvas/), [Canvas: add random set from item bank in New Quizzes — Fullerton](https://canvashelp.fullerton.edu/m/Making_the_Most_of_Canvas/l/1866553-how-do-i-add-a-random-set-of-questions-from-an-item-bank-in-new-quizzes), [New Quiz Items API — Canvas](https://canvas.instructure.com/doc/api/new_quiz_items.html), [Randomising Canvas quizzes — USask](https://teaching.usask.ca/articles/2025-03-04-randomizing-canvas-quizzes-using-item-banks.php)

---

### 1.3 Articulate Storyline 360 — Question Banks + Draw

Storyline has a dedicated *Question Bank* panel (separate from the course scene structure). A bank is a named collection of question slides. A quiz scene references the bank via a *Draw* configuration: authors pick a bank, set "Include X questions" (a count, or "All"), and check "Draw questions randomly" to shuffle. Per-question control: an "Include in Shuffle" column lets the author mark individual questions as *Always* (guaranteed to appear), *Never* (excluded from the pool), or *Randomly* (eligible for the draw).

Multiple draws from the same bank can coexist. Questions within a bank can be pinned to the top of a draw order ("lock to top").

**Resume/stability issue:** Because Storyline publishes as a SCORM package, the LMS's suspend/resume data governs whether the same draw is re-served on resume. Community reports document that some LMSs re-draw from the bank on resume rather than restoring the original draw, corrupting continuity. This is a known gap in the SCORM interaction.

Sources: [Storyline 360: Understanding Question Banks — Articulate](https://community.articulate.com/kb/user-guides/storyline-360-understanding-question-banks/1088644), [Storyline 360: Drawing Slides from a Question Bank — Articulate support](https://www.articulatesupport.com/article/Storyline-360-Drawing-Slides-from-a-Question-Bank), [How to randomize quiz questions — Articulate blog](https://community.articulate.com/blog/articles/how-to-randomize-quiz-questions-in-storyline-360/1127311)

**Articulate Rise 360:**
Rise added Question Banks (released ~2024). A quiz lesson can use "Draw from Question Bank" — selecting a bank, choosing "Random Questions" mode, and specifying a number-of-questions count. Questions are drawn randomly each time a learner encounters the quiz. The bank is reusable across multiple quizzes within the same course (and, in some configurations, across courses).

Sources: [How to use question draw in Rise 360 — Swift eLearning](https://www.swiftelearningservices.com/how-to-use-question-draw-in-articulate-rise-360/), [New feature in Rise 360: Question Banks](https://community.articulate.com/discussions/rise-360/new-beta-feature-in-rise-360-question-banks), [Rise 360: Use Question Banks — Articulate](https://community.articulate.com/kb/user-guides/rise-360-use-question-banks-to-create-knowledge-checks-and-quizzes/1118531)

---

### 1.4 IMS QTI — `selection` and `ordering` Elements

QTI (v2.1, v2.2, v3.0) has first-class XML constructs for randomised delivery.

**Structure:** A test has `testPart` > `assessmentSection` > `assessmentItemRef` (references to external item files by URI). A bank is simply an `assessmentSection` containing many `assessmentItemRef` elements.

**`<selection>` element (child of `assessmentSection`):**
- `select` attribute: integer, how many children to include (draw count).
- `withReplacement` attribute: boolean, whether an item can be drawn more than once (almost always false).
- Items marked `required="true"` are always included before the random draw fills the remaining slots.

**`<ordering>` element (sibling of `<selection>`):**
- `shuffle` attribute: boolean, whether the order of the selected items is randomised.

**Example pattern (QTI 2.2 XML):**
```xml
<assessmentSection identifier="bank" visible="false">
  <selection select="20" withReplacement="false"/>
  <ordering shuffle="true"/>
  <assessmentItemRef identifier="q001" href="items/q001.xml"/>
  <assessmentItemRef identifier="q002" href="items/q002.xml"/>
  <!-- ... 50 total items ... -->
</assessmentSection>
```
The delivery engine reads `select="20"`, draws 20 from the 50 refs at random, then shuffles them. The resulting *instance* (the resolved set with a specific sequence) is what gets presented and must be persisted by the engine to support stable resume.

**Result / attempt record:** QTI itself does not mandate a storage format for the resolved draw. Delivery engines are responsible for persisting the resolved item list per attempt — typically in a Result XML (`assessmentResult`) or in proprietary storage. The spec says the resolved section must be stable for the duration of an attempt.

Sources: [QTI 2.2 Implementation Guide — IMS Global](https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html), [QTI 2.2 ASI Information Model — IMS Global](https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-ASI-InformationModelv1p0/imsqtiv2p2_asi_v1p0_InfoModelv1p0.html), [QTI v3 Best Practices — IMS Global](https://www.imsglobal.org/spec/qti/v3p0/impl)

---

### 1.5 Aviation CBT (Gleim, King, SACAA Prep)

Large aviation knowledge-test prep systems (Gleim: 760+ PPL questions; King Schools; SACAA prep providers) treat the question bank as the primary artefact and generate each practice session by randomly drawing a configurable count from the pool. SACAA maintains a Central Question Bank from which its computer-based tests draw per candidate sitting. The mechanics mirror the "draw N from a large pool, score N/N_drawn" approach. Per-sitting stability (same questions for the duration of a sitting) is enforced by the test delivery system. Specific database schemas are proprietary and not publicly documented.

Sources: [Gleim Aviation: Create a Study or Test Session](https://www.gleim.com/aviation/software/features/session.php), [SACAA Examinations page](https://www.caa.co.za/industry-information/personnel-licensing/examinations/), [SACAA exam prep — Aeroversity](https://aeroversity.co.za/pilot-exams-question-bank/), [PPRuNe: Question Bank for SACAA ATPL](https://www.pprune.org/african-aviation/printthread-602598-question-bank-sacaa-atpl.html)

---

## 2. Selection Mechanics and Data Model Patterns

### 2.1 Draw patterns

**Pattern A — Pick-1-of-N (isomorphic variants):** One slot in the quiz always represents "question about topic X", but the specific phrasing/values come from a pool of equivalent variants. The student sees one variant; every student sees *a* question about X. Fairness is near-perfect because variants are designed to be equivalent in difficulty.

**Pattern B — Draw-N-from-larger-pool:** A quiz draws N from a pool of M (M > N). Students may see completely different questions. This is the dominant pattern in Moodle, Canvas, Articulate, and QTI.

Most systems use Pattern B. Pattern A is recommended by psychometricians when question-level fairness is critical (see NUS recommendation: create per-slot pools of difficulty-matched variants).

### 2.2 Pool metadata

- **Category/collection:** The most common metadata unit. Moodle and Canvas group questions into named categories/banks. A draw is from a whole category (optionally including sub-categories).
- **Tags:** Moodle 4.x supports tag-based filtering as an alternative to pure category membership. This allows cross-cutting draws (e.g., "draw 5 questions tagged `#hard` AND `#navigation`").
- **Per-question:** `required` (always include), `fixed` (never shuffle order), and `weight` are per-question attributes in QTI. Articulate's per-question "Always/Never/Randomly" is equivalent.

### 2.3 Recording the served set

Every mature system separates the *quiz definition* (which pool/category to draw from) from the *attempt instance* (the specific drawn set):

| System | How the drawn set is recorded |
|--------|-------------------------------|
| Moodle | `question_attempts` row per resolved slot; drawn question ID stored in `question_attempt_step_data` as `_realquestionid` |
| Canvas | Proprietary; the attempt submission stores the actual item IDs presented |
| QTI engines | `assessmentResult` XML or engine-specific persistence; spec requires stability for the attempt lifetime |
| Articulate (SCORM) | SCORM suspend data (unreliable; known resume-draw bug) |

The universal principle: **the resolved draw must be persisted at attempt-start and held stable for the duration of that attempt**. Without this, resume/reload re-draws, causing different questions on the same attempt — a critical correctness bug.

### 2.4 Per-attempt stable seeding

Some systems use a deterministic seed (stored with the attempt) so that the draw can be reproduced without storing the full resolved list. This is an optimisation; storing the full resolved list of question IDs is simpler and universally used where storage is not constrained.

---

## 3. Scoring and Fairness When Learners See Different Subsets

### 3.1 Fixed-count draw: the dominant approach

The simplest and most widely adopted approach is to always draw the same count (N) of questions per attempt. This keeps `max_score = N` (or `N × points_per_question`) identical for every learner, preserving a common denominator.

All production systems examined (Canvas, Moodle, Articulate, QTI) use fixed-count draws. Variable-count draws (where the pool size itself varies) are not a supported configuration in any of these systems.

### 3.2 Fairness concerns with difficulty variance

When questions in the pool differ in difficulty, a fixed-count draw is *ex-ante* fair (each student has the same probability of any question) but not necessarily *ex-post* fair (one student may happen to draw three hard questions, another three easy ones). Academic work on "fair grading algorithms for randomized exams" (arXiv:2304.06254) shows that simple averaging is not always ex-post fair.

**Practical mitigations used in production:**
- **Difficulty tagging / stratified draws:** Draw a fixed quota per difficulty tier (e.g., "3 easy + 4 medium + 3 hard") rather than a purely random draw from a flat pool. Moodle supports this via tag-based filter conditions.
- **Variant pools per question position (NUS / Pattern A):** Design the pool so each "slot" has difficulty-matched variants — you draw 1 from a slot-pool, guaranteeing equivalent difficulty. Works well for small quiz sizes and where variants can be constructed.
- **Score normalization / equating:** Used in high-stakes exams (competitive entrance tests). Per-form difficulty equating adjusts raw scores so a harder set does not disadvantage a student. This is complex and rarely implemented in LMS quizzes; it is typically reserved for multi-form standardised tests.

For **compliance training quizzes** (the FLS context), the fairness concern is lower-stakes: learners either pass or repeat the course. The recommended approach is therefore: design a homogeneous pool (questions of similar difficulty testing the same competency) and use a fixed draw count. Document this as an authoring guideline, not an enforcement mechanism.

### 3.3 What breaks if subset sizes differ

If different learners could happen to get different draw counts (e.g., due to a bug or variable pool size), `max_score` would differ per learner. The current `score_quiz()` in FLS sets `max_score` from the count of questions it iterates — so if only the served set is iterated, `max_score` is correct per-attempt. However, any cross-attempt comparison (leaderboard, cohort stats, pass/fail threshold) becomes invalid unless percentages are used rather than raw scores.

Recommendation: always enforce a fixed draw count at draw time, and record `max_score = draw_count` explicitly on the attempt record so it cannot diverge.

Sources: [Fair grading for randomized exams — arXiv:2304.06254](https://arxiv.org/pdf/2304.06254), [Designing fair quizzes with question pools — NUS Teaching Connections](https://blog.nus.edu.sg/teachingconnections/2023/04/26/designing-fair-quizzes-with-a-question-pool/), [Score normalization — QuestionBang blog](https://www.questionbang.com/blog/2020/03/24/normalization-of-scores-in-competitive-exams/)

---

## 4. Authoring Ergonomics

### 4.1 How authors define a bank without exploding the file

**Moodle:** Questions are authored in the admin UI or imported via GIFT/Moodle XML bulk format. The bank is independent of the quiz definition. The quiz editor has a "Random question" slot type that just references a category name — no question content in the quiz file itself.

**Canvas:** Question banks are authored separately from quizzes. A "Question Group" in the quiz editor links to a bank by name and specifies draw count. Very clean separation.

**Articulate Storyline:** Questions in a bank are standalone slides (identical to quiz slides). The bank panel is a separate view. The quiz scene contains only a "draw" placeholder — no actual question content.

**QTI:** Items are separate XML files, referenced by URI from the `assessmentItemRef`. The bank is a logical grouping of URIs. Clean separation; content management tooling handles bank organisation.

**Common principle:** The question bank is a *separate content namespace* from the quiz structure. The quiz references the bank by identifier (category name, bank slug, section ID), not by embedding questions. This keeps quiz definitions small and banks reusable.

### 4.2 In FLS (file-based authoring via YAML/markdown)

Current FLS content authoring: each `FormQuestion` is ordered within a `FormPage` within a `Form`, all expressed in a file tree. There is no separate bank namespace today.

Options for bank authoring ergonomics in FLS:

1. **Sibling pool directory:** A `Form`-level YAML file declares `pool_size: 10` and a `pool/` subdirectory contains question files that belong to the pool. The importer loads all pool questions into a `QuestionPool` model and the form references the pool by slug. Authors add questions to `pool/` without touching the form YAML.

2. **Inline pool declaration:** A `FormPage` or `Form` YAML key `pool: true` plus `draw_count: 10` marks all its `FormQuestion`s as pool members for that form. Simpler but conflates bank and quiz structure.

3. **Shared bank across forms:** A top-level `banks/` directory, parallel to `forms/`, containing question files tagged by `bank_slug`. Forms reference `bank_slug: nav-principles, draw_count: 20`. This is the most Moodle/Canvas-like approach and supports bank reuse across multiple quizzes.

### 4.3 Opt-in so existing fixed quizzes keep working

Every system surveyed treats randomization as *opt-in*: a quiz with no pool configuration behaves identically to today (ordered, complete, deterministic). This is the correct design principle — adding `draw_count` or `pool_ref` to a form enables randomization; absence of those fields means fixed behaviour. No migration of existing quizzes is required.

### 4.4 Order expression

In all systems, question order within the drawn set is separately configurable from the draw itself:
- "Draw N randomly, present in random order" — most common.
- "Draw N randomly, present in fixed order" — less common; useful when question ordering is meaningful (e.g., increasing difficulty).
- QTI separates these via `<selection>` (what to draw) vs. `<ordering shuffle="true|false">` (how to order the drawn set).

For FLS, this maps to two booleans: `randomize_draw` (which questions) and `randomize_order` (sequence of drawn questions).

---

## 5. Concrete Recommendations for FLS

These are high-level design suggestions, not a spec.

### 5.1 New model: `QuestionPool`

Introduce a `QuestionPool` model associated with a `Form` (or shared across forms):

```
QuestionPool
  form (FK to Form, nullable if shared)
  slug (identifier for cross-form sharing)
  draw_count (int: how many questions to serve per attempt)
  randomize_order (bool: shuffle the drawn set; default True)
```

`FormQuestion` gains an optional `pool (FK to QuestionPool, null=True)`. Questions without a pool FK are "fixed" questions (current behaviour). Questions with a pool FK belong to the pool for that form.

This means:
- Existing `FormQuestion`s with no `pool` FK behave identically today.
- New pool questions are just `FormQuestion`s with `pool` set.
- No new question-type model is needed; the existing `FormQuestion` / `QuestionOption` structure works.

### 5.2 New model: `QuizAttemptDraw` (serves as the "served set" record)

```
QuizAttemptDraw
  form_progress (FK to FormProgress, unique — one draw per attempt)
  pool (FK to QuestionPool)
  drawn_question_ids (ArrayField[UUID] or JSONField: ordered list of FormQuestion PKs)
  created_at (DateTimeField)
```

At attempt start (when `FormProgress` is created and/or when the first page is served), the view selects `draw_count` question IDs at random from the pool and writes a `QuizAttemptDraw` row. On subsequent page loads (resume), the view reads `QuizAttemptDraw` — no redraw. This gives per-attempt stability without seeding complexity.

The `drawn_question_ids` field records the exact sequence to be served, including order.

### 5.3 Scoring change: `score_quiz()` with pool awareness

When `form` has a pool:
- Iterate only the `drawn_question_ids` from `QuizAttemptDraw`.
- `max_score = len(drawn_question_ids)` = `draw_count` (fixed, regardless of pool size).
- `score` = count of correct answers among drawn questions only.

When `form` has no pool (fixed quiz):
- Existing `score_quiz()` behaviour unchanged: iterate all pages/questions, `max_score = total_authored_questions`.

`FormProgress.scores` JSON format stays the same: `{"score": N, "max_score": M}`. `quiz_percentage()` and `passed()` need no changes.

### 5.4 `max_score` stability

Because `draw_count` is a fixed property of `QuestionPool` and is recorded as `len(drawn_question_ids)` in `QuizAttemptDraw`, `max_score` is stable across all attempts and learners. Cross-attempt comparisons (cohort pass rate, educator dashboards) remain valid.

### 5.5 Authoring convention

Suggest the pool be declared in the `Form`'s YAML metadata and questions in a `pool/` subdirectory:

```yaml
# forms/nav-principles-quiz.yaml
strategy: QUIZ
pool:
  draw_count: 20
  randomize_order: true
```

Questions in `forms/nav-principles-quiz/pool/q001.yaml`, `q002.yaml`, etc. are imported as `FormQuestion` rows with `pool` FK set. Questions outside `pool/` are fixed questions as today.

Fixed quizzes need no YAML change.

### 5.6 What is not needed for the basic feature

- No difficulty tagging or stratified draw (can be added later).
- No shared cross-form bank (can be added by making `QuestionPool.form` nullable and adding a slug lookup).
- No tag-based filtering (add later if needed for SACAA topic-area draws).
- No seed-based reproducibility (storing the full `drawn_question_ids` is simpler and equally correct).

---

## Reference URLs

- [Moodle: Random question type (user docs)](https://docs.moodle.org/502/en/Random_question_type)
- [Moodle: Question banks (user docs)](https://docs.moodle.org/502/en/Question_banks)
- [Moodle: Question categories (user docs)](https://docs.moodle.org/dev/Question_database_structure)
- [Moodle: Overview of the question engine (dev docs)](https://docs.moodle.org/dev/Overview_of_the_Moodle_question_engine)
- [Moodle: Question Engine 2 Design (dev docs)](https://docs.moodle.org/dev/Question_Engine_2:Design)
- [Moodle: quiz_attempts table schema — Zoola Analytics](https://moodleschema.zoola.io/tables/quiz_attempts.html)
- [Moodle: question_attempts table schema — Zoola Analytics](https://moodleschema.zoola.io/tables/question_attempts.html)
- [Moodle: question_attempt_step_data table — Zoola Analytics](https://moodleschema.zoola.io/tables/question_attempt_step_data.html)
- [Moodle forum: where are random questions stored in 4.x?](https://moodle.org/mod/forum/discuss.php?d=444993)
- [Moodle: Randomising questions with Moodle Quiz — UCL Digital Education blog](https://blogs.ucl.ac.uk/digital-education/2020/12/08/randomising-questions-and-variables-with-moodle-quiz/)
- [Canvas: How to create random quizzes — Pitt](https://teaching.pitt.edu/resources/how-to-create-random-quizzes-in-canvas/)
- [Canvas: Add random set from Item Bank in New Quizzes — Fullerton](https://canvashelp.fullerton.edu/m/Making_the_Most_of_Canvas/l/1866553-how-do-i-add-a-random-set-of-questions-from-an-item-bank-in-new-quizzes)
- [Canvas: New Quiz Items REST API](https://canvas.instructure.com/doc/api/new_quiz_items.html)
- [Canvas: Randomising quizzes using Item Banks — USask 2025](https://teaching.usask.ca/articles/2025-03-04-randomizing-canvas-quizzes-using-item-banks.php)
- [Canvas: Question groups and randomising — Spring SCS Canvas](https://canvas.springscs.org/courses/234/pages/4-dot-4-questions-groups-randomizing-and-question-banks)
- [Articulate Storyline 360: Understanding Question Banks](https://community.articulate.com/kb/user-guides/storyline-360-understanding-question-banks/1088644)
- [Articulate Storyline 360: Drawing Slides from a Question Bank (support article)](https://www.articulatesupport.com/article/Storyline-360-Drawing-Slides-from-a-Question-Bank)
- [Articulate Storyline 360: How to randomize quiz questions (blog)](https://community.articulate.com/blog/articles/how-to-randomize-quiz-questions-in-storyline-360/1127311)
- [Articulate Rise 360: Use Question Banks (user guide)](https://community.articulate.com/kb/user-guides/rise-360-use-question-banks-to-create-knowledge-checks-and-quizzes/1118531)
- [Articulate Rise 360: How to use question draw — Swift eLearning](https://www.swiftelearningservices.com/how-to-use-question-draw-in-articulate-rise-360/)
- [Articulate Rise 360: New beta feature — question banks (community)](https://community.articulate.com/discussions/rise-360/new-beta-feature-in-rise-360-question-banks)
- [IMS QTI 2.2 Implementation Guide](https://www.imsglobal.org/question/qtiv2p2/imsqti_v2p2_impl.html)
- [IMS QTI 2.2 ASI Information Model](https://www.imsglobal.org/question/qtiv2p2/QTIv2p2-ASI-InformationModelv1p0/imsqtiv2p2_asi_v1p0_InfoModelv1p0.html)
- [IMS QTI v3 Best Practices and Implementation Guide](https://www.imsglobal.org/spec/qti/v3p0/impl)
- [IMS QTI v1.2: ASI Selection and Ordering specification](https://www.imsglobal.org/question/qtiv1p2/imsqti_asi_saov1p2.html)
- [Gleim Aviation: Create a Study or Test Session](https://www.gleim.com/aviation/software/features/session.php)
- [SACAA Examinations page](https://www.caa.co.za/industry-information/personnel-licensing/examinations/)
- [SACAA exam prep — Aeroversity](https://aeroversity.co.za/pilot-exams-question-bank/)
- [Fair Grading Algorithms for Randomized Exams — arXiv:2304.06254](https://arxiv.org/pdf/2304.06254)
- [Designing Fair Quizzes with a Question Pool — NUS Teaching Connections](https://blog.nus.edu.sg/teachingconnections/2023/04/26/designing-fair-quizzes-with-a-question-pool/)
- [Blackboard Ultra: Question Pools](https://help.blackboard.com/Learn/Instructor/Ultra/Tests_Pools_Surveys/ULTRA_Reuse_Questions/Question_Pools)

---

status: ok
reason: Research complete — covers all five requested areas (reference implementations, selection mechanics/data models, scoring fairness, authoring ergonomics, FLS-specific recommendations) with citations.
