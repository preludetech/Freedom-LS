# Research: reference implementations for educator-interface page polish

Method note: written from established knowledge of the named systems and design-system docs. The URLs were not re-fetched in this run, so verify exact wording and class names before quoting. LMS dashboards (Docebo, TalentLMS, Thinkific, Teachable) are closed-source and only their visible behaviour is described. Does not repeat `research_comparable_systems.md`.

## 1. Per-learner multi-course progress in a list (idea item 1)

- Moodle (Participants page, "Course participation"; Report builder custom reports): one learner per row, courses are not listed per learner. Course progress is a single % column per course because the page is scoped to one course. Moodle's "My courses" block shows one thin bar plus "NN% complete" text per course in a vertical list, with no per-item border, only vertical spacing.
- Canvas (People, Gradebook, Learning Mastery): same, one course scope. Student's Grades page is a table of course rows with a % per row.
- Open edX Instructor dashboard: per-course only. The Learner "Progress" page is a per-course table.
- TalentLMS Users list and Docebo User management: courses per user are not inline. The row is clickable to a user profile with a Courses tab. Docebo shows a count ("3 courses") and drills down. Support for FLS choice: capped inline list plus "+N more" to the Courses tab is stronger than either.
- Thinkific / Teachable "Students" list: one row per student, columns are enrolment count and last sign-in. Per-course progress is on the student detail page. Reinforces the "+N more goes to the learner's Courses tab" decision.
- Concrete markup pattern (Tailwind UI "Lists / Stacked lists" and the Bootstrap/Moodle progress bar), mini row inside a cell:
  ```html
  <ul class="space-y-2">
    <li>
      <div class="flex items-baseline justify-between gap-2 text-sm">
        <span class="truncate" id="c1">Course title</span>
        <span class="tabular-nums text-muted">62%</span>
      </div>
      <div class="mt-1 h-1.5 w-full rounded-full bg-gray-200"
           role="progressbar" aria-labelledby="c1"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="62">
        <div class="h-1.5 rounded-full bg-primary" style="width:62%"></div>
      </div>
    </li>
  </ul>
  <a href="..." class="text-sm">+2 more</a>
  ```
  Notes: `space-y-2` (8px) between items is the Tailwind UI stacked-list rhythm. `truncate` plus `min-w-0` on the flex child stops long titles breaking the row. `tabular-nums` keeps percentages aligned. `aria-labelledby` pointing at the visible title avoids a duplicate hidden label.
- GOV.UK has no progress bar component (it deliberately avoids one) and uses text such as "3 of 5 sections completed" in its task-list pattern. Support for always having the text beside the bar.
- Refs: https://tailwindcss.com/plus/ui-blocks/application-ui/lists/stacked-lists · https://design-system.service.gov.uk/patterns/complete-multiple-tasks/ · https://carbondesignsystem.com/components/data-table/usage/ · https://docs.moodle.org/en/Course_completion

## 2. A learner's course-progress table with status badges (idea item 2)

- Canvas student Grades page and Moodle "Course overview" / Learner report: a plain table, columns Course, Status, Progress, with a small status pill per row. No border box per item. Header row is muted small caps, rows separated by a hairline `divide-y`.
- Polaris IndexTable / DataTable and Primer DataTable: status is a Badge in its own column, text label always present ("Complete", "In progress", "Not started"). Polaris Badge has an optional progress icon (incomplete/partiallyComplete/complete) so the status is not colour-only.
- Carbon Data table: Tag component in a status cell, with text. Tag colour set is limited to a few semantic colours.
- GOV.UK Task list pattern: each row is label plus a right-aligned status text or `govuk-tag`, separated by a bottom border only. Closest "simple list" alternative to a table.
- Concrete pattern (Tailwind UI "Tables / Simple"):
  ```html
  <table class="min-w-full divide-y divide-gray-200">
    <thead><tr><th scope="col" class="py-2 text-left text-xs font-medium uppercase text-muted">Course</th> ...</tr></thead>
    <tbody class="divide-y divide-gray-100">
      <tr><td class="py-3 pr-4">Title</td><td><span class="badge">In progress</span></td><td>progress bar + 4 of 9</td></tr>
    </tbody>
  </table>
  ```
  On phones Tailwind UI and Polaris collapse rows to a stacked block (`block` on `tr`, `hidden sm:table-cell` for secondary columns) rather than scroll. A reason or flag belongs in a tooltip-free secondary line under the title, only when it adds information not already in the badge. This supports dropping the redundant "Has not started any course item." text.
