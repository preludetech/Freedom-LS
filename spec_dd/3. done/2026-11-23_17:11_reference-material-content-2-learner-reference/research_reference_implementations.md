# Research: reference implementations of course reference material

Spec: `reference-material-content-2-learner-reference`. Question: how do other LMSs and docs-style readers expose reference or resource material that sits beside the learning path, outside progress tracking?

Method note: web search was shallow. Rows marked "verified" are backed by a fetched or searched source. Rows marked "unverified" come from general product knowledge and no source was found. Coursera, Teachable, Docebo and TalentLMS returned no usable sources. Treat those as gaps, not findings.

## Summary table

| System | Entry point | Listing shape | Topic navigation | Tracked? | Source status |
|---|---|---|---|---|---|
| Moodle Book | A course-page activity, so it is in the course flow, not beside it | Table of contents (TOC) block at the side or underneath the chapter. Chapters have one level of sub-chapters. | TOC jump, arrow and text links for previous/next (floating when the page scrolls), print whole book or one chapter | Via activity completion settings. The docs page does not describe them. | verified |
| Canvas | No book equivalent. A Moodle Book migrates to a module heading with pages under it. | Modules list. Pages are items inside modules. | Module sequence, with the module item's own previous/next | Opt-in. Module requirements ("view", "mark as done") are optional. A page with no requirement is not tracked. | verified |
| Open edX | Course navigation tabs (Pages). Course Info is being renamed Home and holds updates and handouts. PDF textbooks each become a tab. | Tab bar of extra pages, outside the Course outline | Per tab. Core tabs (Course, Progress, Discussion) cannot be deleted, only hidden. | The extra tabs sit outside the courseware progress model. | verified |
| LinkedIn Learning | "Exercise files" link in the course Overview tab, under "Related to this course". Optional per course. | Downloadable file bundle, not readable pages | None | Not part of the course completion | verified |
| Thinkific | "Bonus material" is an ordinary curriculum section. Nothing found about excluding it from completion. | Same as lessons | Same as lessons | Unclear. Completion is driven by per-lesson settings. | partly verified |
| Skilljar | Optional lessons in the curriculum | Same list, flagged optional | Same as lessons | Optional lessons do not count towards completion | verified (search snippet) |
| Articulate Rise | Resources tab in the player | Flat list | n/a | Users report no built-in way to split required and optional content | verified (forum snippet) |
| Coursera, Teachable, Docebo, TalentLMS | Not found | Not found | Not found | Not found | gap |
| Docs readers (Docusaurus, GitBook, MkDocs Material) | Top-level navbar or sidebar | Left sidebar tree of sections with topics | Previous/next footer within the sidebar order, breadcrumbs above the title, mobile drawer or hamburger | No tracking | unverified (common pattern) |

## Findings by question

### Entry point in the player
- Most LMSs put reference material inside the learning flow (Moodle Book as an activity, Canvas pages in modules, Thinkific bonus sections). The mixing means it counts as a step, which is the failure mode the idea file avoids by keeping Reference out of `get_course_index`.
- Open edX is the closest to the Reference entry design. Extra pages are tabs in the course chrome, outside the courseware outline, so they are present on every page and never a neighbour in the sequence. Source: https://docs.openedx.org/en/open-release-sumac.master/educators/how-tos/course_development/add_pages.html and https://openedx.org/announcements/update-course-navigation-changes
- LinkedIn Learning puts supplementary material in the Overview tab, away from the lecture sequence. Source: https://www.linkedin.com/help/learning/answer/71925

### Listing shape
- Moodle Book's TOC (chapter then sub-chapter, two levels) matches the spec's part then topic shape. Source: https://docs.moodle.org/en/mod/book
- Moodle lets teachers hide a page from students. That is comparable to the answers file's decision to hide empty parts.

### Topic page navigation
- Moodle Book offers both TOC jump and previous/next arrows within the book. This matches the answers file (previous/next within a part, plus a link back to the listing). Source: https://docs.moodle.org/en/mod/book
- Moodle Book also offers print per chapter or whole book. That is out of scope here but shows a common reference-reader need (regulations to print or keep to hand).
- Docs readers use breadcrumbs, a sidebar tree and a previous/next footer. Previous/next normally follows the sidebar order, and so crosses section boundaries. The answers file scopes it to one part, which is stricter and simpler. Unverified.

### Mobile placement
- No LMS source found. Docs readers collapse the sidebar into a drawer with the same tree. The answers file places the Reference entry right under the course table of contents in the bottom-sheet, which is consistent with a drawer that keeps reference one step from the outline. Unverified.

### Tracking of views
- Canvas: tracking is opt-in per module item, so an item with no requirement is untracked. Source: https://sopaid.tulane.edu/?p=294
- Skilljar: optional lessons are excluded from completion. Source: https://support.skilljar.com/hc/articles/38190327672461
- Open edX: extra tabs sit outside the progress model. Sources as above.
- The common thread is that "optional" is a flag on an item inside the path. Structural separation (own route, own chrome entry, no progress writes), as in this spec, is stronger than a flag. It also avoids the Articulate Rise complaint that required and optional content cannot be separated.

### Public course pages
- No source found for how public pages advertise reference material. Open edX course-about pages and Thinkific/Udemy-style landing pages list the curriculum only. The spec's titles-only section beside "Course content", with no links, has no verified precedent. It is a design choice, not a copied pattern.

## Implications for the spec
1. Keeping Reference as a chrome entry outside the outline matches Open edX and avoids the mixed-in problem of Moodle, Canvas and Thinkific.
2. Previous/next within one part plus a back-to-listing link matches Moodle Book (TOC plus arrows).
3. Two levels (part, topic) is enough. Moodle Book also stops at chapter and one sub-level.
4. Print and download are common in reference readers (Moodle print, LinkedIn exercise files). They are out of scope per the idea file, so note them as deferred only.
5. Gaps worth a second pass if needed: Coursera, Teachable, Docebo and TalentLMS player chrome, and mobile patterns.

## Sources
- https://docs.moodle.org/en/mod/book
- https://docs.openedx.org/en/open-release-sumac.master/educators/how-tos/course_development/add_pages.html
- https://openedx.org/announcements/update-course-navigation-changes
- https://docs.openedx.org/en/ulmo/educators/how-tos/communication/add_course_updates_handouts.html
- https://www.linkedin.com/help/learning/answer/71925
- https://sopaid.tulane.edu/?p=294
- https://support.skilljar.com/hc/articles/38190327672461
- https://community.articulate.com/discussions/rise-360/resources-tab-in-rise-still-no-solution
- https://helpwiki.evergreen.edu/wiki/index.php/Translating_Moodle_to_Canvas

status: ok · reason: shallow coverage, several named systems returned no sources and are marked as gaps
