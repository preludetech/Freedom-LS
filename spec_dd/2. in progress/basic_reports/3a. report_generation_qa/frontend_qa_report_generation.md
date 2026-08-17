# Frontend QA: Cohort progress PDF report (report generation)

Manual browser verification for the cohort report feature: the admin generate flow, the rendered PDF,
permissions, failure branches and the system checks. Everything in this document is a human/browser
check — none of it is covered by the automated suite.

This is one of **two** QA plans for this spec. The other,
`../3b. quiz_marking_qa/frontend_qa_quiz_marking.md`, covers the multi-select quiz scoring fix and
everything it touches in the student and educator interfaces. The two can be run in either order and
by different people.

## Where this run's output goes

**Everything this plan produces stays inside this directory.** The sibling plan owns its own
directory, and neither run may write into the other's:

```
spec_dd/2. in progress/basic_reports/3a. report_generation_qa/
├── frontend_qa_report_generation.md   ← this file
├── qa-artifacts/                      ← the PDFs this run generates
├── screenshots/                       ← desktop_<test-id>_*.png
└── qa_report.md                       ← the write-up
```

Because the plan file lives here, `do_qa`'s "current directory" *is* this directory: its Step 1
`qa_cleanup.sh`, its `screenshots/` and its `qa_report.md` all land here and touch nothing outside.
Do not clean, write to, or read screenshots from `../3b. quiz_marking_qa/`, and do not resurrect the
top-level `qa_report.md`, `screenshots/` or `qa-artifacts/` in the parent directory — those are the
record of the earlier combined run and are left alone deliberately.

**Mobile and tablet passes do not apply to this plan.** Every surface here is either the Django admin
or a PDF, and `do_qa` skips responsive passes for admin work. Desktop only, at 1920x1080.

## Setup

```bash
PORT=$(.claude/ds/scripts/find_available_port.sh)
npm run tailwind_build          # required — the report reads its colours from the compiled bundle
uv run python manage.py migrate
uv run python manage.py runserver $PORT
```

Base URL: `http://127.0.0.1:$PORT`

**Do not skip `npm run tailwind_build`.** The report extracts its role-colour custom properties from
`static/vendor/tailwind.output.css`. Skipping it is itself a test case (QA 9).

**Where the report's fonts come from.** The report embeds its own faces, listed in
`REPORTS_FONT_FACES` and defaulting to FLS's brand faces bundled under
`freedom_ls/reports/static/reports/fonts/`. A face whose path cannot be resolved is both a
`manage.py check` warning (QA 10.7) and a render failure — the report never quietly falls back to a
substitute. `print.css` names no font family and no colour: both come from settings and from the
compiled theme bundle, so a downstream project rebrands the report without editing a template.

**Branding is optional and must degrade cleanly.** The cover and the page footers use the tenant's own
name (`HEADER_TITLE`, else the `Site` row) and the logo at `HEADER_LOGO_STATIC_PATH`. Whoever runs the
platform underneath it comes from `REPORTS_POWERED_BY_NAME` / `REPORTS_POWERED_BY_LOGO_STATIC_PATH`.
All of those except the site name are optional and default to unset, and FLS records no organisation
apart from the `Site` — so a report must read as finished with none of them configured (QA 2.1).

### Login

Credentials are in `.claude/fls-dev/config.md`:

- Admin: `demodev@email.com` / `demodev@email.com`
- Login page: `http://127.0.0.1:$PORT/accounts/login/`
- Admin: `http://127.0.0.1:$PORT/admin/`

### QA artifacts

**Every PDF this QA run generates is kept.** The point of the artifact set is that a human reviewer
can flip through real reports for cohorts of very different sizes and courses of very different
lengths without re-running anything.

Save them in this plan's own `qa-artifacts/` directory:

```
spec_dd/2. in progress/basic_reports/3a. report_generation_qa/qa-artifacts/
```

Rules:

- **Clear this plan's `qa-artifacts/` at the start of the run.** `qa_cleanup.sh` removes `qa_report.md`
  and `screenshots/` only, so stale PDFs from a previous run survive it and will be mistaken for this
  run's output. Delete the directory by hand before QA 0. Leave the parent directory's
  `../qa-artifacts/` alone — it belongs to the earlier combined run.