- Refs: https://tailwindcss.com/plus/ui-blocks/application-ui/lists/tables · https://polaris-react.shopify.com/components/feedback-indicators/badge · https://primer.style/components/data-table · https://carbondesignsystem.com/components/tag/usage/ · https://design-system.service.gov.uk/patterns/complete-multiple-tasks/

## 3. Read-only email on a profile / settings page (idea item 4)

- GOV.UK: a read-only value is plain text, not a disabled input. Use a summary list (`govuk-summary-list`) with key and value, or a paragraph. Disabled inputs are discouraged: they are skipped by keyboard and hard to read (low contrast).
- Primer: "Settings" email shown as text with a "Primary" label, change link beside it. GitHub account settings shows the email as plain text in a dropdown or list, not a greyed input.
- Polaris: read-only fields use `readOnly` on TextField (stays focusable, keeps normal contrast, screen readers announce read-only) as a pattern, or plain text in a description list.
- Carbon: `readonly` input state is a distinct visual (no border, transparent background). Carbon prefers readonly over disabled for values the user may copy.
- Concrete patterns:
  - Description list: `<dl class="..."><dt class="text-sm text-muted">Email</dt><dd class="text-sm">name@example.com</dd></dl>` placed above the form in the same panel, with `dl` rows `flex gap-x-4` or Tailwind UI "Description lists" (`grid grid-cols-3 gap-4 py-3`).
  - Or `<input readonly>` (not `disabled`) so the value can be selected and copied.
- Recommended for FLS: description list above the form. It reads as information, avoids a false affordance, and survives copy. If a later spec makes email editable, swap to an input.
- Refs: https://design-system.service.gov.uk/components/summary-list/ · https://tailwindcss.com/plus/ui-blocks/application-ui/data-display/description-lists · https://carbondesignsystem.com/components/text-input/usage/ · https://primer.style/components/text-input

## 4. Dashboard stat tiles that link to lists (idea item 5)

- Tailwind UI "Stats" (simple, with brand icon): a card with a label (`dt`), value (`dd text-3xl font-semibold`), and an optional "View all" link in a footer strip (`bg-gray-50 px-4 py-4 text-sm` with `<a>View all<span class="sr-only"> {label} stats</span></a>`). The `sr-only` text makes the link unique for screen readers. This is the exact "stat tile links to list" pattern.
- Alternative: make the whole tile the link (`<a class="block ...">`) so the hit area is large. Polaris and Primer "card as link" guidance: only one link per card, and no nested interactive elements. If a tile also needs a second link (cohort progress), use footer links, not a whole-card link.
- Moodle admin/dashboard blocks, Canvas Course Home stats, Thinkific's dashboard tiles ("Students", "Enrolments"): number tiles that go to the matching list. Teachable's dashboard counts also link to Students.
- Docebo and TalentLMS dashboard widgets: widget title is a link to the full report, plus per-row links on named items (course, user). Supports the "anything named is one click away" rule.
- Carbon "clickable tile" (`ClickableTile`): whole tile is an `<a>` with an arrow icon at the bottom right as the affordance. Always add a visible arrow or "View all" text so the link is discoverable, not hover-only.
- Refs: https://tailwindcss.com/plus/ui-blocks/application-ui/data-display/stats · https://carbondesignsystem.com/components/tile/usage/ · https://primer.style/components/link · https://polaris-react.shopify.com/components/layout-and-structure/card

## 5. Modal dialogs locked during in-flight submissions (idea item 6)

- Primer Dialog: `Dialog` accepts `onClose`, and the guidance is to omit or disable the close button for a blocking operation. Primer's `Button` supports `loading` plus `inactive` (aria-disabled, stays focusable, announces why). Primer recommends `inactive` over `disabled` when the reason is shown.
- Polaris Modal: while a primary action `loading: true`, the secondary action gets `disabled: true`. Close button and overlay close still work unless the app blocks them, so Polaris leaves it to the developer.
- Carbon Modal: `preventCloseOnClickOutside` prop keeps the overlay click inert. Carbon pairs it with `InlineLoading` inside the primary button (spinner plus "Submitting...") and disables the secondary button.
- Material / MUI Dialog: `disableEscapeKeyDown` and an `onClose` that ignores `backdropClick` and `escapeKeyDown` reasons while `loading`. Standard MUI pattern.
- Native `<dialog>`: the `cancel` event fires on Esc. Block with `dialog.addEventListener('cancel', e => { if (busy) e.preventDefault() })`. Backdrop click is a custom handler. Note Chrome lets Esc close a `<dialog>` the second time after a prevented cancel unless the user interacted (close-watcher behaviour), so also guard the `close` event.
- Concrete HTML pattern to say why:
  ```html
  <button type="button" aria-disabled="true" aria-describedby="run-note">Cancel</button>
  <p id="run-note" role="status">This is running and can't be stopped. It will finish in a moment.</p>
  ```
  Use `role="status"` (polite live region) so screen readers announce the state change. Prefer `aria-disabled="true"` plus a click guard over `disabled` so the control stays in the tab order and the reason is readable (APG warns disabled controls are skipped by keyboard).
