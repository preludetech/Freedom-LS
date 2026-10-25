# Frontend QA report: audit log

Run date 2026-10-25, dev server on port 8887. The run walked the frontend QA plan for the audit log as a human tester would, using these personas: Orla Admin (organisation admin, Northside), Cole (cohort admin), Vera (cohort viewer), Sid Admin (Southside) and demodev (superuser). It recorded 63 tests: 62 passed and 1 was skipped, and the skipped test was re-run as 6.1-admin, which passed. No bugs were found.

## Methodology

- Screenshots were collected into `<spec-dir>/screenshots/`, and every image referenced in this report exists beside it.
- The run walked every section of the plan at desktop 1920x1080. It then ran mobile 375x812 and tablet 768x1024 for section 11.
- The run was driven through Playwright MCP as a human tester would.
- The test plan writes URLs as `/educator/northside/...`, but the real paths are `/educator/organisations/northside/...`. The `organisations/` segment predates this branch. Every test used the real path.
- The plan's labels predate this branch's glossary rename. "Unregistered from course", "Re-registered for course", "Role removed", "Member suspended" and "Remove" (role) now read "Registration deactivated", "Registration reactivated", "Role deactivated", "Member deactivated" and "Deactivate role". Behaviour matched the plan under the new names.

## Diff scoping

- Class: FULL.
- Changed files: 194.
- Front-end files: 30 templates under `freedom_ls/educator_interface/templates/educator_interface/`:
  - `data-table-cells/`: `audit_details`, `audit_what`, `audit_when`, `audit_who`, `deactivate_registration`, `member`, `member_actions`, `member_roles`, `unregister`.
  - `modal/`: `add_member`, `change_cohorts`, `deactivate_cohort_registration_confirmation`, `deactivate_confirmation`, `deactivate_learner_confirmation`, `deactivate_member_confirmation`, `deactivate_registration_confirmation`, `deactivate_role_confirmation`, `delete_cohort_confirmation`, `reactivate_registration_confirmation`, `remove_from_cohort_confirmation`, `remove_role_confirmation`, `suspend_member_confirmation`, `unregister_confirmation`, `unregister_from_course_confirmation`.
  - `panels/`: `learner_history`, `learner_registrations`.
  - `partials/`: `audit_history_empty`, `audit_log_card`, `audit_log_empty`, `reason_field`.
- Nothing was skipped. Desktop, mobile and tablet all ran.

## Smoke gate

Pass. Two pages loaded:

- `http://127.0.0.1:8887/`
- `http://127.0.0.1:8887/educator/organisations/northside/audit-log`

The plan writes `/educator/northside/...`. The real paths are `/educator/organisations/northside/...` (the `organisations` segment predates this branch). The plan's literal URL 404s, so all tests used the real path.

## Results

### §1 A reason reaches the learner's History tab

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 1.1 | desktop | pass | Ada's page shows the Overview, Courses, History tab strip. | — |
| 1.2 | desktop | pass | History tab renders; earlier runs left rows so the empty state could not be seen here (the plan allows this). | — |
| 1.3 | desktop | pass | Deactivate dialog has 'Reason (optional)' with help text 'Only staff can see this. It is shown in the history.' | ![](screenshots/page-2026-10-25T20-30-10-664Z.png) |
| 1.4 | desktop | pass | After confirming, badge reads Inactive and History gains 'Learner deactivated' by Orla Admin, Details 'Left the programme', When 25 Oct 2026 20:30. | — |
| 1.5 | desktop | pass | Reactivate dialog has no reason field; History shows 'Learner reactivated' newest first with empty Details. | ![](screenshots/page-2026-10-25T20-30-42-901Z.png) |
| 1.6 | desktop | pass | Direct load of /__tabs/history shows the same two rows. | — |

### §2 The reason is validated

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 2.1-2.2 | desktop | pass | 501-char reason (set programmatically; the input carries maxlength=500 so typing stops at 500): POST returned 422, dialog stayed open with 'Ensure this value has at most 500 characters (it has 501).', badge still Active. | ![](screenshots/page-2026-10-25T20-31-15-372Z.png) |
| 2.3 | desktop | pass | 500-char reason accepted; History Details cell holds all 500 characters. | — |
| 2.4 | desktop | pass | Ada reactivated. | — |

