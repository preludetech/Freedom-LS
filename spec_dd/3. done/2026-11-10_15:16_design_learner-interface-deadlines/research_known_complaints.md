# Research: known complaints about learner-facing deadline display

Scope: dashboard course-card deadline band, course player outline next-deadline card, inline coloured/iconed outline dates, body-header deadline card (see idea.md).

Method and confidence: web search summaries only; pages were not fetched in full, so quotes are paraphrases of search-result summaries. Evidence is anecdotal forum material, not research. Gaps are stated per item. Reddit and app-store reviews did not surface in searches; no claims are made from them.

## 1. Timezone confusion / missing timezone label
- Evidence: Canvas students report the dashboard showing a deadline in another zone (e.g. New York), then being locked out of submitting. Others missed assignments because the mobile calendar showed EST. Students ask for "10 p.m. EST" instead of "10 p.m."; one notes "DUE: 11:59 PM" with no zone. An idea to auto-adjust to user location was archived ("will not explore at this time").
  - https://community.canvaslms.com/t5/Canvas-Mobile-Forum/Calendar-time-zone-issues/m-p/563191
  - https://community.canvaslms.com/t5/Idea-Conversations/Automatically-adjust-timezone-based-on-user-location/idc-p/444931
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Clarification-Needed-on-Due-date-Time-Zones-in-Canvas/m-p/647880
  - https://community.canvaslms.com/t5/Canvas-Mobile-Forum/Different-Time-Zones/m-p/604638
- Moodle keeps a regression test that the timeline block's due time matches the activity page after the user changes profile timezone: https://tracker-old.moodle.org/browse/MDL-63044
- Implication: render in one resolved learner timezone everywhere (card, band, row, header must all agree); show the zone (abbreviation) at least where the exact time is shown, e.g. in the header card and tooltip; never mix site-zone and user-zone; test that the same instant renders identically on every surface.

## 2. Surface mismatch (web vs mobile app, list vs detail)
- Evidence: Canvas "Due Dates Differ between Website and App"; changing account timezone fixed desktop only. https://community.canvaslms.com/t5/Canvas-Mobile-Forum/Due-Dates-Differ-between-Website-and-App/m-p/455838
- Implication: one shared formatter/template component for all four surfaces plus the tablet/mobile outline sheet; no per-surface date logic.

