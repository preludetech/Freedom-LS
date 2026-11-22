# Research: prior art

Question: what has already been tried for this, here (`spec_dd/3. done`, `spec_dd/2. in progress`,
git log) or elsewhere, and what happened?

Short answer: no educator attempt viewer has ever been built or removed in this repo (`git log -S`
for `attempt_detail`, `form_progress_detail` and `quiz_attempt` under `educator_interface` finds
nothing). The prior art is the work this spec stands on: the served-paper record, the shuffle, the
learner refactor, the course content preview, the admin `answer_groups` and the application export.
Each one deferred something to this spec, and each sets a constraint the spec has to state.

## 1. Earlier specs and what they left for this one

### `sacaa-compliance-1-served-paper-record` (done, `spec_dd/3. done/2026-11-20_10:30_.../1. spec.md`)

- Stored `FormProgress.served_paper` = `{"seed", "pages": [{"id", "children"}], "options": {q: [opt...]}}`,
  string uuids, written once, lazily, for QUIZ forms only. Old rows stay null. There was no backfill.
- Explicitly **out** of that spec and deferred here: "the admin answer groups and the form export,
  and any per-attempt educator view (`sacaa-compliance-4-attempt-review`)". So the idea's open
  question "`sacaa-compliance-1` may already have moved `answer_groups`" has an answer: **it did not**.
  `freedom_ls/form_engine/queries.py:118` `answer_groups()` still walks `form.pages.all()` in
  authored order and marks undrawn questions "not asked" through `path.has_question`. It does call
  `sitting_path()`, so it gets served membership but not served order.
- `sitting_path()` (`freedom_ls/form_engine/conditions.py:373`) precedence: `served_paper` →
  `asked` (`frozen_path`) → `full_path` for completed → `compute_path`. A completed quiz attempt
  from before spec 1 shipped has no served paper. It reads `asked` if present, else the full form
  in authored order. The review gets this fallback for free, but it has **no seed to show**. The
  spec must say what the review and export show for the seed when `served_paper` is null (blank,
  or a "recorded before served papers" note).
- Missing items: the served paper never drops an id, and `served_path` skips items no longer in
  the form. A served question with none of its served options left falls back to live options.
  The review shows what `SittingPath` gives, so a deleted served question disappears silently. The
  spec should decide whether the review flags "N served items no longer exist" (the stored paper
  still has the ids) or stays silent like the learner results page.
