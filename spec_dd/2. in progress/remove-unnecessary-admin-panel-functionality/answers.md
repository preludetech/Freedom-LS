# Answers: remove-unnecessary-admin-panel-functionality

Asked by `/sdd:start` before the spec was written.

- Q: Should the form_engine form-definition admins (Form, FormPage, FormQuestion, FormContent, QuestionOption) go along with the content engine admin? → A: They must not be editable or deletable in the admin; form answers and attempts should stay visible, read-only. (asked up front)
- Q: What happens to the learner progress admin (TopicProgress, CourseProgress, CourseFormAttempt) and the form answer admin (FormProgress, QuestionAnswer, QuestionAnswerFile)? → A: Remove the learner management admin. Leave progress for now, read-only. (asked up front)
- Q: When Learner, Cohort and the course-registration admins go, what happens to the LearnerAdmin seams (hr_attributes and learner_progress inlines, LEARNER_SUMMARIES) and the Organisation admin's cohort and learner inlines and Learner changelist link? → A: Remove all of them. (asked up front)
- Q: Should a downstream project be able to turn the removed admins back on? → A: No. Remove them outright; a project that wants one registers its own admin. (asked up front)
- Q: Should form definitions disappear from the admin entirely or stay as read-only pages? → A: Remove them entirely, the same as content_engine. (asked up front)
- Q: Should the read-only progress and attempt admins also block delete and bulk delete? → A: Yes. No add, change or delete. (asked up front)
