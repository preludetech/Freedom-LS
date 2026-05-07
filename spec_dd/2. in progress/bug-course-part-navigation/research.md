# Research — course part navigation bugs

Research for the bugs described in `idea.md`. No external URLs were consulted; this is a codebase-internal investigation.

## Where the navigation lives

- Navigation URLs are computed in `freedom_ls/student_interface/views.py` in `view_course_item` (around lines 140–210).
- The "Previous" button is rendered in `freedom_ls/student_interface/templates/student_interface/course_topic.html` (lines 27–30) — `{% if previous_url %}`.
- The flattened item list is built by `Course.children_flat()` in `freedom_ls/content_engine/models.py` (lines 168–179). Crucially, it **includes `CoursePart` entries themselves** alongside their children:

  ```python
  for child in self.children():
      flattened.append(child)            # CoursePart
      if isinstance(child, CoursePart):
          for part_child in child.children():
              flattened.append(part_child)
  ```

  So for the demo `functionality-demo-course-parts` course, the flat indices look like:

  | index | item kind        |
  |-------|------------------|
  | 1     | CoursePart "Getting Started" |
  | 2     | First Topic of Part 1 (bug 1 URL) |
  | 3     | …more children of Part 1 |
  | 4     | CoursePart "Core Concepts" |
  | 5     | "Key Ideas" Topic — first child of Part 2 (bug 2 URL) |
  | …     | … |

## Why each bug occurs

### Bug 1 — extra "Previous" on the very first content item

In `view_course_item`:

```python
previous_url = None
if index > 1:
    previous_url = reverse("student_interface:view_course_item",
                           kwargs={"course_slug": course_slug, "index": index - 1})
```

At `index=2`, `index > 1` is `True`, so `previous_url` is set to point at `index=1`. But `index=1` is the first `CoursePart`, which is not directly viewable. The view's `CoursePart` branch:

```python
if isinstance(current_item, CoursePart):
    if next_url:
        return redirect(next_url)   # forward!
```

…so clicking "Previous" silently bounces the user forward to the same page they were already on. The button should not be rendered at all.

### Bug 2 — broken "Previous" on the first item of subsequent parts

At `index=5` (first topic of part 2), `previous_url` is computed as `index=4`, which is the **CoursePart "Core Concepts" header itself**. Clicking it loads the CoursePart view, which redirects forward to `index=5` again (the same `next_url` rule). Net effect: nothing happens.

The expected behaviour from the idea file: the Previous button on the first item of a subsequent part should land the user on the **last item of the previous part** — i.e. it should skip past the CoursePart marker entirely.

## Fix shape (high level)

Two clean options:

1. **Skip CourseParts when computing prev/next URLs.** In `view_course_item`, walk backwards (and forwards) past any `CoursePart` items to find the nearest viewable index. If no such index exists, set `previous_url = None` so the button isn't rendered.
2. **Filter CourseParts out of the flattened list used for navigation** (introduce `Course.children_flat_viewable()` or similar) and only navigate over that. This is cleaner long-term but changes index semantics, so it would need careful migration of existing URLs/bookmarks. **Not recommended for a bugfix.**

Option 1 is the lower-risk, smaller-blast-radius fix and matches existing CoursePart redirect semantics.

## Test surface (TDD)

The bug spec mandates TDD. New tests should cover, at minimum:

- `view_course_item` at the first viewable index after a leading CoursePart → context contains `previous_url is None`, template does not render Previous button.
- `view_course_item` at the first viewable index of a non-first CoursePart → `previous_url` resolves to the **last viewable index of the previous part** (not to the CoursePart header), and following that URL renders successfully.
- `view_course_item` at a middle index inside a part → `previous_url` still works (regression guard).
- `view_course_item` at the very last viewable index → `next_url is None` (regression guard for the analogous forward edge case, since the same skip logic likely applies).

Demo data already in `demo_content/functionality_demo_course_parts/` (3 parts: Getting Started, Core Concepts, Wrapping Up) is suitable test fixture material.

## Out of scope / questions for the user

- Should the **Next** button on the *last* item of a part also skip the next CoursePart marker? Today, the CoursePart redirect-forward logic papers over this in practice (clicking Next lands on the CoursePart, which immediately redirects to the first child of the next part), so the user-visible behaviour is correct — but it costs an extra HTTP redirect. Worth confirming whether the fix should symmetrically clean up Next as well, or strictly target the documented Previous bugs.
- Should CoursePart pages remain reachable by direct URL at all (currently they always redirect forward)? Likely yes (no change), but worth confirming.

## References

No external references were used — investigation was confined to the worktree at `/home/sheena/workspace/lms/freedom-ls-worktrees/bug-course-part-navigation/`.
