# QA 3b — the progress-tracking sections run 1 never reached

**Run with:** `/fls-dev:do_qa "spec_dd/2. in progress/better_course_progress_tracking/3b. progress_gaps_qa/frontend_qa_progress_gaps.md"`

This directory has no `todo.md`. Tick and append against the parent one:
`spec_dd/2. in progress/better_course_progress_tracking/todo.md`, section `## 9. QA`.

**Viewports: desktop only.** The mobile and tablet passes for all three QA runs are owned by
`3c. form_engine_regression_qa/`. Do not repeat them here.

---

## Why this plan exists

The first QA run of `better_course_progress_tracking` walked the golden path, the two-organisation core,
the educator matrix, the fan-out and the webhook payloads — and then ran out of budget. Twelve sections
were never executed, including **two of the spec's success criteria**: criterion 6 (shared content across
two courses) and criterion 9 (per-organisation deadlines).

Three bugs were also found and fixed **after** that run finished, so none of the fixes has been seen in a
browser since.

This plan is those gaps and nothing else. Section numbers from the original plan are kept in brackets, so
an existing reference to "§8" or "§12.5" still resolves.

`danger_content_delete` is **not** in this plan — it belongs to `3a. seam_qa/` §S8. Do not run it twice.

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

`SITE_NAME` is a positional argument on some of these commands and an option on others. The shapes
deliberately differ — do not normalise them.

```
uv run python manage.py create_demo_data
uv run python manage.py content_save "demo_content/functionality_demo_end_with_quiz" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_end_with_topic" DemoDev
uv run python manage.py content_save "demo_content/functionality_demo_course_parts" DemoDev
uv run python manage.py qa_create_organisation_scenarios
uv run python manage.py qa_create_course_player_learner
uv run python manage.py qa_create_cohort_progress DemoDev
uv run python manage.py qa_create_report_cohort \
    --cohort-name "QA Report Cohort" \
    --course-slug functionality-demo-course-parts \
    --educator-email org.educator@example.com
uv run python manage.py recalculate_progress_percentages
```

`qa_create_cohort_progress` takes `SITE_NAME` **positionally and required** — a bare run exits 2.
`qa_create_report_cohort` requires `--cohort-name`, and without `--course-slug` it succeeds while
registering the cohort for **nothing**; its Course Progress panel then reads "No course registrations
found for this cohort". That is the command behaving as designed.

A click usage error from any command means this plan has drifted. Fix the plan; do not log it as a product
regression. A **traceback** is a real failure — record it.

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

### 0.2 Credentials

- **Superuser / admin:** `demodev@email.com` / `demodev@email.com`
- **Personas from `qa_create_organisation_scenarios`:** all of them use `demodev@email.com` as the
  password, whatever their email address is. The command prints this on its last line.
- **Learners from `qa_create_cohort_progress`:** `testpass123` — the command does **not** reset the
  password of a persona that survived an earlier run.
- **Learners from `qa_create_report_cohort`:** password equals the email address. Its summary claims the
  same for the `--educator-email` educator, but that only holds for a user it created; a persona it merely
  reused keeps the password above.

A learner who cannot log in is probably missing a verified primary allauth `EmailAddress` row
(`ACCOUNT_EMAIL_VERIFICATION` is mandatory). Delegate that to the `fls-dev:qa-data-helper` agent rather
than patching the database by hand.

### 0.3 Personas

| Persona | Email | What they are |
| --- | --- | --- |
| Cara Learner | `cohort.learner@example.com` | Holds a `Learner` row in **two** organisations: RPAS Training (Year 9 Maths cohort) and Northside (individual) |
| Sol Individual | `solo.learner@example.com` | Individually registered through Northside |
| Nell Unregistered | `no.reg.learner@example.com` | A `Learner` with **no** enrolment at all |
| Rita Removed | `removed.learner@example.com` | A **deactivated** `Learner` who still holds an active course registration |
| Olive Educator | `org.educator@example.com` | Organisation staff on RPAS Training and Northside |

The RPAS **Year 9 Maths** cohort is registered for `functionality-demo-course-parts`. Cara's Northside
registration is for `functionality-demo-show-end-with-topic`, a different course.

### 0.4 Log out between personas

Log out explicitly at `/accounts/logout/` between personas. A stale session is the easiest way to record a
false pass.

