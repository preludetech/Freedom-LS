# Research: best practices for showing learners their deadlines

Scope: dashboard course-card band, course-player outline (next-deadline card + inline row dates), body-header deadline card. Deadlines may be hard or soft, per learner or per cohort, and items can be completed late. Sources were not re-fetched in this run. The recommendations come from the cited standards and guidance as I know them, so verify specifics against the URLs before treating them as quotes.

## 1. Urgency tiering
- Use few tiers. 3 to 4 visible states is the practical ceiling. More than that, learners cannot tell the levels apart, and the colour palette runs into the accessibility limits below.
- Suggested tiers (thresholds should be configurable constants, not magic numbers in templates):
  1. No deadline or far off (more than 7 days): neutral, muted. Show the date only, with no urgency styling.
  2. Upcoming or soon (within about 7 days): subtle accent, for example amber/info.
  3. Imminent (within 24 to 48 hours, or "today"): strong accent.
  4. Overdue (passed and not completed): danger styling.
- Completed items drop out of the urgency scale into a separate "done" state (see section 5).
- Thresholds are common in LMSs. Canvas To Do and Moodle's Timeline block group by "Overdue / Today / Next 7 days / Next 30 days / Later". Moodle's Timeline block filters on Overdue, Next 7/30/90 days. These groupings suit the planned grouped-list page.
- Compute the tier in one place, such as a service or template-tag function that returns (tier, date, hardness, state). Dashboard, outline and header must not each re-implement it. This also matches the project rule against repeated code.

## 2. Relative vs absolute dates
- Relative ("in 3 days", "Tomorrow") is quick to scan and conveys urgency. It is ambiguous for precise planning and goes stale in cached pages.
- Absolute ("Fri 14 Nov, 17:00") is unambiguous and is what learners plan against.
- Best practice is a hybrid:
  - Use relative wording near the deadline (within about 7 days: "Today", "Tomorrow", "in 3 days") and absolute beyond that.
  - Show the absolute date in the more detailed surfaces (header card, tooltip/title, screen-reader text).
  - In the narrow outline rows, show a short absolute date ("14 Nov") or a compact relative form ("3d"), plus a tier icon. Do not show both.
- NN/g on timestamps: relative times suit recent or imminent events, and exact dates suit anything the user must act on or compare. Include the time of day only when it matters, for example when the deadline is today or the time is not the usual end of day.
- GOV.UK writes dates in full with no ordinals and with the day name where it helps ("Friday 14 November 2025"), and times as "5pm". It avoids abbreviations in prose, which the narrow outline may need to relax.
- Overdue should read "Due 2 days ago" or "Overdue by 2 days". Do not use negative numbers.

## 3. Timezones
- Store UTC. Render in the learner's timezone (profile setting, falling back to the site timezone). Django's `timezone.localtime` and `{% timezone %}` handle this.
- Show the timezone abbreviation only where it is ambiguous or where the time of day is shown. In the header card, show "17:00 SAST" or similar once. Omitting it in the compact rows is fine if the page makes the timezone discoverable.
- Midnight cut-offs cause confusion. Prefer a visible time of day, and state "end of day" explicitly if that is the rule.
- "Today" and "Tomorrow" must be computed in the learner's timezone, not the server's. Calendar-day difference is the right measure, not 24h-hour deltas ("due in 1 day" at 23:00 for a deadline at 01:00 the next day is wrong).
- Cohort deadlines and per-learner extensions: show the effective deadline for this learner only. Never show the original deadline next to an extension without a label. If an extension exists, a short "Extended" note in the detail view is enough.