- Rename each downloaded PDF to `<fixture-key>.pdf` using the fixture keys in the matrix below —
  the browser will name them all after the cohort slug, which collides across runs and tells the
  reviewer nothing about which scenario produced them.
- Where a check produces a *variant* of a fixture's report (the retry after a forced failure, the
  overflowing table from QA 7), suffix it: `xl-cohort-long-course_column-overflow.pdf`,
  `standard-cohort-medium-course_retry.pdf`.
- Keep the degenerate PDFs too — "cohort has zero students" and "cohort has no course registrations"
  are exactly the outputs most likely to regress unnoticed. The QA 9.2 forced failure produces no
  PDF by design; record it in the manifest as a deliberate absence, with a screenshot of the `failed`
  row standing in for it.
- Screenshots still follow the `do_qa` convention (`screenshots/desktop_<test-id>_*.png`). Artifacts
  are the PDFs; screenshots are the browser evidence. Both are referenced from `qa_report.md`.
- Finish the run by adding an **artifact manifest** table to `qa_report.md`: fixture key, cohort
  size, course length, filename, and one line on what that PDF is there to demonstrate. Any fixture
  in the matrix with no PDF must be listed with the reason it is missing.

### Test data

The whole report fixture matrix is built by one command:

```bash
uv run manage.py qa_create_report_fixtures            # build/refresh everything
uv run manage.py qa_create_report_fixtures --reset    # wipe the fixture cohorts first
```

It is idempotent — re-running changes nothing. Use `--reset` when you want a clean matrix at the
start of a run; it deletes only the fixture cohorts and their `qa-report-*@email.com` students, never
anything created by hand. All fixture logins use the project convention: **password == email**.

Three commands make up the report data set. The first is the one you normally run:

| Need | Command |
|---|---|
| The entire fixture matrix below, plus the two permission users | `uv run manage.py qa_create_report_fixtures` |
| One QA course of a given length and quiz count | `uv run manage.py qa_create_report_course --course-key <key> --num-items <n> --num-quizzes <q>` |
| One cohort of N students with a controlled progress spread | `uv run manage.py qa_create_report_cohort --cohort-name "<name>" --num-students <n> --course-slug <slug> --num-flagged <f>` |

> Do **not** build the report fixtures from `qa_create_cohort_progress`, `qa_create_large_cohort` or
> `qa_add_course_items_for_pagination`. They cannot produce this matrix: the first marks progress
> complete without any answers or scores (so every quiz column, at-risk flag and confusion tally comes
> out empty), the second creates students with no progress at all, and the third appends Topics only
> and can never add a quiz column.

#### Fixture matrix — cohort sizes × course lengths

The report's layout behaviour changes with **both** axes, and they interact: a long course widens the
landscape table (more quiz columns), a large cohort lengthens it (more rows). `qa_create_report_fixtures`
builds every row below in one pass; generate a report for each.

| Fixture key | Cohort name | Cohort size | Course length | Why it exists |
|---|---|---|---|---|
| `empty-cohort` | QA Report Empty Cohort | 0 students | short | Report must say so, not crash (QA 9.5) |
| `no-registrations` | QA Report No Registrations Cohort | 5 students, **no course registrations** | — | Report must state it (QA 9.6) |
| `tiny-cohort-short-course` | QA Report Tiny Cohort | 3 students | short: 4 items, 1 quiz | Smallest real report; everything on few pages |
| `small-cohort-medium-course` | QA Report Small Cohort | 9 students | medium: 12 items, 4 quizzes | **Under 10** — the small-n plain-counts rule (QA 5.6) |
| `standard-cohort-medium-course` | QA Report Standard Cohort | 9 students | medium | The everyday case; the baseline read-through in QA 2 |
| `large-cohort-medium-course` | QA Report Large Cohort | 25 students | medium | Multi-page tables, repeated header rows (QA 3) |
| `xl-cohort-long-course` | QA Report XL Cohort | 40 students, **18 flagged** | long: 30 items, 12 quizzes | Both caps at once — attention list capped at 12, quiz columns past the 10-column budget (QA 4.6, QA 7) |
| `two-course-cohort` | QA Report Two Course Cohort | 9 students | one medium + one **inactive** registration | Both courses sectioned, inactive one marked (QA 2.4) |
| `no-progress-cohort` | QA Report No Progress Cohort | 9 students, zero progress | medium | Every learner shows "No activity recorded" (QA 2.5) |
| `no-pass-mark-cohort` | QA Report No Pass Mark Cohort | 9 students | medium, **first quiz has `quiz_pass_percentage` unset** | Score without verdict must render, not crash or vanish (QA 2.8) |

