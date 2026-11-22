# Answers: sacaa-compliance-content-versions-and-access-1-content-save-safety

Asked by `/sdd:start` before the spec was written.

- Q: What is a path listed under `ignore:` in `.fls-content.yaml` exempt from? → A: Only from being validated or saved as FLS content. It is not exempt from the git clean-tree check, so an uncommitted change to an ignored file still fails the save. (asked up front)
- Q: Where do content_save and content_validate find `.fls-content.yaml`, and what are `ignore` entries relative to? → A: The git repo root that holds each source path. Entries are relative to that root, and it is the same file the fls-content offline validator already reads. (asked up front)
- Q: What happens when a source path's repo has no `.fls-content.yaml`? → A: content_save and content_validate treat it as an empty ignore list. The fls-content offline validator keeps requiring the file. For context: only the fls-content plugin (validator and format-content skills) reads the file today; Django takes admonition and access types from settings. (asked up front, with a follow-up)
- Q: Should content_validate and the offline fls-content validator also skip ignored paths? → A: Yes. content_save, content_validate and the offline validator all honour the `ignore:` list. This is a narrow exception to the idea's "Changing what `content_validate` checks" out-of-scope line. (asked up front)
- Q: Design access? → A: Not asked: the spec directory has no `design_prompt.md`. (n/a)