---

## G1 [§3] Shared content across two courses — success criterion 6

Never exercised. The same `Topic` placed in two courses must be completed independently in each.

1. In the admin, find a **Topic** that appears in two courses, or place an existing topic into a second
   course via **Content collection items** — `collection` = the second course, `child` = the topic.
2. Log in as a learner registered for **both** courses, registering them through the admin if needed.
3. Open course A and mark that topic complete.
4. Open course B.
   **Expect:** the same topic shows as **not started** in course B's table of contents, and course B's
   percentage is unchanged. Completing it in one course silently ticking it in the other is the defect.
5. Mark it complete in course B too.
   **Expect:** both courses count it, independently, and both percentages move.
6. In the admin, check **Topic progress records**.
   **Expect:** two rows, each naming a different course progress record and a different collection item.

---

## G2 [§5.1–5.4] Nothing in this work retires a record — success criterion 4

Run 1 covered §5.5–5.7 (protected deletes) but never the deactivation half.

1. As superuser, find **Rita Removed** (`removed.learner@example.com`) — a deactivated `Learner` who still
   holds an active course registration.
2. Give her some progress if she has none: register a fresh course to her, complete an item as her, **then**
   deactivate her `Learner` again.
3. **Expect:** after deactivation, her course progress record still exists, with its percentage,
   `completed_time` and resume pointer **unchanged**. Deactivation must destroy nothing.
4. Find a **cohort membership** for a learner who has progress. Delete it in the admin.
   **Expect:** the deletion succeeds, and their course progress record still exists untouched.
5. Deactivate a **course registration** that has granted a record, then reactivate it.
   **Expect:** the record's percentage, timestamps and resume pointer are unchanged throughout, and no
   second record appears.

---

## G3 [§6] The educator matrix keeps showing removed learners

Depends on G2 and was never reached.

1. As **Olive Educator**, open the cohort matrix where a member was deactivated in G2 —
   `/educator/` → RPAS Training → Cohorts → the cohort → **Course Progress**.
2. **Expect:** the deactivated member still appears in the matrix, with their history intact. Deactivation
   suspends future access, not the record of past work.
3. **Expect:** their percentage column and their item cells still agree with each other.

---

## G4 [§7.1] Registration fan-out on a new membership — success criterion 2

Run 1 tested the sibling cases (7.2–7.5) but never a brand-new membership.

1. As superuser, add a **new learner** to the Year 9 Maths cohort — create a `CohortMembership` in the
   admin for an active `Learner`.
2. Immediately open **Course progress records** and filter by that learner.
   **Expect:** a record now exists for each active course registration the cohort holds, granted by the
   **cohort** registration, with the correct **site**.
3. Repeat with a learner whose `Learner` row is **inactive**.
   **Expect:** **no** record is created.

---

## G5 [§8] Deadlines are now per-organisation — success criterion 9

Never exercised. This is the behaviour reversal with nothing to grep for: a person in two organisations
must see each organisation's deadlines separately, not a union of both.

The two commands that matter take the cohort and course explicitly:

```
uv run python manage.py qa_create_soft_deadline DemoDev \
    --cohort-name "Year 9 Maths" --course-slug functionality-demo-course-parts
uv run python manage.py qa_create_deadline_overrides DemoDev \
    --cohort-name "Year 9 Maths" --course-slug functionality-demo-course-parts \
    --learner-email cohort.learner@example.com
```

`--days-from-now` (negative for the past) and `--hard` / `--soft` produce the specific deadlines the steps
below ask for; `--item-slug` narrows a deadline to one topic or form instead of the whole course.

`qa_create_learner_deadlines` seeds its own hard-coded learners and courses and has nothing to do with
these personas — run it only if you want a second, independent fixture to look at.

First, create the overlap: as superuser, add a **Learner course registration** giving Cara's **Northside**
`Learner` row access to `functionality-demo-course-parts`, the course her RPAS cohort already grants. She
now holds a cohort grant and an individual grant on one course, and the cohort grant wins resolution.

1. Give Cara a deadline on that course through **one** organisation only — a `CohortDeadline` on the RPAS
   Year 9 Maths cohort's registration.
2. Log in as Cara and open the course table of contents.
   **Expect:** the deadline shows, attached to the item it was set on.
