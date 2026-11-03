# Screen-reader checklist: educator interface

A pass for a person with a real screen reader over three surfaces: the learners table, a
learner's quick view, and one confirmation dialog. QA has already checked the accessibility tree
in a browser (names, roles, live regions, keyboard flow; see `qa_report.md`). This pass checks
what a screen reader actually says.

Use one of these pairs:

- VoiceOver with Safari on macOS. Turn it on with Cmd+F5. "VO" below means Control+Option.
- NVDA with Firefox on Windows. "NVDA" below means the NVDA key (Insert by default).

## Record of the run

Fill this in when you run it.

| | |
|---|---|
| Who ran it | |
| Date | |
| Screen reader and version | |
| Browser and version | |
| Operating system | |
| Theme (`default` or `first_class`) | |
| Result | Not run |

Result is one of: **Pass** (every step passed), **Pass with findings** (every finding is filed
below and none blocks a task), or **Fail** (a task cannot be done by screen reader alone).

## Setup

1. Start the dev server: `uv run python manage.py runserver`.
2. Sign in at `http://127.0.0.1:8000` with the admin login in `.claude/sdd/config.md`,
   `## QA Login`. That account is an organisation admin, so every control below is shown.
3. Use a desktop-width window (at least 1280px wide).
4. Make sure the organisation has at least three learners, one of them with no first or last name,
   and that at least one learner is Active. `uv run manage.py` QA seed commands or the Django admin
   can set this up.

Mark each step **P** (pass) or **F** (fail) in the last column. For every F, add a row to
[Findings](#findings).

## 1. The learners table

Open **Learners** from the sidebar.

| # | Do | Expect to hear | P/F |
|---|---|---|---|
| 1.1 | Jump to the table (VoiceOver: VO+Cmd+T; NVDA: T). | "Learners", then "table", with the number of rows and columns. | |
| 1.2 | Move across the header row (VoiceOver: VO+Right; NVDA: Ctrl+Alt+Right). | Each column is named by its label, read as a column header. The sorted column says it is sorted ascending or descending. No header announces an icon name such as "sort neutral". | |
| 1.3 | Tab to a sortable header's link and press Enter. | The link is named by the column label. After the table reloads, focus is not lost to the top of the page, and the header now reports its new sort direction. | |
| 1.4 | Move down the Name column, then right along one row (NVDA: Ctrl+Alt+Down, then Ctrl+Alt+Right). | Each cell is read with its column header. | |
| 1.5 | Reach the row checkbox of a learner with a name. | "Select" and the learner's name, "checkbox", "not checked". | |
| 1.6 | Reach the row checkbox of the learner with no name. | "Select" and the learner's email. Their name link is also read as the email, never as a dash or blank. | |
| 1.7 | Read a Status cell. | The status as a word ("Active", "Pending" or "Inactive"), not only a colour. | |
| 1.8 | Tick one row checkbox with Space. | The selection status is announced, for example "1 selected · showing 1–10 of N learners". | |
| 1.9 | Untick it. | The selection bar goes away without moving focus off the checkbox. | |

## 2. A learner's quick view

Stay on **Learners**.

| # | Do | Expect to hear | P/F |
|---|---|---|---|
| 2.1 | Tab to a learner's quick-view button, beside their name. | "Quick view:" and the learner's name, "button" (or "link"). | |
| 2.2 | Press Enter. | Focus moves into the quick view, and the learner's name is read as its heading. The quick view is announced as a dialog named by that heading. | |
| 2.3 | Read through the quick view (VoiceOver: VO+Right; NVDA: Down). | Email, status, cohorts, course registrations with progress, and last active, in reading order. Badges read as words. The Open full page link and Close button are named. | |
| 2.4 | While the quick view is open, Tab past its last control. | On a desktop width, focus can leave the quick view and reach the page, because it is not modal there. Focus is never hidden behind the quick view or the sticky header. | |
| 2.5 | Return to the quick view and press Escape. | The quick view closes, and focus returns to the quick-view button you opened it from, which is read again. | |
| 2.6 | Open a second learner's quick view, then Tab to a third learner's quick-view button and press Enter. | The quick view now shows the third learner, and their name is read as the heading. | |

## 3. A confirmation dialog

Open a learner's page (follow their name link) whose status is Active.

| # | Do | Expect to hear | P/F |
|---|---|---|---|
| 3.1 | Tab to **Deactivate** in the page header and press Enter. | A dialog opens, named "Deactivate" and the learner's name, as a question. | |
| 3.2 | Note where focus lands. | On **Cancel**. | |
| 3.3 | Read the dialog body. | It says the learner loses access to this organisation's courses, and that their cohorts, registrations and progress are kept and return on reactivation. | |
| 3.4 | Tab through the dialog. | The optional **Reason** field is labelled, and says it is shown to staff only. Then Cancel, then Deactivate. Focus wraps inside the dialog and never reaches the page behind it. | |
| 3.5 | Press Escape. | The dialog closes, and focus returns to the **Deactivate** button in the page header. | |
| 3.6 | Open the dialog again, Tab to **Deactivate** and press Enter. | While it runs the button reads "Deactivating…". The result is announced without moving focus to the top of the page, and the header now reads Inactive. | |
| 3.7 | Reactivate the learner the same way, so the data is as you found it. | The Reactivate dialog behaves as in 3.1 to 3.6. | |

## Findings

One row per failed step. File each as a QA bug, or as an idea in `spec_dd/1. next/` if it needs
new work.

| Step | What was heard | What was expected | Filed as |
|---|---|---|---|
| | | | |
