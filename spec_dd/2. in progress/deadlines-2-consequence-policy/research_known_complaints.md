# Research: known complaints about LMS deadline consequences (spec 2)

Adds to `spec_dd/1. next/deadlines/research_deadlines_user_sentiment.md` (the sentiment file). That file's sections (a) and (g) already cover the Canvas "Late" label inside a grace period, the Docebo soft-deadline suppression, Coursera reset destroying work, 11:59 pm and Moodle unlabelled timezones. None of that is repeated here. Terms in quotes belong to the named system, not to FLS.

## Method and limits

- Four standard web searches. Each result was a search summary, not a full read of every thread. Claims are limited to what the summaries stated.
- No Reddit, G2 or Capterra threads were returned again. Not found: any complaint about not seeing which layer set a value in an LMS. That finding rests on adjacent Canvas section/override threads (below). Treat it as a gap.
- Evidence is mostly university help desks and vendor/community posts. Several are anecdotal and are marked.

## 1. Lost in-progress work at close time

- Canvas classic quizzes auto-submit when the "Until" (availability end) date is reached, even if the student's own attempt has not expired. A submitted attempt cannot be reopened; the instructor must give an extra attempt or use "Moderate Quiz" with "Manually unlock the quiz for the next attempt". https://community.canvaslms.com/t5/Question-Forum/Quiz-not-auto-submitted-No-activity-log-after-quiz-closed/m-p/447195
- Canvas timed quizzes sometimes do not auto-submit at all, reported "around the world" and sporadic; staff said engineers knew (undated thread). So the opposite complaint exists too: closing that silently fails to fire. https://community.canvaslms.com/t5/Question-Forum/Timed-Quiz-Did-Not-Auto-Submit-for-a-Student/m-p/418192
- New Quizzes has no "due at a time then counts as submitted" behaviour; an idea asks for auto-submit at the due datetime. https://community.canvaslms.com/ideas/15021-new-quizzes-automatic-submission-at-the-due-datetime
- Canvas "Until" overrides the quiz timer: students are "prematurely kicked" from a quiz when the Until time (or a section end date earlier than it) arrives mid-attempt. https://support.csuchico.edu/TDClient/1984/Portal/KB/Article/113763/Students-are-Prematurely-Kicked-from-a-Quiz-in-Canvas
- Giving a student extra time mid-quiz changes the timer but not the lock date, so they are still cut off. https://community.canvaslms.com/t5/Canvas-Question-Forum/Quiz-Available-Unit-date-meaning/m-p/612167
- Canvas answers are autosaved while connected, and an interrupted student can rejoin only until the allowed time or the available date passes. https://med.stanford.edu/edtech/services/lms/medcanvas/exams.html

Bearing on the spec: the common fix in Canvas is a manual per-student rescue after the fact. A closed item with an in-progress form attempt is where learners lose work; the complaint is less "it closed" than "it closed under me with no recovery". Staff recovery needs a defined route. This favours deciding explicitly whether an open attempt stays finishable (idea file open question).

## 2. Access ended while mid-course

- Moodle self-enrolment with a duration: students expired after 14 days and were locked out, yet still appeared on the enrolled list, so they could not self-enrol again; admin workaround was manual unenrolment of expired users. https://moodle.org/mod/forum/discuss.php?d=218183 (via search summary; thread number as returned)
- Moodle helpdesk "Known Issue: students enrollment automatically expires": an end date on an individual enrolment or on the enrolment method silently removes access, and staff must hunt through Participants to find the cause. https://vcc.teamdynamix.com/TDClient/50/Portal/KB/Article/276/KB1157-Known-Issue-Students-enrollment-automatically-expires
- Integration complaint (Axcelerate): re-enrolling a student in a new class reports "already enrolled" and keeps the old dates, leaving them locked out until someone edits the dates by hand. https://support.axcelerate.com.au/hc/en-gb/community/posts/202329644-moodle-elearning-enrolment-dates
- WordPress/LearnDash style: expired learners are sent to a purchase page; progress is retained but inaccessible. https://whitelabelcoders.com/blog/what-is-the-best-way-to-handle-course-access-expiry-in-a-wordpress-lms/

Bearing on the spec: the lock-out is not the main grievance; the grievance is the mismatch between "listed as enrolled" and "cannot enter", and a restore path that is blocked by the existing record. The idea file's choice (registration stays active, dashboard shows "access ended", only staff restore) matches the first; the dashboard label is what stops the mismatch.

## 3. Progress loss on restore or re-enrol

