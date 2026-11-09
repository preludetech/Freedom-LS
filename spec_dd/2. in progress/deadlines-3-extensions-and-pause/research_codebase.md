# Research: codebase (deadlines-3-extensions-and-pause)

What this spec touches, reuses or conflicts with. Paths are relative to the repo root. Read from the
worktree at commit `04ea58af0`. (Written in one `Write` straight to the final path: the worker has no
rename tool; the `status:` footer is the completeness marker.)

Headline findings, then detail per brief item.

1. The resolver has one seam where a shift plugs in: `resolve_deadline()` -> `due_instant()` in
   `freedom_ls/deadlines/resolver.py`. Overdue (`is_overdue`), close (`close_instant`) and access end
   (`access_end_instant`) in `consequences.py` are all derived from the same `ResolvedDeadline.due_at`
   plus the policy's grace window. So a shift applied once to `due_at` moves due, close and access-end
   together; "one extension cannot leave an item overdue-while-open" falls out for free if the
   extension is applied in the resolver and not in `consequences.py`.
2. `has_access_ended` / `access_end_instant` are enforced in exactly one place for the player: the
   `DeadlineEnforcingBackend` wrapper (`freedom_ls/course_access/backends.py`), which sets
   `CourseAccessDecision.access_ended_at` / `after_access_ended`. Every learner_interface route reads
   that decision. A pause needs its own branch there, but must NOT reuse `access_ended_at`: the ended
   path finalises open form attempts (`form_submit_and_exit`), which the "frozen" decision forbids.
3. New webhook event names are constrained by `freedom_ls/audit_log/tests/invariants/test_vocabulary.py`:
   each event must use a glossary noun and verb, share its string and label with an audit action unless
   it is in `WEBHOOK_ONLY`, and have a sample in `WEBHOOK_EVENT_TYPE_SAMPLES`. "suspend" is a retired
   word. `pause`/`resume`/`extend` nouns/verbs do not exist yet and need adding (glossary + test sets).
4. Nothing audits an admin action automatically. `record_entry()` (`freedom_ls/audit_log/writer.py`)
   is explicit. The Django admin's built-in `LogEntry` is the only automatic record.
5. `deadlines` has no dependency today on `webhooks`, `comms` or `audit_log`
   (`docs/app_structure.md`, generated). Pause/extension actions need all three: new app edges, no
   cycle (none of them import `deadlines`).

---

## 1. `freedom_ls/deadlines/`

### models.py
- `DeadlineKind` (`fixed` / `relative` / `none`), `_validate_deadline_override(...)` (shape rules).
- `CohortDeadlineOverride` (FK `cohort_registration`) and `LearnerDeadlineOverride` (FK
  `course_progress`, related_name `deadline_overrides`). Both: `collection_item` (null = course time
  limit), `kind`, `due_date`, `due_time`, `due_days_after_registration`, `replaced_value`, `set_by`
  (FK user, SET_NULL), `reason` (TextField, blank OK). `value()` returns a `DeadlineValue`.
  Unique constraints: one row per `(parent, collection_item)` and one time-limit row per parent
  (`unique_learner_override_per_item`, `unique_learner_time_limit_override`).
  Consequence: an override is a REPLACING value (one row per target, the first layer holding a value
  wins outright). It cannot stack and has no "N more days" kind. `DeadlineKind` has no "shift" kind.
- `DeadlineConfigFields` (abstract): `mark_overdue`, `close_items`, `end_course_access`,
  `notify_educators` (all `DeadlineSwitch` inherit/on/off), `grace_window` (nullable
  DurationField), `after_access_ended` (`AfterAccessEnded`). `Meta.constraints` use
  `%(class)s_...` names. Module constants `SWITCH_FIELDS`, `CONFIG_FIELDS` drive admin lists, the
  E001 check and the policy resolver. Six concrete layer tables (all `SiteAwareModel, TimestampedModel,
  DeadlineConfigFields`): `SiteDeadlineConfig`, `OrganisationDeadlineConfig`, `CourseDeadlineConfig`,
  `CohortDeadlineConfig`, `CohortCourseRegistrationDeadlineConfig`,
  `LearnerCourseRegistrationDeadlineConfig` (migration `0003_cohortcourseregistrationdeadlineconfig_and_more.py`;
  latest is 0003, so the next migration is `0004_*`).
- No model for a pause, an extension or a ledger exists.

### resolver.py
- `DeadlineValue` (frozen dataclass: kind, due_date, due_time, due_days_after_registration;
  `from_columns`, `canonical`), `DeadlineLayer(source, value)`, `DeadlineSource` (content /
  cohort_registration / learner), `ResolvedDeadline(due_at: datetime | None, source)`, `NO_DEADLINE`.
- `due_instant(value, registration_date, tz)`: FIXED -> that date; RELATIVE -> `registration_date +
  timedelta(days=N)` on the local DATE (DST-safe); time = `due_time` or `time.max`; returns an aware
  datetime. This is where "whole days" arithmetic already lives (date + days, not instant + 24h).
