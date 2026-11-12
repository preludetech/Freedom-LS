# Prior art: educator course content preview

Question: what has already been tried for this, here or elsewhere, and what happened?
Method: Grep/Glob over `spec_dd/` (next, in progress, done, noop, corporate-readiness), `docs/product/educator-interface.md` and the roadmap. No git log was available, so history is read from the spec archive only.

## Part 1: here

### 1.1 What exists today

- The educator interface already has a Courses list and a course page (`docs/product/educator-interface.md`, "Courses"). It is read-only and organisation-scoped. The page shows the title and category, the cohorts registered with each cohort's status, and direct registrations. Frontend QA from educator-interface-1 describes the same page as "Details" (Title, Dashboard category), "Cohort Registrations" and "Direct Registrations" (`spec_dd/3. done/2026-09-26_16:41_educator-interface-1-panel-framework-core/3. frontend_qa.md`, lines 116-120).
- So the idea's "course details page" is not new ground: it extends an existing course page. It adds course details plus a table of contents (TOC), and it needs a preview control per TOC item. The idea's last line, "Also show the course details page", is ambiguous: it may mean the existing page, or the learner-facing details content.
- Docs state "Courses have no quick view" (`docs/product/educator-interface.md`, "Quick view"). The quick view covers learners and cohorts only.

### 1.2 Why courses have no quick view

The archive records no deliberate decision to defer a course preview. It is an absence, not a rejection.

- educator-interface-3 (panel-framework-dialogs, done 2026-10-04) built the quick view for exactly two first consumers: a learner and a cohort. Its stated reason was that "the learner table, the cohort detail and the dashboard's attention list all want it" (`spec_dd/3. done/2026-10-04_09:07_educator-interface-3-panel-framework-dialogs/1. spec.md`, "First consumers"). Courses were never listed as a consumer.
- Reading the quick view code and spec suggests that a course's summary is already short and fits on the course page itself. This is inference, not recorded.
- The quick view is a summary drawer for list rows. A TOC item preview is different: it shows content, not a summary. The modal, not the quick view, is the matching framework piece (see 1.3).

### 1.3 The modal was built with this use in mind and deliberately left unconsumed

This is the most important finding. educator-interface-3 built one shared native `<dialog id="app-modal">`, opened with `showModal()` and filled over HTMX on open. Its idea text says the modal "can also show read-only content, such as a topic's markdown at reading width so an educator can check what a learner sees" (`.../educator-interface-3-panel-framework-dialogs/idea.md`, line 11).

Decisions and detail from the spec (`1. spec.md`):

- Out of scope: "A real read-only modal consumer such as a topic preview. Tests prove read-only fragments work." (line 30). The topic preview was deferred, not rejected. This feature is that deferred consumer.
- A "modal fragment" is the HTML an action's GET returns into the modal body. It can be a form, a destructive confirmation, or read-only content with its own heading.
- A read-only base template exists: `panel_framework/modal/read_only.html`. The heading gets `tabindex="-1"` and `autofocus`, and the content sits at reading width.
- Backdrop click closes the dialog only when the body contains no `<form>`, so read-only content closes on a backdrop click and forms never do.
- Spec 1 left empty `modal_host` and `quick_view_host` blocks in `_base_interface.html`, outside `#interface-main`, so navigation swaps of `#main-content` never touch the dialogs.
- `#main-content` has `tabindex="-1"` so focus can land there after a dialog closes. Upgrade notes say to keep it in any override.
- The old `cotton/modal.html` (Alpine `div` with `role="dialog"`) was deleted. It did not trap focus, inert the page or restore focus. Do not reintroduce an Alpine modal.
- Host templates must include the dialog hosts (upgrade notes line 63).
- Responses: no panel action sends `HX-Redirect` any more. Success is a 204 with `HX-Trigger` (including `closeModal`). A permission failure used to return an empty 403 (upgrade notes lines 100-104).
- Docs promise (`docs/product/educator-interface.md`): dialogs take their names from headings, move focus in, close on Escape and return focus.

### 1.4 Bugs and lessons from related work

