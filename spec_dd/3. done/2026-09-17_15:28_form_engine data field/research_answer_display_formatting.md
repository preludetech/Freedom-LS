# Research: displaying `date`/`time`/`datetime` `QuestionAnswer.text_answer` values

## What this settles

**Display surfaces that read `text_answer` as human-readable text (need formatting for the new types):**

1. `freedom_ls/course_applications/templates/course_applications/check_your_answers.html:59` — `{{ row.answer.text_answer }}` inside a `<dd>`. The applicant-facing "check your answers" review. This is the surface the idea names explicitly.
2. `freedom_ls/form_engine/admin.py:345-352` (`QuestionAnswerAdmin.answer_preview`) — `list_display` column, does `obj.text_answer[:50]` directly as Python, not a template. Any formatting has to happen in this method (or something it calls), not a template filter.
3. `freedom_ls/form_engine/admin.py:341` — the `QuestionAnswerAdmin` change-form's `text_answer` field itself is a plain `TextField` widget (not overridden), so today it shows the raw string when a superuser opens one answer row directly. Whether this is in scope is a call for the spec, not this research: it is an edit widget, not a read-only display, and reformatting it changes what gets saved back if untouched.
4. `freedom_ls/form_engine/admin.py:245` (`QuestionAnswerInline.fields`, on `FormProgressAdmin`) — the same `text_answer` field rendered inline under a `FormProgress` in the admin. Same edit-widget caveat as #3.

No other human-readable surface currently renders `text_answer` at all:

- **Quiz results / review** (`freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`) shows only `selected_options` (`item.learner_selected`, `item.correct_options`) via `FormProgress.get_incorrect_quiz_answers()` (`freedom_ls/form_engine/models.py:535-599`). That method explicitly skips `FREE_TEXT_QUESTION_TYPES` (`models.py:567`), so a quiz built with a `date`/`time`/`datetime` question never surfaces its answer text on this page at all — confirmed by decision 4 in `idea.md` (typed free-text questions score 0 and carry no correct-answer concept). Nothing to format here today.
- **`course_form_page.html`** (the form runner) only reflects the answered-count and page furniture in the template; it never echoes `text_answer` as text — the value only comes back through the input's `value`/inner-text (see below).
- **`educator_interface`**: grepped for `text_answer`/`selected_options`/`answer` across the app — no view or template renders an applicant's or learner's answer content. Educators see cohorts, progress percentages and scores, not raw form answers, so there is currently no educator-facing surface to update for this idea.
- **CSV/export**: no `ModelResource` or admin export exists for `QuestionAnswer`, `FormProgress`, or `form_engine` at all (grepped `csv`/`export` across the codebase; the only export machinery is `freedom_ls/site_aware_models/admin_exports.py`, used today by `referral_tracking/resources.py`, not by `form_engine`). There is nothing to update on this axis, only something to keep in mind if a `form_engine` export is ever added (see the sorting/export research point below).

**Surfaces that must keep the raw ISO string — do not format:**

- Every `value="{{ answer.text_answer }}"` in `freedom_ls/form_engine/templates/form_engine/inputs/short_text.html:10` and `inputs/number.html:15`, and the equivalent inner-text interpolation in `inputs/long_text.html:9` (a `<textarea>` has no `value` attribute; its stored content is its text node, same constraint). These re-populate a form input the browser must be able to parse: an `<input type="date">`/`type="time">`/`type="datetime-local">` **requires** its `value` to be exactly `YYYY-MM-DD`, `HH:MM` (or `HH:MM:SS`), or `YYYY-MM-DDTHH:MM` respectively — any other string is silently rejected by the browser and the field renders empty. New `inputs/date.html`, `inputs/time.html`, `inputs/datetime.html` templates (implied by the idea, not yet built) must follow the same pattern as the existing three: raw `answer.text_answer`, unformatted, straight into `value`.
- `search_fields = (..., "text_answer")` on `QuestionAnswerAdmin` (`admin.py:334`) searches the raw stored string. A formatted display does not change what is searched; note it so a future "search doesn't find my typed date" report isn't a bug in the display helper.