- `resolve_deadline(layers, registration_date, tz)`: first layer with a value wins; returns
  `ResolvedDeadline`. The natural plug-in for a shift: after picking the value, add the stacked
  extension days and the pause shift days to the DATE before combining with the time (same
  date-arithmetic as the relative branch), keeping end-of-day and DST behaviour.
- `course_deadlines_for(records)` is the bulk path (fixed query count); `course_deadlines(record)` wraps
  it. It builds `cohort_rows`/`learner_rows` dicts keyed `(parent_id, collection_item_id)` and calls
  `_layers()` per item and for the time limit (`collection_item_id=None`). A pause/extension store must
  be fetched here in bulk (one query per table for all records), never per item.
- `is_overdue(resolved, completed, now)`: `due_at is not None and not completed and now > due_at`.
  Takes no pause input. Spec 7's idea (`spec_dd/1. next/deadlines-7-educator-at-risk/idea.md:46-47`)
  assumes "the resolver stops the clock for a paused learner, so a paused learner is not overdue".
  An OPEN pause (no resume yet) has no final shift. Decide: either `ResolvedDeadline` carries a
  `paused` flag / provisional shift `now - paused_at` rounded up, or `is_overdue` and the
  `consequences` functions take pause state. Whichever, it must live in the resolver so all callers agree.
- `registration_date_of(record, tz)` = `record.created_at` in site tz (the start is `CourseProgress.created_at`).
- `content_defaults_for_course(course_id)`, `content_layer_value(row)`, `time_limit_value(days)` are shared
  with admin (`queries.py`).
- Per-placement dates (spec 8): `CoursePartChildDueDate` rows resolved by `_defaults_by_course`; keyed by
  `ContentCollectionItem.pk` so an extension keyed on `collection_item` covers part-placed items.

### policy.py
- `ResolvedDeadlinePolicy` frozen dataclass: the six settings + `sources` (setting -> layer name).
  `DeadlinePolicy` ABC-ish base (`resolve`, `resolve_for` raising NotImplementedError). Loaded by
  `loader.get_deadline_policy()` (`functools.cache`, cleared by autouse fixture in
  `freedom_ls/conftest.py`).
- `LayeredDeadlinePolicy.LAYER_ORDER = registration, cohort, organisation, course, site, settings`;
  `resolve_for(records)` bulk-reads each layer via `_rows_by_owner(model, owner_field, ids, site_id)` using
  `_base_manager`; `_resolve_one(layers)` has three closures: `switch(field)` (inherit/on/off),
  `grace_window()` (None = inherit), `after_access_ended()` (`inherit` = next layer). Defaults from
  `config.DEADLINE_POLICY_DEFAULTS`.
- **Adding pause limits** touches, for EACH new setting: (a) a field on `DeadlineConfigFields` (so all six
  layer tables get it) + a new migration `0004` altering six tables, with matching `CheckConstraint`s
  in `Meta.constraints`; (b) the name in `CONFIG_FIELDS` (and `SWITCH_FIELDS` if a switch);
  (c) a key in `DEADLINE_POLICY_DEFAULTS` (`config.py`) because `checks._default_errors` (E001)
  requires the defaults to name EXACTLY `CONFIG_FIELDS` (and type-checks per field, so the check needs a branch
  per new type); (d) a field on `ResolvedDeadlinePolicy` and a new closure in `_resolve_one`
  (a nullable-int resolver for "max pauses" / a nullable duration for "max length" follows the `grace_window()`
  pattern; "learners may pause" follows `switch()`); (e) `admin.py` `_policy_value_text` handles
  bool/timedelta/str only, so an int needs a branch; `list_display`/`SiteDeadlineConfigForm.Meta.fields` use
  `CONFIG_FIELDS`; `DeadlineConfigForm.clean_*` for negatives; (f) tests in `test_policy.py`, `test_checks.py`,
  `test_models.py`, `test_config.py`. Upgrade notes for spec 2 list `DEADLINE_POLICY_DEFAULTS` as a
  project setting that "must name all six keys": adding keys makes a downstream project's existing
  override fail E001, so this is a breaking settings change to flag in upgrade notes (requires_settings_change).
  Existing field `end_course_access`/`after_access_ended` have no pause relation. Staff in admin are not held to limits (settled).
  Policy reads are via `get_deadline_policy().resolve(record)`; pause limits are only read by spec 4, but
  must exist here.

### consequences.py
Pure functions over `(ResolvedDeadline, ResolvedDeadlinePolicy, completed, now)`:
`shows_overdue`, `access_end_instant` (`time_limit.due_at + grace`, None unless `end_course_access`),
`close_instant`, `is_closed`, `has_access_ended`. No state. A pause check would sit beside these as a
new function (e.g. `is_paused(...)`) or inside the resolver; do not put it in `has_access_ended`.

