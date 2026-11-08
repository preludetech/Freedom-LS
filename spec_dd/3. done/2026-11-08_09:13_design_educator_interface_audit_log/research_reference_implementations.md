# Research: reference implementations of audit log presentation and export

Topic: `reference_implementations`. Question: how do reference implementations solve (1) avatars where users are mentioned, (2) export, (3) compact, expandable rows?

Only findings fetched during this research are listed. Where a product could not be verified it is under "Not verified".

## Per-product findings

### GitHub organization audit log
Source: https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization
- Row: organization, acting user, affected user, repository, action, country, date and time. Actor and target are separate fields.
- Filter: qualifier-based search, not free text: `operation`, `repo`, `actor`, `action`, `created` (ISO 8601, ranges), `country`; `-` excludes.
- Retention: 180 days; default view shows the last 3 months.
- Export: JSON or CSV from an Export dropdown. Filters are applied first and carry into the export (`action`, `actor`, `user`, `org`, `repo`, `created`). Keys include `action`, `actor`, `user`, `actor_location.country_code`, `org`, `repo`, `created_at` (epoch milliseconds).
- Limits: export capped at 100 MB compressed or 10 minutes processing; the docs advise narrowing with filters.
- Who: owners only (access to the log).
- Also: REST and GraphQL API on Enterprise Cloud.

### Google Workspace admin log events
Source: https://knowledge.workspace.google.com/admin/reports/admin-log-events
- Requires the "Audit & Investigation" privilege (a distinct admin privilege, not all admins).
- Default filter: last 7 days; filters are attribute / operator / value combined with AND / OR. Attributes: Actor, Event, Date, IP address, Target, User email, and others.
- "Manage columns" lets each admin add, remove and reorder columns and save the layout.
- Export: to Google Sheets or CSV, up to 100,000 rows (30 million in the security investigation tool). Multi-value fields are flattened into one text cell.
- Gotcha: renamed users do not appear under their old names, so identity-at-time matters.

### Atlassian organization audit log (API)
Source: https://developer.atlassian.com/cloud/admin/organization/rest/api-group-events/
- Event shape: `actor` (id, name, email, auth type, on-behalf-of, app), `context[]` (related objects), `container[]` (the resource it happened in), `location` (ip, geo), `message`, `action`.
- Filters: `q`, from, to, action, actor, ip, product, location; cursor pagination.
- Rate limit on the query endpoint is low (10 requests a minute); a polling stream endpoint is recommended for bulk retrieval.
- The page documents no UI export and no before/after change data.

### Okta System Log
Sources: https://developer.okta.com/docs/reference/api/system-log/ and https://developer.okta.com/docs/reference/system-log-query/
- Events have actor and target objects, filterable by `actor.id` and `target.id`; also `eventType`, keyword `q`, `since` / `until`.
- Default 100 per page; 30-second query timeout; the page gives both 90-day and 180-day age limits (inconsistent in the docs).
- Exports should follow `next` links, because manual since/until paging can skip or duplicate events. Lesson: paginate on a stable cursor or ordering.
- Admin console CSV export not verified.

### WorkOS Audit Logs
Source: https://workos.com/docs/audit-logs/exporting-events
- CSV only. Scoped to one organization and a date range, with optional action, actor and target filters.
- Asynchronous: create an export, receive an ID, poll until state `pending` becomes `ready`, then fetch a URL.
- Download URL expires after 10 minutes and can be refreshed by re-fetching.
- Available from a dashboard Actions menu ("Export CSV") or the API.
- Events model `actors` and `targets` explicitly. Schema details were not fetched.

### Moodle Logs report
Source: https://docs.moodle.org/en/Logs
- Course-level and site-level logs. Each row shows time, the user (linked to profile), the page or activity (linked), the IP (linked to a location lookup), and the action (view / add / update / delete).
- Filters: group, student, date, activity, action, level (Teaching / Participating / Other). Results appear after clicking "Get these logs".
- View on the page or download as text, ODS or Excel. The file name includes the course short name.
- Live logs: a streaming view that can be paused.
- Closest analogue to an LMS educator log. There is no avatar and no expandable row: a flat table.

### django-simple-history admin
Source: https://django-simple-history.readthedocs.io/en/latest/admin.html
- Per-object history page: object snapshot link, date and time, comment, author. Optional extra columns via `history_list_display`.
- A delta block renders what changed between consecutive records. Default page size 100.

### django-auditlog admin
Source: https://django-auditlog.readthedocs.io/en/latest/usage.html
- Per-object history page lists user, timestamp, action and field changes; page size default 10.
- `changes_display_dict` gives readable before/after: verbose field names, choice labels, localized dates, strings truncated to 140 characters by default.
- The actor is set by middleware (the request user), or `set_actor` outside requests.
- No export documented. Only a flush command.

## Not verified (fetch failed or not covered)
- Slack Audit Logs: the docs pages returned 404 or 403. Nothing is claimed.
- Canvas LMS, django-reversion, Linear and Notion: not researched in this pass. Do not rely on them.
- Avatars and accordion rows: none of the sources fetched documented avatar or expandable-row presentation. The admin consoles above use flat tables with the actor shown as a name, email or ID. The avatar and accordion work therefore rests on the supplied design (`design.md`), not on these references.

## Cross-cutting patterns useful for the spec
1. Actor and target are first-class and separate (GitHub, Atlassian, Okta, WorkOS). This supports showing an avatar on each mention.
2. Identity at event time: Google notes renamed users vanish from old-name searches. Deleted or renamed users need a stored display name or a fallback in the avatar and name rendering.
3. Export honours the active filters (GitHub, WorkOS, Google). Users export what they see.
4. Formats: CSV is universal; JSON is common for developers (GitHub); Excel / ODS appears in Moodle.
5. Size handling: synchronous with a row cap (Google 100,000 rows) or a size and time cap (GitHub), versus asynchronous with an expiring link (WorkOS: 10 minutes). Both are documented to cope with large logs.
6. Access: export is limited to a privileged role (GitHub owners, Google "Audit & Investigation" privilege). Export is never open to every user.
7. Before/after diffs live in a per-event detail view (simple-history and auditlog), with readable labels and truncation (140 characters), which maps onto the expandable-row detail.
8. A default time window (Google 7 days, GitHub 3 months) keeps lists fast.
9. Stable ordering or cursor for paging and export (Okta).
10. Per-user column customization (Google) is optional and probably out of scope given "don't build functionality that is not explicitly requested".

status: ok · reason: web research complete; Slack, Canvas, reversion, Linear and Notion unverified
