# Reference implementations: LMS course cards

## Summary recommendations

- Treat the three states as three distinct cards, not one card with toggles. In-progress shows progress; not-started shows an enrolment affordance; complete shows a success affordance. Coursera, edX and LinkedIn Learning all visibly differentiate the three.
- Make the whole card the click target, but show a clear secondary affordance (eyebrow + label) so the destination is predictable. Canvas, edX and Pluralsight all rely on full-card click; Duolingo uses a popup as an intermediate step before the user commits. [1][2][6]
- For the not-started state, prefer a modal / popup preview over a separate detail page. Duolingo's tap-circle popup and modal-UX guidance both support keeping users anchored on the dashboard so they can compare/scan adjacent courses. [2][9]
- Render the in-progress affordance as a thin progress bar with a numeric percent and a short "next up" hint. This is the convergent pattern across Coursera, Pluralsight, Canvas and Khan Academy. [1][3][6][7]
- For the complete state, route to a dedicated completion page (certificate-style) rather than collapsing onto the card. LinkedIn Learning explicitly does this; edX and Coursera mark the card with a "Completed" pill that links to a course-end summary. [4][5]
- An icon-on-tinted-block thumbnail (the FLS approach) is well supported provided the icon reads at small sizes and the tint is the main carrier of identity. Canvas's color-overlay-over-image pattern shows that learners use colour, not imagery, to recognise courses at a glance. [6]

## Per-platform observations

### Coursera
Card shows thumbnail, course title, partner/org, and (when enrolled) a progress bar with percent plus a "Resume" / "Continue Learning" button. Not-enrolled cards lead to a full course detail page. Completed courses get a "Completed" badge and link to a certificate page. [1]

### Udemy ("My Learning")
Card shows wide thumbnail, title, instructor, and a thin progress bar with percent. Hover/click resumes at the next lecture. Not-started cards show "Start course". No modal preview - the card is the launcher; a separate browse page handles enrolment. [8]

### Khan Academy (Learner Home)
"My Courses" cards include the course name, the next unit to start or resume, and a count of skills completed in the in-progress unit. Strong emphasis on "what's next" rather than overall percent. The Learner Queue surfaces a focused next step instead of a long list. [3]

### edX / Open edX
Course card shows organisation name, course name, end date and a thumbnail. Status filters: In progress, Not started, Done, Not enrolled, Upgraded. Triple-dot menu for secondary actions (unenrol, share). The 2024 redesign proposal explicitly separates org/title/date for legibility and adds icons for faster scanning. [4][5]

### Canvas (Instructure)
Each card is a colour block (or image with colour overlay) plus title and up to four feature tabs (Announcements / Assignments / Discussions / Files). Learners can recolour cards and rename via nicknames - colour is the primary recognition cue, image is secondary and optional. The colour-overlay system is a strong precedent for FLS's "icon over tinted background". [6]

### Duolingo
Lesson "cards" are nodes on a linear path. Tapping a node opens a popup with the lesson's name and a Start button - this is essentially the not-started preview pattern. Completed nodes are gold; current node has a bouncing animation; future nodes are greyed. Click commits to a lesson; the popup is the safe preview step. [2]

### LinkedIn Learning
Continue-learning rail shows thumbnail, title, instructor, time remaining and a progress bar. Completion takes the learner to a dedicated congratulations page with certificate download, "add to LinkedIn profile" CTA and follow-on recommendations - not back to the card. [7]

### Pluralsight
Cards show title, author, completion percent and last-activity timestamp. Path cards aggregate constituent course progress. Reset-progress is surfaced inside the course, not on the card. [10]

## Cross-cutting patterns

- Three visually distinct states with stable layout: same card silhouette, different content slot.
- Progress shown as a slim bar plus numeric percent; "next up" text is increasingly common and reduces friction over a bare percent.
- Status as text label (eyebrow) above title: "In progress", "Not started", "Completed". Improves scanability vs colour-only signalling.
- Modal/popup for not-started detail is preferred when learners are comparing several courses on a dashboard; a full detail page is preferred when there is significant marketing/syllabus copy. [9]
- Completion is a milestone moment: dedicated page with certificate / share / next-course beats a quiet badge.
- Colour + small icon is a workable alternative to photographic thumbnails when courses lack curated imagery; Canvas validates this at scale. Risk: low colour contrast or generic icons (e.g. one icon used across many courses) collapses recognition.

## References

1. Coursera dashboard / course card UI patterns (search results, May 2026): https://www.coursera.org/
2. The Science Behind Duolingo's Home Screen Redesign: https://blog.duolingo.com/new-duolingo-home-screen-design/
3. Khan Academy - Learner Home / My Courses: https://support.khanacademy.org/hc/en-us/articles/360030629852
4. Open edX - About the Course Dashboard: https://docs.openedx.org/en/latest/learners/concepts/open_edx_platform/what_is_course_dashboard.html
5. Open edX - Proposal: Enhanced Course Card Design: https://github.com/openedx/platform-roadmap/issues/355
6. Canvas - How do I use the Dashboard as a student / Card View Dashboard: https://community.instructure.com/en/kb/articles/662815-how-do-i-view-my-courses-in-the-card-view-dashboard
7. LinkedIn Learning - Course progress and completion: https://www.linkedin.com/help/linkedin/answer/a700781
8. Udemy - Course management & learning dashboard: https://support.udemy.com/hc/en-us/sections/206457387-Course-Organization
9. Modal vs. Separate Page UX Decision Tree (Smashing Magazine, 2026): https://www.smashingmagazine.com/2026/03/modal-separate-page-ux-decision-tree/
10. Pluralsight - Paths and progress: https://help.pluralsight.com/hc/en-us/articles/24418811505044-Paths
