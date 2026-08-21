---
requires_migrations: true
requires_template_review: true
changed_template_paths:
  - freedom_ls/student_interface/templates/student_interface/course_form_complete.html
  - freedom_ls/student_interface/templates/student_interface/partials/exam_score_ring.html
  - freedom_ls/student_interface/templates/student_interface/course_finish.html
  - freedom_ls/student_interface/templates/student_interface/course_form_page.html
  - freedom_ls/webhooks/templates/admin/webhooks/send_test_form.html
  - freedom_ls/webhooks/templates/admin/webhooks/send_test_result.html
requires_settings_change: true
changed_settings:
  - INSTALLED_APPS          # add "freedom_ls.reports" if you maintain your own list
  - STORAGES                # declare a private "reports" alias, or reports land in MEDIA_ROOT
  - REPORTS_STORAGE_ALIAS   # new, default "reports"
  - REPORTS_MAX_STUDENTS    # new, default 500
  - REPORTS_MAX_QUIZ_COLUMNS # new, default 10
  - REPORTS_FONT_FACES      # new, defaults to FLS's bundled brand faces
  - REPORTS_FONT_DISPLAY    # new
  - REPORTS_FONT_BODY       # new
  - REPORTS_FONT_MONO       # new
requires_package_upgrade: true
changed_packages:
  - weasyprint>=69.0        # new base dependency — needs Pango/cairo/gdk-pixbuf/HarfBuzz
  - pypdf>=6.16.1           # new dev dependency — PDF assertions in the test suite only
requires_npm_install: false
changed_npm_packages: []
requires_tailwind_rebuild: true
---

# Upgrade notes: basic_reports

This release adds **`freedom_ls.reports`** — a staff-only, admin-driven cohort progress report
rendered to PDF by WeasyPrint and generated in a background task.

It also lands a set of changes to quiz marking and course completion that reach well beyond the
report. **Those are the parts that can change what your learners see, and they apply whether or not
you ever generate a report.** Read the breaking changes before upgrading a live installation.

## Breaking changes

### 1. Multi-select quiz questions are marked by exact match

Previously a checkbox question counted as correct if **any** selected option was marked correct.
It now requires **every** option marked `correct=True` to be selected and **no** option marked
`correct=False` — an option left unmarked (`correct=None`) is neither required nor forbidden.

- Existing checkbox questions become **harder**. A learner who ticked one right answer out of three
  and passed under the old rule fails the same question today.
- **Historical scores are not rescored.** `FormProgress.scores` is left exactly as it was recorded,
  so past attempts and past pass/fail outcomes do not move. Future attempts, and any re-sit, are
  marked under the new rule.
- Where a stored score disagrees with what the attempt would earn today, the results page now shows
  a "This quiz has changed since you sat it" note rather than silently presenting a stale number.
- Single-select (radio) questions are unaffected — one required option, one selection.

If your content relies on partial credit for checkbox questions, review that content before
upgrading. There is no partial-credit mode.

### 2. A failed quiz no longer counts as a completed item

Course progress and course completion now ask whether the learner **passed**, not merely whether
they submitted:

- `CourseProgress.progress_percentage` no longer counts a form whose latest completed attempt failed
  its own pass mark. **Existing `CourseProgress` rows are stale after this upgrade** — see manual
  steps.
- `/courses/<slug>/finish` no longer stamps `completed_time` while any quiz in the course is
  unpassed. The page still renders, but as "Not finished yet", naming the outstanding quizzes and
  linking to the re-sit. Anything downstream that keys off `CourseProgress.completed_time`
  (certificates, webhooks, reporting) will therefore fire later, or not at all, for a learner who
  failed a quiz.
- A quiz with **no** `quiz_pass_percentage` has no bar to clear, so completing it still completes the
  item, exactly as before. Surveys are unaffected.

### 3. `is_failed_quiz` is gone from the quiz results context

The results templates now receive **`quiz_verdict`** — the string `"passed"`, the string `"failed"`,
or empty for a quiz with no pass mark (which gets a score and no verdict at all). The old boolean
could not express that third state and reported "failed" for it.

If you override `course_form_complete.html` or `partials/exam_score_ring.html`, a template still
testing `{% if is_failed_quiz %}` does not error — it silently renders the *pass* branch for every
attempt, including failures. Sweep for that string.

