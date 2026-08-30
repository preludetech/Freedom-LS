# Research: what queued work implies about today's schema

Every item currently queued in `spec_dd/1. next/` and `spec_dd/2. in progress/` (excluding this
cleanup's own siblings) implies **nothing** about today's schema: built as sketched, each one adds a
new table and/or a nullable field to a model that already exists or is itself brand new. Nothing
forces a change to an existing table's shape, keys, or uniqueness. Two items get closer treatment
because the task asked for it, not because they change that answer:
`debt-simplify-course-progress-tracking` confirms the cleanup should leave `CourseProgress` alone
rather than touch it again, and `content_snapshots` has a stale dependency boundary worth recording
before it is specced.

The one structural question the previous pass left open — a run/registration id wanted
independently by `better_course_progress_tracking` and `xapi_implementation` — is now closed:
`course.registered` already fires `course_progress_id` (`freedom_ls/learner_progress/signals.py:154`,
asserted at `freedom_ls/learner_progress/tests/test_registration_signals.py:320`). See §6.

## Verdict table

| # | Item | Verdict | Why |
|---|---|---|---|
| 1 | `certificates` | implies nothing | New, additive `Certificate` model FK'd to `CourseProgress` (`freedom_ls/learner_progress/models.py:106`), which today is a stable-enough frozen completion record because no retake mechanism exists yet. See §4. |
| 2 | `compliance-exam-remediation` | implies nothing | Optional per-answer explanation/reference text is a new nullable field on `FormQuestion` (`freedom_ls/form_engine/models.py:125`) or `QuestionOption` (`:172`), the same shape as their existing `question`/`text` fields. |
| 3 | `content-glossary-widget` | implies nothing | A Cotton component. Its one open design fork ("shared glossary registry" vs. two self-contained widgets) would, if taken, add one small new table — it does not touch anything that exists. |
| 4 | `content-links` | implies nothing | A URL-resolution and template bug fix (`freedom_ls/content_engine/templates/cotton/content-link.html:12`, `Topic.preview_url()` at `freedom_ls/content_engine/models/topics.py:18`). No model changes. |
| 5 | `content-plugin-distribution` | implies nothing | Governs how Claude Code plugins reach content-author repos. Touches no FLS database at all. |
| 6 | `critical_security_fixes` | implies nothing | Authorisation and queryset-filtering fixes in `panel_framework`/`educator_interface`. Its one live design fork, "introduce a `view_course` object permission," is a new `Permission` row through Django's/guardian's existing generic permission tables (already used for cohort grants) — no new table. |
| 7 | `debt-cotton-vs-partials` | implies nothing | A template/partial placement convention. No models. |
| 8 | `debt_markdown_rendering_package_isolation` | implies nothing | `markdown_rendering` has no `models.py` at all and already carries a compliant `freedom_ls_markdown_rendering` label (`freedom_ls/markdown_rendering/apps.py:7`). See §3. |
| 9 | `debt-simplify-course-progress-tracking` | implies nothing, and settles the question this cleanup asked about | See §1. |
| 10 | `educator-interface-full-polish` | implies nothing | Panel-framework layout, CSS and template polish against an existing design. No new fields. |
| 11 | `educator-interface-quick-view-panel` | implies nothing | Reads existing `TopicProgress`/`FormProgress`/`CourseFormAttempt` fields only; any field needing new computation is explicitly deferred by the idea itself (`idea.md:60`). |
| 12 | `extract-icons-app` | implies nothing | `freedom_ls/icons` has no `models.py` at all (confirmed: no `freedom_ls/icons/**/models.py` file exists). See §3. |
| 13 | `learner-management-actions` | implies nothing | The cohort-move action re-points `CourseProgress.cohort_registration` (`freedom_ls/learner_progress/models.py:126`) at a different `CohortCourseRegistration` row. That FK carries no immutability constraint — only "exactly one of the two FKs is set" (`:171-183`) — so re-pointing it is an `UPDATE`, not a schema change. |
| 14 | `multi-factor-authentication` | implies nothing | A device/secret table is new and FK's to `User`. "Configurable per test" is a new nullable boolean on `Form`, the same shape as its existing `submit_on_exit` (`freedom_ls/form_engine/models.py:63-69`). |
| 15 | `panel-framework-tables-and-panel-api-upgrades-and-design` | implies nothing | `Panel`, `Tab`, `PanelAction` are plain Python classes, not Django models. The whole workstream is code structure. |
| 16 | `post-mvp` | implies nothing | Per-seat billing scoped to an organisation now has its anchor: `Learner.objects.filter(organisation=..., is_active=True)` (`freedom_ls/learner_management/models.py:51-77`) — landed since the prior pass treated it as an in-flight sibling assumption. The payment gateway is a wholly new, additive integration. |
| 17 | `re-consent-idea.md` | implies nothing | `LegalConsent` (`freedom_ls/accounts/models.py:161-212`) and `SiteSignupPolicy` (`:137-158`) are unchanged. A grace-period toggle is a new nullable field on `SiteSignupPolicy`, the same shape as its existing booleans. |
| 18 | `referral-link-tracker` | implies a decision, already made | See §3. |
| 19 | `student-communication` | implies nothing | A registration-scoped comms config would FK into `LearnerCourseRegistration`/`CohortCourseRegistration` following the precedent `CourseProgress` already set (exactly-one-of-two-FKs, `freedom_ls/learner_progress/models.py:119-132`). Its own idea text still says `UserCourseRegistration` (`idea.md:129`, `:160`) — a name `learner-terminology-rename` retired. That is an idea-freshness gap to close before spec, not a schema question. |
| 20 | `student-interface-course-color-token-simplification` | implies nothing | CSS custom properties only. |
| 21 | `system_qa` | implies nothing | A QA slash-command and report format. Touches no FLS models. |
| 22 | `user-data-retention-idea.md` | implies nothing, and is the correct owner of this question | See §5. |
| 23 | `xapi_implementation` | implies nothing to today's schema | Its event table's registration/attempt concept should key off `CourseProgress.id`, which now exists for exactly this reason. See §6. |
| 24 | `compliance-form-randomization` | implies nothing | The sub-page "group" primitive is a new model sitting between `FormPage` (`freedom_ls/form_engine/models.py:78`) and `FormContent`/`FormQuestion` (`:107`, `:125`), with new nullable FKs from those two. `realized_order` is a new JSON field on `FormProgress`, the same shape as its existing `scores` (`:207-209`). |
| 25 | `content_snapshots` | implies nothing to today's schema, but its own dependency boundary is stale | See §2. |

## 1. `debt-simplify-course-progress-tracking` — leave `CourseProgress` alone

The idea's complaint is real and already visible in the code, not hypothetical: `course_progress_for`
(`freedom_ls/learner_progress/queries.py:125-152`) takes a bare `(user, course)`, resolves which
registration wins through `learner_for_course`, and only then looks up the `CourseProgress` row —
precedence logic (`cohort_registration` vs. `learner_registration`, `-is_active`, `-registered_at`)
that `course_progress_by_course_for` (`:162-260`) repeats for the bulk case. That guesswork is exactly
what the idea wants deleted, and every view that opens a course today calls into it with only a course
in hand (`freedom_ls/learner_interface/views.py:153`, `:820`, `:1269`).

The fix the idea describes does not need a new column. `CourseProgress` already carries a UUID
primary key (`SiteAwareModel.id`, `freedom_ls/site_aware_models/models.py:79-83`) and already supports
"a learner registered for the same course in two different ways" as two distinct rows — its own
docstring says so (`freedom_ls/learner_progress/models.py:106-107`), and its constraints
(`:158-184`) are what make two coexisting records legal. Passing `CourseProgress.id` in the course
player's URL and reading the record directly, instead of re-deriving it from `(user, course)` on every
request, removes the guesswork the idea is asking to remove without altering what `CourseProgress`
stores or how it is keyed.

This is why the answer to the question this cleanup asked is the opposite of "leave progress models
alone because they are about to move again": `debt-simplify-course-progress-tracking` does not
restructure `CourseProgress` a second time. It is a routing and query-layer simplification that the
shape `better_course_progress_tracking` just shipped already supports. The pre-deploy cut can safely
apply hardening (timestamps, `PROTECT`, indexes — see `research_field_level_hardening.md`) to
`CourseProgress`/`TopicProgress`/`CourseFormAttempt` now; nothing here reopens their shape.

## 2. `content_snapshots` — the QuestionAnswer question isn't its to own, and its own scope is stale

**The parked question stays parked, for the reason this cleanup's Decision 3 already gives.**
`content_snapshots`' public surface is `take_snapshot(content_obj)` / `get_latest_snapshot(content_obj)`
/ `get_snapshot(snapshot_id)` (`idea.md:52-56`) against `content_engine` objects — it snapshots
*authored content*, and says explicitly that wiring any consumer to it is out of scope
(`idea.md:57`, `:75`). Freezing `question_text` and `selected_option_texts` on `QuestionAnswer` at
answer time is a different thing: it is about what a *learner's answer row* should remember, not
what a *piece of content* looked like. `content_snapshots` gives a future consumer the mechanism to
close that gap — a caller could store the `snapshot_id` returned by `take_snapshot(form)` on
`FormProgress` at completion — but it does not decide to do so, and nothing in its idea, spec-phase
open questions, or success criteria commits to it. The gate this cleanup's idea.md already names
(`idea.md:115-117`) — "before the first learner answer exists," which is deploy time, not today —
still holds, and still isn't this cleanup's or `content_snapshots`'s to close.

**Its own scope statement no longer matches the tree it will be built against.** The idea requires
"no imports from apps other than `content_engine`, `accounts`, and `site_aware_models`" (`idea.md:23`,
repeated at `:75`), but also lists `Form`, `FormContent` and `FormQuestion` — "full body, not
truncated; with options" — as in-scope content models (`idea.md:30-37`). Those three no longer live in
`content_engine`: `extract_forms_into_seperate_app` moved them to `form_engine`
(`freedom_ls/form_engine/models.py:43`, `:107`, `:125`), and `content_engine/models/__init__.py`
re-exports only `Activity`, `ContentCollectionItem`, `Course`, `CoursePart`, `File`, `Topic` — no
`Form`. The dependency graph confirms the direction: `content_engine --> form_engine`
(`docs/app_structure.md:49`), not the reverse, so `content_snapshots` cannot reach `Form` through
`content_engine` at all. Whoever specs this needs `form_engine` as an explicit fourth dependency
(`freedom_ls/content_base` is the natural fifth, since it is what both `content_engine` and
`form_engine` already share for `BaseContent`/`TitledContent`/`MarkdownContent`,
`freedom_ls/content_base/models.py:10-93`, and sits below both in the graph,
`docs/app_structure.md:45-46`) — or the idea's form-content scope needs to shrink. This is a
dependency-list correction for the idea document, not a schema decision; nothing about it is expensive
to fix later.

## 3. Apps headed out of FLS — the `SiteAwareModel`/`freedom_ls_` exemption, checked against all three

This cleanup's Decision 5 (`idea.md:143-149`) already settles that self-contained, extractable apps
are a named exception to the `SiteAwareModel` convention, with `referral-link-tracker` as the worked
example. Checking all three apps the prompt named against that decision:

- **`referral-link-tracker` wants the exemption and has already reasoned through it.** Its own idea
  is explicit twice over: it "must **not** ... subclass FLS base classes (`SiteAwareModel`)"
  (`idea.md:29-33`), restated at the model layer (`:102-106`) with an optional `django.contrib.sites`
  FK instead. The idea also catches and overrides its own sibling research doc, which sketches models
  subclassing `SiteAwareModel` directly (`research_data_model.md:170, 194, 221-224`) — flagged as
  needing translation before spec (`idea.md:196-199`). Nothing further to decide here; the exemption
  this cleanup already wrote down is exactly what the idea asks for.
- **`extract-icons-app` has no model to exempt.** `freedom_ls/icons/apps.py` declares
  `name = "freedom_ls.icons"` with no explicit `label` and no `models.py` anywhere under
  `freedom_ls/icons/` — zero tables, so the `SiteAwareModel` question never arises, and the
  `freedom_ls_` label question (which this cleanup's own do-now finding #1 already flags as
  zero-risk for `icons` precisely because it has no tables) is likewise moot for this app. The
  extraction idea's own decisions (`idea.md:76-81`) rename the package (`django-semantic-iconify`)
  and its settings prefix (`SEMANTIC_ICONIFY_*`) — an app identity change this cleanup's `freedom_ls_`
  labelling work should not pre-empt by relabelling `icons` first.
- **`debt_markdown_rendering_package_isolation` is not actually proposing an extraction, and the
  premise doesn't fit it.** `markdown_rendering` has no `models.py` either, and unlike `icons` it
  already carries a correct, explicit `label = "freedom_ls_markdown_rendering"`
  (`freedom_ls/markdown_rendering/apps.py:7`). Its idea is entirely about relocating misplaced test
  code across an existing dashed dependency edge (`idea.md:39-93`) so the app's tests stop reaching
  into `content_engine`; it never proposes publishing `markdown_rendering` as a separate installable
  package the way `extract-icons-app` and (eventually) `referral-link-tracker` do. There is no
  `SiteAwareModel`/`freedom_ls_` exemption question here at all, because there is no model and no
  extraction plan — the three apps do not, in fact, share one implication.

## 4. `certificates` — re-derived against what shipped

The old research bound certificates to a "frozen completion record" and named the sibling spec's
(then-proposed) `CourseRun` model as that record. `CourseRun` did not ship.
`better_course_progress_tracking` landed a different shape: `CourseProgress` keyed on `learner` plus
exactly one of `learner_registration`/`cohort_registration` (`freedom_ls/learner_progress/models.py:106-184`),
and its own decision record states plainly that **nothing in that work retires a record** — no
resolver reads `is_active` as a retirement signal, and there is deliberately no retake trigger yet
(`spec_dd/3. done/2026-08-28_14:19_better-course-progress-tracking/1. spec.md:206-259`). A `CourseProgress`
row's `completed_time` is therefore not reset or superseded by anything in the codebase today —
stable enough for `certificates` to FK against directly, the same way any other content-bearing model
FKs against a stable row.

That stability is conditional on retake staying unbuilt. `learner-management-actions` names the
"explicit retake trigger" as work `better_course_progress_tracking` deliberately left unbuilt
(`spec_dd/1. next/learner-management-actions/idea.md:111-112`), and when it lands, deciding whether a
retake resets the same `CourseProgress` row or mints a new one is that spec's question to answer, not
this cleanup's or `certificates`'s. `certificates` needs nothing from the pre-deploy cut: a new,
additive `Certificate` model (hash/token, public verify URL) FK'd to `CourseProgress`.

## 5. `user-data-retention-idea.md` — confirmed as the sole owner of `delete_user()`

This cleanup's own idea.md already declares retention out of scope and defers it here by name
(`idea.md:95`: "Retention, anonymisation, and a canonical `delete_user()` flow... belongs to
`user-data-retention-idea.md`"), and the idea file itself agrees — it is explicitly "the placeholder
for a future spec," not an implementation (`user-data-retention-idea.md:7`, `:30-32`). Every user-side
CASCADE the pre-deploy cut leaves in place — `LegalConsent.user`
(`freedom_ls/accounts/models.py:174-177`), `FormProgress.user` (`freedom_ls/form_engine/models.py:201-203`),
`CourseApplication.user` (`freedom_ls/course_applications/models.py:32-35`), and the rest — is
compatible with this idea's own stated options (hard-delete, anonymise-in-place, or snapshot-and-detach,
`idea.md:16-19`): CASCADE is one legitimate default among the three the future spec will choose per
model, not a decision this cleanup is making on the retention spec's behalf. Nothing here needs
revisiting before deploy; the retention questions are all still open exactly where this idea leaves
them.

## 6. Convergent demand — the run/registration id gap is closed, and two more items lean on the same shape

**The gap the prior research flagged is shipped, not merely planned.** `better_course_progress_tracking`
landed with `course.registered` firing `"course_progress_id": str(record.id)`
(`freedom_ls/learner_progress/signals.py:145-156`), asserted by
`freedom_ls/learner_progress/tests/test_registration_signals.py:320`. `xapi_implementation` wants
exactly this concept — xAPI's own `Context` object has a standing `registration` (UUID) field
(`spec_dd/1. next/xapi_implementation/research_xapi_standard.md:13`) — and its idea already commits
to `SiteAwareModel` for its own new event table (`0. idea.md:9`), so it is building fresh tables
regardless. The one thing worth writing down for whoever specs it: point the event table's
registration/attempt concept at `CourseProgress.id` (via `CourseFormAttempt.course_progress_id`,
`freedom_ls/learner_progress/models.py:254-256`, for form-shaped events) rather than re-deriving or
reinventing attempt identity that already exists.

**A second, independent feature is leaning on the same shape.** `student-communication`'s
registration-scoped comms config (§19 above) wants to attach to "a specific `UserCourseRegistration`
*or* `CohortCourseRegistration`" (`idea.md:129`) — precisely the exactly-one-of-two-FKs shape
`CourseProgress` already uses (`freedom_ls/learner_progress/models.py:119-132`, constraints at
`:158-184`). Nothing needs building now — the config model doesn't exist yet, and inventing it ahead
of a spec would be exactly the risk this task was warned against — but it is a second data point that
this shape is becoming a house pattern, not a one-off.

status: ok
