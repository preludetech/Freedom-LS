# The case behind intake courses

A second case for the effort, added after the cut. `multi-step-course-applications-11-intake-courses`
and `multi-step-course-applications-12-applicant-picks-onward-courses` build it.

## The case

A deployment takes applications centrally and works with partner organisations that deliver the
courses. Each partner has its own version of the same courses, so "the remote pilot course" is a
different `Course` at each `Organisation`.

An applicant applies for something broad, such as "become a drone pilot", and goes through steps
common to every applicant. After that they are registered for one or more real courses. Which ones
depends on their answers. Two courses may be at the same partner or at different ones.

Three things complicate it:

- **Bundles.** Applying for several courses at once can earn a discount, so one application may cover
  more than one course.
- **Order.** A learner registered for two courses may not be allowed to start the second until they
  have qualified from the first.
- **The partner's say.** Some partners take whoever is sent. Others want to agree first, and may
  refuse, in which case the learner goes to a different partner.

## The decision

A reviewer handles all three by hand. They read the application, talk to the partner the way people
do, and register the learner by clicking. FLS does not model a partner's agreement, a course order or
a discount.

| Need | How it is met |
| --- | --- |
| Apply for something that is not one course | An intake course |
| Say where applicants may end up | The intake course's onward courses, in content |
| Several courses, at one partner or several | The reviewer registers each onward course separately |
| The second course waits for the first | The reviewer registers it later |
| A partner must agree | The reviewer asks, then registers |
| A partner refuses | The reviewer registers at another partner, deactivating the first registration if one was made |
| A bundle price | The intake course's own price. Nothing is charged or discounted by FLS |
| The applicant chooses, or the reviewer does | A content switch on the intake course |

A deployment that later wants any of this automated has the seams the effort already defines: the
requirement resolver and the approval outcome.
