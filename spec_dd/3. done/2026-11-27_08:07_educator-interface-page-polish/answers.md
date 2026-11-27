# Answers: educator-interface-page-polish

Asked by `/sdd:start` before the spec was written.

- Q: The idea says items 1, 2 and 7 need a design, but there is no `design_prompt.md`. How does the spec settle their layout? → A: The spec describes the layout in words, with no Claude Design step. (asked up front)
- Q: Learner Courses tab (item 2): a simple table, or whitespace-separated rows? → A: A simple table. (asked up front)
- Q: Learners list Courses column (item 1): which courses show first before "+N more" (cap 3)? → A: In-progress courses first, most recently active first. (asked up front)
- Q: Page-header and dialog-footer buttons on a 375px phone (item 7): how do they take less room? → A: A smaller visual button with a 44px hit area, not an overflow menu. (asked up front)
- Q: Should flagged courses come before the in-progress ordering in the Learners Courses column? → A: Yes: flagged first, then in progress, most recently active first. (asked while research ran)
- Q: Where do a course's completed items and quiz attempts go once the Courses tab is a table? → A: One row per course in the table, then a section per course below it for completed items and quiz attempts. (asked while research ran)
- Q: Drop the no-activity flag reason on the Courses tab only, or everywhere it repeats the badge? → A: Everywhere the reason only repeats the badge; report downloads keep it. (asked while research ran)
- Q: Page-header actions are already small; what does item 7 change? → A: Dialog footer only; QA confirms the page header at 375px. (asked while research ran)
- Q: Flagged-first ordering cannot reuse the per-learner gather at constant query count. How? → A: A new page-wide gather in `freedom_ls/reports`, run from a `LearnerDataTable.get_rows` override. (asked at spec review)
- Q: Apply the recommended option for every other spec-review judgement call? → A: Yes. (asked at spec review)
