# Notes from the spec 1 code review

The code review of spec 1 (PR 178) found two row-visibility gaps on the course detail page. They were left for this spec because "lists use the visibility helpers to filter rows" is this spec's job. Spec 6 rebuilds the courses section too, so whichever of the two lands first should close them.

On `main` before spec 1, neither table filtered by organisation at all. Spec 1 narrowed both to the current organisation. What is still missing is the cohort scope for cohort-scoped educators.

## Gaps

- **`CourseLearnerRegistrationDataTable.get_queryset`** (`freedom_ls/educator_interface/views.py`, the "Direct Registrations" panel) filters by `learner__organisation` only. An instructor or TA whose only grant is on one cohort can open any course (`CourseConfig` authorises every course) and see the first name, last name and email of every learner in the organisation who is directly registered to it. Filter by `learners_visible_to(request.user, organisation)`.
- **`CourseCohortRegistrationDataTable.get_queryset`** (same file, the "Cohort Registrations" panel) filters by `cohort__organisation` only, so it names and links cohorts the educator has no grant on. Filter by `cohorts_visible_to(request.user, organisation)`.

The matrix test should cover both panels, so this can't come back.

## Related framework guarantee

`ObjectViewConfig.get_instance_view` now runs `check_request` before the host's `get_object`. As a result, every section type (list, object, base) fails closed on an anonymous request, or on one missing a `required_request_attrs` attribute, before any host code runs. The permission hooks this spec implements can rely on that.
