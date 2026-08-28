# QA 3c — did the progress commit break the form_engine split?

**Run with:** `/fls-dev:do_qa "spec_dd/2. in progress/better_course_progress_tracking/3c. form_engine_regression_qa/frontend_qa_form_engine_regression.md"`

This directory has no `todo.md`. Tick and append against the parent one:
`spec_dd/2. in progress/better_course_progress_tracking/todo.md`, section `## 9. QA`.

**This plan owns the mobile and tablet passes for all three QA runs.** `3a. seam_qa/` and
`3b. progress_gaps_qa/` are desktop-only by instruction, so the responsive work happens once, here, in
§R9.

---

## Why this plan exists

The `form_engine` split moved the code behind every form page in the product into its own app, repointed
around 69 consumer files, and replaced a `post_save` hook with a `form_attempt_completed` signal. It was
QA'd on its own branch — 35 tests, zero bugs — and merged into `main`.

Then this branch landed on top and changed things underneath it: `FormProgress.form` became `PROTECT`, the
signal gained an `attempt` kwarg, every course-side attempt helper moved to
`learner_progress/attempts.py`, and the report layer started reaching form attempts through a new join
model.

So the forms QA's clean result no longer covers the code that ships. This plan re-walks it, corrected and
condensed to what the progress commit could plausibly have broken. The overlap itself — which record an
attempt credits — belongs to `3a. seam_qa/`; do not duplicate it here.

Four things break silently, and each has a section below:

1. **The signal substitution** — course progress is recalculated from an explicit send inside
   `FormProgress.complete()`, now carrying the attempt.
2. **`ContentType.get_for_model(Form)`** — deadlines and cohort reporting resolve forms through the
   content-type table, whose rows are keyed on the app label.
3. **`content_tags.get_content_by_path`** — a `Form` import that runs at template-render time, on every
   request rendering a `<c-content-link>`.
4. **The Django admin** — twelve admin classes moved app, and a thirteenth model appeared.

---

## 0. Setup

### 0.0 Rebuild the database — required, not optional

**Check this before anything else.** This worktree's database was rebuilt on 2026-08-25 and was correct
at that point, so a run starting soon after should find nothing to do here. The check stays because the
failure it catches is silent-adjacent and cheap to miss.

Before that rebuild, the database had been *migrated* across the `form_engine` rebase rather than rebuilt,
and was missing the split entirely: `freedom_ls_form_engine`'s three migrations unapplied, the
`freedom_ls_form_engine_form` table absent, and `django_content_type` still holding stale
`freedom_ls_content_engine.form` rows whose `model_class()` returned `None`. In that state any code that
walks a course containing a form dies with
`AttributeError: 'NoneType' object has no attribute '_base_manager'`. If the branch is rebased again, or
you are on a database from before that date, you will land back in it.

Confirm the state:

```
uv run python manage.py showmigrations freedom_ls_form_engine
```

If any of `0001_initial`, `0002_formprogress_questionanswer` or `0003_alter_formprogress_form` shows
`[ ]`, the database must be **dropped and rebuilt**. The `form_engine` split ships ordinary
`makemigrations` output — `content_engine` deletes five models, `learner_progress` deletes two, and
`form_engine` creates all seven from scratch — so migrating a populated database drops every form, page,
question, option and learner attempt. Its `upgrade_notes.md` says plainly that this release cannot be
migrated onto a database you intend to keep. Rebuilding is the only path, and everything in it is
reproducible from §0.1.

```
.claude/fls-dev/scripts/dev_db_delete.sh
.claude/fls-dev/scripts/dev_db_init.sh
uv run python manage.py migrate
```

`dev_db_delete.sh` drops this branch's `db_better_course_progress_tracking` and its test database only —
it derives the name from the current branch, so no other worktree is touched.

Then run §0.1 in full. After the rebuild, `showmigrations freedom_ls_form_engine` must show all three
applied, and this must print an empty list:

```
uv run python manage.py shell -c "from django.contrib.contenttypes.models import ContentType; print([(c.app_label, c.model) for c in ContentType.objects.all() if c.model_class() is None])"
```

