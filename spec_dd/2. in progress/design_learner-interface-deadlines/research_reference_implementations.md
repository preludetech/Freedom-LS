# Research: reference implementations of learner deadlines

Scope: how established LMSs show deadlines on dashboard course cards, in the course outline and in the current item's header. Evidence is from help-centre pages and search snippets. WebFetch of support.edx.org returned 403, so Open edX details come from search summaries. Items marked (unverified) were not confirmed against a vendor page. I did not inspect screenshots, so colour and icon notes come from text only.

## Per-system findings

### Canvas (Instructure)
- **Dashboard cards:** the card shows course name, code and term, plus shortcut icons to Assignments, Discussions and so on. It carries no deadline band. Deadlines live in a separate **To Do** list in the dashboard sidebar. Sources describe it as roughly the next 7 days or up to 7 items (sources disagree, so the window is version-dependent).
- **To Do contents:** items with a due date, a to-do date (pages, if the instructor enables "Add to student to-do") or a calendar event.
- **List View dashboard:** a separate layout that groups items by date: Today, Tomorrow, This Week, and Overdue. It is the closest precedent for the "grouped list" in the idea.
- **Modules page:** each item shows its due date as a line under the title, date only, no time. Item types have icons. Completion requirements show as a checkmark.
- **Assignment page:** the "Due" date and time sit in the header area. Late and Missing status labels appear in the Grades and Submission views.
- **Hard vs soft:** "Available until" is the hard lock, and due date is soft. Late submissions are tagged "late" and the instructor can apply a penalty. (Sources: Canvas guides below.)
- **Takeaway:** the cards stay clean and deadlines go into a separate aggregate. The module rows use a small date line, which matches the idea's "minimal text" for outline rows.

### Moodle
- **Dashboard Timeline block:** it lists activities by date. Filters are Overdue, Next 7 days, Next 30 days, and so on, each with a sort option. It shows 5 items per course by default, with "Show more activities". Items are grouped by date headers and show the activity name and course name. Overdue is an explicit filter and it is limited to recent weeks (one college page says the past two weeks). MDL-72594 asks for marking all currently overdue activities.
- **Quizzes:** "Quiz opens", "Quiz is due" and "Quiz closes" appear as separate events. Open date, due date (soft) and cut-off (hard) are distinct concepts.
- **Course page and course index:** the "Activity dates" feature (4.x onward) shows "Opened: <date>" and "Due: <date>" under each activity on the course page, in grey text. The course index drawer (a collapsible tree on the left) shows only titles and completion state, with no dates.
- **Hard vs soft:** due date vs cut-off date vs "Allow submissions from". Late submissions show "Assignment was submitted N days late" (red text in the submission status table).
- **Takeaway:** a hard-vs-soft split exists in the data model, but the course index deliberately omits dates. FLS puts dates in the outline, which is a departure from Moodle.

### Open edX
- **Dates tab:** a chronological list of course dates (course start, assignment due dates, course end, and so on). Past items are labelled "Past due" and the next one "Due next". The course home also has a "Shift due dates" button for self-paced courses. A community thread reports completed items still showing past due, which warns that completion state must override the overdue state.
- **Course home outline:** each subsection row shows "Due <date>" under its title, with a completion tick. A "Past due" style label appears on late rows (unverified, search did not confirm the badge).
- **Hard vs soft:** self-paced courses have suggested due dates that learners can shift (soft). The course end date and open response assessments stay fixed (hard). Instructor-paced due dates are fixed.
- **Mobile:** the support page says the Dates tab is the place to check on mobile.
- **Takeaway:** it is the closest analogue to this feature, with due date text per outline row and a "Due next" concept that matches the idea's next-deadline card.

