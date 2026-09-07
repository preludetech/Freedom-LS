# Simple application forms

An application-gated course can already be applied to. `ApplicationCourseAccessBackend` shows an
"Apply now" CTA, `apply` creates a `CourseApplication`, and a status page says the request was
received. Nobody is ever asked anything. Give each gated course a questionnaire the applicant fills
in, so there is something to review when review lands.

Forms differ per course. They are ordinary questionnaires, a handful of questions each, with no file
uploads and no scoring.

## Reuse `form_engine`

`CourseApplication` gains a foreign key to a `Form`, and the answers live in `FormProgress` and
`QuestionAnswer`, the same models a quiz uses. FLS does not grow a second question-and-answer family.

This reverses the June 2026 decision that `course_applications` would own an `ApplicationConfig`
family. The NOTEs in `course_applications/models.py` and `views.py` that reserve it are now stale and
will mislead anyone who reads them. The reservation was overtaken: `form_engine` was extracted in
August 2026 because this feature was about to duplicate `Form → FormPage → FormQuestion →
QuestionOption` model-for-model, and the extraction spec named that duplication as its whole
justification. Building the duplicate now would spend the extraction and get nothing back.

The reuse is cheaper than the June research feared. `FormProgress` is keyed `(user, form)` and has no
course foreign key. The paging and answer-saving methods on it touch nothing course-shaped. The
course-progress receiver already returns early for an attempt with no `CourseFormAttempt`, an outcome
its own docstring names an application form as the example of. `research_form_engine_reuse.md` traces
all of it.

One new app edge falls out, `course_applications` to `form_engine`. `form_engine` gains none, so the
graph stays acyclic.

## A form's strategy describes the form, not who is using it

`FormStrategy` gains `UNSCORED`, and `FormProgress.score()` does nothing for it. An unscored form is a
form nobody scores. An application form is one use of that. A survey is another.

Nothing on `Form` records that a particular form is an application form. That constraint decides where
the application-ness lives: only `CourseApplication` knows, through its own foreign keys. Anything
needing to tell an application answer from a quiz answer asks the application, not the form.

Little needs to ask. The cohort report and the educator data table both reach answers through
`CourseFormAttempt`, which is minted only from an existing `CourseProgress`, which an applicant does
not have. Application answers are therefore unreachable from both by construction, with no filter
involved. `research_application_pii.md` traces every read path and the join that excludes it. One rule
falls out of that and has to be stated so the review spec inherits it. **An application's
`FormProgress` must never be adopted into a `CourseFormAttempt`.** If an approved learner is later
meant to sit the same form as course content, that is a fresh sitting.

The residual cost of the shared table is that an author can place an application form into a course's
content collection as though it were a survey. With `UNSCORED` that renders and behaves sensibly,
because it is a survey. So it is an authoring mistake to warn about in the authoring docs, not a state
to police in code.

## Authoring and binding

Application forms are authored as ordinary file-backed content, in their own top-level directory
alongside the course directories rather than inside any one of them. The loader already saves a form
found anywhere in the content root. A form becomes course content only when some course's `children:`
list or directory scan claims it, so a form in its own directory loads, validates, and is reachable by
nothing. There is no "hide this" flag to invent, because absence from `ContentCollectionItem` is
already the mechanism. `research_application_form_authoring.md` traces the loader and shows why a
reserved subdirectory inside a course directory cannot work without changing it.

A course names its form by path, the way `children:` names a child, and the loader resolves that path
to a real `Course.application_form` foreign key. This works because the loader parses every file
before it saves any of them, then resolves collection children last against a path-to-object map it
has already built. Binding an application form is one more lookup in that same phase.

Path beats slug because a path survives a rename and a slug does not. Resolution also happens inside
the load transaction, so a broken reference shows up immediately instead of needing a system check
after the fact.

The cost is one application-shaped field on `Course`, which otherwise knows nothing about
applications. That is a real cost and worth naming, but it buys the rename-safety, and the foreign key
adds no app edge, because `content_engine` already depends on `form_engine`. The alternative, keeping
the binding in `access_config`, would have the loader writing into JSON it is explicitly not allowed
to interpret. `access_config` keeps `access_type: application_gated` and nothing more.

One form may serve several courses. That is useful, one intake questionnaire for a family of
programmes, and it forces the next decision.

## `CourseApplication` owns the link to its answers

`CourseApplication` gains two fields. `form` is resolved from `course.application_form` once, when the
application is created. `form_progress` is the sitting holding that applicant's answers.

Resolving the sitting by `(user, form)` instead would be a bug waiting for the first shared form.
`FormProgress` has no uniqueness on that pair, so an applicant to two courses sharing one form would
read and overwrite one application's answers from the other. This is the same hazard `CourseFormAttempt`
exists to solve for course-embedded quizzes, and `learner_progress/attempts.py` says so in its own
docstring. `CourseApplication` needs its own narrow resolver for the same reason, and a direct link is
the simplest one.

`form` is resolved at creation rather than looked up live, so changing which form a course points at
does not rewrite a historical applicant's questions. `form_progress` is nullable and survives its
sitting being deleted, so a future targeted purge of the answers does not take the review record with
it.

