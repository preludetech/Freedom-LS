# Research: reference implementations of instructor content preview

Question: how do established LMSs and course platforms let instructors or staff preview course content, and what do they do about progress, assessments and navigation?

Scope note: this was web research through search snippets and a few page fetches. Several vendor pages were unreachable (Thinkific returned 403) or silent on specifics. Anything marked "unverified" or "not found" is a gap. I did not find primary sources for Docebo, TalentLMS, Coursera or Kajabi, so they are omitted rather than guessed. No source code was read.

## Moodle

- **Preview versus attempt (permissions).** Preview and attempt are separate capabilities. In the default roles, Manager and Teacher have `mod/quiz:preview` and not `mod/quiz:attempt`. Student has attempt and not preview. The capability docs say a user cannot currently be allowed to both preview and attempt. A preview is therefore a distinct kind of attempt that a student can never make. https://docs.moodle.org/22/en/Capabilities/mod/quiz:preview and https://moodle.org/mod/forum/discuss.php?d=347735
- **Recording.** Preview attempts are flagged as previews, not as student attempts. A tracker bug reports that instructor previews leaked into quiz item analysis as if they were real attempts, so the separation needs care in reporting queries. https://tracker-old.moodle.org/browse/MDL-74302 (single search snippet, treat as indicative).
- **Switch role to student.** A forum comment says a manager who switches to the student role before taking the quiz gets a normal attempt, and without the switch the result posts as a preview. This is anecdotal, not official documentation. https://moodle.org/mod/forum/discuss.php?d=347735
- **Preview behaviour.** The Quiz FAQ says a changed question needs a new preview to pick up the change, because the open preview keeps the old version. It also suggests a dummy student account as an alternative. The teacher reviews that account's attempt and deletes it under Results > Grades. https://docs.moodle.org/404/en/Quiz_FAQ
- **Entry point.** The Preview action lives on the quiz activity page. This is from general knowledge; the fetched docs did not confirm it.
- **Code location (from memory, unverified).** The quiz module is at `mod/quiz/` in https://github.com/moodle/moodle. The attempt flow is `mod/quiz/startattempt.php` and `attempt.php`. A preview is a `quiz_attempts` row with `preview = 1`.

## Canvas (Instructure)

- **Student View.** An instructor enters a "Test Student" mode from the course. The Test Student is a special enrolment that exists in the course and can submit work. This is a role-switch into a fake enrolment, not a modal and not a new tab.
- **Recording.** Test Student activity is recorded, and "Reset Student" wipes it. It does not remove interactions involving real students, such as discussion replies. For New Quizzes the attempts are not deleted by reset, and the guidance is to use the quiz Preview instead of taking it as the Test Student. Community reports say reset sometimes fails, for example a quiz stays locked by test submissions. Deleted submissions are marked "deleted by" the instructor, so they leave a trace.
- Sources: https://community.canvaslms.com/t5/Canvas-Question-Forum/Test-Student-submission-still-there-after-Resetting-Student-View/m-p/606451, https://community.canvaslms.com/t5/Canvas-Ideas/New-Quizzes-Delete-test-student-attempts-when-test-student-is/idi-p/545559, https://eclass.ualberta.ca (search result "using view as student in canvas": https://support.eclass.ualberta.ca/Knowledgebase/Article/View/552/55/using-view-as-student-in-canvas-to-test-the-student-experience).
- **Lesson.** A fake participant who writes real rows creates cleanup and reporting problems. A separate preview path that writes nothing avoids them.

## Open edX