A non-empty list means stale content types survived, and deadlines and cohort reporting will give silent
wrong answers rather than errors.

### 0.1 Seed the data

Every command below was checked against its actual signature. The original forms QA plan ran two of these
bare and they exit 2 that way — the corrected forms are given here.

```
uv run python manage.py create_demo_data
uv run python manage.py content_save "demo_content/functionality_demo_end_with_quiz" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_end_with_topic" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_content_widgets" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_course_parts" DemoDev
uv run python manage.py qa_create_form_question_types
uv run python manage.py qa_create_quiz_progression_block
uv run python manage.py qa_create_free_text_survey
uv run python manage.py qa_create_cohort_progress DemoDev
uv run python manage.py qa_create_learner_deadlines
uv run python manage.py qa_reset_learner_progress --learner demodev_quizqa@email.com
uv run python manage.py recalculate_progress_percentages
```

Corrections carried from the original plan, all of which used to hard-stop a literal-reading tester:

- `qa_create_cohort_progress` takes `SITE_NAME` **positionally and required**. A bare run exits 2.
- `qa_reset_learner_progress` requires `--learner`. A bare run exits 2.
- **Ordering trap:** `qa_create_learner_deadlines` must run **after** `qa_create_cohort_progress`, which
  is what seeds `qa-eve.middle@example.com`. Run the other way round it exits 1 with
  `User 'qa-eve.middle@example.com' not found`. The original forms plan had them the wrong way round.
- **Ordering trap:** `qa_reset_learner_progress` zeroes `progress_percentage` on every in-scope record.
  `recalculate_progress_percentages` must run **after** it, or the dashboard reads 0% and §R2's first
  assertion fails for the wrong reason.

`functionality_demo_content_widgets` saves as slug **`content-widgets-demo-reference`**, not
`functionality-demo-...`.

**Every command above imports form symbols and is itself part of what the split repointed.** A
`ModuleNotFoundError` or `ImportError` from any of them is a QA failure, not a setup problem — record it
and carry on with the ones that do run.

`content_save` must also leave the worktree clean:

```
git status --short demo_content/     # must print nothing
```

A modified file there means a form, page, question or option UUID was not carried through.

### 0.1b Former blocker — two seed commands used to crash. Fixed on 2026-08-27

`qa_create_report_cohort` and `qa_complete_form` both run clean now; the whole of §0.1 was re-run against
a wiped database on 2026-08-27 and seeded without a traceback. Nothing here is blocked any more. The
history is kept only so a re-appearance is recognised rather than re-diagnosed.

Both commands used to die with:

```
django.db.utils.IntegrityError: null value in column "site_id"
of relation "freedom_ls_form_engine_formprogress" violates not-null constraint
```

One root cause. `CourseFormAttemptFactory` took an explicit `site=` for the join row but did not pass it
down to its `FormProgressFactory` sub-factory. `SiteAwareFactory.site` is a `LazyFunction` reading the
thread-local request context, which is unset inside a management command, so the `form_engine` row was
built with `site=None`. Fixed in `2c2b5e35`, which makes the site-aware factories forward `site` to their
nested sub-factories.

If this signature ever comes back, it is a factory problem and not plan drift — mark the dependent steps
`BLOCKED` with this cause rather than `FAIL`, run the rest of the plan, then re-seed and pick them up.

### 0.2 Accounts

| Account | Email | Password | Used for |
|---|---|---|---|
| Admin / educator | `demodev@email.com` | same as email | admin, educator interface, the all-question-types quiz |
| Quiz QA learner | `demodev_quizqa@email.com` | same as email | the progression-block course and the free-text survey |

Learners from `qa_create_cohort_progress` use `testpass123`, and the command does **not** reset the
password of a persona that survived an earlier run. A learner who cannot log in is probably missing a
verified primary allauth `EmailAddress` row — delegate that to the `fls-dev:qa-data-helper` agent.

### 0.3 Course item numbering

The original plan got this wrong and cost the last run time. `functionality-demo-show-end-with-quiz` lays
out as:

