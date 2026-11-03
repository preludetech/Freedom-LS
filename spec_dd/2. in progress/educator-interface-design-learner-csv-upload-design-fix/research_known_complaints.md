# Research: known complaints about bulk CSV import of users/learners

Scope: UI/presentation complaints relevant to restyling an existing working import. Evidence is from web search; coverage is uneven (Moodle, Canvas, HubSpot found; TalentLMS, Docebo, Mailchimp, Shopify, Google Classroom not found in results, so claims about them are not made). Some sources are old (Moodle 1.9 era).

## Complaints found (with sources)

1. **Cryptic, terse errors.** Canvas reports generic "malformed csv" or "Couldn't find Canvas CSV import headers" when the real cause is a hidden character or BOM; the headers look right in a text editor. Moodle "is not a valid field name" is caused by spaces between fields, which the message does not say.
   - https://community.canvaslms.com/t5/Admin-Group/SIS-Import-UTF8-and-quot-Couldn-t-find-Canvas-CSV-import-headers/m-p/205460
   - https://community.canvaslms.com/t5/Canvas-Question-Forum/SIS-Import-Malformed-CSV-Hidden-Characters/m-p/481599
   - https://docs.moodle.org/39/en/error/moodle/invalidfieldname
2. **Structure errors with no actionable detail.** Moodle "Number of columns is not constant" arises because Excel drops trailing commas when the last column is empty. Users cannot tell which row is at fault.
   - https://moodle.org/mod/forum/discuss.php?d=91833
3. **Unclear result: created vs updated vs skipped vs warned.** HubSpot users say the error log does not show which errors blocked a row, which were only warnings, or which were new vs duplicate. The import count can be lower than the row count with no explanation. Some errors still import the record, which confuses users.
   - https://community.hubspot.com/t/error-log-after-importing-csv/60300
   - https://knowledge.hubspot.com/import-and-export/troubleshoot-import-errors
4. **Error report is separate and hard to read.** HubSpot's failed rows are a downloaded zip containing a CSV (readers are told to use Excel Text to Columns); there is no in-app or API access. Canvas keeps import errors only 30 days.
   - https://community.hubspot.com/t5/APIs-Integrations/How-to-see-list-of-failed-records-on-import/m-p/353616
   - https://developerdocs.instructure.com/services/canvas/file.all_resources/sis_import_errors
5. **Excel encoding/BOM/delimiter traps.** Canvas requires UTF-8 without BOM, yet Excel adds a BOM or switches encoding. "CSV UTF-8" is missing in older Office builds. Semicolon-delimited files appear in comma-decimal locales. Moodle docs tell users to open the file in a text editor before upload and offer an encoding picker.
   - https://community.canvaslms.com/docs/DOC-3372
   - https://docs.moodle.org/19/en/admin/uploaduser
5a. **Sensitive values redacted** in HubSpot error output, forcing users back to the source file.
6. **Drop zone accessibility.** Drag-only zones exclude keyboard and screen-reader users (WCAG 2.2 SC 2.5.7 Dragging Movements needs a non-drag alternative). Reported fixes: keep a real file input or button as fallback, label the zone and state allowed types, link errors with `aria-describedby`, use a visually-hidden (not `display:none`) input, announce progress at sensible intervals, test with a real screen reader.
   - https://blog.filestack.com/html-file-upload-accessibility/
   - https://blog.filestack.com/accessible-react-file-upload/
   - https://ezud.com/accessible-file-upload-design/
   - https://carbondesignsystem.com/components/file-uploader/accessibility/

## Not evidenced by this search (from the brief, unverified here)
All-or-nothing failures, no preview, no progress indication, timeouts, re-upload losing context, mobile usability, template and header naming confusion (only Canvas header/BOM and Moodle field-name cases found), TalentLMS/Docebo/Mailchimp/Shopify specifics.

## Implications for a restyle (inference, not sourced)
- Show a clear result summary with distinct counts (created, updated, skipped, failed) and visible per-row errors with row numbers, in the page rather than a download.
- Distinguish blocking errors from warnings visually, with text as well as colour.
- Offer a template download and plain-language notes on UTF-8 and delimiter.
- Make the drop zone keyboard operable: a real file input or button, an associated label, and errors tied to the input.
- Keep the chosen file or context visible after an error so re-upload is easier.

status: ok
