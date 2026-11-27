# Answers: sacaa-compliance-assessment-controls-7-course-restart

Asked by `/sdd:start` before the spec was written.

- Q: Which data shape do the restart and test-out's renewals share: option B (runs on `CourseProgress` under one registration) or option C (a registration chain)? → A: Option C, a registration chain. The idea recommended B; the owner overrode it. (asked up front)
- Q: Under option B, may a run's previous-run link cross registrations? → A: Not applicable. Option B is not used: a registration is associated with one course run. (asked up front)
- Q: When can staff restart a learner's course from the learner page? → A: Only on an active registration, whatever state the current run is in: untouched, in progress or complete. (asked up front)
- Q: Can a mistaken restart be undone? → A: No. A restart is final and audited; the earlier run stays readable. (asked up front)
- Q: How is a learner who holds the course through a cohort restarted, given a cohort registration is shared by the whole cohort? → A: The restart mints an individual `LearnerCourseRegistration` for that learner, linked back to the cohort registration. The learner's run under the cohort grant is closed for that learner only. (asked up front)
- Q: What state does the earlier registration take after a restart? → A: A new "superseded" state, distinct from `is_active`. It records the registration that superseded it, readers skip it, and reactivate refuses it. (asked up front)
- Q: What does the new registration get from the earlier registration's deadline settings? → A: It copies the registration-level deadline config, so the deadline rule carries over and only the clock restarts. (asked up front)
- Q: What do the cohort's pages (educator matrix, cohort report) show for a cohort learner who was restarted onto an individual registration? → A: They follow the chain to the learner's current run and label it as a restart. (asked up front)
- Q: Which webhook events does a restart send? → A: A single new `registration.restarted` event that carries the earlier and new registration ids and the reason. It sends no `registration.added` and no `registration.deactivated`. (asked up front)
- Q: A cohort run can't be superseded on its shared cohort registration. Where do the restart chain's back-link and the "closed for this learner" fact live? → A: The new `LearnerCourseRegistration` links to the earlier run's `CourseProgress`. That is one record per learner for both kinds of registration, so supersession is the same check for individual and cohort runs, and a renewal chains the same way. (asked while the research ran)
- Q: A learner restarted onto an individual registration is later moved into, or added to, another cohort that also holds the course. Which registration is their current run? → A: The restart registration stays current. An individual registration made by a restart beats any cohort registration for that course. (asked while the research ran)
