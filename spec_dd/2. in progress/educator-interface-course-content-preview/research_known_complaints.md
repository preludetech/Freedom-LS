# Research: known complaints about educator course-content preview

Topic: `known_complaints`. Question: what do users commonly complain about with this kind of work?

Feature (from idea.md): an educator-interface course details page showing course details and the table of contents (TOC). Each TOC item has a preview button that opens a modal showing the item as a learner sees it.

Method and limits: web searches in one pass (Canvas Community, Moodle docs/tracker, Open edX docs/GitHub, general modal-UX sources). Frequency and severity ratings are my judgement from the sources found, not counts. Reddit and G2/Capterra were not surfaced by the searches, so they are not covered. Brightspace and Limerick claims came through search summaries and were not opened.

## Theme 1: Preview does not match what learners see (HIGH frequency, HIGH severity)

- Canvas: the instructor's gradebook total includes hidden (unposted) grades while the student view excludes them, so the two views disagree. Test Student scores also differ between the Grades and Assignments pages.
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Student-course-grade-is-incorrect-differs-from-the-teacher-view/m-p/547582
  - https://community.canvaslms.com/t5/Canvas-Ideas/Gradebook-Warning-that-grade-differs-due-to-unposted-assignments/idi-p/599309
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Student-s-view-Grades-and-Assignment-order-wrong/m-p/611990
- Open edX: Staff view in preview mode also shows content marked "Visible to Staff Only", so staff see more than learners. Other roles lose the staff functions.
  - https://docs.openedx.org/en/ulmo/educators/references/roles_for_viewing.html
  - https://docs.openedx.org/en/ulmo/educators/references/testing_course_content.html
- Open edX: the Studio "Preview" button did not use the Learning MFE (the learner-facing front end), so the preview path was not the learner path. It was reported fixed later.
  - https://github.imc.re/openedx/frontend-app-learning/issues/1455 (mirror of the openedx/frontend-app-learning issue)
- Other LMSs: the University of Limerick help page says its Learner view is not 100% accurate. Brightspace documents that its content preview can show hidden or conditional content differently from learners and recommends impersonation for end-to-end tests.
  - https://ul.ie/node/75682
  - https://community.d2l.com/brightspace/kb/articles/35011

Implication: render the modal with the same templates and components the learner interface uses, not a separate educator rendering. Say plainly in the UI what the preview is: content rendering only, with no learner-specific state such as progress, completion or unlock status. Any known difference should be labelled, not silent.

## Theme 2: Preview creates attempts, progress or grades that pollute data (HIGH frequency, HIGH severity)

- Moodle: teacher quiz previews are documented as not saving scores and not appearing in reports, yet bugs reported preview attempts being counted in item analysis and results (MDL-11213, since fixed). A teacher showed up in a grade report because attempt capabilities, not roles, drive inclusion (MDL-66946).
  - https://docs.moodle.org/test/Quiz_preview
  - https://tracker-old.moodle.org/browse/MDL-11213
  - https://tracker-old.moodle.org/browse/MDL-66946
- Moodle: the standard workaround is a dummy "Test Student" account, then deleting its attempts by hand afterwards.
  - https://docs.moodle.org/en/Quiz_FAQ
- Canvas: Test Student is added to every section and shows in the gradebook. Its data is excluded from analytics, and removing it from the gradebook is a manual, repeated step.
  - https://community.canvaslms.com/t5/Archived-Questions/What-does-quot-Test-Student-scores-are-not-included-in-grade/m-p/228673
  - https://helenacollege.edu/online/removing-test-student-from-canvas-gradebook.pdf

Implication: the preview must be read-only and must create no rows in learner progress, form attempt or registration models. Opening a preview must not mark a topic complete, start a form attempt or touch progress. Do not use the test-account approach. Forms and activities that normally write on render or submit must be suppressed or shown inert in the modal. Add a test that opening a preview creates no progress or attempt records.

## Theme 3: Quizzes and forms cannot be previewed, or behave differently in preview (MEDIUM frequency, MEDIUM severity)

- Moodle: a timed quiz did not auto-submit when previewed as a teacher but did for students (MDL-37514). Quiz preview differences are common enough to have their own docs page.
  - https://tracker-old.moodle.org/browse/MDL-37514
  - https://docs.moodle.org/test/Quiz_preview
- Hidden or conditional content is shown differently in some previews (Brightspace link in Theme 1).