- Moodle: unenrolment removes grades; they come back only if "recover old grades" is ticked, and forum subscriptions reset and grade-based completion dates can reset to the re-enrolment date. Last access can show "never". https://docs.moodle.org/503/en/Unenrolment
- Teachable (secondhand): resetting progress goes through the school owner; deleting and re-enrolling a student is a quoted workaround. Thinkific (single anecdote): an admin could not change progress or completion. https://community.gamedev.tv/t/reset-course-videos-to-unwatched/224685 ; https://codecrew.codewithchris.com/t/is-it-possible-to-reset-a-course/15486
- Contrast, praised by help articles: "Reactivate enrolment" continues from previous progress (Group.app); LearnWorlds keeps progress, scores and completion after expiry and restores them on re-enrol. https://help.group.app/en/articles/235-manage-learner-course-access-and-progress ; https://support.learnworlds.com/support/solutions/articles/12000041927-how-to-set-up-a-product-expiration-date
- One LMS warns that "Restart Course" wipes progress, recoverable only by an admin reactivating the session. https://intercom.help/alison-lms/en/articles/16096970-managing-learners-access-deactivation-and-reactivation
- A new enrolment can make the old one inactive; whether the learner resumes or restarts depends on the platform. Same Alison article.

Bearing on the spec: restoring the same registration with a new window (not a new registration) is the pattern that avoids Moodle's side effects (completion dates reset, subscriptions reset). Spec should state that completion dates and progress timestamps are untouched on restore.

## 4. Hidden consequences and unclear precedence between layers

- Canvas: "Available until" is the real cutoff but many instructors do not know; a section end date earlier than the quiz Until date silently cuts students off; section overrides may need their own availability dates. Precedence was not confirmed in official docs by the search; users infer "earliest applicable date wins". https://support.csuchico.edu/TDClient/1984/Portal/KB/Article/113763/Students-are-Prematurely-Kicked-from-a-Quiz-in-Canvas ; https://sites.usask.ca/gmcte/2020/10/06/understanding-canvas-classic-quizzes-timer-availability-and-accommodation-settings/
- Canvas guidance: a quiz with a due date and an Until date is marked late at the due date and auto-submitted at Until; the two-stage consequence is documented only in guides. https://wps.freshservice.com/support/solutions/articles/18000103489
- Moodle: an enrolment end date can sit on the individual enrolment or the method, and the admin must open Participants to find which (see section 2).
- Carried from the sentiment file: Docebo soft deadline silently suppressing a notice; Open edX relative-date setting enabled site-wide but not appearing. These are the closest evidence for "admin cannot tell why a thing did or did not happen".

Bearing on the spec: no source asked for "show which layer set this value", but every precedence complaint above is a case where the effective value had no visible origin. In the Django admin, show the resolved value and its source layer for a course or registration. This is design judgement from adjacent evidence (WEAK as demand, MODERATE as pattern).

## 5. Timezone boundaries (new evidence only)

- Canvas "Until" and section end dates are enforced at an exact time with no grace; the Chico article shows the cut-off arrives mid-attempt. Combined with the sentiment file's 11:59 pm and unlabelled-zone findings, the failing case is a boundary instant seen in a different zone. Nothing new on DST beyond sentiment (g).

## 6. Notification noise tied to consequences

- No new threads beyond the sentiment file (Edinburgh, Sussex, MSU, Docebo). The point relevant here: spec 2 only records "notify educators"; the complaint evidence says the setting needs a clear scope (overdue only, not after completion) when spec 5 raises it.

## Implications for decisions in this spec

1. In-progress form attempt at close: STRONG that silent cut-off is a complaint (several Canvas threads, university KBs). Decide it explicitly and show the learner a warning before the date. If the attempt is allowed to finish, state its limit (grace window). If not, define the staff route to reopen it.
2. Grace window: MODERATE support that the window should be visible to learners next to the date, and that it should apply identically to closing and ending (Canvas Until vs. due split confuses instructors).
3. Ending access: keep the registration listed with a visible "access ended" state. MODERATE (Moodle list/lock-out mismatch).
4. Restore: reopen the same registration, new window, untouched completion timestamps. MODERATE (Moodle docs side effects vs Group.app/LearnWorlds praise). Single-record restore avoids "already enrolled" lock-outs.
5. Precedence: use one documented rule (most specific wins, as in the idea file) and surface the source layer in the admin. WEAK-to-MODERATE.
6. Override interaction: an extra-time allowance must move the close date too (Canvas timer vs lock date). Matches sentiment implication 3.
7. Silent failure of enforcement is also a complaint (Canvas non-auto-submit). Enforcement on read, as the idea file chooses, avoids this class.

## Sources not reached

Reddit, G2, Capterra deadline-specific reviews, Thinkific and Teachable community threads.

status: ok · reason: web research complete for Canvas, Moodle, access-expiry and restore; Reddit/G2 not reachable; layer-visibility complaint not found directly