1. **Quick view reopen bug (educator-interface-3 QA, B1).** Reopening a quick view after a sidebar navigation and Back opened an empty, permanently skeletoned drawer with no request, and a console `InvalidStateError: showModal ... element is not in a document`. B2 was pagination overflow under the docked drawer. B3 was the drawer 8px under the header after a viewport resize. All three were fixed (`.../educator-interface-3-panel-framework-dialogs/qa_report.md`). Lesson: dialogs that live outside `#main-content` while their trigger lives inside it break around history navigation and HTMX swaps. Test Back/forward and reopen on the preview modal.
2. **Closed `<dialog>` swallowing clicks (image-modal QA, BUG 1, high severity).** A custom `display:flex; position:fixed` on `.spotlight-dialog` overrode the UA rule `dialog:not([open]) { display:none }`. Every closed dialog blanketed the page and intercepted clicks and taps. The fix was `dialog:not([open]) { display:none }` or scoping the layout to `[open]` (`spec_dd/3. done/2026-06-08_19:14_student-interface-course-player-image-modal/qa_report.md`). Lesson: do not style the shared modal's display in a way that beats the UA closed state. Check the closed state when a preview is added.
3. **Accordion re-sanitises its slot (open downstream bug, LEARN-1).** `<c-accordion>`, and likely `card`, `admonition`, `grid`, `table` and `pull-quote`, render their slot through `{% markdown slot %}`, which runs `nh3.clean` a second time on already-rendered component output. This strips `x-data`, `role` and `class`, so a nested `<c-equation>` shows raw LaTeX (`spec_dd/2. in progress/downstream_bugs_oct_29/accordion-strips-nested-component-attributes/idea.md`). Lesson: a content preview in a modal will show this same breakage unless the preview reuses the learner's render path and the bug is fixed or known. Interactive content (equations, accordions, flashcards) must mount in an HTMX-loaded modal, so Alpine initialisation after a swap needs checking.
4. **Course detail "Continue" restarts at item 1 (open downstream bug, LEARN-2).** `_detail_start_url` in `learner_interface/views.py` returns item 1 for every registered learner, while only the label reflects progress (`.../course-detail-continue-restarts-at-item-one/idea.md`). This affects the learner page. For the educator preview it is a reminder that a start URL differs from a resume URL. The educator has no progress, so a preview must not touch learner progress.
5. **TOC ignores closing (deadlines-2 QA).** The learner course detail "Course content" outline ignored closing, so a closed failed quiz read "Needs retry" and closed items read "Not started" (`.../deadlines-2-consequence-policy/todo.md`, line 26). Lesson: a TOC built for the educator must not copy learner status logic, because the educator sees structure and not per-learner state.
6. **TOC expand and course-part bugs.** I found no record of a TOC expand bug or a course-part navigation bug in `spec_dd/`. The TOC partial is `course_minimal_toc.html`, which deadlines work builds on (`1. next/deadlines/research_deadline_integration_points.md` lines 245, 354). `get_course_index` in `learner_interface/utils.py` builds each TOC entry's status (BLOCKED, and so on). Chevron expand and collapse icons are in the icon audit (`3. done/2026-03-01_22:40_open-source-icons/research_current_icon_audit.md`). Playwright tests `test_course_toc.py` and `test_course_detail_toc_in_development.py` exist (`1. next/test-organisation-and-hygene-13-learner-interface-part-1/idea.md`). If the caller has a specific bug in mind, it is not in the spec archive. Ask or check the code.
7. **Authorisation gap on the educator Courses list and course page.** `spec_dd/corporate-readiness/README.md` (lines 56-58) says a security reviewer who finds it "will stop the deal", and says to fix it before the first corporate pilot. The roadmap flags it. I found no record of a fix. This feature adds content access behind that page. Any preview endpoint must enforce organisation scope itself and must not rely on the page's check. A preview exposes course content (possibly of another organisation's non-public course), which makes the gap more serious.
8. **Course visibility.** The Courses list shows published courses, plus hidden or coming-soon ones only where this organisation uses them, and omits other organisations' non-public courses. A preview of a hidden or coming-soon course is allowed only through the same rule. Learner pages use `raise_404_if_hidden_unregistered` for the equivalent gate (`0. noop/landing-pages/research_dev_authored_page_mechanics.md` line 312).
9. **Related: learner course detail.** `spec_dd/2. in progress/learner-facing-ux-refinements` changes the learner course detail (a single Back link). Downstream bug notes cover a hero icon misplaced on phone (DISC-8) and the course-detail footer. These are learner-side. Check for reuse before copying learner templates into the educator page.
10. **Earlier related specs.** `spec_dd/3. done/2026-02-27_08:53_educator-interface-cohort-course-progress` (educator view of cohort course progress), `2026-07-11_16:24_override_course_access_and_details_page`, and `2026-06-04_14:41_student-interface-unstarted-course-click-behaviour/research_course_landing_ux.md`. I did not read them in depth. They are the nearest earlier work on course landing and detail pages.

### 1.5 Net decisions to carry forward

- Use the shared `app-modal` and the read-only fragment base. Do not build a new dialog.
- Do not use the quick view drawer for content. It is for summaries.
- Docs must change: "Courses have no quick view" stays true if this uses a modal. The Courses section says the page shows title, category and registrations only, so it needs the TOC and preview added.
- No existing spec deferred a course preview on its merits. The topic preview was explicitly deferred as "a real read-only modal consumer".

## Part 2: elsewhere (well-known attempts)

Not fetched in this run. These are from background knowledge, with the official pages that cover them. Verify before quoting.

- **Canvas Student View.** An instructor enters Student View, which creates a hidden "Test Student" enrolment in the course. The Test Student's submissions and grades live in the course until reset, and Canvas offers "Reset Student" to clear the data. Instructors report that stray test data lingers and affects gradebook views, so the course must be reset or the test student deleted. Data from Test Students is excluded from some analytics but not all, depending on the report. Lesson: a preview that creates a fake learner pollutes data, so FLS should create no learner, progress, attempt or registration records when previewing. https://community.canvaslms.com/t5/Canvas-Basics-Guide/How-do-I-view-a-course-as-a-test-student-using-Student-View/ta-p/1228 (likely URL; may have moved)
- **Moodle "Switch role to... Student".** Teachers preview by switching role. The known problems are that the interface resembles the real student view yet behaves differently: actions can be blocked or can write records for the teacher. People forget they are switched, and a page looks different from what a real enrolled student sees (groups, completion, restrictions). Moodle's own documentation warns that switching role does not mimic a real student exactly. A "Test student" account (a separate user) is the standard recommendation. Lesson: label the preview clearly and keep it read-only. https://docs.moodle.org/en/Switch_role
- **Open edX Preview vs Live.** In Studio, "Preview" and "View Live" render the unit from the draft or published branch. The two can drift apart: unpublished changes show in Preview only, and staff see content that learners do not (release dates, group access). Authors repeatedly publish the wrong version or are confused about which one they are viewing. Lesson: say which version and which audience the preview shows. In FLS there is no draft branch, but visibility (hidden, coming soon, published) plays a similar role. https://edx.readthedocs.io/projects/open-edx-building-and-running-a-course/en/latest/ (course authoring docs; the preview section is the relevant part)

Takeaway for the spec: a read-only structural preview needs no fake learner, no role switch and no draft/live split. These are the three failure modes in the other systems. FLS avoids them by rendering content directly in a read-only modal with no progress writes.

status: ok