Implication: decide explicitly how a form or activity item appears in the modal. Options are a read-only render of the questions, or a "not previewable" state. Whichever is chosen, show the questions as learners see them. Do not offer a working submit. State behaviour for scoring, answers shown or hidden, and timers in the spec.

## Theme 4: Locked, unreleased or draft content (MEDIUM frequency, MEDIUM severity)

- Open edX splits "View Live" (published) from "Preview" (draft/unreleased), and staff-only content only shows in one of them. Educators have to know which mode they are in.
  - https://docs.openedx.org/en/ulmo/educators/references/testing_course_content.html
- Canvas: hidden or unposted state is the main cause of educator and learner views disagreeing (Theme 1 links).

Implication: the TOC should list all items, including unpublished ones, with a visible status badge. Preview should work for every item regardless of unlock or release state. Make clear that the preview ignores gating, and that real learners may be blocked.

## Theme 5: Course overview / TOC problems (MEDIUM frequency, LOW to MEDIUM severity)

- Canvas has no sub-modules. Users work around it with text headers. Long modules (50+ items) overwhelm and make items hard to find. The Modules list is flat: every item looks the same, with only indentation as a cue.
  - https://community.canvaslms.com/t5/Canvas-Ideas/Sub-Modules/idi-p/659522
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Modules-within-Modules/m-p/108042
  - https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Too-many-Modules-Options-for-resorting-structuring/m-p/55983
  - https://canvas.ucdavis.edu/courses/34528/modules/items/4983
  - https://lisahistory.net/wordpress/2020/06/working-against-canvas-three-tips/
- Educators ask for a table of contents or outline at the top of the course (Canvas Community suggestion).

Implication: show the whole TOC on one page with a clear hierarchy. Show a content type per item (topic, form, activity and so on) so items are not all alike. Indent or group so nested structure is visible. Avoid N+1 queries on large courses. Use select_related and prefetch_related, as the project conventions require. I found no direct source on TOC load speed; treat that as an inference from the project conventions.

## Theme 6: Modals for reading content (MEDIUM frequency, MEDIUM severity)

- Long content in a modal is widely called a misuse of the pattern. Modals hide the page behind and break the user's train of thought.
  - https://medium.com/@adamshriki/the-high-cost-of-interruption-re-evaluating-the-modal-dialog-in-modern-ux-e448fb7559ff
- Scroll chaining: the background page scrolls when the modal content ends, and closing can leave the user somewhere else. A native HTML dialog does not lock background scroll by default.
  - https://issues.joomla.org/tracker/joomla-cms/43076
- Mobile: nested scrolling in a tall modal is awkward, especially on iOS. One design system recommends inline expansion or a separate page instead.
  - https://forums.oracle.com/ords/apexds/post/apex-5-1-modal-scroll-issue-4434
  - https://mdbootstrap.com/support/jquery/using-modal-full-height-breaks-scroll/
  - https://vpon.me/articles/modals-and-user-experience
- Content taller than the viewport that cannot be scrolled is a recurring library bug.
  - https://lightrun.com/answers/akveo-nebular-cant-scroll-the-dialog-content-if-its-taller-than-the-viewport
  - https://lightrun.com/answers/sweetalert2-sweetalert2-unable-to-scroll-to-the-top-of-the-modal-when-using-a-long-text
- Not found: specific LMS-educator complaints about missing next/previous or deep links in preview modals. Treat these as plausible risks from the general modal literature, not as evidenced LMS complaints. The NN/g attribution in one source was unverified.

Implication: make the modal large (near full-screen on mobile), with the body scrolling inside it and the page behind locked. Provide a close control, Escape to close, focus return to the opening preview button, and a heading showing which item is open. Consider a stable URL for each preview so an educator can open it in a new tab or share it, and consider next/previous buttons following TOC order. These are optional given "don't build functionality not requested"; flag them for the spec to decide. Load content on demand through HTMX (a request per preview), so the TOC stays light.

## Summary table

| Theme | Frequency | Severity | Main implication |
|---|---|---|---|
| 1 Preview differs from learner view | High | High | Reuse learner rendering, label differences |
| 2 Preview pollutes data | High | High | Strictly read-only, test for no writes |
| 3 Quiz/form preview | Medium | Medium | Define form/activity behaviour explicitly |
| 4 Locked/unreleased content | Medium | Medium | Preview every item, show status |
| 5 TOC overview | Medium | Low-Medium | One-page hierarchy, type labels, efficient queries |
| 6 Modal reading | Medium | Medium | Large scrollable modal, focus handling, mobile; deep link optional |

status: ok
