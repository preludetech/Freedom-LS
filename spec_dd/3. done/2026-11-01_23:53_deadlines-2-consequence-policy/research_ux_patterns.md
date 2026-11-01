# Research: UX patterns for deadline consequences and layered policy configuration

Topic `ux_patterns` for the deadline consequence policy spec. Scope: how a learner sees late, closed and ended; what a closed item allows; how the Django admin shows inherited vs overridden policy values.

## Evidence base and limits

- Web evidence is thin. Canvas and Moodle are documented, but the exact learner wording after a cut-off is not on the pages I could read. Findings marked (practice) come from instructor syllabi, not product docs.
- The FLS template survey was shallow. A grep of `freedom_ls/learner_interface/templates/` found no deadline or lock markup in the dashboard, course card, or the TOC. The only lock-like markup is in `course_form_page.html`, where locked form pages render as a non-link `<span>` and reachable ones as `<a>`. `cotton/course-card-shell.html` exposes an `eyebrow` slot, documented as "e.g. status label". The player's lock message and the TOC status partial were not located. The spec author should read those two files before fixing component names.
- `spec_dd/1. next/learner-interface-design-deadlines/idea.md` is one line: deadline and window blades "don't look very good", improve with the design tool. That work is visual polish. The consequence wording below is meant to slot into whatever it produces.
- Voice (`.claude/skills/brand-guidelines/voice.md`): direct, specific, no SaaS phrasing. Error-style text names the problem, suggests the fix, leaves blame out, and ends on a full stop. Learner-facing UI carries the organisation's brand. Use "learners", never "students".

## 1. Patterns for showing a consequence next to a date

### What other systems do

- Canvas: a soft deadline plus a hard deadline. Work submitted in the grace window is flagged "late" with no grade penalty. The activity closes at the hard deadline. The "late" label cannot be turned off (the sentiment file, section a, records the complaint). Sources: https://community.canvaslms.com/t5/Canvas-LMS-Blog/Use-the-Canvas-Grace-Period/bc-p/274739 (practice: instructor syllabi such as https://3764su16.tracigardner.com/policies/late-policy/).
- Moodle: separate "Due date" and "Cut-off date". Moodle's own settings text says "Submissions are still allowed after this date but will be marked as late" for the due date. For the cut-off it says that after this date the submit button is hidden. Source: https://docs.moodle.org/en/Assignment_settings. Moodle explains the consequence at the setting, and the learner sees it as an absent button. The page does not say whether a message replaces it.
- Takeaway: both systems separate three states: on time, late but open, closed. Neither labels the closed state well to the learner, which is the gap FLS can fill.

### Recommended pattern for FLS

Put the consequence in the same line as the date, as a second clause, not in a separate banner. One sentence per state, in a fixed order: date, then what happens.

| State | Learner sees (suggested copy) | Treatment |
|---|---|---|
| Before due date, consequence is close | "Due 12 Mar. Closes 14 Mar." | neutral text |
| Before due date, policy is overdue-only | "Due 12 Mar." | neutral; do not promise anything the policy does not do |
| Past due, inside grace window | "Overdue. Closes on 14 Mar." | warning tone; the "closes on" date is the load-bearing part |
| Past due, no closing consequence | "Overdue since 12 Mar." | warning tone; stays open |
| Closed | "Closed on 14 Mar. You can no longer start this." | muted, with a lock icon and text (never colour alone) |
| Course access ended | "Access ended on 30 Jun." | course-level state, see section 3 |

Rules that follow from the research:

1. Always state the date of the next consequence ("Closes on …"), not only the current state. This addresses the sentiment-file finding that invisible consequences are what users complain about.
2. Say "overdue" inside the grace window, but also say it is still open. Canvas's "Late" inside a grace window with no way to hide it is the cited complaint. Because the policy can switch mark-overdue off, the label must be a conditional, not hard-coded. When mark-overdue is off but closing is on, show only "Closes on 14 Mar." with no overdue wording.
3. Use distinct words for the three states and do not reuse them: "Overdue" (past due, still open), "Closed" (an item, cannot be opened), "Access ended" (a course). Do not use "locked" for closed items. "Locked" already means "not reached yet" for prerequisites and form pages, and mixing the two confuses learners.
4. Dates render in the learner's timezone with the site's date format. A relative hint ("in 2 days") may sit in a `title` attribute only, so the absolute date is the primary text.
5. Text plus an icon, not colour alone (accessibility).

### Placement

- Table of contents row: right-aligned secondary line under the item title, beside the existing status marker. A closed item loses its link, matching the form-page `<span>` convention above.
- Item page header: under the title, in the slot that spec 1 uses for the due date. The consequence rides in that same element so there is one place to change.
- Dashboard course card: use the `eyebrow` slot of `course-card-shell` for course-level status ("Access ended"); keep per-item overdue out of the card.
- One shared template partial, fed by the single decision object the spec already requires ("one decision the player and TOC both read"), so the three surfaces cannot disagree.

## 2. What a learner sees on a closed item

Settled by the idea: completed items never close, and results pages and `form_submit_and_exit` stay ungated.

Practice elsewhere:
- Moodle hides the submit button after the cut-off, so the page stays viewable and only the action disappears.
- Canvas closes the submission but keeps the assignment and its submission viewable (practice).

