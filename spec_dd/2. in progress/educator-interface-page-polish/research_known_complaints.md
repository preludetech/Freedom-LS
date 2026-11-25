# Known complaints: educator dashboard and admin UI polish

Scope: what educators, admins and accessibility users complain about for the seven items in `idea.md`. Evidence is uneven. Where I found no direct complaint thread, I say so and rely on standards guidance. I did not read `answers.md` or `research_comparable_systems.md`, so this adds to that research and does not repeat it.

## 1. Cluttered per-learner progress, truncated names
- Moodle's tracker has repeated reports of long course names being cut off. MDL-77364 asks for the full name or a tooltip on "My courses" cards. MDL-65661 reports long names in the "Recently accessed courses" block. MDL-79701 reports that the full course name can't be seen in the upcoming events block. The theme tracker has "long course names spill over".
  - https://tracker-old.moodle.org/browse/MDL-77364
  - https://tracker-old.moodle.org/browse/MDL-65661
  - https://tracker-old.moodle.org/browse/MDL-79701
  - https://bitbucket.org/covuni/moodle-theme_adaptable/issues/304/long-course-names-spill-over-in-my-courses
- Adobe Learning Manager users also asked for full course names without truncation in the admin and author views: https://community.adobe.com/questions-471/feature-request-display-full-course-names-without-truncation-admin-author-view-and-course-title-headers-246674
- Pattern: the complaint is names clipped with no way to read them. It is not about names being long. A cut-off name that isn't recoverable by tooltip, wrapping or a click-through is the failure.
- I found no direct forum thread about per-learner progress being cluttered. That point rests on the QA screenshots in the idea.

## 2. "+N more" that hides important information
- I found no sourced complaint specific to LMS lists. The usual objection is that the hidden items can't be reached, or that the hidden items hold the worst news, such as the stalled or overdue course.
- Cap by importance, not alphabetically, and make "+N more" a real link or button with an accessible name such as "Show 4 more courses for Jane Doe". This is my inference, not a sourced finding.

## 3. Progress shown only by colour
- WCAG 1.4.1 Use of Color says to add text, shape or another cue beside colour. Mass.gov lists a red/yellow/green status chart as a failure. A Jan 2026 W3C WAI thread on a red/green/grey segmented bar has one reply arguing that passing 1.4.11 contrast still doesn't satisfy 1.4.1, but that is one person's opinion.
  - https://w3.org/WAI/WCAG21/Understanding/use-of-color
  - https://www.mass.gov/info-details/digital-accessibility-fundamentals-color
  - https://lists.w3.org/Archives/Public/w3c-wai-ig/2026JanMar/0064.html
- Design systems recommend a text percentage beside the bar and a bar that exposes its value to assistive technology (https://ux4g.gov.in/components/progress, https://primer.style/product/components/progress-bar/accessibility). The idea already settles this: text, `role="progressbar"` and a label naming the course.
- Pitfall: the label should name the course, because a list of unlabelled progressbars all read "progress bar 40%". Flag badges such as "No recorded activity" also need text, not just a colour.

## 4. Read-only fields that look editable, or disabled inputs
- `disabled` inputs can't be focused, selected or copied, and browsers and designers grey them out to low contrast. WebAIM and W3C threads discuss read-only text in light grey at as low as 1.5:1 contrast. The W3C debate is unsettled on whether disabled controls must meet contrast, but contributors argue users must at least be able to tell the control is disabled.
  - https://adrianroselli.com/2024/11/avoid-read-only-controls.html
  - https://spark.staffbase.com/patterns/disabling-elements
  - https://designsystem.maersk.com/guidelines/disabled-and-readonly-states/
  - https://github.com/w3c/wcag/issues/2308
- Staffbase advises `readonly`, not `disabled`, for display values, because read-only fields stay focusable and copyable. Maersk says users can select and copy a readonly value.
- Adrian Roselli ("Avoid Read-only Controls") warns that `readonly` works only on text inputs and that some screen readers announce it poorly, for example TalkBack announced "disabled". He recommends plain text for values that aren't editable.
- Relevant to item 4, the learner email: plain text with a label is safest. If it stays in an input, it needs `readonly`, enough contrast and a visible difference from editable fields. It must not use `disabled`, because educators copy emails.

## 5. Dashboard numbers that aren't clickable
- I found no specific forum thread on this. It is a general dashboard-design expectation that a count tile leads to the list behind it. The idea already has the rule. Pitfall: the link target must show the same count the tile shows, so the filter and the number can't drift apart. The whole tile should be one link, with a single accessible name that includes the number.

## 6. Dialogs during a running request
- Developer forums report duplicate records from repeated clicks on a slow submit, and users clicking again with no feedback. Fixes are to disable submit and show a busy state.
  - https://github.com/newpanjing/simpleui/pull/479
  - https://community.pega.com/support/support-articles/multiple-clicks-are-needed-submit-buttons
  - https://feedback.telerik.com/kendo-react-ui/1690365-disable-submit-buttons-during-async-submission-in-kendo-react-form
  - https://west-wind.com/wconnect/Weblog/ShowEntry.blog?id=899
- I found no authoritative source on disabling Cancel specifically. The reasoning is that Cancel promises to stop something that can't be stopped. The educator closes the dialog, thinks it was cancelled, and the action finishes anyway. They then retry and duplicate it. Escape, backdrop click and the close button must be blocked as well as Cancel.
- Pitfalls: a disabled Cancel with no explanation reads as a bug, so the reason must be text. Announce it to screen readers, for example with `aria-live`, and don't rely only on a spinner. Re-enable everything if the request fails.

## 7. Phone buttons, too small or too big
- WCAG 2.5.8 (AA) sets 24x24 CSS px, or spacing around smaller targets. 2.5.5 (AAA) sets 44x44. Apple recommends 44pt, Android 48dp, and NN/g about 1cm. The standards set minimums only, so oversized buttons are a layout problem, not an accessibility one.
  - https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced
  - https://adrianroselli.com/2019/06/target-size-and-2-5-5.html
  - https://craftcms.com/blog/accessible-target-sizes
- Pitfall: shrinking the padding shrinks the hit area. Keep the target at 44px (min-height or padding on an invisible hit area) while the visible button is smaller. Crowding several 44px buttons can make adjacent taps collide, so the gap matters.

## Pitfalls the spec should guard against
1. A truncated course name with no way to read it. Wrap, or give it a tooltip and a link.
2. A "+N more" cap that hides the worst course. Sort so the worst-first course stays visible, state the order, and make "+N more" a link with a descriptive accessible name.
3. Colour-only status. Percentage text and badge text are always present, and each bar has `role="progressbar"`, `aria-valuenow` and a label naming the course.
4. `disabled` used for display values, and low-contrast read-only text. Educators must be able to copy the email. Prefer plain labelled text, or `readonly` with full contrast.
5. A dashboard tile that links to a list that disagrees with its number. Make the whole tile one link, and test the count against the destination.
6. A bulk dialog that can be dismissed mid-run. Cover Cancel, the close button, Escape and the backdrop. Show the reason as text and announce it. Re-enable on error.
7. A phone button fix that shrinks the touch target below 44px, or leaves oversized buttons eating the screen. Test at 375px that the hit area is at least 44px and the buttons don't crowd each other.
8. Untested "looks fixed" claims. Each item needs a test, per the idea ("a template and a test each"), covering the text, the labels and the disabled states.

status: ok · reason: web research done; some points (+N more, clickable tiles, Cancel while a request runs) have no direct complaint source and are marked as inference
