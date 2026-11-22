# Research: how reference implementations show non-sequenced resources to instructors

Scope: web search only (snippet-level). Canvas and Thinkific yielded nothing verified; do not rely on them.

## Findings

### Open edX
- Course Updates and Handouts live on their own Studio page, as separate panels (an Updates panel and a Handouts panel). They are not part of the section/subsection/unit outline. Handouts are uploaded files listed with a title and URL.
- The outline is previewed through Studio's Outline page, with "Preview" or "View Live" actions.
- Docs differ between releases, so check the release you target.
- https://docs.openedx.org/en/ulmo/educators/how-tos/communication/add_course_updates_handouts.html
- https://docs.openedx.org/en/ulmo/educators/concepts/communication/about_course_updates_handouts.html
- https://open-edx-building-and-running-a-course.readthedocs.io/en/latest/course_assets/handouts_updates.html
- https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/open-release-maple.master/developing_course/course_outline.html

### TalentLMS
- Each course has a Files tab for extra resources, separate from the units. Instructors manage it, and learners see their own Files tab. This is the closest match to a separate "Reference" panel.
- https://help.talentlms.com/hc/en-us/articles/9651458837660-How-to-share-files-with-users-in-TalentLMS
- https://help.talentlms.com/hc/en-us/articles/360015530740

### Docebo
- A community thread asks how to attach reference documents without adding them to the table of contents. The snippet shows no confirmed answer. Training materials sit in a library area that is attached to courses, apart from the learning objects.
- https://community.docebo.com/product-q-a-7/how-to-add-documents-that-are-not-training-materials-5464
- https://community.docebo.com/product-q-a-7/resources-related-to-course-materials-7922

### Moodle
- Resources sit inside course sections alongside activities, so there is no separate panel by default. Instructors preview with "Switch role to" Student or Auditor, or "Student view". Hidden items show a "Hidden from students" badge. The "View hidden activities" capability decides who sees hidden items.
- https://www.st-andrews.ac.uk/guides/manage-moodle-activities-resources-visibility/
- https://askathena.brynmawr.edu/help/moodle-hide-or-show-sections-and-items
- https://docs.moodle.org/19/en/Roles_tutorial_-_viewhiddenactivities

## Patterns for this spec
1. Separate panel or tab for supplementary material is the norm (Open edX handouts, TalentLMS Files). It supports the settled "own panel after Course content" decision.
2. Preview in these systems reuses the normal learner rendering (Open edX Preview, Moodle role switch). This supports reusing the existing topic preview.
3. The empty case is not documented in the sources found. TalentLMS and Open edX show their tabs or pages regardless of content, but the snippets do not confirm that. The sources do not settle the "no panel vs empty state" open question. Hiding the panel when a course has no reference parts remains the lower-noise choice, since most courses have none. This is an inference, not a sourced fact.
4. Visibility gating is a capability check (Moodle "View hidden activities"). This is analogous to the `preview_available` gate. Both panels should use one shared check.

## Gaps
- No Canvas (Modules vs Files, Student View) or Thinkific sources were found.
- No source documents empty-state behaviour for resource areas.

status: ok
