# QA 3d — cohort report smoke test

**Run with:**
`/fls-dev:do_qa "spec_dd/2. in progress/better_course_progress_tracking/3d. report_smoke_qa/frontend_qa_report_smoke.md"`

This directory has no `todo.md`. Tick and append against the parent one:
`spec_dd/2. in progress/better_course_progress_tracking/todo.md`, section `## 9. QA`.

**Viewports: desktop only.** The artifact under test is a PDF at a fixed page size, so it has no
responsive behaviour to check, and the browser half of the run is the Django admin. The mobile and
tablet passes for this branch are owned by `3c. form_engine_regression_qa/` §R9.

---

## Why this plan exists

The report branding feature — `spec_dd/3. done/2026-08-28_07:52_report-rendered-with-org-name` — shipped
on its own branch and was QA'd there against eight tests spanning six organisations, missing logo files,
unset platform marks and non-Latin names. That pass is done and is not repeated here.

What has not been checked is whether reports still come out at all **on this branch**. This branch
rewrote the two modules that assemble a report's numbers:

```
freedom_ls/reports/gather.py      128 lines changed
freedom_ls/reports/indexes.py     190 lines changed
freedom_ls/reports/report_data.py   6 lines changed
```

plus three of its partials. Quiz results now reach a report through
`course_attempt__course_progress__cohort_registration`, a chain that did not exist before
`CourseProgress` was re-keyed onto the granting registration. An attempt with no `CourseFormAttempt`
join row is simply invisible to the gather — no error, no warning, an empty cell.

So this is a smoke test with two jobs, and they are different in kind:

1. **Does a report still generate, download and open?** A pass/fail with a traceback attached.
2. **Are the numbers on it real?** A report can reach `Ready` with every quiz cell blank and every
   percentage zero. That is the failure mode the re-keying makes possible, and it looks like a
   working feature until you read the page.

One organisation, one small cohort, one short course. If this plan fails, the branding QA above it
is moot and nothing else in `3d` needs running.

### What this plan deliberately does not cover

The wordmark fallback, the house organisation's suppressed attribution, long and non-Latin names,
both-logo-variants, missing logo files, the unconfigured platform mark, download permissions,
repeat generation. All of those live in
`spec_dd/3. done/2026-08-28_07:52_report-rendered-with-org-name/3. frontend_qa.md`. Run that plan if
this one finds branding damage; do not re-derive its cases here.

---

## 0. Setup

### 0.0 Database state

Reports read `form_engine` tables. If this worktree's database was migrated across the `form_engine`
rebase rather than rebuilt, every course containing a form dies with
`AttributeError: 'NoneType' object has no attribute '_base_manager'` and nothing below can run.

```
uv run python manage.py showmigrations freedom_ls_form_engine
```

All three of `0001_initial`, `0002_formprogress_questionanswer` and `0003_alter_formprogress_form` must
show `[X]`. If any shows `[ ]`, the database must be dropped and rebuilt — see
`3a. seam_qa/frontend_qa_seam.md` §0.0 for the full recipe and why migrating is not an option. The
database was rebuilt on 2026-08-25 and a run starting soon after should find nothing to do here.

### 0.1 Seed the data

Three commands, in this order. All are idempotent.

```
uv run python manage.py create_demo_data
uv run python manage.py qa_create_organisations DemoDev
uv run python manage.py qa_create_report_fixtures \
    --only tiny-cohort-short-course \
    --organisation-slug rpas-training
```

`create_demo_data` builds the DemoDev site and its superuser. Skip it only if `demodev@email.com` can
already log in.

`qa_create_organisations` takes `SITE_NAME` **positionally**, with a default of `DemoDev`. It seeds
four organisations; the one this plan uses is **RPAS Training**, which carries a real logo file
(`freedom_ls/qa_helpers/fixtures/RT-logo.webp`). Its slug derives from its name, so it is
`rpas-training` — not `rpas-training-academy`, which appears in `qa_create_report_cohort`'s docstring
and belongs to a different fixture.

`qa_create_report_fixtures` takes `--site-name` as an **option**, defaulting to `DemoDev`, so it is
omitted above. `--organisation-slug` is what puts the cohort in RPAS Training rather than the site's
default organisation; without it the fixtures land in the house org, which suppresses the "Powered by"
attribution and would make §RS5 unfalsifiable.

`--only tiny-cohort-short-course` is what makes the report short: 3 learners on a 4-item course with
1 quiz. The full matrix builds eleven cohorts up to 40 learners and 12 quizzes and takes minutes.

