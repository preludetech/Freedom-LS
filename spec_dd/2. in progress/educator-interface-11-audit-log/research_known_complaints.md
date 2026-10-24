# Research: known complaints about audit logs and activity history

Question: what do staff, admins, operators and developers commonly complain about with audit log features?

Method and honesty note: a handful of web searches (standard mode). Evidence is thin for some themes. Where a theme is not backed by a source I fetched, it is marked "general knowledge / not verified here". No Open edX, Blackboard, TalentLMS, Docebo or LearnWorlds threads were found in this pass, and no django-auditlog issue threads were retrieved.

## Findings by theme

### 1. Missing who (actor) or why
- Canvas: admins asked who added or removed a student. The answer was that the enrollments API shows when an enrollment was created but not the user or system that created it. Others asking who extended a deadline were told audit logging seemed not to exist, with support tickets as the workaround. Students cannot see grade history at all.
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Enrollment-Audit-Log-for-course/m-p/539553
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Student-removed-from-courses/td-p/559261
  - https://community.canvaslms.com/t5/Canvas-Question-Forum/Viewing-Grade-History-as-Student/m-p/645633
- "Why" is almost never captured in any product reviewed (general knowledge; the idea's Open edX reason prompt is the exception).

### 2. Coverage gaps: some actions logged, others not
- Canvas keeps grade change logs but enrollment, deadline and user add/delete changes are scattered across account reports and Canvas Data. A Canvas idea thread asked for detailed logs in the GUI (grade, enrollment, user add/delete changes) and was archived because "parts of it exist" elsewhere. Users said there is too much data to comb through, and Canvas Data querying is too heavy for these questions.
  - https://community.canvaslms.com/t5/Idea-Conversations/Access-to-detailed-Canvas-logs-in-GUI/idi-p/316181
  - Sub-account admins cannot view grade change activity in Admin Tools: https://community.canvaslms.com/docs/DOC-2999
- django-simple-history: history is written from post_save signals, so bulk_create, bulk_update and queryset update() write no history unless special helper functions are used. Classic "silent hole" complaint for signal-based logging.
  - https://django-simple-history.readthedocs.io/en/stable/common_issues.html
- Microsoft 365: auditing must already be on when the event happens; past events cannot be recovered. https://www.syskit.com/blog/onedrive-audit-log
- Implication class: system and bulk code paths that bypass the normal save path are the ones that go unlogged.

### 3. Slow pages and table bloat
- Moodle: a query on a ~34 million row log table took ~35 s versus under 1 s on a small table; heavy log report queries blocked log inserts and so blocked almost all site traffic (old issue, closed Won't Fix). https://tracker-old.moodle.org/browse/MDL-75591 and https://tracker-old.moodle.org/browse/MDL-11901
- Moodle cron cleanup of logs was reported slowing cron runs (same tracker family).
- ABP Framework (.NET): slow viewing at ~3 million AuditLogs rows, with the poster unable to delete periodically because of retention requirements. https://support.aspnetzero.com/QA/Questions/9720/AuditLogs-table-performance-and-optimization
- Generic advice: lean log model, proper indexes, retention strategy, decouple writes from the request. https://medium.com/@djangowiki/django-activity-logs-performance-9bc352ce69ea
- One-table-for-everything is called out as a heavy-db risk by another Django package. https://pypi.org/project/awesome-audit-log-django/

### 4. Retention too short, or unbounded growth
- Both sides appear. GitHub Enterprise Cloud: most events up to 6 months (UI shows 3 months by default), Git events 7 days; Enterprise Server defaults to indefinite unless configured. https://docs.github.com/en/enterprise-server@3.15/admin/concepts/security-and-compliance/audit-log-for-an-enterprise and https://resources.github.com/learn/pathways/administration-governance/essentials/access-capture-consume-audit-logs
- Atlassian Guard: a 10,000-entry cap means large organisations lose events in as little as 14 days. https://jira.atlassian.com/browse/ACCESS-991
- Moodle: docs advise limiting retention (a year is typically enough); cron deletes only for about five minutes per run so shrinking a large table takes a long time; manual deletes need backups and hurt performance. https://moodle.org/mod/forum/discuss.php?d=111131 and https://docs.moodle.org/27/en/Cleanup
- Nintex K2 moves old entries to an archive table. https://help.nintex.com/en-US/k2five/DevRef/5.4/Content/DBRef/AuditLog-Archive.html

### 5. Can't filter, search, or find things; too much data
- Canvas thread above: "way too much data to comb through". Canvas Admin Tools grade log is searchable only by grader, student, course ID or assignment ID, so you need to know IDs up front.
- Microsoft 365: search cmdlet returns only 100 records by default, so scripts appear to "miss" events unless the large-set option is used; events take 60-90 minutes (up to 24 h) to appear. https://learn.microsoft.com/sv-se/powershell/module/exchange/search-unifiedauditlog and https://www.syskit.com/blog/onedrive-audit-log
- Silent truncation and ingestion lag are the complaint; a visible "showing N of M" and a clear time-of-write guard against it.

### 6. Noise
- GitHub moves Git events out of the UI because of volume, exposing them only through export and streaming. https://docs.github.com/en/enterprise-server@3.15/admin/concepts/security-and-compliance/audit-log-for-an-enterprise
- Moodle standard log records views and every page hit, which is the main driver of its table size (general knowledge; see tracker links above).
- Bulk actions as thousands of per-object entries is a recognised noise pattern (general knowledge / not verified with a source here).

### 7. No export or long-term storage
- GitHub offers UI, API and streaming; users stream to S3 and query with Athena for long-term storage. https://dev.classmethod.jp/articles/github-enterprise-cloud-audit-log-integratin-aws-s3-athena/
- Canvas users fall back to the API or Canvas Data for answers the UI cannot give.

### 8. Timezone confusion
- Only weakly evidenced: a third-party troubleshooting page advises widening search windows for timezone differences (https://www.wps.com/office-quick-solution/security-issues/how-to-generate-sharepoint-online-audit-log-reports/). No official Microsoft guidance on UTC handling was found. Treat as plausible, not established.

### 9. Unreadable entries, deleted targets, editable logs, privacy
- Not directly sourced in this pass. General knowledge, to verify if the spec depends on it: id-only entries become meaningless after the target is deleted (the idea already stores a label); logs that live in ordinary editable tables are not trusted as evidence; logs holding personal data raise retention and erasure questions.

## Implications for this feature (educator-interface-11-audit-log)

Already addressed by the idea: actor plus nullable system actor, stored target label, organisation scope, optional reason, one summary entry per bulk run, writes in the action transaction, no update or delete, retention command, filter by actor/action/date, paged history tabs, past-tense fixed vocabulary.

Suggested additions or sharpened decisions for the spec:
1. Index for the actual read paths: (organisation, when), (target type and id, when), (actor, when). Moodle shows unindexed or huge log reads hurting the whole site. Page with a hard cap and never `COUNT(*)` over the full table without a filter.
2. Write only meaningful, state-changing actions from the fixed vocabulary (no views, no reads). This keeps noise and bloat down; matches the idea's "one summary per bulk run".
3. Bypass risk: the simple-history lesson. Because writing is explicit in service code, not signal-based, the spec should require a test per capability in the spec 5 matrix proving an entry is written, including bulk paths and queryset `update()` call sites, and state that new actions must add an entry.
4. Actor must never be lost when a user is deleted: keep the actor FK nullable with SET_NULL but also store an actor label, the same way the target label is stored. Distinguish "system" (null actor by design) from "actor deleted" so Canvas-style "who did this?" gaps do not reappear.
5. Bulk summary entry: show counts in the list and per-object detail on expand/detail, and have the per-learner and per-cohort history tabs find bulk runs that touched them (otherwise a learner's history silently omits bulk moves). Decide how per-object detail in JSON is bounded in size.
6. Show truncation honestly: display "newest N of M" or paging totals, and tell the user whether filters are applied (Microsoft 100-record default complaint).
7. Times: store UTC, render in the site timezone and say which one in the column header or tooltip (low evidence, cheap to do).
8. Retention: keep the default of keep everything, with the prune command batching its deletes (Moodle's slow, blocking cleanup) and logging how many rows it removed. Document that pruning is the one sanctioned delete path and that it bypasses the append-only guard deliberately. Consider an "oldest entry available" note in the UI so a short retention is not mistaken for no activity.
9. Export: the idea has none. Complaints show that admins reach for APIs when the UI cannot answer. A filtered CSV export of the organisation log is a small, likely-asked-for addition; flag as an open question rather than silently adding (project rule: do not build what is not requested).
10. Privacy: entries hold learner names and reasons. Keep the log staff-only (matrix row for site admin and organisation admin), keep reasons free of requirement, and decide in the spec how learner erasure interacts with stored labels (the stored label is a copy of personal data).
11. Read-only admin and no edit/delete in application code give the "cannot be edited" property only against application paths; say so plainly in the spec rather than claiming tamper-proofing.

## Gaps
No evidence gathered on: Open edX, Blackboard, TalentLMS, Docebo, LearnWorlds, Google Workspace, Slack, django-auditlog issue threads. Run follow-up searches if the spec needs them.

status: ok
