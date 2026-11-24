# Research: known complaints

Scope: what LMS educators/admins and UI users complain about for the issues in `idea.md`. Evidence is thin and mostly indirect. One web search was run. It found vendor help docs and forum posts, but nothing on most of the specific themes. Items marked (general UX) come from established UX practice, not from a source I fetched.

## Sourced findings (enrolment management)

- **Enrolment can only be managed from one place.** A Docebo forum user says you can only manage the user-to-course relationship from the course in the UI. Another calls a CSV-only route for several courses "old school" for an LMS. This supports acting on enrolments where they are listed.
  - https://community.docebo.com/product-q-a-7/how-to-easily-unenroll-multiple-courses-from-a-user-perspective-1935
  - https://community.docebo.com/product-q-a-7/easiest-way-to-unenroll-from-multiple-courses-13907
- **Mistaken enrolments are routine.** ScholarLMS lists "users were mistakenly enrolled" as a reason for bulk unenrol, so removal needs to be easy but safe.
  - https://www.scholarlms.com/?p=46256
- **Confirmation dialogs are vague.** A Drupal LMS UX issue flags the prompt "perform 'Reset course progress' action on 1 entity?" as confusing.
  - https://www.drupal.org/node/3525100
- **Confirmations that state scope work well.** LearnUpon says unenrolling from a journey does not remove the learner from courses or delete course progress.
  - https://support.learnupon.com/hc/en-us/articles/36404057690909
- **Success messages that don't match the outcome erode trust.** An SAP SuccessFactors article describes this for removals.
  - https://userapps.support.sap.com/sap/support/knowledge/en/3649033

## General UX complaints (no fetched source)

- **Overloaded detail pages.** Details, registrations and content all sit on one page, so users scroll and cannot find things. The usual fix is tabs that group related items. That matches the idea's tab 1 (details and registrations) and tab 2 (content).
- **Lists that don't link to the item.** Users see a name and cannot click through to the cohort, learner or course. They then navigate by hand through menus. Rows should link to the thing and offer its actions.
- **Fully expanded outlines.** Every part open by default makes long courses a wall of text. Collapsed by default is the usual expectation.
- **Close-and-reopen previews.** Previewing items one by one means closing and reopening the modal each time. Prev/next within the modal is the standard fix.
  - Keep disabled prev/next at the ends, as in `answers.md`.
  - Keep other ways to close (header X, Esc, backdrop). Removing the footer Close button is acceptable only if these work.
- **Accidental removals.** Putting a remove button inline in a list invites mis-clicks. Mitigations: a confirmation that names the learner and the course, states what is and isn't removed (progress kept or lost), and has a clear destructive style.

## Button text misalignment from custom web fonts

Not researched on the web. From general knowledge, custom fonts commonly shift text vertically in buttons for these reasons:

- The font has unusual ascent/descent metrics, so line-height centring looks off.
- The fallback font swaps in before the web font loads, so text jumps.
- Padding is tuned for one font's metrics.

Where to look: font-face metric overrides (`ascent-override`, `descent-override`), `line-height` and padding on button classes, and `display: inline-flex; align-items: center`. Check the FLS theme first, then the First Class repo, per `answers.md`.

## Implications for the spec

- Registration panels need add and remove actions, and rows need links.
- Removal needs a confirmation naming the learner and course and stating what happens to progress.
- Preview modal prev/next must follow the agreed outline order and keep the other close routes.

status: ok
