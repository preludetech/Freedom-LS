# QA 3a — where the two features meet

**Run with:** `/fls-dev:do_qa "spec_dd/2. in progress/better_course_progress_tracking/3a. seam_qa/frontend_qa_seam.md"`

This directory has no `todo.md`. Tick and append against the parent one:
`spec_dd/2. in progress/better_course_progress_tracking/todo.md`, section `## 9. QA`.

**Viewports: desktop only.** The mobile and tablet passes for all three QA runs are owned by
`3c. form_engine_regression_qa/`. Do not repeat them here.

---

## Why this plan exists

Two features are stacked on this branch and have never been tested together.

The `form_engine` split — already merged into `main` — moved `Form`, `FormProgress` and `QuestionAnswer`
into their own app and replaced a `post_save` recalculation hook with an explicit `form_attempt_completed`
signal. It was QA'd on its own branch and passed clean.

This branch then re-keyed `CourseProgress` onto `Learner` + the granting registration — and reached
straight into the seam the split created:

- `FormProgress.form` went `CASCADE` → `PROTECT`. Deleting a form anyone has ever sat now raises.
- `form_attempt_completed.send(...)` gained an `attempt` kwarg. The receiver contract changed.
- A new join model, `CourseFormAttempt`, binds a `form_engine` attempt to a `learner_progress` record and
  a placement. It did not exist before this branch.
- Cohort reports now reach form attempts through
  `course_attempt__course_progress__cohort_registration`. An attempt with no join row is invisible to a
  report.

The forms QA tested the signal *before* progress was re-keyed. The progress QA tested re-keying but only
ever sat quizzes as learners holding a single grant. **Nothing below has ever been run.**

Every failure here is silent. Nothing 500s; a plausible percentage simply lands on the wrong record. So
most steps ask you to check *whose* number moved, not that a number is there.

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

Every command is copy-pasteable as written. `SITE_NAME` is a positional argument on some of these and an
option on others — the shapes deliberately differ. Do not normalise them.

```
uv run python manage.py create_demo_data
uv run python manage.py content_save "demo_content/functionality_demo_end_with_quiz" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_course_parts" DemoDev
uv run python manage.py qa_create_organisation_scenarios
uv run python manage.py qa_create_form_question_types
uv run python manage.py qa_create_cohort_progress DemoDev
uv run python manage.py qa_create_report_cohort \
    --cohort-name "QA Report Cohort" \
    --course-slug functionality-demo-course-parts \
    --educator-email org.educator@example.com   # currently crashes -- see 0.1b
uv run python manage.py recalculate_progress_percentages
```

`qa_create_cohort_progress` takes `SITE_NAME` **positionally and required** — a bare run exits 2.
`qa_create_report_cohort` requires `--cohort-name`, and without `--course-slug` it silently builds a cohort
registered for nothing.

Any of these exiting 2 with a click usage error means this plan has drifted from the commands. Fix the
plan; do not log it as a product regression. A **traceback** is a real failure — record it.

### 0.1b Known blocker — two seed commands crash

Verified on this branch on 2026-08-25, against a freshly rebuilt database. **Do not spend budget
rediscovering this.**

`qa_create_report_cohort` and `qa_complete_form` both die with:

```
django.db.utils.IntegrityError: null value in column "site_id"
of relation "freedom_ls_form_engine_formprogress" violates not-null constraint
```

One root cause. `CourseFormAttemptFactory` (`freedom_ls/learner_progress/factories.py:70`) takes an
explicit `site=` for the join row but does not pass it down to its `FormProgressFactory` sub-factory.
`SiteAwareFactory.site` is a `LazyFunction` reading the thread-local request context, which is unset
inside a management command, so the `form_engine` row is built with `site=None`. Callers:
`qa_create_report_cohort.py:354` (`_complete_attempt`) and `qa_complete_form.py`.

This is a genuine regression from this branch, not plan drift — `FormProgress` only became a
`form_engine` `SiteAwareModel` with a NOT NULL `site` after the split, and this branch's factory is what
now builds it.

**Until it is fixed**, everything that depends on those two commands is blocked. Mark those steps
`BLOCKED` with this cause rather than `FAIL`, and run the rest of the plan. Once it is fixed, re-run the
seed and pick the blocked steps back up.

