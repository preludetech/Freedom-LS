# Event schemas

Schemas for every event type we emit, keyed by `(verb, object_type)`.

Guiding principle: **capture too much rather than too little**. Fields like `cohort_id`, `course_id`, and `attempt_number` are cheap to record now and expensive to backfill later. If there's any chance we'll want it for course-quality analytics, struggle-point detection, or privacy/retention purposes, record it.

## Immutability and the audit trail

The xAPI log is an **immutable audit record**. Once a statement is written, it is never updated or deleted by application code. Source records (users, courses, forms, cohorts) can be renamed, unpublished, or hard-deleted over time — the log of what a learner actually did must survive all of that.

This drives two rules that apply to **every** schema below:

1. **All foreign keys and UUID references are nullable pointers, not required links.** A `course_id`, `form_id`, `user_id`, etc. may point at a record that no longer exists. FKs on the storage model must be declared `null=True, on_delete=SET_NULL` (or equivalent — never `CASCADE`). The pointer is a convenience for joining to live data when it's still there; it is not the source of truth for the audit record. **Exception: `site_id`** is `null=False, on_delete=PROTECT` (inherited from `SiteAwareModel`). Sites are not expected to be deleted while their events still exist; teardown must archive first.
2. **Denormalized snapshots are the source of truth.** Every event must carry enough self-contained information — titles, slugs, email addresses, display names, scores, thresholds, question text, option labels — that an auditor reading the event row alone (with no access to the current database state) can reconstruct what happened, to whom, about what, in which cohort/course, under which rules. When `required` appears next to a snapshot field, it means required *at write time*; the ID next to it may become dangling, but the snapshot must always be populated.

In the schemas below, fields flagged as required are required **at event-emission time**. The ID fields are nullable in storage to accommodate later deletion of the referenced record, but the tracker must attempt to populate them on write, alongside the snapshot.

## How to read this document

Each schema describes the shape of a single `track()` call. The `track()` helper composes the final xAPI-shaped statement from these inputs plus inferred values (site, timestamp, actor IFI and actor snapshot).

Fields are organized into the standard xAPI sections:

- **actor** — who did it (`request.user` at event time; stored as nullable FK plus a required snapshot of identifying fields)
- **verb** — what they did (constant from `verbs.py`)
- **object** — what they did it to (Django model instance; tracker extracts type, nullable id, and a snapshot of identifying fields)
- **result** — the outcome (scores, success, duration, response)
- **context** — the circumstances (site, cohort, course, session, attempt — all FKs paired with snapshots; all nullable except `site`)

Every event also carries these **global context fields** inferred by the tracker:

| Field | Source | Notes |
| --- | --- | --- |
| `site_id` | `request.site` / current site | Multi-tenant isolation; non-nullable, `on_delete=PROTECT` |
| `site_domain` | snapshot at write time | Audit-trustworthy record of which domain the event was emitted on, even if the site's domain is later changed |
| `session_id` | Django session key (SHA-256, salted with `SECRET_KEY`) | Groups events from one browser session |
| `user_agent` | request headers | For frontend events later |
| `ip_address` | request headers (optional, subject to privacy policy) | Null if policy forbids capture |
| `timestamp` | server time on write | UTC, microsecond precision; never overwritten |
| `platform` | `"backend"` or `"frontend"` | Distinguishes event source |

The **actor snapshot** is attached to every event (not repeated in each schema below):

| Field | Required | Notes |
| --- | --- | --- |
| `actor_user_id` | optional (nullable FK) | May become dangling if user is deleted |
| `actor_email` | required | Snapshot at event time — primary IFI for audit |
| `actor_display_name` | required | Snapshot at event time |
| `actor_role` | required | e.g. `"student"`, `"educator"`, `"admin"`, `"system"` |

Field notation: `name  type, required|optional|derived  — description`.

Convention: wherever a field ending in `_id` appears, it is a **nullable pointer**. The accompanying `_slug`/`_title`/`_name` fields are the **authoritative snapshot** for audit purposes.

---

## Topic events

### `(VIEWED, Topic)`

Emitted when a student loads a topic page.

```
object:
  topic_id          UUID,   optional (nullable FK) — pointer; may become dangling
  topic_slug        str,    required       — snapshot; stable identifier for analytics
  topic_title       str,    required       — snapshot for readability
  topic_type        str,    required       — snapshot; e.g. "reading", "video", "interactive"
context.extensions:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
  cohort_id         UUID,   optional (nullable FK) — null if viewing outside cohort context
  cohort_name       str,    optional       — snapshot; required when cohort_id is set
  registration_id   UUID,   optional (nullable FK) — CourseRegistration.id, if registered
  referrer          str,    optional       — previous URL (from HTTP referrer)
  position_in_course int,   optional       — ordinal position of topic in course
```