3. Add a **different** deadline for the same course through the **Northside** individual registration (a
   `LearnerDeadline`), with an obviously different date.
4. Reload Cara's course table of contents.
   **Expect:** she sees the deadline for the organisation she is **studying through** — the cohort one —
   and **not a merged list of both**. Two deadlines side by side for one item is the un-scoped union this
   change removes.
5. Set a **hard** deadline in the past on an item Cara has not completed, through her resolved
   organisation. Open that item's URL directly.
   **Expect:** she is redirected to the course detail page, not shown the item.
6. Set a hard past deadline through the **other** organisation only.
   **Expect:** it does **not** lock her out, because that is not the organisation she is studying through.
7. Deactivate Cara's `Learner` row in Northside, leaving a `LearnerDeadline` on that individual
   registration.
   **Expect:** the individual-registration deadline still resolves. The active-learner filter was
   deliberately dropped from that branch, so a deactivated learner's own deadlines survive.

---

## G6 [§9.7] Submit-on-exit, and the double-submit

Run 1 skipped this, reporting that no form was configured for submit-on-exit. **That was a fixture
mismatch, not a missing fixture.** The submit-on-exit form is item **2** of
`functionality-demo-show-end-with-quiz` — "Mid course Quiz", `submit_on_exit: true`, pass mark 80%. Nothing
in `functionality-demo-course-parts` has it.

1. As a learner registered for `functionality-demo-show-end-with-quiz`, open item 2 and start the quiz.
2. Answer page 1, then use the exit dialog's **"Leave and submit"**.
   **Expect:** it finalises and takes you to the results page. Re-entering does **not** offer to resume.
3. **Expect:** the answers you gave on the page you were standing on are **counted in the score**. A form
   branch bug — since fixed — used to discard them and lock in a 0% failed attempt. Check the results page
   names the questions you answered and scores them.
4. **Expect:** the course percentage recalculated, because this path also ends in `complete()`.
5. Do the "Leave and submit" twice in quick succession — double-click, or resubmit.
   **Expect:** no error, and **no second attempt**. Confirm in the admin that only one `FormProgress`
   exists for that sitting.
6. Compare with item **4**, the End course Quiz, which has no `submit_on_exit`.
   **Expect:** exiting mid-attempt there **saves and allows resume**, and does **not** move the percentage.

---

## G7 [§11.5] Access types degrade rather than crash — success criterion 11

```
uv run python manage.py qa_create_course_access_types
```

1. **Expect:** the command runs to completion. It used to delete registrations, which are now protected —
   an unhandled `ProtectedError` here is the regression.
2. Log in as **Nell Unregistered** and walk the free, application-gated and registration-gated courses it
   seeded.
   **Expect:** each behaves as its badge says. The catalogue lists them at 0% with enrol or
   express-interest affordances rather than "Continue"; detail pages render with an enrol CTA and no 500.
3. Guess a player URL for one of the gated courses.
   **Expect:** turned away by the access gate — a redirect to detail or preview, not a 500 — and **no**
   progress row of any kind created for her. Confirm in the admin.

---

## G8 [§12.1, §12.3–12.7] The report body — HUMAN-RUN in a PDF viewer

Reports render **PDF only**, through `FileResponse`. There is no HTML view, so none of this can be clicked
in a browser. Run 1 verified anchor ids statically and left the rest.

**A human must open the generated PDF and confirm:**

1. [§12.1] As the **superuser**, generate and download the report cohort's report from **Generated
   reports** in the Django admin. That is the only route: reports are admin-only, the educator interface
   has no report entry point and is not meant to have one yet, so do not record its absence as a failure.
   **Expect:** it renders — contents page, summary table, per-learner sections, at-risk list.
2. [§12.3] Click a learner's name in the **Contents** list.
   **Expect:** it jumps to that learner's section. The anchor id was re-keyed in this work, so a link that
   goes nowhere is the regression.
3. [§12.4] Click a name in the **at-risk / attention** list.
   **Expect:** same — it jumps to the right learner.
4. [§12.5] Check the **"No recorded activity"** flag.
   **Expect:** it fires for a learner who has a record but has never opened anything, and does **not** fire
   for a learner with real activity. Under eager creation every registered learner has a record from day
   one, so a report where nobody is ever flagged inactive is the eager-creation regression.