To rebuild a single row, pass its fixture key: `qa_create_report_fixtures --only xl-cohort-long-course`.

Course lengths are built by `qa_create_report_course`, which lays out topics and quizzes into a
standalone QA course (`qa-report-<key>-course`). The **long** course must carry enough quizzes to push
past the landscape column cap, which is 10 — its 12 quizzes clear it. If a change to the cap ever
leaves 12 too few to force a table split, raise it and rebuild:

```bash
uv run manage.py qa_create_report_fixtures --only xl-cohort-long-course --long-course-quizzes 16
```

The command is additive, so raising the count appends quizzes to the existing course rather than
starting over. Note in `qa_report.md` how many quizzes it took — QA 7 reads that number.

`qa_create_report_fixtures` also seeds the two users the permission checks need:

- `qa-report-educator@email.com` — guardian `view_cohort` on every fixture cohort.
- `qa-report-restricted@email.com` — `is_staff`, every `GeneratedReport` model permission, and
  guardian `view_cohort` on **QA Report Standard Cohort only**. That cohort is "cohort A" in QA 8;
  every other fixture cohort is "cohort B". Model-level `student_management.view_cohort` is
  deliberately *not* granted — holding it globally would hand the user every cohort and defeat the
  check.

Two properties of the generated data that later sections depend on:

- Students are spread across a completion ladder (opened-but-nothing-completed, 20%, 40%, 60%, 80%,
  100%), so median completion, "not started" and "complete" are all non-trivial, and every cohort has
  both flagged and explicitly unflagged learners (QA 4.5).
- Each cohort's highest-progress student has **three** completed attempts at the first quiz, all wrong
  on the same question. That is the fixture behind two checks: the QA 2.10 quiz attempts table, which
  must show all three sittings, and the QA 5.7 cross-check, where their own section counts every
  attempt, the cohort confusion section counts first attempts only, and the two are meant to
  disagree.

### Forms with no pass mark are a supported configuration, not an edge case

`Form.quiz_pass_percentage` is `blank=True, null=True`. **Leaving it unset is a normal, intended
authoring choice** — a questionnaire, a survey, a self-assessment, a practice quiz, or any form
that should report a score without ever pronouncing the learner passed or failed. Authors will do
this routinely.

Everything that touches a form must therefore treat "no pass mark" as an ordinary state that
renders cleanly, never as a misconfiguration to reject. The rule for every surface in this plan:

> **A missing pass mark means "no verdict". It must never mean an error page, a blank panel, or a
> missing row.** Show the score; omit the pass/fail judgement.

Do not treat a crash on a no-pass-mark form as acceptable on the grounds that the author "should
have set one". They should not have to. Any surface that calls `FormProgress.passed()` — which
raises `ValueError` when `quiz_pass_percentage is None` — must guard the call.

The `no-pass-mark-cohort` fixture keeps such a form in the matrix for the whole run, so QA 2.8
exercises it against a real generated report. The student-facing half of the same rule is checked in
the sibling plan (QA 12.2).

### Free-text questions do not appear in scored quizzes

**A quiz that gets scored will not contain `short_text` / `long_text` questions.** Free-text
belongs in questionnaires, surveys and reflective forms — the kinds of form that collect answers
without producing a mark. It is not an authoring pattern to mix free-text into a `strategy: QUIZ`
form that produces a score.

This matters for how fixtures are built and how results are read:

- **Build the scored-quiz fixtures from option-backed questions only** (`multiple_choice` and
  `checkboxes`). A quiz built that way can actually reach 100%, which is what makes pass marks,
  RAG bands and the report's completion figures meaningful.
- A fixture that mixes free-text into a scored quiz will show a **score ceiling below 100%**,
  because free-text questions count toward `max_score` but can never be scored correct. If you see
  a quiz that cannot reach 100%, check the fixture before reporting a scoring bug — it is far more
  likely to be an unrealistic fixture than a defect.
