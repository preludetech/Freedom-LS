# Simple application forms

An application-gated course can already be applied to. `ApplicationCourseAccessBackend` shows an
"Apply now" CTA, `apply` creates a `CourseApplication`, and a status page says the request was
received. Nobody is ever asked anything. Give each gated course a questionnaire the applicant fills
in, so there is something to review when review lands.

Forms differ per course. They are short and unscored, and some of them ask the applicant to upload a
document.

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

A number type, for questions like age. It joins the free-text family, so it is a small addition rather
than a new answer shape. A file-upload type is the other addition, and it has a section to itself.

No dropdown type and no boolean type. A dropdown is a rendering choice about an existing type, not a
new one, and a yes/no question is a two-option multiple choice. Both can be added the day a form is
awkward without them. `research_question_types_and_validation.md` maps every question in the first
form onto the resulting set.

There are no conditional questions. `form_engine` has no mechanism for one, and a follow-up like "how
did you hear about us, tell us more" is shown always rather than revealed. Building conditionals for
one optional text box is not worth it.

## File uploads

An applicant may be asked to upload a scan or photo of an ID or passport. That is the most sensitive
thing FLS accepts, from the least trusted source it has, so this path carries more design than the
rest of the form together.

`QuestionType` gains `FILE_UPLOAD`. This is the same shape of decision as `UNSCORED` and holds for the
same reason: a file-upload question is a question `form_engine` can render and store an answer for,
and an ID scan is one use of it. A survey asking for a photo of a finished project is another.

The cost is worth naming. `form_engine` today has no object storage, no private bucket, no quarantine
state and no per-user erasure surface, and it gains all four permanently, for every deployment,
whether or not that deployment ever asks anyone for a file. Reusing `form_engine` saved work on the
question, answer and paging side. It saves nothing here, because there was nothing to reuse.

### Where the bytes go

The `user_uploads` alias already exists for exactly this, in the private user-data bucket, with no
consumer yet. This is its first. The key is namespaced away from the reports prefix sharing that
bucket, prefixed by the uploading user so erasure is a scoped delete rather than a bucket scan, and
leafed on a UUID rather than the applicant's filename, which is attacker-controlled and can carry path
segments. The user prefix is deliberately predictable: it names a scope, not an object.

A new `QuestionAnswerFile` in `form_engine` holds the file one-to-one with the `QuestionAnswer` it
answers, carrying the stored file, the original filename for display, and the scan state. Those three
columns on `QuestionAnswer` itself would widen a table shared by every quiz answer in the system to
hold nulls for very nearly every row it will ever have.

### The upload never rides the page POST

`save_answers` deletes the answer row for any question arriving blank. That is correct and
load-bearing for the four existing types, because a cleared text box has to lose its row or the
answered tally counts it and hides what is still outstanding. A file input sends nothing on a page
re-post, since no browser refills one, so a file question reads as blank every time the applicant
revisits its page. Left alone, `save_answers` deletes the row holding an uploaded ID scan and cascades
the file record away with it, on the most ordinary action available: leaving and coming back. The
bytes orphan in the bucket and the applicant is given no reason their upload vanished.

Two requirements, both load-bearing rather than belt and braces. Upload and removal each go to their
own endpoint in their own request, so a page submit has no opinion about the file either way; because
the attached state renders no file input, the page form posts nothing for that question and stays an
ordinary urlencoded form. And `save_answers` skips file questions outright, never inspecting their
rows. That second one lands in `form_engine`, so it is a property of the question type rather than
anything application-aware, and it holds even if someone later puts a file question on a page form.

### The widget has two states, and the filled one matters more

Empty is a file picker. Attached shows the applicant's own filename and the size, with two separate
controls.

Remove is its own action, not a side effect of replace. An applicant who uploaded the wrong document
and does not have the right one to hand needs to be rid of it now, rather than stuck with it until
they find a replacement.

Remove deletes the stored object, not just the row. Django does not delete from storage when a row
goes, so a removed file still sitting in the bucket is the worst outcome here: the applicant is told
it is gone and their ID scan is not. A receiver on `QuestionAnswerFile` makes that true however the
row was removed, including a cascade from deleting the user, which is also what makes the erasure
prefix mean anything.

Removing a file from a required question puts the application back into an incomplete state. That is
correct, and the widget says so where it happens rather than letting the applicant find out on the
review page.

One invariant ties the widget to the rest of the form: a `QuestionAnswer` row exists if and only if
its question has a real answer. Remove deletes the row rather than blanking a field, and nothing
creates the parent row without a file. Break it and the required check reads an empty row as answered,
and the resume rule drags the applicant back to a page they already finished.

### What happens to the bytes

Checks run cheapest first: extension, declared size, a bounded read, then the real type from magic
bytes. The browser's content type and the original filename are both applicant-controlled and neither
is evidence of anything. Images are decoded and re-encoded through Pillow, which strips EXIF, since a
phone photo of an ID carries the coordinates of where it was taken, and forces a full decode of the
pixel stream, which is what catches an image that parses at the header and not beyond. One operation
buys both, at the cost of some detail that a reviewer reading a passport page will not see. No new
dependency: Pillow is already here and does more than a MIME sniffer would, and the PDF check is five
magic bytes. JPEG, PNG and PDF are accepted. Not WebP, which no camera or scanner produces, and not
HEIC, which would need another dependency to decode.

Uploads are quarantined. A file is pending when stored and becomes clean or rejected. FLS ships the
seam and a default scanner that clears nothing, because a default that cleared everything would let
every deployment believe files were scanned when they were not. A downstream project points the
setting at a real scanner, and a system check warns when production is still running the no-op.

In a stock install, the thing that clears a file is a superuser, deliberately, through a logged admin
action. That has to exist from the first day, or stock FLS has a review queue nobody can ever open.

The applicant sees none of this. A scan state offers them no action, submission is not gated on it,
and telling them their document is pending raises a question they cannot answer.

### Reading one back

A reviewer reaches a file through an admin-gated view that streams it, mirroring the report download
that already does this: permission checked on every request, sent as an attachment, never cached. It
differs in one line, refusing anything not marked clean.

A signed bucket URL is the wrong tool even though the bucket supports one. It is minted once and
carries no session, so it can neither re-check the scan state on each fetch nor express superuser
only. A file reclassified as rejected stays fetchable for the rest of the signature's life, and the
link works for whoever ends up holding it. The applicant can re-open their own upload from the review
page through the same view with its own ownership check, because they already own the document.

Production caps a request at 5 MB in two pinned places, the production settings and a Caddy directive
tracked as a deployment conformance item. A phone photo is routinely 2 to 8 MB, and a body over the
cap is refused at the edge before Django runs, so there is no friendly error to be had. Both move to 8
MB, still pinned, with FLS's own per-file limit at 6 MB so an oversized file gets a proper in-form
message and the rest of the request still fits underneath. The browser checks size before sending, so
the common case never reaches a bare rejection at the edge.

One gap stays open, and is better stated than discovered. Nothing FLS runs inspects the inside of a
PDF, so a payload embedded in a well-formed one passes every check here. The quarantine scanner is the
only control for it, and FLS ships none.

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
- **Encryption at rest, a shipped virus scanner, a retention scheduler.** Database and backup
  encryption are handled at the infrastructure layer already and cover these rows like any other.
  Scanning gets a seam and no scanner. Uploads are deletable by design and by hand, and nothing
  expires on a timer.
- **Client-side image downscaling, and per-question upload limits.** The size ceiling moves instead,
  and the allowed types and sizes are one set of constants rather than per-question configuration.
  There is one use case; either can be built the day a second one disagrees with it.
