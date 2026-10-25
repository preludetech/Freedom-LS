# Research: best practices for layered due dates, relative offsets and overdue

Scope: decisions spec `deadlines-1-dates-and-overdue` must make. Does not repeat the parent research
(`spec_dd/1. next/deadlines/research_lms_deadlines_landscape.md`, sections a, b, f;
`research_deadlines_user_sentiment.md`, sections d, g). Source note: the URLs below are the canonical
documentation pages for well-established behaviour; they were cited from knowledge of those docs and
not re-fetched in this run, so treat quoted specifics as "check at spec time" where marked.

## 1. Storing relative offsets

- Store the offset as a **calendar-day count (integer)**, not a duration of seconds. "30 days after
  registration" means the same wall-clock time 30 calendar days later; a 30 x 24h duration drifts by an
  hour across a DST change. ISO 8601 itself distinguishes nominal durations (`P30D`, calendar days) from
  exact time (`PT720H`); `P30D` is the day-based form. [1][2]
- Compute in the **site time zone, then convert to UTC**: take the anchor (`CourseProgress.created_at`,
  UTC) -> convert to site zone -> add `timedelta(days=n)` to the *naive/local wall time* (or add to the
  local date) -> attach zone -> convert to UTC. Python's aware-datetime `+ timedelta(days=n)` keeps the
  wall time in `zoneinfo` (arithmetic is wall-clock within one tzinfo), which is the wanted behaviour; do
  not do arithmetic after converting to UTC. [3]
