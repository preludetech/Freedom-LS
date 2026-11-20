# Recommendations from application answers

Spec 10 of 12 in the Multi-step course applications effort. Read the "Multi-step course applications" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A deployment supplies a producer that reads an application's answers and names the courses to recommend to the applicant. The courses appear as `RecommendedCourse` rows, so learners see them in the existing "Recommended courses" section of the dashboard. FLS ships a default producer that recommends nothing.

## Why

The way of studying an applicant picks (for example e-learning or in-person) changes which courses suit them. The deployment knows the mapping; FLS has to carry it into the recommendations learners already see, without growing a second recommendation mechanism.

## What is settled

- Recommendations stay `RecommendedCourse` rows. FLS grows no second recommendation mechanism, and `course_recommendations` gains no source field and no new dependency.
- The producer is a new setting-named class in the house pluggable pattern: a loader, a decision value listing courses, a boot check and a conformance probe a downstream project imports. It takes the application and returns the courses to recommend. It reads the answers from the application's form progress. Its input is the application as a whole, so it can read more as the application grows.
- FLS's default producer recommends nothing, so an install works out of the box.
- A provenance table in `course_applications` records which `RecommendedCourse` rows the producer made. When an answer changes, the producer's old rows go and its new ones appear; staff-made rows and rule-made rows for the same user stay. A row shared with another maker survives until its last holder lets go, the same many-owners rule registration rules follow.
- The producer never re-adds a course the user is registered for.
- Rows exist only once the application has a user, because `RecommendedCourse` is keyed on `User`. An anonymous application gets no rows until it gains a user. The recompute therefore runs on answer changes, on the sitting completing, and when an anonymous application gains a user through the claim.
- No `Learner` is needed. Course visibility is still filtered by the existing dashboard section.
- There is no new applicant-page UI. Learners see recommendations only in the existing dashboard section.
- The study-mode-to-course mapping stays in the downstream project. The demo or the tests show a producer that maps a study-mode answer to courses, to prove the seam.

## Open until the spec

- Whether the producer also re-runs on reviewer verdicts once `multi-step-course-applications-6-reviewer-verdicts` exists.
- The trigger mechanism: a task after commit, as registration rules do, or inline.

## Out of scope

- Recommendations for applicants with no user, and any applicant-page display of them.
- Making `RecommendedCourse.user` nullable.
- Ranking, reasons or expiry on recommendations.
- Any real study-mode mapping in FLS.

## Resources

- `spec_dd/1. next/multi-step-course-applications/research_help_and_recommendations.md`, sections 5 and 6.
- `spec_dd/1. next/multi-step-course-applications-5-requirements-and-resolver/research_requirements_and_forms.md`, section 1 (the house pluggable pattern).
- `spec_dd/1. next/multi-step-course-applications/idea.md`, "Recommendations from application answers" and "What stays in the downstream project".
