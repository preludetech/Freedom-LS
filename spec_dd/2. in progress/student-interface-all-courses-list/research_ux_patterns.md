# UX Research: "All Courses" List Page

Research to inform the redesign of the FLS student "All Courses" listing toward a simpler,
denser, horizontal `[icon][details]` row. Four statuses must read clearly: **Not registered**,
**Registered** (registered, 0% progress), **In progress**, **Complete**.

This doc surveys how leading platforms present a course *catalogue/list* and convey
enrolment + progress + completion, then distils recommendations for our direction.

---

## 1. Status communication

How platforms distinguish not-enrolled / enrolled-not-started / in-progress / completed:

- **The four states are an industry-standard set.** LMS enrolment/status taxonomies map almost
  exactly to ours: `not enrolled`, `not started`, `in progress`, `completed` (LearnUpon, Absorb,
  Schoox, Zensai all use this or a close variant). So our four statuses are well-aligned with
  learner expectations — no need to invent vocabulary.
- **Status is shown as a short label/badge or eyebrow**, usually paired with an icon and/or
  colour. The dominant pattern is a small pill/badge ("Enrolled", "In progress", "Completed")
  rather than long sentences.
- **Completion is almost universally a checkmark** (often green) plus the word "Completed" — the
  checkmark is the single most recognisable course-status signal.

### Accessibility — do not rely on colour alone (WCAG 1.4.1, Level A)

- WCAG 1.4.1 requires that colour is never the *only* means of conveying information. ~8% of men
  and ~0.5% of women have colour-vision deficiency.
- A status badge must combine **colour + (icon and/or text)**. The canonical accessible example is
  an icon + text label ("✓ Completed", "● In progress") so the meaning survives greyscale.
- Practical rule for us: every status must be distinguishable with colour removed. Text label is
  the safest carrier; icon reinforces; colour is decoration, never the sole signal.

---

## 2. Progress indicators in a list

- **A progress bar is shown in a list only when it carries information** — i.e. for *enrolled,
  partially-complete* courses. Most platforms show the bar/percentage only for courses the learner
  is enrolled in or has started; it is hidden for not-enrolled catalogue items (LearnDash,
  Totara).
- **0% and 100% bars are low-value / redundant in a list.** A bar pinned at 0% adds clutter and
  duplicates the "Registered / Not started" label; a bar at 100% duplicates the "Completed"
  checkmark. The status label already says it. Several support threads (Moodle, Totara) show that
  bars near the extremes mostly generate confusion ("says 100% but not complete", etc.).
- **Alternatives to a bar are often clearer in a dense list**: percentage text ("45%"),
  fraction ("3 of 8 topics"), or a checkmark for done. These take less vertical space than a bar
  and read well in a row layout.
- Bars are most justified on **detail / dashboard / "continue learning"** views where the learner
  is focused on a single active course — not on a long browse list.

**Implication for us:** the optional progress bar should appear **only for In progress** rows.
Suppress it for Not registered, Registered (0%), and Complete — let the status badge carry those.

---

## 3. Layout — horizontal row vs vertical grid card

NN/g and general UX-pattern guidance strongly support the horizontal-row direction for this page:

- **Lists are more scannable than cards** for homogeneous, mostly-text items. Fixed element
  positions let the eye predict where the title and status will be; card grids vary layout and
  force re-scanning (NN/g: "cards are less scannable than lists").
- **Lists are denser** — more items visible without scrolling, lower short-term-memory load.
  Cards consume more space per item.
- **NN/g explicitly says: don't use cards to make text-based content easier to scan — use a list.**
  Cards win only when items are visually browsable (rich thumbnails drive the decision). A small
  icon + title is *not* that case.
- **Mobile:** a full-width horizontal row collapses cleanly to one column and gives a large,
  comfortable touch target. Grid cards have to reflow and divide horizontal space.

### Whole-row click target — accessibility (important)

The "make the whole row clickable" goal has a well-known accessible solution and a well-known
anti-pattern (Adrian Roselli; Nomensa; Kitty Giraudel):

- **Do NOT wrap the entire row in one `<a>`.** Screen readers then announce the whole row's text
  as one giant link name, and you cannot nest a second interactive element (e.g. an "Unregister"
  button) inside it. Invalid HTML and poor SR experience.
- **Do use the "stretched link" pattern:** put the `<a>` on the **title only**, then expand its
  hit area over the whole row with a pseudo-element:
  ```css
  .course-row a::after { content:""; position:absolute; inset:0; }
  .course-row { position:relative; }
  ```
  The accessible name stays short ("Intro to Python"), but the whole row is clickable.
