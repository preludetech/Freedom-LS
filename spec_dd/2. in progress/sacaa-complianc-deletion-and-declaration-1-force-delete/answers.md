# Answers: sacaa-complianc-deletion-and-declaration-1-force-delete

Asked by `/sdd:start` before the spec was written.

- Q: How often should a User's last-active time be written? → A: Throttled: written only when the stored value is older than an interval, default 5 minutes, held in a setting (asked up front)
- Q: Should requests authenticated with an API key move the key owner's last-active time? → A: No; only session (browser) activity counts (asked up front)
- Q: Where does the superuser-only force delete appear in the Django admin for User and Learner? → A: Both: the changelist action list, and a "Force delete" button on the change page where the Delete button used to be (asked up front)
- Q: Should the last-active time also show on the educator interface's learner pages? → A: Yes, read-only on the educator learner detail page (asked up front)
- Q: A User being force deleted can hold Learner rows in several organisations; how is it audited? → A: One `user` entry with no organisation, plus one `learner` entry per organisation the user was a learner in (asked during the spec)
- Q: Can a superuser force delete their own account, or another superuser's? → A: No restriction: any account, their own included (asked during the spec)
- Q: Learner force delete leaves the quiz sittings (FormProgress, QuestionAnswer, answer files) that hang off the User; what happens to them? → A: Delete each FormProgress reached through the deleted CourseFormAttempt rows; sittings outside that organisation's course progress stay (asked during the spec)
- Q: The educator interface already has a course-based "Last active"; how does the new site-wide value show? → A: Replace: every educator "Last active" (learner quick view, learners table and its export) reads `User.last_active`, and the learner detail page gains the same row (asked during the spec)
- Q: The in-progress spec remove-unnecessary-admin-panel-functionality may remove LearnerAdmin; how does this spec handle it? → A: Build learner force delete on LearnerAdmin as the idea says, and record that the other spec must keep it or move it (asked during the spec)
