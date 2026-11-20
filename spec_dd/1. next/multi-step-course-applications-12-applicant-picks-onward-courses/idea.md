# Applicants pick onward courses

Spec 12 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

An author can let applicants for an intake course pick the onward courses they want. The applicant
picks on their status page and can change the picks later. Reviewers see the picks beside each onward
course in the registrations section and still make every registration themselves.

## Why

Who chooses the courses and the organisation differs by deployment and by course. Sometimes a reviewer
decides from the applicant's answers. Sometimes the applicant already knows which organisation is
near them and which courses they want. Without a place to say so, they put it in a free-text answer
and the reviewer matches it to the onward list by eye.

## What is settled

- The switch is authored on the intake course's content and is off by default. With it off only the
  reviewer chooses, as `multi-step-course-applications-11-intake-courses` leaves it.
- With it on, an applicant with a claimed account sees the intake course's onward courses on their
  status page and picks any number of them. Each shows the course and the organisation.
- Picks are open from the moment the application exists, before and after approval.
- The applicant can add or remove a pick at any time. A pick for a course they are already registered
  for cannot be removed, and the page shows that course as registered.
- A pick is a request. It registers nobody and holds nothing back: an application with no picks can
  be approved, and a reviewer can register the applicant for an onward course they did not pick.
- The registrations section marks each onward course the applicant picked, so a reviewer sees the
  request in the place they act on it.
- Picks are not audited, in line with the applicant's own submit and withdraw. A reviewer's
  registration is audited as before.
- No notification is raised when an applicant picks or changes a pick.
- The demo intake course turns the switch on.

## Open until the spec

- The content key for the switch.
- Whether picks made before the application is submitted show to the applicant as part of the
  application form flow, or only on the status page.

## Out of scope

- Registering an applicant because they picked a course.
- Limiting how many onward courses an applicant may pick, or making some picks exclude others.
- Picks for an unclaimed applicant.
- Ranking onward courses or suggesting one, for example by distance.

## Resources

- `spec_dd/1. next/multi-step-course-applications-11-intake-courses/idea.md`: intake courses, onward
  courses and the registrations section.
- `spec_dd/1. next/multi-step-course-applications/intake_courses_case.md`.
- `spec_dd/1. next/multi-step-course-applications-1-review-states/idea.md`: the status page and what
  is audited.
- `claude_plugins/fls-dev/skills/notifications/SKILL.md`.