- The report excludes free-text from its confusion analysis by design; QA 2.3 checks the definitions
  block says so.

If you do find free-text inside a `strategy: QUIZ` form in real authored or demo content, treat
that as an **authoring-content finding** to call out in the upgrade notes.

---

## QA 0 — Build the fixture matrix and capture the artifact set

Every later section reads a PDF rather than stopping to generate one, so build the whole set up front.

1. Delete this plan's `qa-artifacts/` directory if it exists.
2. Build every fixture in the matrix above with `uv run manage.py qa_create_report_fixtures --reset`.
   This also seeds the QA 8 educator and restricted staff users. Delegate to
   `fls-dev:qa-data-helper` only if a fixture the command builds turns out to be wrong for a check —
   and fix the command rather than patching the database by hand, so the next run reproduces it.
3. Walk QA 1 in full for `standard-cohort-medium-course` first — that pass is what verifies the
   generate flow itself.
4. Then generate the remaining nine fixtures the same way, through the admin UI rather than the
   shell. This pass *is* the execution of QA 9.5 and QA 9.6; record what the degenerate reports say
   when you get to that section.
5. Download each one and save it to `qa-artifacts/<fixture-key>.pdf`.
6. Record, per fixture: page count, and for the summary table, the number of data columns and
   whether the table split. A fixture that produced a `failed` report instead of a PDF is a QA 9
   finding — note it and keep going.

**Expect:** ten PDFs, spanning 0 to 40 students and 1 to 12+ quizzes, and including one course
whose quiz has no pass mark. If any fixture cannot be built, say so explicitly in the manifest
rather than quietly dropping it.

## QA 1 — Generate a report end to end (success criterion 1)

1. Log in as the admin and go to `/admin/`.
2. Find the **Reports → Generated reports** section in the admin index. Confirm it is there and that
   there is **no** "Generate report" button on the Cohorts changelist — the trigger deliberately lives
   under Reports.
3. Open the Generated reports changelist. Confirm:
   - There is **no "Add generated report"** button (reports are created by the task, not by hand).
   - There is a link/button to the **Generate cohort report** page.
4. Click through to the generate page. Confirm the cohort dropdown lists cohorts.
5. Pick a cohort with real progress data — use `standard-cohort-medium-course` — and submit.
6. **Expect:** redirect back to the changelist, a success message, and a new row.
   - In dev the task backend is `ImmediateBackend`, so the row will most likely already read **ready**
     by the time the page renders. If it reads **pending** or **running**, refresh once.
7. **Expect** the row shows: cohort name, status, requested by (your admin email), requested at,
   finished at, and a **Download** link.
8. Click Download. **Expect** a PDF file download (not an inline render, not a media URL). Check the
   browser's download panel: the filename should be a slugified cohort name, e.g.
   `qa-cohort-progress-report.pdf`, never the raw cohort name with spaces.

## QA 2 — Read the PDF (success criteria 2, 3, 6, 14)

Read `qa-artifacts/standard-cohort-medium-course.pdf` in full, then spot-check the same points in
`tiny-cohort-short-course.pdf` and `xl-cohort-long-course.pdf` — a report that reads correctly at 9
students and 3 quizzes can still fall apart at 3 students or at 40. Check, in order:

The report calls the people in the cohort **learners** throughout. That is deliberate — the model and
field names are still `student_*`, but nothing a reader sees says "student". A page that says
"student" is a miss, not a variant.

1. **Cover page** — the tenant's name top right (`HEADER_TITLE` if set, otherwise the `Site` row's
   name), its logo beside it, the report title, the cohort name, the "Courses covered" card listing
   each course with its item and quiz counts and the inactive registration explicitly marked, a
   generated-at timestamp **including a timezone**, who generated it, the cohort size, the caveat that
   figures and cohort membership are as of generation time, and the brand band across the foot.
   **Expect** the cover carries **no** running header, footer line or page number of its own.
   - Now unset `HEADER_LOGO_STATIC_PATH` and regenerate. **Expect** the cover renders with the name
     alone and **no gap where the logo was** — a fresh FLS install configures no logo, and the page
     must read as finished, not as missing a piece.
   - With `REPORTS_POWERED_BY_NAME` unset (the default), **expect no "Powered by" line anywhere** in
     the document, on the cover or in any page footer. Set it, together with
     `REPORTS_POWERED_BY_LOGO_STATIC_PATH`, regenerate, and **expect** the name and logo in the cover
     band and the name appended to every page footer.
   - A cover naming any organisation FLS does not store — a partner, an accreditation body, a cohort
     code — is a bug. The `Site` is the only organisation in the data model.
