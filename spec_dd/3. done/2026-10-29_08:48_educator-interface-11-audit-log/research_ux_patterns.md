# Research: UX patterns for an audit log shown to staff

Spec 11 (audit log). Question: what are the common UX patterns for showing an audit log or activity history to staff in admin interfaces?

Evidence labels: **[fetched]** means read from the page this session. **[prior note]** means taken from `spec_dd/1. next/educator-interface-full-polish/comparable-systems-learner-management.md` (which cites the URLs given). **[general]** means widely seen product behaviour that I did not re-verify this session; treat it as a design heuristic, not a citation.

## 1. What the project already gives us

- **Tables (spec 2, done).** `DataTable` with `Column` (with a `card` grouping for mobile), declared filters (`ChoiceFilter` multi-value, `RelatedChoiceFilter`, `BooleanFilter`), chips and an "Add filter" `<details>` disclosure that works without JavaScript, sort, pagination, CSV export through `get_export_columns()` (GET `<key>-export=csv`, honours search/filter/sort, streams, formula-safe, BOM), and a mobile card list below `md` with a "Filter & sort" bottom sheet. There is no date-range filter type. The three filter types are choice, related-choice and boolean. A date range needs either a new `TableFilter` subclass or presets declared as a `ChoiceFilter` (for example "Last 7 days", "Last 30 days", "This term"), which fits the existing no-JS link toggling. `ChoiceFilter` takes several values, which maps onto an action multi-select. The mobile card for a log row should use `card="primary"` for the sentence and `secondary` for time and reason.
- **Design mockups** (`Educator LMS Interface Design/`): no history or audit screen. The only matches for "activity" are a learner "Activity" column in `Educator Learners.dc.html` and `Educator Mobile Learners.dc.html`, and an activity feed block on `Educator Dashboard.dc.html` (line 73). Use the Learners table toolbar and the mobile M03/M04 sheet as the visual reference. Do not invent a new layout language.
- **Brand voice** (`.claude/skills/brand-guidelines/voice.md`): direct, specific, technical, no SaaS phrasing. Routine messages end on a full stop. Use "learners" not "students". Error text names the problem and a fix. Empty state sample: "No courses yet. Drop some Markdown files ... to get started." The same shape suits the log: state the fact, then say what produces entries.

## 2. Comparable systems

- **GitHub organisation audit log [fetched]** https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization
  Entries are named `category.operation` (`repo.create`, `team.create`) and show the actor, affected user, target, action and date/time. Filtering is qualifier text (`actor:`, `action:`, `operation:`, `created:` with `>=`, `<=`, `..` ranges), with no free-text search. The default view is the last three months. Older events need an explicit `created:` date. Retention is 180 days. Export is JSON or CSV, applies the current qualifiers, and is capped (100 MB / 10 minutes), so narrowing first is advised. Event-specific data sits under `data.*` keys. Takeaways: a stable action vocabulary that doubles as the filter, a default time window, export honouring filters, details as a keyed bag.
- **Google Workspace admin audit / Classroom log events [prior note]** https://support.google.com/a/answer/11479793 and https://support.google.com/edu/classroom/answer/11362627
  Under Reporting > Audit and investigation. The default view is the last 7 days. It filters by date range and other fields, and tracks "who removed a student from a class or archived a class". BigQuery export on higher tiers: https://workspaceupdates.googleblog.com/2021/09/google-classroom-activity-audit-logs-and-big-query-activity-logs.html . Takeaway: a short default window and a question-shaped framing ("who removed...").
