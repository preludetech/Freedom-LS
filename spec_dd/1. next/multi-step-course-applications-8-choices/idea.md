# Requirement choices

Spec 8 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

The resolver can offer a choice: a group of requirements where any one being accepted is enough ("upload a certified copy of your licence, or book exam X"). The applicant sees the options side by side and works on whichever suits them. Applicants can switch between options until one is accepted, and an accepted option settles the choice.

## Why

Forcing an exam on someone who uploaded the wrong file costs them weeks. Forcing a re-upload on someone who does not have the document leaves them stuck. The applicant usually knows which of the two is true, so the application lets them say.

## What is settled

- A choice is a group of requirements where any one being accepted is enough.
- The resolver's decision value can group wanted requirements into a choice. The fixed-list resolver's content format can express a choice too.
- Choices are one level deep. A choice inside a choice is refused at content load and by the decision value itself.
- The applicant sees the options side by side, in plain words, and can switch between them until one is accepted. Work already done on an option they switched away from is kept, not discarded.
- The first option accepted satisfies the choice. The remaining options become superseded through the reconcile step, and superseded requirements are kept like any other.
- A choice holds back whatever its options hold back (approval, registration or nothing).
- Reviewers see a choice as a group on the review screen, not as unrelated requirements.
- A changed answer behaves as it does for any requirement: the resolver re-runs and the choice follows.

## Open until the spec

- Whether the applicant must pick an option before working on it, or simply starts one.
- What a choice means when its options hold back different things. Default: refused, at content load and by the decision value.

## Out of scope

- Choices inside choices.
- Requirement kinds and upload handling, which belong to their own siblings.

## Resources

- `spec_dd/1. next/multi-step-course-applications/idea.md`, sections "No workflow graph" and "Choices".
- `spec_dd/1. next/multi-step-course-applications-5-requirements-and-resolver/research_requirements_and_forms.md`, sections 1 (the pluggable-resolver pattern and decision value) and 6 (where choices sit in the split).