2. **Cohort at a glance** — four stat cards (cohort size, median completion, not started, completed
   everything), the "N of M flagged" count, and the learners-needing-attention list. Each flagged
   learner has a page reference. **Click one** — in a PDF viewer it should jump to that learner's
   detail section, and the printed page number should be correct.
3. **Contents and definitions** — one section carrying both. The table of contents shows real page
   numbers (not "0" or blanks), with dot leaders running to them, and two levels: the numbered
   sections, and the courses, learners and quizzes under them. Open the viewer's bookmarks/outline
   panel: it should mirror the contents.
   The definitions block must state, in plain language, all of:
   - what "complete" means and that it is recomputed rather than read from a cached field
   - that quiz score means the **latest** attempt
   - what counts as an attempt (completed only)
   - the first-attempt rule for cohort-wide analysis, and why
   - that multi-select scoring changed, so an old stored score can disagree with the detail below it
   - that a quiz with no pass mark carries a score but no verdict
   - that Activities and free-text questions are excluded, and why
   - that individually-registered courses are not covered
   - the RAG legend including the glyphs
4. **Summary of learner progress** — one table **per course**, landscape. Every course the cohort is
   registered for has a section, including the inactive one, which is marked inactive. Use
   `two-course-cohort.pdf` for this one.
5. **Every learner in the cohort appears** in both the summary table and the per-learner sections,
   including learners with no activity — who must show an explicit **"No activity recorded"** line,
   not be omitted. `no-progress-cohort.pdf` is the fixture where *every* learner takes that branch.
6. **Orientation:** the summary tables are landscape and everything else is portrait.
7. **Page numbers** appear on every page but the cover.
8. **Quizzes with no pass mark** — use `no-pass-mark-cohort.pdf`, whose first quiz has
   `quiz_pass_percentage` unset (a normal authoring choice; see "Forms with no pass mark" above).
   **Expect** its column shows the score with **no** pass/fail verdict and no RAG pass/fail glyph,
   and that the report still generates rather than landing in `failed`. A no-pass-mark quiz that
   silently drops out of the summary table, or that renders as a failure, is a bug — the learner
   did take it, and the score is real. Confirm the definitions block explains that a quiz with no
   pass mark carries a score but no verdict.
9. **Page furniture.** On every page but the cover: the current section's title top left, the page
   number bottom right, and bottom left the line `{site} · Cohort progress report · {cohort}` —
   with `Powered by {name}` appended when that setting is configured. **Expect** the section title in
   the header to change as you cross from one section into the next, and to stay correct on a
   section's second and later pages.
10. **Per-learner quiz attempts.** In a learner's own section, find the "Quiz attempts" table.
    **Expect** one row per **completed** sitting, oldest first, each with its attempt number, its date
    and its score — so a learner who failed twice and passed on the third attempt reads as exactly
    that. Cross-check the last row against the same quiz's cell in the summary table: the summary
    shows the **latest** attempt, so the two must agree. An abandoned, uncompleted sitting must not
    appear as a row. Use `standard-cohort-medium-course.pdf`, whose highest-progress learner has three
    attempts at the first quiz.
11. **A legacy checkbox score shows through unchanged.** The multi-select scoring fix does not rescore
    stored attempts, so a report can legitimately print a score that disagrees with the wrong-answer
    detail underneath it — and the methodology block has to say so. Ask `fls-dev:qa-data-helper` for a
    pre-fix-shaped attempt on a fixture cohort: a completed `checkboxes` question with **every** option
    ticked and a stored score of full marks, as the old scoring would have recorded it. Generate a
    report for that cohort and **expect** the summary table to show the **stored** score, the learner's
    incorrect-answer detail to mark the same question wrong, and the definitions block to explain the
    discrepancy rather than leaving the reader to spot a contradiction. Keep it as
    `qa-artifacts/legacy-score-discrepancy.pdf` — it is the one artifact showing the two numbers side
    by side. The student-facing half of this rule (the results page must not rescore either) is
    QA 12.6 in the sibling plan.