| Index | Item | Notes |
|---|---|---|
| 1 | topic | |
| 2 | **Mid course Quiz** | `submit_on_exit: true`, pass 80%, shows incorrect |
| 3 | topic | |
| 4 | **End course Quiz** | pass 50%, does not show incorrect |

### 0.4 Known and already judged — do not re-file

- **`None%` in the educator progress grid.** A completed-quiz cell whose `FormProgress` has `scores=None`
  renders the literal text "None%". Verified byte-identical on `main` in the previous run. Cosmetic,
  pre-existing, belongs to its own ticket.
- **The "last chapter" content link renders as not-found.** No Topic anywhere has file path
  `01-what-is-git-for.md`. A demo-content authoring gap, not a regression.
- **A content link to a Form renders with an empty `href`.** `Form` has no `preview_url`, so
  `content-link.html` emits `<a href="">`. Filed under `## 9. QA` in the parent `todo.md`, together with
  the sibling defect that `Topic.preview_url()` reverses a URL name no URLconf defines. Both belong to
  the content-link spec the `TODO. - non-preview link` in that template already names. Record the anchor
  as the R6.3 pass; do not re-file the href.

---

## R1 [A1–A3] The form player golden path

1. Log in as `demodev@email.com` and go to `http://127.0.0.1:$PORT/courses/qa-question-types-course/`.
   Open item 1.
   **Expect:** the form start page, with the title, a question count and a Start button. The count must be
   **4** — one of each question type. That number comes from `count_form_questions`, which moved app.
2. Click **Start**.
   **Expect:** the runner showing all four questions — a radio group, a checkbox group, a single-line text
   input and a textarea.
3. Answer all four, choosing correctly for the radio and both correct options for the checkboxes, and
   complete.
   **Expect:** the completion page with a score ring and a **passed** banner. Free-text questions never
   score correct, so confirm the percentage matches the ring rather than assuming 100%.
4. **Resume.** Start the **End course Quiz** (item 4 of `functionality-demo-show-end-with-quiz`), answer
   page 1, navigate away without finishing, then return to the same item.
   **Expect:** the start page offers to **resume**, and re-entering shows page 1's answers still selected.
   This runs through the attempt helpers that moved to `learner_progress/attempts.py` on this branch.
5. **A form with no verdict.** Log in as `demodev_quizqa@email.com` and open the survey course seeded by
   `qa_create_free_text_survey`. Fill page 1's required short-text and long-text questions, continue to
   page 2, leave the optional questions blank, and complete.
   **Expect:** **no** score ring, **no** pass/fail banner and **no** incorrect-answer review.
   `CATEGORY_VALUE_SUM` forms have no verdict.
6. Use **Previous** to walk back to page 1.
   **Expect:** the saved free-text answers are still rendered into the input and the textarea.

---

## R2 [B1–B4] The signal substitution

The highest-value section. Read the percentage **before** and **after**; a stale or unchanged percentage is
the failure mode.

1. Log in as `demodev_quizqa@email.com`, go to the dashboard, and note the percentage on the card for
   `qa-progression-block-course`. The first topic is pre-completed, so it should be non-zero and below
   100 — if it reads 0%, `recalculate_progress_percentages` was not run after the reset in §0.1.
2. Open the course, sit the quiz at item 2, answer the checkbox question and all three multiple-choice
   questions correctly, and complete it.
3. Return to the dashboard **and** to the course home page.
   **Expect:** the percentage has **increased**. If it is unchanged, the receiver is not connected or the
   send is not firing.
4. **No double-counting.** Hard-refresh both pages several times.
   **Expect:** the percentage is stable and never exceeds 100.
5. Return to the completed quiz item.
   **Expect:** it reads complete, re-entering does not offer a second attempt that would re-fire the
   signal, and the percentage does not move again. `complete()` returns early once `completed_time` is set.