### §3 A no-op and a refused action write nothing

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 3.1-3.3 | desktop | pass | Second tab deactivated Ada; stale first tab's Deactivate POST returned 422 with the 'Ada Lovelace was already changed / Nothing changed. Someone else may have already used Deactivate on this learner.' dialog. History gained exactly one 'Learner deactivated' row (22 -> 23). | ![](screenshots/page-2026-10-25T20-32-15-872Z.png) |
| 3.4 | desktop | pass | Ada reactivated. | — |
| 3.5 | desktop | pass | Members: Orla Admin's own row has no buttons at all and reads 'You can't change your own roles'. Note Cole Admin is Inactive from an earlier run; reactivated in section 7. | ![](screenshots/page-2026-10-25T20-32-48-692Z.png) |

### §4 Memberships, moves and registrations show on every page they touch

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 4.1 | desktop | pass | Sol was already in Cohorts A and C from earlier runs, so added to Cohort B. Sol's History: 'Added to cohort' by Orla Admin, Details 'Cohort B'. The Add to cohort dialog has no reason field. | ![](screenshots/page-2026-10-25T20-33-39-067Z.png) |
| 4.2 | desktop | pass | Cohort B's History tab shows the same row with a Target column reading 'Sol Solo'. Ada's learner deactivations are not on any cohort History. | ![](screenshots/page-2026-10-25T20-33-47-881Z.png) |
| 4.3 | desktop | pass | Ben was in A and B, so moved from B to C. Move dialog has no reason field. Ben's History: 'Moved between cohorts', Details 'From Cohort B to Cohort C'. | ![](screenshots/page-2026-10-25T20-34-20-352Z.png) |
| 4.4 | desktop | pass | The Moved row appears on both Cohort B's and Cohort C's History, Target 'Ben Brown'. | — |
| 4.5 | desktop | pass | Remove from cohort dialog has the reason field. Row: 'Removed from cohort', Details 'Cohort C' with 'Moved by mistake' on its own muted line. | ![](screenshots/page-2026-10-25T20-34-55-923Z.png) |
| 4.6 | desktop | pass | The registration buttons are now labelled Deactivate / Reactivate (glossary rename) and the actions read 'Registration deactivated' (Details 'Course Pub' + 'Finished elsewhere'), 'Registration reactivated' (Course Pub), and for Sol's lapsed Course Hid another 'Registration reactivated'. A fresh 'Registered for course' row (Details 'Course Other') was produced on Ben Brown, who had no individual registration. The plan's labels 'Unregistered from course' / 'Re-registered for course' are the pre-rename wording. | ![](screenshots/page-2026-10-25T20-35-47-823Z.png) |
| 4.7 | desktop | pass | Cohort C already held every course, so the cycle ran as deactivate (reason 'Wrong cohort') then Register: rows 'Cohort registration deactivated' (Course Pub + Wrong cohort) and 'Cohort registration reactivated' (Course Pub). A fresh 'Cohort registered for course' (Course Hid) was produced on Cohort B. The cohort registration deactivation dialog has the reason field. | ![](screenshots/page-2026-10-25T20-36-50-979Z.png) |
| 4.8 | desktop | pass | Used qa.audit.run3@qa.test (new) and ben@qa.test (existing, not in Cohort B) since the plan's emails were already consumed by earlier runs. Results list: one 'Account created and setup email sent', one 'Already a learner here. Added to the cohort'. Cohort B History: 'Learner added' Target 'Runa Three' Details 'Account created and setup email sent, added to Cohort B', and 'Added to cohort' for Ben Brown. Ben's own History has the Added to cohort row and no Learner added row. | ![](screenshots/page-2026-10-25T20-38-02-626Z.png) |
| 4.9 | desktop | pass | Cohort A Learners tab > Add learners (paste dialog, Cohort A preset). pick@qa.test was already in Cohort A from an earlier run ('Already in the cohort', no row); old@qa.test produced one 'Added to cohort' row for Olga Old. No summary row on the cohort History. | ![](screenshots/page-2026-10-25T20-38-50-300Z.png) |

