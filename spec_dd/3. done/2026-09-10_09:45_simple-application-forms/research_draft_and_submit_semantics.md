# Draft, resume, submit — testing the multi-step research against the shipped runner

Companion to `research_multistep_ux.md` (prior research, not repeated here). That
research was written before `form_engine`'s runner shipped and before the "reuse
`form_engine`" decision was made. This note re-tests its ten recommendations
against the code that exists today and against `freedom_ls/course_applications/`.

**Load-bearing finding used throughout this note:** an applicant has no
`LearnerCourseRegistration` and therefore no `CourseProgress` — that registration
is the very thing approval will later grant. `_ensure_player_course_progress`
(`freedom_ls/learner_interface/views.py:776-794`) returns `None` whenever
`learner_for_course` can't resolve a registration, and every course-side form
helper in `freedom_ls/learner_progress/attempts.py` (`get_or_create_incomplete`,
`get_latest_incomplete`, `completed_attempts`, `finalise_stale_incomplete`) takes
a `CourseProgress` as a required argument, not an optional one. So the reuse
decision can only mean "reuse the `form_engine` **models**" — `Form`, `FormPage`,
`FormQuestion`, `QuestionAnswer`, `FormProgress` and its methods
(`save_answers`, `get_current_page_number`, `existing_answers_dict`,
`complete`) — none of which import anything course-shaped. It cannot mean
"reuse `form_fill_page`/`form_start`/`course_form_complete` as-is": those views,
and the chrome they render, are wired through `CourseFormAttempt` and
`course_progress` the whole way down. This governs the answer to nearly every
question below.

## Where the ten prior recommendations land

| # | Recommendation | Verdict |
|---|---|---|
| 1 | Persisted-draft model, not session/cookie wizard storage | **Already satisfied.** `FormProgress` is exactly this: a DB row, resumable via `get_current_page_number`, survives logout/device switch because it's keyed on `user`. Nothing to build. |
| 2 | One URL per step | **Already satisfied** by the pattern, not the URL itself. `form_fill_page(course_slug, index, page_number)` is one real GET/POST URL per page with working back/refresh/bookmark behaviour. The application flow needs its own analogous URL (there is no course/index to key off), but the *pattern* survives unchanged. |
| 3 | Question-bank schema (`Course → ApplicationStep → ApplicationQuestion → ApplicationResponse`) | **Now wrong.** Superseded outright by the reuse decision. `Form`/`FormPage`/`FormQuestion`/`QuestionAnswer` already are this schema. Building a parallel one would duplicate `form_engine` for no reason. |
| 4 | Numbered + labelled progress indicator, all steps visible | **Already satisfied.** `course_form_page.html`'s `exam-page-dots` partial and "Page X of Y" strip (`:336-357`) already do this. Applications inherit it if they keep the paging chrome (see Q6). |
| 5 | GOV.UK Check Answers as the final step, per-section Change links round-tripping to review | **Survives, scoped down.** See Q4 — the full per-section round-trip protocol (`?return=review`) is not warranted here; a single review-as-final-page is enough and cheap. |
| 6 | Auto-save on each step advance + visible "Save and exit" | **Already satisfied.** `form_fill_page` calls `save_answers` on every POST regardless of validation outcome (`views.py:1106`, before the required-check branches). `save_and_exit_url` already exists in the runner chrome (`views.py:1209-1212`). |
| 7 | File upload UX | **Out of scope, not merely deferred.** `QuestionType` (`form_engine/enums.py:11-17`) has exactly four members — `multiple_choice`, `checkboxes`, `short_text`, `long_text` — no file type. Every question in `idea.md`'s list maps onto one of the four. Nothing to design against. |
| 8 | Status model with admin round-trip (`draft → submitted → under_review → …`) | **Correctly reserved for the later review spec.** Don't pre-build it — see Q1. |
| 9 | Branching invalidation rule | **Not applicable.** `idea.md`'s question set has no conditional reveal (the `heard_about_detail` prefill is a default value, not branching) and `form_engine` has no cross-question conditional model. Nothing to design against until a form actually branches. |
| 10 | Playwright back-button test | **Survives, and there's a template for it.** `learner_interface/tests/playwright/test_form_submit_navigation_guard.py` already exercises this shape of test against the exam runner; write the applicant-flow equivalent. |

