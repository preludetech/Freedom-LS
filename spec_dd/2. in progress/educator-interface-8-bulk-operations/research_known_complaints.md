# Research: known complaints about CSV user import and bulk actions

Scope note: web search surfaced mostly bug trackers, vendor help pages and community idea threads, not many first-person rants. Frequency ratings are my judgement from how often the theme appears in trackers, docs and troubleshooting guides, not a measured count. Searches for Teachable, Thinkific, TalentLMS, Google Classroom, Schoology and Teams/SDS complaints found nothing usable; those are not covered.

## Findings first

1. The most documented failures are file-format ones: BOM on the first header, Excel locale delimiters (semicolons), non-UTF-8 encoding, stray spaces in headers, leading zeros stripped. FLS should normalise these on read and say what it did, not fail with a generic error.
2. The most damaging failures are silent: partial success with no error report (Moodle MDL-8941), duplicates "ignored" without a message, errors aggregated into a total (Canvas, fixed 2018), no alert when an import has errors (Canvas idea). The preview plus per-row label plus downloadable error CSV in the idea answers these directly. Keep every skipped row visible with a reason.
3. Overwriting existing users is the sharpest risk. Vendors match by email or external ID and UPDATE the existing record; Moodle makes it opt-in and warns it can "affect your users badly". The idea's "never overwrite" is the right default; the preview must say so.
4. No undo exists in the systems found. Vendors offer only a batch/Load ID for tracing. FLS's "every add has its remove" plus a result summary is ahead of this, but see the batch-identity suggestion below.
5. "Select all" ambiguity (page vs all matching) is a known pitfall; the confirmation must state the real scope and count.
6. Email behaviour is inconsistent across vendors (some send nothing, some send on tick-box, Canvas defaults off). Educators need to know before commit how many emails will go out.

## Theme by theme

