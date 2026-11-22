# Answers: reference-material-content-1-authoring

Asked by `/sdd:start` before the spec was written.

- Q: When `content_save` sees a part newly listed under `reference:`, how should the cleanup of that course's old course→part collection item, its deadline overrides and its part-placement due dates behave? → A: Delete and report: delete in the same atomic load and name every removed row in the save output, as the idea says (asked up front)
- Q: Once a part leaves the learning path, should `content_save` recompute stored `CourseProgress.progress_percentage` and `completed_time` for learners with progress on that course? → A: No. Leave the stored values as they are, the same as for any content change today; they refresh on the learner's next activity, and this spec adds no recompute (asked up front)
