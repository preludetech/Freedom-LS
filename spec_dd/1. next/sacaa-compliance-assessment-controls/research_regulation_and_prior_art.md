# Research: SACAA e-learning rules and LMS prior art

Date: 2026-11-26. Complements (does not repeat) `spec_dd/3. done/2026-11-24_17:39_sacaa-compliance/research_sacaa_requirements.md` (pass mark 75%, 5-year retention, CAR 141.01.17, randomisation findings).

Labels: (a) stated in regulation, (b) guidance/practice, (c) inference, (?) not found.

## 1. Source of the quoted lines

- (a) The legal hook is CAR 141.07.1 (Part 141 Subpart 7, e-Learning, inserted by R.1503 of 15 Nov 2021): ATO must be approved before e-Learning can be endorsed; course, material and assessments approved by the Director; no e-Learning aircraft-maintenance type courses above 5 700 kg MCTOW; blended learning allowed where a practical component exists; an e-Learning course on the OpSpec "shall have a skills or knowledge test ... per the e-Learning matrix in Document SA-CATS 141 ... completed in a Controlled Environment"; the e-Learning system must be "of high integrity to minimise fraud and meet the criteria set out in SA-CATS 141". https://source.acts.co.za/civil-aviation-act-2009/nr425_141_07_1_requirements_re.php
- (?) The seven quoted lines (moderation, time lapse, adequate time, minimum tutorial time, 2 min 30 s interaction, disturbance = fail, two re-writes) were NOT found in any public text. Searches on the exact phrases returned nothing. They are very likely from the SA-CATS 141 e-learning criteria / SACAA e-learning approval checklist, which is not on the public web (SACAA points to the LexisNexis legislation portal https://caa.mylexisnexis.co.za/ and the ATO mailbox peltraining2@caa.co.za, per https://www.caa.co.za/?p=3731). (c) Obtain the document from the client or SACAA before the spec is final; treat the quoted lines as client-supplied until then.
- (b) Closest public corroboration of SA-CATS 141.07.1 content: a 2024 SA Airways Technical tender annex reproducing the "SA-CATS 141.07.1 Risk Matrix" (risk categories 1 to 5). Indicative only, not SACAA's own file. https://documents.easytenders.co.za/public/tenders/2024/03/145827/blobname659d9792-a493-473c-8c36-91e3f2c4f023pdfdownloadedfilenameannexure-a-e-learning-platform-risk-matrix.pdf

### Nearby requirements the idea may have missed

From the risk matrix (b; read from the PDF image). Rows by category:
- Authentication: Cat 2 unique-password logon; Cat 3 unique password plus instructor signature and licence number on forms; Cat 4 unique password plus "rigorous/undeniable identification (biometrics / proxy controlled / controlled exam environment)", record of who took it before/during assessment, examiner signature; Cat 5 SACAA exam centre and ID on entry.
- Record keeping: Cat 2 audit trail; Cat 3 to 5 "all data kept for 5 years".
- Moderation: Cat 2 internal; Cat 3 to 5 internal moderation plus SACAA auditing.
- Assessment: random questions from a master list; Cat 2 also allows randomised question and answer order; Cat 3 adds instructor verification of knowledge during practical testing before completion of forms.
- Remediation: any incorrect answer "immediately remediated" per the online database (Cat 2 to 4); Cat 3 allows online or verbal discussion with the learner.
- Security: secure question database with annual audit of access to it; internal audit trail of results.
(c) Missed by the idea, so worth capturing: per-course risk category / controlled-environment flag; identity evidence per attempt (who sat it, examiner sign-off); immediate remediation of wrong answers (feedback with correct answer after attempt, tied to the question bank); question-bank access audit log; instructor-to-student ratio of 30 per day in a CBT environment with instructor in a support role (a: CAR 141.06.9(3) https://api.acts.co.za/civil-aviation-act-2009/nr425_141_06_9_student_to_inst.php) and 30 students per examiner per day for computer-based assessments (a: CAR 141.06.10, https://api.acts.co.za/civil-aviation-act-2009/nr425_141_06_10_student_to_exa.php). The ratios are a reporting/scheduling concern, not necessarily a hard enforcement.

## 2. "Disturbance" in online exams

- (?) No SACAA, EASA, ICAO or FAA definition found. A targeted search for EASA/ATO guidance on candidate disconnects returned only vendor and university material.
- (b) Practice in proctoring: browser "blur"/focus-loss events and switching away from the exam page are logged as suspicious (https://icie.ieseg.fr/wp-content/uploads/sites/17/2024/06/Digital-exams-chronicle-1-reducing-the-risk-of-web-based-cheating.pdf, https://formative.jmir.org/2021/8/e23834). Connection loss is tolerated for a bounded gap, e.g. Proctorio reconnects for up to 2 minutes and may invalidate the exam if unsupervised time is longer (https://library.maastrichtuniversity.nl/?p=4220915).
- (c) For this LMS "disturbance" is not defined by the quote; the spec must define it as a configurable set: explicit logout, session expiry (including the 2 min 30 s inactivity rule), server-side detection of no heartbeat beyond a threshold, and optionally focus loss/tab switch. Focus loss is noisy (notifications, OS dialogs) and the quote says "logout", so the narrowest reading is session end. Record every event with timestamp so an auditor or moderator can review a fail, and surface the policy to the learner before the exam starts.

## 3. "Minimum tutorial time"

- (?) No definition found. (c) Two plausible readings: course-total hours (matches "minimum tutorial course hours have been met and the course modules have been completed", i.e. a course-level total plus module completion) versus per-module dwell. The quote's wording favours course-total hours; per-module minimums are a client extension. Ask the client.
- (b) Evidence in other LMSs is the platform's own time counter: Moodle Lesson has a "time spent" completion condition (tracker MDL-48715, https://tracker-old.moodle.org/browse/MDL-48715); SCORM relies on `cmi.total_time`, which is unreliable on abnormal exits (https://moodle.org/mod/forum/discuss.php?d=310357). No maintained Moodle SCORM minimum-time plugin was found.
- (c) Count only active time: with the 2 min 30 s interaction rule, time is credited per interaction window, not wall clock. Store time as accumulated active seconds per learner per module, and the gate is a check of (total active seconds >= required, all modules complete) before the knowledge test unlocks.

## 4. Prior art

Moodle quiz (b, https://docs.moodle.org/en/Quiz_settings): optional time limit with countdown; "When time expires" offers auto-submit open attempts (default), grace period (can submit but not answer), or attempt must be submitted before expiry (otherwise not counted); attempts allowed with per-user/group override; enforced delay set separately for 1st-to-2nd and later attempts; review options per timeframe. The SACAA line "assess when time has lapsed regardless of questions answered" equals Moodle's default auto-submit.
Moodle regrade and broken questions (b, https://docs.moodle.org/en/Quiz_statistics_report): fix the question then regrade, "cannot be undone easily"; or award everyone the full mark by hand. That is the "moderation awarded the mark" case, and Moodle's weakness is no moderator note.
Moodle gradebook override (b, https://docs.moodle.org/en/Grader_report): overridden grades carry a flag icon. The page does not describe retaining the original or a history report. (?) from this page; Moodle's grade history tables exist but were not verified here.
Moodle course reset (b, https://docs.moodle.org/en/Course_reset): deletes user data, including quiz attempts, completion and grade overrides, "forever"; course logs survive. Moodle "recompletion" plugin by contrast clears completion but saves grades to grade history and offers archive options for quiz and SCORM attempts (https://github.com/danmarsden/moodle-local_recompletion/wiki). This is the model for "redo the course for readmission": archive, not delete (5-year retention).
Canvas (?) fudge points, quiz log (page left/resumed events) and moderated grading exist, but the fetch of the Canvas quiz-log page failed and nothing was verified for this report. Treat as unverified from memory: Canvas quiz log lists events such as page left/returned, and fudge points are a manual score adjustment on top of automatic scoring (kept separate from the question score).
Idle timeout with warning (?) Moodle session-timeout warning page not retrieved. WCAG 2.2.1 Timing Adjustable (Level A, a-equivalent for accessibility, b for this project): each time limit must be turn-off-able, adjustable to at least 10 times, or extendable with a warning and at least 20 seconds to extend by a simple action, at least 10 times. Exceptions: real-time events, "essential" limits where extending would invalidate the activity, and limits over 20 hours (https://www.w3.org/WAI/WCAG22/Understanding/timing-adjustable.html). (c) A hard 2 min 30 s auto-logout is a conflict: it fits only the "essential" exception, and only if SACAA requires it. Mitigate with a warning and a one-click "I am here" extend within the window, and accommodations for learners with documented needs (extended time with moderator note).

## 5. Implications for the LMS design

- Define "controlled environment" and a per-course risk category as data; they drive authentication, moderation and logging requirements.
- Idle rule: a per-course configurable interaction interval (default 150 s), with a warning and "still here" prompt before logout; a server-side heartbeat is the source of truth, not client timers alone. Apply a different policy in exams (any logout = fail).
- Exam attempt state machine: auto-submit at deadline scoring only answered questions; disturbance events logged with timestamps; a fail by disturbance is recorded as an attempt status, distinct from a scored fail, and counts toward the re-write limit (c, confirm).
- Moderation: never edit the learner's raw score. Store a moderation record (moderator, reason, question, mark awarded, time) linked to the attempt; display "system mark" and "moderated mark" side by side. This satisfies "marks on the system cannot be manipulated" and keeps history.
- Re-write limit: count attempts per course enrolment; after 2 re-writes (3 attempts), block the exam until the course is redone. Course redo creates a new enrolment or cycle, archiving the old one (progress, time, attempts), never deleting (5-year retention). Open question: is the limit 2 re-writes or 2 attempts in total.
- Minimum tutorial time: accumulate active seconds per module and course; gate the knowledge test on total hours and all modules complete; "except timed modules" implies a per-module flag so non-timed modules never expire.
- Configurable, not hardcoded: seconds, hours, re-write count and the disturbance event set belong in per-course settings, since the client's approved manual and SA-CATS version govern.
- Identity and examiner evidence per attempt, immediate remediation feedback, question-bank access audit log, exportable audit trail.
- Get SA-CATS 141 (e-learning matrix) before finalising; every disturbance, minimum-time and re-write detail above is inference until then.

status: ok
reason: source document of the quoted lines not publicly findable (reported as not found); regulation 141.07.1, risk matrix and prior art found with URLs; Canvas and Moodle session-timeout items unverified
