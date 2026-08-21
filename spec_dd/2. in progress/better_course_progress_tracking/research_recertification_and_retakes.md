# Research: Recertification, Retakes, and Completion History

Scope: how mature LMS/certification products model "this learner did this course before and is
doing it again" — recertification windows, retake semantics, certificate binding, and reporting
that doesn't double-count. Grounded against FLS's current models where relevant.

## FLS baseline (for context, not the audit)

Confirmed by reading the actual model code (not re-auditing, just checking the specific claims in
the brief):

- `TopicProgress` — `unique_together = ["user", "topic"]` (`freedom_ls/student_progress/models.py:560`).
  One row per (user, topic), full stop. There is no dimension to hang a second attempt off.
- `CourseProgress` — `unique_together = ["user", "course"]` (`freedom_ls/student_progress/models.py:607`).
  Same problem at the course level.
- `FormProgress` — **no** unique constraint; many rows per (user, form) already exist, one per
  attempt, with `get_or_create_incomplete` picking the latest incomplete one
  (`freedom_ls/student_progress/models.py:167-188`). This is the one place in FLS that already has
  attempt semantics, and is a useful internal precedent for the design.
- `UserCourseRegistration` — `UniqueConstraint(fields=["site_id", "collection", "user"])`
  (`freedom_ls/student_management/models.py:59-64`), with an `is_active` boolean. This hard-blocks a
  second registration for the same user+course today; a re-run/recert cannot be represented without
  either reusing the same row (losing history) or relaxing the constraint.
- The `certificates` idea (`spec_dd/1. next/certificates/idea.md`) is currently a 3-line stub
  ("verifiable, tamper-evident certificates with a public verify URL") with no binding model decided
  yet — this research's "Certificates" section is directly load-bearing for that spec.

## Recertification / validity windows

**Totara Certifications** are the most fully-specified public model of this problem:

- A certification has an **active period** (how long a completion stays valid) and a
  **recertification window** — "the period before the certification expires that a learner can
  start recertifying," e.g. a 1-month window before a 12-month expiry.
  [Totara: What are certifications?](https://totara.help/docs/what-are-certifications) ·
  [Totara: Recertification cycles](https://www.totara.com/articles/recertification-cycles/)
- Three ways to calculate the *next* expiry date, each with different drift behaviour:
  **completion-based** (expiry = completion date + period — drifts later each cycle if learners
  finish early), **expiry-based** (expiry = previous expiry + period — no backward drift, but if a
  learner is overdue the next cycle is still measured from the missed date), and **fixed
  date-based** (anchored to a base date, e.g. hire date, with the period added repeatedly until a
  future date results — never drifts). [Totara: Fixed dates and minimum certification interval](https://totara.help/docs/fixed-expiry-date-minimal-interval)
- When the window opens, Totara **resets activity/course completion on the recertification pathway**
  (including RPL/credit-transfer records) so the learner is forced through the course again, while
  the certification record itself keeps the prior cycle's completion in history. States exposed are
  effectively **active / window-open / expired**, plus a "primary path vs recertification path"
  distinction so admins can require a shorter refresher course on renewal rather than the full
  original course. [Totara: Exploring the certification completion editor](https://totara.com/articles/exploring-the-certification-completion-editor-in-totara-learn/) · [Totara: Recertification settings](https://totara.help/19/docs/recertification-settings)
- **Known failure mode**: if a learner completes the refresher *before* the window officially opens,
  Totara does not credit it — the completion is recorded but doesn't roll the certification forward,
  and admins report having to manually patch data. This is a direct consequence of coupling "window
  state" to "which completion counts" instead of treating every completion as a first-class,
  independently timestamped record. [Totara Community forum: Certification window opening removes completion data if taken outside the window](https://totara.community/mod/forum/discuss.php?d=25221)

**Moodle Certifications** (the older Totara/Moodle-shared module, still documented) work the same
way structurally: expiry is "never / fixed date / N months after completion"; the recertification
window opens N months before expiry; when it opens, completion records for the *program's* courses
are reset and the learner must retake them, even if they're directly enrolled in those courses
outside the program. Config changes after enrolment don't retroactively touch existing completion
records — historical rows are immutable once written. [MoodleDocs: Certifications](https://docs.moodle.org/403/en/Certifications)

**Moodle course-level "reset"** is a blunter, non-recertification-aware operation:
- `block_resetcompletion` lets a *learner* self-reset their own quiz/SCORM/choice/completion data to
  redo a course — a pure wipe, no history kept. [Moodle: Reset Completion block](https://moodle.org/plugins/block_resetcompletion)
- `local_recompletion` (Dan Marsden) is the de-facto standard plugin for scheduled recertification on
  plain (non-Totara) Moodle: on a configured trigger (time since completion, or a fixed date) it
  wipes course + activity completion, with an **optional archive** step that copies the outgoing
  data into separate `local_recompletion_cc` / `local_recompletion_cc_cc` / `local_recompletion_cmc`
  (and per-activity, e.g. `local_recompletion_h5p`) tables before deleting the live rows. Quiz/SCORM
  attempts can either be archived-and-wiped or kept-and-appended-to (learner gets a new attempt on
  top of old ones). Reporting against the archive requires a **separate custom-report-builder
  source** — it is not part of the normal "current completion" report. [GitHub: danmarsden/moodle-local_recompletion](https://github.com/danmarsden/moodle-local_recompletion) · [Moodle Plugins: Course recompletion](https://moodle.org/plugins/local_recompletion)
- **Known gap**: `local_recompletion` explicitly does *not* reset the certificate module's cached PDF
  — admins report that after a wipe-and-retake, the old certificate (with the old completion date)
  is still what gets served unless the certificate's date field is repointed from "course completion
  date" to an activity date or "issue date" as a workaround. This is exactly the certificate-binding
  problem below. [Moodle forum: Course certification expires - new certificate date?](https://moodle.org/mod/406/en/discuss.php?d=440069) [Moodle forum: recertification/recompletion plugin](https://moodle.org/mod/forum/discuss.php?d=357491)

**Docebo** (SaaS competitor, no self-hosted recertification module to inspect directly, but public
docs are explicit about the pattern):

- A **Certification** object sits above courses/learning-plans; it has a validity period and,
  optionally, "**Allow users to retake the same course or learning plan to renew their
  certification**." When a learner renews, "**the previous enrollment will be archived, and not
  overwritten**" — new enrolment created, progress reset, old one demoted to a queryable "archived"
  state, not deleted. [Docebo Help: Certificates and certifications](https://help.docebo.com/hc/en-us/articles/22057130562066-Certificates-and-certifications) · [Docebo Help: Managing legacy certifications](https://help.docebo.com/hc/en-us/articles/360020083240-Managing-the-Certifications-and-retraining-app)
- **Known failure mode #1** (structural): outside of the Certification app, Docebo's base **course
  enrolment model only tracks a single completion record per (user, course)** — retaking overwrites
  nothing by default and doesn't create a new record either; admins report learners retake a course
  expecting a fresh completion date/score and the system just keeps the *first* completion forever.
  The community's own workaround is renaming courses per cycle ("BSA 2021", "BSA 2022") purely to get
  a distinct completion row. [Docebo Community: Users Retaking Training](https://community.docebo.com/product-q-a-7/users-retaking-training-692)
- **Known failure mode #2** (sync/consistency): the Certification object and the underlying Course
  enrolment are separate entities with no back-communication. When a certification expires, the
  *course* enrolment still shows "Completed" — there is no "Expired" enrolment state — so
  dashboards and reports built off course status say the learner is compliant while the
  certification widget says expired. Docebo's own community explicitly asked for either a merged
  status model or a genuine "Expired" enrolment state. [Docebo Community: Course Status Not Matching Certification Status](https://community.docebo.com/docebo-superadmins-46/course-status-not-matching-certification-status-11248)

**Absorb LMS** documents the same archive-on-reenrol pattern in plain language: "When a User is
Re-enrolled in a Course, all of their Lesson progress will be reset... However, their previous
Enrollments will be archived, and the LMS will retain all of the reporting data from these Historic
Enrollments." Reports (User/Course Enrollments, Course Activity) can pull historic enrolments
specifically, kept separate from "current" by default. Automatic re-enrolment can be wired to a
certificate's expiry (e.g. certificate expires in 1 day → auto re-enrol triggers the day before).
[Absorb Help: Re-Enrollment & Re-Certification](https://support.absorblms.com/hc/en-us/articles/219544607-Re-Enrollment-Re-Certification)

**Cornerstone OnDemand**: public docs are marketing-level rather than schema-level, but consistently
describe "recurring certification cycles," "validity periods," and "grace periods" as first-class,
independently configurable settings distinct from the course itself — i.e. the certification/cycle
concept is a wrapper *around* one-or-more course completions, not a property baked into the course.
No implementation detail on archive-vs-overwrite was publicly documented. [Cornerstone: Compliance Training with Advanced Training Models](https://www.cornerstoneondemand.com/resources/article/ways-to-manage-compliance-training/)

## Completion archives: pattern and trade-offs

Two structural approaches recur across every product above:

1. **Archive-on-reset** (Moodle `local_recompletion`, Absorb, Docebo Certifications): the *live*
   progress/completion table always holds exactly one row per (user, course) representing the
   current cycle. On retake, the outgoing row is copied to a separate archive table (or an
   `is_archived`/`state=archived` flag) and the live row is reset in place. **Pro**: every "current
   status" query stays a trivial `WHERE user=X AND course=Y`, no dedup logic needed, fast and safe by
   construction. **Con**: archive tables need their own reporting surface (Moodle's is bolted on via
   custom report-builder sources, not the standard reports) — history is a second-class citizen, and
   plugins/queries that don't know about the archive schema silently ignore prior attempts.

2. **Single table, attempt/registration key** (Docebo's Certification-level enrolment archiving is
   actually a light version of this — old rows get an `archived=true` flag rather than moving tables;
   FLS's own `FormProgress` already does this with unbounded rows per user+form). **Pro**: one
   schema, one set of joins, history and current state live together, easy to add new report views
   later without a migration. **Con**: every query that wants "current status only" must explicitly
   filter/rank (see Reporting section) — get this wrong once and you double-count or show stale
   status, which is exactly what the Docebo course-vs-certification bug above is.

Given FLS's `FormProgress` precedent (many rows, no unique constraint, `get_latest_incomplete`
convention) and that the codebase is Django/Postgres (window functions and partial indexes are
cheap), the single-table-with-attempt-key pattern is the better structural fit for FLS specifically
— it avoids introducing a second schema shape (archive tables) that the existing `FormProgress`
pattern doesn't use, and Postgres partial unique indexes (`UNIQUE (user_id, course_id) WHERE
is_current`) can give the archive-table's query-simplicity without an actual second table.

## Retake semantics: does prior progress carry over?

No product researched defaults to full carry-over of item-level completion into a fresh attempt —
all of them treat "retake" as "reset the child items, keep the outer record for history":

- Totara/Moodle Certifications: explicit, unconditional reset of course + activity completion on
  the recertification pathway, including previously-approved RPL/credit-transfer entries. [Totara: Recertification settings](https://totara.help/19/docs/recertification-settings)
- `local_recompletion`: resets course/activity completion; **quiz and SCORM attempts** are the one
  exception with a genuine *configurable* choice — either delete-and-archive the old attempts, or
  keep them and let the learner add new attempts on top (so grading-method "highest of all attempts"
  can still see the old data). This is the closest thing to a documented "partial credit carry-over"
  toggle, and it's scoped narrowly to attempt-graded activities, not blanket item completion. [GitHub: danmarsden/moodle-local_recompletion](https://github.com/danmarsden/moodle-local_recompletion)
- Docebo/Absorb re-enrolment: unconditional "Lesson progress will be reset" — no partial-credit
  option surfaced in docs at all. [Absorb Help: Re-Enrollment & Re-Certification](https://support.absorblms.com/hc/en-us/articles/219544607-Re-Enrollment-Re-Certification)
- Where "keep the better score" *does* exist as a first-class, commonly-offered setting is at the
  **quiz/SCORM attempt level, within a single course run** (not across recertification cycles):
  Moodle SCORM's grading method (first / last / average / highest across attempts *within one
  enrolment*), and 360Learning's multi-attempt SCORM sessions. [MoodleDocs: SCORM settings](https://docs.moodle.org/502/en/SCORM_settings) · [360Learning: Set up a SCORM file to allow several attempts](https://support.360learning.com/hc/en-us/articles/4402930736788-Set-up-a-SCORM-file-to-allow-several-attempts-in-a-session)

So the pattern is two-tiered, and worth keeping distinct: (a) **within one registration/attempt**,
"keep highest/latest score across N tries at one quiz" is common and configurable; (b) **across
registrations** (a genuine recert/re-run), full reset of item-level completion is the default and,
where a carry-over exists at all, it is a narrowly-scoped, explicit RPL/credit-transfer mechanism —
never an implicit inheritance.

## Certificates: binding to a specific completion, not to (user, course)

This is the sharpest, most transferable finding for FLS given the queued `certificates` spec:

- Docebo's course-vs-certification desync bug (above) is a direct consequence of certificates/
  compliance status being computed from a (user, course) row that only ever holds the *first*
  completion, while the certification wrapper independently tracks expiry. The fix the community
  asked for — an explicit "Expired" enrolment state, or merging the two objects — is really asking
  for the certificate/compliance status to be **derived from the specific completion record it was
  issued against**, not recomputed against a mutable "current" row that a later retake can silently
  invalidate or leave stale. [Docebo Community: Course Status Not Matching Certification Status](https://community.docebo.com/docebo-superadmins-46/course-status-not-matching-certification-status-11248)
- Moodle's `mod_customcert` generates the PDF **on demand** from whatever the current completion
  record says (it is not a stored artifact) — "A Learner's Certificate is not saved in the LMS...
  will only appear as a temporary file when it is viewed." That means if the certificate's date
  field is bound to "course completion date" and a recompletion plugin resets that date, **the
  certificate silently changes retroactively** to reflect the new (or blank, mid-retake) state,
  which is the opposite of "tamper-evident" — there is no snapshot of what the certificate said at
  issuance time. [Absorb-equivalent finding also holds; primary source:] [Moodle forum: recertification/recompletion plugin](https://moodle.org/mod/forum/discuss.php?d=357491) · [GitHub mdjnelson/moodle-mod_customcert issue #484](https://github.com/mdjnelson/moodle-mod_customcert/issues/484)
- Absorb explicitly does **not** retroactively award a certificate for completions that predate the
  certificate being attached to the course — evidence that Absorb's certificate issuance is a
  point-in-time event tied to *when completion happened*, not a live query over current state.
  [Absorb Help: Course Certificates](https://support.absorblms.com/hc/en-us/articles/14232811270291-Course-Certificates)
- No product researched documents an explicit "superseded" certificate status shown to the
  certificate holder/verifier (e.g. "this certificate is no longer your most recent — see
  certificate #2"); expiry is generally computed live from the certification wrapper, and the
  certificate PDF itself is either regenerated fresh each time (Moodle) or a static artifact from
  issuance (Absorb-style) with no visible "superseded" marker distinct from "valid/expired."

**Direct implication**: FLS's `certificates` spec should bind a certificate row to an immutable
completion/attempt record (e.g. `CourseProgress` snapshot at completion time, or a dedicated
`registration_id` + `completed_at`), not to `(user, course)`. The public verify URL then always
resolves to "what was true when this certificate was issued," independent of whatever the learner's
*current* registration says — this also composes cleanly with the already-queued
`content_snapshots` spec (verify page can show "issued against course content as of snapshot N").

## Reporting: current-status vs history, avoiding double-counting

The recurring failure pattern across every product is a report built against a table that doesn't
disambiguate "the row that matters right now" from "a row that used to matter":

- Docebo forum: "*Discrepancies in enrollment records, such as learners appearing as 'Not Started'
  despite having completed a course... arise due to the presence of multiple enrollment records for
  the same learner in a course, or the inclusion of historical enrollment data in reports.*" — i.e.
  reports that don't filter to "latest/active registration" surface stale or contradictory rows.
  [Search-aggregated finding, consistent across Absorb/Docebo community reports on re-enrolment reporting]
- Absorb's answer is structural: "current" reports (User Enrollments, Course Enrollments, Course
  Activity) only ever show the live/current enrolment; a *separate* "Historic Enrollments" report is
  where prior cycles live, reachable by drilling into the current enrolment. The two are never
  merged in one result set, which is what prevents double-counting. [Absorb Help: Re-Enrollment & Re-Certification](https://support.absorblms.com/hc/en-us/articles/219544607-Re-Enrollment-Re-Certification)
- The canonical SQL-level pattern for "is this person currently compliant" over a single-table,
  multi-attempt schema (the shape FLS's `FormProgress` already uses) is: partition by
  (user, course) [or (user, registration-group)], order by `started_at`/`registered_at` DESC,
  take the top row (`ROW_NUMBER() OVER (PARTITION BY user_id, course_id ORDER BY registered_at DESC)
  = 1`), and only that row feeds "current status" dashboards/reports; any row-count or completion
  aggregate report groups by that same partition key first to avoid counting cycle 1 and cycle 2 of
  the same learner as two people. Equivalently, a partial unique index / boolean flag
  (`is_current_registration`) maintained by the app layer avoids paying the window-function cost on
  every report query. No vendor documents this query pattern publicly at the SQL level (confirmed by
  search — this is standard practice inferred from the archive-vs-live-table split every vendor
  does at the product level, not a documented SQL recipe), so treat it as an implementation pattern
  FLS should design explicitly rather than something to copy from a vendor doc.

## Failure modes summary (what to explicitly avoid)

1. Completion/certificate state computed from a mutable "current" row that a later retake can
   overwrite or reset out from under an already-issued certificate (Docebo, Moodle customcert).
2. Certification/compliance wrapper and course-completion status stored and updated independently,
   with no back-reference, so they silently disagree ("Completed" course + "Expired" certification
   shown simultaneously) (Docebo).
3. Recertification triggered strictly by a time window, so an early/eager retake outside the window
   is recorded but doesn't count, requiring manual data fixes (Totara).
4. Reports that don't partition by registration/attempt, so a learner with 3 runs of a course is
   counted 3 times, or their "Not Started" archived run masks their "Completed" current run
   (Docebo/Absorb community reports).
5. Certificate-relevant date fields (issue/expiry) bound to a live "course completion date" column
   instead of a frozen value captured at issuance, so the rendered certificate changes after the
   fact (Moodle customcert + local_recompletion interaction).

## Implications for FLS

1. **Give registrations, not just progress, an attempt identity.** Relax
   `UserCourseRegistration`'s `UniqueConstraint(site_id, collection, user)` to allow multiple rows,
   but add an explicit "current" marker — either a partial unique index
   (`UNIQUE (site_id, collection, user) WHERE is_active`) so there is at most one *active*
   registration at a time (extending the existing `is_active` boolean rather than replacing it), or
   an explicit `attempt_number`/`cycle` integer. Every `TopicProgress`/`CourseProgress` row should
   carry a nullable FK to the registration it belongs to, so history can be reconstructed
   per-attempt even though the current unique constraints stay largely as-is for the "current" slice.

2. **Default retakes to a hard reset of item-level completion, no partial credit carry-over.** Every
   product researched defaults this way; the one place carry-over is genuinely offered
   (quiz/SCORM "keep highest attempt") is scoped to attempts *within* a single registration, which
   FLS's `FormProgress` (no unique constraint, multiple attempts per form already) already supports
   structurally. Don't build cross-registration carry-over now — it is not what any compliance-grade
   product does by default, and B-BBEE/aviation-regulator contexts specifically want "retake means
   retake," not silently inherited answers.

3. **Don't build a full validity/expiry (recertification-window) concept yet — but don't foreclose
   it.** The window-based recert model (Totara/Docebo/Absorb) is real complexity (drift rules,
   window-open state, auto-re-enrolment) that none of FLS's named drivers (cohort re-runs, ad hoc
   renewal) strictly require today. What *is* needed now is the substrate it would sit on top of:
   multiple registrations per user+course, each with its own timestamps. Adding `valid_until` /
   recert-window fields later is additive if the registration model already supports multiple rows;
   it is a rewrite if it doesn't.

4. **Bind certificates to a specific registration/attempt, never to (user, course).** Given the
   `certificates` spec explicitly wants "tamper-evident" verification, this is not optional — it is
   the one finding with a documented real-world failure (Moodle customcert regenerating differently
   after a reset; Docebo's course/certification desync). The certificate row should snapshot the
   completion timestamp, course version (pairs naturally with the queued `content_snapshots` spec),
   and score at issuance, and the verify page should resolve against that snapshot, not a live query
   over current registration state.

5. **"Current registration" resolution rule**: when several registrations exist for a user+course,
   the canonical rule should be *the most recently registered active one* (`is_active=True` row,
   highest `registered_at`) — mirroring Absorb/Docebo's "one current enrolment, N archived" model.
   All student-facing views (resume, progress bar, TOC) and default reports should filter to that row
   only; a distinct "history" view/report (mirroring Absorb's separate Historic Enrollments report)
   should be the only place prior attempts surface, so default reports never need de-duplication
   logic and can't double-count by construction — this sidesteps the Docebo/Absorb double-counting
   complaints entirely rather than requiring every report author to remember a window-function query.

6. **Reuse the `FormProgress` shape as the template, not a new archive-table pattern.** FLS already
   has a working "many rows per (user, form), no unique constraint, `get_or_create_incomplete`
   helper" convention for attempts. Extending `TopicProgress`/`CourseProgress` to the same shape
   (FK to registration instead of a bare unique constraint on user+item) keeps one schema style
   across the app, rather than introducing Moodle-style separate archive tables that need their own
   bolted-on reporting surface.

status: ok
