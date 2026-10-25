# Reference implementations: how deadlines are built in code and data

Scope: HOW Open edX, Moodle and Canvas store and resolve due dates. Product-level comparison is in `spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md` and is not repeated.

Verification: the edx-when section was read from source this session (models.py, api.py). The Moodle and Canvas sections are from prior knowledge of their schemas and code and were not re-read from source this session; items marked (unverified) should be checked before the spec relies on them.

## 1. Open edX: edx-when

### Data model (verified)
- `DatePolicy`: `abs_date` (nullable datetime) and `rel_date` (nullable timedelta). `clean()` rejects both set. One row is one "when", shared by many content items.
- `ContentDate`: `course_id`, `location` (usage key of the block), `field` (e.g. `due`, `start`), `policy` FK, `active`, plus display labels. Unique on `(policy, location, field)`. This is the "content default" layer: one row per (block, field).
- `UserDate`: `user` FK, `content_date` FK, nullable `abs_date` or `rel_date` (not both), `reason` (free text), `actor` (nullable FK to the user who made it), `is_content_gated`. This is the per-learner override layer. No cohort layer exists in edx-when; cohort-like behaviour comes from course-level start and schedule.
- Resolution depends on a per-learner `Schedule` (from the edx-platform "personalized learner schedules" feature), not on a field in edx-when.

### Resolution (verified)
- `DatePolicy.actual_date(schedule, end_datetime, cutoff_datetime)`: absolute returns as is. Relative needs a schedule, otherwise `MissingScheduleError`. Result is schedule start plus `rel_date`, capped at the course end (`end_datetime`). Returns `None` if the schedule was created after `cutoff_datetime` (course end minus the largest relative offset), so late starters get no relative date that would fall past the course end.
- The schedule start is the enrollment date (or course start if later) in self-paced courses; this is the anchor, analogous to FLS `CourseProgress.created_at`. Relative rows are only used if a per-course feature flag is on.
- Overrides applied after policy resolution and replace the value. Among several `UserDate` rows for one content date, the most recently modified wins. Overrides may be absolute or relative to the same schedule start.
- Model-level `UserDate.clean()` says "Override date must be later than policy date", but api.py applies stored overrides without comparing, so "extension only" is enforced at the write/admin path, not at read.
- No default time of day in edx-when. Absolute dates are whatever datetime was supplied. Relative dates inherit the time of day of the schedule start. Time-of-day is therefore decided by the authoring layer (Studio asks for date and time in UTC, labelled).

### Authoring
- OLX `due` is an absolute datetime attribute on a subsection. For self-paced courses, `relative_weeks_due` (whole weeks) on the subsection is used, and the course's `self_paced` flag selects between them. Relative dates exist only in whole weeks, a deliberately coarse unit.
- Course publish syncs these into `ContentDate` + `DatePolicy` rows (`set_dates_for_course`). Content defaults are rewritten on every publish, so edits to the default flow to every learner except those with a `UserDate`.

### Takeaways
- Separate the "when" value (absolute or delta, never both) from the thing it attaches to.
- Store the override as the same shape as the default (absolute or relative), plus `actor` and `reason` on the override row itself.
- An override that is absolute stops following default edits; a relative override follows the schedule start but not the default's offset. Nothing in edx-when flags a stale override.
- A cap/cutoff for relative dates relative to a course end is a real edge case; FLS has no course end, so it does not apply.

## 2. Moodle (unverified against current source)

### Data model
- Activity table holds the default: assign `duedate`, `allowsubmissionsfromdate`, `cutoffdate`; quiz `timeopen` / `timeclose` / `timelimit`. Stored as integer Unix timestamps (UTC).
- Override tables: `assign_overrides` and `quiz_overrides`: `id`, activity id, nullable `groupid`, nullable `userid`, `sortorder` (group only), and nullable copies of the date fields. A null field means "do not override this field", so each field resolves independently. Each row is either a user override or a group override.
- Extensions (`assign_user_flags.extensionduedate`) are a separate mechanism from overrides, set per user per assignment.
- Absolute timestamps only. Overrides store dates, not deltas.

### Precedence and ties
- User override beats group overrides, which beat the activity default (same direction as the FLS layers).
- Several group overrides for a user in multiple groups: in quiz, per-field "most permissive" merge (earliest open, latest close, largest time limit; any "unlimited" wins). In assign, group overrides use `sortorder` (educator-ordered priority, first match wins per field) (unverified, check `assign::override_exists`). So Moodle has both patterns; the quiz one matches the FLS "most permissive wins" rule.
- Consequence for FLS: "most permissive" is well established, but it needs a definition for fixed vs relative dates: compare resolved instants, not raw values.