- **Correctness is judged against live options** ("Scoring judges answers against the live
  options", spec 1 Decisions), and stored scores are never rewritten. No per-answer correct/incorrect
  flag is stored. A per-question "correct?" in the review is therefore recomputed now and can
  disagree with the stored `scores["score"]` after an option's `correct` flag is edited. The
  learner results page already handles this case with the `stored_score_outdated` check
  (`learner_interface/views.py`). The spec needs a rule here: reuse that check and show a notice,
  or state that per-question marks are today's marking.
- Option rendering already takes a path: `multiple_choice.html`, `checkboxes.html`,
  `dropdown.html` render `path.options_of(question)` when the context carries a path. Without one
  they fall back to authored order.

### `sacaa-compliance-2-shuffle` (done, `spec_dd/3. done/2026-11-21_11:09_.../1. spec.md`)

- Lists "the educator per-attempt view and export (spec 4)" as out of scope.
- The seed now drives the shuffle (`f"{seed}:pages"`, `f"{seed}:page:{page.id}"`,
  `f"{seed}:options:{question.id}"`), **but `random.shuffle` output is not stable across Python
  versions, so nothing rebuilds an order from the seed**. This bears on the idea's line "an
  inspector can reproduce the paper from the file": the served-order column must be the
  reproduction. The seed is provenance only and cannot be relied on to regenerate the order.
- Open question there, deferred here: "Should the served paper record group membership for the
  audit view? → No ... `sacaa-compliance-4-attempt-review` can add it." Groups live on the model
  rows (`group` key). The spec should say yes or no. The default carries over: no change to the
  paper shape.
- Learner-facing numbering: `get_incorrect_quiz_answers` returns `number` from
  `path.question_positions()` (served position). Reports and `data-testid` keep the authored
  `question_number`. The review should number questions the way the learner saw them (served
  position) to match the learner's results page. Say so explicitly.
- Demo data for QA exists: `demo_content/functionality_demo_shuffled_quiz/` (all three shuffle
  knobs on, a locked "All of the above", a group with a picture).

### `sacaa-compliance-3-question-pools` (in progress, `spec_dd/2. in progress/sacaa-compliance-3-question-pools/idea.md`)

- Draws N of a page's questions into the served paper. Same paper shape. `max_score` = served
  count. Lists "the educator per-attempt view and export of the draw" as out (line 83). Nothing
  to build for it here beyond reading `sitting_path()`. An undrawn question is simply absent from
  the path.

### `educator-interface-refactor-5-learner` (done 2026-11-22, `spec_dd/3. done/2026-11-22_12:05_.../`)

- Created `freedom_ls/educator_interface/panels/learner/` (`config.py`, `instance_view.py`,
  `panels.py`, `quick_view.py`, `data_tables.py`, `messages.py`, ...) with one-way import rules
  inside the area (`quick_view` ← `panels`, `panels`/`messages` ← `instance_view` ← `config`). A
  new attempt module must fit that import order. The spec should name where it goes.
- `visible_registrations_with_progress` stays in `panels/learner/quick_view.py`. It is the
  visibility filter the Courses tab already uses.

### Downstream that depends on this spec's choices

- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-5-answered-version-review/idea.md`
  extends **this** page and says "the panel placement, framework and educator-interface conventions
  are those the attempt review set". It plans to:
  - replace the current-wording rule with the answered version;
  - gate question/answer detail behind a new permission, leaving a "score and pass/fail only"
    view;
  - write an audit entry per full-review open, "following the `conversation.viewed` precedent:
    the viewer is the actor, the attempt is the target, the learner is a subject, and the
    organisation is the learner's";
  - gate the quick view the same way. A quick view with no question detail needs no audit entry;
  - add a version-number cell to the export "next to the served-order and seed cells".
  So the page should keep the summary (score, %, pass mark, verdict, times, attempt number)
  separate from the question detail. The export should put served order and seed in per-attempt
  cells. If this spec writes no audit entry, spec 5 adds it, and an action code chosen here
  should be one spec 5 can reuse.
- `spec_dd/1. next/sacaa-compliance-content-versions-and-access-4-question-access/idea.md`
  plans a `question.viewed`-style action (verb `viewed`, new noun `question`, glossary first),
  written only on the HTMX request that renders the content. "Gating the attempt review" is
  explicitly left to spec 5.

## 2. Existing code this spec reuses or must change

- **Attempts table** (where the link and quick view go):
  `freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html:37-61`,
  a hand-written `<c-panel-table>` inside `LearnerCoursesPanel`
  (`panels/learner/panels.py:100`). Rows come from `QuizResult.attempts: list[QuizAttempt]`
  (`freedom_ls/reports/report_data.py:50-77`), built by `_quiz_result_for`
  (`freedom_ls/reports/gather.py:392`) out of `FormProgressIndex.completed_attempts_by_learner_form`.
  - `QuizAttempt` carries **no `FormProgress` id and no start time**. A row cannot link anywhere
    until `QuizAttempt` gains the sitting's pk, and the quick view's "started" needs `start_time`.
    `QuizAttempt` is shared with the cohort report and PDF (`reports/`), so the spec must accept
    a field added there.
  - The table already lists **completed attempts only** (`_quiz_result_for` skips rows with no
    `completed_time`), which matches the answers.md decision.
  - **Attempt number is not stored.** It is `len(attempts) + 1` over completed sittings, oldest
    first, per course progress record (`keyed_by="course_progress"`). The review page must
    compute "attempt N" the same way, or the page and the row will disagree. One helper should
    serve both.
- **Quick views in the framework are tied to a `ListViewConfig` row.** `QuickView`
  (`freedom_ls/panel_framework/quick_view.py`) is served by `_handle_quick_view`
  (`panel_framework/views.py:1199`), which 404s unless the section is a `ListViewConfig` with
  `quick_view` set. The route is `<section>/<pk>/__quick-view` (`views.py:653-690`). The
  attempts table is not a `DataTable`, so there is no existing hook for a quick view on its rows,
  and no section lists `FormProgress`. The spec must choose between three options. (a) A new
  section (`ListViewConfig` with `model = FormProgress`, an `instance_view` and a `quick_view`)
  that is reachable but has no menu entry. Sections today are sidebar destinations
  (`SectionConfigBase`), and nothing found hides a section from the menu while keeping its paths;
  `is_visible`/`is_available` false makes every path 404. (b) A framework addition for a child
  instance page under the learner. (c) A panel action on the learner page that opens a dialog or
  sheet. This is a framework-shape decision. The answers chose "its own instance page", so (a)
  or (b), and the framework change, if any, belongs in the spec.
- **Read-only form rendering with answers already exists**: `_form_preview_context`
  (`freedom_ls/educator_interface/panels/course/content_preview.py:313`) renders form pages
  through the learner's page partial with `read_only=True`, `show_answer_key=True`,
  `existing_answers={}`, `path=full_path(form)`, `question_positions`. Swapping in
  `sitting_path(form_progress)` and the attempt's answers gives "every page, block and question
  served, in order, options in served order, with the learner's answers and the key". This is
  the closest prior art to the review body. Its layout rule (educator-interface skill) is: the
  previewed content sits in the reading column (`max-w-reading mx-auto`).
- **Admin per-attempt answers**: `answer_groups` (`form_engine/queries.py:118`) → `admin.py:295`
  → `templates/admin/form_engine/_answers.html`. Still authored order, still lists undrawn
  questions as "not asked". The `FormProgress` admin already shows `served_paper` read-only
  (`admin.py:359,378`), so the seed is visible to superusers today.
- **"The existing form export" is the course-application export, not a quiz export.**
  `freedom_ls/form_engine/exports.py` (`answer_columns`, `off_path_question_ids`, `answer_cell`)
  has exactly two consumers: `freedom_ls/course_applications/resources.py`
  (`CourseApplicationResource`, rows = applications) and `course_applications/api.py:90`. No
  export of quiz `FormProgress` rows exists anywhere: not in the educator interface (the only
  panel exports are the audit log and the learners table), and the `FormProgress` admin has no
  import-export resource. Applications are never QUIZ forms, so they never have a served paper.
  **Adding served-order and seed columns to the existing export would add columns that are always
  blank.** This contradicts the idea's assumption and is the largest finding here. The spec has
  to pick one: (a) a new quiz-attempt export that reuses `answer_columns`/`answer_cell` (authored
  columns, "Not asked" for undrawn) plus served-order and seed cells; (b) a CSV/download of one
  attempt from the review page; (c) drop the export from this spec. Check with the user before
  writing the spec.
- **Scores and verdict**: `_score_attempt` (`reports/gather.py:366`) reads stored
  `scores["score"]`/`["max_score"]` and guards `quiz_percentage()`/`passed()` `ValueError`s.
  `FormProgress.passed()` (`form_engine/models.py:403`) compares against the form's **current**
  `quiz_pass_percentage`. The pass mark is not stored on the attempt, so if an author changes the
  pass mark, past verdicts change. The idea settles "pass mark applied is the form's
  `quiz_pass_percentage`". The spec should record that this is today's pass mark, as it already
  does for wording, and reuse `_score_attempt` so the page and the table agree.
- **Audit precedent**: `conversation.viewed` (`audit_log/actions.py:275`), written in
  `panels/learner/messages.py:229` only on the HTMX request that renders the thread (`Http404`
  otherwise), with actor = viewer, target = conversation, `subjects=[learner]`,
  `organisation=learner.organisation`. New actions must follow the domain glossary first
  (`audit_log/tests/invariants/test_vocabulary.py` enforces the vocabulary).

## 3. Elsewhere (from knowledge of the products; URLs for reference)

- **Moodle quiz "Review attempt"** (`mod/quiz/review.php`): a summary table at the top (Started
  on, State, Completed on, Time taken, Marks, Grade), then every question in the attempt's own
  slot order, each with the learner's response, right/wrong marking and the right answer. Pages
  can be shown one at a time or "show all questions on one page". The served order is stored per
  attempt (`quiz_attempts.layout`, plus each question usage's slot order and chosen random
  variant). Reproduction uses that stored layout, not a re-run seed. Moodle also stores a text
  snapshot per question attempt (`questionsummary`, `rightanswer`, `responsesummary`) so
  reports survive later edits, which is the `content_snapshots` concern this spec keeps out of
  scope. https://docs.moodle.org/en/Quiz_reports, https://docs.moodle.org/en/Quiz_settings#Review_options
- **Moodle "Responses" report** exports one row per attempt with per-slot response and right-answer
  columns in slot order. Its columns are positional (Q1..Qn), not per question. That is the
  opposite of the idea's "per-question columns stay in authored order". The FLS choice keeps
  answer cells comparable across attempts and puts the order in its own cell. Moodle's report is
  where an inspector-style export of served order is a known need.
  https://docs.moodle.org/en/Quiz_responses_report
- **Canvas** (classic quizzes) shows an educator one submission in SpeedGrader with the questions
  in the order that student received, plus a "View Log" of the attempt's events. There is no
  seed. Order is per submission. https://community.canvaslms.com/t5/Instructor-Guide/How-do-I-view-a-quiz-log-for-a-student-in-a-course/ta-p/1166
- Common thread: every product stores the served order as data and shows a summary block first,
  with the question detail below. None relies on replaying a seed. This matches spec 2's decision
  that the stored lists are the record.

## 4. What the spec must say, from this prior art

1. Export: the existing export is the application export and quiz attempts have no export. Decide
   new quiz-attempt export, per-attempt download, or drop, before anything else (§2).
2. How the attempt instance page and its quick view are routed, given that quick views and
   instance pages hang off `ListViewConfig` sections that appear in the menu (§2).
3. `QuizAttempt` gains the `FormProgress` pk (and `start_time` for the quick view). Attempt
   number comes from one shared computation (§2).
4. Per-question "correct" is recomputed against live options. Say how disagreement with the
   stored score shows (§1, spec 1).
5. Seed and served order for a completed attempt with no served paper (pre-spec-1 rows) (§1).
6. Question numbering in served position, matching the learner results page (§1, spec 2).
7. Keep summary and question detail separable, and choose an audit action code that spec 5 can
   reuse or leave to it (§1, downstream).
8. `answer_groups`: still authored order. Move it onto served order here or leave it. The idea
   lists it as open, and spec 1 did not move it (§1).
9. Reuse `_form_preview_context`'s rendering (read-only page partial with path and answer key)
   rather than new question markup (§2).

status: ok
