# Idea: a signed-in learner can "apply" to a free course and gets an application that never resolves

## The bug

Source: this downstream project's mega QA run on 2026-10-28 (DISC-2).

1. Log in as any learner.
2. Open `/applications/apply/introduction-to-the-drone-industry/`. The course's `access_type` is
   `free`.
3. Click "Submit application".

Expected: 404, or a redirect to the course detail page.

Actual: the page says "You are about to submit an application for Introduction to the Drone
Industry. A reviewer will consider your application...". Submitting creates a `CourseApplication`.
The dashboard then shows "Your applications: Introduction to the Drone Industry, Pending review"
for good, while the course page still offers "Enrol for free".

Only reachable by typing the URL, but the stray panel row never goes away.

## Cause

`apply` (`freedom_ls/course_applications/views.py:121-176`) checks visibility and coming-soon but
never checks that the course is application-gated. A course with no `application_form` falls
through to the confirm page, and the POST calls `_start_application` (`:165-170`).

The anonymous path already has the check. `_anonymous_applications_allowed` (`:419-426`) returns
true only for `APPLICATION_GATED`, and `_anonymous_apply` and `applicant_details` use it
(`:439`, `:575`). The signed-in path doesn't.

## Suggested fix

Apply the same access-type check to signed-in learners, after the existing-application
short-circuit (so an applicant whose course later changed type can still reach their record).
Redirect to the course detail page. Add a view test for a free course.

## Downstream workaround

None.