## QA 3 — Page-break and running-header behaviour (success criterion 6)

Use `large-cohort-medium-course.pdf` (25 students) so tables and sections span multiple pages, then
repeat steps 1–3 on `xl-cohort-long-course.pdf` (40 students, 12+ quizzes) where the table is both
long and wide. Compare against `tiny-cohort-short-course.pdf`: a three-student table that still
splits, or that carries a running header on a one-page section, is its own failure.

1. Find a summary table that spans more than one page. **Expect** the header row repeated at the top
   of each page it continues onto. A table that runs off the bottom with no repeated header, or that
   is clipped instead of continuing, is a failure.
2. Confirm no table row is split across a page boundary.
3. Scroll through the per-learner sections. **Expect** each learner starts on a fresh page, and the
   running header at the top right of each page carries **that** learner's name — including on the
   second and third pages of a long learner's section. A header still showing the *previous*
   learner's name is the failure mode to watch for. The section title stays top left throughout, and
   **no** learner's name leaks onto a landscape summary page or into the confusions section.
4. Check the learners are ordered alphabetically by surname.
5. Check quiz columns are ordered by their position in the course, not alphabetically, and that the
   abbreviated column headers have a legend under the table title. **Expect one column per quiz**,
   carrying the glyph, the latest score and the attempt count together — deliberately not a separate
   score column and attempts column, because doubling the quiz columns would halve how many fit on a
   landscape page.

## QA 4 — At-risk flags are consistent (success criterion 4)

1. On the at-a-glance page, note a flagged learner and the exact wording of every reason line.
2. Turn to that learner's own detail section.
3. **Expect** the same flags with **identical label and reason text**, in the same order. Any wording
   difference, or a flag present in one place and not the other, is a failure. The badge is coloured
   by the rule's severity, so a flag may look heavier in one place than another only if the *text*
   still matches exactly.
4. **Expect** every flag badge to carry the `▲` glyph as well as its colour, and the learner's own
   section to show a coloured rule down the side of the flags panel. Two severities distinguishable
   only by shade would fail the greyscale check in QA 6.
5. Find a learner with no flags. **Expect** an explicit **"No flags"** line in their section — not an
   empty gap.
6. Using `xl-cohort-long-course.pdf` (>12 flagged learners): **expect** the at-a-glance list capped at
   12 with a disclosure like "Showing 12 of 18 learners flagged", and **every** flagged learner —
   including the six not listed on the front page — still carrying their flags in their own detail
   section.

## QA 5 — Cohort quiz confusions (spec §7.3)

1. Find the "Quiz confusions across the cohort" section.
2. **Expect** each question shows the incorrect answers chosen and how often, the correct answer
   alongside them, and worst-first ranking. Wrong answers and the correct one are shown as tinted
   chips, and the proportion who got it wrong as a figure with a bar beside it.
3. **Expect** no option anywhere in the report — here or in a learner's own incorrect-answer table —
   to be prefixed with a letter or a position marker. FLS does not letter a question's options, so
   `B — overcast skies` would be an ordering the learner never saw. Only the option's own text.
4. **Expect** a cap disclosure such as "Showing 10 of 23 questions with at least one incorrect
   answer" wherever the cap bites.
5. **Expect** the interpretive caution that a high error rate can mean a hard-but-fair question. It
   appears once, under the section heading.
6. Using `small-cohort-medium-course.pdf` (9 learners): **expect** plain counts ("7 of 9 learners")
   and **no percentages** anywhere in this section — and **no proportion bar either**, since a bar
   puts back exactly the precision the plain count exists to avoid claiming. A percentage or a bar
   appearing for a small-n question is a failure. Then confirm the opposite in
   `large-cohort-medium-course.pdf` — at 25 learners percentages and bars **should** appear. The rule
   flipping at the boundary is what is under test, so `tiny-cohort-short-course.pdf` (3 learners)
   should read as plain counts too.