Any of these exiting 2 with a click usage error means this plan has drifted from the commands. Fix the
plan; that is not a product regression. A **traceback** is a real failure — record it and stop.

If a re-run of `qa_create_report_fixtures` finds stale progress from an earlier run, add `--reset`.
It deletes only the QA-owned fixture cohorts and their learners.

### 0.2 Credentials

- **Superuser / admin:** `demodev@email.com` / `demodev@email.com`

Everything in this plan happens as the admin. No learner login is needed — the report reads progress
that the fixture command wrote directly.

### 0.3 What the fixture contains

| | |
| --- | --- |
| Organisation | **RPAS Training** — has a logo, so §RS4 checks the logo path rather than the wordmark fallback |
| Cohort | **QA Report Tiny Cohort** — 3 learners, 1 of them at-risk flagged |
| Course | `qa-report-short-course` — 4 items, 1 quiz, 4 questions |
| Expected report | a handful of pages: cover, contents, at-a-glance, one landscape summary table, three learner sections |

### 0.4 Generation runs inline

`TASKS` in `config/settings_base.py` uses `ImmediateBackend` in dev, so generation happens during the
POST rather than in a worker. By the time the changelist reloads, the row should already read `Ready` —
you should not have to poll. A row that sits at `Pending` in dev means the task raised before it could
set its own status, which is a real failure, not an environment quirk.

### 0.5 Reading the PDF

The rendered surface is a PDF, so the assertions below are split between the browser (generate,
download) and the shell (read the file). Do not mark a PDF check `SKIP` for want of a viewer — the
tools are installed and every check below has a command.

The generated file also sits on disk at:

```
media/cohort_reports/<report-pk>-cohort-report.pdf
```

Available for reading it: `pdftotext`, `pdfinfo`, `pdfimages` (system), and `pypdf` inside the venv
(`uv run python -c "import pypdf; ..."`). `pdftotext -layout <file> -` prints the text to stdout with
the page geometry roughly preserved, which is what the footer and table checks need.

---

## RS1 — A report generates

In the admin at `/admin/freedom_ls_reports/generatedreport/`:

1. Click **Generate cohort report** (the object-list action).
2. The dropdown is one flat list labelled `<Organisation> — <Cohort>`, ordered by organisation. Pick
   **RPAS Training — QA Report Tiny Cohort** and submit.
3. You land back on the changelist with *"Generating a progress report for QA Report Tiny Cohort."*

Checks:

- The dropdown **contains** the entry. A cohort missing from it means the cohort or its organisation
  did not seed — re-read §0.1 before recording a failure.
- The new row's status is **`Ready`**, not `Failed` and not stuck at `Pending`.
- **The runserver console shows no traceback.** Check it even on a `Ready` row: a swallowed exception
  in the gather is exactly what produces a report that renders but says nothing.
- If the status is `Failed`, the row's error message is the finding — record it verbatim, screenshot
  the changelist, and skip to §RS7, which can still be run against the fixture data directly.

Screenshot the changelist row.

## RS2 — It downloads, named for the organisation

Click the row's **Download** link.

- The download succeeds — no 404, no 500, no empty file.
- The saved file is named **`rpas-training-qa-report-tiny-cohort-progress-report.pdf`**. The
  organisation comes first, then the cohort. Read the name from the Playwright tool response, which
  reports the suggested filename for a download.

If the browser tooling does not surface the filename, get it from the response header instead:

```
uv run python manage.py shell -c "
from django.test import Client
from freedom_ls.accounts.models import User
from freedom_ls.reports.models import GeneratedReport
r = GeneratedReport.objects.order_by('-created_time').first()
c = Client(); c.force_login(User.objects.get(email='demodev@email.com'))
print(c.get(f'/admin/freedom_ls_reports/generatedreport/{r.pk}/download/')['Content-Disposition'])
"
```

A filename with the organisation missing (`-qa-report-tiny-cohort-progress-report.pdf`) is a failure,
not a cosmetic one: it is the same slugify call that the non-Latin case in the branding plan turns on.

## RS3 — The file is a real, short PDF

```
pdfinfo media/cohort_reports/<report-pk>-cohort-report.pdf
```

- `pdfinfo` parses it without error.
- **Pages: fewer than 15.** This fixture is 3 learners and 1 quiz; a report running to dozens of pages
  means it picked up a different cohort.