6. **A pre-completed row.** Run the batch seeder, which is **cohort-scoped** — positional `SITE_NAME`, then
   `--cohort-name` and `--form-slug`. There is no `--learner` option:
   ```
   uv run python manage.py qa_complete_form DemoDev \
       --cohort-name "QA Progress Demo Cohort" --form-slug knowledge-check
   ```
   `qa_create_cohort_progress DemoDev` builds **QA Progress Demo Cohort** on
   `functionality-demo-course-parts`, whose scored quiz is **Knowledge Check** (slug `knowledge-check`).
   The command resolves the course from the form's placement and skips any cohort member not registered
   for it, so a form slug from a different course silently skips everyone.
   **Expect:** it exits 0 and reports how many completions it created and how many learners it skipped.
   **Assert on the attempt rows, not on the percentage.** This command now creates a `CourseFormAttempt`
   and calls `complete()`, so it *does* fire a recalculation — but a failed 0-score attempt moves no
   percentage, so a percentage comparison cannot tell "no recalculation happened" from "a recalculation
   happened and produced the same number". In the admin, open **Course form attempts** and filter to the
   cohort. Each touched learner must have exactly one new row naming the `FormProgress` the command built,
   that learner's course progress record, and the Knowledge Check's collection item; its `FormProgress`
   must carry a `completed_time` and a populated `scores`. Skipped learners must have no such row, and
   their number must match the skipped count printed above.
   `last_accessed_time` must **not** move here, and for a learner who has never opened the course it stays
   empty. The command completes a form without anyone viewing anything, and `last_accessed_time` is a read
   timestamp: only the player stamps it, when a learner opens an item.
7. Then run the batch recalculation:
   ```
   uv run python manage.py recalculate_progress_percentages
   ```
   **Expect:** no `ImportError`, and the dashboard percentages afterwards match what the course pages show.

---

## R3 [B3] A failed quiz blocks the next item

1. Reset so the quiz can be re-sat, then recalculate — in that order:
   ```
   uv run python manage.py qa_reset_learner_progress \
       --learner demodev_quizqa@email.com --course-slug qa-progression-block-course
   uv run python manage.py recalculate_progress_percentages
   ```
   Course-scoping is what protects the survey course's deliberate 100%. Leaving `--include-topics` off is
   what keeps the pre-completed first topic.
2. As `demodev_quizqa@email.com`, sit the quiz again, answering the **checkbox question wrongly** (3 of 4,
   below the 80% pass mark) and everything else correctly.
   **Expect:** a **failed** banner, the ring showing 75%, and a review of the incorrect answers, because
   `quiz_show_incorrect` is set on this form.
3. Go back to the course table of contents.
   **Expect:** item 3 is **locked**, and the course percentage did **not** rise to count the failed quiz as
   complete.
4. Try to reach item 3 directly: `http://127.0.0.1:$PORT/courses/qa-progression-block-course/3/`.
   **Expect:** blocked — a redirect back to the course, or a 403/404. **Not** the topic content. Gating
   must be enforced by the view, not only hidden in the table of contents.
5. Re-sit and pass.
   **Expect:** item 3 unlocks and the percentage rises.

---

## R4 [C1–C3] Content types: deadlines and reporting

The app label changed, so `django_content_type` holds new rows for `Form`. This is the one place a stale
content type gives a silent *wrong answer* rather than an error.

1. As `demodev@email.com`, go to `/educator/`, open an organisation, a cohort, and a course registration
   whose course contains a **form** — **QA Progress Demo Cohort**, seeded by
   `qa_create_cohort_progress` on `functionality-demo-course-parts`, is the target. That course holds two
   forms: Knowledge Check (a scored quiz) and Course Feedback (a survey).
2. Find the per-item deadline column for the learner list.
   **Expect:** deadline cells render for **form** items as well as topic items — not blank, not an error.
   A blank deadline column against forms specifically, while topics show theirs, means
   `get_for_model(Form)` is resolving to a stale row.
3. Set a deadline on a form item, save, and reload.
   **Expect:** it persists and reappears on **that** form item, not on some other item.
4. Log in as a learner in that cohort and open the course table of contents.
   **Expect:** the deadline shows against the correct form item.
