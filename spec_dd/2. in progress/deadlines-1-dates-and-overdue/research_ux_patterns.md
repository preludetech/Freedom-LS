# Research: UX patterns for due dates, overdue and time limits

Scope: the four learner surfaces (table of contents, overdue mark, course detail time-limit end, dashboard course card) and the admin override entry. Competitor behaviour below is from memory of the products plus the sources in References; where a search could not confirm a detail, it is marked "unverified".

## 1. What other systems do

| System | Date format | Overdue treatment | Card / list summary | Time zone |
|---|---|---|---|---|
| Canvas | Absolute ("Due Oct 30 at 11:59pm") in lists; relative only in To Do ("Due Tomorrow"). | "Missing" and "Late" text labels beside the item, red text. | Dashboard card shows nothing per-item; the To Do sidebar lists next due items. | Shown in the viewer's own profile zone; many forum threads show confusion when browser, app and course zones differ. Users ask for the zone beside each date. |
| Moodle | Absolute ("Friday, 30 October 2026, 11:59 PM"), plus relative "Assignment is due in 3 days" on the activity page and "Overdue" in red on the timeline block. | Timeline block groups "Overdue"; activity page says "Assignment was due 2 days ago" (unverified exact wording). | Timeline block, not the course card. | User profile zone. |
| Open edX | Dates tab is a vertical list by date, with badges "Due", "Completed", "Past due", "Today". | "You are behind / missing deadlines" banner above the Dates tab with a "Shift due dates" button (self-paced courses). Source: `dates_banner.html`, `missed_deadlines` flag in the Dates API. | Outline shows "Due Oct 30, 2026" under each subsection. | Shows the learner's zone, and the course outline labels dates with the zone abbreviation. |
| Coursera | Absolute short form ("Due Oct 30, 11:59 PM PDT") in the item list, with the zone abbreviation; deadlines are suggested, and a "Reset deadlines" action sits on a missed-deadline notice. | Soft: "Deadline passed" style notice, not alarming. | Course home shows the next deadline and a banner when behind. | Learner's browser zone with abbreviation. |
| Google Classroom | Relative-first ("Due tomorrow", "Due Oct 30"), "Missing" and "Done late" as text labels. | "Missing" in red text on the To-do page, grouped under "Missing". | Card has an "Upcoming" line; not per-item. | Local time, zone not labelled. |
| TalentLMS, LearnDash | TalentLMS shows a "Due in N days / Overdue" chip on the course tile and a "Time limit" on the unit; LearnDash shows a "Due date" line on the course and lesson list and "Overdue" text (mostly via add-ons). | Chip with text. | TalentLMS: one chip per course tile. | Site/user zone, mostly unlabelled (unverified). |

Cross-cutting patterns:

