# Research: known complaints about audit/activity logs

Topic: what admins and educators commonly complain about with audit/activity logs, and what each complaint implies for the educator audit log improvements (avatars, export, compact expandable rows).

Method note: five web searches plus the project QA report. Findings are limited to what search snippets showed; pages were not opened. Categories with no direct source are marked "no source found" and rest on the general pattern only.

## A. Export complaints

| # | Complaint | Source | Implication for this work |
|---|---|---|---|
| A1 | Row cap too small. Atlassian's 10,000-entry CSV cap covers only a few days for large orgs. | https://jira.atlassian.com/browse/ACCESS-1045 | Decide whether to cap. If so, state the cap in the UI, and let the educator narrow by date. |
| A2 | Silent truncation. GitLab truncates the remainder past 100,000 events. Coralogix truncates silently past 10,000. | https://docs.gitlab.com/ee/administration/audit_reports.html , https://coralogix.com/docs/user-guides/data_exploration/logs/export/ | Never truncate silently. Either export everything or tell the user the export is partial. |
| A3 | Export ignores the on-screen filter and returns the latest N rows. | https://jira.atlassian.com/browse/ACCESS-2781 | The export must use exactly the same filtered queryset as the list view (Who, What, When). Test with each filter. |
| A4 | A filter silently dropped from the export. GitLab's export allowlist omitted the username filter, so exports included all users. | https://gitlab.com/gitlab-org/gitlab/-/merge_requests/252628 | Reuse the list view's filter parsing instead of a second code path. Cover every filter in tests. Also keep organisation scoping, so an export can never leak another organisation's rows. |
| A5 | Other products ignored a search term or period filter in exports (FileCloud, Drupal, Liferay date/time inaccuracy). | https://knowledgebase.filecloud.com/audit-logs-export-issue , https://www.drupal.org/node/3605379 , https://learn.liferay.com/kb-article/audit-events-filtered-by-date/time-are-not-being-exported-accurately | Same as A3. Add a date-boundary test for the When presets. |
| A6 | Confirmation dialog shows the total event count, not the filtered count. | https://jira.atlassian.com/browse/JRACLOUD-97158 | If the UI shows a count or confirmation, show the filtered row count. |
| A7 | Exported times differ from on-screen times (Moodle log download off by about ten hours versus the page). Another Moodle report says exported logs omit the year. | https://tracker-old.moodle.org/browse/MDL-14934 , https://tracker-old.moodle.org/browse/MDL-49473 | Pick one timezone for display and export. Use full date plus time, and ideally an ISO 8601 timestamp with offset. Label the column with the timezone. |
| A8 | Excel garbles UTF-8 CSV. Excel assumes ANSI. Moodle asked for a UTF-8 BOM on its Excel-compatible CSV. | https://tracker-old.moodle.org/browse/MDL-72035 , https://www.qnap.com/hu-hu/how-to/faq/con_show.php?cid=720 | Names with accents or non-Latin characters are likely in a learner audit log. Write a UTF-8 BOM or document the encoding. Test with a non-ASCII name. |
| A9 | Corrupt or polluted exports. Moodle log CSV had 23,670 rows followed by page HTML. Another report had HTML inside exported log cells. | https://tracker-old.moodle.org/browse/MDL-83938 , https://tracker-old.moodle.org/browse/MDL-46626 | Export plain text, not rendered template fragments. Do not reuse cell templates that contain HTML or avatar markup. |
| A10 | Slow or timing-out exports on large logs (implied by the caps and Moodle truncation above). No direct source with timings. | Inferred from A1, A2, A9 | Stream the response, or bound the size. Decide whether the export is synchronous. |
| A11 | Unreadable JSON blobs in exports. No source found. | None | The existing log has human-readable Details text (for example a reason on its own line). Export that text, plus the raw action code if useful. Do not dump internal JSON. |
| A12 | CSV formula injection. No source found in these searches (general knowledge). The QA report already tests markup in names and reasons (section 10). | QA report section 10 | Names and reasons are free text, so a value starting with `=`, `+`, `-` or `@` can run as a formula in Excel. Neutralise these in the export. |

## B. Deleted or missing users

| # | Complaint | Source | Implication |
|---|---|---|---|
| B1 | The actor or "Updated By" column goes blank once the user is deleted. QuickBooks shows blank or "Unknown User". | https://ibm-ai-apps.ideas.ibm.com/ideas/ENVIZISWAT-I-75 , https://insightfulaccountant.com/accounting-tech/general-ledger/the-data-detective---the-case-of-the-missing-user/ | Avatars need a fallback for a missing user. Show the stored label, not a blank. |
| B2 | Deleted users vanish from the filter, or are listed with only the word "deleted". | https://nation.marketo.com/t5/help-feedback-discussions/audit-trail-for-deleted-user/m-p/78262 , https://nation.marketo.com/t5/product-discussions/audit-trail-and-deleting-users/m-p/125332 | Keep deleted users in the Who filter if their rows remain. |
| B3 | The log records the deletion but not who did it. | https://jira.atlassian.com/browse/JRACLOUD-79216 , https://gitlab.com/gitlab-org/gitlab/-/issues/21606 | Cohort and learner deletion rows must keep the actor. |
| B4 | Fix pattern. Store identity in the record at action time and show "(Deleted User)" when the account is gone. | https://support.powerdmarc.com/support/solutions/articles/60001597211-using-the-audit-logs-feature-as-an-end-user-in-powerdmarc , https://docs.oracle.com/health-sciences/empirica-signal-811/ESIUG/admAdminCurrentUserActivity.htm | The QA report shows the model already has Actor label and Target label snapshots (section 12). Avatars must work from a user link that can be null, and fall back to the snapshot label with a neutral placeholder avatar. Export the snapshot label. |