Two other new context variables those templates render:
`stored_score_outdated` (bool, drives the note in §1) and, on `course_finish.html`,
`unpassed_forms` (the list behind the "Not finished yet" state in §2).

### 4. Non-model helpers moved out of `student_progress.models`

`freedom_ls.student_progress.models` was carrying query, scoring, submission-parsing and
signal-handling code. It now holds models only. Direct imports of the moved names break at import
time:

| Was | Now |
| --- | --- |
| `student_progress.models.update_course_progress_on_completion` | `student_progress.signals.update_course_progress_on_completion` |

The completion recalculation is now a `post_save` receiver connected in
`StudentProgressConfig.ready()` rather than a `CourseItemProgress.save()` override. **The receiver
names its senders**, so a downstream `CourseItemProgress` subclass no longer inherits the behaviour
by subclassing — it needs its own `@receiver` line. As before, neither path fires on
`queryset.update()`.

New modules alongside it, if you want to reuse them rather than re-derive the rules:
`student_progress.scoring` (`is_quiz_answer_correct`, `evaluate_quiz_answers`),
`student_progress.queries` (`attempt_completes_form`, `completed_form_ids_by_user`),
`student_progress.submissions`.

### 5. The quiz player now gates and validates where it did not

- `form_start`, `form_fill_page` and `form_submit_and_exit` now run the course-access and
  sequential-unlock checks **before** they write anything. A learner who previously reached a locked
  quiz by typing its URL is redirected instead. This closes a hole; it will look like a sudden
  redirect if any of your links point directly at a locked item.
- Required questions are enforced server-side. Submitting a page with a required question blank
  re-renders it with `required_answers_error` in the context instead of saving. If you override
  `course_form_page.html`, render that variable or the refusal is invisible to the learner.
- The "Next" / "Try Again" buttons on a quiz start page are now decided by the quiz's own
  `quiz_pass_percentage` rather than a hardcoded 80%, and a `CoursePart` whose only outstanding work
  is a re-sit reads "Needs retry" instead of "Locked".

### 6. `pytest` marker taxonomy gained a fifth marker

`weasyprint` marks the tests that actually call `write_pdf()`. If you run FLS's suite, register it in
your own `[tool.pytest.ini_options] markers` — `--strict-markers` makes an unregistered marker a hard
error — and exclude it if your environment has no Pango/cairo:

```
-m "not playwright and not fls_internal and not ci_only and not weasyprint"
```

FLS's own default `addopts` now excludes it locally; CI overrides `addopts` on the command line and
still runs it.

## Who can generate and download a report

Report access is **not** a new permission model — it follows the same two cohort-authorisation paths
the rest of FLS already uses, and a user needs only one of them:

- an **`organisation_staff`** role on the organisation that owns the cohort, or
- a per-cohort **`view_cohort`** grant (guardian object permission) on that cohort.

Django staff status alone is not enough. `admin_site.admin_view()` only guarantees `is_staff`; the
object-level check is separate and runs on every surface:

- the **changelist** is filtered to reports whose cohort the user may see,
- the **generate** page's cohort dropdown lists only those cohorts, and re-checks the chosen one on
  POST,
- the **download** view raises `PermissionDenied` for a cohort the user may not see, and streams the
  PDF as a private `no-store` attachment rather than exposing a storage URL.

These resolve through two new helpers in `freedom_ls.student_management.queries` —
`all_cohorts_visible_to(user)` and `can_view_cohort(user, cohort)`. They are the
organisation-unscoped siblings of the existing `cohorts_visible_to`, for surfaces like the Django
admin that are site-wide and have no organisation in scope to pass. If you have your own staff-facing
surface that needs the same answer, call these rather than re-deriving the two branches.

## At-risk rules are a fixed list, not a settings hook

The report flags a learner as at-risk using the rules in `freedom_ls/reports/at_risk.py`:
no recorded activity, failed most recent quiz attempt, and no activity in over 7 days. They are a
plain module-level list, `AT_RISK_RULES`, with **no setting, no registry and no entry point** — this
was a deliberate simplification, not an oversight.

A project that needs a different rule set, a different inactivity threshold, or a per-organisation
rule has to fork that module for now. Rule selection moves into the database in the planned
`report-upgrades` work; if you are tempted to build a configuration layer on top of this list, that
is the thing to wait for rather than to invent twice.

## Manual steps

