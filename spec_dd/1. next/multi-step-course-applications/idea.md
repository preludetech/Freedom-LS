# Multi-step course applications

Let a course's application be a set of steps the applicant works through in any order, over weeks
if need be, where which steps they get depends on what they have told us and on what reviewers have
decided so far. FLS owns the machinery. A downstream project owns the rules that decide the steps.

## The case that drives this

An aviation deployment. An applicant says what qualifications they already hold. Depending on the
answer they may have to sit an exam at a centre near them, and they need a medical from a specialist
doctor who is also near them. They pick a way of studying, e-learning or in-person lectures, and that
changes which courses we recommend. They upload documents along the way: licences, logbooks, medical
certificates. These are often hard to find, so they arrive in any order. Some steps come after the
application is approved.

A reviewer may decide an uploaded document is not good enough. Sometimes that means "upload a better
scan". Sometimes it sends the applicant down a different path: the qualification they claimed is not
accepted, so now they have to sit an exam and upload the result instead.

Long application forms also lose people. An applicant who is stuck needs a way to ask for a person to
contact them and talk them through it.

## What FLS has today

A `CourseApplication` is one sitting of the course's application form plus an `is_submitted` flag
derived from that sitting. It has no states, no reviewer, and no audit trail. Uploads exist only as a
file-upload question inside a form sitting (`QuestionAnswerFile`), so a document cannot be sent on its
own, weeks after the form was finished, or re-sent after a reviewer turns it down.

Nearby work this builds on:

- `educator-interface-full-polish/application-review-ui`: the application state machine, reviewer
  permissions, the audit log and the review inbox. Drafted, not yet a spec.
- `form-engine-branch-logic`: conditional pages and questions, which covers "ask about previous
  qualifications and branch on the answer".
- `file-scanning`: content scanning for uploaded files.
- `phone-number-form-field`: needed by the ask-for-help contact form.
- `RecommendedCourse` and the recommend outcome in
  `corporate-job-course-recommendations-3-recommend-outcome`.

## Application requirements

**Application requirement** is a new term. It means one thing an applicant has to do or provide for
one `CourseApplication`. "Requirement" is not a model, field or function name anywhere in FLS today.

A requirement has a kind:

- fill in a form
- upload a document
- wait for staff to verify something

An exam or a medical happens outside FLS. The applicant proves it with an upload, such as the exam
result or the medical certificate, and a reviewer accepts it. Where there is nothing to upload, a
staff verification requirement covers it: a reviewer marks it done.

It has a status: outstanding, submitted, accepted, turned down, or superseded. It can offer the
applicant a list of options and record which one they picked, for "choose the exam centre nearest to
you". FLS stores the pick. The list of options comes from the deployment.

Each requirement says which step of the application it holds back:

- **approval**: the application cannot be approved until it is accepted
- **registration**: due after approval, and the learner is not registered for the course until it is
  accepted
- **nothing**: asked for, but not blocking

So the application needs a state after approval and before registration, "approved, conditions
outstanding" or similar. Most requirements in the aviation case hold back approval. The flexibility
to put some after approval is a stated product need.

The applicant sees one page listing their requirements and their status, and can work on them in any
order.

## The requirement resolver

Which requirements an applicant gets is decided by a **requirement resolver**, a class a deployment
names in a setting, following the house pattern for pluggable behaviour (`COURSE_ACCESS_BACKEND`,
`MESSAGING_POLICY`): a loader, a `*Decision` return value, a boot-time check, and conformance tests.

The resolver FLS ships reads a fixed list of requirements from the course's access configuration in
the course content. A deployment with real rules writes its own resolver in Python, reading the
applicant's form answers, their uploaded documents and reviewer verdicts.

### No workflow graph

This is the decision the rest of the design rests on. **The resolver is a function of the
application's current data, and FLS re-runs it after every event**: an answer saved, a document
uploaded, a reviewer verdict. FLS compares the resolver's answer with the
stored requirements:

- a requirement the resolver now wants, and that is not stored, is created as outstanding
- a stored requirement the resolver no longer wants is marked superseded. It is kept, never deleted,
  so a reviewer can see what happened
- an accepted requirement stays accepted

There are no transitions between steps for an author or developer to draw, so there is no way to send
one applicant to two places at once. The case of a rejected qualification needs no special handling:

1. The applicant says they hold a qualification. The resolver asks for the qualification document.
2. A reviewer turns the document down and picks a reason.
3. The resolver runs again and reads the reason. What it asks for next is its call:
   - the same upload again, because the scan is unreadable
   - better evidence, because the applicant uploaded the wrong thing. A new upload requirement, for
     example "a certified copy of the licence", replaces the old one.
   - "sit exam X" and "upload exam result", because the qualification itself is not recognised
   - a choice between better evidence and the exam (see "Choices" below)

   In every case but the first, the old qualification requirement becomes superseded.

### Choices

The resolver can offer a **choice**: a group of requirements where any one being accepted is enough.
"Upload a certified copy of your licence, or book exam X." The applicant usually knows whether the
right document exists somewhere. Forcing an exam on someone who uploaded the wrong file costs them
weeks, and forcing a re-upload on someone who does not have the document leaves them stuck.

The applicant sees the options side by side, in plain words, and can switch between them until one is
accepted. The first one accepted satisfies the choice and the others become superseded. Choices are
one level deep: no choice inside a choice.