### queries.py
Per-row admin reads: `content_default_for`, `layers_beneath`, `canonical_beneath` (what `replaced_value`
stores). Only serves the override inline's "Default changed" note. If an extension is a second kind of
row, `layers_beneath` and `canonical_beneath` should ignore it (a stacked extension is not a "value
beneath").

### signals.py
One receiver: `carry_over_deadline_overrides` on `content_engine.signals.collection_items_synced`. It
re-points `CohortDeadlineOverride`, `LearnerDeadlineOverride` and `CoursePartChildDueDate` from a stale
`ContentCollectionItem` to the new one when content moves, via `_CARRIED_PARENTS` (model, parent field)
tuple. **A new per-item extension model keyed on `collection_item` must be added to `_CARRIED_PARENTS`**
or its rows silently stop applying after a content move (same unique-pair logic: needs a unique
`(parent, collection_item)` or the carry's `exclude(parent__in=...)` is wrong for many rows per parent).
Pause records have no `collection_item`, so need no carry.

### admin.py
- Inlines on foreign admins by assignment at import: `CohortCourseRegistrationAdmin.inlines += [...]`,
  `CourseProgressAdmin.inlines += [LearnerDeadlineOverrideInline]`, and `setattr(CourseProgressAdmin,
  "effective_deadlines" / "effective_deadline_policy" / "readonly_fields" / "fieldsets")` with a "Deadlines"
  fieldset. A pause/extension UI on the learner's `CourseProgress` page follows this exact seam
  (`CourseProgressAdmin` lives in `freedom_ls/learner_progress/admin.py`, no actions defined there).
- `DeadlineOverrideInline` (TabularInline subclasses; formset `DeadlineOverrideFormSet` stamps `set_by`
  and `replaced_value`; `ConstraintValidationFormMixin` for constraint-as-form-error).
- `effective_deadlines(model_admin, record)` renders item lines + "Course time limit end" via
  `course_deadlines(record)` and `site_zone_text`; `effective_deadline_policy` renders each setting with
  its source plus "Access ends". Both would need to show pause state and extension days.
- Six `_DeadlineConfigAdmin(SiteAwareModelAdmin)` subclasses, `form = DeadlineConfigForm`,
  `list_display = ["__str__", *CONFIG_FIELDS]`.

### config.py / checks.py / loader.py
- `DeadlinesConfig(AppSettings)` with `declared_settings`: `DEADLINE_POLICY` (dotted path) and
  `DEADLINE_POLICY_DEFAULTS` (dict). Pattern from `freedom_ls/base/app_settings.py` (skill
  `fls-dev:app-settings`). Any other pause setting (e.g. a hard cap) would be added here.
- `checks.py`: E001 (defaults dict shape/types/choices, exactly `CONFIG_FIELDS`), E002 (policy class
  imports and subclasses `DeadlinePolicy`; refuses an uninstalled `freedom_ls.*` app).
- `loader.get_deadline_policy()` cached; tests rely on the autouse cache clear.

### other
`templatetags/deadline_tags.py` only re-exports `local_time`. `apps.py` connects signals in `ready()`.

---

## 2. Player gates and access check

### Access check
`freedom_ls/course_access/backends.py`:
- `CourseAccessDecision` (frozen dataclass): `cta_label`, `cta_url`, `can_self_register`,
  `can_access_content`, funnel copy, `is_accessible_for_free`, `access_ended_at`, `after_access_ended`
  (last two default None). Adding a field is additive (spec 2 did it).
- `_ended_or_none(inner_decision, time_limit, policy)`: if `has_access_ended(...)` returns
  `replace(inner, cta_label=None, cta_url=None, can_self_register=False, can_access_content=False,
  access_ended_at=..., after_access_ended=policy.after_access_ended)`.
- `DeadlineEnforcingBackend(inner)` wraps every backend (`get_course_access_backend()` returns
  `VisibilityEnforcingBackend(DeadlineEnforcingBackend(<COURSE_ACCESS_BACKEND>))`, per spec 2 upgrade notes).
  `get_access`, `get_access_for_request`, `get_access_many` (bulk: reads records via
  `course_progress_by_course_for`, policies via `resolve_for`, deadlines via `course_deadlines_for` only for
  records whose policy `end_course_access` is on). Skips finished courses (`record.completed_time is not None`)
  and anything the inner backend refused. Imports are function-local (`deadlines` depends on `learner_progress`).
  A pause check must (a) run even when `end_course_access` is off (today the policy gate short-circuits),
  (b) be added to all three entry points including `get_access_many`, (c) read the pause store in bulk.
  Order question for the spec: pause beats ended access (a learner paused cannot be "ended"), and
  a completed course never pauses (match "a finished course never ends").
- Nothing is written; "recomputed on every call" is the established contract and fits "evaluated when read".

### Views (`freedom_ls/learner_interface/views.py`)
- `_course_access_decision(user, course)`: hidden-404 then `get_course_access_backend().get_access`.
- `_course_access_redirect(decision, course, *, route, collection_item, course_progress)`: the one gate for
  `view_course_item` (route ITEM, ~l.1466), `form_start` (ITEM, ~1835), `form_fill_page` (ITEM, ~1961),
  `course_form_complete` (FORM_RESULTS, ~2067), `course_finish` (FINISH, ~2210), `form_submit_and_exit`
  (SUBMIT_AND_EXIT, ~2316). Logic: `can_access_content` -> None (open); `access_ended_at is None` ->
  redirect to `course_detail`; else `_ended_route_redirect`.
- `PlayerRoute` enum (ITEM, FORM_RESULTS, SUBMIT_AND_EXIT, FINISH).
- `_ended_route_redirect`: SUBMIT_AND_EXIT is always open to an ended learner; FORM_RESULTS open if
  `completed_attempts(...)` exists; ITEM open only if `_shows_ended_outline(decision)` and the item is complete.
- **Frozen attempt conflict.** `form_submit_and_exit` computes `closed = decision.access_ended_at is not None
  or _is_closed_for_learner(...)` and, when closed, FINALISES the open attempt ("`if not form.submit_on_exit
  and not closed: redirect`" ... `form_progress.complete()` follows). For a paused course (decided: frozen,
  work kept, continued after resume) this route must refuse and write nothing. If pause were encoded as
  `can_access_content=False` with `access_ended_at=None`, `_course_access_redirect` already sends every
  route (including SUBMIT_AND_EXIT) to `course_detail`, which is the frozen behaviour, with no change to
  `_ended_route_redirect`. That is the least-edit option, but it also removes past results (FORM_RESULTS
  is refused too), while "past results, including quiz scores, stay visible" is settled. So either add a
  `paused` branch in `_course_access_redirect`/`_ended_route_redirect` that allows FORM_RESULTS for
  completed attempts only and refuses ITEM/SUBMIT_AND_EXIT/FINISH, or a new `PlayerRoute` rule table.
- `_is_closed_for_learner` and `get_course_index` per-item `is_closed` come from `is_closed(resolved, policy,
  complete, now)` (`consequences`). `form_fill_page` also calls `_blocked_item_redirect(..., refuse_closed=True)`
  using `_player_course_index`. `_render_closed_notice` offers submit-and-exit for an open attempt on a
  closed item; a paused learner never reaches it if the course gate runs first.
- `course_detail` (~l.947): reads `decision`, `_shows_ended_outline(decision)`, builds `children` via
  `get_course_index(... can_access_content=decision.can_access_content, access_ended_outline=...)`; `start_url`/
  `cta_label` None when `access_ended`; passes `"access_ended_at"` to the template.
  `learner_interface/templates/learner_interface/course_detail.html` l.190-192 shows "Your access to this course
  ended on ..." (the paused banner would be a sibling branch), l.284 gates the TOC.
- `dashboard` / `_annotate_registered_courses` (~l.369-418): calls `backend.get_access_many`, stamps
  `course.access_ended_at`, passes deadlines/policy into `_annotate_next_up` only when `can_access_content`.
  Card/row templates: `partials/course_card.html`, `partials/course_row.html`, `partials/course_status_eyebrow.html`,
  `partials/course_status_label.html` branch on `course.access_ended_at` (status `access_ended`). A paused status
  is a new branch in the same four templates + `all_courses` (~l.903 stamps `access_ended_at` too). Template docs in
  these partials enumerate statuses and must be updated. `local_time` tag renders dates.
- `get_course_index` in `learner_interface/utils.py` (~l.480-690): `can_access_content=False` makes every
  row BLOCKED with no progress fetched; `access_ended_outline=True` keeps finished rows linked.
  `DeadlineKeys` / `_deadline_keys` compute due/overdue/closed per row.

### Collision note
`deadlines-4-learner-self-pause` also edits these gates (roadmap collision). Spec 3 should land the gate
shape (a paused field on the decision + one place where routes read it) so spec 4 only adds the control.

---

## 3. `freedom_ls/webhooks/`

- Registry source of truth: `freedom_ls/base/webhook_event_types.py` (importable from settings before
  apps load): `FLS_WEBHOOK_EVENT_TYPES: list[tuple[str, str]]` and `WEBHOOK_EVENT_TYPE_SAMPLES:
  dict[str, dict[str, str | bool | None]]`. `webhooks/config.py` `WEBHOOK_EVENT_TYPES` default = that list;
  `webhooks/registry.validate_event_type()` raises `ValueError` on unknown types; the admin test-send picker
  (`webhooks/forms.py`) is built from the registry; `WebhookEndpoint` test sample comes from
  `WEBHOOK_EVENT_TYPE_SAMPLES.get(event_type, ...)` in `webhooks/models.py` (~l.289) and
  `webhooks/views.py::send_test_result_view` (~l.61). Falls back to `user.signed_up` sample for an unlisted
  type; the audit invariant test requires every type to have its own sample.
- **Existing event names (13):** `user.signed_up`, `course.completed`, `registration.added`,
  `registration.reactivated`, `registration.deactivated`, `cohort_registration.added`,
  `cohort_registration.reactivated`, `cohort_registration.deactivated`, `learner.added`,
  `learner.deactivated`, `learner.reactivated`, `cohort_membership.added`, `cohort_membership.removed`.
  (The integration-points research lists older names `course.registered` etc.; those are stale. Use the above.)
- Firing: `webhooks/events.py::fire_webhook_event(event_type, payload, site=None)` (site from arg, else request
  thread-local, else silently dropped) -> `fire_webhook_event_for_site(event_type, payload, site_id)` (validate,
  create `WebhookEvent`, enqueue `_dispatch_event_task`). Dispatch fans out to active `WebhookEndpoint`s with
  `event_types__contains`, circuit breaker, unique `(event, endpoint)` delivery row (at-least-once guard).
  `presets.py` (`WEBHOOK_PRESETS`: Discord, Brevo) renders templates via `rendering.py` with
  `event.type/id/timestamp/data.*`; presets are not tied to event names, so no change needed.
- Helpers to reuse: `learner_management/utils.py::fire_webhook_event_on_commit(event_type, payload, site)`
  (fires in `transaction.on_commit`), `learner_webhook_payload(learner)` (`user_id`, `user_email`,
  `organisation_id`, `learner_id`). `deadlines` already depends on `learner_management`.
- Payload convention (from `learner_progress/signals.py`, `learner_interface/views.py` ~l.2241,
  `learner_management/utils.py`): `user_id` (raw `user.pk`, not str), `user_email`, `organisation_id` (str),
  `learner_id` (str, in learner events), `course_id` (str), `course_title`, plus event-specific fields
  (`registered_at`, `completed_time` as `.isoformat()`, `course_progress_id`). Registration/completion events carry
  `course_progress_id`; learner events carry `learner_id`. Deadline events should carry both
  (`course_progress_id` identifies the record) plus pause/extension fields (e.g. `paused_at`, `resume_on`,
  `days`, `reason`? — reason is free text; audit `details` rule says no tokens/emails; decide).
- Rule from `audit_log/README.md` "Audit actions and webhook event types": a change has ONE name. A
  webhook that is also an audited change uses the same string and label as the audit action.
  `test_vocabulary.py` enforces: (a) `NOUNS`/`VERBS` frozensets — nouns now: learner, cohort, cohort_membership,
  registration, cohort_registration, role, staff_member, user, course, bulk_action, import, conversation, api_key,
  audit_log; verbs: created, added, deactivated, reactivated, removed, deleted, assigned, moved, renamed, resent,
  completed, committed, signed_up, viewed, issued, revoked, exported; (b) a webhook type not in `WEBHOOK_ONLY`
  (`{"user.signed_up", "course.completed"}`) must exist as an audit action with the same label;
  (c) `test_webhook_only_event_types_are_exactly_the_ones_listed` asserts WEBHOOK_ONLY equals the audit-less set
  exactly; (d) every webhook type has a sample; (e) retired words `unregister, suspend, revoke, granted,
  reregister`. So for `registration.paused`-style names: either add noun/verbs to the test + glossary
  (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`, "Changes" section) and register matching audit
  actions in `audit_log/actions.py::FLS_AUDIT_ACTIONS` (with `group` following `NOUN_GROUPS`, `describe` renderer),
  or add to `WEBHOOK_ONLY` (and fix the exact-set test). Spec 5 will add `deadline.missed` the same way, and
  spec 5's idea relies on spec 3's "resume webhook" firing from the sweep.
- Docs to update: `freedom_ls/audit_log/README.md` table (if audited), a webhooks doc listing events
  (grep `docs/` for `registration.deactivated` to find it).

---

## 4. `freedom_ls/comms/` notifications

- `comms/notify.py::raise_notification(*, user, category, target, site_id, data: dict[str, str])`: validates
  the category and `%(placeholder)s` data synchronously (ValueError on missing keys), writes the
  `Notification` row in `transaction.on_commit(..., robust=True)`, enqueues `deliver_notification` per
  `NOTIFICATION_DELIVERY_BACKENDS`. An FLS category absent from `NOTIFICATION_CATEGORIES` = silent opt-out.
  `rollup=True` categories fold repeated unread events on the same target.
- Registry: `freedom_ls/base/notification_categories.py::FLS_NOTIFICATION_CATEGORIES` (list of
  `NotificationCategory(key, label, icon, message, url_builder, colour, rollup)`). Today exactly two:
  `course.registered` (message "You've been registered for %(course_title)s", `url_builder` =
  `freedom_ls.learner_interface.notification_urls.course_home_url`) and `bulk_action.finished`.
  (The integration research's `message.received` is not in this list; ignore.) `comms/checks.py` rejects duplicate keys.
- **Deadline specs 1 and 2 raise no notifications** (grep of `deadlines/` finds no `raise_notification`;
  `comms` has no deadline category). Only `learner_progress/signals.py::_ensure_and_announce` raises
  `course.registered` and only `if notify and not registration.self_registered` — the "somebody else acted"
  rule in code, and the pattern to copy: pass `target=registration.course`, `site_id=...`, `data=
  {"course_title": ...}`.
- New categories needed here (three, or one with a verb in `data`): paused / resumed / extended by staff.
  Each needs an `icon` name from `freedom_ls/icons` mapping, a message with placeholders, and
  `url_builder` (reuse `course_home_url` or `course_detail`; a paused course cannot be "opened", so the target
  should be course detail, check `learner_interface/notification_urls.py`). The `fls-dev:notifications`
  skill's five-question checklist applies. The skill says: user not the actor; burst of events on one
  target should be `rollup=True` (a staff pause + extension in a row for one course = one bell row).
- Dependency: `deadlines` -> `comms` is a new edge (comms imports only accounts/base/site_aware_models). `learner_progress`
  already imports `comms` function-locally in `_ensure_and_announce`.

---

## 5. Progress, registrations, audit log

- `learner_progress/models.py::CourseProgress`: `learner`, `course` (PROTECT), exactly one of
  `learner_registration` / `cohort_registration` (check constraint `course_progress_has_exactly_one_grant`),
  `created_at` (auto_now_add = the registration date and the start of relative deadlines),
  `started_at` (first content access, not the same), `last_accessed_time`, `completed_time`,
  `progress_percentage`, `updated_at` (changed-since signal; `UpdatedAtInUpdateFieldsMixin`). One record per
  learner per registration. A cohort move mints a new `CourseProgress`, so a pause/extension keyed on the
  record stays behind with the old one (the glossary notes the same for `LearnerDeadlineOverride`).
  `deadline_overrides` is the reverse name used by the override model; pick another for a pause store.
- Registrations (`learner_management/models.py`): `LearnerCourseRegistration` (`is_active`,
  `self_registered`, `registered_at` auto_now_add, `loaded_is_active` tracking mixin for post_save diffing) and
  `CohortCourseRegistration` (`is_active`, `registered_at`). A pause must leave `is_active` alone (settled), so
  the existing `registration.deactivated` receivers (`learner_progress/signals.py::ensure_course_progress_on_learner_registration`,
  `_announce_deactivated`) never fire for it. `latest_registration(user, course)` in `learner_management/queries.py`
  exists. Pause belongs per `CourseProgress` (a cohort registration fans out to many records), not on a registration.
- Audit: **not automatic.** `record_entry(action, actor, target, target_label, organisation, subjects, reason,
  details, run_id, site)` raises `ValueError` for unregistered action codes or `reason` > `REASON_LENGTH` (500);
  call inside the `transaction.atomic()` making the change. Existing writers are service functions
  (`learner_management/learner_actions.py::record_learner_entry`, `utils.py::record_cohort_entry`) and
  `api_admin` (admin-side `record_entry` for `api_key.issued`/`revoked`). So the admin pause/extend must call
  `record_entry` itself (roadmap spec 6 says "Every change is audit-logged" for the educator interface; the idea
  here does not require audit, but the audit README says "A change has one name" for anything that also fires a
  webhook, so shared codes are the cheapest consistent path). `Organisation` for the entry: use
  `learner.organisation`. Subjects: the learner. `audit_log` entry display groups by `NOUN_GROUPS`; a new noun
  needs a group mapping in test + `AUDIT_ACTION_GROUPS`.
- Django admin `LogEntry` records admin saves of models but not custom actions.

---

## 6. Admin patterns

- Base: `freedom_ls/site_aware_models/admin.py::SiteAwareModelAdmin(unfold.admin.ModelAdmin)` with
  `exclude = ["site"]` and a CSS Media; django-unfold IS used (`unfold.admin.ModelAdmin`, `TabularInline`,
  `unfold.decorators.action`/`display`, `UnfoldAction`). Helpers: `admin_page_context(request, model_admin, title)`
  (use for any custom admin page so the shell/breadcrumb render), `admin_change_link`, `SiteAwareExportModelAdmin`,
  `ConstraintValidationFormMixin` (`site_aware_models/forms.py`) that turns constraint violations into form errors.
- Custom admin actions with an intermediate page: `freedom_ls/api_admin/admin.py` + `views.py::revoke_view` is the
  closest pattern: unfold `@unfold_action(description, url_path, permissions=["change"])` for the detail button +
  `@admin.action` for the changelist; `get_urls()` adds `path("revoke/", self.admin_site.admin_view(partial(revoke_view,
  model_admin=self)), name="freedom_ls_api_apikey_revoke")`; the view checks `has_change_permission`, shows a confirm
  template on GET (`admin/api_admin/revoke_confirm.html`), applies under `transaction.atomic()` with
  `select_for_update()` on POST (so a repeat post is idempotent), calls `record_entry`, then `model_admin.message_user`
  and a redirect. `get_actions_detail` can hide the button conditionally. Another: `webhooks/admin.py`
  `actions_detail = ["send_test_action"]` with form/result views; `reports/admin.py` `actions_list`.
- **No existing admin "action with a reason" form.** A reason field exists on the educator side:
  `educator_interface/forms.py::ReasonForm` and `educator_interface/actions.py::ReasonMixin` (panel actions, not Django
  admin; `educator_interface` is above `deadlines` so deadlines must not import it). Override rows carry `reason`
  TextField; `REASON_LENGTH` (500) is the audit length cap. Spec 6 will reuse spec 3's service functions from the
  educator interface, so the admin action should be a thin shell around service functions in `deadlines`
  (e.g. `deadlines/pauses.py` / `extensions.py`: `pause_course(record, actor, reason, resume_on)`, etc.) that
  also write audit, fire webhooks and raise notifications. That keeps spec 6 and spec 4 from copying logic.
- Where to attach: a "Pause / Resume / Extend" detail button set on `CourseProgressAdmin` (via the same
  import-time `setattr` seam in `deadlines/admin.py`), because the record is the unit; extending one item or the time
  limit is also possible from the existing `LearnerDeadlineOverrideInline` page. The admin readonly "Effective
  deadlines" block there must reflect pause + extensions.
- Admin tests: `deadlines/tests/test_admin.py` uses `staff_client` and `mock_site_context` fixtures.

---

## 7. Housekeeping / sweep hook for spec 5

- `freedom_ls/deployment/housekeeping.py::run_housekeeping_sweeps()` returns `HousekeepingOutcome(sweep_failures,
  findings, notes)`; each sweep is its own `try/except SWEEP_FAILURES`/`DatabaseError` block appended in sequence
  (existing: `prune_db_task_results`, `clearsessions`, late unpicked task check, orphan task reap, orphaned report
  reap, stale import previews, three bulk-record sweeps over `BULK_RECORD_MODELS`). Run by `fls_run_housekeeping`
  (management command; deployment provides cadence; doc `docs/product/deployment.md`). Sweeps use `_base_manager`
  and explicit `site_id` (no request). `deployment` depends on `base, content_engine, learner_management, organisations,
  panel_framework, reports`: it does not depend on `deadlines`; spec 5 adds that edge.
- `fire_webhook_event_for_site(event_type, payload, site_id)` is the sweep-safe webhook entry.
- **What spec 3 must leave:** (1) a "resume announced" marker on the pause record (nullable `resume_announced_at`
  or `ended_notified_at`), because a planned resume takes effect on read with no write; spec 5's sweep then selects
  `planned_resume_on <= today AND marker IS NULL` (idempotent, runs late/twice safely) and fires the resume webhook
  through the same function a staff resume uses; (2) that function must take `site_id` and no request (the fire helper
  needs `site=`); (3) an index on `(status/ended_at, planned_resume_on)` or equivalent for the sweep query; (4) a
  queryset/helper `paused_course_progress_ids(now)` or an `is_paused_at(record, now)` the sweep calls to skip reminders
  ("No paused learner gets a reminder").
- A staff resume done early must set the same marker so the sweep never fires a second resume webhook.

---

## 8. Tests layout and factories

- `freedom_ls/deadlines/tests/`: `test_resolver.py` (88 tests; ~every resolver rule), `test_policy.py`, `test_consequences.py`,
  `test_models.py`, `test_admin.py`, `test_checks.py`, `test_config.py`, `test_loader.py`, `test_queries.py`,
  `test_signals.py`, `templatetags/test_deadline_tags.py`, `helpers.py` (writes course/part/topic files for content-load tests).
- Factories: `freedom_ls/deadlines/factories.py` — `CohortDeadlineOverrideFactory`, `LearnerDeadlineOverrideFactory`
  (default: time-limit row, 14 days relative), and `<Layer>DeadlineConfigFactory` for each of six layer tables, all
  `SiteAwareFactory`. Related: `learner_progress.factories.CourseProgressFactory`, `learner_management.factories`
  (`CohortCourseRegistrationFactory`, `LearnerCourseRegistrationFactory`, `CohortFactory`, `LearnerFactory`),
  `content_engine.factories.CourseFactory`, `organisations.factories.OrganisationFactory`. New factories
  (pause, extension) belong here.
- Cross-app tests that will need paused cases: `course_access/tests/test_backends.py` (11 refs to `access_ended_at`),
  `learner_interface/tests/views/test_course_access.py` and `test_course_player.py`, `learner_interface/tests/test_utils.py`,
  `deadlines/tests/test_consequences.py`, `qa_helpers/management/commands/qa_create_deadlines_seed.py` (+ its test) —
  the QA seed command should gain a paused learner.
- Autouse fixture in `freedom_ls/conftest.py` clears `get_deadline_policy` cache; webhook tests under `webhooks/tests/`
  (`test_events.py`, `test_views.py` test-send); audit invariants in `audit_log/tests/invariants/test_vocabulary.py`.
- Test-skill: `fls-dev:testing`; app map generator (`tests/test_generate_app_map.py`) checks `docs/app_structure.md` is
  current, so new app edges (`deadlines` -> `webhooks`/`comms`/`audit_log`) regenerate that doc.

---

## 9. Conflicts and in-flight work

- `spec_dd/2. in progress/` siblings (briefly read): `design_learner-interface-deadlines` (restyle how deadlines/windows
  look to learners — touches the same templates: `partials/deadline_labels.html`, `course_card.html`, `course_row.html`,
  `course_status_eyebrow.html`, `course_detail.html`; expect merge conflicts in templates; the paused banner/status
  should be a small additive branch), `compliance-form-randomization` (form_engine and the quiz flow; shares
  `form_fill_page`), `learner-facing-ux-refinements`, `educator-interface-13-staff-roles`, `design_educator-interface-bulk-action`
  (spec 6's bulk extension later), `downstream_bugs_oct_29`, `educator-interface-course-content-preview`,
  `auto-run-tailwind-watch`, `new-register-design-process`, `test-organisation-and-hygene-2-*`. None mentions pause or extension.
- `deadlines-7-educator-at-risk` is in `spec_dd/1. next/` (status "ready", not in progress; roadmap says it "runs beside" spec 3 and
  edits `reports/at_risk.py`). It states that after spec 3 "the resolver stops the clock for a paused learner, so a paused learner is not
  overdue" (idea.md l.46-47): spec 3's resolver contract must make an open pause visible to `is_overdue` consumers, or spec 7 reads
  pause state itself. Agree the call shape (`course_deadlines_for` bulk) so it does not N+1 on the cohort report.
- Roadmap collisions (spec_dd/1. next/roadmap.md l.151-154): spec 3 and spec 4 both edit the player gates (spec 4 blocked on 3, so
  spec 3 sets the shape); spec 5 adds a housekeeping sweep as do `retry-sent-emails` and `file-scanning` (merge in
  `deployment/housekeeping.py` is spec 5's problem; spec 3 does not touch it).
- `user-communication-2-notification-email` (not landed): staff-action notifications are in-app only until then.
- Spec 1/2 behaviour that must be preserved: `registration_date_of` = `created_at` in site tz; a time-limit override of
  fixed date or day count "restores ended access" (admin TIME_LIMIT_HELP); a finished course (`completed_time`) never ends;
  completed items are never overdue or closed; grace window applies to both close and access end; part-placement values
  keyed by `ContentCollectionItem`.
- `docs/app_structure.md` is generated; `course_access -> deadlines` and `learner_interface -> deadlines` exist already.
- Wording: use the project glossary (`claude_plugins/fls-dev/skills/domain-glossary/SKILL.md`); learner-facing copy says
  "Deadline"/"Missed deadline", never "Due"/"Overdue"; "deactivated/reactivated" are the only `is_active` verbs, and "suspended"
  is retired, so the paused state must not be named "suspended".

## Design hooks the spec can lean on (findings, not decisions)

- A single shift applied inside `resolve_deadline()` to the date part of every layer's value (override or content) gives
  stacking extensions + pause shift with end-of-day preserved. The per-item extension store needs `(course_progress,
  collection_item)` with null for the time limit, mirroring `LearnerDeadlineOverride`, and a carry entry in `signals._CARRIED_PARENTS`.
- Whole-course shift ("every unmet deadline and the time limit by N days") and a resume's rounded-up days share one
  maths function; "unmet" = item not complete at the time of the shift, so the whole-course shift and a resume must either
  write per-item rows or store a record-level day count that the resolver applies to items not completed at resume time. A
  record-level count applied at read time would also shift items completed later (harmless: completed items are never
  overdue) but would move the displayed due date of an item met BEFORE the pause if the item is read after; "met deadlines are
  untouched" therefore needs either per-item snapshots or a rule that a completed item's displayed date ignores the shift.
- Pause record fields the downstream specs need (per the idea): `course_progress` FK, `started_at`, `planned_resume_on`
  (date or datetime), `ended_at` (null while open), `reason`, `started_by`, `ended_by`, source/actor kind (staff now, learner for spec 4),
  `shift_days` stored at resume, `resume_announced_at` marker. Evaluated-when-read means status is derived:
  open = `ended_at is None and (planned_resume_on is None or planned_resume_on > now)`.
- Counting pauses for spec 4's "how many pauses" limit = count of pause rows per `CourseProgress` (or per registration across a
  cohort move: decide).

status: ok · reason: complete, every brief item covered