## 1. State mapping: `completed_time` vs. draft/submitted

The NOTE at `freedom_ls/course_applications/models.py:23-29`, verbatim:

> NOTE: when application review lands, this model gains `state = FSMField(protected=True)`, the
> submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions,
> submitted_at/decided_at/decided_by, the view_application/change_application permissions,
> ApplicationNote + ApplicationStateTransition, the application_state_changed signal, and the
> active-state PARTIAL unique index that REPLACES the plain constraint below.
> NOTE: when application forms land, this model gains `config FK ApplicationConfig` + answer/file children.
> Do not architect these away — leave this model standalone and additive.

Two things fall out of that note directly:

- **`submitted_at` is spoken for.** It belongs to the review FSM, not to this
  spec. Do not add a field of that name to `CourseApplication` now — a later
  migration would either collide with it or have to rename around it.
- **`state` is spoken for too.** No `status`/`is_submitted` boolean either —
  anything that reads as "the review FSM's field, built early" is exactly the
  thing the NOTE says not to pre-build.

`FormProgress.completed_time` (`form_engine/models.py:210`, set by `complete()`
at `:313-322`) is the only completion signal `form_engine` has, and it already
means the right thing for this spec's purposes: "the applicant finished
answering and this sitting is final." That is draft-vs-submitted, exactly.
**Recommend deriving the applicant-facing draft/submitted distinction from
`completed_time` on the linked `FormProgress`, not from a new field on
`CourseApplication`.** This is additive-compatible with the FSM: when review
lands, `state`'s initial value can be driven by the same signal (submit() the
transition and `form_progress.completed_time` being set can be made to agree,
or the transition can simply require it), and the FSM's own `submitted_at` can
record *when the state transition ran* — a different, later moment than *when
the applicant finished typing* — without the two ever needing to be reconciled
retroactively.