### Coursera
- **Week outline:** each graded item shows "Due <date>" within its week. Lessons are grouped by week with deadline text in the week header. There is a "Reset deadlines" action on the Grades page, offered after missed deadlines (forum reply, offered after two missed deadlines or two weeks late; unverified against Coursera's own help centre).
- **Overdue:** the item shows as overdue and a "Reset deadlines" or "Switch to a later session" prompt is offered. Session-based courses use soft deadlines that can be reset. Resetting can discard work, per several forum reports.
- **Takeaway:** the overdue state comes with a recovery action, not just a red mark. The idea does not include this, so keep it out of scope unless requested.

### Google Classroom
- **To-do (student):** tabs for Assigned, Missing and Done. The "Assigned" tab groups by "No due date", "This week", "Next week" and "Later". Cards show "Due tomorrow" or "Due <time>" (wording per Google help and school guides, unverified for "Due tomorrow").
- **Statuses:** Assigned, Missing (not turned in after due), Done late (turned in after due), Turned in. Statuses apply "as soon as the due date or time arrives".
- **Hard vs soft:** every deadline is soft. Classroom never blocks late work, and teachers set the policy.
- **Takeaway:** a minimal status vocabulary (Assigned, Missing, Done late) and grouping by time buckets, which supports the grouped list in the idea.

### Blackboard Ultra
- **Activity stream:** Important section for overdue items, which sit at the top. Recent for the rest. Items move to overdue when they pass due date.
- **Course content:** the due date appears in the item row. After the due date, submission info shows in red, and a submit attempt is warned as "late". Late penalty is instructor-set.
- **Accommodations:** students with a due date accommodation get no missed-due-date alerts, so deadline state is per learner.
- **Hard vs soft:** late submission is allowed unless the instructor sets the item to close, and "Overdue" is soft.
- **Takeaway:** per-learner deadlines need per-learner state, and the colour (red) is applied to the text after the due date.

### Brightspace (D2L)
- **Work To Do widget:** lists overdue and upcoming items, default upcoming 2 weeks and overdue 12 weeks (admin-configurable). Learners can dismiss overdue items with an X (Sept 2026 release).
- **Content table of contents:** items show their due date, and an "Overdue" badge shows after the date passes (red text) (unverified, search found only the widget and alerts). The "Due dates and overdue course alerts" KB describes alerts.
- **Rules:** start date, due date and end date. Due date is soft, with the assignment still open until the end date. The end date is hard. Learners see "This activity is past due" in grades (May 2026 release). Inconsistent overdue flags for third-party (LTI) items are a known complaint.
- **Takeaway:** the overdue window is bounded, and learners can dismiss stale overdue items.

### Docebo / TalentLMS
- Not covered by search results, so I have nothing reliable to report. Both are mostly self-paced, with course-level due dates or time limits on the catalogue card. No finding.

## Cross-system patterns

| Aspect | Common practice |
|---|---|
| Dashboard | Most systems keep cards clean and show deadlines in a separate aggregate (Canvas To Do, Moodle Timeline, Brightspace widget, Classroom To-do). Cards with a deadline strip are rare, so the band is a design choice, not a convention. |
| Aggregate | Grouped by time buckets (Overdue, Today, This week, Later). Short window plus overdue bounded to recent weeks. |
| Outline row | Short date line under the title (Canvas, Open edX, Moodle course page). Only a minority add an overdue badge. Date format omits the time on list views. |
| Header | The item page shows the due date and time with the longest wording, plus a submitted, late or missing status. |
| States | Upcoming, due soon (rarely named, usually relative wording like "Due tomorrow"), overdue or missing, done, done late, closed (hard end). |
| Colour | Red is almost universal for overdue or missing. Amber for due soon is less common. Neutral grey for upcoming. Colour is always paired with text. |
| Completion | Completion overrides overdue (Open edX bug report, Brightspace false-overdue complaints). Never flag a completed item. |
| Hard vs soft | Soft due date plus hard close or end date (Canvas, Moodle, Brightspace, Open edX). Classroom is all soft. Show the soft one as "due", and only show "closed" or "locked" when the item is actually blocked. |
| Mobile | Open edX points mobile users to the Dates tab. Most others collapse to the same list. Sources give little detail on mobile layouts. |

## Implications for the spec
1. The next-deadline card in the outline panel matches Open edX "Due next", so name the concept "next deadline" and derive it from incomplete items only.
2. Outline rows should show one short date plus a state icon and colour. Keep states to roughly: upcoming (neutral), due soon (amber), overdue (red), done (no deadline shown).
3. Distinguish soft and hard deadlines in the wording ("Due" vs "Closes") only if FLS models both. Check the existing deadline model before deciding.
4. Accessibility: never colour alone, always icon or text (the idea already says icons).
5. Overdue items need a bounded presentation, or the outline fills with red.
6. Do not add recovery actions (Coursera "Reset deadlines", Open edX "Shift due dates") unless requested.

## References
- Canvas To Do and sidebar: https://community.canvaslms.com/docs/DOC-8345
- Canvas List View release: https://community.canvaslms.com/t5/Canvas-Releases-Board/Canvas-Release-Student-Dashboard-List-View-2018-08-04/td-p/388945
- Canvas to-do and sidebar (Seton Hall): https://setonhall.atlassian.net/wiki/spaces/PUBLICKBA/pages/3773988872/To+Do+List+and+Sidebar+in+the+Canvas+Dashboard
- Canvas due and do dates (UMN): https://ccaps.umn.edu/academic-technology-and-design/instructors/tutorials-course-activities/due-and-do-dates
- Moodle Timeline block: https://docs.moodle.org/503/en/Timeline_block
- Moodle tracker MDL-72594: https://tracker-old.moodle.org/browse/MDL-72594
- Moodle dashboard (Edinburgh): https://www.moodle.is.ed.ac.uk/pluginfile.php/72261/mod_resource/content/9/dashboard_2023.pdf
- Open edX, where to view due dates: https://support.edx.org/hc/en-us/articles/17710928522263-Where-can-I-view-my-due-dates
- Open edX, does my course have due dates: https://support.edx.org/hc/en-us/articles/360049382273-Does-my-course-have-due-dates
- Open edX, missed deadline: https://support.edx.org/hc/en-us/articles/206501098-I-can-t-make-a-deadline-can-I-get-an-extension
- Open edX forum, completed items shown past due: https://discuss.openedx.org/t/even-after-completing-the-quiz-and-ora-still-showing-past-due-or-due-next-in-frontend-in-dates-tab/13377
- Open edX Dates tab default: https://discuss.openedx.org/t/dates-tab-added-as-default-for-all-courses/7849
- Coursera reset deadlines (community): https://community.deeplearning.ai/t/how-can-i-reset-the-course-deadline-i-am-not-trying-to-pursue-a-grade/270822
- Coursera sessions blog: https://blog.coursera.org/improvements-to-sessions-experience-for-learners/
- Google Classroom help: https://support.google.com/edu/classroom/answer/6020284
- Blackboard Activity Stream: https://help.blackboard.com/he/Learn/Student/Ultra/Stay_in_the_Loop/Activity_Stream
- Blackboard activity stream external content: https://help.blackboard.com/node/28631
- Blackboard learner progression: https://help.blackboard.com/node/47541
- Brightspace due dates and overdue alerts: https://community.d2l.com/brightspace/kb/articles/6068-due-dates-and-overdue-course-alerts
- Brightspace Work To Do widget: https://community.d2l.com/brightspace/kb/articles/3510-about-the-work-to-do-widget
- Brightspace May 2026 students: https://servicedesk.minnstate.edu/TDClient/30/Portal/KB/Article/653/What-s-New-in-D2L-Brightspace-May-2026-for-Students
- Brightspace Sept 2026 students: https://servicedesk.minnstate.edu/TDClient/30/Portal/KB/Article/695
- Brightspace start, due and end dates (Purdue): https://engineering.purdue.edu/I2IApps/Brightspace/Documents/How to set Start Due and End Dates and what they mean.pdf

status: ok