### 0.2 Credentials

- **Superuser / admin:** `demodev@email.com` / `demodev@email.com`
- **Personas from `qa_create_organisation_scenarios`:** every one uses `demodev@email.com` as the
  password, whatever their email address is. The command prints this on its last line.
- **Learners from `qa_create_cohort_progress`:** `testpass123` — but the command does **not** reset the
  password of a persona that survived an earlier run.

If a learner cannot log in, they are probably missing a verified primary allauth `EmailAddress` row
(`ACCOUNT_EMAIL_VERIFICATION` is mandatory). Delegate that to the `fls-dev:qa-data-helper` agent; do not
patch the database by hand.

### 0.3 Personas and fixtures

| Persona | Email | What they are |
| --- | --- | --- |
| Cara Learner | `cohort.learner@example.com` | Holds a `Learner` row in **two** organisations: RPAS Training (via the Year 9 Maths cohort) and Northside (individual) |
| Nell Unregistered | `no.reg.learner@example.com` | A `Learner` in RPAS Training with **no** enrolment at all |
| Olive Educator | `org.educator@example.com` | Organisation staff on RPAS Training and Northside |

Courses and forms this plan uses:

| Slug | Contains |
| --- | --- |
| `functionality-demo-course-parts` | **Knowledge Check** — a `QUIZ`, pass mark 80%, shows incorrect answers. Also **Course Feedback**, a `CATEGORY_VALUE_SUM` survey with no verdict. The RPAS Year 9 Maths cohort is registered for this course, so it is Cara's cohort grant. |
| `functionality-demo-show-end-with-quiz` | Item 1 topic, item 2 **Mid course Quiz** (`submit_on_exit`, 80%), item 3 topic, item 4 **End course Quiz** (50%) |
| `qa-question-types-course` | One quiz with all four question types, for `demodev@email.com` |

### 0.4 Log out between personas

Several steps depend on *which* learner is logged in. Log out explicitly at `/accounts/logout/` between
personas. A stale session is the easiest way to record a false pass here.

### 0.5 The two admin changelists you will live in

- **Course progress records** — `/admin/freedom_ls_learner_progress/courseprogress/`
- **Course form attempts** — `/admin/freedom_ls_learner_progress/courseformattempt/` — the new join model.
  This is where you confirm which record an attempt was credited to.

---

## S1. The join row exists, and the recalculation credits it

The receiver ignores `user` and `form` entirely. It reads `attempt`, looks up the one `CourseFormAttempt`
that points at it, and recalculates that record. No join row means no recalculation — silently.

1. Log in as `demodev@email.com` and open `http://127.0.0.1:$PORT/courses/qa-question-types-course/`.
   Note the percentage on the course card and the course home page.
2. Open item 1, start the quiz, answer all four questions and complete it.
   **Expect:** the completion page renders with a score ring.
3. Go back to the course home and the dashboard.
   **Expect:** the percentage has **gone up**. If it has not moved, either the receiver is not connected
   or no `CourseFormAttempt` was written for the attempt.
4. In the admin, open **Course form attempts** and find the row for this sitting.
   **Expect:** exactly **one** row, and it names
   - the `FormProgress` you just completed,
   - the **course progress record** belonging to `demodev@email.com` on `qa-question-types-course`,
   - the **collection item** the form sits at in that course — not the bare form.
5. Open that course progress record.
   **Expect:** its `progress_percentage` matches what the browser showed, and `last_accessed_time` still
   reads the moment you opened the item page in step 2, not the moment you submitted.
   `last_accessed_time` is a read timestamp: only opening a piece of content stamps it, and completing an
   attempt deliberately does not. However stale it looks after a long sitting, that is correct. Do not log
   it as a bug.

---

## S2. Two grants, one course, one quiz — the core of the overlap

This is the case that exists in neither prior QA run: success criterion 5 crossed with the signal
substitution. Cara holds a `Learner` row in two organisations, but the seed registers her for a *different*
course in each. Create the overlap so one course is reachable through both.

### S2.1 Create the second grant

Log in as the superuser and go to `/admin/`.

Cara already reaches `functionality-demo-course-parts` through the **RPAS Training** Year 9 Maths cohort —
a *cohort* grant. Give her a second, *individual* grant on that same course through her other
organisation, so the two grants are of different kinds and there is something to resolve.

