# Prior art: exposing course registrations and course interest

(No Bash available, so `git log` was not run. Findings come from spec_dd files.)

## In the project

### No earlier export or API covers registrations or interest
- `more_lead_admin_exports` (3. done) added only Users and CourseApplication exports. It explicitly left out registration-form answers, `LegalConsent`, HR attributes and signup attribution (`1. spec.md:33`). No registration or interest export has ever shipped.
- `1. next/apis-for-lead-monitoring/research_data_sources.md`: "no admin export today for course registrations, course progress, course interest, or form attempts"; all are new data.

### Data hazards already recorded (research_data_sources.md rows 29-31, 142)
- `CourseInterest`: `created_at` only; toggle-off hard-deletes the row (source: `referral-attribution-over-time/1. spec.md:297-301`), so deletion is invisible to incremental pulls.
- `LearnerCourseRegistration` / `CohortCourseRegistration`: `registered_at` only. Deactivate and reactivate leave no timestamp. Rows are not deleted (`is_active`); `course` FK is PROTECT.
- `LearnerCourseRegistration.learner` goes to `Learner` (user + organisation), so identity needs flattening.
- Optional `registration_rules.RuleRegistration` marks rule-made registrations (1:1, no timestamp). Not in the idea; rule-made registrations are not `self_registered` (roadmap rule 10).

### Decisions this spec must stay consistent with (roadmap "Lead monitoring API", lines 683-735; foundation spec)
- Read only; DRF + django-filter + drf-spectacular; JSON only; explicit field lists; snake_case; UUIDs as strings; ISO 8601.
- One key = one site; scope `registrations_and_progress`; API-key auth only; throttled per key; site-aware querysets (`site_queryset(...)`).
- Cursor pagination on `("updated_at", "id")`; opaque `cursor`; ties on equal `updated_at` page with no dupes or skips (foundation tested 1,500 rows with one identical `updated_at`). `updated_since` is inclusive; naive or unparseable value is 400. `UpdatedSinceFilterSet` in `freedom_ls/api/filters.py` is reusable.
- Each resource's viewset must be registered with an `ApiScope` as `required_scope` or the `freedom_ls_api.E001` system check fails.
- Foundation added an index on `(site, updated_at, id)` for `User` (accounts `0004`). Do the same for each new `updated_at`.
- Deletions are invisible to `updated_since`; no deletion feed. The docs example checkpoints at max `updated_at` minus 5 minutes and upserts by `id`.
- Adding `updated_at`: foundation touched `User.updated_at` by signal using `User._base_manager.filter(...).update(...)`. Queryset `update()` and bulk ops send no signals and are not covered. This applies here too: bulk deactivation or `bulk_create`/`queryset.update(is_active=...)` of registrations would not bump an `auto_now` field. Check the educator and admin code paths that flip `is_active`.
- Spec 5 (course progress) reads the answer to the kind/endpoint question and reuses whichever flattening lands first. Roadmap line 679 also says whichever of 4 and 5 lands second reuses the flattening.
- Roadmap table also notes: 2-5 each register routes and add a docs section, so expect merge conflicts in the router and `docs/api.md`.
- Other adjacent specs touching registrations: `corporate-job-course-recommendations` (rules create/deactivate registrations, adds a provenance field to `LearnerCourseRegistration`), educator-interface 6 and 7 (deactivate/reactivate registrations, cohort `is_active`, never hard-delete), `deadlines` (ending access does not set `is_active=False`). They may add more writers of `is_active`, so `updated_at` must move on any ORM `.save()`. Ending access leaves `is_active` true, so `is_active` alone does not mean the learner has access.
- Roadmap line 580: "one registration governs" (`learner_for_course`); a learner in two registrations for one course appears in both rows; the API should not collapse them.

### Recurring QA findings from foundation (qa_report.md, upgrade_notes.md)
- B3: allauth `EmailAddress` admin was not site-aware and leaked other sites' rows. Lesson: test every new queryset against a second site, and use real `Site` rows, `ALLOWED_HOSTS` and `HTTP_HOST`, not `mock_site_context`.
- B1/B2: Unfold admin CSS (`break-all`, `truncate`) clipped the key and scope labels on mobile. Only relevant if this spec touches the admin UI; it should not.
- Full-tier tests ran 11530+ passed; pre-commit clean; rebase conflicts occurred in `test_organisation/mirroring_exemptions.txt`. Expect the same when new test files land.
- Upgrade notes: a new `updated_at` is a migration for every adopter (`requires_migrations: true`); the foundation migration for accounts ran even when the API was not installed. The same will apply to `learner_management` and `course_interest`. Existing rows need a sensible `updated_at` backfill (`auto_now_add`-style default of migration time, or `registered_at` / `created_at`). Not decided anywhere; a spec question.
- Plan-vs-spec wording differences were all judged pass; the QA found spec wording more reliable than plan wording.

## Elsewhere

- Deletes are invisible to a delta or last-modified query. If the source has no is_deleted flag, deletion timestamp or "recently deleted" endpoint, incremental sync cannot detect deletions. Common fixes: periodic full snapshot and diff, and fail the run rather than mark records deleted when a fetch fails partway. Nango: https://nango.dev/docs/implementation-guides/syncs/deletion-detection and https://docs.nango.dev/guides/syncs/detecting-deletes
- Some connectors update `updated_at` only when the record itself changes, or have none at all; always test incremental sync per source (Chift): https://docs.chift.eu/developer-guides/unified-api/incremental-synchronization
- Modifying records without updating the cursor field means incremental sync misses them (Squared docs): https://docs.squared.ai/guides/data-modelling/sync-modes/cursor-incremental.md
- Canvas Data 2: records are often soft deleted (workflow state "deleted", delivered as an upsert) rather than hard deleted, so consumers watching only for delete rows miss removals; submissions linger with a normal state after the enrolment is gone. https://community.canvaslms.com/t5/Canvas-Question-Forum/Canvas-Data-2-Submissions-without-Enrollment-still-having-a/m-p/607886 and https://community.canvaslms.com:443/t5/Data-and-Analytics-Group/CD2-Quiz-submissions-missing-losing-data/m-p/570794
- No Moodle-specific post-mortem was found.
- Implication: FLS registrations already use soft state (`is_active`), which matches the Canvas pattern and is visible once `updated_at` exists. `CourseInterest` toggle-off is the one genuine hard-delete gap; the idea accepts it and the docs should tell scripts to do a periodic full pull to reconcile.

## Open points for the spec
- One endpoint with `kind` vs two endpoints: not tried anywhere in the project. Ordering two tables by one `(updated_at, id)` cursor needs a union or a merged-key cursor (UUIDs are unique across tables, but a union queryset is awkward with DRF and django-filter). Two endpoints avoids that and keeps shapes distinct.
- `updated_at` backfill for existing rows.
- Paths that flip `is_active` without `.save()`.

status: ok · reason: project history and web sources summarised; git log not run (no Bash)