7. Cross-check one question against a learner's detail section: a learner's repeated wrong answers
   should read as "×3" in their own section (counted per attempt), while the cohort section counts
   first attempts only. These two numbers disagreeing is **correct** — confirm the definitions block
   explains it.
   The fixture is already there: in every cohort the highest-progress student has three completed
   attempts at the first quiz, all wrong on the same question. Find them by sorting the summary table
   by completion, or in the shell with
   `FormProgress.objects.filter(completed_time__isnull=False).values("user__email", "form__slug").annotate(n=Count("id")).filter(n__gte=3)`.

## QA 6 — Greyscale legibility (success criterion 7)

**No physical printer.** Rasterise the PDF to greyscale and read that instead — it is reproducible,
it needs no hardware, and it leaves an artifact the next run can compare against. Use
`xl-cohort-long-course.pdf`: it has the widest spread of statuses across the most cells.

```bash
pdftoppm -gray -r 150 -png qa-artifacts/xl-cohort-long-course.pdf screenshots/desktop_6_greyscale
```

1. Open the greyscale pages and read them at 100%.
2. Walk every status cell: completion bars, quiz pass/fail, RAG-coloured cells.
3. **Expect** every status to remain unambiguous because each cell carries a glyph
   (`✓` complete, `✗` failing/not started, `▲` warning, `●` in progress, `○` started-no-verdict,
   `—` not applicable) **as well as** its number. Two statuses that are distinguishable only by shade
   are a failure.
4. Confirm no glyph renders as a hollow `.notdef` box or a missing-character rectangle — that means
   no embedded face carries the code point. The report now embeds several families, so check the
   glyphs wherever they appear: the definitions legend, the summary cells, the completion bars, the
   flag badges and the quiz attempts table.
5. Confirm no glyph renders as a colour emoji.
6. Open the PDF's font properties (in most viewers, Document Properties → Fonts). **Expect** every
   listed face to be embedded and to be one of the configured families — a face named as a system
   font, or a synthesised "bold"/"oblique" of a family whose real weight is not embedded, means a
   weight is missing from `REPORTS_FONT_FACES`.

## QA 7 — Landscape column budget (spec §7.1)

**The budget is signed off at 10.** `REPORTS_MAX_QUIZ_COLUMNS = 10` was measured on rendered A4
landscape pages, in the report's own body face and with the summary table's separate "When" column:
at 10 quiz columns (14 in all) every "Last item completed" title still clears "When", and at 11 the
title is squeezed below the width one word needs and runs into it. This section is a regression check
on that number, not an open sign-off — re-measure only when the page size, the fonts or the fixed
columns change.

1. Use `xl-cohort-long-course.pdf` — the long course carries 12 quizzes, past the cap, so it is built
   to force the split.
2. View one landscape summary page at 100% / actual size.
3. **Expect:** text is legible at normal reading distance, nothing is clipped at the right margin, and
   the quizzes past the cap move into a second `(continued)` table rather than the type shrinking.
4. Confirm the boundary still holds: the first table carries **10** quiz columns, and the item titles
   under "Last item completed" keep a clear gap before "When". A title touching or overlapping the
   date means the budget has drifted.
5. If it has drifted, walk the matrix to re-measure — the short course (1 quiz), the medium course
   (4), then the long one (12) — and record the largest column count that renders cleanly and the
   smallest that does not. To push past 12, rebuild with more quizzes and regenerate:
   `uv run manage.py qa_create_report_fixtures --only xl-cohort-long-course --long-course-quizzes 16`
   (additive — it appends quizzes rather than starting the course over). Adjust
   `REPORTS_MAX_QUIZ_COLUMNS` (`freedom_ls/reports/config.py`) to the measured number and keep the PDF
   that demonstrates the overflow as `qa-artifacts/xl-cohort-long-course_column-overflow.pdf` — it is
   the evidence behind the change.

## QA 8 — Permissions and access control (success criteria 11, and spec §12.1)

Failure branches — these matter more than the golden path.

The restricted staff user is `qa-report-restricted@email.com` (password == email), seeded by
`qa_create_report_fixtures`. **Cohort A** is *QA Report Standard Cohort* — the only one it holds
`view_cohort` on. Any other fixture cohort is **cohort B**.