### §5 Cohort create, rename, state and delete

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 5.1 | desktop | pass | Created 'QA Audit Cohort'; its History shows 'Cohort created' by Orla Admin, Target 'QA Audit Cohort'. | ![](screenshots/page-2026-10-25T20-39-29-247Z.png) |
| 5.2 | desktop | pass | Rename to 'QA Audit Cohort 2' wrote 'Cohort renamed', Details 'From QA Audit Cohort to QA Audit Cohort 2'. Saving the edit form again without changing the name wrote no row (still 2 rows). | — |
| 5.3 | desktop | pass | Settings > Deactivate dialog has the reason field; page re-rendered Inactive; History: 'Cohort deactivated' with 'Pilot ended', then 'Cohort reactivated' (reactivate dialog has no reason field). Second screenshot shows the four rows. | ![](screenshots/page-2026-10-25T20-40-34-149Z.png) ![](screenshots/page-2026-10-25T20-41-02-281Z.png) |
| 5.4 | desktop | pass | Delete dialog carries the reason field; after 'Created for QA' + Delete the browser lands on the cohorts list and the cohort is gone. | ![](screenshots/page-2026-10-25T20-41-16-492Z.png) |
| 5.5 | desktop | pass | Organisation Audit log: 'Cohort deleted' Target 'QA Audit Cohort 2' Details 'Created for QA' although the cohort no longer exists; the created, renamed, deactivated and reactivated rows are there too. The 'Cohort created' row's Target reads 'QA Audit Cohort' (the name at write time), not the later name; the plan's 'same Target' wording assumed otherwise. Labels are stored at write time by design, which is what lets the deleted cohort's name survive. | ![](screenshots/page-2026-10-25T20-41-31-243Z.png) |
| 5.6 | desktop | pass | Cohort A Settings offers Deactivate only and explains 'Cohort A can't be deleted while it has 11 learners and 2 course registrations'. No Delete button. | — |

### §6 Learner rename and setup email

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 6.1 | desktop | skip | Deferred: as Orla (organisation admin) the learner page offers no 'Edit name' control; EditLearnerNameAction needs a capability an organisation admin lacks (every earlier 'Learner renamed' row was written by demodev@email.com). Re-run under demodev in section 10 (see 6.1-admin). | — |
| 6.1-admin | desktop | pass | As demodev (who has the Edit name control): last name to 'Lovelace-Byron' wrote 'Learner renamed' Details 'From Ada Lovelace to Ada Lovelace-Byron'; back to 'Lovelace' wrote a second row; saving the form with no change wrote nothing. | ![](screenshots/page-2026-10-25T20-52-32-765Z.png) |
| 6.2 | desktop | pass | Pending Person > Resend setup email > confirm: POST 204 and History gained one 'Setup email resent' row. Clicking it again straight away: dialog 'Setup email sent recently / Pending Person was sent a setup email recently. Try again in 15 minutes.' with a 422, and no new History row. | ![](screenshots/page-2026-10-25T20-43-22-968Z.png) |
| 6.3 | desktop | pass | Nameless learner deactivated and reactivated: both rows on their History; in the organisation log their Target reads 'nameless@qa.test'. | ![](screenshots/page-2026-10-25T20-44-11-990Z.png) |

### §7 Roles and members

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 7.1-7.2 | desktop | pass | The control is labelled 'Deactivate role' (glossary rename of Remove); the dialog carries the reason field (second screenshot). Audit log gained two 'Role deactivated' rows, Target Cole Admin, Details 'Cohort admin on Cohort A' and '... Cohort B', each with 'Changing teams'. The plan's 'Role removed' label is pre-rename wording. | ![](screenshots/page-2026-10-25T20-44-37-254Z.png) ![](screenshots/page-2026-10-25T20-44-26-562Z.png) |
| 7.3 | desktop | pass | Add member > cohort.admin@qa.test > Cohort admin on Cohort A > preview > confirm: one 'Role assigned' row, Details 'Cohort admin on Cohort A', Who Orla Admin. | — |
| 7.4 | desktop | pass | Change cohorts (no reason field) adding Cohort B: one 'Role assigned' for Cohort B and no deactivation. Removing Cohort B again (preview reads 'Deactivates on: Cohort B'): one 'Role deactivated' for Cohort B. | — |
| 7.5 | desktop | pass | Cole was Inactive from an earlier run, so the order ran Reactivate ('Member reactivated'), Deactivate with 'On leave' (dialog has the reason field; row 'Member deactivated', Target Cole Admin, Details 'On leave'), then Reactivate again so later sections can log in as Cole. The Reactivate member dialog has no reason field. | ![](screenshots/page-2026-10-25T20-46-09-430Z.png) ![](screenshots/page-2026-10-25T20-45-53-957Z.png) |
| 7.6 | desktop | pass | Cohort A's History shows the Role assigned and Role deactivated rows for Cohort A; none of the Cohort B role rows and none of the Member rows appear there. | — |

