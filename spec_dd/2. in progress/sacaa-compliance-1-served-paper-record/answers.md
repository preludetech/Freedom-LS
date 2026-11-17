# Answers: sacaa-compliance-1-served-paper-record

Asked by `/sdd:start` before the spec was written.

- Q: An attempt in flight at deploy time (started, not completed) has no served paper record. What should happen to it? → A: Write the record from the authored order on the attempt's next request. The same lazy write covers new attempts wherever they are created (learner views, `course_applications`), and freezes the paper against later edits. (asked up front)
- Q: Should the educator form preview (`full_path`) and the admin answer groups follow the served record in this spec? → A: No. Leave both to `sacaa-compliance-4-attempt-review`. (asked up front)
- Q: A served page or option is later deleted from the live form. How should the attempt treat it? → A: Skip it on read. Navigation and scoring drop items that no longer exist, and `max_score` shrinks accordingly. No deletion is blocked. (asked up front)
- Q: After a learner completes a quiz, an educator deletes one of the questions the learner was served, so the results page's recomputed score differs from the stored one. Should the page show its "your score is out of date" notice? → A: No. Keep the stored mark. Stored scores are never rewritten, and deleting a served item never makes the stored mark look out of date; a question added after the attempt doesn't either, because it was never served. (asked during `/sdd:spec_from_idea` Step 2)
- Q: The main worktree had an untracked `spec_dd/1. next/content-widget-sayit-reveal/` directory from another process, failing the worktree's clean-tree check. Proceed? → A: Create the worktree anyway, leaving the directory untouched. (asked up front)