- Because the spec's due time is end-of-day, offsets are really "N days after the registration *date*",
  then end of that day. That removes most DST sensitivity (only the day's end instant varies).
- Keep the unit set small. Days only for v1; weeks/months are a UI/authoring sugar (`4w` = 28d). Months
  are ambiguous (31 Jan + 1 month) and need an explicit clamp rule; avoid unless asked.
- Zero/negative offsets: reject negative; decide whether `0d` (due at end of registration day) is legal.
- Ambiguous/non-existent local times (DST gap/fold) only arise if a time of day other than end-of-day is
  allowed. End-of-day avoids it except for zones that change at midnight; use `zoneinfo` + Django
  `make_aware(..., is_dst)` removed in Django 5 -> use `zoneinfo`, `fold` defaults. [4]

## 2. End-of-day semantics

- Best practice for **storage**: an aware instant in UTC (Django `USE_TZ = True` stores UTC in
  PostgreSQL `timestamptz`; convert at the edges with `django.utils.timezone` and `zoneinfo`). [4][5]
- For **meaning**, prefer storing the *date* (and offset) as authored and deriving the instant in the
  resolver. A stored `DateField` + implicit "end of day in site zone" keeps the date stable if the site
  zone is later changed deliberately and avoids baking 23:59:59 into rows. If an override needs a
  specific time, add an optional time-of-day later; do not make it v1.
- **Exclusive next-midnight** (`due < start_of_next_day`) is the more robust comparison than
  `<= 23:59:59`: no gap for sub-second values (23:59:59.5) and no leap-second/precision argument. Show
  the learner "11:59 PM" or "end of 14 March", but compare with `now >= next_midnight`. This is the
  pattern used for date-range queries in Django generally (half-open intervals). [5]
- Midnight defaults (00:00 of the due date) are the single biggest source of "it closed a day early"
  complaints (parent sentiment, section d). End-of-day is consistent with the settled decision.
- Moodle and Canvas both show a date+time and the time zone offset; the spec should show time zone
  abbreviation and the date, never a bare time. (See parent landscape section f.)

## 3. Override modelling

- **Nullable override field on a row that already exists, one row per (scope)** is the simplest pattern:
  a `CohortCourseRegistration`-level and a learner-level row, each with nullable `due_date` / offset /
  time-limit fields; `NULL` = "inherit". Resolver walks learner -> cohort -> content, first non-null
  wins. Separate per-item override rows (one row per placement x scope) scale better when only a few items
  are overridden, and avoid wide tables of nullable columns per placement. Given placements are the unit
  (idea.md), a row per (placement, scope) with a unique constraint is the cleaner fit; a course time limit
  is a row per (course registration, scope) or a field on the registration.
- **Distinguish "no override" from "override to no deadline"** (explicit removal). A nullable column
  cannot express both. Use a separate flag/choice (e.g. `kind`: inherit / fixed / offset / none) or a row
  whose existence is the override and whose fields may be empty meaning "no deadline". This is a frequent
  bug source in layered-config systems.
- **Follow vs snapshot.** Best practice for configuration inheritance (e.g. Moodle overrides, Canvas
  assignment overrides, Kubernetes-style layering) is *reference the layer, don't copy it*: an override
  that stores only the changed value keeps following everything it didn't set. Storing a snapshot of the
  default is the cause of "silently stops following" complaints (idea.md, sentiment implication 4). Recommend:
  override is a stored *value*, not a copy of the default; changing the content default changes learners
  who have no override, and an override never silently converts. If an override is "relative", store the
  offset and let the anchor change; if "fixed", store the date. Flag in admin when an override equals the
  default (redundant) or sits on a placement that no longer exists.
- **Audit**: record `created_by`/`updated_by` (actor, FK nullable `SET_NULL`), `reason` (text, required for
  overrides by humans), and `created_at`/`updated_at`. For a history, `django-simple-history` or an
  append-only log table is the standard; for v1 the "who, why, when of the *current* value" is enough, and
  spec 3 (extensions) can add history. In admin, set actor in `save_model`, not via a form field, so it
  cannot be forged. [6]
- Same-layer "most permissive wins" (settled) -> resolver takes `max` of candidate instants at that layer.
  Document that "none" at a layer means no deadline at that layer, which with "most permissive" must beat
  any dated one: decide this explicitly.

## 4. Resolver design

- **Pure function over plain values**: `resolve(anchor, content_default, cohort_override, learner_override,
  site_tz, now?) -> ResolvedDeadline(instant, source_layer)`. No ORM inside; the caller loads data. This
  keeps it unit-testable and lets later specs (pause shifts) add an input without a second resolver.
- Return the **source layer** with the value ("from cohort", "learner override") — it makes admin/ UI
  explanations and the audit story possible at near-zero cost.
- **Batching**: for a TOC, load all placements for the course (one query, `select_related`), all cohort
  overrides for the registration (one query), all learner overrides for the registration (one query), the
  anchor once; then call the pure function per placement in Python. Cost: three or four queries
  independent of the item count. Avoid per-item `.get()` and per-item model properties. [7]
- Provide a bulk entry point `resolve_for_course(registration) -> dict[placement_id, ResolvedDeadline]` and
  a single-item convenience that calls it. Prefer returning dataclasses (frozen) over dicts.
- Overdue is derived: `not completed and now >= due_instant`. Compute `now` once per request and pass it
  in (testable, consistent across a page).

## 5. Validating authored dates in YAML/frontmatter with pydantic

- YAML parses bare `2026-03-14` as a `date` and `2026-03-14 17:00` as a `datetime`; quoted values are
  strings. Pydantic v2 accepts `date`, `datetime`, and ISO strings. Use **`date`** for fixed item due dates
  (matches end-of-day semantics) and reject datetimes with a clear error via a `field_validator(mode=
  "before")` (pydantic coerces some datetimes at midnight to date, and rejects others). [8]
- Offsets: model as a small value type parsed from a string, e.g. `"30d"` -> `RelativeOffset(days=30)`, with
  a regex validator (`^\d+d$`, optionally `w`), or accept the integer form via a discriminated model
  (`{after: 30, unit: days}`). Parse in a `BeforeValidator`; keep the canonical form on the model so the
  loader writes an integer day count to the DB. ISO `P30D` is also acceptable but unfamiliar to authors;
  prefer the short form and document it. [1][8]
- Mutual exclusion: a model validator rejecting both fixed date and offset on the same item. Unknown keys:
  `extra="forbid"` so typos like `due_in` fail load rather than silently dropping a deadline.
- Error messages should name the file and field; validation runs at content load (idea.md), so failures
  must surface in the sync report, not as runtime errors.
- Timezone not accepted in authored dates: authors give a date only; the site zone supplies the rest.

## 6. Displaying dates

- Always show zone: Django `{% load tz %}` with `localtime` and format `"j M Y, g:i A T"` renders the
  abbreviation (`SAST`, `EST`); some zones render numeric offsets (`+04`) because `zoneinfo` has no
  abbreviation — prefer the IANA name or "UTC+4" in a tooltip/help text. [4][9]
- Use `<time datetime="...">` with the ISO-8601 instant for machines/assistive tech; visible text for
  people. [10]
- Relative phrasing ("due in 3 days") is helpful but should accompany, not replace, the absolute date; relative
  is computed in site-zone calendar days, not 24h blocks, or "due in 1 day" at 23:00 the day before reads
  wrongly. Django `timesince`/`timeuntil` give elapsed time not calendar days; write a small helper over
  site-zone dates. Cache nothing: compute server-side per request; avoid client JS counting. [9]
- Say "Due by end of 14 March (SAST)" for end-of-day dates; this resolves the midnight ambiguity.

## 7. Accessibility of overdue markers

- WCAG 2.2 SC 1.4.1 Use of Color: colour must not be the only way to convey information. Overdue needs a
  text label ("Overdue") and/or icon with accessible name, plus colour. [11]
- Contrast: text and badge meet 4.5:1 (1.4.3); non-text indicators 3:1 (1.4.11). [12]
- Do not use `title`-only tooltips. Put "Overdue" as visible text, or visually-hidden text on an icon
  (`sr-only`). For a list, include the due date in the item's accessible text ("Due 14 March, overdue").
- Don't announce via live regions on page load; static text is correct for a derived state shown on render.
- On a dashboard card with several overdue items, a count in text ("3 items overdue") satisfies 1.4.1 and is
  more informative than a coloured dot.

## Decisions the spec should take from this

1. Offset unit = whole calendar days, stored as integer; arithmetic in site zone on dates.
2. Fixed date = `DateField`; effective instant = start of next day in site zone (exclusive); show as
   "end of <date> <zone>".
3. Overrides carry explicit state (inherit / fixed / offset / none), actor, reason, timestamps; they store
   values, not snapshots of defaults.
4. Resolver pure + bulk loader + returns source layer; `now` injected.
5. Frontmatter: `date` for fixed, `"Nd"` string for offsets, `extra="forbid"`, mutually exclusive.
6. UI: absolute date + zone always; relative phrase optional; overdue as text + icon, not colour alone.

## References

1. ISO 8601 duration overview - https://en.wikipedia.org/wiki/ISO_8601#Durations
2. RFC 3339 / ISO date-time conventions - https://datatracker.ietf.org/doc/html/rfc3339
3. Python `datetime` aware arithmetic and `zoneinfo` - https://docs.python.org/3/library/datetime.html and https://docs.python.org/3/library/zoneinfo.html
4. Django time zones - https://docs.djangoproject.com/en/stable/topics/i18n/timezones/
5. Django database `DateTimeField`/`USE_TZ` and range lookups - https://docs.djangoproject.com/en/stable/ref/models/fields/#datetimefield
6. Django admin `save_model` - https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.save_model ; django-simple-history - https://django-simple-history.readthedocs.io/
7. Django `select_related`/`prefetch_related` - https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related
8. Pydantic v2 datetime types and validators - https://docs.pydantic.dev/latest/api/standard_library_types/#datetimedate and https://docs.pydantic.dev/latest/concepts/validators/
9. Django template filters `date`, `timesince`, `timeuntil` - https://docs.djangoproject.com/en/stable/ref/templates/builtins/
10. HTML `<time>` element - https://developer.mozilla.org/en-US/docs/Web/HTML/Element/time
11. WCAG 2.2 SC 1.4.1 Use of Color - https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
12. WCAG 2.2 SC 1.4.3 / 1.4.11 contrast - https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html and https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html

status: ok
