Fix these bugs using TDD.

# 1. "Previous" button is present when we are looking at the first item of the first course part

If there is a course with multiple course parts and we visit the first item within the first part then there is a "previous" button. There should not be.

http://127.0.0.1:8000/courses/functionality-demo-course-parts/2/
This links to the first topic in the course, there is nothing prior. but there is a "previous" button that does nothing.

# 2. "Previous" button is present but broken when looking at the first item of subsequent course parts

Eg:
http://127.0.0.1:8000/courses/functionality-demo-course-parts/5/

Here we are looking at the "Key Ideas" topic from the demo_content.

The previous button is present, but it doesn't do anything when clicked. It should redirect to the last thing from the previous course part.

# Context from research

See `research.md` in this directory for the full investigation. Summary:

- Both bugs live in `view_course_item` in `freedom_ls/student_interface/views.py`. The "Previous" template lives in `student_interface/templates/student_interface/course_topic.html`.
- Root cause: `Course.children_flat()` (in `content_engine/models.py`) interleaves `CoursePart` markers with their child items. The previous URL is computed as `index - 1`, which can point at a `CoursePart`. CourseParts are not directly viewable — visiting one redirects **forward** to the next item — so "Previous" at the first child of any part either bounces the user forward (loop) or appears to do nothing.
- Recommended fix shape (low risk): when computing `previous_url` (and by symmetry, `next_url`), skip over any `CoursePart` entries. If no viewable predecessor exists, leave `previous_url = None` so the button is not rendered. Do **not** change the index scheme of `children_flat()` — existing URLs and bookmarks rely on it.

# Open questions

- The "Next" button has the same theoretical edge case (last item of a part → next index is a CoursePart marker → CoursePart view redirects forward to the first child of the next part). The end-user behaviour is currently correct but costs an extra redirect hop. **Question for the user:** should the fix symmetrically clean up Next as well, or strictly target the documented Previous bugs? Default: clean up Next for symmetry, since the skip logic is the same code path.

# Testing

Per project convention, fix via TDD. Tests should cover:

- First viewable index after a leading CoursePart: `previous_url` is `None`; template does not render the Previous button.
- First viewable index of a non-first CoursePart: `previous_url` resolves to the **last viewable index of the previous part** (skipping the CoursePart marker), and that URL renders the expected topic/form.
- Middle index inside a part: Previous still works (regression guard).
- Last viewable index of the course: `next_url` is `None` (regression guard).

The existing `demo_content/functionality_demo_course_parts/` fixture (3 parts) is suitable test data.