### `(COMPLETED, Topic)`

Emitted when a student marks a topic complete (or the system does on their behalf).

```
object:
  topic_id          UUID,   optional (nullable FK)
  topic_slug        str,    required       — snapshot
  topic_title       str,    required       — snapshot
  topic_type        str,    required       — snapshot
result:
  completion        bool,   required       — always true
  duration          ISO 8601 duration, required — time from first VIEWED to COMPLETED in this session
  success           bool,   optional       — null for topics without pass/fail
context.extensions:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    optional       — snapshot; required when cohort_id is set
  registration_id   UUID,   optional (nullable FK)
  view_count        int,    required       — how many VIEWED events preceded this completion
  total_time_on_topic ISO 8601 duration, required — cumulative across all sessions
  completion_source str,    required       — "manual" | "auto_on_view" | "auto_on_form_pass"
```

---

## Form events

### `(ATTEMPTED, Form)`

Emitted when a student starts a form (first interaction, not page load).

```
object:
  form_id           UUID,   optional (nullable FK)
  form_slug         str,    required       — snapshot
  form_title        str,    required       — snapshot
  form_type         str,    required       — snapshot; "quiz" | "survey" | "assignment"
  question_count    int,    required       — snapshot at attempt time
  max_score         int,    optional       — snapshot; null for ungraded forms
context.extensions:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    optional       — snapshot; required when cohort_id is set
  registration_id   UUID,   optional (nullable FK)
  topic_id          UUID,   optional (nullable FK) — parent topic, if form is embedded
  topic_slug        str,    optional       — snapshot; required when topic_id is set
  topic_title       str,    optional       — snapshot; required when topic_id is set
  attempt_number    int,    required       — 1-indexed
  time_limit        ISO 8601 duration, optional — if form is timed
```

### `(ANSWERED, Question)`

Emitted per question, when a student submits an answer. High volume — this is the primary source for struggle-point analytics.

```
object:
  question_id       UUID,   optional (nullable FK)
  question_slug     str,    required       — snapshot
  question_text     str,    required       — snapshot at answer time (questions can change)
  question_type     str,    required       — snapshot; "multiple_choice" | "short_answer" | "essay" | etc.
  options           list,   optional       — snapshot of available choices for multiple_choice/select questions; each entry has {id, label}; null for free-text types
result:
  response          str|list, required     — the learner's raw answer (serialized)
  success           bool,   optional       — null for ungraded questions
  score.raw         int,    optional
  score.max         int,    optional
  duration          ISO 8601 duration, required — time spent on this question
context.extensions:
  form_id           UUID,   optional (nullable FK)
  form_slug         str,    required       — snapshot
  form_title        str,    required       — snapshot
  form_attempt_id   UUID,   required       — groups answers within one attempt; copy of `student_progress.FormProgress.id` (snapshotted into the event so it survives deletion of the FormProgress row)
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    optional       — snapshot; required when cohort_id is set
  attempt_number    int,    required       — of the parent form
  question_position int,    required       — 1-indexed position within form
  changed_answer    bool,   required       — did the learner revise a previous answer?
  correct_answer    str|list, optional     — snapshot of expected answer (for later analysis)
```

### `(COMPLETED, Form)`

Emitted when a student submits a form.

```
object:
  form_id           UUID,   optional (nullable FK)
  form_slug         str,    required       — snapshot
  form_title        str,    required       — snapshot
  form_type         str,    required       — snapshot
  question_count    int,    required       — snapshot at submit time
  max_score         int,    optional       — snapshot; null for ungraded
result:
  completion        bool,   required       — always true
  success           bool,   required       — passed threshold? null for ungraded
  score.raw         int,    required       — null for ungraded
  score.max         int,    required       — null for ungraded
  score.scaled      float,  derived        — raw/max, 0..1
  duration          ISO 8601 duration, required — from ATTEMPTED to COMPLETED
  response          str,    optional       — serialized final answers (for audit)
context.extensions:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    optional       — snapshot; required when cohort_id is set
  registration_id   UUID,   optional (nullable FK)
  topic_id          UUID,   optional (nullable FK)
  topic_slug        str,    optional       — snapshot; required when topic_id is set
  topic_title       str,    optional       — snapshot; required when topic_id is set
  attempt_number    int,    required
  pass_threshold    float,  optional       — the threshold that was in force at submit time
  answers_changed   int,    required       — count of ANSWERED events with changed_answer=true
  timed_out         bool,   required       — did they hit a time limit?
```

