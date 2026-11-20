# Intake courses

Spec 11 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An author marks a course as an intake course: people apply for it and nobody is ever registered for
it. Its content lists the onward courses its applicants may end up in, each a course at an
organisation. Once an application for an intake course is approved, a reviewer registers the applicant
for whichever onward courses they choose, one at a time, from the review screen. The applicant's
status page lists the courses they have been registered for.

## Why

Some deployments take applications in one place and deliver the courses somewhere else. An applicant
applies to "become a drone pilot". Which courses they take, and which organisation delivers each, is
worked out afterwards from their answers and from conversations with the organisations. Today an
application leads to one registration for the course applied for, so staff would approve the
application and then register the person by hand in each organisation, with nothing tying those
registrations to the application.

The deciding stays with people. A reviewer reads the application, talks to the organisations and
clicks. FLS records the result.

## What is settled

**Two new terms**, to be added to the glossary.

- An **intake course** is a course whose content marks it as one people apply for and are never
  registered for.
- An **onward course** is a course at an organisation that an intake course's content lists as
  somewhere its applicants may be registered. The list says what is possible. It never says an
  applicant will be registered for all of it, or any of it.

**Content**

- The intake mark and the onward course list are authored on the course. Each onward course names a
  course and an organisation, the organisation by slug as `organisations:` and `shared_with:` do.
- Content load rejects an onward course whose course or organisation does not exist, whose course is
  not open to that organisation, or that is itself an intake course. It rejects an onward list on a
  course that is not an intake course, and an intake course that takes no applications.
- A course can be an onward course of several intake courses.

**Nobody is registered for an intake course**

- Every path that makes a `LearnerCourseRegistration` or a `CohortCourseRegistration` refuses an
  intake course, with a message that names the reason.
- An intake course is left out of the places that list the courses a learner or a cohort can be
  registered for.
- FLS's default approval outcome registers nobody for an intake course. The approve dialog says that
  approval registers nothing and that the reviewer chooses the courses afterwards.

**Registering for onward courses**

- The review screen of an approved application for an intake course gains a registrations section. It
  lists every onward course, with the organisation, and shows which the applicant is registered for.
- Each onward course has a register action. It makes the applicant a `Learner` in that organisation
  through `ensure_learner` and registers them through `register_for_course`, with the reviewer as
  actor. The existing audit entries and webhooks cover it. No new notification is added, because the
  existing `course.registered` notification reaches the applicant.
- A reviewer may register for an onward course only when they hold the existing permission to register
  learners in that organisation. An onward course they may not register for is shown and cannot be
  clicked. There is no new way to gain that permission.
- Registrations are made one at a time, whenever the reviewer chooses, for as long as the application
  is approved. Registering for a second course weeks after the first is the ordinary case.
- Registering twice is harmless. An active registration stays as it is.
- Taking a learner off an onward course is the existing deactivate action in the educator interface.
  The registrations section then shows that registration as inactive and offers the others as before.
- FLS records which registrations were made from an application. The applicant's status page lists
  those courses with a link to each, and says so plainly when there are none yet.

**The demo.** A demo intake course in `demo_content/` lists onward courses at two organisations.

## Open until the spec

- The content keys for the intake mark and the onward list, and whether they sit in `access_config`.
- Which lists and pickers show an intake course today and need to leave it out. The spec finds them.
- Whether an intake course may hold content of its own, such as a welcome page, or must be empty.

## Out of scope

- Registering automatically from the applicant's answers, and any rule that picks an organisation.
- An organisation accepting or refusing a learner inside FLS. The reviewer asks them and acts on the
  answer.
- Enforcing an order between onward courses. The reviewer registers the second when the learner is
  ready for it.
- Payments, discounts and bundle prices. The price shown is the intake course's own.
- The applicant picking onward courses (`multi-step-course-applications-12-applicant-picks-onward-courses`).
- Holding registrations back for requirements (`multi-step-course-applications-6-reviewer-verdicts`).

## Resources

- `spec_dd/1. next/multi-step-course-applications/intake_courses_case.md`: the case behind this spec
  and what it leaves to a person.
- `spec_dd/1. next/multi-step-course-applications-3-approval-outcome/idea.md`: the outcome this spec
  changes for intake courses.
- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md`, section 2 ("What
  automatic registration on approval needs").
- `freedom_ls/learner_management/learner_actions.py` (`register_for_course`,
  `require_course_open_to`) and `freedom_ls/learner_management/utils.py` (`ensure_learner`).
- `demo_content/functionality_demo_organisation_course_northwind/course.md`: how content names
  organisations.
- Skills `fls-dev:domain-glossary`, `fls-dev:educator-interface` and `fls-dev:panel-framework`.
