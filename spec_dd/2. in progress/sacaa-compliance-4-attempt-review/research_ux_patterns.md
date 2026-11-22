# Research: UX patterns for the attempt review page and the attempt quick view

Question: what are the common UX patterns for an educator-facing single quiz attempt review page,
and for a summary quick view of one attempt? Decisions already taken in `answers.md`: the attempt
gets its own instance page linked from the learner Courses tab attempts table; the row also gets a
quick view with a summary; only completed attempts link; no design pass, built from
panel-framework pieces.

## 1. Common LMS patterns (web)

The review page has a similar shape in Moodle, Canvas and Blackboard:

1. **Summary block at the top.** Moodle's attempt review opens with a key/value table: Started on,
   State, Completed on, Time taken, Marks (x/y), Grade (percentage or scaled), Feedback. The
   grades report has the same columns for every attempt, and each row links to "review the
   attempt, just as the student would see it".
   https://docs.moodle.org/en/Quiz_grades_report
2. **Questions in served order, one block per question.** Each block carries the question number
   (its position in the paper served), a status (Correct / Incorrect / Partially correct / Not
   answered) and the mark ("Mark 1.00 out of 1.00"). Under those come the question text and every
   option in the order the learner saw it, with the learner's choice marked (a checked radio or
   checkbox) and a tick or cross beside it. A "The correct answer is: …" line closes the block.
   https://docs.moodle.org/en/Quiz_settings#Review_options
3. **Correctness is never colour alone.** Canvas labels the learner's pick "You Answered" and the
   key "Correct Answer" with text tags, as well as red and grey arrows.
   https://canvas.txstate.edu/courses/1288098/modules/items/48296262
4. **Question navigation.** Moodle has a numbered grid of question links coloured by result, for
   jumping through a long paper. It is optional, and a short quiz reads fine without one.
5. **Event log kept separate.** Canvas's quiz log (timestamps, answer changes) is a separate
   teacher view, not part of the graded review.
   https://community.canvaslms.com/docs/DOC-2988 ,
   https://answers.illinois.edu/illinois/156331 . Out of scope here, but it confirms that the
   review shows the final answers, not their history.
6. **Reached from a list of attempts.** Every LMS above opens one attempt from a per-learner (or
   per-quiz) attempts table whose columns match the summary block: attempt number, completed,
   score, percentage, result.

Quick view or summary drawer: none of these LMSs has a drawer for an attempt. The pattern
closest to one is the grades-report row, which holds the summary itself. So the quick view
should carry the summary block (pattern 1) plus a link to the full review, and no per-question
detail.

## 2. Codebase: what the spec has to fit

### Where the link and quick view sit

- The attempts table is a static `<c-panel-table>` in
  `freedom_ls/educator_interface/templates/educator_interface/panels/learner_courses.html`
  (`LearnerCoursesPanel`, `freedom_ls/educator_interface/panels/learner/panels.py`). Its columns
  are Attempt, Completed, Score, Percentage, Pass mark and Result (with a "Latest" marker). Each
  row is a `reports.report_data.QuizAttempt` (`attempt_number`, `completed_at`, `score`,
  `max_score`, `percentage`, `passed`). **It carries no `FormProgress` pk.** The spec must have
  `gather_learner_course_details` / `QuizAttempt` (`freedom_ls/reports/gather.py`) carry the
  attempt id, or the panel must build its own rows. `QuizAttempt` is also read by the PDF report
  and the cohort report, so adding a field touches those readers too.
- `QuizAttempt` is "one completed sitting", so the table already lists completed attempts only.
  That matches the "completed only" answer, and in-progress attempts never get a row.
