# Reopening a submitted application form

Spec 4 of 10 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A signed-in applicant who has submitted their application form can reopen it from the application status page. Their earlier answers are filled in, they change what was wrong, and they submit again through check-your-answers as before. This works while the application is submitted. Once it is approved, rejected or withdrawn, the form stays closed.

To make that possible, `form_engine` gains the mechanism to reopen a completed `FormProgress`. The application views are the first and only code that uses it.

## Why

People notice their own mistakes after they submit. Today a submitted form is final, so fixing one means emailing a reviewer. The later requirements work reopens forms the same way, so the mechanism has to exist and be proven on the application form first.

## What is settled

- `form_engine` provides the mechanism to reopen a completed sitting. It does not decide when that is allowed. The owner of the sitting decides, by being the only code that calls it. There is no flag on `FormProgress`. The reopen refuses a sitting that is not completed.
- A quiz in a course never reopens. No quiz view calls it, and retakes keep their own path through `CourseFormAttempt`.
- Answers on the current path survive a reopen. Off-path answers that completion deleted stay deleted, so a changed gate answer opens blank questions, as in a live sitting. `furthest_page_reached` stays as it is.
- Completing a reopened sitting runs the whole completion again and sends the completion signal again. Listeners of that signal can tell a re-completion from a first completion.
- For an application, the applicant reopens from the status page, only while the application is submitted. The application stays submitted while the form is open. Reviewers see that the form is being edited, and the spec decides how that is shown. Re-submitting goes through check-your-answers as before.
- Each reopen writes an `audit_log` entry. It never carries the applicant's name.
- Only a claimed (signed-in) applicant can reopen. An unclaimed application's form pages stay closed after submit, as they are today.
- This spec covers only the application form. `multi-step-course-applications-5-requirements-and-resolver` extends reopening to each form requirement and makes reopening an accepted form put it back to submitted.
- It needs the states and withdraw from `multi-step-course-applications-1-review-states`, because the rule is "until approved".

## Open until the spec

- Whether a reviewer can approve or reject while the form is reopened. The default is that both are refused until the applicant submits again.
- What the reviewer sees while the form is reopened, and whether the earlier submitted answers stay visible beside the edits.

## Out of scope

- Reopening for an unclaimed applicant, or any change to how anonymous sittings are reached.
- Reopening forms that are requirements, and anything that depends on requirement status.
- Reopening a quiz or survey sitting in a course.
- Reviewers asking an applicant to redo a form.

## Resources

- `spec_dd/1. next/multi-step-course-applications-5-requirements-and-resolver/research_requirements_and_forms.md`, sections 3, 4 and 6.
- `spec_dd/1. next/multi-step-course-applications/research_review_foundations.md`, section 7.
- `spec_dd/1. next/multi-step-course-applications/idea.md`, "Reopening a completed form".