---

## Course events

### `(REGISTERED, Course)`

Emitted when a student registers for a course (self-enrol or admin-enrol).

```
object:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
result:
  success           bool,   required       — registration succeeded
context.extensions:
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    required       — snapshot
  registration_id   UUID,   optional (nullable FK) — id is nullable; registration_id_snapshot below is immutable
  registration_id_snapshot UUID, required  — tracker-assigned UUID that survives registration deletion
  registered_by     str,    required       — "self" | "educator" | "system"
  registered_by_user_id   UUID, optional (nullable FK) — present if not self-registered
  registered_by_email     str,  optional   — snapshot; required when registered_by is "educator" or "admin"
  registered_by_display_name str, optional — snapshot; required when registered_by is "educator" or "admin"
  start_date        date,   optional       — cohort start date snapshot
  end_date          date,   optional       — cohort end date snapshot
```

### `(PROGRESSED, Course)`

Emitted when course-level progress changes (topic/form completion propagates up).

```
object:
  course_id         UUID,   optional (nullable FK)
  course_slug       str,    required       — snapshot
  course_title      str,    required       — snapshot
result:
  completion        bool,   required       — true if course is now 100% complete
  extensions:
    progress.scaled float,  required       — 0..1 completion fraction
    progress.topics_completed int, required
    progress.topics_total     int, required
    progress.forms_completed  int, required
    progress.forms_total      int, required
context.extensions:
  cohort_id         UUID,   optional (nullable FK)
  cohort_name       str,    required       — snapshot
  registration_id   UUID,   optional (nullable FK)
  trigger_event_id  UUID,   required       — the event that caused this progress update (references another xAPI event, which is itself immutable)
  trigger_verb      str,    required       — e.g. "completed"
  trigger_object_type str, required        — e.g. "Topic"
  trigger_object_slug str, required        — snapshot of the triggering object's slug
  trigger_object_title str, required       — snapshot of the triggering object's title
```

---

## Extending the schemas

When adding a new event type:

1. Define the `(verb, object_type)` pair in `verbs.py` and document it here first.
2. Err toward required fields — it's easier to relax than to tighten.
3. Always include `course_id`/`course_slug`/`course_title` and `cohort_id`/`cohort_name` in context when they apply. These drive the bulk of analytical queries and must survive deletion of the referenced records.
4. **Every FK or UUID reference must be nullable in storage and paired with a required denormalized snapshot** (slug/title/name/email — whatever identifies the entity without depending on it still existing). The snapshot is the source of truth for audit; the ID is a convenience pointer.
5. Snapshot all mutable context at event time (titles, question text, thresholds, pass marks, cohort dates, role labels). Source records mutate; events must not silently change.
6. If a field will obviously be useful for struggle-point analysis (durations, attempt counts, change counts), record it.
7. No event type may define an `UPDATE`, `DELETE`, `CORRECT`, or `AMEND` verb over an existing event. Corrections are expressed as new events (e.g. `(VOIDED, Statement)` per the xAPI spec) that point at the earlier event's immutable id.

## Immutability at the storage layer

The model that persists these events must enforce immutability beyond the schema:

- **No updates after write.** `save()` on an existing row should raise. Use a `pre_save` signal or override to block mutation of previously-persisted rows.
- **No deletes from application code.** The Django model should not expose `.delete()` (override to raise `NotImplementedError` or similar). Retention-driven purges are a separate, audited operation handled outside normal model APIs.
- **All FK references use `on_delete=SET_NULL`** (never `CASCADE`), with one exception: the `site` FK is `on_delete=PROTECT, null=False` (inherited from `SiteAwareModel`). Deleting a user, course, cohort, form, or question must not delete their xAPI history — it should only null the pointer. Deleting a site that still has events is blocked outright.
- **No uniqueness constraints that depend on live FKs.** A form can be deleted and recreated with the same slug; both histories must coexist.
- **Database-level protection is preferred.** Where the DB supports it, use a table-level trigger or `REVOKE UPDATE, DELETE` on the xAPI statement table to prevent accidental direct mutation.

## Validation

The `track()` helper validates against these schemas at call time:

- Missing required fields (including required snapshots) → raise `TrackingSchemaError` (fail loud in dev, log + drop in prod behind a flag)
- A populated ID field with its paired snapshot missing → raise `TrackingSchemaError`. We never persist a dangling ID without its snapshot.
- Unknown fields → log a warning but persist (we'd rather keep the data)
- Type mismatches → coerce where safe (int↔str for IDs), error otherwise

Schemas are defined in `freedom_ls/experience_api/schemas.py` as Pydantic models (or equivalent) so validation is centralized.