5. **Cohort report generation.** As `demodev@email.com` in the admin, find **Generated reports** and run
   the generate-cohort-report action against a cohort whose course contains a scored quiz. Wait for it to
   reach the ready state and download it.
   **Expect:** it generates without error, and its contents include the quiz questions and the learners'
   answers and scores. This exercises `reports/gather.py` and `reports/indexes.py`, which between them
   import nine moved symbols and which this branch re-keyed from user to learner.

---

## R5 [D1–D7] The Django admin

Twelve admin classes moved app, so their section heading changed. That is expected, not a bug. A
thirteenth model — the join row — is new on this branch.

1. Go to `/admin/`.
   **Expect:** a **Freedom_Ls_Form_Engine** section containing Forms, Form pages, Form contents, Form
   questions, Question options, Form progress records and Question answers.
2. **Expect** the Content engine section to no longer list Forms, Form contents or Question options — but
   to still list Topics, Activities, Courses, Course parts, Content collection items and Files.
3. **Expect** the Learner progress section to no longer list Form progress or Question answers — but to
   list Topic progress, Course progress and **Course form attempts**, the new join model.
4. Open a **Form**.
   **Expect:** its page inline renders; drilling into a Form page shows the content and question inlines;
   a Form question shows the option inline. An inline whose model moved to a different app than its parent
   admin would fail loudly here.
5. Open a **Form progress record**.
   **Expect:** the question-answer inline renders the learner's answers.
6. Open **Course form attempts**.
   **Expect:** the changelist loads and each row names a course progress record, a collection item and a
   form progress record. A `FieldError` or a 500 here is the admin regression.
7. Confirm site scoping still holds: the changelists show only the current site's rows. Only the negative
   direction is testable — `FORCE_SITE_NAME=DemoDev` pins every request to DemoDev regardless of port, so
   a second site's rows must be **absent**, and proving the positive direction is out of scope for this
   run.

---

## R6 [E] The template-render-time edge

`content_tags.get_content_by_path` imports `Form` and runs on **every** request that renders a
`<c-content-link>`. It is the call site most easily forgotten, because everyone remembers the loader.

1. As `demodev@email.com`, open the topic at item 1 of `functionality-demo-show-end-with-quiz`, which
   contains two `<c-content-link>`s.
   **Expect:** the page renders with no 500, and no `TemplateSyntaxError` or `ImportError` in the terminal.
   The "last chapter" link renders as the not-found fallback rather than an anchor — see §0.4; that is a
   content gap, not a regression.
2. Open the `content-widgets-demo-reference` course, the widest exercise of the markdown and cotton
   pipeline.
   **Expect:** every widget renders and no page 500s.
3. On that same topic page, find the **"the Mid course Quiz"** link, which points at
   `../3. quiz/form.md`. This is the fixture for the **Form branch** of `get_content_by_path` — the Topic
   lookup misses, the Form lookup hits.
   **Expect:** it renders as an `<a>` element, **not** a `<span class="text-error">`. That flip from span
   to anchor is the whole check: only the Form branch can produce it.
   Its `href` is empty, because `Form` carries no `preview_url`. Known and already filed — see §0.4; do
   not re-file it.

---

## R7 [F1–F5] Failure and adversarial branches

Deliberately hostile input. None of this should 500 or leak content.

1. **Required-question validation.** Start the `qa-question-types-course` quiz — all four questions are
   required — and submit the page with nothing answered.
   **Expect:** the page is not accepted, and the unanswered required questions are named. The client-side
   `required` gate fires first, so a browser network-tab check will **not** observe the server's 422; that
   branch is unreachable through the UI and is not a failure.
2. Answer only the radio question and submit again.
   **Expect:** validation still blocks, now naming the remaining three.
3. **Repeat submission.** Answer a page, submit, then use the browser **Back** button and submit the same
   page again.
   **Expect:** the answers update rather than duplicating. `QuestionAnswer` is unique per
   `(form_progress, question)`; a duplicate would surface as an `IntegrityError` 500.