- **Trade-off to note:** the stretched pseudo-element blocks text selection inside the row. Fine
  for a terse `[icon][title][status]` row; would hurt if rows contained copy-worthy text (they
  won't).
- Any secondary interactive control (e.g. a register/continue button or status badge that links
  elsewhere) must sit **above** the stretched link via `position:relative; z-index` so it stays
  independently clickable.

---

## 4. Catalogue vs "Continue learning"

- Mature platforms (Coursera, Udemy, edX, LinkedIn Learning) **separate** a personalised
  "Continue learning / My courses / In progress" rail from the "browse all / catalogue" view.
  The two have different jobs: resume vs discover.
- When a **single combined list mixes statuses** (our case — one "All courses" list spanning all
  four states), the load shifts onto the per-row status indicator to do the disambiguating work.
  That makes a clear, consistent status badge *more* important, not less.
- A common and effective compromise in a combined list is **grouping/sectioning by status**
  (e.g. "In progress", then "Available", then "Completed") or at least ordering so active courses
  surface first. This preserves a single page while giving the "continue learning" affordance.
  Our existing dashboard already owns the focused "continue learning" view, so the All Courses page
  can lean into being the browse/overview surface.

---

## 5. Common pitfalls to avoid

- **Cluttered cards.** Too many elements/buttons per item is the most-cited card complaint. Keep
  the row to icon + title + one status signal (+ optional bar only when in progress).
- **Unclear enrolment state.** If a learner can't tell at a glance whether they're registered, the
  list has failed its primary job — this is the headline risk for a combined list.
- **Redundant 0% / 100% progress bars** duplicating the status label (see §2).
- **Colour-only status** (fails WCAG 1.4.1).
- **Whole-`<a>`-wrapped rows** breaking screen readers and blocking secondary actions (see §3).
- **Removing "Next up: <item>"** (already planned) is consistent with best practice: that detail
  belongs on the dashboard/detail view, not a dense browse list.

---

## Recommendations for this project

**Do**

- Use a **horizontal `[icon][details]` row**, full-width, denser than the dashboard grid card.
  It's the right pattern for a scannable, mostly-text, mixed-status list.
- Give every row a **status badge that combines text + icon** (and colour as reinforcement only):
  e.g. `Not registered`, `Registered`, `In progress`, `✓ Completed`. Must survive greyscale.
- Show the **progress bar only for `In progress`** rows. Consider terse text ("45%" or "3 of 8")
  if a bar feels heavy in the dense layout.
- Make the **whole row clickable via the stretched-link pattern** — `<a>` on the title, hit area
  expanded with `::after { inset:0 }`, row `position:relative`.
- Keep any secondary action (register / continue button) **above** the stretched link with
  `z-index` so it stays independently operable.
- Consider **grouping or ordering by status** (active first) so the combined list still serves the
  "what do I resume?" need without a separate rail.
- Ensure the row touch target meets a comfortable minimum height for mobile.

**Don't**

- Don't show a progress bar at **0% or 100%** — the status badge already says Registered / Complete.
- Don't rely on **colour alone** to signal status.
- Don't **wrap the whole row in a single `<a>`** (SR verbosity + invalid nested interactives).
- Don't carry over the dashboard's **tall card / accent-hero band / centred icon** — that's
  visual-browse styling, wrong for a dense list. (Dashboard cards stay as-is, per scope.)
- Don't reintroduce **"Next up: <item>"** or other detail-view clutter on these rows.
- Don't pack multiple buttons/metadata into the row — one status signal is enough.

---

## References

- WCAG 1.4.1 Use of Color (Level A): https://www.wcag.com/designers/1-4-1-use-of-color/
- WCAG 1.4.1 plain-English guide: https://aaardvarkaccessibility.com/wcag-plain-english/1-4-1-use-of-color/
- WCAG 1.4.1 status-badge examples: https://testparty.ai/blog/wcag-1-4-1-use-of-color-2025-guide
- NN/g — Cards UI component (cards vs lists, scannability): https://www.nngroup.com/articles/cards-component/
- UX Patterns — Table vs List vs Cards: https://uxpatterns.dev/pattern-guide/table-vs-list-vs-cards
- Adrian Roselli — Block Links, Cards, Clickable Regions (stretched link, SR pitfalls): https://adrianroselli.com/2020/02/block-links-cards-clickable-regions-etc.html
- Nomensa — How to build accessible cards / block links: https://www.nomensa.com/blog/how-build-accessible-cards-block-links/
- Kitty Giraudel — Accessible Cards: https://kittygiraudel.com/2022/04/02/accessible-cards/
- LearnDash — Course Grid (progress shown only for enrolled/completed): https://learndash.com/support/kb/core/courses/course-grid/
- Totara — Progress bar (course features): https://totara.help/docs/progress-bar
- LearnUpon — Course / enrolment statuses (status taxonomy): https://support.learnupon.com/hc/en-us/articles/360004011578-Courses-enrollment-statuses-explained
- Thinkific — Viewed vs Completed percentages (completion checkmark): https://support.thinkific.com/hc/en-us/articles/360033331514-Understanding-Viewed-and-Completed-Percentages
- Absorb — Enrollment, Completion & Progress: https://support.absorblms.com/hc/en-us/articles/115015751048-Enrollment-Completion-Progress
- edX — Checking your progress in a course: https://edx.readthedocs.io/projects/open-edx-learner-guide/en/latest/SFD_check_progress.html
- Userpilot — Progress bars in UI/UX: https://userpilot.com/blog/progress-bar-ui-ux-saas/