## 3. Ambiguous cut-off time (midnight / 11:59pm)
- Evidence: an instructor reports many students read 12:00am as noon, so deadlines were set to 11:59pm instead (Canvas community, via https://community.canvaslms.com/t5/Canvas-Question-Forum/Assignment-submitted-on-due-date-time-marked-as-late/m-p/511838 and related late-label threads). Canvas course pages also lacked full dates on Modules (idea: https://community.canvaslms.com/t5/Canvas-Ideas/Pages-Display-full-dates-consistently-across-all-course-pages/idi-p/651688).
- Implication: use 24h or explicit "12:00 AM"/"end of day" wording consistently; avoid showing bare dates when the time matters; show time in header card (full precision) while band/rows can show date only if the time is the same default.

## 4. Late/overdue shown wrongly (on-time, completed, or ungraded items)
- Evidence: Canvas threads of on-time submissions flagged late; LTI submissions flagged late using grading date rather than submission date; "Incorrect late notice showing".
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Assignment-submitted-on-due-date-time-marked-as-late/m-p/511838
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Google-Submission-Marked-Late/m-p/408365
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Incorrect-Late-notice-showing/td-p/215583
- Moodle: overdue handling in the timeline ignored items overdue "today" (MDL-72594) and the Dashboard caps overdue look-back at 2 weeks. https://tracker-old.moodle.org/browse/MDL-72594 ; https://docs.moodle.org/503/en/Timeline_block
- Gap: I found no direct source for "completed item still shown overdue" in Moodle; treat as plausible, unverified.
- Implication: completed items must drop out of the next-deadline card, band and "late" styling and show a neutral completed state; overdue = past deadline AND not complete, evaluated on the same instant/boundary as the server; "due today, now past" must read as overdue.

## 5. Items never appearing / wrong "next" item
- Evidence: Canvas students missed work because some item types never reached the To-Do list (idea later deployed); course copies left stale dates so items did not appear. https://community.canvaslms.com/t5/Canvas-Ideas/Put-everything-with-a-deadline-into-the-to-do-list/idi-p/304836 ; https://community.canvaslms.com/t5/Archived-Questions/ARCHIVED-Days-missing-from-To-Do-List/m-p/193334 ; https://community.canvaslms.com/t5/Canvas-Question-Forum/Student-To-Do-List-not-being-properly-populated/m-p/631961
- Implication: next-deadline card must draw from every deadline-bearing content type (and cohort/course deadlines) with one query definition shared with dashboard band and outline rows; define tie-break and what shows when none exist (explicit empty state, not blank).

## 6. Truncation / hidden behind clicks
- Evidence: Moodle timeline shows only 5 activities per course, oldest first, behind "Show more activities". https://docs.moodle.org/404/en/Timeline_block
- Implication: put the single most urgent deadline on the surface without a click (band, top-of-outline card, header card); the idea's "keep text to a minimum" must not drop the date itself; verify short strings on the mobile outline sheet and narrow cards (no clipped dates; truncate titles, never dates).

## 7. Red/alarm overload and colour-only signalling
- Evidence: Sakai SAK-40566: due date in red as the only indicator of lateness; fix proposed was the word "(late)". Agilix BUZZ: a red-green colour-blind student could not distinguish grades/due dates; vendor uses a clock icon. WCAG 1.4.1 forbids colour as sole carrier of meaning.
  - https://sakaiproject.atlassian.net/browse/SAK-40566
  - https://support.agilix.com/hc/en-us/community/posts/10824925928596-Color-Blind-Settings
  - https://www.utmb.edu/accessibility/digital/100-days-of-a11y/100-days-article/days-of-a11y/2024/04/29/day-20--indicating-meaning-with-color
- Gap: no source found specifically on "alarm fatigue" from too many red items in an LMS; the point below is design reasoning.
- Implication: every state (upcoming, due soon, late, done) needs icon + short word or shape in addition to colour, with sufficient contrast; reserve the strongest (red) state for genuinely overdue incomplete items, keep upcoming neutral, so a long outline is not a wall of red; provide accessible text (aria/visually hidden) for icons.

## 8. Soft vs hard deadlines unclear; self-paced reset confusion
- Evidence: Coursera/DeepLearning.AI learners: deadline showing as a negative value with no clear way to reset; reset option appearing late; resetting removed submissions; automatic reset then nagging. edX shows "shift due dates" only after a suggested date is missed. https://community.deeplearning.ai/t/cannot-reset-deadlines-for-course-3-dls/155009 ; https://community.deeplearning.ai/t/resetting-deadline-removed-quiz-and-home-submissions/7643 ; https://community.deeplearning.ai/t/my-compleated-assignments-disappeared-with-no-warning-after-deadline-reset/5861 ; https://support.edx.org/hc/en-us/articles/206501098-I-can-t-make-a-deadline-can-I-get-an-extension ; https://blog.coursera.org/improvements-to-sessions-experience-for-learners/
- Implication: if FLS has deadline kinds (hard vs target/suggested), label them differently in text and icon, and use gentler "behind" styling for soft ones; do not show raw negative numbers; say what lateness means (still submittable or locked) in the header card.

## 9. Relative times going stale
- Evidence: no direct forum source found. Moodle's tracker cases on "today" boundaries (MDL-72594) are the nearest. Design reasoning only.
- Implication: if using "in 3 days"/"Tomorrow", compute server-side from the learner's local date at render, pair with the absolute date (title/tooltip or on header card), and avoid long-cached fragments; HTMX partials should recompute at request time.

## Summary of design rules for the spec
1. One shared deadline value + formatter across all surfaces; learner timezone, zone shown for exact times.
2. Completed items never styled as late; overdue = past AND incomplete.
3. Colour always paired with icon and short word; red only for overdue.
4. Most urgent deadline visible without a click; empty state explicit.
5. Distinguish hard and soft deadlines if both exist.
6. Absolute date always recoverable alongside relative text.
7. Test narrow widths: truncate titles, not dates.

status: ok