## 4. Accessibility
- WCAG 1.4.1 Use of Color (A): colour must not be the only visual means of conveying information. Every tier needs an icon shape and/or a text label in addition to the colour. Icons should differ by shape (clock, warning triangle, check, exclamation), not just colour.
- WCAG 1.4.3 Contrast (AA): 4.5:1 for text, 3:1 for large text. WCAG 1.4.11 Non-text Contrast: 3:1 for meaningful icons and the band against its background. Check tier colours in light and dark themes. Amber text on white commonly fails, so use darker amber text or put the text on a tinted background.
- WCAG 1.1.1 Non-text Content: meaningful icons need a text alternative. Decorative icons next to visible text get `aria-hidden="true"`. If the row shows only an icon plus a short date, add visually hidden text such as "Overdue, due 12 Nov".
- Use `<time datetime="2025-11-14T17:00:00+02:00">` for dates. Put the long absolute form in the visible text, or in visually hidden text when the visible text is compact. `title` tooltips alone are not accessible (no touch or keyboard access), so they are only a supplement.
- Screen-reader text should lead with the state and then the date: "Overdue, was due Friday 14 November at 5pm". Avoid reading raw ISO strings or "3d".
- Don't rely on live updates. If a client-side script rewrites relative text, don't use `aria-live`, because that spams assistive technology.
- WCAG 1.4.4 Resize Text and 1.4.10 Reflow: the compact row must still work at 200% zoom and at 320px width. Allow wrapping rather than truncating dates.
- WCAG 2.5.8 Target Size (AA, 24px) applies if the band or card is clickable. WCAG 1.4.13: any tooltip must be dismissible and hoverable.
- For a card in the body header, use real text in a landmark-friendly region, with a heading or `aria-label`, instead of a decorative banner.

## 5. States after the date passes
Model state as the combination of (completed?, completed_at vs deadline, hardness), not as a single "late" flag.

| State | Condition | Treatment |
|---|---|---|
| Upcoming | not complete, before deadline | tiered per section 1 |
| Overdue (soft) | not complete, deadline passed, still completable | danger tier, "Overdue", item remains actionable. Wording should encourage ("Still open, finish when you can"). |
| Missed (hard) | not complete, deadline passed, completion blocked or not counted | distinct from overdue: "Closed" or "Missed", no urgency pulse. It is no longer actionable, so don't keep shouting. |
| Completed on time | completed_at at or before deadline | neutral or positive check. Hide the countdown and don't show the deadline in a prominent colour. |
| Completed late | completed_at after deadline | check plus quiet "Late" marker. It must not look like an error state, because the learner has done the work. Keep it distinguishable from on-time completion (accessibility: not colour alone). |
| No deadline | none | show nothing. Do not render an empty "No deadline" in rows. |

- Hard vs soft needs a visible cue in the detailed surfaces ("Hard deadline: submissions close", versus "Target date"). In compact rows it may be shown through the icon only, if the screen-reader text states it.
- Completed items should stop contributing to the "next deadline" card and to the course-card band's urgency.
- LMS precedents: Canvas marks "Missing" (past due, nothing submitted) and "Late" (submitted after due) as separate labels. Moodle shows "Overdue" in the timeline and "Submitted late by X" in assignment status. Both separate due date from cut-off date. Treat that as the standard model for soft vs hard.

## 6. Density: narrow sidebars and mobile
- Outline rows: title first, deadline secondary. Use a single line: tier icon plus a short date, right-aligned or under the title in small text. Only items with a relevant deadline get it. Don't show it on completed rows, or show only a check.
- Show deadlines on rows only where the tier is above "far away", or show the date in muted style for far-off ones. Don't repeat the same date on every row of a section whose items share a deadline. Show it once at the section header (the idea's design includes a section header deadline block).
- The next-deadline card at the top of the outline is the one prominent element. Keep it to the item title, the date/relative time and a link ("jump to").
- On mobile (outline sheet): same content, with row height meeting touch target needs (about 44px, minimum 24px per WCAG 2.5.8). Allow wrapping and don't hide the deadline behind hover.
- Material guidance: use chips or small badges for status with an icon plus a label, and keep the label short. Material's accessibility guidance says not to use colour as the only indicator.
- Dashboard band: one line, with a full-width strip under the thumbnail, showing the next deadline of that course only. If there are none, leave the band out (or keep a neutral spacer so the cards stay aligned in the grid). Reserve the band's height so cards line up.

## 7. Avoiding alarm fatigue
- Reserve the strongest style (red, bold, pulse) for overdue and imminent states. Everything else stays calm. If most items are red, none are.
- Do not colour far-off deadlines. Show one prominent "next deadline" rather than a badge on every row.
- Do not animate or pulse. It fails WCAG 2.2.2 Pause, Stop, Hide when it lasts more than 5 seconds, and it is a distraction.
- Cap what overdue shows: group multiple overdue items into a count on the dashboard ("3 overdue") instead of three alarming bands.
- Tone: informative rather than punitive ("Due tomorrow"). NN/g's guidance on status and visibility says to inform without nagging. Late-completed work should not be shamed.
- Let the same item show consistent styling across all surfaces, so learners learn the vocabulary once.