- **Absolute date is the source of truth; relative text is a supplement.** Every system that shows only relative text ("tomorrow") gets complaints once the page is read the next day, and every system that shows only a date forces mental arithmetic. Most pair them: absolute in the list, relative in the summary ("Due in 3 days").
- **Overdue is a text label first.** Canvas, Classroom and Moodle all write "Missing", "Late" or "Overdue"; red is reinforcement.
- **Time zone is the commonest complaint.** The fix is to print the zone beside the time (see the idea's "every date shown names its time zone").
- **Cards summarise, lists detail.** No competitor puts per-item dates on a course card. They show one of: next due date, a count of overdue, or a single chip. The idea's open question (several overdue items on one card) is best answered with a count plus the earliest overdue item.
- **Time limits are shown as an end date, with a countdown only when near.** Coursera/TalentLMS show "Ends Dec 1"; countdowns ("12 days left") appear as the supplement. A live ticking countdown is used only for timed exams, not for course windows, so it is not suitable here (and it is a poor screen-reader experience).
- **Open edX's "missed deadlines" banner** is a page-level summary above the list with a count, which is the useful part. Its "shift dates" button is a consequence (spec 2/3), not for this spec.

## 2. Accessibility (WCAG 2.2)

- **1.4.1 Use of Colour:** overdue must carry visible text ("Overdue") and an icon; colour only reinforces. The project already states this rule in `course_status_eyebrow.html`.
- **1.4.3 Contrast:** brand file says Forest and Sand are background-only; Signal (`text-error`) on white must be checked, and a `-light` pair is the documented route for status text on a tint. The current TOC badge uses `text-warning` (Sand) as text, which fails contrast; do not carry this over.
- **`<time datetime>`:** use `<time datetime="2026-10-30T23:59:59+02:00">30 Oct 2026, 23:59 SAST</time>` so assistive tech and browsers can parse it; keep the visible text human.
- **Screen readers:** icons `aria-hidden`; the word "Overdue" is real text or `sr-only` that reads in sequence ("Due 30 Oct 2026, 23:59 SAST. Overdue."). Do not rely on `title` (the old badge does; it is unreliable on touch and keyboard).
- **Relative text and live regions:** no auto-updating countdown. Relative text is computed at render; it goes stale on a long-open page, so always keep the absolute date next to it.
- **Forced-colours mode:** `c-panel-status-badge` already keeps the badge legible; prefer it.
- **Dates in compact rows:** a truncated TOC row must not truncate the date or the overdue label (the row title is `truncate`, the date column is `shrink-0`; keep that split).

## 3. Project conventions found

- **TOC** (`freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`): `deadline-badges` partial renders `{{ dl.deadline|date:"d M" }}` with a `deadline` icon, `text-error` or `text-warning`, and `title="{{ dl.source }}"`. It has no year, no time, no zone, no overdue text, no `<time>`, and `text-warning` as text. Status icon partial already uses `sr-only` text (Locked, Not started...). This partial is removed with the old implementation, so the replacement is a fresh `partialdef`, kept at the `shrink-0` right-hand column in all three call sites (course part header, nested child, plain item).
- **Dashboard card** (`partials/course_card.html`, `course_status_eyebrow.html`): the eyebrow is "the single place status is ever shown; no duplicate chip/badge". An overdue chip would break that comment's rule, so overdue sits in the body (next to "Next up:"), not as a second status chip. The card already has a `Next up:` line (`text-sm text-muted`) that a "Next due" or "N overdue" line can follow.
- **Icon:** `deadline` is a clock-style icon already used for "Coming soon" in the eyebrow, for Duration on `course_detail.html` (line 117), and in `403_csrf.html`. Reusing it for overdue loses the distinction; for overdue use it with the word "Overdue", or choose another existing icon name in the set. The name stays regardless (idea).
- **Brand:** `Overdue` is named in the brand file as an example of a status badge, so use `<c-panel-status-badge tone="error" label="Overdue">`, which is legal on learner-facing views. A non-status due date label is plain muted text, not a chip. Voice: direct, brief, no SaaS phrasing; "Overdue", not "You've fallen behind!"; error-ish copy names the fact and the next step.

## 4. Recommendations by surface

### 4.1 Table of contents (per item)
- Right-hand column per row: `<time>` with absolute short date, time and zone abbreviation, e.g. "Due 30 Oct 2026, 23:59 SAST". Include the year (the old `d M` is ambiguous across a year boundary and for a long course). Muted text by default.
- Relative text ("in 3 days") only as a second muted line or on hover/focus is optional; the minimum is the absolute form. If used, absolute stays visible.
- Overdue: an incomplete item past due gets `<c-panel-status-badge tone="error" label="Overdue">` plus the date in `text-error`. A completed item shows no overdue mark (idea); it may show the date in muted text, and no due date for a Completed row keeps the list quiet.
- A course-part (group) row shows no date of its own unless the part has one; do not roll up child dates into it, but an "N overdue" count on a collapsed part is worth a short note for the spec: a collapsed part otherwise hides overdue children from the learner.
- Fixed versus offset dates look the same to the learner: both resolve to a date. Do not show "30 days after registration" as the primary text; it can sit in `title`-free secondary text on the detail page if at all.

### 4.2 Overdue mark
- Text + icon + colour, all three. Text "Overdue" is mandatory. Pair with `aria-hidden` icon; colour from `error` / `error-light` tokens, never raw hexes.
- One word, no exclamation, no blame. Do not use "Late" (suggests submitted), and do not use "Missed", which implies it is closed; overdue is shown, not enforced (idea).

### 4.3 Course detail (time limit end)
- Show the end as an absolute date and zone in the existing stat-style row (the `Duration` stat uses the `deadline` icon): label "Course ends" or "Finish by", value `<time>` with zone. Use a relative supplement ("12 days left") only when under ~14 days; no ticking countdown.
- Label the time limit in the learner's terms: "Finish by 30 Nov 2026, 23:59 SAST", with the offset ("60 days from registration") as help text if the offset is the only thing authored, since it shows why the date is what it is.
- Past the end: the same text turns to "Time limit ended 30 Nov 2026" with the Overdue badge; nothing closes in this spec.
- Course detail also lists item due dates in its TOC; the 4.1 partial is reused unchanged so the two surfaces stay identical.

### 4.4 Dashboard card
- One card per course. Use the Classroom/Coursera approach: one line, not a list. Priority:
  1. Any overdue incomplete items: `<c-panel-status-badge tone="error" label="2 overdue">` in the card body (below the title, above Next up), singular "1 overdue". Linked to the course home so the learner lands on the TOC.
  2. Otherwise the next due date: muted "Next due 30 Oct, 23:59 SAST" (with `<time>`).
  3. Course time limit end only if no item date is nearer, same format; or when the limit is past, "Time limit ended".
  4. Neither: nothing, so the card stays quiet for courses without deadlines.
- Do not add a second status chip in the eyebrow slot (its comment forbids duplication); keep the eyebrow as the progress status only.
- Do not list item names; if a name is wanted, show only the earliest overdue item's name in "Next up"-style text.
- Complete courses show no overdue or due line.
- Card footers already carry the progress bar; the summary line goes above it to avoid a crowded bottom edge.
- This needs the `CourseListingEntry` to carry an overdue count and a next-due datetime (see the idea's open question); not a per-item list.

### 4.5 Dates everywhere (shared rules)
- One template tag or partial for "date with zone" used by all four surfaces so the format cannot drift. Format: `30 Oct 2026, 23:59 SAST` (day-month-year avoids the US/UK ambiguity; zone abbreviation from the site's time zone, with the IANA name in a `title`-independent place such as the detail page help text).
- The abbreviation (SAST, GMT) is ambiguous in some zones (CST); render the numeric offset in the machine `datetime` attribute and the abbreviation or "UTC+2" visibly.
- Midnight default: the idea settles "end of the day in the site's time zone". Show "23:59" rather than "00:00 the next day", so "due 30 Oct" does not read as 29/31 Oct (the Canvas 11:59 PM convention).

### 4.6 Admin: entering and reading overrides (Django admin)
- Common pattern (Moodle "Override" per user/group, LearnDash/TalentLMS per-user due date): an override row beside the default, with the default shown read-only so staff can compare.
- Entry: two mutually exclusive inputs, "Fixed date" (datetime) and "Days after registration" (positive integer), with help text and `clean()` that rejects both or neither. Name the unit in the label ("days after registration", not "offset"). Show the site time zone in the datetime field's help text.
- Show the **resolved** date as a read-only column/field ("Effective due date: 30 Oct 2026, 23:59 SAST, from: learner override") on the changelist and the change form, so staff see the result without computing it. This also gives a "source" display that the old `title="{{ dl.source }}"` aimed at.
- Follows-default indicator: a read-only column "Follows default" yes/no (or "Default now: 14 days, override: 21 days") with a text badge, not colour alone. If the spec decides overrides are snapshots, show the default at the time of override next to the current default and flag a mismatch with a text note ("Default has changed since this override was set"). This answers the sentiment file's implication 4.
- Record actor and reason (open question in the idea) with read-only "set by / set on" and a required or encouraged "reason" text field; the changelist should show them.
- Admin list filters: "has override", "overridden by layer". Stay inside `fls-dev:admin-interface` conventions.

## 5. Risks to carry into the spec
- Truncation of the TOC row on narrow screens: the date column must wrap or stack, not clip.
- Stale relative text on long-open pages.
- Dates with zones that differ from the learner's local clock; the idea says no user zone field, so the label is the only mitigation.
- A learner in two organisations (separate deadlines): the card summarises only the governing registration.

## References
- Open edX Dates banner template: https://code.vt.edu/hsinyu/edx-platform-release/-/blame/514d10599df8dbbe16c032cd8347c1a1e8c5eb82/lms/templates/dates_banner.html
- Open edX "Dates Tab Added As Default for All Courses": https://discuss.openedx.org/t/dates-tab-added-as-default-for-all-courses/7849
- Open edX shift-dates and missed-deadlines commit: https://git.andalsoftware.com/Andal.LND/edx-platform/src/commit/4230f1fb3922a2df3e86b8789b4cd677dfdf4b1d
- Canvas due date time zone discussion: https://community.canvaslms.com/t5/Canvas-Question-Forum/Clarification-Needed-on-Due-date-Time-Zones-in-Canvas/m-p/647880
- Canvas app vs desktop due date mismatch: https://community.canvaslms.com/t5/Canvas-Mobile-Forum/Different-Time-Zones/m-p/604638
- WCAG 1.4.1 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- HTML `<time>` element: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/time
- Project: `.claude/skills/brand-guidelines/visual.md`, `.claude/skills/brand-guidelines/voice.md`, `freedom_ls/learner_interface/templates/learner_interface/partials/course_minimal_toc.html`, `partials/course_card.html`, `partials/course_status_eyebrow.html`, `course_detail.html` (line 117), `freedom_ls/base/templates/403_csrf.html`
- Not fetched, from general knowledge only (unverified details): Moodle timeline/activity dates, Coursera, Google Classroom, TalentLMS, LearnDash.

status: ok
