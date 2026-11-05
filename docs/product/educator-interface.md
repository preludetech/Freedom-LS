# Educator Interface

_Last updated: 2026-11-03_

## Summary

- Educators work in one panel scoped to one organisation at a time, with Dashboard, Cohorts, Learners and Courses under Teaching, and Staff and Audit log under Administration for admins. See [Organisation scope](#organisation-scope).
- The dashboard shows totals, the learners who need attention and each cohort's progress. See [Dashboard](#dashboard).
- Educators add learners by email or CSV file, see whether each is active, pending or inactive, manage their cohorts and course registrations, and deactivate or reactivate them. A quick view previews a learner or cohort without leaving the list. See [Learners](#learners).
- Educators can act on many learners or cohorts at once, including everything matching the current filter. See [Bulk actions](#bulk-actions).
- Educators create, rename, deactivate and delete cohorts, and register a cohort for courses. See [Cohorts](#cohorts).
- The Courses list shows each course's visibility and interest count. Visibility is read-only here. See [Courses](#courses).
- Organisation admins add staff, assign and deactivate their roles, and deactivate or reactivate them. See [Staff and roles](#staff-and-roles).
- Site and organisation admins see who changed what and when, on learner and cohort pages and in an Audit log. See [History](#history).
- A cohort's progress report shows on screen, with a PDF to download. See [Reports](#reports).
- Access is granted by role: site admin, organisation admin, cohort admin or cohort viewer. See [Access control](#access-control).
- **Limits:** educators cannot see or set deadlines, and moving or deleting in bulk and updating existing learners from a file are not built. See [Limits](#limits).

## Dashboard

![Dashboard with learner, cohort, average progress and needs-attention tiles above the list of learners needing attention](screenshots/educator_dashboard.png)

The dashboard is the first page an educator sees. It covers every active cohort they can see in the current organisation: tiles for learners, cohorts, average progress and learners needing attention, a list of flagged learners across those cohorts, and one progress row per cohort. A cohort larger than the report's learner limit is left out, and the dashboard says so. There are no charts.

A learner with nothing to do yet, because their cohort is not registered for a course, is never flagged as needing attention, and nor is a learner who has finished everything. Overdue learners are not flagged either; see [Limits](#limits). The figures are recalculated every few minutes rather than live, and the page says when they are from. See [Reports](#reports).

## Learners

### The list

![Learners list with search, status filter and Export CSV above a table of each learner's status, cohorts and course progress](screenshots/educator_learners_list.png)

The Learners list shows the learners of the current organisation the educator has access to: learners in cohorts they can see, plus, for an educator holding an organisation-wide role, everyone associated with the organisation, whether or not they are registered for anything yet. Someone studying with more than one organisation appears once per organisation, with only that organisation's cohorts and registrations.

Each learner is **Active**, **Pending** (staff created their account and they have not yet set a password and signed in) or **Inactive**. The list shows Active and Pending until the Status filter asks for others, and clearing the filter returns to that view. A learner with no name is shown by email. The list can be searched, filtered and sorted, and **Export CSV** downloads what the list shows (name, email, status, cohorts, courses and last active date), narrowed by the current search and filters. A cohort's Learners tab exports the same way.

### The learner page

![A learner's page with the name and email above Overview, Courses, Messages, Settings and History tabs](screenshots/educator_learner_page.png)

The header shows the name and email, and a badge only while the learner is Pending or Inactive. The tabs are:

- **Overview**: details, cohorts and course registrations.
- **Courses**: for each registered course, completion, a progress status and any at-risk flags, the items completed and the last one, and every quiz attempt with its score and the quiz's pass mark.
- **Messages**: when direct messaging is turned on. See [Messaging from a learner](#messaging-from-a-learner).
- **Settings**: every action that changes the learner, listed below. Shown to anyone who may take at least one of them.
- **History**: see [History](#history).

From the Settings tab an educator can:

- **Add to a cohort, remove, or move** a learner to another active cohort in the organisation. Each confirmation names the courses the learner loses access to. A move carries course progress across, keeping whichever record is further along for a course both cohorts give access to. Nothing is deleted.
- **Register for a course**, and deactivate or reactivate a registration. Any course that is not coming soon can be registered, but not one that is closed to the learner's organisation, which is refused with a message. Deactivating a registration keeps progress and says whether a cohort still gives access to the course.
- **Deactivate or reactivate** the learner. Deactivating removes access to this organisation's courses while keeping cohorts, registrations and progress, which return on reactivation. On the site's default organisation, a learner can undo a deactivation, of themselves or of a registration, by registering for an open course themselves.
- **Edit the name.** Only a site admin can. Email is the learner's login for every organisation, so it is changed in the Django admin; see [admin interface](./admin-interface.md#learner-rosters).

Cohort admins manage membership and course registrations within their own cohorts. Adding, deactivating and reactivating learners, and resending the account setup email, need an organisation admin or site admin. Learners are deactivated here, never deleted. Each action sends a [webhook](./webhooks.md) event.

### Quick view

![Learners list with a learner's quick view open on the right, showing status, cohorts, course registrations and a message box](screenshots/educator_learner_quick_view.png)

Selecting a learner's or cohort's preview control opens a summary beside the list, with a link through to the full page. On a wide screen it sits beside the list; on a phone it opens as a sheet. For a learner it shows email, status, cohorts, course registrations with progress, and when they were last active. For a cohort it shows status, learner count and courses. It shows only what the educator could already see on the full page. Courses have no quick view.

### Messaging from a learner

When direct messaging is turned on, the learner's quick view shows the latest messages with that learner and a composer to reply, and the learner's Messages tab shows the signed-in educator's own conversation with them. Who an educator may message follows the messaging policy; see [messaging](./messaging.md).

Organisation admins and site admins also see, on the Messages tab, a read-only list of the learner's other conversations with their educators, and can open one to read it. Each open is recorded in the learner's History. No other role has this.

### Adding learners

Organisation admins and site admins paste up to 50 email addresses, optionally with names, and can put them straight into a cohort. An address that already has an account on the site joins the organisation and keeps its name; a new one gets an account and an **account setup email** with a link to choose a password, which can be resent from the learner's page. The dialog reports what happened to each address. Staff-created people still meet the site's terms and registration forms at first login.

### Importing learners

![Import preview with a count for each row label, and the table of rows below](screenshots/educator_learner_import_preview.png)

Organisation admins and site admins import larger lists from a CSV file, from the Learners list or into one cohort from its Learners tab, in three steps: upload, preview, result. A downloadable template shows the columns: `email` (required), `first_name`, `last_name` and `cohort`. On a cohort's page everyone goes into that cohort; otherwise `cohort` is matched by name to an existing active cohort. Cohorts are never created from a file, and people are treated as in the add-by-email dialog.

The preview labels every row (new account, joined, reactivated, added to cohort, already a member, or error) with counts, before anything is written. Rows with errors can be downloaded as a CSV and do not stop the valid rows. A file is rejected whole if it is over 1 MB or has more rows than `LEARNER_IMPORT_MAX_ROWS` (default 2000). Imports over `BULK_BACKGROUND_THRESHOLD` rows (default 250) continue in the background with a result page that shows progress; no notification is sent when an import finishes. Background runs need the worker process described in [deployment](./deployment.md#background-tasks). Cohort admins cannot import, and an import cannot update an existing person's details.

### Bulk actions

![Bulk add to cohort confirmation, with the cohort picker above a sentence saying what will change](screenshots/educator_bulk_add_to_cohort.png)

Tick rows in the Learners or Cohorts list and an action bar appears. When every row on the page is ticked and the filter matches more, **Select all N matching** extends the selection to every match. Changing page, sort or filters clears the selection.

- **Learners**: add to a cohort, remove from a cohort, register for a course, deactivate a course registration, deactivate, reactivate, and resend the account setup email.
- **Cohorts**: register for a course, deactivate a course registration, deactivate and reactivate.

Each action offers only what the educator could do to a single learner or cohort, and each row is checked on its own. Rows the educator may not change are skipped rather than blocking the rest. Nothing runs before a confirmation that says what will change and how many rows will be skipped, and why. Afterwards a result names the skipped and failed rows. Each row is handled as if done by hand, so [webhook](./webhooks.md) events and emails fire once per learner or cohort changed.

Runs over `BULK_BACKGROUND_THRESHOLD` rows (default 250) continue in the background: the educator can leave the list, and an in-app notification says when the run is done.

## Cohorts

![Cohort page on its Overview tab, with details, course completion and needs-attention list](screenshots/educator_cohort_overview.png)

The Cohorts list shows each cohort in the current organisation the educator has access to, with its status, learner count and registered courses. Inactive cohorts are hidden until **Show inactive** is switched on, and the list can be filtered by course. Creating, editing, deactivating and deleting a cohort, and registering it for a course or deactivating that registration, happen in a dialog over the current page. The list takes [bulk actions](#bulk-actions).

- **Creating and renaming.** A name is all a cohort needs, and names are unique within an organisation. **Save and add another** keeps the dialog open to create several in a row.
- **Cohort page.** Tabs are *Overview* (details, completion for each registered course, the educators assigned with their roles, and a needs-attention list), *Learners*, *Courses*, *Report* (see [Reports](#reports)), *Settings* (renaming, deactivation and deletion) and *History* (see [History](#history)). The Learners tab adds learners, and removes or moves one from their row.
- **Registering for courses.** The Courses tab registers the cohort for any course that is not coming soon and not closed to the organisation, and deactivates a registration from its row. Deactivating is reversible and everyone keeps their progress. The confirmation says how many learners lose access and names those who keep it through another registration.
- **Deactivating.** An inactive cohort's registrations give no access to their courses and the cohort becomes read-only, so it takes no membership action. Learners keep their place and progress, and reactivating restores access. See [learner tracking](./learner-tracking.md#what-is-recorded).
- **Deleting.** Only while the cohort has no learners and no course registrations, inactive ones included; otherwise the Settings tab says what still depends on it. Deleting a cohort also deletes the cohort roles held on it.

Renaming, deactivating, reactivating and deleting need an organisation admin or site admin. A cohort admin can register their own cohort for courses and deactivate those registrations. An organisation admin can add a staff member to the cohort from the Overview's educators panel; roles are changed from [Staff](#staff-and-roles).

## Courses

![Courses list with each course's visibility, interest, active learners, active cohorts and cohorts](screenshots/educator_courses.png)

The Courses section is read-only and scoped to the current organisation. It lists every published course, plus any course registered to a cohort or learner the educator can see, so a hidden or coming-soon course appears only where this organisation uses it. A course that belongs to other organisations and is not public is not listed; see [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations). Cohorts are registered for courses from the cohort page.

Each course shows its **visibility** (published, coming soon or hidden), its active learner and cohort counts, and the cohorts registered for it. Counts and links include only what the educator can see, and inactive cohorts are not counted. A course's page shows the title and category, the cohorts registered with each cohort's status, and any direct registrations.

Each course also shows an **interest count**: the learners who have expressed interest through the coming-soon waitlist, counted site-wide rather than per organisation and shown for every course, so a launched course still shows the demand it attracted. Who expressed interest, and when, is read in the Django admin; see [admin interface](./admin-interface.md).

Visibility is set only in the course's content frontmatter and takes effect on import; see [content editing workflow](./content-editing-workflow.md). Learners' experience of coming-soon and hidden courses is in [learner experience](./learner-experience.md).

## Staff and roles

![Staff list with each staff member's roles, the cohorts a role covers and who added it, and an Add staff member button](screenshots/educator_members.png)

Staff are the people who help run an organisation, whether or not they teach. A staff member holds one or more roles in the organisation:

- **Organisation admin**: manages learners, cohorts and staff in this organisation.
- **Cohort admin**: manages the learners and course registrations in their cohorts.
- **Cohort viewer**: sees the learners and progress in their cohorts, and changes nothing.

A fourth role, **site admin**, gives full access to every organisation on the site. It is not given from this interface (see [Limits](#limits)), and a site admin is listed as staff of an organisation only through a role they hold in it. A learner is a staff member only if they also hold one of these roles.

The Staff section is visible only to organisation admins and site admins. It lists each staff member with their roles, the cohorts a cohort role covers, and who added each role and when, and can be searched and filtered by role. From it an organisation admin can:

- **Add a staff member** by email. An existing account shows that person's name and email before anything is saved; a new address gets an account and an [account setup email](#adding-learners). The admin picks one role and, for a cohort role, the cohorts it covers, which does not extend to cohorts added later.
- **Change the cohorts** on a cohort role.
- **Deactivate a role.** The person keeps their account, their other roles and any place as a learner.
- **Deactivate a staff member**, which stops everything they can do in this organisation while keeping their roles, and **reactivate** them.

Admins can give only roles at or below their own. A change that gives someone access they did not have, or takes access away, is confirmed first and says what changes. Roles add up: to change someone's role, assign the new one and deactivate the old. The person is not notified when a role is assigned or deactivated, a setup email cannot be resent from this section, and staff members have no page of their own. Role changes and staff deactivations are recorded in the [Audit log](#audit-log).

## History

### History tabs

![A cohort's History tab listing when, who, what, target and details for each change](screenshots/educator_history.png)

The educator interface records who changed what, and when, for the actions educators take here: learner changes, cohort membership and course registrations, cohort changes, and member roles and deactivations. The record shows as a **History** tab on a learner's page and on a cohort's page. A move between cohorts appears on the learner and on both cohorts. Each row shows when, who, what and any details, and the cohort tab also names the person each row is about. Deleting a cohort also records each role that went with it, and the learner's History tab shows each time an admin opened one of the learner's conversations. Changes with no user behind them show as "System".

### Reasons

![Deactivate dialog for a learner, saying what is kept and offering an optional Reason shown only to staff](screenshots/educator_confirm_with_reason.png)

Confirming a removal or deactivation (removing a learner from a cohort, deactivating a course registration, deactivating a learner or cohort, deleting a cohort, deactivating a role, deactivating a member) offers an optional **Reason**, shown in the history to staff only. Every confirmation says what stops, what is kept and how to undo it.

### Audit log

![Audit log table of when, who, what, target and details, with an Add filter control](screenshots/educator_audit_log.png)

The Audit log, under Administration, lists the current organisation's entries, newest first, filtered by who, by what and by when, and names the person each row is about. Only site admins and organisation admins see it and the History tabs; cohort admins and cohort viewers do not.

Not recorded: anything before the feature was installed (there is no backfill), records edited directly in the Django admin, and logins. The log has no search or CSV export, and entries cannot be edited or undone. For how long entries are kept and how they are protected, see [security and data handling](./security-and-data-handling.md#audit-log-built).

## Reports

![A cohort's Report tab with a Downloads table and a Generate report button beside its title, above the on-screen cohort report](screenshots/educator_cohort_report.png)

A cohort's **Report** tab shows the [cohort report](./reports.md) on screen: the cohort at a glance, the learners needing attention, a progress summary per course with quiz scores, and the quiz confusions. Per-learner detail stays in the PDF. An educator with the report download capability generates the PDF from the same tab, with a button beside the Downloads title, and the table under it lists the last five finished reports with who generated each one and when. A report that has not finished after ten minutes can be started again. While the cohort is over the report's learner limit the button is disabled and the reason sits beside it.

On-screen figures, here and on the dashboard, are recalculated every few minutes (see `REPORTS_SCREEN_CACHE_SECONDS` in [configuration and extension](./configuration-and-extension.md#settings-reference)) and each page says when its figures are from. Adding or removing a learner, or registering a course or deactivating a registration, shows at once; new progress shows at the next recalculation, or when the Report tab's Refresh is pressed.

## Organisation scope

The educator interface is scoped to one **organisation** at a time. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md#organisations) for what an organisation is and where the isolation boundary sits, and [admin interface](./admin-interface.md#organisation-management) for how organisations are created.

The current organisation is part of every page's address, so two browser tabs can sit on two organisations at once and any page can be linked to directly. A switcher at the top of the sidebar names the current organisation; where an educator can reach more than one, it opens a list to switch between them. Switching while viewing a cohort or learner that does not belong to the new organisation returns to the equivalent list with a notice.

![Organisation switcher open in the educator sidebar](screenshots/educator_organisation_switcher.png)

## Access control

Access comes from **role assignments**; permissions granted on a cohort or organisation in the Django admin have no effect here. The roles are described in [Staff and roles](#staff-and-roles).

A person holding several roles gets all of them. A role on an organisation covers every cohort in it, including ones created later; a role on a cohort covers that cohort and its learners. Organisation and cohort roles count only while the person is an active member of that organisation: deactivating a member switches off their access without deleting their roles, and reactivating restores it. Organisation admins can assign roles only within their own organisation, nobody can change their own roles, and an organisation's last admin can have the role deactivated, or be deactivated as a member, only by a site admin.

Listings and detail pages are limited to what the educator's roles cover, and an educator who opens a page outside their access gets the same "not found" as for a record that does not exist. Every write is checked before it runs, and a control the role does not allow is hidden rather than shown disabled. If an educator acts from a page that was open when their access was removed, or the record has left their access, a dialog says the action can no longer be used there and names who to ask: the organisation's admins by name where the educator may see them, otherwise "an administrator".

All queries stay scoped to the current site, so nothing here crosses a tenant boundary. See [multi-tenancy and isolation](./multi-tenancy-and-isolation.md).

## Accessibility and small screens

![Learners list at phone width, with each learner as a card showing status, cohorts, courses and last active](screenshots/educator_learners_mobile.png)

The interface is designed for phones as well as desktop. On a phone, tables become cards, filters open in a sheet, sorting is a menu of columns, and the quick view is a sheet; controls are at least 44px high on phones. Both themes, default and first class, are light only: there is no dark mode.

Every action works by keyboard. Dialogs and the quick view take their names from their headings, move focus in when opened, close on Escape and return focus afterwards; tables are labelled and mark the sorted column; and results and notices are announced to screen readers. Text and borders are designed to meet WCAG contrast targets in both themes.

Not done: no screen reader (NVDA, VoiceOver or TalkBack) has been run through the screens, only a browser check of names, announcements and keyboard flow. Inline links inside table cells and the footer's Terms and Privacy links are smaller than 44px on a phone.

## Limits

These are not available in the educator interface:

- **Bulk operations**: moving several learners between cohorts, deleting in bulk, and bulk actions on a cohort's Learners tab or on Staff. Imports cannot import anything but learners.
- **Email changes**: a learner's email is changed in the [Django admin](./admin-interface.md#learner-rosters).
- **Deleting a learner**: learners are deactivated, never deleted, here.
- **Site admin**: the role is not assigned or deactivated from the educator interface, nor from the Django admin.
- **Deadlines**: due dates, time limits, deadline overrides and overdue status are not shown or set here, and overdue learners do not appear in needs-attention lists. Overrides are set in the Django admin; see [admin interface](./admin-interface.md#deadline-overrides).
- **Dark mode**: neither theme has one.

Educators cannot send email to learners from FLS, and there is no group or broadcast messaging; see [messaging](./messaging.md#not-built). Remaining gaps are in the [roadmap](./roadmap.md).