- **Entry point.** The Studio course outline has "Preview" and "View Live" buttons per course, section, subsection and unit. They open the LMS in the staff view. Source: https://docs.openedx.org/en/ulmo/educators/references/roles_for_viewing.html and https://docs.openedx.org/en/ulmo/educators/references/testing_course_content.html
- **Mode.** Navigation leaves Studio for the LMS courseware, with a "View this course as" selector (Staff, Learner, a specific learner, or a content group). This is a role/masquerade switch inside the real learner UI, in a new location rather than a modal.
- **Content visibility.** View Live shows Published and Live content plus Visible-to-Staff-Only content, and hides Private units. Preview additionally shows Draft (Never Published) content. Staff can work problems to confirm correct and incorrect answers are graded as intended.
- **Recording.** The docs do not say whether staff interactions are stored. This is unverified.
- **Navigation.** The learner sequence navigation (previous and next within a subsection) works as normal. Staff can jump back to the unit in Studio.
- **Known problems.** Preview redirecting to the legacy course view (https://github.imc.re/openedx/frontend-app-learning/issues/1455); older reports of "Page not found" when the preview subdomain was not configured (https://groups.google.com/g/edx-code/c/HNNixPMpNd4); `render_xblock` initially denied access to staff masquerading as learners (https://git.andalsoftware.com/Andal.LND/edx-platform/src/commit/1f392bdc3e10ecd87a0b960fe010ab06a569de8c).
- **Code.** https://github.com/openedx/edx-platform: LMS courseware and masquerade in `lms/djangoapps/courseware/` and `lms/djangoapps/courseware/masquerade.py`; the Studio side is the course authoring MFE (`openedx/frontend-app-authoring`). Paths are from memory, unverified.

## Thinkific

- Course Builder offers "view your course from a student's perspective", with three preview options. In the enrolled-student preview, prerequisite lessons do not apply, so the instructor can move freely. Free-preview needs a real signed-up student account. Source: https://support.thinkific.com/hc/articles/360030737873 (read through a search snippet only; the page returned 403).
- Recording and quiz behaviour: not found.

## Teachable

- Many entry points: Course Index kebab menu "Preview as Student", Curriculum tab "Preview", Setup Guide "Preview Curriculum", and a Preview button in the lesson editor with an Admin, Student or Public view choice. Only published content is shown, as an enrolled student sees it. Drip and lock settings behave per course settings. Source: https://support.teachable.com/en/articles/11682499-preview-your-school-and-products
- New tab, progress recording and quizzes: the article does not cover them.

## Google Classroom

- No built-in student view. The "preview" feature (Education Plus) shares classwork with other teachers, hiding drafts, student submissions, comments and grades. Teachers wanting the student experience use a test student account in the domain. Sources: https://support.google.com/edu/classroom/answer/13768073 and https://gatlabs.com/education/blog/google-classroom-student-view

## Kajabi, Docebo, TalentLMS, Coursera

No usable source found in this pass. Gap.

## Comparison

| Platform | Entry point | Mode | Records progress or attempts? | Assessments in preview |
|---|---|---|---|---|
| Moodle | Quiz activity page, Preview | Page in the learner UI | Flagged as preview, separate from attempts (leaks into some reports) | Taken and graded like a real attempt |
| Canvas | Course, Student View | Role switch to Test Student | Yes, real rows, wiped by Reset Student (not New Quizzes) | Submittable |
| Open edX | Studio outline, Preview or View Live | Navigate to LMS staff view, "View this course as" | Unverified | Work and graded |
| Thinkific | Course Builder | Student-perspective view | Not found | Not found |
| Teachable | Course Index, Curriculum, lesson editor | Preview as Student | Not found | Not found |
| Google Classroom | None (test account) | Separate account | Real | Real |

## Patterns that recur

1. The preview entry point sits in the authoring or curriculum view, next to each item: Teachable (lesson editor and curriculum), Open edX (per unit in the course outline), Moodle (on the activity). This matches the idea of a preview button on each table of contents item.
2. Preview renders the learner's real rendering, not a separate staff view. The point is to see what learners see, and the staff variant adds visibility of draft or staff-only content (Open edX).
3. No platform uses a modal. Previews are a page, a new location, or a role or mode switch. A modal is therefore a design choice made here without precedent in these systems, and the spec should treat its constraints (size, nested navigation, embedded forms) as new.
4. Visibility rules are explicit. Teachable shows only published content. Open edX distinguishes Preview from View Live by draft and private content. A spec should say whether unpublished items are previewable.
5. Locks and prerequisites are bypassed or follow settings. Thinkific ignores prerequisites for the previewer. Teachable honours drip and lock settings. This needs a decision.
6. Writing real learner data for a previewer causes recurring pain: Canvas needs Reset Student with known gaps, and Moodle preview rows leaked into analysis. The safer pattern is a separate preview flag (Moodle) or no persistence, with no fake learner enrolment.
7. Assessments are typically interactive in preview, so authors can verify grading. A read-only preview is the cheaper alternative, but the references that were verified let staff try problems.
8. Sequential navigation inside preview follows the normal learner navigation (previous and next). The sources were thin on this, so treat it as likely rather than confirmed.

status: ok