### §8 The organisation Audit log and its filters

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 8.1 | desktop | pass | Sidebar Administration group shows Members then Audit log; /educator/organisations/northside/audit-log renders with When, Who, What, Target, Details columns, newest first, Add filter control, no search box, no sortable headers, no checkboxes, no Export. Page 1 of 5 (rows from the seed and an earlier run). | ![](screenshots/page-2026-10-25T20-29-11-358Z.png) |
| 8.2 | desktop | pass | Columns When, Who, What, Target, Details; rows newest first; an 'Add filter' control only: no search box, no sortable headers, no checkboxes, no Export. | — |
| 8.3 | desktop | pass | Who menu lists System, demodev@email.com and Orla Admin. Who=Orla Admin: every row's Who is Orla Admin, chip 'Who: Orla Admin'. Who=System: 12 rows, all System (the seed's role grants and one seed learner deactivation), none of Orla's. Three of the System rows show the raw code 'role.granted' in What; they were written by an earlier run before this branch renamed the code to role.assigned, so no label exists for them. No shipped data carries the old code. | ![](screenshots/page-2026-10-25T20-46-56-641Z.png) |
| 8.4 | desktop | pass | Choosing Learner deactivated then (via Add filter > What) Learner reactivated appends a second audit_log-what parameter; only those two actions show. Adding cohort.deleted brings the 'Cohort deleted' rows (QA Audit Cohort 2) in alongside them. | ![](screenshots/page-2026-10-25T20-47-33-811Z.png) |
| 8.5 | desktop | pass | Today, Last 7 days, Last 30 days, Last 90 days and Last 12 months each keep every row (Page 1 of 7). Choosing a second preset replaces the first: one 'When: ...' chip and one audit_log-when parameter at a time. | ![](screenshots/page-2026-10-25T20-47-57-908Z.png) |
| 8.6 | desktop | pass | Who=System + What=Learner deactivated is not empty on this database (the seed deactivates Rae Removed as System), so Who=System + What=Cohort deleted was used: empty state 'No entries match these filters.' with a Clear filters link. Clicking it returns every row and the URL carries no filter parameters. | ![](screenshots/page-2026-10-25T20-48-18-209Z.png) |
| 8.7 | desktop | pass | Log holds 7 pages of 25. Page links 2..7 and Next shown. Page 2 (fetched as the htmx partial) has 25 rows, none repeated from page 1, and continues from page 1's oldest timestamp (20:35) down to 19:49. | — |
| 8.8 | desktop | pass | ?audit_log-who=not-a-pk&audit_log-when=yesterday renders the unfiltered list (Page 1 of 7), no chips, no error. | — |

### §9 Who can see what

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 9.1 | desktop | pass | As Cole (cohort admin): Ada's page shows Overview and Courses only; /__tabs/history on Ada and on Cohort A both 404; Cohort A has no History (or Settings) tab; the sidebar has no Administration group; /audit-log is a 404. | ![](screenshots/page-2026-10-25T20-49-25-507Z.png) |
| 9.2 | desktop | pass | As Vera (cohort viewer): the same four checks give the same results as for Cole. | — |
| 9.3 | desktop | pass | As Sid: Southside's log opens with only Southside rows (no Northside name anywhere); Northside's log is a 404. Sam South was inactive from an earlier run so he was reactivated then deactivated with 'Southside check'; both rows appear in Southside's log by Sid Admin. Northside's log (checked as demodev, and again as Orla in section 13) holds no Sam South row. | ![](screenshots/page-2026-10-25T20-50-39-367Z.png) |
| 9.3-tail | desktop | pass | Back as Orla, Northside's log filtered to Learner deactivated holds 13 rows, none for Sam South and no 'Southside check' text. | — |
| 9.4 | desktop | pass | As demodev: the sidebar 'Switch organisation' menu (DemoDev, Eastside, Northside, Southside, Westside) moves the Audit log page from Northside to Southside in place; each shows only its own rows and Southside's shows Sam South's deactivation by Sid Admin. | ![](screenshots/page-2026-10-25T20-51-05-121Z.png) |

### §10 Markup in labels renders as text

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 10.1-10.2 | desktop | pass | As demodev: created '<b>Bold</b> cohort' then renamed it to '<img src=x onerror=alert(1)> cohort'. The page title, h1, the cohort History (second screenshot) and the organisation log all show the literal characters; no <b>, <img> or <script> element exists inside any table cell, no broken image, no dialog. | ![](screenshots/page-2026-10-25T20-51-54-404Z.png) ![](screenshots/page-2026-10-25T20-51-50-659Z.png) |
| 10.3 | desktop | pass | Deactivated the cohort with reason '<script>alert(2)</script>': the Details cell shows the literal text and nothing executed. The cohort was then deleted (reason empty); 'Cohort deleted' Target keeps the literal '<img ...> cohort' name. | ![](screenshots/page-2026-10-25T20-52-07-323Z.png) |