1. Add a **Learner course registration**: `learner` = Cara's **Northside** `Learner` row, `collection` =
   `functionality-demo-course-parts`, `is_active` = checked.
   **Expect:** it saves without error.
2. Open **Course progress records** and search `cohort.learner@example.com`.
   **Expect:** **two** records for that course — one granted by the RPAS cohort registration, one by the
   new Northside individual registration. Note both ids. Both should read 0% with no attempts.

Cohort registration beats individual registration when the player resolves which record Cara is working
in, so everything below should land on the **RPAS cohort-granted** record.

### S2.2 Sit the quiz and see which record moved

3. Log out. Log in as **Cara** and open `functionality-demo-course-parts`. Work forward to the
   **Knowledge Check** and complete it, answering well enough to pass (80%).
4. Back in the admin, open **Course form attempts** and filter to Cara.
   **Expect:** exactly **one** new row, and its course progress record is the **cohort-granted** one.
   A row against the Northside record — or two rows — is the failure this whole change exists to prevent.
5. Open **both** of Cara's course progress records for that course.
   **Expect:** the cohort-granted one has moved off 0% and carries a fresh `last_accessed_time`. The
   Northside one is **still 0%**, with no `started_at`, no `completed_time` and no `last_accessed_item`.
6. As Cara, go back to the dashboard.
   **Expect:** the course appears **once**, not twice, showing the percentage of the record she is
   actually working in.

### S2.3 The other record cannot see the attempt

7. Still as Cara, reopen the Knowledge Check's start page.
   **Expect:** the previous-attempts list shows the attempt she just sat, and only attempts from **this**
   record. Nothing from another course's record leaks in.

---

## S3. Attempts are keyed on placement, not on the form

The same form placed twice in one course is two `ContentCollectionItem` rows, and therefore two
independent attempt streams. Course completion is gated on placements, not forms.

1. In the admin, add a second **Content collection item** placing the **Knowledge Check** form into
   `functionality-demo-course-parts` a second time (a different `order`, same `child`).
2. As Cara, open the course table of contents.
   **Expect:** the Knowledge Check appears **twice**, and the placement she already passed reads complete
   while the new one reads not started. One tick marking both is the defect.
3. Work through to the course finish page without sitting the second placement.
   **Expect:** the course is **not** complete, and the page names the outstanding Knowledge Check and
   links to it. Passing one placement must not satisfy the other.
4. Sit and pass the second placement.
   **Expect:** the course completes, and **Course form attempts** now shows two rows against the same
   record — one per placement, each with its own collection item.
5. Remove the extra collection item afterwards so later runs start from the documented fixture.

---

## S4. Resume is scoped to the record, and the credit is frozen at the start

Which record an attempt credits is decided when the attempt is minted, not when it completes. That is the
design; this step confirms it holds and that nothing is destroyed when the resolution changes underneath.

1. Log in as Cara and start the **Mid course Quiz** (item 2 of `functionality-demo-show-end-with-quiz`) —
   register her for that course through the RPAS cohort first if she is not already. Answer page 1, then
   navigate away without finishing.
2. Return to the same item.
   **Expect:** it offers to resume and drops you on the page you left, with page 1's answers still
   selected — not a fresh attempt and not page 1 of a new one.
3. In the admin, **deactivate** the cohort course registration that currently grants her this course, so
   resolution falls through to her individual grant.
4. As Cara, return to the quiz.
   **Expect:** she now resolves to the other record and gets a **fresh start screen**. The half-finished
   attempt is not offered, because it belongs to the other record.
   **Expect:** the original incomplete `FormProgress` and its `CourseFormAttempt` **still exist** in the
   admin, untouched. Re-resolving must never destroy work.
5. Reactivate the cohort registration.
   **Expect:** she is offered the original half-finished attempt again, at the page she left.

---

## S5. No registration means no attempt is minted

`form_start` refuses to create an attempt when the learner has no course progress record. This branch
added that refusal; it is a new failure mode with no prior coverage.