4. **Out-of-range and wrong-type indexes.** As a logged-in learner registered for the course:

   | URL | Expect |
   |---|---|
   | `/courses/qa-question-types-course/99/` | 404 |
   | `/courses/qa-question-types-course/0/` | 404 |
   | `/courses/qa-question-types-course/1/fill_form/99` | 404 or a redirect back to the form — **not** a 500 |
   | `/courses/functionality-demo-show-end-with-quiz/1/start_form` (item 1 is a Topic) | 404 — a non-Form item must be rejected |

5. **Unauthenticated and unregistered.** Log out entirely and visit
   `/courses/qa-progression-block-course/2/start_form`.
   **Expect:** a redirect to login. Not the form, not a 500.
   Then log in as a learner **not** registered for that course and visit the same URL.
   **Expect:** the course-access redirect or a 404 — never the form's questions. All authorisation to
   answer a form is *course* authorisation; the split deliberately added no form-level permission concept.
6. **Submit-on-exit** is covered in `3b. progress_gaps_qa/` §G6. Do not repeat it here.

---

## R8 [G] Sweep and log scan

1. With the server still running, click through every course on `/courses/` as `demodev@email.com`,
   opening each course home and at least one item of each.
   **Expect:** no 500s, no missing progress bars, no empty course lists.
2. Scan the whole session's `runserver` output.
   **Expect:** no `ImportError`, no `ModuleNotFoundError`, no `RuntimeError: Model class … doesn't declare
   an explicit app_label`, no `ContentType matching query does not exist`, no `IntegrityError`, and no
   **`RelatedObjectDoesNotExist`**. The last one matters more on this branch than it did before: the report
   layer now reads `form_progress.course_attempt`, which raises if an attempt without a join row reaches
   it.
3. Check the browser console on the form runner and completion pages.
   **Expect:** no new JavaScript errors. Pre-existing console output on this project is report-only CSP
   lines for CDN htmx/Alpine/chart.js, a web-share unrecognised-feature warning, and a YouTube embed
   adapter warning — none of those are findings.

---

## R9 Responsive — owned by this plan for all three runs

`3a` and `3b` are desktop-only, so this is the only mobile and tablet coverage across the whole feature
set. Do not re-run every desktop test; walk this named list at each viewport.

**Mobile, 375×812:**

1. The dashboard course cards, with their progress bars.
2. The course table of contents, including a part-based course (`functionality-demo-course-parts`) and its
   deadline badges.
3. The form runner — all four question types on one page — and the completion page with its score ring.
4. The educator Course Progress matrix, which is the widest table in the product. Check it scrolls inside
   its own container rather than pushing the page sideways.
5. Primary navigation and the hamburger/drawer.

**Tablet, 768×1024:**

6. The same navigation check — does the tablet get the desktop nav or the mobile one, and does it work?
7. The educator Course Progress matrix and its two paginators.
8. The course player and its table-of-contents panel. Run 1 observed that at 768px the player still uses
   the mobile drawer, leaving the right half of the viewport empty. That works correctly and is a layout
   observation, not a defect — confirm it still behaves the same rather than re-filing it.
9. The cohort **Delete** dialog in its blocked state, which gained a new layout on this branch: check the
   blocked message and the Close button render at a reasonable width.

At both viewports, look for elements that overflow, overlap or become unusable, and for touch targets too
small to hit.

---

## What "pass" means

Every numbered **Expect** above holds, and in particular:

- Completing a form still moves the course percentage, exactly once (R2).
- Deadlines resolve against form items on both the educator and learner side, and cohort reports generate
  (R4).
- The admin's Form engine section is complete, its inlines render, and Course form attempts loads (R5).
- Every page rendering a `<c-content-link>` renders (R6).
- Adversarial URLs 404 or redirect, never 500 and never leak a form (R7).
- The `runserver` log holds none of the import, app-label, content-type or related-object errors listed in
  R8.
- Nothing overflows or becomes unusable at 375 or 768 (R9).

For a failure, capture the URL, the account used, a screenshot, and the full traceback from the
`runserver` terminal. Note which of the four silent-failure candidates in the preamble it belongs to —
that is what tells the fixer where to look.