## The applicant's flow

`apply` still shows a confirmation page. Its POST now creates the application together with its
sitting and sends the applicant into the form, rather than straight to the status page. A returning
applicant is routed on whether their sitting is finished. An unfinished one resumes in the form. A
finished one goes to the status page, which is what already happens today.

The form is paged, because `FormPage` already exists and the machinery driving it is course-free. The
last page is followed by a check-your-answers page: the answers laid out, a change link per question
that is an ordinary link back to that question's page, and the submit control. Walking forward again
lands back on the review page because it is next in sequence, so none of the redirect-threading the
full GOV.UK pattern needs is required.

The review page earns its place twice over. Submission is one-way until the review spec adds a
needs-changes round trip, so a mistake caught after submitting cannot be fixed at all, which raises
the value of catching it before. And it is the only correct home for the check that every required
question has been answered. Per-page validation is not enough. Nothing enforces page order on POST, so
the last page can be posted directly and a required question on a never-visited page sails through.
`research_draft_and_submit_semantics.md` has the trace.

Draft versus submitted is `FormProgress.completed_time`, not a new field. `state` and `submitted_at`
are spoken for by the review spec, and adding either now is exactly the pre-building its NOTE forbids.
The read-only-once-submitted check belongs in the `course_applications` view, so that when review
lands and read-only-ness follows `state` instead, one call site changes.

The applicant does not get the exam runner. Its chrome is built for a timed, scored test: the
leaving-will-submit-and-score dialog, the answered count framed as exam progress, the unload guard.
None of that is true of an application. The four question-input partials render a `FormQuestion` and
nothing else, so they are reused directly. The shell around them is new and plain.

## Question types

One new type, a number, for questions like age. It joins the free-text family, so it is a small
addition rather than a new answer shape.

No dropdown type and no boolean type. A dropdown is a rendering choice about an existing type, not a
new one, and a yes/no question is a two-option multiple choice. Both can be added the day a form is
awkward without them. `research_question_types_and_validation.md` maps every question in the first
form onto the resulting set.

There are no conditional questions. `form_engine` has no mechanism for one, and a follow-up like "how
did you hear about us, tell us more" is shown always rather than revealed. Building conditionals for
one optional text box is not worth it.

## Defects this work sits on top of

Both are live in the shipped course runner today. Both are `form_engine`-shaped rather than
application-shaped, so they get fixed there and both flows benefit.

**Resume walks backward.** `get_current_page_number()` returns the first page carrying any unanswered
question, required or not. Skip an optional question on page two, answer everything after it, come
back tomorrow, and you land on page two again. Every session, forever. The runner already computes a
corrected furthest page for its page-jump links, with a comment explaining exactly this, but never
applies it to the resume redirect.

**Explicit `children:` lists silently drop everything.** The loader compares the author's path against
a map keyed on the content-root walk, and normalises neither, so the relative form the authoring docs
document never matches. Probed against a real load, two documented children resolved to nothing. The
loader logged a warning for each and carried on. No demo course uses `children:` and no test covers an
explicit list, which is how it stayed hidden. Path binding needs this fixed anyway, and fixing it
makes `children:` work as documented.

**`FormAdmin` cannot mint a slug.** `slug` is read-only there and there is no save override, so a form
created through the admin saves with an empty slug and the second one collides on the per-site unique
constraint. It has never mattered, because every form has come through the loader. It matters as soon
as anyone authors a form another way.

Separately, and not fixed here: submitted option ids are not checked against the question being
answered, so an option belonging to another question is accepted into the answer. It predates this
work and is not made worse by it, but it now applies to application answers too.

## Not in this spec

- **The review workflow.** State machine, reviewer notes, approve, reject, withdraw, needs-changes,
  and the partial unique index that lets a rejected applicant re-apply. All reserved by the NOTE in
  `course_applications/models.py`, and untouched here. Answers are read in the Django admin, by
  superusers. No role is granted a table-wide permission over answers, which would hand every
  instructor every course's applicants.
- **A pluggable form-context backend.** §12 of the extraction spec reserved one. There is one consumer
  here, not a plugin point. The applicant's view is keyed on the application, resolves the form from
  it, and 404s on non-owners the way the status page already does.
  `research_form_context_backend.md` holds the design for whoever turns out to need it, including why
  one setting cannot serve both contexts.
- **The first deployment's actual questions.** Provinces, nationality, dealer referral. These ship in
  the concrete project. FLS ships the mechanism and at most a demo form.
- **Referral prefill.** Prefilling "Dealer — [name]" needs referral capture, which is its own idea with
  nothing built. The question ships as an ordinary one, and the prefill arrives with the spec that
  owns it.
- **File uploads, encryption at rest, virus scanning, a retention scheduler.** The June research
  designed all four for a separate-model system with document uploads. This form has no files, and
  database and backup encryption are already handled at the infrastructure layer. The only obligation
  carried forward is not choosing a deletion behaviour that forecloses a targeted purge later.