## 8. Server-side vs client-side rendering, caching
- Render the state server-side: tier, absolute date (localised to the learner's timezone) and the screen-reader text. The page then works without JavaScript, is accessible by default, and is testable.
- Relative text ("in 3 days") goes stale the moment a page is cached or left open. Options:
  1. Server-render relative text and keep pages uncached per user (the default for a per-learner authenticated page). Simplest, with staleness limited to the page's age. Acceptable for day-granularity text.
  2. Progressive enhancement: render the absolute text in `<time datetime>` and have a small script update relative labels on load and periodically. This avoids stale text in long-open tabs and bfcache restores, but the markup must have a sensible no-JS fallback and must not flicker.
- Day-granularity relative text ("Today / Tomorrow / in 3 days") is stable enough for server rendering. Minute and hour counters ("in 3 hours") need client updates and are rarely worth it. Prefer "Today, 17:00".
- Caching: per-learner deadline data must not be in shared caches (fragment keys need the learner, cohort and tier date, or skip fragment caching). If caching is used, key by learner and by local date so "Today" doesn't survive midnight. Invalidate on deadline edit, cohort change or completion.
- HTMX partials: when a completion action changes state, the response should swap the affected row, the next-deadline card and the header card (out-of-band swaps), so all three surfaces stay consistent.
- Query cost: compute deadlines for the whole outline in one prefetch (per-learner and cohort overrides resolved in bulk), not per row. This avoids N+1 queries on the outline and dashboard.
- Test the tier boundaries with a fixed clock (inject `now`) and with cases around local midnight and DST.

## 9. Concrete recommendations for this spec
1. One function resolves (effective deadline, hardness, completion state, tier) for a learner and item. All surfaces use it.
2. Four urgency tiers plus separate done states: completed on time, completed late, and missed (hard). Define the thresholds as named settings.
3. Hybrid dates: relative within 7 days, absolute beyond. Always include the absolute date and time in the header card and in screen-reader text.
4. Each state has icon shape + short text or screen-reader text + colour. Verify contrast in light and dark themes.
5. Render server-side with `<time datetime>`. Use no `aria-live`, and no animation.
6. Outline: the next-deadline card is the main emphasis. Rows show a compact icon plus date only where useful. The section header carries a shared deadline.
7. Completed work leaves the urgency system and stops counting toward the next deadline.

## References
- WCAG 2.2 SC 1.4.1 Use of Color: https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- WCAG 2.2 SC 1.4.3 Contrast (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- WCAG 2.2 SC 1.4.11 Non-text Contrast: https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html
- WCAG 2.2 SC 1.1.1 Non-text Content: https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html
- WCAG 2.2 SC 2.2.2 Pause, Stop, Hide: https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html
- WCAG 2.2 SC 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- WCAG 2.2 SC 1.4.10 Reflow: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- MDN `<time>` element: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/time
- GOV.UK Design System, Dates (style guide): https://www.gov.uk/guidance/style-guide/a-to-z-of-gov-uk-style#dates
- GOV.UK Design System, Tag component (status not by colour alone): https://design-system.service.gov.uk/components/tag/
- Nielsen Norman Group, Timestamps on content: https://www.nngroup.com/articles/timestamps-on-content/
- Nielsen Norman Group, Visibility of system status: https://www.nngroup.com/articles/visibility-system-status/
- Material Design, Accessibility: color and contrast: https://m3.material.io/foundations/designing/color-contrast
- Material Design, Chips: https://m3.material.io/components/chips/overview
- Moodle Docs, Timeline block: https://docs.moodle.org/en/Timeline_block
- Moodle Docs, Assignment settings (due date, cut-off date): https://docs.moodle.org/en/Assignment_settings
- Canvas Community, Assignment statuses (missing, late): https://community.canvaslms.com/t5/Canvas-Basics-Guide/tkb-p/CanvasBasicsGuide
- Django docs, Time zones: https://docs.djangoproject.com/en/stable/topics/i18n/timezones/

status: ok