1. Log in as **Nell Unregistered** (`no.reg.learner@example.com`).
2. Guess a form URL directly: `http://127.0.0.1:$PORT/courses/<slug>/<index>/start_form` for a course
   containing a quiz.
   **Expect:** she is turned away — a read-only start screen or a redirect to the course detail page.
   **Not** a 500, and **not** the form's questions.
3. In the admin, confirm **no** `FormProgress`, **no** `CourseFormAttempt` and **no** `CourseProgress` row
   was created for her.
4. Guess a player URL for a later item: `http://127.0.0.1:$PORT/courses/<slug>/5/`.
   **Expect:** redirected to the course detail page, with no progress row of any kind written.

---

## S6. A sitting outside a course must not raise

An attempt with no `CourseFormAttempt` is how `form_engine` represents a form sat outside a course. The
receiver has to return silently rather than raise.

1. In the admin, create a **Form progress record** by hand against any form, for any learner, and mark it
   complete — do **not** create a `CourseFormAttempt` for it.
   **Expect:** it saves. No traceback, no `RelatedObjectDoesNotExist`.
2. Check that learner's course progress records.
   **Expect:** no percentage moved anywhere. A standalone sitting must credit nothing.
3. Watch the `runserver` terminal through this step.
   **Expect:** no `RelatedObjectDoesNotExist`, and no exception swallowed into a 500.

---

## S7. Deleting content that has been answered is refused

`FormProgress.form` is `PROTECT` as of this branch. This is new behaviour, and the admin is where a human
meets it.

1. In the admin, try to **delete a Form** that someone has sat — the Knowledge Check will do.
   **Expect:** a protected-object page naming what still depends on it. **Not** a cascade that quietly
   erases the answers.
2. Try to **delete a Topic** that has progress against it.
   **Expect:** also refused.
3. Try to **delete a `LearnerCourseRegistration`** that has granted a course progress record.
   **Expect:** refused, naming the course progress record. A registration that authorised a learner's work
   cannot be deleted while that work exists.
4. Try to **delete a Cohort** that holds a course registration that granted records.
   **Expect:** refused in the admin with a protected-object message — not a 500.
5. Log in as the **superuser**, open a cohort that **has** granted progress in the educator interface
   (`/educator/organisations/<org-slug>/cohorts/<id>`), and open its **Delete** dialog.
   **Expect:** the panel renders, and the dialog shows a plain sentence naming what blocks the delete —
   e.g. *"This cohort cannot be deleted because it still has 9 course progress records."* — with **no**
   Delete button, only Close. A cascade list here would be a lie: the deletion cannot happen.
6. Open a cohort with **no** granted progress.
   **Expect:** the ordinary "Are you sure you want to delete…" dialog, with a working Delete button. The
   blocked message must not be shown for everything.

---

## S8. `danger_content_delete` clears the whole new chain — HUMAN-RUN

**This step must be run by a human at a terminal.** The previous QA run's command-permission classifier
refused it outright, and it is an explicit pass criterion. It is also the regression that ruins the next
person's database reset.

The command now clears `QuestionAnswer → CourseFormAttempt → FormProgress → TopicProgress →
CourseProgress` explicitly, because the old "CASCADE will handle it" comment stopped being true when
`FormProgress.form` became `PROTECT`.

Run it **last**, after everything else in this plan:

```
uv run python manage.py danger_content_delete
```

Answer yes at the confirmation.

**Expect:** it completes without a `ProtectedError`. A protected-object traceback here is the regression.

Then re-seed from §0.1 before running any other plan.

---

## S9. Cohort reports only see attempts sat under the cohort registration

`reports/indexes.py` reaches form attempts through
`course_attempt__course_progress__cohort_registration`. An attempt sat under an *individual* registration
is therefore invisible to a cohort report — by design. What must not happen is a crash.

Reports are generated and downloaded from the **Django admin only**, as a user with `is_staff`. The
educator interface has no report entry point and is not meant to have one yet, so do not go looking for
one and do not record its absence as a failure. Use the superuser for every report step below.

1. Seed some completions through the cohort path:
   ```
   uv run python manage.py qa_complete_form DemoDev \
       --cohort-name "QA Report Cohort" --form-slug knowledge-check
   ```
   `knowledge-check` is the Knowledge Check quiz in `functionality-demo-course-parts`, which is the course
   §0.1 registers that cohort for. The command resolves the course from the form's placement and skips any
   member not registered for it, so a slug from a different course silently skips everyone.
   Note the command is **cohort-scoped**: positional `SITE_NAME`, then `--cohort-name` and `--form-slug`.
   There is no `--learner` option.
   **Expect:** it exits 0 and reports how many completions it created, and how many learners it skipped
   for not being registered.