- **Quick view routing is tied to a `ListViewConfig` section.** `_resolve_path` in
  `freedom_ls/panel_framework/views.py` matches `<section>/<pk>/__quick-view` (with an instance
  view) or `<section>/<pk>/__quick-view` on a section with `instance_view=None` and
  `quick_view` set. Instance pages likewise live at `<section>/<pk>`. The framework has no
  nested instance route (`learners/<pk>/attempts/<pk>`). The spec has to pick one of two:
  - a new `ListViewConfig` section for attempts (model `FormProgress`, `instance_view` and
    `quick_view` set, `check_access` going through the learner's visibility). The section needs
    to stay out of the sidebar, because an attempt list page is not wanted. Check whether
    `SectionConfigBase` supports a section with no menu entry or list page: the fields seen are
    `menu_label`, `is_visible`, `is_available`, and a hidden-from-menu flag was not found; or
  - a framework extension for a child instance under the learner. That is bigger, and the
    framework stays generic (see `HOST_CONTRACT.md`).
- Triggers: `<c-quick-view-trigger href url>`
  (`freedom_ls/panel_framework/templates/cotton/quick-view-trigger.html`) makes the `href` the
  full page and the `url` the drawer, so one anchor gives both ("a plain click opens the drawer,
  a modified click reaches the page"). A row then needs no separate "Open" button: one control
  covers the quick view and the instance page. `<c-panel-person-link quick_view_url=…>` and
  `<c-panel-attention-row quick_view_url=…>` show the precedent (`<pk>/__quick-view` appended).
- Panel-framework rules that apply (`claude_plugins/fls-dev/skills/panel-framework/SKILL.md`):
  - "A row's own record is opened in the quick view; detail a row does not need to be scanned …
    lives there, not in the row." The attempt-number cell (or the Completed cell) is the natural
    trigger.
  - Table row buttons are `size="small"` `secondary`, inside `<c-data-table-actions>`. Anchors
    need `no-underline` or `btn` (row-link style `no-underline text-on-surface`).
  - `#quick-view` opens with `show()`, never modal. It shares the sheet chrome (a bottom sheet on
    a phone, a header with a close control).
  - The educator-interface Placement table
    (`claude_plugins/fls-dev/skills/educator-interface/SKILL.md`) has no row for viewing an
    attempt. The spec decides whether it gains "A learner's Courses tab quiz attempts table →
    open attempt (quick view, review page)".

### Quick view content (fits `QuickView`)

- `QuickView` (`freedom_ls/panel_framework/quick_view.py`): `get_title`, `get_subtitle` (one
  muted line) and `get_context_data`. Precedent: `LearnerQuickView` and its template
  `educator_interface/quick_views/learner.html`, which uses
  `<c-panel-definition-list columns="2">` with `<c-panel-definition-row>`.
- A suggested shape that follows LMS pattern 1 and the existing table:
  - title "<quiz title>, attempt N", subtitle the learner's name (or the course);
  - rows: Result (`<c-panel-status-badge>` from `passed_badge`; with no pass mark, show no
    verdict, the same three-state guard as the learner results page), Score x/y, Percentage,
    Pass mark (or "No pass mark"), Started, Completed, Time taken (if wanted; derived from start
    and completion, like Moodle);
  - one link to the full review page (row-link or `variant="link"` style).
- Keep per-question detail out of the drawer.

### Review page content (fits `InstanceView`)

- Header: `<c-panel-page-header>` with `StatusBadge` / `HeaderStat`. The skill says the badge
  carries a state only when it is not the default and no action sits in the header. Pass/fail
  then fits as the header badge, or as stats (score, percentage), but not as both header stats
  and a repeated summary panel ("states each fact once").
- One panel per job: a summary panel (`<c-panel-definition-list>`: attempt number, started,
  completed, score, percentage, pass mark, result) and a paper panel (pages in served order, each
  page a section with its own heading, separated by space, never a card inside a card, per the
  Panels rules). Content blocks served are rendered where they sat.
- Per question: the number in served order, the status in text plus an icon, the options in the
  order shown with the learner's selections marked, and the correct options. The learner results
  page already has markup for this
  (`freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`,
  "Review incorrect answers"). It uses `success`/`error`/`unknown` icons with `aria_label`
  "Marked correct"/"Marked incorrect"/"Not marked", "Your answer" / "Correct answer" labels and
  "did not answer". The educator page should reuse the icon semantics and wording, changing
  "Your answer" to "Learner's answer". That template uses raw `rounded-lg border` cards and
  `bg-white`, which the panel rules forbid inside a panel. Reuse the semantics, not the markup.
- Data reader: `sitting_path()` in `freedom_ls/form_engine/conditions.py` gives the served paper.
  `answer_groups()` in `freedom_ls/form_engine/queries.py` walks the authored form and marks
  undrawn questions "not asked", which is the wrong shape for this page. The idea says undrawn
  questions are not shown.
- **Stale score note.** The learner results view computes `stored_score_outdated`
  (`freedom_ls/learner_interface/views.py` around line 2190) and shows a "This quiz has changed
  since you sat it … not re-marked" note. The review shows current wording against a frozen score
  (the idea's "question wording is the current wording"). So a per-question correctness that
  disagrees with the stored score can appear. The spec should say whether the educator page
  shows the same note (as a `<c-panel-callout tone="warning">`) and where.
- Navigation: a `<c-back-link>` to the learner's Courses tab. A Moodle-style question grid is
  optional. Quiz length decides whether it is worth it, and it is not in the idea.

### Accessibility and responsive rules the spec can cite

- Correctness in text plus an icon, never colour alone (Canvas, existing learner markup).
- A table whose columns do not fit becomes cards (`cards_when_narrow`): the attempts table
  should keep working beside an open quick view at 375px.

## 3. Points the spec must settle

1. How the attempt id reaches the attempts table row (`QuizAttempt` gains a field, or the panel
   builds its own rows).
2. The route: a new hidden `ListViewConfig` section for `FormProgress` with `instance_view` and
   `quick_view`, versus a nested route. Confirm the framework can keep such a section out of the
   menu.
3. Which cell is the trigger. One `<c-quick-view-trigger>` gives the drawer on click and the page
   on a new-tab click.
4. The fields in the quick view and the header, each fact stated once.
5. Whether the stale-score note appears.
6. Whether the Placement table in the educator-interface skill gains a row.

status: ok
