# Learner and cohort administration flows

Type: grilling
Status: open
Blocked by: 05

## Question

How do the learner and cohort capabilities behave, in terms of the current models (`Learner`, `ensure_learner`, `CohortMembership`, `LearnerCourseRegistration`, `CohortCourseRegistration`, `Cohort`)? Cover:

- adding a learner to an organisation (new account vs existing `User`, first-login and password setup, resending invites);
- removing and deactivating a learner vs deleting one (GDPR);
- cohort membership add, remove and move within an organisation, and what the educator is told about access and progress (`CourseProgress` is never retired by these, per `better_course_progress_tracking`);
- registering and unregistering cohorts and individual learners for courses;
- cohort create, deactivate and delete;
- CSV import (preview, matching, errors) and multi-select bulk actions;
- webhook events for access changes.
