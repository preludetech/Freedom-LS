# Research: known complaints about progress/completion APIs and incremental sync

Scope: web search (standard mode, limited depth; vendor docs, Canvas community, blogs). Evidence on
Moodle, Open edX, LearnDash, TalentLMS and Thinkific specifically was not surfaced; findings are
general or from Canvas, Ciphr and Unified.to. Treat as directional.

## Complaints found

1. **Percent differs between report/API and UI.** Ciphr documents that the progress percentage in
   one report differs from the learning plan view because a different calculation method is used,
   with no workaround. Percent-complete definitions vary by what activities are counted (hidden,
   graded, etc.).
   - https://customercare.ciphr.com/hc/en-gb/articles/43241477313809-Known-Issues-Ciphr-LMS
   - https://www.plushcap.com/content/unified-to/blog/unified-to-how-to-track-learner-progress-completion-status-and-course-activity-with-unifieds-lms-api
2. **Status changes not syncing downstream / stale data.** Ciphr: LMS updates but HR record stays on the
   old status. Course syncs on schedules give ~15 minute lag in other vendors' docs.
   - https://customercare.ciphr.com/hc/en-gb/articles/43241477313809-Known-Issues-Ciphr-LMS
   - https://twostoryrobot.notion.site/LMS-Synchronization-Details-835dbdb410494957806560972ba40046
3. **No incremental filter on activity/progress records.** Unified.to notes LMS integrations do not
   universally support incremental filtering for activity records, forcing full re-pulls; no webhooks
   for roster changes so polling is required.
   - https://unified.to/blog/how_to_track_learner_progress_completion_status_and_course_activity_with_unified_lms_api
   - https://unified.to/blog/how_to_sync_enrollment_rosters_across_lms_platforms_with_unified_lms_api.md
4. **Deletions / unenrolments invisible.** Canvas community: records absent from later imports are
   marked deleted, enrolment deletion does not always cascade (submissions remain after enrolment
   deleted), batch mode deleting wanted enrolments. Common workaround is full snapshot diffing.
   - https://community.canvaslms.com/t5/Question-Forum/Un-enrolling-students-faculty-via-SIS-import-diffing/td-p/404202
   - https://community.canvaslms.com/t5/Developers-Group/SIS-import-batch-mode-deletes-courses-enrollments-we-include-in/m-p/415559
   - https://community.canvaslms.com/t5/Canvas-Question-Forum/Canvas-Data-2-Submissions-without-Enrollment-still-having-a/m-p/607886
5. **Paging instability.** Sorting on a non-unique or mutable timestamp skips or repeats rows; cursor
   must store the (timestamp, id) pair; rows bumped mid-sync reappear or get skipped; deleted rows
   vanish before being fetched. Advice: unique tie-breaker, overlap/watermark window, randomized
   tie-order tests.
   - https://oneuptime.com/blog/post/2026-08-24-test-cursor-pagination-record-integrity/markdown
   - https://getknit.dev/blog/how-to-preserve-api-pagination-stability.md
   - https://www.vincentschmalbach.com/defining-stable-ordering-rules-for-cursor-pagination/
6. **Partial or missing completion data from content (SCORM/xAPI).** Progress not recorded when the
   window loses connection; "in progress" status never emitted. Relevant only as a reason percent can
   be low or stale at source.
   - https://community.articulate.com/discussions/rise-360/rise-not-completing-progress-not-recorded-for-5-of-learners
7. Not evidenced by search (general knowledge, unverified): rate limits and N+1 calls, needing
   separate user joins, timezone ambiguity, inconsistent "completed" definitions.

## Against this idea

Addressed:
- `updated_at` bumped by background recalculation, with bulk-update bypass forbidden, backfilled
  (complaints 3, 2).
- Cursor on `(updated_at, id)`, inclusive `updated_since` (complaint 5 tie-handling).
- Flattened user and organisation, no joins (7: user joins).
- Query count pinned with select_related; per-key throttle and capped page size (7: N+1, rate limits).
- ISO 8601 timestamps (7: timezone, partly; should state UTC/offset explicitly).
- Integer percent, course level only, narrows definition drift.

Left open (candidates for the spec):
- **Deletions/unenrolments** (complaint 4): explicitly out of scope. Spec should at least document
  that consumers must periodically full-snapshot and diff, and state what happens to a
  `CourseProgress` row on unenrolment.
- **Percent definition vs. UI** (1): spec should state how `progress_percentage` is computed and
  confirm the UI shows the same value; document in the API docs.
- **Mutable sort key mid-pull** (5): `updated_at` changing during a pull can cause a row to be
  re-served or missed; document that clients should re-read from a slightly earlier watermark (inclusive
  `updated_since` helps) and be idempotent.
- **Completion semantics**: say whether `completed_time` set is the sole "finished" signal, and
  whether it can be unset.
- **Staleness**: say whether percent is recalculated synchronously or on a lag, so scripts know the
  freshness bound.
- **Timezone**: state timestamps are UTC with offset.

status: ok