- HTMX: use `hx-disabled-elt="this, #cancel, #close"` on the form or button so HTMX toggles `disabled` for the request's duration and re-enables on response with no custom JS. Combine with `hx-indicator`.
- Refs: https://primer.style/components/dialog · https://polaris-react.shopify.com/components/deprecated/modal · https://carbondesignsystem.com/components/modal/usage/ · https://mui.com/material-ui/react-dialog/ · https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/cancel_event · https://htmx.org/attributes/hx-disabled-elt/ · https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/

## 6. Compact header actions on mobile with large tap targets (idea item 7)

- GOV.UK button: 40px high on desktop, but full-width stacked on mobile, with at least 10px between. Its guidance is "do not make mobile buttons smaller", the opposite of this spec's wish. Use it as a counter-argument for dialog footers: stacked full-width is acceptable for 2 actions.
- Polaris page header: `PageHeader` primary action stays a button, secondary actions collapse into an "Actions" disclosure menu below the `sm` breakpoint (`actionGroups` and `secondaryActions`). Mobile header shows one primary action plus a "More actions" button. This is the overflow approach.
- Primer PageHeader: `Actions` slot with `hidden: {narrow: true}` on secondary actions and an `ActionMenu` kebab shown at narrow widths (`hidden: {regular: true, wide: true}`).
- Tailwind UI "Page headings with actions": `<div class="mt-4 flex md:ml-4 md:mt-0">` with buttons `ml-3`; the primary button is `inline-flex ... px-3 py-2 text-sm`. On mobile they flow under the title. The "More" menu variant is `sm:hidden` on the dropdown trigger and `hidden sm:flex` on the full list.
- Carbon: small button is 32px, default 40px, large 48px. Carbon mandates that touch layouts use a large button.
- Small visual with a 44px hit area, concrete Tailwind patterns:
  - Utility: `relative px-3 py-1.5 text-sm` plus `after:absolute after:-inset-x-1 after:-inset-y-2 after:content-['']` (a 28px button grows to a 44px target). Needs the pseudo-element not to overlap neighbouring targets, so keep `gap-2` or more between adjacent buttons (WCAG 2.5.8 spacing exception).
  - Or `min-h-11 min-w-11 inline-flex items-center justify-center` on an icon-only button with an `aria-label`. This keeps the size honest and is simplest for icon buttons.
  - Tailwind v4 breakpoints: apply size only below `sm`: `text-sm py-1.5 sm:py-2`, and keep `min-h-11` on touch via `pointer-coarse:min-h-11` (Tailwind v4 `pointer-coarse` variant, which targets touch devices rather than width).
- Recommended for FLS (for the design step): small visual (`text-sm`, tighter padding) plus the `pointer-coarse:min-h-11` rule is the lowest-risk, one-class-set change that works for both header actions and dialog footers. Reserve an overflow menu for a header with three or more actions.
- Refs: https://design-system.service.gov.uk/components/button/ · https://polaris-react.shopify.com/components/layout-and-structure/page · https://primer.style/components/page-header · https://tailwindcss.com/plus/ui-blocks/application-ui/headings/page-headings · https://tailwindcss.com/docs/hover-focus-and-other-states#pointer-and-hover-media-queries · https://carbondesignsystem.com/components/button/usage/ · https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

## Takeaways for the spec

1. Item 1: name + 4 to 6px bar + percentage, `space-y-2`, a capped list, "+N more" link to the Courses tab. Use `aria-labelledby` on the progressbar.
2. Item 2: table with a Status badge column and `divide-y`. Collapse to stacked rows on phones. Drop reason text that repeats the badge.
3. Item 4: description list (not a disabled input) above the form.
4. Item 5: a footer "View all" link (with `sr-only` context) or a clickable tile with a visible arrow.
5. Item 6: `aria-disabled` plus click guard, a `role="status"` reason, and guard Esc (`cancel` event) and backdrop click. `hx-disabled-elt` covers the request lifetime.
6. Item 7: small visual plus `pointer-coarse:min-h-11`, 8px or more between targets. The overflow menu is the fallback for 3+ header actions.

status: ok · reason: complete; written from prior knowledge, URLs not re-fetched