Recommended:
- A closed, not-started item opens to a short explanation page instead of a 404 or silent redirect: "This item closed on 14 Mar. Ask your educator if you need more time." plus a link back to the course outline. It follows the voice rule: name the problem, suggest the fix, no blame.
- Learning content (a topic with no action to take) arguably does not need to close; the idea says closing applies to item due dates, so leave the choice of which item types close to the spec. Flag it as a question rather than assume.
- A completed item keeps its normal view and shows no closed badge. Do not show "Closed" on something the learner finished; show their completion.
- In-progress form attempt: the idea leaves this open. The least surprising UX is to let a started attempt be finished and submitted, with a note ("Closed on 14 Mar. You can finish this attempt."), because blocking mid-attempt loses work and reads as punitive. If the spec decides otherwise, the copy needs to say answers are saved but cannot be submitted. This is a product decision; recorded here as the lower-regret option, not a settled one.
- Items inside a closed item's parent keep their own state; do not cascade closed visually.

## 3. Distinguishing late, closed and ended

- Three different levels: item overdue (label), item closed (item-level block), course access ended (course-level block). Keep the vocabulary strictly separate (section 1, rule 3).
- Ended access does not set `is_active=False`, so the course must still appear on the dashboard. Pattern: the card stays in its normal place but renders in a muted state with the eyebrow "Access ended on 30 Jun." and no "Continue" action. Progress and completion are still shown, since progress is kept.
- Clicking an ended course: land on a course page that shows the ended message and the learner's progress, not an error page. Copy: "Your access to this course ended on 30 Jun. Your progress is saved. Contact your educator to get access again." This matches decision 8 (only staff restore) and avoids implying a self-service way back. Do not show a "Register again" button.
- Ended is not shown inside the grace window; the course-level text reads "Access ends on 30 Jun" before and "Access ended on 30 Jun" after, using tense to separate them.
- Where "access ended" is enforced decides who still sees a hidden course (an open question in the idea). From the UX side: an ended course must still show on the dashboard, so the enforcement approach must give the dashboard a way to read "ended" without treating the course as unregistered.

## 4. Showing inherited vs overridden values in the Django admin

Evidence: the web search found no standard Django admin pattern for this. Django's own tickets show only that help text and read-only overrides are awkward (https://code.djangoproject.com/ticket/9321, https://code.djangoproject.com/ticket/31656). The best analogue is GitLab's cascading settings, where a value inherits from ancestors, can be locked from above, and the UI shows the locked state as a disabled control (https://docs.gitlab.com/development/cascading_settings/). I could not confirm GitLab's exact label wording. So the following is design recommendation, not a documented convention.

The policy rows have "unset" markers and a missing row inherits. Recommendations:

1. Make unset a visible, first-class choice. Every non-flag field uses a three-way select: "Inherit" (the default), then the real values. Flags use a nullable select: "Inherit / Yes / No". A plain checkbox cannot express unset, so avoid it.
2. Show what inheriting will give. Next to each field, render the resolved value and its source layer as help text or a read-only column: "Inherits: 2 days, from organisation 'Acme'." This is the single most useful thing; without it an admin has to open four other rows to know the effect.
3. A read-only "Effective policy" panel on each policy change page and on the registration, course and cohort pages that link to it: a small table with columns Setting, Effective value, Set at (site, organisation, cohort, course, registration). Build it from the same resolver the enforcement uses, so the display cannot drift from behaviour (the same single-source principle as the TOC and player).
4. Changelist columns: show the layer, the target (organisation or course name), and which settings the row overrides, as text such as "grace window, close". A row that overrides nothing is a candidate for deletion; flag it.
5. Visually separate overridden fields on a change form (a "Overrides" fieldset first, or bold labels when not "Inherit") so an admin sees at a glance what this row does.
6. Validation: reject a row whose layer and target do not match (a cohort-layer row without a cohort), and a row with no layer set. Messages follow the voice rule: name the problem, suggest the fix.
7. Read order: most specific wins, so the panel lists layers in resolution order, registration first. State the order in the admin help text once, because the course-versus-organisation order is still an open question in the idea. Whatever the spec decides, the panel should print the order it uses.
8. Admin-only configuration (settled): do not add educator-facing editing. Under the FLS admin conventions, follow `fls-dev:admin-interface` (not read here).
9. Do not lock values from above. GitLab-style enforcement ("organisation forces this on all cohorts") is not in the idea; mention it only as a possible follow-up so it does not creep in.

## 5. Open questions this research surfaces for the spec

- Which item types close (any item with a due date, or only forms and action items).
- Whether a started form attempt can be finished (section 2 recommends yes; product decision).
- Exact wording and component names, to be checked against the TOC status partial and player lock message, which I did not find.
- Whether "overdue" is shown inside the grace window when mark-overdue is off (recommended: no).
- Where the "Effective policy" panel is placed beyond the policy page itself.

## Sources

- Canvas grace period: https://community.canvaslms.com/t5/Canvas-LMS-Blog/Use-the-Canvas-Grace-Period/bc-p/274739
- Instructor practice with Canvas grace period (syllabus): https://3764su16.tracigardner.com/policies/late-policy/
- Moodle assignment settings (due date, cut-off): https://docs.moodle.org/en/Assignment_settings
- GitLab cascading settings: https://docs.gitlab.com/development/cascading_settings/
- Django admin help text tickets: https://code.djangoproject.com/ticket/9321, https://code.djangoproject.com/ticket/31656
- Local: `spec_dd/2. in progress/deadlines-2-consequence-policy/idea.md`, `spec_dd/1. next/learner-interface-design-deadlines/idea.md`, `.claude/skills/brand-guidelines/voice.md`, `freedom_ls/learner_interface/templates/cotton/course-card-shell.html`, `freedom_ls/learner_interface/templates/learner_interface/course_form_page.html`

status: ok