### Course end and relative dates
- Course `startdate` and `enddate` exist but do not by themselves drive activity due dates.
- "Relative dates mode" (course setting, Moodle 3.11+): when on, every date on the course page shifts by (user's enrolment start minus course start), so authors write dates against the course start and each learner sees them shifted. Implemented as a display-time transform of stored absolute dates, not as stored deltas. It is a course-wide switch, and overrides interplay poorly (overrides are shifted too, a known confusion).
- Default time: the date picker defaults to a time set when the activity is created (due date defaults to a week out at the creating time of day); the time zone is the user's. No end-of-day rule.
- Actor/reason: the override rows record no actor or reason; the event log (`\mod_assign\event\user_override_created`, with `userid` of the actor) is the audit trail.

## 3. Canvas (unverified against current source)

### Data model
- `assignments.due_at`, `unlock_at`, `lock_at` are the defaults (UTC timestamps).
- `assignment_overrides`: `assignment_id`, `set_type` (`CourseSection`, `Group`, `ADHOC`), `set_id`, `due_at`, `unlock_at`, `lock_at`, plus booleans `due_at_overridden`, `lock_at_overridden`, `unlock_at_overridden` so "override to empty" differs from "not overridden". `workflow_state`, `title`.
- `assignment_override_students`: join of override to users for `ADHOC` overrides (one override row can cover many students).
- "Everyone else" is the assignment's own dates, applying to students not covered by any override.
- Absolute dates only; overrides never store a delta.

### Precedence and ties (unverified, see `AssignmentOverrideApplicator`)
- The applicator collects every override whose set contains the student, then collapses to one effective set of dates: for due_at, the latest due date wins (most permissive), and an override that clears the date (overridden to nil) wins over any date. If the student has an ADHOC (individual) override, applicable-by-student behaviour is that individual overrides take priority over section/group ones in some paths (the code orders by set type). Treat the exact order as to be verified before quoting.
- One student in two sections gets the most permissive result: this is the same tie rule FLS settled on.

### Time of day
- The UI defaults a date-only entry to 11:59 PM in the course/user time zone; the API stores whatever `due_at` timestamp is sent. The end-of-day default is a UI convention, not a schema rule. Canvas displays dates in the viewing user's profile zone and lets the course have a zone. This confirms the FLS choice (site zone, end of day) as an authoring-layer decision.

### Actor/reason
- No actor or reason on override rows. Created/updated by auditing (course/assignment event logs) only.

## 4. Chamilo / ILIAS
Not examined in depth. Both attach a start/end window to a learning object and a course-level access period; neither has a cohort layer. Not informative beyond Moodle/Canvas/Open edX.

## 5. Comparison

| Aspect | Open edX | Moodle | Canvas |
|---|---|---|---|
| Default lives on | `ContentDate` -> `DatePolicy` | activity row | assignment row |
| Fixed vs relative stored | both, separate nullable columns, never both | absolute only (relative mode is display shift) | absolute only |
| Override layers | learner only | learner, group | learner (ADHOC), section, group |
| Override value shape | abs or rel, mirrors default | absolute, null = inherit that field | absolute, flag per field for "cleared" |
| Multi-override tie | latest modified `UserDate` | quiz: most permissive; assign: `sortorder` (unverified) | most permissive (unverified) |
| Default time of day | none in model, set at authoring | creation time of day | UI 11:59 PM |
| Actor/reason on override | `actor` FK + `reason` on row | no (event log) | no (audit log) |
| Follows later default edits | abs: no; rel: follows anchor only | no for absolute fields; null fields do | no for set fields; unset fields do |

## 6. Implications for the FLS spec
1. Model a deadline value as nullable absolute date plus nullable offset with a check constraint that exactly one is set (or neither for "none"), as edx-when's `DatePolicy` does. Reuse for item defaults, cohort overrides and learner overrides.
2. Per-field nullable overrides (Moodle, Canvas flags) is how "inherit the default" is expressed; an explicit "no deadline" override needs a distinct representation (Canvas's `*_overridden` flag) or it cannot be told from "inherit".
3. Edx-when is the only one with `actor` and `reason` on the override row, and it is the shape asked for in "How an override records its actor and reason". It does not flag a stale override; FLS would need to add that by recording, for example, the default value that was in force when the override was set, or by storing offsets so overrides never go stale against the anchor.
4. Resolve to an instant, then compare; "most permissive" among co-layer values means the latest instant, where "none" beats any date (Moodle quiz, Canvas).
5. Relative dates resolve at read time as anchor + offset, with no stored computed date, as in edx-when and Moodle's display shift; this avoids data migration when the anchor moves.
6. Do not copy: Open edX's whole-weeks-only unit, the course-end cutoff (no FLS course end), UTC-only author input, and Moodle's relative-dates-mode as a display-wide transform.

## References
- https://github.com/openedx/edx-when (models: `edx_when/models.py`; resolution: `edx_when/api.py`) - read this session
- https://raw.githubusercontent.com/openedx/edx-when/master/edx_when/models.py
- https://raw.githubusercontent.com/openedx/edx-when/master/edx_when/api.py
- https://docs.openedx.org/en/latest/educators/references/course_development/ (OLX `due`, `relative_weeks_due`, self-paced)
- https://docs.moodle.org/en/Assignment_settings and https://docs.moodle.org/en/Course_settings (relative dates) - not re-read
- https://github.com/moodle/moodle/blob/main/mod/assign/locallib.php (`override_exists`) - not re-read
- https://github.com/moodle/moodle/blob/main/mod/quiz/lib.php (`quiz_update_effective_access`) - not re-read
- https://github.com/instructure/canvas-lms/blob/master/app/models/assignment_override.rb and `lib/assignment_override_applicator.rb` - not re-read
- https://community.canvaslms.com/ (assignment overrides, "Everyone else", 11:59 PM default) - not re-read

status: ok