- The **Title** is `QA Report Tiny Cohort — Cohort progress report`.
- File size is non-trivial — a few hundred KB. A PDF of 2 KB rendered nothing.

## RS4 — The organisation's brand is on the cover

Screenshot or open page 1. This is a visual check; the shell can only confirm the text.

- The **logo sits at the top left**, whole — nothing clipped, squashed or stretched.
- The organisation's **name is set as text beneath the logo**, above the accent rule.
- The accent rule sits under the brand block, aligned **left**.
- The **Organisation** row of the metadata list reads `RPAS Training` in full.
- The cover names the cohort, and **Cohort size** reads `3 learners`.

Confirm the two text halves from the shell as well, because a name rendered as missing-glyph boxes
still passes a glance:

```
pdftotext -f 1 -l 1 media/cohort_reports/<report-pk>-cohort-report.pdf - | head -40
```

`RPAS Training` must appear as real text.

And confirm the logo is genuinely embedded rather than a broken reference:

```
pdfimages -list media/cohort_reports/<report-pk>-cohort-report.pdf | head
```

Page 1 carries at least one image — the organisation's logo. (The platform's own mark on the band is
a second.)

## RS5 — The band and the footer

**On the cover:** the solid coloured band at the foot of the page bleeds off the left, right and
bottom edges, and carries the platform's reversed mark followed by **"Powered by FirstClass"**.

**"Powered by" appears exactly once on the cover** — on the band only, never also in the page's bottom
margin. This was the branding work's most likely defect and the check is cheap:

```
pdftotext -f 1 -l 1 media/cohort_reports/<report-pk>-cohort-report.pdf - | grep -c "Powered by"
```

The answer must be `1`.

**On page 2 and after:** the bottom-left footer is a two-line stack — organisation on the first line,
cohort on the second, and nothing else. Bottom-centre reads `Powered by DemoDev` with the full-colour
mark beside it on one line. Bottom-right reads `Page N of M`. The three do not collide.

Landscape pages (the summary table rotates) carry the whole footer row too.

## RS6 — Document properties

```
pdfinfo media/cohort_reports/<report-pk>-cohort-report.pdf | grep -E "Author|Creator|Title"
```

- **Author** is `RPAS Training` — the organisation, and **one name only**. `RPAS Training, DemoDev`
  means two author meta tags survived.
- **Creator** is the site name.

## RS7 — The numbers are real

This is the section this plan exists for. Everything above can pass on a report with nothing in it.

Read the body:

```
pdftotext -layout media/cohort_reports/<report-pk>-cohort-report.pdf -
```

- **All three learners appear**, each with a section of their own.
- The landscape summary table has a **column for the course's one quiz**, and the cells under it hold
  **scores** — a percentage or a pass/fail verdict — not blanks or dashes for every learner. Every cell
  empty is the join-row failure this branch makes possible: the attempt exists, the
  `CourseFormAttempt` linking it to the learner's `CourseProgress` does not, and the gather cannot see
  it. Record it as a bug with the table screenshotted.
- **Completion percentages are not uniformly 0%.** The fixture spreads learners across a completion
  ladder, so median completion, "not started" and "complete" should all be represented. Three zeroes
  is the same failure wearing different clothes.
- **One learner is flagged at-risk**, and the at-risk section names them and gives a reason.
- The wrong-answer / confusion tables for the quiz hold **option text**, not `Not answered` for
  everything.

Cross-check against the database if any of these look wrong, so a bug report says which side is
empty:

```
uv run python manage.py shell -c "
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_management.models import Cohort
c = Cohort.objects.get(name='QA Report Tiny Cohort')
print('cohort', c.pk, 'org', c.organisation.name)
print('join rows:', CourseFormAttempt.objects.filter(
    course_progress__cohort_registration__cohort=c).count())
"
```

A non-zero join-row count with blank quiz cells in the PDF puts the fault in `gather.py`. A zero count
puts it in the fixture command or in `CourseFormAttempt` creation. The two get different bug reports.

---

## What to report

For each failure: which section, what you expected, what you saw, and the page number. Attach the
runserver traceback if there was one, and screenshot the PDF page for anything on the cover — a
cover defect is far easier to judge from the page than from a description.

A clean run of this plan means the report feature survived the re-keying. It does **not** mean the
branding QA passes; that is the eight-test plan in
`spec_dd/3. done/2026-08-28_07:52_report-rendered-with-org-name/3. frontend_qa.md`, and this plan
touches one of its six organisations.