**Template-filter convention already in place:** `freedom_ls/base/templatetags/fls_base_filters.py` is exactly this kind of thing — the `duration` filter (`fls_base_filters.py:12-38`) takes an arbitrary `object`, returns `""` for anything it can't handle rather than raising, and is documented with a usage comment. `get_dict_item` is the other filter in the library and is already loaded (`{% load fls_base_filters %}`) in every input template and in `check_your_answers.html`'s surrounding page. A date/time-answer display filter fits this library and this loading convention; it does not need a new templatetag module.

**Settings actually in force (`config/settings_base.py:236-242`):**

```
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
```

`USE_L10N` is not set — it was deprecated in Django 4.0 and removed entirely as of Django 5.0; localized formatting is now unconditionally on. FLS is Django 6.x, so this project cannot turn localized formatting off even if it wanted to. No `DATE_FORMAT`, `DATE_INPUT_FORMATS`, `SHORT_DATE_FORMAT`, or `FORMAT_MODULE_PATH` override exists anywhere in `config/`. `freedom_ls/site_aware_models/config.py` — the per-site settings surface (`FORCE_SITE_NAME`, header/logo/favicon overrides) — has no locale, timezone, or date-format field. **FLS's multi-site support does not extend to formatting**: every site on the install shares one `LANGUAGE_CODE`, one `TIME_ZONE`, and Django's built-in `en-us` locale formats (`DATE_FORMAT = "N j, Y"`, `SHORT_DATE_FORMAT = "m/d/Y"`, `TIME_FORMAT = "P"`, `DATETIME_FORMAT` similarly, from Django's own `django/conf/locale/en/formats.py`). Any per-site date-format need is a new capability, not something to route through Django's existing i18n machinery, which is process-wide.

**Options for formatting a stored value** (not choosing one — see detail below):
- **A**: parse with `django.utils.dateparse.parse_date`/`parse_time`/`parse_datetime`, then format the resulting `date`/`time`/`datetime` object with `django.utils.formats.date_format()` (locale-aware, matches whatever every other date on the site looks like) or with the `date`/`time` template filters directly on the parsed object.
- **B**: same parse step, then format with a fixed `strftime` pattern independent of locale (e.g. always `"14 Mar 1987"`), sidestepping locale/format-module questions entirely at the cost of not matching Django's own locale-aware rendering elsewhere (e.g. `FormProgress.start_time` in `list_display`, which Django's admin renders locale-aware for free).
- **Fallback for both**: display the raw stored string unchanged when parsing fails (covers legacy rows written before any validation existed, and any row a bad actor or bug wrote directly).

**Options for the naive-`datetime` problem** — this project already stores whatever comes back from a `datetime-local` input as a naive ISO string in `text_answer` per the idea's decision, so this is purely a *display* question, not a storage one:
- **Read the string as a naive datetime and print it exactly as entered.** No timezone math at all. Cheapest, always round-trips exactly what the person typed, but "10:00" means whatever `TIME_ZONE`/the person's own local zone was on the day they answered — indistinguishable from any other 10:00 on the site.
- **Attach `TIME_ZONE` (`timezone.make_aware`) and localize for display with `timezone.localtime`.** Makes the value comparable/renderable alongside every other aware datetime in the system (`start_time`, `completed_time`, etc.), but silently asserts every respondent answered in the server's configured zone — false for any multi-timezone audience, and `make_aware` on a datetime that falls in a DST-transition gap raises `pytz`/`zoneinfo`-family exceptions Django's own docs flag as unreliable.
- **Display it plainly labelled as a local, timezone-less value** (e.g. render the date and time parts without ever converting), which is the compromise: no incorrect timezone claim is made, but the UI has to say (or imply through absence of a zone abbreviation) that no zone is attached.

None of these is picked here per the assignment; the spec has to choose given who is expected to answer `datetime` questions (a single-site staff form vs. a globally distributed applicant).

---

## Detail

### 1. Parsing: `django.utils.dateparse`