2. As the **superuser**, go to **Generated reports** in the admin, run the generate-cohort-report action
   against that cohort, wait for it to reach the ready state, and download it.
   **Expect:** it generates without error, and the quiz answers and scores from step 1 appear.
3. Now have a cohort member sit that same quiz under an **individual** registration instead — give one
   member a `LearnerCourseRegistration` for the course, deactivate their cohort route, and sit the quiz.
4. Regenerate the report from the admin.
   **Expect:** the report **still generates**, and that sitting does **not** appear in the cohort report.
   Absent is correct — the cohort did not authorise that work. A **crash** is not: watch for
   `RelatedObjectDoesNotExist` in the `runserver` terminal, which is what `fold_form_progress_rows` would
   raise if a row without a join row reached it.
5. Cross-check one learner's completion counts in the report against the educator Course Progress matrix
   for the same cohort.
   **Expect:** they agree. Two views of the same person disagreeing means one of them is merging records.

---

## S10. Deadlines and progress are keyed at different grains

Deadlines are stored against the **form's primary key**. Progress and attempts are keyed on the
**collection item**. Two placements of one form therefore share a single deadline but have independent
progress. Separately, this branch narrowed deadline resolution to a single `Learner`, which can make
content *more* locked than before for someone in several organisations.

Record expected-versus-actual carefully here rather than assuming a bug: some of this is the documented
design, and some of it may be a genuine wart worth raising.

1. Set a deadline on the Knowledge Check in `functionality-demo-course-parts` through the RPAS Year 9
   Maths cohort's registration:
   ```
   uv run python manage.py qa_create_soft_deadline DemoDev \
       --cohort-name "Year 9 Maths" --course-slug functionality-demo-course-parts
   ```
   `--days-from-now` (negative for the past), `--hard` / `--soft` and `--item-slug` are how you shape a
   specific deadline.
2. As Cara, open that course's table of contents.
   **Expect:** the deadline shows against the Knowledge Check.
3. If §S3's second placement still exists, check both placements.
   **Expect:** the same deadline shows against **both**, because the deadline names the form, not the
   placement. Note this explicitly in the report — it is the grain mismatch.
4. Set a **hard** deadline in the past on the Knowledge Check through Cara's **resolved** organisation
   (the RPAS cohort), for a placement she has **not** completed. Open that item's URL directly.
   **Expect:** she is redirected to the course detail page, not shown the item.
5. Now the adversarial case. Make Cara resolve to her **Northside** individual grant (deactivate the
   cohort registration as in §S4), leaving the hard past deadline in place on the *other* organisation's
   registration.
   **Expect:** the RPAS deadline does **not** lock her out, because that is not the organisation she is
   studying through.
6. The reverse case, and the one to look at hardest: give Cara a hard past deadline through her
   **resolved** organisation on a form she has **already passed under the other grant**.
   **Expect (per the design):** she is locked out, because completion is checked against the record she is
   currently in and that record has no passing attempt.
   Record what actually happens either way, with both record ids, so this can be judged rather than
   guessed at.

---

## What "pass" means

Every numbered **Expect** above holds, and in particular:

- Completing a form moves the percentage of the **granting registration's** record, and no other (S1, S2).
- Exactly one `CourseFormAttempt` row exists per sitting, naming the right record and the right placement
  (S1, S2, S3).
- A sitting with no join row credits nothing and raises nothing (S6).
- Deleting a form, topic, registration or cohort that has answered work behind it is **refused** — and the
  refusal is readable in both the admin and the educator interface (S7).
- `danger_content_delete` completes without a `ProtectedError` (S8).
- Cohort reports generate whether or not every attempt has a cohort route (S9).
- No page 500s, and the `runserver` log holds no `RelatedObjectDoesNotExist`.

Record any failure with the URL, the persona logged in, what you expected, what you saw, and **the admin
row ids of both course progress records involved** — without those, a wrong-record failure cannot be
reconstructed later.