- **Moodle logs report [prior note]** https://docs.moodle.org/502/en/Log_in_as and the Logs report in the same docs. Filters by course, user, day, activity and action, with download. Dense table, one row per event, columns Time, User, Affected user, Event context, Component, Event name, Description, Origin, IP. Takeaway: a "Time / Actor / Affected / Description" column set is the long-standing LMS layout. Moodle also separates a "Course participation" report from the log, so the log can stay a plain record.
- **Open edX [prior note]** `ManualEnrollmentAudit` in edx-platform's support app records staff enrolment and unenrolment with a reason text, who, when, and the before/after state. The prior note says the reason is "a specific, detailed reason" in the Open edX flow, while the idea fixes FLS to optional and never required. Follow the prompt placement from Open edX but not its required-ness. The prior note also records an LMS-wide tracking log that is not staff-readable.
- **Canvas [prior note]** Admin Tools has Logging tabs (grade change, course activity, enrollment activity), searched by user or course and date range, plus a separate login/logout activity view that depends on permissions. Takeaway: log views split by subject (grades, enrolment), which maps loosely to FLS's per-learner and per-cohort tabs.
- **Docebo Audit Trail [prior note]** https://help.docebo.com/hc/en-us/articles/360020124059-Managing-the-Audit-trail . Described as immutable, with who (including impersonator), what resource and when. Event catalogue: https://help.docebo.com/hc/en-us/articles/6095145987346-Audit-trail-events-details . Retention not found.
- **TalentLMS Timeline [prior note]** https://help.talentlms.com/hc/en-us/articles/9652229276828-How-to-work-with-the-extended-timeline . Filters by event type, date range, user and course; CSV export.
- **Slack, Stripe, Sentry, GitLab [general; not verified this session]** The Slack Audit Logs API page I tried (https://slack.com/help/articles/360002084807-Audit-Logs-API) covered access logs only and gave no entry shape, so I cite nothing from it. From general knowledge: Slack, Stripe and GitLab entries all have an actor, an action string, an entity and a time. Sentry's audit log (https://docs.sentry.io/organization/audit-log/ , not fetched) is a plain table of actor, event name and time with a filter on event. GitLab's group audit events (https://docs.gitlab.com/ee/administration/audit_event_reports.html , not fetched) filter by actor, target and date range and allow CSV export. None of this changes the recommendations below.

## 3. Patterns and recommendations

### 3.1 Entry sentence structure
Common shape: **actor + past-tense verb + target + optional qualifier**. GitHub uses a machine action name; Moodle uses a description column. For FLS, where the audience is non-developer staff, render a sentence and keep the raw action string as a small secondary label or filter value only.

- "Ana deactivated Ben. Reason: left company."
- "Ana moved Ben from Cohort A to Cohort B."
- "Ana removed Ben from Cohort A."
- "Ana ran a bulk deactivation: 14 learners, 2 skipped."
- "System expired 3 registrations." (system actor)

Build the sentence from the stored `action` plus the stored target label and the details JSON, in one place (a registry keyed by vocabulary string, each with a template and a details formatter). An unknown action (from a later version or a downstream project) falls back to "<actor> <action> <target label>" so the log never breaks. Use the project's words (learner, cohort, registration, organisation). Keep the reason on its own labelled line or after a full stop, not inline with a dash, so it is searchable and screen-reader friendly. A trailing full stop follows the brand voice.

### 3.2 Timestamps
- Relative ("3 hours ago") for the last day or so, absolute beyond that [general]. Accounting needs unambiguous time, so always make the absolute value available: render `<time datetime="2026-10-24T09:14:00Z" title="24 Oct 2026, 09:14 SAST">` with the relative text visible, or the reverse. Relative text alone decays when a page is cached or left open.
- In the org-level table use absolute date and time (a log is looked up by date). In the learner/cohort History tab use grouped day headings plus time of day, with relative only for "Today".
- Show the viewer's configured time zone; say which one in the column header or a tooltip if the project does not already.

### 3.3 Grouping by day
Per-subject history (learner, cohort) reads well as a timeline: a day heading ("Today", "Yesterday", "Mon 20 Oct 2025") then entries with a time. The org-level log is a filterable table, where groups add little (GitHub, Moodle and Google use flat rows). With paging, a day can span a page break. Either repeat the heading at the top of the next page or group per page only, and state which. Grouping is a presentation concern: group in the template with `{% regroup %}` or `itertools.groupby` over an already ordered page, never by changing the query.

### 3.4 Actor display
- **System action** (actor null): "System" in the actor position, never blank or "None". Optionally the action's source in details (management command, import, expiry).
- **Deleted or deactivated user**: show the stored name or email captured at write time. This means the model should store an actor label too, since the idea stores a label for the target only. Mark a deactivated actor in quiet text ("Ana (deactivated)"). Do not link to a deleted actor.
- **Impersonation** (Docebo): out of scope for FLS now, but a single details key would keep the door open.
- Actor identity should be a human name with email on hover or as the secondary line. GitHub's `actor:` accepts a username only, which is a known annoyance; FLS filter choices should list names.

### 3.5 Links to targets that may be gone
Store a label at write time (already settled). Render the label as a link only if the target still resolves and the viewer can see it; otherwise plain text, optionally with "(removed)" in muted text. Resolving needs one query per content type, so batch by content type for the page (prefetch the generic key) to avoid N+1 queries. A deactivated learner still has a page, so link; a hard-deleted object does not. Never raise on a missing target.

### 3.6 Reasons and details
- Reason: show inline under or after the sentence, in quoted or labelled text, and omit the label entirely when none was given (no "Reason: none"). Truncate long reasons in the table and show the full text in the expanded row.
- Details (move source and destination, bulk counts): inline for one or two short facts; for bulk runs, a summary line ("14 learners, 2 skipped") with a disclosure. `<details>/<summary>` works with no JavaScript and is keyboard accessible, and it fits the framework's existing `<details>` use. The expanded area lists per-object results (the JSON field) as a plain list, with a cap and "and N more" to keep the row bounded. A bulk run is one summary entry, so the detail view is a modest list, not a second log.
- Raw JSON is for export and the admin, not for staff-facing screens.

### 3.7 Filter controls
- **Actor**: a `RelatedChoiceFilter` of people who appear in the log for the organisation (scoped like the table queryset), not every user. Include "System" as a choice.
- **Action**: multi-select `ChoiceFilter` over the vocabulary, with human labels ("Learner deactivated"). GitHub groups by category (`team`, `repo`) and operation; a group per subject (learner, cohort, registration, role, import) is worth considering if the vocabulary grows beyond about a dozen.
- **Date**: presets (Today, Last 7 days, Last 30 days) plus a custom range of two date inputs. Google defaults to 7 days and GitHub to 3 months; a default window keeps the first load cheap. If a default is applied, show it as a visible chip so staff know the list is narrowed. The existing "Clear all" covers removal. A custom range needs a new filter class because spec 2 ships none. Use `<input type="date">` with the HTML min/max, and treat the end date as inclusive of that whole day. Dates are interpreted in the display time zone.
- Searching free text across details is a long-tail feature (GitHub does not do it). Not needed first.
- Filter state in the URL (spec 2 already does this) so a filtered view can be shared or bookmarked, which matters for "send me the link to what you saw".

### 3.8 Empty states
Two cases, as in spec 2's tables: nothing recorded yet, and nothing matches the filters. In the brand voice:
- Nothing yet (learner tab): "No history for this learner yet. Actions such as moving or deactivating them are recorded here."
- Filters match nothing: "No entries match these filters. Clear them, or widen the date range." with a "Clear all" link.
- If a retention prune has run, say so only if the data can be known; otherwise leave it out.

### 3.9 Paging vs infinite scroll
Every comparable log uses numbered or next/previous paging (GitHub, Moodle, Google) [general]. Infinite scroll breaks the footer, bookmarkable position, keyboard navigation and "find on page", and is a poor fit for a record staff search. Use spec 2's pagination. Default 25 per page, newest first, with a stable tie-break order (time then primary key) so entries do not repeat or vanish across pages. For a large organisation, avoid a total count over the full table where possible; check what spec 2's footer requires before deciding.

### 3.10 Export
GitHub and TalentLMS offer CSV, and Google/GitHub offer richer formats at higher tiers. Spec 2's CSV export already exists and honours filters and skips paging. Reuse it. Columns: time (ISO 8601 with offset), actor (name), actor email, action (vocabulary string), target label, target type, reason, details (JSON string). Keep to the same formula-escape rules. The org-level log is the only place to offer export; per-learner export is probably not needed. Note GitHub caps exports and advises narrowing first; with `iterator(chunk_size=500)` streaming FLS needs no cap, but a permission check is needed since the log holds personal data.

### 3.11 Mobile layout
Spec 2's rule applies: a card per entry. Primary line: the sentence. Secondary: time, and the reason line when present. Expandable details via `<details>` inside the card. Filters in the bottom sheet. A timeline on the learner/cohort tab already suits a narrow screen: a single column with day headings, the time left or above. Avoid a multi-column table that scrolls sideways.

### 3.12 Accessibility of timelines
- Use an ordered list (`<ol>`) for the entries, with `<h3>` or `<h2>` day headings. A sequence is semantically a list, so no ARIA roles are needed. Do not rely on a decorative vertical line or coloured dots to carry meaning; if icons mark the action type, give them text (or `aria-hidden` plus visible text).
- `<time datetime>` for every timestamp; absolute time available to assistive technology, not just on hover (a `title` alone is not reachable by keyboard or touch). Show it as visible text or in an expanded row.
- `<details>/<summary>` for expanders: keyboard operable with a clear label ("Show 14 learners"). Do not use hover-only reveals.
- Paging: `<nav aria-label="Pagination">` with `aria-current="page"`, as in spec 2. When an htmx swap replaces the list, follow spec 2's announcement and focus rules rather than inventing new ones.
- Do not convey "System" vs person, or removed vs present, by colour alone.
- On the org-level table: real `<th scope="col">`, and it is a data table so keep table semantics (do not switch to a div grid).

### 3.13 Prompting for an optional reason on removal or deactivation
- **Open edX [prior note]**: staff unenrolling a learner type a reason, stored in `ManualEnrollmentAudit`. **Required there; FLS decided optional.**
- **GitHub [general]**: destructive confirmation dialogs usually ask you to type the name, not a reason. The audit entry records no reason. **Google Workspace [general]**: suspending a user has no reason prompt; it relies on the audit log's actor and time. So the reason prompt is a differentiator, not a convention, and that is fine, but keep it low-friction.
- Recommended shape inside the confirm modal that spec 2 already provides (`confirm_template_name`, count shown: "This will affect 3 learners"): a labelled single textarea or text input "Reason (optional)", below the consequence text, with a help line "Shown in the history of this learner." Make clear whether the learner will see it (the idea says nothing is learner-facing, so state "Only staff can see this."). Submit button labelled with the verb ("Deactivate learner"), not "OK". Pre-focus the confirm button or the reason field? The reason field gets focus is risky because Enter can submit a textarea; use a single-line input or a textarea with the confirm button immediately reachable. A max length (for example 500 characters) with a visible counter or a validation message in the brand's error style, returned as 422 for htmx. An empty value is stored as null, not an empty string. For bulk actions one reason applies to all rows and is stored once on the summary entry (and echoed on each per-object entry if those exist; the spec must decide which).
- Do not default to a canned dropdown of reasons; the idea settled free text. Canned options could be an extension.

## 4. Decisions the spec needs to take (flagged, not decided here)
1. Whether to store an actor label alongside the actor key (3.4). The idea stores a target label only.
2. How date-range filtering is built (new `TableFilter` subclass vs presets only) (3.7), and whether a default window applies.
3. Where the sentence is built (a registry keyed by vocabulary) and its fallback for unknown actions (3.1).
4. Day grouping on the History tab and what happens at page boundaries (3.3).
5. Reason length cap and where the reason is stored for bulk runs (3.13).
6. Whether the export is offered on the org-level log only (3.10), and its permission.
7. Whether "System" appears as an actor filter choice (3.7).

## 5. Gaps in this research
- Slack, Stripe, Sentry and GitLab pages were not read this session. Statements about them are from general knowledge and are labelled as such.
- The Moodle, Canvas, Open edX, Docebo and TalentLMS claims rest on the earlier comparable-systems note, not fresh fetches.
- No screenshot-level comparison of any product was made.

## Sources
- https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization (fetched)
- https://support.google.com/a/answer/11479793 and https://support.google.com/edu/classroom/answer/11362627 (via prior note)
- https://workspaceupdates.googleblog.com/2021/09/google-classroom-activity-audit-logs-and-big-query-activity-logs.html (via prior note)
- https://docs.moodle.org/502/en/Log_in_as (via prior note)
- https://help.docebo.com/hc/en-us/articles/360020124059-Managing-the-Audit-trail and https://help.docebo.com/hc/en-us/articles/6095145987346-Audit-trail-events-details (via prior note)
- https://help.talentlms.com/hc/en-us/articles/9652229276828-How-to-work-with-the-extended-timeline (via prior note)
- https://docs.sentry.io/organization/audit-log/ and https://docs.gitlab.com/ee/administration/audit_event_reports.html (not fetched; listed for the spec writer to verify)
- Project: `spec_dd/3. done/2026-10-03_05:29_educator-interface-2-panel-framework-tables/1. spec.md`, `spec_dd/1. next/educator-interface-full-polish/comparable-systems-learner-management.md`, `.claude/skills/brand-guidelines/voice.md`

status: ok
reason: complete; non-GitHub sources are second-hand or unverified and labelled so