Source: [`django/utils/dateparse.py`](https://github.com/django/django/blob/main/django/utils/dateparse.py) (also documented at the [Django `django.utils.dateparse` module docs](https://docs.djangoproject.com/en/6.0/ref/utils/#module-django.utils.dateparse)).

- `parse_date(value)`, `parse_time(value)`, `parse_datetime(value)` each first try `datetime.date.fromisoformat` / `datetime.time.fromisoformat` / `datetime.datetime.fromisoformat`, then fall back to a regex (`date_re`, `time_re`, `datetime_re`) for the small set of ISO variants `fromisoformat` doesn't accept in older Pythons.
- **Malformed input** (doesn't match any accepted pattern at all — e.g. `"banana"`, `"14/03/1987"`) → **returns `None`**. No exception.
- **Well-formed but impossible values** (e.g. `"2025-02-30"`, `"25:00"`, a datetime with month 13) → the underlying `date`/`time`/`datetime` constructor **raises `ValueError`**, which propagates out of `parse_date`/`parse_time`/`parse_datetime` uncaught.
- `parse_time` returns `None` if the string carries a UTC offset (time-of-day has no offset concept in Python's `time` type); `parse_datetime` does accept an offset (including `Z`) and returns an aware `datetime` in that case — but nothing in this project ever writes an offset into `text_answer`, since the browser's `datetime-local` input never emits one.

**Consequence for a display helper**: it must catch **both** `None` and `ValueError` as "could not parse this value" and fall back to the raw string — catching only one of the two leaves either a `2025-02-30` legacy row or a `banana` legacy row crashing the page instead of degrading.

### 2. Formatting: filters, `django.utils.formats`, and what a site can actually control

Docs: [Format localization](https://docs.djangoproject.com/en/6.0/topics/i18n/formatting/), [built-in template filters `date`/`time`](https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#date).

- The `date` and `time` template filters accept a Python `date`/`time`/`datetime` object (not a string) and an optional format-string argument; with no argument they fall back to the `DATE_FORMAT`/`TIME_FORMAT` (or, with `USE_L10N` behaviour — permanently on since Django 5.0 — the locale's own format) resolved through `django.utils.formats.get_format()`.
- `django.utils.formats.date_format(value, format=None, use_l10n=None)` is the Python-side equivalent of the `date` filter — the thing to call from `QuestionAnswerAdmin.answer_preview`, which is plain Python, not a template. `django.utils.formats.localize(value)` is the more generic entry point that dispatches on the value's type (date, time, datetime, Decimal, etc.).
- The `l10n` template tag library's `{% localize on/off %}` block tag and `localize`/`unlocalize` filters give per-template-region control over whether locale-aware formatting is applied to a value — irrelevant here unless the spec wants *some* surface to show ISO-9601-shaped-but-not-quite output on purpose.
- What FLS actually gets from this machinery, given `LANGUAGE_CODE = "en-us"` and no `FORMAT_MODULE_PATH`: Django's bundled `en` locale formats — `DATE_FORMAT = "N j, Y"` (renders `"March 14, 1987"`), `SHORT_DATE_FORMAT = "m/d/Y"` (`"03/14/1987"`), `TIME_FORMAT = "P"` (`"10 a.m."`/`"10:30 a.m."`), `DATETIME_FORMAT` combining the two. These are fixed process-wide constants unless overridden with a `FORMAT_MODULE_PATH` app (not present).
- **Multi-site complication, confirmed by reading the code**: `freedom_ls/site_aware_models/config.py` defines the only per-site-configurable settings FLS has (logo/favicon/header text), and none of them is locale, timezone, or date format. `LANGUAGE_CODE`/`TIME_ZONE`/`USE_TZ` live in `config/settings_base.py` as ordinary Django settings, which are process-wide, not resolved per `Site` the way `freedom_ls/site_aware_models` resolves other configuration. So: **every site sharing this FLS install will see the same date/time format**, and if the eventual spec wants "an operator can pick their locale's date format," that is new work on top of `site_aware_models/config.py`, not something Django's `USE_I18N`/format-module mechanism gives for free per site.

### 3. Timezones: naive `datetime-local` values under `USE_TZ = True`

Docs: [Time zones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/).

- FLS has `USE_TZ = True`. Every *model* `DateTimeField` FLS already has (`FormProgress.start_time`, `.completed_time`, `TimestampedModel.created_at`/`updated_at`) stores an aware, UTC-backed value, and Django warns at runtime (`RuntimeWarning`) if a naive datetime is ever assigned to one of those fields.
- `QuestionAnswer.text_answer`, however, is a plain `TextField`, not a `DateTimeField` — Django's aware/naive machinery never touches it at write time, and the ISO string it holds for a `datetime` question is, per the idea, deliberately naive (no offset, matching exactly what a `datetime-local` input emits).
- The only place naive/aware matters is if and when this naive string is turned back into a Python `datetime` object for display or comparison:
  - `timezone.is_naive(dt)` / `timezone.is_aware(dt)` — inspect whether a `datetime` carries a `tzinfo`. `parse_datetime("1987-03-14T10:30")` returns a naive `datetime` (no `tzinfo`), so this is always the naive branch for values this project writes.
  - `timezone.make_aware(dt, timezone=None)` — attaches a `tzinfo` (defaulting to the current timezone, i.e. `TIME_ZONE` unless a per-request/per-thread timezone was activated with `timezone.activate()`, which FLS does not appear to use anywhere in `form_engine`/`learner_interface`). Raises on values that fall in a DST-transition gap for zones that observe DST (`TIME_ZONE = "UTC"` never has this problem, but a `FORMAT_MODULE_PATH`/`TIME_ZONE`-overriding deployment could).
  - `timezone.localtime(aware_dt, timezone=None)` — converts an *already-aware* datetime into another zone for display; irrelevant to a value that was never made aware in the first place, and only becomes relevant if the spec picks "attach the site's zone" as its approach.
- Concretely, three approaches (repeated from the summary, with cost spelled out per option):
  1. **Never touch timezone at all — print the naive `date`/`time` parts as parsed.** Cost: a `datetime` answer of `2026-09-12T14:00` is shown as `Sept 12, 2026, 2:00 p.m.` with no zone indication, which is honest (no zone was ever recorded) but ambiguous if respondents span zones.
  2. **`make_aware()` using `TIME_ZONE` and format with `timezone.localtime`.** Cost: asserts the answer was given in the server's `TIME_ZONE` ("UTC" here), which is very unlikely to be true for a `datetime-local` value a person typed into their own browser — the input has no concept of the visitor's zone either, so "UTC" is already a guess the moment it's stored, and formatting compounds the guess by presenting it as fact (e.g. converting a fictitious-UTC value to a fictitious "local" time makes the number *and* the appearance of precision wrong).
  3. **Treat it as a plain wall-clock value and say so in the UI copy** (e.g. no zone abbreviation is ever appended anywhere a `datetime` answer is shown) — functionally identical output to option 1, but framed as a deliberate choice to avoid silently implying a zone, rather than an oversight.

None of the three requires new storage — this is purely how the existing naive ISO string gets read back. The spec has to decide who is answering `datetime` questions (single-timezone staff cohort vs. a distributed applicant pool) to pick between them.

### 4. Graceful degradation for unparseable stored values

There is no schema-level guarantee that `text_answer` for a `date`/`time`/`datetime` question is a valid ISO string of the right kind:
- Rows written **before** any server-side validation exists (decision 2 in `idea.md` is explicitly still open) can hold anything `submitted_text_answer` (`freedom_ls/form_engine/submissions.py:18-20`) let through, i.e. any `.strip()`ed string at all.
- A `FormQuestion.type` can be **changed after answers exist** — nothing in `models.py` prevents an admin from retyping a `short_text` question to `date` once learners have already answered it in free text, which would leave arbitrary strings under a question the display code now expects to be ISO.
- Given §1, the plain, always-safe option is: attempt to parse; on either `None` or `ValueError`, **fall back to displaying the raw stored string unchanged** — the same string the check-your-answers page and admin already show today for every other free-text type. This preserves current behaviour as the worst case rather than hiding or erroring on a row a formatter can't handle. (This is the fallback named in the "options for formatting" list above, not a new fourth option — repeated here because the assignment calls it out separately.)

### 5. Sorting and export: do ISO 8601 strings in `text_answer` sort chronologically?

- **`date`** (`YYYY-MM-DD`) and **`time`** (`HH:MM`, both zero-padded by the browser) sort lexicographically identically to chronological order for any set of *well-formed* values of the *same* shape — this is a standard, well-documented property of the ISO 8601 profile FLS is using (fixed-width, most-significant-first fields, `0`-padded).
- **`datetime`** (`YYYY-MM-DDTHH:MM`) sorts correctly too, because the fixed-width `T` separator sorts identically to any other fixed-width character at the same position across all rows of that shape — but only if every row is exactly the same shape.
- **Where it breaks**, concretely, all stem from FLS's decision to store this in an untyped `TextField` shared by every free-text question type:
  - **Mixed formats in one column**: `QuestionAnswer.text_answer` is not partitioned by question type at the database level — a query that orders `text_answer` across *different questions* (e.g. an educator export sorted by answer text across a whole cohort) mixes date strings with number strings and free text; lexicographic order across genuinely different formats is meaningless, not merely imprecise. Sorting only makes sense scoped to a single `FormQuestion` of a single typed kind.
  - **Times without leading zeros**: the `HH:MM` browser output for `<input type="time">` is always zero-padded (confirmed HTML spec behaviour), but a legacy row typed by hand, imported, or written by test/QA fixtures (`freedom_ls/qa_helpers/management/commands/qa_create_standalone_form_sitting.py` writes `text_answer` directly — grepped as one of the 39 hits above) is not guaranteed to be. `"9:30"` sorts *after* `"10:00"` lexicographically (`"9" > "1"`), breaking chronological order the moment one unpadded value is mixed in.
  - **`T` separator vs a space**: Python's `datetime.fromisoformat` (and hence `parse_datetime`) accepts either `T` or a space as the date/time separator, but the two do not sort identically against each other character-for-character in every locale-independent comparison in the way two `T`-separated values do relative to each other — in practice this only matters if some rows use `"YYYY-MM-DD HH:MM"` and others `"YYYY-MM-DDTHH:MM"` in the same sorted set, which the idea's decision to write `T` (`"YYYY-MM-DDTHH:MM"`) via the browser input avoids going forward, but cannot retroactively guarantee for any hand-written or legacy row.
- No CSV/export path exists yet for `form_engine` data (§0 above), so there is nothing in the current codebase whose sort order is at risk today — this is forward-looking, relevant only if a future spec adds a `form_engine` export or an admin `list_display`/`ordering` on `text_answer`.

---

## Sources

- [`django.utils.dateparse` source](https://github.com/django/django/blob/main/django/utils/dateparse.py)
- [Django utils reference — `django.utils.dateparse`](https://docs.djangoproject.com/en/6.0/ref/utils/#module-django.utils.dateparse)
- [Format localization](https://docs.djangoproject.com/en/6.0/topics/i18n/formatting/)
- [Built-in template filters — `date`/`time`](https://docs.djangoproject.com/en/6.0/ref/templates/builtins/#date)
- [Time zones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/)
- [Django deprecation timeline (`USE_L10N` removal in 5.0)](https://docs.djangoproject.com/en/dev/internals/deprecation/)
- [Django ticket #32873 — Deprecate `USE_L10N` setting](https://code.djangoproject.com/ticket/32873)

## Code read

- `freedom_ls/form_engine/models.py` (`QuestionAnswer`, `FormQuestion`, `FormProgress`, lines 133-178, 294-337, 535-599, 602-623)
- `freedom_ls/form_engine/enums.py` (`QuestionType`, `FREE_TEXT_QUESTION_TYPES`)
- `freedom_ls/form_engine/submissions.py`
- `freedom_ls/form_engine/admin.py` (`QuestionAnswerAdmin`, `QuestionAnswerInline`, `FormProgressAdmin`)
- `freedom_ls/form_engine/templates/form_engine/question.html`, `inputs/short_text.html`, `inputs/long_text.html`, `inputs/number.html`
- `freedom_ls/course_applications/templates/course_applications/check_your_answers.html`
- `freedom_ls/learner_interface/templates/learner_interface/course_form_complete.html`, `course_form_page.html`
- `freedom_ls/base/templatetags/fls_base_filters.py`
- `freedom_ls/site_aware_models/config.py`
- `freedom_ls/site_aware_models/admin_exports.py`
- `config/settings_base.py` (lines 233-243)
- `spec_dd/2. in progress/form_engine data field/idea.md`

status: ok
reason: codebase display surfaces enumerated and Django parsing/formatting/timezone/sorting behaviour researched with citations; no implementation choices made.