A changed answer works the same way. If the applicant reopens the qualifications form and changes
"yes" to "no", the resolver runs and the requirements follow.

### Reopening a completed form

`form_engine` gains the ability to reopen a completed form sitting. It does not decide when that is
allowed. Whoever owns the sitting does: a course application can allow it, while a scored quiz in a
course does not, because retakes already have their own path through course form attempts.

For an application:

- The applicant can reopen any of their form requirements until the application is approved. People
  notice their own mistakes, and fixing one should not need an email to a reviewer.
- Their earlier answers are filled in, so they change only what was wrong.
- Reopening an accepted form puts it back to submitted, so a reviewer sees the new answers before
  they count.
- A reviewer can ask for a form to be redone the same way as any other requirement, by turning it
  down with a reason.
- Each reopen goes in the audit log. A reviewer can see that answers changed and when.

This is the same position `form-engine-branch-logic` takes inside a form: show or skip based on what
is already known, rather than a routing graph.

### Reviewer verdicts

A reviewer either accepts a submitted requirement or turns it down with a **rejection reason**. The
reviewer says what is wrong, never what happens next. They should not have to know the resolver's
rules, and they cannot pick "reject" when they meant "try again", because they never choose between
the two. The resolver turns the reason into the consequence.

Because the resolver works only from the application's current data, the review screen can run it on
the proposed verdict and show "the applicant will be asked to: …" before the reviewer confirms.

Rejection reasons are defined in Python by the deployment, per document type, next to the resolver,
because the resolver's code branches on them. A reason an author added in content would be one the
code has never heard of. FLS ships a generic set any resolver can use, such as unreadable, wrong
document, expired, and name does not match. Each reason has a label for the reviewer and an
explanation for the applicant saying what to do next, and the wording can be changed through template
overrides. The reviewer can always add a free-text note for the applicant as well.

One accept is enough. No requirement or application needs more than one person to sign it off.

Because a turned-down requirement already says "the applicant has more to do", the application-level
"changes requested" transition drafted in `application-review-ui` may no longer be needed. That spec
should be revisited before it is written.

## Documents as requirements

An upload requirement takes a document on its own, outside any form sitting, and takes it again when
the resolver asks for the same upload again. The upload validation and storage `form_engine` already
does should be reused, not copied. Every version a reviewer has seen is kept.

The applicant can see their own earlier uploads, including those on superseded requirements, in a
collapsed history with the reason each was not accepted. It answers "did you get my document?" before
they have to email anyone.

Medical and identity documents get the same storage, retention and access rules as every other
upload. No special handling.

## Who reviews: organisation roles

Reviewers are people holding an organisation role, not Django staff. Several people can hold that
role, and any one of them can accept a requirement or approve an application.

A `CourseApplication` has no organisation today: the applicant is not a `Learner` yet, and a course is
not owned by an organisation. So:

- a new application belongs to the site's default organisation (`get_default_organisation`)
- a person with access to more than one organisation can move an application to another of those
  organisations. Moving it is an action that goes in the audit log.

When an application is approved and the learner is registered, the `Learner` is made in the
application's organisation, through `ensure_learner`.

## Asking for help

From any requirement, and from any page of an application form, the applicant can ask for a person to
contact them. A short contact form takes their name, phone number, a good time to call, and their
question. The request records where they were when they asked: the application, and the requirement
or form page.

The request goes to the reviewers of the application's organisation. The `notifications` skill decides
whether that is an in-app notification. A signal or webhook lets a deployment push requests into its
own CRM.

Anonymous applicants have no `User`, so this cannot be built on `comms` direct messaging. A request
hangs off the `CourseApplication`, which already covers both kinds of applicant.

## Recommendations from application answers

The way of studying an applicant chooses changes which courses we recommend. Those recommendations are
`RecommendedCourse` rows made by a pluggable producer, the same seam as the resolver. FLS does not grow
a second recommendation mechanism.

## What stays in the downstream project

- The qualification types and the rules mapping them to exams and medicals, as a requirement resolver
- The lists of exam centres and medical examiners, and the "nearest to you" ranking
- The study-mode-to-course mapping
- Its own document types
- Its wording, through template overrides

The rule for what is content and what is Python: anything an author changes per course without a
deploy is content (forms, branching, a course's fixed requirement list, document type descriptions).
Anything computed from applicant data with domain rules is Python behind an FLS seam.

## Order

This is too big for one spec. `/sdd:roadmap multi-step-course-applications` should cut it. The order
already looks like this:

1. Application review states and organisation-role reviewers, from `application-review-ui`, revised
   for the decisions here, including the default organisation and moving between organisations
2. `form-engine-branch-logic`, already ready to start
3. Application requirements and the requirement resolver, with the fixed-list resolver, and
   reopening a completed form sitting
4. Upload requirements outside form sittings, with rejection reasons, choices and upload history
5. Asking for help
6. Recommendations from application answers

`file-scanning` should land before a deployment takes medical or identity documents in production.

## Out of scope

- An outside system (an exam body, a booking service) reporting that a step is done. For now an
  applicant proves it with an upload or a reviewer marks it done.
- A provider list and distance ranking in FLS, until a second deployment needs them.
- More than one sign-off on a requirement or an application.
