# Learner reference: read a course's reference material from the player

Spec 2 of 4 in the Reference material effort. Read the "Reference material" section of
`spec_dd/1. next/roadmap.md` first: it holds the build order, what this spec depends on and may
run beside, the decisions already taken and the assumptions every idea in the effort makes.

## What

A registered learner can open a course's reference listing and read reference topics from any page of the course player. Reading is not tracked. The public course detail page also tells visitors that the course has reference material.

- A **Reference entry** in the player chrome, present on every player page, opens the reference listing.
- A **reference listing page** shows the course's reference parts, in order, with the topics in each.
- A **reference topic page** shows one topic's rendered content.
- The public `course_detail` page lists the reference part titles in a section beside "Course content".

## Why

Learners on a course such as drone training need the regulations to hand while they work, and come back to them as needed. Today the player only knows the learning path, so reference parts attached by `reference-material-content-1-authoring` would be stored but unreadable.

## What is settled

**Routes and scope**
- Reference pages have their own URLs under the course, shaped like `courses/<slug>/reference/...`. They do not take a position in the flat `courses/<slug>/<int:index>/` numbering.
- Pages are scoped through `CourseReferencePart` for that course. Part slugs are unique per site and a part shared by several courses is one row, so the course scoping is what makes a part slug in the URL unambiguous.

**Chrome**
- The Reference entry sits in the sidebar region of `_course_base.html`, which is also the HTMX out-of-band swap target for Previous and Next. It therefore appears on every page extending that template: topics, forms, the closed-item page and the finish page.
- It is not a row in the `get_course_index` outline list. That list feeds next/previous, next-up and the deadline picks, and a reference row would be taken as a neighbour in the learning path.

**Nothing is tracked**
- The reference route never goes through `view_course_item` or `view_topic`, because those write progress.
- It writes no `TopicProgress`, no resume pointer, no `started_at` and no analytics event.
- Reference pages show no mark-complete control, no Finish Course control and no Home link to index 1.

**Access**
- Access reuses the player's decision: `raise_404_if_unavailable` followed by `can_access_content` from the wrapped `COURSE_ACCESS_BACKEND`. A bare `is_registered_for_course` is not enough, since it would skip the audience gate, hidden-course 404s, a non-free backend and the paused and ended outcomes.
- Paused and ended learners cannot read reference material, the same as lessons. The reference route needs no read-only exception.
- Anonymous visitors cannot use player routes, as today.

**Rendering**
- A reference topic is rendered with `Topic.rendered_content()`. Images and media resolve from the topic's own `file_path`, so a shared part at a `../` path works under whichever course it is opened from.

**Detail page**
- `course_detail` is public, so the reference section shows part titles only, with no links into reference pages for visitors who cannot open them. A course with no reference parts shows no such section.

## Open until the spec

- Whether the topic page offers next and previous within a reference part, or only a way back to the listing.
- The breadcrumb shape on reference pages. The learning-path part crumb links into the player by index and cannot be reused as it is.
- Where the Reference entry sits in the mobile outline bottom-sheet.
- The empty state of the listing, for a course whose reference parts have no topics.
- The visual treatment of the Reference entry, the listing and the topic page. Design states go through the project's frontend rules (`brand-guidelines`).

## Out of scope

- Educator outline and preview of reference parts: `reference-material-content-3-educator-reference`.
- A library-only course, with no learning path: its home, dashboard and catalogue cards, progress display and finish behaviour belong to `reference-material-content-4-library-courses`.
- Authoring, `content_save` and the demo course: `reference-material-content-1-authoring`.
- Tracking reference views, search, PDFs and files, forms in reference, nesting deeper than part to topics.

## Resources

- `spec_dd/1. next/reference-material-content/research_learner_player.md`: player chrome, topic rendering, access and empty-course facts.
- `spec_dd/1. next/reference-material-content/idea.md`: the original brief.
- Depends on `reference-material-content-1-authoring` for the model, loader and demo course.