1. **Install the system libraries WeasyPrint needs** — Pango, cairo, gdk-pixbuf and HarfBuzz — on
   every host and in every image that runs the app *or the task worker*. On Debian/Ubuntu that is
   roughly `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b`. WeasyPrint
   is imported lazily inside the render function precisely so a host without them fails at
   generation time with a clear message rather than refusing to start — but the report will not
   generate until they are present.

2. **Install the Python dependencies.** `weasyprint>=69.0` is a new **base** dependency;
   `pypdf>=6.16.1` is new in the `dev` group. `uv sync` picks both up.

3. **Add the app to `INSTALLED_APPS`** if you maintain your own list rather than inheriting FLS's
   `config/settings_base.py`:

   ```python
   INSTALLED_APPS = [..., "freedom_ls.reports", ...]
   ```

4. **Run `uv run manage.py migrate`.** One migration, `freedom_ls_reports.0001_initial`: the
   `GeneratedReport` table plus a partial unique index that is what actually prevents two concurrent
   generate requests producing two reports for one cohort. No existing table is touched.

5. **Recalculate course progress.** Because a failed quiz no longer counts as complete (§2), every
   `CourseProgress.progress_percentage` written before this upgrade may be too high:

   ```
   uv run manage.py recalculate_progress_percentages
   ```

   The command now walks learners in batches of 500 rather than loading every completed item at
   once, so it is safe to run against a large installation. It does **not** touch `completed_time` —
   a learner already marked complete stays complete; only new completions are held back.

6. **Declare a private storage alias for reports.** A generated report contains named learners and
   their scores. `REPORTS_STORAGE_ALIAS` defaults to `"reports"`, and if no such key exists in
   `settings.STORAGES` the file falls back to your default storage — which may be a publicly served
   `MEDIA_ROOT`. `manage.py check` raises `freedom_ls_reports.W001` when that is the case. Add a
   private, non-public-read alias:

   ```python
   STORAGES = {
       ...,
       "reports": {"BACKEND": "...", "OPTIONS": {...}},  # private; no public read
   }
   ```

   Downloads are always streamed through the admin view with a per-cohort permission check and
   `Cache-Control: no-store`, never linked directly.

7. **Rebuild Tailwind** (`npm run tailwind_build`, or your project's equivalent). Two reasons, and
   the second is not optional:
   - The reworked quiz results, course-finish and quiz-page markup introduce utility classes your
     bundle has not seen.
   - **The report reads its colours out of the compiled bundle.** `render.py` extracts the role-token
     block from `vendor/tailwind.output.css`; if the finders cannot resolve it, `manage.py check`
     raises `freedom_ls_reports.W002` and report rendering fails outright rather than producing a
     colourless PDF.

8. **Run `collectstatic`.** The app ships ~3.5 MB of font files under
   `freedom_ls/reports/static/reports/fonts/` (Inter, Source Sans 3, Source Code Pro and DejaVu Sans,
   all OFL, shipped unmodified with their licences). WeasyPrint resolves them through the staticfiles
   finders; `freedom_ls_reports.W004` warns for any face it cannot find.

9. **Make sure a task worker is running.** Report generation is a `django-tasks` task. With the
   production `DatabaseBackend`, a report enqueued with no `manage.py db_worker` running sits at
   status `pending` forever. Dev and tests are unaffected — the `ImmediateBackend` runs it inline.

10. **Review and re-apply your customisations** to the changed templates listed in the frontmatter.
    The two that can go wrong silently are
    `student_interface/course_form_complete.html` and
    `student_interface/partials/exam_score_ring.html` — see breaking change §3. The webhooks admin
    templates changed only in how the send-test form and result pages are laid out (a shared
    `_detail_row.html` partial); nothing about the webhook contract moved.

11. **Optional: tune the report's limits and typography.** All defaults work out of the box.
    `REPORTS_MAX_STUDENTS` (500) and `REPORTS_MAX_QUIZ_COLUMNS` (10) are resource and layout budgets,
    not product rules — raise or lower them to match your workers and page size. To put the report in
    your own brand faces, override `REPORTS_FONT_FACES` together with `REPORTS_FONT_DISPLAY`,
    `REPORTS_FONT_BODY` and `REPORTS_FONT_MONO`; keep `"DejaVu Sans"` last in every stack, since it
    is the face that carries the report's status glyphs.
