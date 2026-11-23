# Research: known complaints about course reference/resource sections

Scope: what learners and authors complain about with reference/resource material inside LMS course players. Evidence is mostly vendor blogs, practitioner forums and institutional policy pages (anecdotal, not formal studies). Three web searches were run; coverage is light on mobile and on stale/duplicated material, where the points below come from general practice and were not confirmed by a source.

## Complaints found

1. **Resources hard to find or scattered.** Links buried at the page bottom or spread across a page; broken or expired links; confusing navigation buttons.
   - https://elearningindustry.com/learning-management-system-lms-navigability-issues-negatively-impact-user-experience
   - https://elearning.adobe.com/2018/06/improve-user-experience-avoiding-7-lms-navigability-issues
   - https://www.capterra.com/resources/problems-with-learning-management-systems/
2. **Feeling lost; no persistent course map or home link.** Learners will not click Next repeatedly to get back to where they stopped. Canvas students ask for a "Start Here" link to the module list rather than to a particular page.
   - https://community.canvaslms.com/thread/34727
   - https://elearningindustry.com/advertise/elearning-marketing-resources/blog/6-tips-to-improve-elearning-course-navigation
3. **Broken back navigation and resume.** Browser Back makes Continue buttons vanish in Rise; after resume, Storyline menus lock previously viewed sections; learners cannot find their way back to the LMS after a module.
   - https://community.articulate.com/discussions/rise-360/rise-continue-buttons-disappearing (thread "Rise continue buttons disappearing", https://community.articulate.com/discussions/discuss/rise-continue-buttons-disappearing/1238041)
   - https://community.articulate.com/discussions/articulate-storyline/restricted-navigation-not-working-in-html5-output-when-course-is-resumed
   - https://community.articulate.com/discussions/rise-360/connection-rise-moodle
4. **Optional or reference items distorting progress.** Moodle's percentage counts accessed/marked items, so untouched optional resources leave progress looking incomplete. Docebo learners who skipped an optional survey show 50% progress though "completed". Rise cannot tell required from optional.
   - https://mustedustudents.freshdesk.com/en/support/solutions/articles/154000233329-what-does-the-progress-percentage-in-moodle-mean-
   - https://community.docebo.com/product-q-a-7/course-progress-doesn-t-reflect-100-completion-7387
   - https://community.articulate.com/discussions/rise-360/course-complete-based-on-completed-what-gets-included
5. **Access lost when the course ends.** Windows run from about two weeks to eight weeks to a year after term end. Third-party content can vanish sooner. Institutions tell learners to save copies, which is the opposite of "regulations to hand".
   - https://www.vanderbilt.edu/brightspace/about/course-availability-policy/
   - https://www.trincoll.edu/tdi/academic-technology/moodle/moodle-data-retention/
   - https://www.weber.edu/online/course-archiving.html
   - https://td.usnh.edu/TDClient/60/Portal/KB/Article/1301/Canvas-Post-Term-Course-Access-FAQ
6. **Not sourced (general practice, unverified here):** mobile access to reference material, stale or duplicated copies of the same material across courses, public pages promising material a visitor cannot open.

## What this spec's design already avoids

- **Hard to find:** a Reference entry in the sidebar of `_course_base.html`, on every player page (topics, forms, closed-item, finish), plus the mobile bottom-sheet entry directly under the table of contents.
- **Lost place / dead ends:** reference has its own routes and does not take part in `get_course_index` numbering, so it cannot become a neighbour in Next/Previous. Course › Reference › Part breadcrumb, a link back to the listing, and Previous/Next within a part.
- **Progress distortion and blocking:** nothing is tracked. No `TopicProgress`, resume pointer, `started_at` or analytics event, and no mark-complete or Finish Course controls.
- **Stale or duplicated material:** a part shared by several courses is one row, so one edit updates every course. Images resolve from the topic's own `file_path`.
- **Public over-promising:** `course_detail` shows part titles only, with no links for visitors who cannot open them, and no section when there are no parts.
- **Empty or broken listing:** empty parts hidden; a single "No reference material yet" message when nothing has topics.
- **Access leaks:** reuses `raise_404_if_unavailable` then `can_access_content`, so audience gate, hidden courses and non-free backends are honoured.

## What the spec should guard against

- **Access lost after the course ends (complaint 5).** The spec deliberately blocks paused and ended learners, as with lessons. Research shows this is the most commonly cited grievance for regulations a learner wants to keep consulting. State it as a conscious decision, tell the learner why access is gone (the closed-item message), and note it as a candidate follow-up rather than silently accepting it.
- **Back navigation.** The Previous/Next HTMX out-of-band sidebar swap and the browser Back button must agree: reference URLs need to be real, bookmarkable, full-page-loadable routes with correct history, and the Reference entry must render correctly on a direct load as well as after an HTMX swap.
- **Lost place when leaving for reference.** Reading reference writes no resume pointer, so a learner who opens reference mid-lesson must be able to return to that lesson. The breadcrumb's Course link goes to course home, which may not be where they were. Consider a browser-Back-friendly design or a "back to course" that does not reset them. Do not add a Home link to index 1 (already ruled out), and check the finish and closed-item pages do not strand the learner.
- **Part crumb anchor.** The part crumb links to a section anchor on the listing. Check that anchors work and that the listing stays scannable with many parts.
- **Mobile.** Sidebar-only placement is invisible on small screens; the bottom-sheet entry covers this, so test it, including a long regulation topic's readability and tables.
- **Visibility before access.** Learners who are registered but blocked (paused/ended) or visitors on `course_detail` must not see a link that leads to a 404.
- **Stale or duplicated material.** Shared parts rely on `../` paths. Guard against broken images when the same part is opened from different courses, and against a part appearing twice in a listing if attached twice.
- **Empty-state wording.** An entry that always shows but leads to an empty page is a known source of "dead link" complaints. The agreed message should say the material is not yet added, not that it is missing.

status: ok