**One field is worth adding now, and it is not a status field:** a direct FK
from `CourseApplication` to the `FormProgress` that holds its answers (e.g.
`CourseApplication.form_progress`), rather than resolving it by `(user, form)`
at read time. The domain glossary is explicit about why: *"Course code
resolves attempts through `learner_progress/attempts.py`, never through
`FormProgress`'s own `(user, form)` helpers, which would hand back a sitting
from another record."* The same hazard exists here — nothing stops the same
`Form` being reused across two courses' application configs, and `(user,
form)` can't tell those two applications apart. `CourseApplication` needs its
own narrow resolver (a direct FK is the simplest one), the same way
`CourseFormAttempt` is `learner_progress`'s.

**Also load-bearing for `complete()`:** `FormProgress.score()`
(`form_engine/models.py:495-503`) unconditionally dispatches on
`form.strategy`, and raises a bare `Exception` for anything that isn't
`CATEGORY_VALUE_SUM` or `QUIZ`. An application form must be created with
`strategy=FormStrategy.CATEGORY_VALUE_SUM` — `score_category_value_sum()`
degrades harmlessly to an empty `scores` dict when no page/question carries a
`category` and no option carries a numeric `value`, which an application form
won't. `QUIZ` must not be used: it drags in `quiz_pass_percentage`,
`passed()`, and the passed/failed verdict branch in
`course_form_complete.html` (`:8-153`), none of which mean anything for an
application, and would render nonsense if that template were reused as-is
(see Q6 for why it shouldn't be).

## 2. Where the applicant enters and exits

`freedom_ls/course_applications/views.py:19-62`'s own NOTE:

> NOTE: when application forms land, the POST body will resolve the
> ApplicationConfig, create a draft application, and redirect to the
> multi-step form flow instead.

("ApplicationConfig" in that NOTE predates the reuse decision — read it as "the
course's `Form`", per recommendation #3 above.)

Resulting URL set and redirect chain:

- `GET/POST course_applications:apply` (`course_slug`) — unchanged front door.
  `GET` still shows the confirmation page. `POST` no longer bare-creates a
  `CourseApplication` and redirects to `status`; it creates the draft
  (`CourseApplication` + its `FormProgress`, via `get_or_create` exactly as
  today, race-safety included) and redirects into the form flow's first page.
- A new pair analogous to `form_start` / `form_fill_page`, scoped to the
  application rather than to a course index — e.g.
  `course_applications:application_form_page(pk, page_number)`. `apply`'s POST
  redirects to page 1 of this (or to `get_current_page_number()`'s answer —
  see Q3 for why that needs correcting first).
- `course_applications:status` (`pk`) stays the read-only "received, pending
  review" page, but it is now reached from **two** directions: the existing
  one (an applicant who already has an application, per the early-return at
  `views.py:43-45`), and a new one — the final page of the form flow
  redirecting here once `complete()` has run.

Returning-applicant behaviour, both driven off the same early-return at
`apply:43-45` (`get_application_for_course`), which must now branch on
`completed_time` rather than treat every existing row alike:

- **Half-finished draft** (`form_progress.completed_time is None`): `apply`
  should send them back into the form flow — resuming at the corrected
  current page (Q3), not back to the confirmation page (they've already
  confirmed) and not to `status` (there is nothing to report yet).
- **Submitted** (`form_progress.completed_time is not None`): `apply` sends
  them to `status`, exactly as today's code already does — this direction
  needs no change.

Note the collision surface: `spec_dd/2. in progress/better-form-start-page/`
is a pure visual restyle of `course_form.html` (the *course-content* form start
screen — "Quiz Start — First Time"), explicitly scoped to look-and-feel only
("this design is not aware of the internal mechanisms of this code base... you
must not make new functionality based on the design"). Since this spec does
not reuse `course_form.html` for the applicant-facing start screen (there is
no course index/collection item to key its `view_form` off), the two specs
touch different templates and don't collide on content — only worth flagging
if `better-form-start-page` also touches the shared question-partial or button
components this spec might borrow (it doesn't appear to, per its one-line
scope).

## 3. Resume across sessions: `get_current_page_number` is not safe to call bare

`get_current_page_number()` (`form_engine/models.py:251-272`) returns the
first page carrying **any** unanswered question — required or not:

```python
for question in questions_on_page:
    if not self.answers.filter(question=question).exists():
        return idx + 1