1. **Anonymous:** log out. Paste the download URL directly
   (`/admin/freedom_ls_reports/generatedreport/<uuid>/download/`). **Expect** a redirect to the admin
   login, never the PDF.
2. **Staff without `view_cohort` on that cohort:** log in as the restricted staff user and open the
   same download URL for a report on cohort B. **Expect 403**, not the PDF and not a 500.
3. **Same user, the generate page:** confirm cohort B does **not** appear in the dropdown at all.
4. **Forced POST:** submit the generate form with cohort B's id (edit the option value in devtools, or
   POST directly). **Expect** the request rejected (403/404) and **no** new report row created for
   cohort B. Verify in the changelist as the admin.
5. **No media URL:** view the changelist page source and confirm no link contains `/media/`. The
   download must always route through the admin view.
6. **Caching headers:** open devtools → Network, click Download, inspect the response headers.
   **Expect** `Cache-Control: private, no-store, must-revalidate` and a
   `Content-Disposition: attachment` header.
7. **Direct media guess:** try `http://127.0.0.1:$PORT/media/reports/<report-uuid>/cohort-report.pdf`.
   In dev with local file storage this may serve the file — that is why the storage-alias system check
   exists. Note the result; it is expected to be blocked in a correctly configured deployment, and the
   `manage.py check` warning in QA 10 is the control.

## QA 9 — Failure branches (success criteria 12, 13)

1. **Double-click / concurrent generate:** submit the generate form twice in quick succession for the
   same cohort (or open two tabs and submit both). **Expect** exactly **one** report row for that
   cohort, and an informational message like "A report for this cohort is already being generated" —
   never a 500 and never two rows.
   - In dev with `ImmediateBackend` the first request completes synchronously, so the second will
     usually succeed as a *new* report. To exercise the real race, temporarily set a report's status
     back to `pending` in the shell and then submit the generate form for that cohort.
2. **Failed render:** force a failure — the simplest is to move/rename `static/vendor/tailwind.output.css`
   (or delete the bundled font) and restart the server, then generate a report.
   **Expect:** the row shows status **failed** with a **readable error message** in the changelist or
   detail view (e.g. pointing at the missing Tailwind bundle), `finished_at` set, and **no** stuck
   `running` row.
3. **Retry after failure:** restore the file, then generate for the **same cohort** again. **Expect**
   it succeeds immediately — a failed report must not block the cohort. Save the result as
   `qa-artifacts/<fixture-key>_retry.pdf` and confirm it is complete, not a truncated re-render.
4. **Pending report has no download link:** confirm the Download column is empty for `pending`,
   `running` and `failed` rows, and that hitting the download URL for such a report 404s.
5. **Cohort with zero students:** generate a report for the `empty-cohort` fixture. **Expect** a valid
   PDF that says so explicitly rather than a crash or a blank page. Keep it as
   `qa-artifacts/empty-cohort.pdf`.
6. **Cohort with no course registrations:** same — a report that states it, not an error. Keep it as
   `qa-artifacts/no-registrations.pdf`.

## QA 10 — Deletion and system checks (spec §12.2, §12.4)

1. In a shell, note the on-disk path of a ready report's file
   (`GeneratedReport.objects.first().file.path`), and confirm the file exists.
2. Delete that report from the admin changelist (single delete). **Expect** the row gone **and the
   file gone from disk**.
3. Repeat using the admin's **bulk delete action** on two reports. **Expect** both files gone.
4. Generate a report, then **delete its Cohort** from the admin. **Expect** the cohort's reports gone
   *and* their PDF files gone from disk — an orphaned PDF with student names in it is the failure.
5. Run `uv run manage.py check`. **Expect** a warning that the reports storage alias is not configured
   and that reports will fall back to the default storage.
6. Move `static/vendor/tailwind.output.css` aside and run `uv run manage.py check` again. **Expect** a
   warning naming `npm run tailwind_build`. Restore the file.
7. Rename one file under `freedom_ls/reports/static/reports/fonts/` and run `uv run manage.py check`
   again. **Expect** a `freedom_ls_reports.W004` warning naming that path, and a report generated
   while it is renamed to land in `failed` rather than rendering in a substituted face. Restore the
   file and confirm both the warning and the failure go away.
