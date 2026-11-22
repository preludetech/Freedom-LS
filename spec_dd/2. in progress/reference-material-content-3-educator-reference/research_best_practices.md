# Best practices: educator Reference panel

Note: written from established knowledge of the cited sources; URLs were not re-fetched this session.

## 1. Supplementary material apart from the sequenced curriculum

- Mainstream LMSs keep the sequenced path (modules, lessons, progress) apart from reference or resource libraries. Canvas has Modules vs Files. Moodle has course sections vs a Resources block. Open edX has the course outline vs Course Handouts and Updates. Instructors see both, but reference items carry no completion or deadline state.
- Practical rule: reference never changes the path's numbering, progress or counts. It is its own list with its own heading. This matches the settled decision (separate panel, no deadline or progress columns, separate footer count).
- Keep the same row shape (group row, child topic rows, a "Preview" action). Educators then learn one pattern, and the same table component can render both.
- Refs:
  - https://learn.microsoft.com/en-us/style-guide/ (consistent labels)
  - https://www.nngroup.com/articles/consistency-and-standards/
  - https://docs.openedx.org/en/latest/educators/ (course outline vs handouts)

## 2. Empty state for a secondary panel

- Guidance (NN/g, Material, Carbon): an empty state is for a primary area where the user expects content or can act. A secondary, optional section should not shout "nothing here".
- Here, most courses have no reference. The educator cannot add reference from this interface (editing is out of scope), so there is no call to action. Showing an empty panel on every course would be noise with nothing to do.
- Recommendation for the open question: **hide the panel entirely when the course has no reference parts.** This is the likelier choice the idea names.
- The exception is the withheld case. If `preview_available` is false but reference parts exist, show the panel with the same "Content preview isn't shared with your organisation." note. Hiding it would leak nothing, but it would make the two panels behave differently.
- A reference part with no topics keeps the group empty note, as a learning-path part does.
- Refs:
  - https://www.nngroup.com/articles/empty-state-interface-design/
  - https://carbondesignsystem.com/patterns/empty-states-pattern/
  - https://m3.material.io/foundations/content-design/overview

## 3. Numbering separate outlines

- Numbering restarts per outline (`1.`, `1.1`). This is the convention in multi-part documents: appendices restart as "A.1", and "Part II" restarts its chapters.
- Compute numbers per section from the section's own ordered list. Never keep a running counter shared across sections.
- Only the order matters, so use `forloop.counter` (and a nested counter) inside each section's loop. Don't derive numbers from stored positions or database IDs, which can have gaps.
- Test it. A course with 2 path parts and 1 reference part should render the reference part as `1.`, not `3.`.
- Ref: https://docs.djangoproject.com/en/stable/ref/templates/builtins/#for (`forloop.counter`)

## 4. Sharing authorization between sibling views and panels

Drift happens when the gate is written twice. Patterns that prevent it:

- **One function or queryset owns the rule.** Put the `preview_available` decision and the organisation-scoped course lookup in one helper. A mixin or a small function works. Both the panel context builder and `PreviewContentAction` call it. The Django docs describe mixins and shared `get_queryset` as the supported way to share view behaviour: https://docs.djangoproject.com/en/stable/topics/class-based-views/mixins/
- **Compute once, pass the result.** The course-page context computes `preview_available` one time and hands the same boolean to both panels. A panel never recomputes it.
- **One outline template or cotton component** takes `sections` (rows plus a numbering scope) and `preview_available`. The "Preview" button and the withheld note then live in one place. Cotton components and includes are the DRY mechanism: https://docs.djangoproject.com/en/stable/ref/templates/language/#include
- **Scope lookups through the course.** The widened lookup should be a queryset rooted at the course (`course.reference_parts`, then topics under them), not `Part.objects.get(pk=...)`. This makes "a part shared by several courses is reachable only through a course that lists it" structural rather than a check someone could forget. See https://docs.djangoproject.com/en/stable/topics/db/queries/#retrieving-a-single-object-with-get and `get_object_or_404` with a scoped queryset: https://docs.djangoproject.com/en/stable/topics/http/shortcuts/#get-object-or-404
- **Fail closed, return 404 not 403** for out-of-scope objects, so existence is not leaked. OWASP guidance on IDOR: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- **Single lookup path.** Prefer one function that returns the union (learning path plus own reference), with the source labelled. Two parallel lookups invite divergence.

## 5. Tests that guard object-level isolation

- Test the 404 for each out-of-scope case, not only the happy path. Use the same fixture for each and assert `404`:
  1. a reference topic of another course
  2. a reference part shared by two courses, requested through a course that does not list it
  3. a reference topic in an organisation that holds only a registration (withheld)
  4. a reference topic in another site (site-aware manager)
  5. a collection item from another course (the existing 404 must stay)
- Pair each negative test with a positive control. The same URL as the in-scope educator returns 200 with the "(Preview)" title and the "Topic" chip. A test that only checks 404 passes if the URL is simply wrong.
- Also test the panel, not just the URL. When withheld, the panel shows the note and has no "Preview" buttons (`assertNotContains` on the preview URL).
- Parametrise the withholding test over both panels, so a future change to one fails the other's test.
- Assert that the "Course content" footer count excludes reference rows, and that the Reference footer counts its own.
- Refs:
  - https://docs.pytest.org/en/stable/how-to/parametrize.html
  - https://docs.djangoproject.com/en/stable/topics/testing/tools/#django.test.SimpleTestCase.assertNotContains

## Recommended decisions for the spec's open questions

1. No reference parts: render no panel. Reference parts exist but the preview is withheld: render the panel with the withheld note.
2. Share one gate: compute `preview_available` once in the course-page context and pass it to a single shared outline component. The preview action uses the same scoped-course helper.
3. Empty-learning-path wording: leave it to spec 4. Nothing here blocks it, as long as the panel visibility depends on reference parts only, not on the learning path.

status: ok