5. [§12.6] Check a learner's **quiz attempts** table.
   **Expect:** attempt numbering starts at 1 for each quiz, and the "first attempt" shown is their first
   attempt **in this cohort's course**, not their first attempt ever.
6. [§12.7] Cross-check each learner's completion counts against what the educator matrix shows for them.
   **Expect:** they agree. Two views of the same person disagreeing means one of them is merging records.

---

## G9 [§14.1, §14.3] Webhook reference and live delivery

Run 1 verified the new `organisation_id` and course-progress-record id against real emitted events, which
is stronger evidence than a static reference page. Two pieces are still unrun.

1. [§14.1] As superuser, look for the integrator-facing **event type reference** in the webhooks section
   of the admin.
   **Expect:** it exists, and the sample payloads for **`course.registered`** and **`course.completed`**
   both list `organisation_id` and the course progress record id alongside their original fields.
   Run 1 could not find such a page at all. If it genuinely does not exist, say so plainly rather than
   recording a failure — that is a documentation gap, not a regression.
2. [§14.3] Configure a webhook endpoint pointing at a request-bin style catcher, or watch the server log
   if delivery attempts are logged.
   **Expect:** registering a learner for a course produces exactly **one** `course.registered` delivery,
   carrying both new fields, with a course progress record id that matches a real row in **Course progress
   records**.
   **Expect:** saving the same registration again produces **no** second delivery, and deactivating then
   reactivating it produces none either. It fires on creation only.

---

## G10 Regression check on run 1's three fixes

All three were fixed after the browser run ended. None has been seen in a browser since.

**B2 — the educator cohort panel used to 500 with a `ProtectedError`.**

1. As **superuser**, open a cohort that **has** granted course progress —
   `/educator/organisations/rpas-training/cohorts/<id>` for Year 9 Maths or QA Pagination Cohort.
   **Expect:** the panel renders normally, with its tabs and Course Progress matrix. A 500 here is the
   regression returning.
2. Open that cohort's **Delete** dialog.
   **Expect:** a plain sentence naming what blocks the delete, and **no** Delete button — only Close.
3. Open a cohort with **no** granted progress.
   **Expect:** the ordinary confirmation dialog, with a working Delete button that works.
4. The fix covers the submit path as well as the render path. If you can reach the delete endpoint for a
   blocked cohort directly, **expect** a 422 with the same readable message, not a 500.

**B1 — `qa_create_report_cohort` used to leave stale percentages.**

5. Straight after §0.1 — with **no** manual `recalculate_progress_percentages` in between — open the
   report cohort's Course Progress matrix as **Olive Educator**.
   **Expect:** every learner's percentage in the left column agrees with the completed cells across their
   row. 0% beside a "Completed" cell is the regression returning.

**B3 — the plan used to name commands that do not exist.**

6. Confirm every command in §0.1 and in G5/G7 ran as written, with no click usage errors. If one did not,
   fix this plan rather than filing a product bug.

---

## G11 Triage of run 1's two open observations

Neither was investigated. Both need a verdict, not a fix.

1. **Course part state.** Find a `CoursePart` whose children are partly complete but with none currently
   in progress.
   **Expect:** it reads "In progress". Run 1 saw "Not started" in that situation, and an "In progress"
   part state does exist and was observed elsewhere. Confidence that this relates to this branch was low —
   check against `main` before calling it a regression.
2. **Empty In-Progress copy.** Log in as a learner who **is** registered for courses but has completed all
   of them, so the In Progress section is empty.
   **Expect:** the copy says her courses are finished and waiting in Learning History — **not** "You
   haven't signed up for any courses yet.", which is untrue for a learner who is still registered. A
   learner with no registrations at all still gets the never-signed-up copy.

---

## What "pass" means

Every numbered **Expect** above holds, and in particular:

- The same topic in two courses is completed independently in each (G1 — success criterion 6).
- A person in two organisations sees one organisation's deadlines, not a union (G5 — success criterion 9).
- Deactivating a learner, a registration or a membership destroys nothing (G2, G3).
- "Leave and submit" scores the answers on the page the learner was standing on, once (G6).
- The educator cohort panel and its delete dialog do not 500 for a viewer who can delete (G10).
- No page 500s, and nothing shows a blank where a date or percentage belongs.

Record any failure with the URL, the persona logged in, what you expected, what you saw, and the relevant
admin row ids.