## C. Dense or unreadable rows, expandable rows, accessibility

| # | Complaint or risk | Source | Implication |
|---|---|---|---|
| C1 | `aria-expanded` is misused on rows. On a row that controls nothing it falsely marks a parent row. | https://developer.mozilla.org/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-expanded | Put `aria-expanded` and `aria-controls` on a real button. Rows with no extra detail should have no toggle. |
| C2 | Row counts and structure change on expand and collapse. Colour alone is used for state. | https://developer.semrush.com/intergalactic/table-group/data-table/data-table-a11y | Use a text or icon indicator for expanded state, not colour alone. Give the table an accessible name. |
| C3 | Expanding a row in a data table is a known hard problem. A WebAIM thread debated disclosure versus grid, focus management, and rejected modals. | https://webaim.org/discussion/mail_message?id=49117 , https://webaim.org/discussion/mail_message?id=28918 | Prefer the simple disclosure pattern, with keyboard operation (Enter and Space on the button). Keep focus on the toggle after HTMX swaps. |
| C4 | Losing context. Expand state lost on pagination, filter change or HTMX swap. Pagination resetting. No source found; this is a known risk, not a cited complaint. | None | The list is paginated (25 per page) and filtered via query params. Expanded state is ephemeral, so decide explicitly. Keep filters in the URL across pages. Collapse on page change is acceptable if stated. |
| C5 | Compact layout hides the information that identifies a row. | Inferred from C2 and the QA notes in section E | The collapsed row should still show What, Target, Who and When. Put only secondary text (long reasons) in the expanded part. |

## D. Avatars

- Identical initials make people hard to tell apart (for example two "AL" users). No direct source found in these searches. Implication: show the avatar next to the name, never in place of it, and keep the text label as the accessible name. Use consistent colour per user if colours are used.
- Avatar images need alt text or `aria-hidden` when the name is adjacent. Avoid announcing the name twice. Inferred from the accessibility sources in C.
- Users with no name show an email in the log (QA report: the superuser has no name, so Who shows `demodev@email.com`). The avatar must derive initials from the email in that case.
- "System" actions are unclear. No source found. In this project, Who has a "System" option for seed role grants. Implication: give System a distinct non-person icon, not an initial avatar, and explain it in the Who filter.

## E. Complaints and notes from the project QA report (educator-interface-11-audit-log)

Source: `spec_dd/3. done/2026-10-29_08:48_educator-interface-11-audit-log/qa_report.md`. It found no bugs, but its General notes record these issues:

1. No Export on the audit log, and no search, sort links or checkboxes (section 8). Implication: export is new, so any filter, date and timezone behaviour is unspecified.
2. Mobile cards show an empty "Details" label when a row has no details. Implication: the compact layout should omit empty fields. Rows with no details should have no accordion.
3. On mobile org-log cards, What and Target sit on one bold line with no separator, so a cohort with markup in its name reads as one run of text. Implication: separate What and Target visually.
4. The mobile filter sheet is titled "Filter & sort" but the log has no sort (shared component wording). Implication: minor, probably out of scope. Do not add a sort control unasked.
5. Details is the narrowest column on tablet, so long details wrap to several lines (section 11.3). A 500-character reason is permitted (sections 2 and 11.1). Implication: this is the case the accordion targets. Long reasons need a defined collapsed truncation, and the expanded view shows the full text.
6. Markup in names and reasons must render as literal text (section 10). Implication: avatars, the accordion and the export must all keep escaping.
7. Pagination is 25 per page (section 8.7), and the Learner and Cohort History tabs share the same cell templates. Implication: changes to the cell templates affect those tabs, the mobile cards and the tablet layout. Retest all of them.
8. The superuser has no name, so Who shows an email. Implication: see D.

## Summary of implications to carry into the spec

1. Export must use the same filtered, organisation-scoped queryset as the list view (A3, A4).
2. State the row-cap and truncation policy, and never truncate silently (A1, A2).
3. Use one stated timezone, with full date and time, in the display and the export (A7).
4. Handle UTF-8 for Excel and neutralise formula-leading values (A8, A12).
5. Export plain text and avoid rendered HTML (A9, A11).
6. Avatars need a safe fallback for deleted or null users, nameless users and System (B1, B4, D).
7. The accordion needs a real button with `aria-expanded`, a visible non-colour indicator, keyboard operation, and no toggle on rows with nothing to reveal (C1 to C3, E2).
8. Keep identifying fields visible when collapsed. Decide what happens to expanded state on pagination and filter changes (C4, C5).
9. Retest the mobile cards, tablet table and History tabs (E7).

status: ok · reason: web findings gathered from search snippets (pages not opened); four categories flagged "no source found"