### 1. Cryptic or generic import errors
- Frequency: very common.
- Evidence: Moodle "number of columns is not constant" thread, where the answer was to fill the last column on every row (https://moodle.org/mod/forum/discuss.php?d=91833). Moodle rejects a header with a stray leading space as "invalid header" (https://tracker-old.moodle.org/browse/MDL-64959). Canvas once reported only a few errors and rolled the rest into a total (https://community.canvaslms.com/t5/Admin-Group/SIS-Import-Lack-of-Detail-Aggregates-errors-into-a-total/td-p/156021). Adobe Learning Manager publishes a guide just to decode its CSV errors (https://elearning.adobe.com/2023/09/alm-lms-know-your-csv-import-errors-better-and-a-guide-to-fix-the-csv-issues).
- FLS should: give every error its row number, column, offending value and a plain-language reason ("Row 14: email 'jo@' is not a valid address"). Trim header whitespace. For unknown or missing headers, name the header, list the accepted ones and say which was expected. Never aggregate errors into a count without listing them.

### 2. Excel-mangled files: BOM, delimiter, encoding
- Frequency: very common for any school or admin audience using Excel.
- Evidence: a UTF-8 BOM attached to the first column name breaks Moodle group CSV import; workaround is to strip it (https://tracker-old.moodle.org/browse/MDL-72342). Excel in a German-locale Windows saves semicolon-separated CSVs that fail until the separator is changed (https://launchpad.net/bugs/1393472). StudyTube's troubleshooting lists hidden characters and non-UTF-8 encoding as the usual cause of a failure with no clear message (https://support.studytube.nl/hc/en-us/articles/35861343159186-CSV-import-troubleshooting). Moodle exposes delimiter and encoding pickers on the form (https://docs.moodle.org/19/en/admin/uploaduser).
- FLS should: decode with utf-8-sig, sniff comma versus semicolon versus tab, fall back to a Windows encoding when UTF-8 fails, and show the detected delimiter and encoding on the preview. Make the template download UTF-8 with BOM-safe handling so Excel opens it correctly. Reject files that are really .xlsx with a message saying "save as CSV".

### 3. Leading zeros and date or number reformatting
- Frequency: common wherever an ID column exists. FLS's import has only email, names and cohort name, so the exposure is small.
- Evidence: Docebo community thread on usernames losing leading zeros on export and round-trip through Excel (https://community.docebo.com/product-tips-tricks-3/excel-wizards-wanted-cells-with-leading-zeros-removed-when-converting-to-csv-7162); Excel strips zeros from numeric-looking cells by default (SAP article https://userapps.support.sap.com/sap/support/knowledge/en/2328644).
- FLS should: not add numeric ID or date columns to this import (the idea already avoids them). If cohort names are numeric-like ("2025", "07"), match them as strings and warn when no cohort matches rather than coercing.

### 4. Template does not match what the importer expects
- Frequency: common.
- Evidence: Moodle's "invalid header" from a stray space; column-order confusion in the "columns not constant" thread (links above). Vendors ship long troubleshooting pages for this.
- FLS should: ship the downloadable template with the exact headers and two example rows (as the idea says), match headers case-insensitively and trimmed, and reject unknown headers with a clear message or map them. Strict headers with a good message is the cheaper option and avoids the mapping UI; a typo like "e-mail" or "firstname" should produce a "did you mean" hint.

### 5. Imports overwriting existing users; duplicate accounts
- Frequency: common as a design hazard; vendor behaviour varies.
- Evidence: vendor docs where a matching email or External User ID causes the existing record to be UPDATED (https://support.latitudelearning.com/?p=858, and the other bulk-upload pages in the same search such as https://help.guroo.academy/bulk-user-import). Moodle skips existing usernames by default and requires opting in to update; its docs warn that errors when updating existing accounts "can affect your users badly" (https://docs.moodle.org/22/en/Upload_users). Some systems error on duplicates, some silently ignore them (Toon Boom: "Duplicates will be ignored", https://helpcentre.toonboom.com/hc/en-ca/articles/53247697939219-How-do-I-add-students-in-bulk-using-CSV-import). Canvas community raised a harm case where a changed key field in a SIS file caused "a lot of chaos" and asked for change-threshold halts (https://community.canvaslms.com:443/t5/Idea-Conversations/SIS-Imports-adjustable-thresholds-and-notifications/idi-p/503179).
- FLS should: match on normalised email (lowercase, trimmed), never write names for an existing account, and label the row "existing account joined to this organisation" or "already a member". Detect duplicate emails within the same file and label the second as an error or already-in-file rather than silently dropping it. When an existing account's name differs from the file, show it in the preview as information ("name in file differs; existing name kept") so nobody believes the file updated it.

### 6. No bulk remove or undo
- Frequency: common as a gap; none of the sources found offered rollback.
- Evidence: vendor docs describe only a batch log or Load ID for tracing (https://info.latitudelearning.com/blog/userimportfeature and the Load ID note in the search results). The idea's own comparable-systems research reached the same conclusion.
- FLS should: ship every bulk add with its remove (already settled). Cheap addition worth considering for the spec: record the import's created account ids and membership ids in the result summary so a "remove the learners added by this import" action is possible later. Do not delete accounts; removal means leaving the cohort or deactivation, with wording stating that.

### 7. Silent partial failures
- Frequency: common and high-impact.
- Evidence: Moodle MDL-8941, a badly quoted field caused partial enrolment with no error reported (https://tracker-old.moodle.org/browse/MDL-8941). Modern Campus distinguishes "imported, but some records did not get updated" from a clean success (https://involve-support.moderncampus.com/hc/en-us/articles/26330016959629). Canvas admins get no notification when an SIS import has errors or warnings (https://community.canvaslms.com/t5/Canvas-Ideas/SIS-SIS-Import-Error-Warning-Notification-for-Select-Admins/idi-p/568966).
- FLS should: reconcile at the end. Result counts must sum to the file's data row count, and the page should say so ("42 rows: 30 new, 8 joined, 3 already members, 1 error"). Treat unparseable rows (bad quoting, wrong column count) as error rows with a reason, never skip. For background runs, always email or show failure; a background import that dies must change the visible status to failed.

### 8. Timeouts and no progress feedback on big files
- Frequency: moderate; I found no direct first-person reports in this search, only vendors adding background paths (Docebo's threshold, per the idea's resources).
- Evidence: weak. The Canvas threshold idea and vendor "improved import" posts imply the problem (https://www.ihasco.co.uk/?p=12210).
- FLS should: keep the settled threshold design. For the background path show a status page with processed-of-total, survives reload, and shows failure. Cap file size and row count with a clear message (the preview itself must stay fast: do one query per batch for existing emails and cohorts, not per row).

### 9. Welcome or setup email floods, or emails not sent
- Frequency: common as confusion; direction of the complaint varies.
- Evidence: platforms differ: some offer a welcome email after creation with a summary, some send none and tell admins to announce credentials manually, some use a tick-box (search results incl. https://help.guroo.academy/bulk-user-import and https://schoolsupport.strongmind.com/hc/en-us/articles/16965740331924-Add-Users-in-Bulk-to-the-LMS). Canvas' password-notification column defaults to false, and a tester saw no email in a test environment (https://community.canvaslms.com:443/t5/Canvas-Question-Forum/Regarding-SIS-user-imports-with-password-notifications/m-p/585816 was in the results list; the detail comes from the search summary).
- FLS should: state on the preview exactly how many setup emails will be sent ("12 new accounts will get a setup email"), and none for existing accounts. Because the idea sends emails only for new accounts, a re-run sends nothing. Consider rate-limiting the sends in the background path and recording per-row send success so "email not sent" shows up as a visible result, with the existing resend-setup-email bulk action as the remedy. Whether to offer a "do not send emails" tick-box is a spec decision; schools importing before term start often want to stage accounts.

### 10. Select-all only selects the current page; unclear confirmation counts
- Frequency: well-known pattern in admin tables.
- Evidence: WordPress core only selects visible-page rows, which is why plugins exist to add "All Entries" (https://wordpress.org/plugins/?p=30164). Shopify's guidance separates page, loaded rows and all matching results, and recommends a scoped confirmation like "Archive 2,418 active products" (https://shopify.dev/docs/apps/build/app-home/migrate-from-polaris-react/select-all-actions). A Livewire tables package uses a select-all-pages flag plus an exclusion list rather than shipping every id to the browser (https://www.mintlify.com/alp-develop/laravel-livewire-tables/features/bulk-actions).
- FLS should: show a banner after the header checkbox ("30 selected on this page. Select all 412 matching this filter") and make the confirm modal state the real count and, where relevant, the filter. If the all-matching mode ships, store the filter and an exclusion list, and re-resolve server-side at confirm time; show "N selected" persistently. Selection must not silently change when the filter changes; clear it when it does. Each confirm names the action, the number of objects and the target ("Add 30 learners to Cohort A").

### 11. Permission surprises
- Frequency: not found directly in this search; included because the idea calls it out.
- FLS should: check permission per object server-side (settled). The confirm and result must report objects skipped for permission as a distinct label ("3 skipped: you can't manage them"), not as failures or silent omissions, and hide actions from roles the matrix denies.

## Suggested inputs to the spec

- Strict headers with a clear message and "did you mean", over a mapping UI, unless the mockup requires mapping. Opening a file in Excel and re-saving is the dominant user path, so the delimiter, BOM and encoding handling is a requirement, not polish.
- Preview must show: detected delimiter and encoding, count per label summing to total rows, email count, any rows whose existing details differ from the file.
- Error CSV download must round-trip: same columns as the template plus a reason column, so the educator fixes and re-uploads it. Because the import is idempotent, re-uploading the whole file is also safe.
- Background path: visible failed state, not only success.
- Results of bulk actions mirror import labels, including a "skipped" label for permission and "no change" cases.

## References

- https://tracker-old.moodle.org/browse/MDL-72342 (BOM in CSV header)
- https://tracker-old.moodle.org/browse/MDL-8941 (partial enrolment, no error)
- https://tracker-old.moodle.org/browse/MDL-64959 (header with leading space)
- https://launchpad.net/bugs/1393472 (Excel semicolons)
- https://moodle.org/mod/forum/discuss.php?d=91833 (column count error)
- https://docs.moodle.org/19/en/admin/uploaduser and https://docs.moodle.org/22/en/Upload_users (upload modes, delimiter and encoding options)
- https://community.canvaslms.com/t5/Canvas-Ideas/SIS-SIS-Import-Error-Warning-Notification-for-Select-Admins/idi-p/568966
- https://community.canvaslms.com:443/t5/Idea-Conversations/SIS-Imports-adjustable-thresholds-and-notifications/idi-p/503179
- https://community.canvaslms.com/t5/Admin-Group/SIS-Import-Lack-of-Detail-Aggregates-errors-into-a-total/td-p/156021
- https://community.canvaslms.com:443/t5/Canvas-Question-Forum/Regarding-SIS-user-imports-with-password-notifications/m-p/585816
- https://community.docebo.com/product-tips-tricks-3/excel-wizards-wanted-cells-with-leading-zeros-removed-when-converting-to-csv-7162
- https://userapps.support.sap.com/sap/support/knowledge/en/2328644
- https://support.studytube.nl/hc/en-us/articles/35861343159186-CSV-import-troubleshooting
- https://elearning.adobe.com/2023/09/alm-lms-know-your-csv-import-errors-better-and-a-guide-to-fix-the-csv-issues
- https://involve-support.moderncampus.com/hc/en-us/articles/26330016959629
- https://helpcentre.toonboom.com/hc/en-ca/articles/53247697939219-How-do-I-add-students-in-bulk-using-CSV-import
- https://support.latitudelearning.com/?p=858 and https://info.latitudelearning.com/blog/userimportfeature
- https://help.guroo.academy/bulk-user-import
- https://schoolsupport.strongmind.com/hc/en-us/articles/16965740331924-Add-Users-in-Bulk-to-the-LMS
- https://www.ihasco.co.uk/?p=12210
- https://wordpress.org/plugins/?p=30164
- https://shopify.dev/docs/apps/build/app-home/migrate-from-polaris-react/select-all-actions
- https://www.mintlify.com/alp-develop/laravel-livewire-tables/features/bulk-actions

status: ok