```

Trace the optional-skip case: applicant reaches page 2, leaves an optional
question blank, clicks Next (allowed — the required-check at
`views.py:1098-1102` only inspects `required` questions), and goes on to
answer every question on pages 3 onward. They log out and come back. The
equivalent of `form_start` calls `get_current_page_number()` again — it still
sees no answer row for that optional question on page 2, so it **routes them
back to page 2**, discarding no data but discarding their forward progress:
every resume from here on lands on page 2, not on page 8 where they actually
were.

This is not a hypothetical for this spec — it is a **pre-existing, partially
patched defect already present in the shipped runner**, and `form_fill_page`
itself says so. Its page-links loop (`views.py:1150-1167`) computes a
corrected `furthest_page`:

```python
# A skipped question leaves no answer row behind, so the first-outstanding
# page can sit behind where the learner has actually reached. On its own it
# would lock the page they are standing on, and pages they have already
# answered, out of the page-jump navigation.
...
furthest_page = max(
    form_progress.get_current_page_number(), page_number, furthest_answered_page
)
```

That correction is applied **only** to which page-dots render as clickable
inside a page the learner has already reached. It is never applied to
`form_start`'s redirect (`views.py:1016`, bare
`form_progress.get_current_page_number()`), so the resume entry point still
has the bug the fix was written for. Doesn't strand the applicant (each page
they land on remains completable — required-only gating still lets them
proceed), but it does **loop them backward** on every fresh session, forcing
them to re-click through pages they'd already cleared.

**Recommend:** the application flow's resume view must not call
`get_current_page_number()` bare. Reuse (or extract into `form_engine`, since
it's a form_engine-shaped bug, not an application-shaped one) the same
`furthest_page`-style correction — the max of the raw current-page number and
the highest page number carrying any saved answer — before redirecting.

## 4. Check-your-answers: warranted, but scope it down

The runner today has no review/summary step at all. The final page's "submit"
control is a confirm dialog (`course_form_page.html:510-590`) showing an
answered/total **count**, not the answers themselves, and clicking through it
calls `complete()` directly (`views.py:1113`) — there's no code path today for
"show me what I put, let me fix one thing, come straight back here."

For an ~8-10 question form, the **full** GOV.UK pattern from the prior
research — per-section Change links, a `?return=review` redirect override
threaded through every page's POST handler — is not warranted: that machinery
earns its cost on long or branching forms, and (per row 9 above) this form has
neither length nor branches. Building it would mean adding a "where do I
redirect after this page" parameter to `form_fill_page`'s POST handling that
doesn't exist today, for a form short enough that walking forward through it
again is not a burden.

But **do include a review step**, and for a reason the prior research didn't
have available to it: with the review FSM deferred to a later spec, submission
in *this* spec is one-way — there is no "needs changes" round-trip yet to
recover from a mistake spotted after submitting. That raises the cost of
letting an error through, which argues for catching it before `complete()`
fires, not after.

**Recommend:** implement the review step as literally the page **after** the
form's last real `FormPage` — same Previous/Next chrome, no new redirect
parameter. A "Change" link on it is just a normal link to that page's own URL;
walking forward again naturally lands back on the review page, because it's
next in the page sequence. Cost: one new template (list
`existing_answers_dict` across every page, not just the current one) and one
branch in the page view ("page_number == total_pages + 1" renders the review
instead of a `FormPage`, and its POST calls `complete()` instead of advancing
by one page). That's the whole GOV.UK "check-answers-as-final-step" idea
delivered without the per-section round-trip protocol its full version needs.

This step is also the natural, and arguably the *only correct*, home for the
whole-form required-answers check — see Q5.

## 5. Submit-time validation: per-page gating has a hole

`save_answers` (`form_engine/models.py:290-311`) deletes the row for any
question submitted blank — deliberate, so a blank question never counts
toward the answered tally or hides itself from "still outstanding." The
required-answers check that stops a blank required question reaching
`complete()` lives in `form_fill_page`, scoped to **the page just posted**
(`views.py:1098-1102`, `1108-1121`): a 422 re-render of that one page,
carrying `required_answers_error`, built from `_unanswered_required_message`
(`views.py:1027-1033`) — this is the FLS-convention HTTP 422 for a validation
failure, already followed correctly here (`views.py:1243`).

That check assumes the applicant reached the final page by walking forward
through every earlier one in order — but nothing in `form_fill_page` enforces
that assumption. The view accepts any `page_number` in range
(`views.py:1056-1058`); the "is_accessible" gate that greys out unreached
pages (`views.py:1185-1186`) is UI-only, rendered as a non-link `<span>`
(`course_form_page.html:181-184`) rather than a server-side check on POST. A
bookmarked or hand-typed URL for the last page, posted directly, only
validates *that page's* required questions — a required question on an
earlier page that was never visited (or was visited and then had its answer
row deleted by leaving it blank on a later re-post) can sail through to
`complete()` unexamined.

**Recommend:** the whole-form required-answers check must not be "trust that
each page validated on the way through." Run it once, across every question
in the form, at the point that would call `complete()` — which, per Q4, is
the review page's POST handler. On failure, 422 the review page (same
convention as today) with a message naming every outstanding required
question, and probably a link to the earliest one — not just the questions
belonging to whatever page happened to be posted last, since the review page
has no "current page" of its own to scope the message to.

## 6. Reuse versus rewrite of the runner UI

The load-bearing finding at the top of this note settles most of this: the
**models** are shared; the **course-content player views and their chrome are
not**, because they're wired through `CourseFormAttempt`/`course_progress`,
which an applicant never has. So this was never a choice between "reuse the
template with chrome switched off" and "a second template" at the view level —
a second view is structurally required regardless.

At the template level, the honest split is finer-grained than "reuse" or
"rewrite whole":

- **Reuse directly, unchanged:** the four question-input partials —
  `form-input-multiple-choice`, `form-input-checkboxes`,
  `form-input-short-text`, `form-input-long-text` — and `form-question`
  (`course_form_page.html:38-158`). These render a `FormQuestion` and nothing
  else; they carry no course or quiz coupling.
- **Wrong for an application, and must not be inherited:** everything
  `_exam_runner_base.html`'s chrome does for a *timed test* — the
  `beforeunload` guard while mid-attempt (`alpine-components.js:92-138`), the
  submit-on-exit "leaving now will submit and score, you can't change your
  answers" dialog copy (`course_form_page.html:264-273`), the live
  answered-count tally framed as exam progress (`:329-332`), and the submit
  dialog's "your answers will be scored" copy (`:548-568`). None of this
  language or behaviour belongs on an application — nothing is timed, nothing
  is scored, and (per Q1) `strategy=CATEGORY_VALUE_SUM` guarantees `scores`
  stays an empty, meaningless dict.

**Recommend:** a second, simpler application-runner template, built by
composing the reusable question partials into new chrome — not by carrying
`_exam_runner_base.html`'s Alpine components (`examRunner`, `examRunnerForm`,
`examExitDialog`) into a mode where their copy has to be conditionally
suppressed throughout. The exit dialog's own template already forks its copy
on `form.submit_on_exit` (`:264-273`); adding a third fork for "this isn't a
test at all" throughout that file would leave quiz-only strings and
quiz-only Alpine wiring (submit-and-exit, answered-vs-scored framing) sitting
inert in a template an application page pulls in. That's a bigger long-term
cost than building a plain "save-on-exit, no scoring, no timer" page shell
that composes the same five reusable partials.

Cost: one new base template with page-number/Previous/Next chrome (reusing the
page-dots partial pattern, without the exam framing), one new Alpine component
scoped to "save this page's answers, no beforeunload panic" if any client-side
behaviour is wanted at all — plausibly none is needed, since there's no
timer/score to protect the applicant from losing. The five question partials
move or get shared via `{% include %}`/a shared partial module rather than
copy-pasted.

## 7. What must stay open for a later "needs changes" round-trip

Nothing is built now — review is explicitly a later spec — but three
decisions here would otherwise have to be undone:

- **Don't gate "read-only" on `completed_time` inside the reused
  `form_engine` model layer.** Put that check in the `course_applications`
  view (Q1's `CourseApplication.form_progress.completed_time is not None`
  check), not inside anything shared with the course-content runner. When the
  FSM lands and read-only-ness should instead follow `state`, only that one
  call site changes.
- **`complete()` is one-way in `form_engine`** — it guards on `if
  self.completed_time: return` (`:315-316`) and has no "reopen" method.
  Nothing here needs to add one, but the design must not do anything that
  makes reopening structurally impossible later — e.g. don't add a database
  constraint or signal that treats a completed `FormProgress` as immutable.
  Nulling `completed_time` and re-running the applicant back through the form
  page view is a legitimate future write against the existing model; leave it
  legitimate.
- **Don't decide now whether "needs changes" edits the same `FormProgress` or
  mints a new one** (the way `learner_progress/attempts.py` mints a fresh
  attempt per quiz retry, keeping history). That's a real design choice — one
  `FormProgress` reopened loses the reviewer's view of "what did they
  originally submit before the change request", a fresh one preserves it —
  and it belongs to whichever spec adds `request_changes`/`resubmit`. This
  spec should keep `CourseApplication.form_progress` as a plain FK to a single
  row so either answer stays available, rather than building anything (a
  history table, a M2M) that presumes one answer over the other.

status: ok