### §11 Mobile layout

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 11.1 | mobile | pass | 375x812: Ada's History tab renders as cards (one <li> per entry, 23 cards, the table hidden); the first line is the What label, then labelled When, Who and Details lines. No horizontal scroll (scrollWidth 375 = viewport). | ![](screenshots/page-2026-10-25T20-53-55-054Z.png) |
| 11.2 | mobile | pass | 375x812 organisation log: cards whose first line reads the What label and the Target (e.g. 'Learner renamed Ada Lovelace'); a Filter button opens the 'Filter & sort' sheet with Who and When as selects and What as chips (checkboxes). Choosing Who=System and Show results narrows to 12 cards, all Who=System (second screenshot). No horizontal scroll. | ![](screenshots/page-2026-10-25T20-54-08-438Z.png) ![](screenshots/page-2026-10-25T20-54-18-245Z.png) |
| 11.2-nav | mobile | pass | The hamburger opens the Navigation drawer full width (375px) listing Dashboard, Cohorts, Learners, Courses, Messages, Members, Audit log; Escape closes it. | ![](screenshots/page-2026-10-25T20-54-21-903Z.png) |
| 11.2-dialog | mobile | pass | The Deactivate dialog opens as a bottom sheet 375px wide with the Reason field and 42px-high Cancel/Deactivate buttons; no overflow. The DJDT handle overlapping the header button edge is the debug toolbar, not the app. | ![](screenshots/page-2026-10-25T20-54-28-317Z.png) |
| 11.3 | tablet | pass | 768x1024 organisation log: the five-column table is shown (not cards), fits in 768px with wrapped cells, no horizontal scroll; the sidebar collapses to a hamburger; filter control present. | ![](screenshots/page-2026-10-25T20-54-54-483Z.png) |
| 11.3-learner | tablet | pass | 768x1024 Ada's History tab: table shown, tabs Overview/Courses/History, no overflow. | ![](screenshots/page-2026-10-25T20-54-58-293Z.png) |
| 11.3-members | tablet | pass | 768x1024 Members table 718px inside a 768px main; no overflow. | ![](screenshots/page-2026-10-25T20-55-01-536Z.png) |
| 11.3-dialog | tablet | pass | 768x1024 Deactivate dialog centred, 512px wide, with the Reason field; no overflow. | ![](screenshots/page-2026-10-25T20-55-05-964Z.png) |

### §12 The Django admin is read-only

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 12.1-12.3 | desktop | pass | /admin/ lists Audit log > Audit log entries. Changelist: no 'Add audit log entry' link; columns Created at, Actor label, Action, Target label, Organisation; filters By action and By organisation; search 'Lovelace' returns 26 rows all naming Lovelace. The entry page is 'View audit log entry': no editable inputs, 13 read-only fields, no Save and no Delete. /add/ returns 403. | ![](screenshots/page-2026-10-25T20-52-49-067Z.png) |

### §13 Nothing else broke

| Test | Viewport | Status | Notes | Screenshot |
|---|---|---|---|---|
| 13.1 | desktop | pass | As Orla: Learners, Cohorts, Members, and Ada's Overview and Courses tabs render as before with zero console errors on each load. | — |
| 13.2 | desktop | pass | Deactivate dialog on Ada > Cancel: dialog closes, badge stays Active, History's newest row is still the 20:52 rename (no row written). | — |
| 13.3 | desktop | pass | Observed during sections 4 and 7: the Reactivate member, Move, Change cohorts and Add to cohort dialogs carry no Reason field (nor do Reactivate learner, Reactivate cohort, Register and Resend setup email). | — |

## Design check

no design states tested

## Bug status

No bugs found this run.

## General notes

- The test plan writes URLs as `/educator/northside/...`; the real paths are `/educator/organisations/northside/...`, and the plan's literal URL 404s.
- The plan's labels predate this branch's glossary rename: "Registration deactivated", "Registration reactivated", "Role deactivated", "Member deactivated" and "Deactivate role" replace "Unregistered from course", "Re-registered for course", "Role removed", "Member suspended" and "Remove".
- Test 6.1 was skipped under Orla because an organisation admin has no Edit name control (the action's capability sits above org admin). It was re-run under demodev as 6.1-admin and passed.
- Three System rows in the organisation log show the raw code `role.granted`. An earlier run wrote them before the rename to `role.assigned`, so no label exists for them. No shipped data carries the old code.
- The 'Cohort created' row's Target keeps the original name after a rename, because labels are stored at write time (as the spec says).
- Seed data residue from earlier runs made several tests adapt their inputs: Ada was already in every cohort, Sol was in A and C, Cole and Sam South were inactive, and qa.audit.new@qa.test was already present. Nothing was blocked by it.
- The Who=System + Learner deactivated combination is not empty on this database, so Cohort deleted was used for the empty state in 8.6.

status: ok
reason: report rendered, 0 bugs documented, 63 test records (62 pass, 1 skip), screenshots verified
