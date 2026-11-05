# Research: how reference APIs expose enrolments, group enrolments and interest records

Extends `spec_dd/1. next/apis-for-lead-monitoring/research_comparable_apis.md` (auth, scoping, general pagination are not repeated). Evidence tags: **[fetched]** = read from the cited page in this run; **[knowledge]** = from memory of the vendor docs, not re-fetched, verify before quoting in the spec. Vendor terms are kept as the vendor uses them ("enrollment", "section", "group"); FLS terms are "course registration", "cohort course registration", "course interest".

## 1. Per-system findings

### Canvas LMS Enrollments API [fetched]
Source: https://canvas.instructure.com/doc/api/enrollments.html
- **One resource, discriminated by `type`.** A single Enrollment object, `type` one of StudentEnrollment, TeacherEnrollment, TaEnrollment, DesignerEnrollment, ObserverEnrollment. `role`/`role_id` refine it. Group-like placement is not a separate resource: `course_section_id` is a field on the same row, and the same rows can be listed three ways: `/courses/:id/enrollments`, `/sections/:id/enrollments`, `/users/:id/enrollments` (the section is a filter/scope, not a different table).
- **State field:** `enrollment_state` (active, invited, inactive, completed...). `state[]` filter defaults to active+invited, so a naive client silently misses inactive rows (a trap to avoid: FLS should default to returning inactive rows or document it loudly).
- **Source:** `created_for_sis_id[]` filter distinguishes SIS-imported enrollments from others (closest analogue of `self_registered`, but it only identifies import origin, not "chose it themselves").
- **Timestamps:** `created_at`, `updated_at` ISO 8601 in the object, but the page documents **no updated-time filter**. FLS `updated_since` is better than Canvas here.
- **Identity:** embedded nested `user` object (id, name, sortable_name, short_name) plus `user_id`. Email is not in the embedded object; it needs a separate users call. FLS flattening user id + email + organisation is more useful for a script.
- **Deactivation/deletion:** `DELETE .../enrollments/:id?task=conclude|delete|inactivate|deactivate`. Inactivate keeps the row (state flips, `updated_at` should move); delete removes it (no feed). Reactivate is a PUT. This matches FLS: `is_active=false` stays visible, hard delete is invisible.
- Pagination: Link headers (see https://canvas.instructure.com/doc/api/file.pagination.html).

### Open edX Enrollment API [fetched from source]
Source: https://raw.githubusercontent.com/openedx/edx-platform/master/openedx/core/djangoapps/enrollments/views.py (docs entry: https://docs.openedx.org/en/latest/developers/references/api_docs.html)
- **Two endpoints for two audiences, same row shape.** `/enrollment` (per-user, `user` param, no pagination) and `/enrollments` (admin list, `course_id`, `course_ids`, `username`, `email` filters, page-number pagination with `page_size`, `next`/`previous`). Both return `created`, `mode`, `is_active`, `user` (username), `course_id`.
- **No group enrolment concept** in this API (cohorts in Open edX are a discussion/content grouping, not an enrolment kind).
- **Deactivation is a flag, not a delete.** Unenrol = POST with `is_active=false`; the list view does not filter on `is_active`, so deactivated rows still appear with `is_active: false`. This is the exact model FLS wants: soft state visible, never silently dropped.
- Only `created` timestamp is exposed and there is no `modified` filter, so incremental sync is impossible without full re-reads. Evidence for why `updated_at` matters.
- Identity: username only (email needs a filter or the accounts API). Mode (audit/verified) is a commercial track, a loose analogue of nothing in FLS; do not borrow.

### Thinkific [partly fetched]
Source: https://developers.thinkific.com/api/api-documentation/
- Enrollment resource fields: user id, course id, activation date, expired status, free-trial flag, completion status, percentage completed, last-updated timestamp. Filters: `query[user_id]`, `query[updated_after]`, created-on date. [fetched, summary level]
- **Group enrollments are via a separate Groups API** (groups, group analysts, user-group membership), not mixed into the enrollments list. [fetched: "handled through the Groups API"; detail knowledge]
- Identity: `user_id` plus (in knowledge) separate users endpoint; no flattened email. Expiry is signalled by `expired` / `expiry_date` rather than deletion. Page-number pagination.
- Takeaway: a named `updated_after` filter on enrollments is the nearest precedent for `updated_since`; completion and registration live on one row, which FLS deliberately splits (progress is spec 5).

### Moodle web services [knowledge]
Sources: https://moodledev.io/docs/apis/subsystems/external ; function names `core_enrol_get_enrolled_users`, `core_enrol_get_users_courses`, `enrol_manual_enrol_users`, `core_cohort_get_cohorts`, `core_cohort_get_cohort_members` (index: https://docs.moodle.org/dev/Web_service_API_functions). The externallib page could not be fetched (404), so field names are unverified.
- **Group enrolment is a different mechanism.** Moodle "cohort sync" is an enrolment *method* instance on a course that enrols all cohort members; the resulting rows appear as ordinary user enrolments with an `enrol` method name (`manual`, `self`, `cohort`). So Moodle expands cohort enrolment to per-user rows; it does not expose "this cohort is enrolled" as its own record via the standard enrol functions. Cohort membership itself is a separate function family.
- Source is carried by the enrolment method (`self` = self-enrolled, `manual` = staff, `cohort` = group-derived). This is the strongest precedent for exposing a source discriminator, but Moodle uses an open-ended method name rather than a boolean.
- Status: user enrolment `status` (0 active, 1 suspended), `timestart`, `timeend`, `timecreated`, `timemodified` on the user_enrolments table (knowledge). Suspension is the soft-deactivate; unenrol deletes the row.
- Pagination/incremental: none standard. Confirms the gap.

### Teachable, LearnWorlds, Kajabi [knowledge, verify]
- Teachable: enrollments sit under a course (`/v1/courses/{id}/enrollments`) and a user (`/v1/users/{id}`), with `enrolled_at`, `completed_at`, `percent_complete`, `has_full_access`; an enrol/unenrol is a POST/DELETE style action. Ref: https://docs.teachable.com/reference
- LearnWorlds: `/v2/users/{id}/courses` and a course-scoped users list; enrolment is a sub-resource of user with `enrolled_at`/`expires_at`; groups via tags and user "groups" endpoints, kept separate. Ref: https://www.learnworlds.dev/
- Kajabi: public API exposes customers/offers/purchases; access to a course is derived from an offer grant (a purchase), so "enrolment" is a purchase record with a `source`-like offer. Ref: https://developers.kajabi.com/ (not re-checked).
- Pattern: enrolment is nested under user or course; group access, where it exists, is a separate groups/tags resource; expiry fields rather than deletion.

### Docebo and TalentLMS [knowledge, verify]
- Docebo: enrollment endpoints under the Learn API (`/learn/v1/enrollments`) with `status` (enrolled, in progress, completed, waiting, suspended), `enrollment_date`, `enrollment_created_by` (who enrolled them, a real "who placed this" field), and separate `/learn/v1/enrollments` for groups/branches: audiences are assigned through groups ("groups & branches") and a course-level enrolment *rule* auto-enrols them, producing per-user rows. Ref: https://help.docebo.com/hc/en-us/articles/360020066113 (API browser: https://www.docebo.com/apidocs).
- TalentLMS: `addusertocourse`, `getusersbycourse`, `addusertogroup`, `addcoursetogroup` (groups are a separate noun; a course added to a group yields per-user enrolments); fields include `role`, `enrolled_on`, `completion_status`, `completed_on`. Ref: https://support.talentlms.com/hc/en-us/articles/115008109408-TalentLMS-API-documentation
- Pattern: group/audience enrolment is a rule that fans out to per-user rows, with a `created_by`/method marker for who did it.

### Stripe list conventions [fetched]
Source: https://docs.stripe.com/api/pagination
- Uniform list envelope: `object: "list"`, `data`, `has_more`, `url`. Cursor is an object id (`starting_after`/`ending_before`), `limit` 1-100 default 10, newest first. Cursor is a single table's id, so a merged list from two tables has no natural cursor. Stripe sidesteps this by one resource per list endpoint. Related: `created[gte]` range filters (https://docs.stripe.com/api/charges/list), Events API for deletions (https://docs.stripe.com/api/events). Stripe also exposes `type` on polymorphic payment-method objects within one list (discriminator pattern: https://docs.stripe.com/api/payment_methods/object).

### HubSpot [knowledge, verify]
- List via cursor `after` with `paging.next.after` (https://developers.hubspot.com/docs/api/crm/contacts); incremental via Search API filtering `hs_lastmodifieddate` GTE, sorted ascending, which is the pattern behind `updated_since` + `(updated_at, id)` ordering. Archived records are fetched with `archived=true`, i.e. deletion is explicit and opt-in (https://developers.hubspot.com/docs/api/crm/contacts). Associations (contact to company) are a separate v4 association API listing typed links, not embedded rows.

### Salesforce and Shopify: discriminators [knowledge, verify]
- Salesforce: one object holding several kinds, discriminated by `RecordTypeId` (and a `Type` picklist), with a `LastModifiedDate`/`SystemModstamp` for incremental sync and `IsDeleted` plus `getDeleted` for deletions (https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_getdeleted.htm). `SystemModstamp` + id is the standard sync cursor.
- Shopify: polymorphic payloads use a `__typename` (GraphQL) or a `type`/`kind` string; REST webhooks signal deletes as separate topics (`*/delete`). (https://shopify.dev/docs/api/admin-graphql). Shopify's Discount codes and `Order` source fields (`source_name`) are the "where did this come from" analogue.

## 2. Cross-cutting answers

**One endpoint vs two for individual and group enrolments.**
- One list with a discriminator: Canvas (`type`), Salesforce (record type), Stripe payment methods (`type`). All of these are single-table or single-id-space resources, so the cursor stays simple.
- Separate nouns: Thinkific (Groups API), TalentLMS (groups), LearnWorlds (groups/tags), Moodle (cohort functions), Docebo (audience rules). In every one of these, group enrolment either fans out into per-user rows or is its own resource. None merges two *tables* with different shapes into one cursor.
- Nobody exposes both "cohort X is registered on course Y" and "learner Z is registered" in one list. FLS's cohort registration is closer to the Docebo audience rule or the Moodle cohort-sync instance than to a Canvas enrolment row.

**Source (self vs staff).** Moodle `enrol` method (`self`/`manual`/`cohort`), Docebo `enrollment_created_by`, Canvas `created_for_sis_id`. A boolean (`self_registered`) is simpler than any of them and adequate.

**Status.** Always an explicit field on the row, never row removal: Canvas `enrollment_state`, Open edX `is_active`, Moodle `status`, Docebo `status`. Open edX returns inactive rows by default; Canvas hides them by default (a documented trap).

**Identity.** Canvas embeds a nested user object; Open edX gives username (plus filter by email); Thinkific gives `user_id`. Nobody flattens email onto the enrolment; FLS's flattening of id, email, organisation is a deliberate usability gain for scripts, at a privacy cost handled by the scope.

**Deactivation / deletion.** Soft states are visible and, where there is a modified timestamp, show up in incremental sync (HubSpot, Salesforce). Hard deletes need a separate feed or event: Salesforce `getDeleted`, Stripe Events, Shopify delete webhooks, HubSpot `archived=true`. Canvas, Open edX, Moodle have none. FLS's "no deletion feed" decision matches the LMS peers and is a known limitation to document, not a defect.

**Filtering by updated time.** Absent on Canvas enrolments and Open edX; present as `query[updated_after]` on Thinkific; `hs_lastmodifieddate` (HubSpot); `SystemModstamp` (Salesforce). The reliable form pairs the timestamp with an id tiebreak.

**Interest / wishlist records.** None of the LMS APIs surveyed expose a wishlist/interest record as a first-class read resource. The nearest analogues are CRM-style lead/contact-interest data (HubSpot contact properties and list membership; Salesforce `CampaignMember`/`Lead`) and e-commerce wishlists (Shopify has none in the Admin API, wishlists are app-owned). Hence course interest should follow the registration shape, with no external naming precedent beyond a plain noun. Teachable/Thinkific show only waitlist-style behaviour through marketing tags. [knowledge]

## 3. What this spec should borrow

1. **Two separate endpoints, not one merged list** (e.g. `course-registrations` for individual and `cohort-course-registrations`), because no reference merges two tables of different shape under one cursor, and Stripe/HubSpot cursors are single-resource. This answers the open question and keeps `(updated_at, id)` ordering trivially correct. If a combined view is still wanted, Salesforce-style `kind` can be added later; the progress child then points at one endpoint per kind. Note this is a recommendation, not a verified consensus beyond the above pattern.
2. **Soft state as a field, rows never filtered by default.** Follow Open edX: return `is_active` false rows by default (avoid the Canvas default that hides inactive rows), optionally offer an `is_active` filter.
3. **A boolean source field** (`self_registered`), with Moodle's `self`/`manual` and Docebo `created_by` as the justification; no open-ended method string.
4. **`updated_since` as a named filter with `(updated_at, id)` ordering**, ascending, inclusive: Thinkific `updated_after`, HubSpot `hs_lastmodifieddate` + Salesforce `SystemModstamp`. The Canvas and Open edX gaps are the argument for adding `updated_at`.
5. **Flattened identity** (user id, email, organisation) as plain scalar fields; keep Canvas's nested `user` object out, per the idea. Cohort registration carries the cohort id and name in place of the user fields, like Docebo/Moodle cohort sync, where the group is a distinct noun.
6. **Uniform list envelope and cursor** from the foundation (Stripe-style `has_more`/`next`); do not copy Open edX page-number paging.
7. **Document, do not fix, deletion blindness**: say in the endpoint docs that hard-deleted course interest and registrations vanish with no event, as Canvas, Open edX and Moodle do, and that `is_active=false` is the visible way to end a registration. Salesforce `getDeleted` and Stripe Events are the later-feed precedents if it is ever added.
8. **Course interest follows the registration shape** (user id/email, course id/title, `created_at`/`updated_at`): there is no wishlist precedent in comparable LMS APIs to deviate toward.

status: ok · reason: Canvas, Open edX, Thinkific (summary) and Stripe fetched; Moodle, Teachable, LearnWorlds, Kajabi, Docebo, TalentLMS, HubSpot, Salesforce, Shopify from knowledge and marked verify
